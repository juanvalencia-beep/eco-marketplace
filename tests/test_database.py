import sqlite3
import threading
import time

import pytest

ANA = ('Ana Pérez', 'ana.perez@example.com')


def stock(conn, tienda_id=1, producto_id=1):
    row = conn.execute('SELECT cantidad_stock FROM inventario WHERE tienda_id = ? AND producto_id = ?',
                       (tienda_id, producto_id)).fetchone()
    return row[0] if row else None


def add_order(conn, cliente_id, cantidad, fecha='2026-11-16 10:30:00', tienda_id=1, producto_id=1, precio=2.80):
    """Inserts an order header and one order line (detalle_pedido)."""
    cur = conn.execute('INSERT INTO pedido (fecha_exacta, cliente_id, tienda_id) VALUES (?, ?, ?)',
                       (fecha, cliente_id, tienda_id))
    add_line(conn, cur.lastrowid, producto_id, cantidad, precio)
    return cur.lastrowid


def add_line(conn, pedido_id, producto_id, cantidad, precio=2.80):
    conn.execute('INSERT INTO detalle_pedido (pedido_id, producto_id, cantidad, precio_unitario) '
                 'VALUES (?, ?, ?, ?)', (pedido_id, producto_id, cantidad, precio))


def test_tc01_register_customer(conn):
    """FR-01: a new customer gets an automatic id and starts with 0 points."""
    cur = conn.execute('INSERT INTO cliente (nombre_completo, correo_electronico) VALUES (?, ?)', ANA)
    conn.commit()

    row = conn.execute('SELECT cliente_id, puntos_ecologicos FROM cliente WHERE correo_electronico = ?',
                       (ANA[1],)).fetchone()
    assert row == (cur.lastrowid, 0)
    assert row[0] == 1


def test_tc02_register_inventory(base_conn):
    """FR-02: an inventory row for store 1 / product 1 is saved with its stock."""
    base_conn.execute('INSERT INTO inventario VALUES (1, 1, 100.00)')
    base_conn.commit()

    rows = base_conn.execute('SELECT tienda_id, producto_id, cantidad_stock FROM inventario').fetchall()
    assert rows == [(1, 1, 100.00)]


def test_tc03_concurrent_stock_updates(base_conn, db_path):
    """NFR-01: 50 concurrent transactions subtract 1.00 each without errors in under 2 seconds."""
    base_conn.execute('INSERT INTO inventario VALUES (1, 1, 100.00)')
    base_conn.commit()
    # WAL is SQLite's mode for concurrent access: writers don't wait for readers.
    base_conn.execute('PRAGMA journal_mode = WAL')
    errors = []

    def buy():
        # SQLite's own busy handler waits in steps of up to 100 ms (rounded up even more
        # on Windows), so with 50 writers it takes ~3 s. A short busy timeout plus
        # retrying the transaction after 1 ms does the same job much faster.
        worker = sqlite3.connect(db_path, timeout=0.01, isolation_level=None)
        try:
            worker.execute('PRAGMA foreign_keys = ON')
            for _ in range(2000):
                try:
                    worker.execute('BEGIN IMMEDIATE')
                    worker.execute('UPDATE inventario SET cantidad_stock = cantidad_stock - 1.00 '
                                   'WHERE tienda_id = 1 AND producto_id = 1')
                    worker.execute('COMMIT')
                    return
                except sqlite3.OperationalError:
                    if worker.in_transaction:
                        worker.execute('ROLLBACK')
                    time.sleep(0.001)
            errors.append('transaction never got the lock')
        except sqlite3.Error as e:
            errors.append(e)
        finally:
            worker.close()

    threads = [threading.Thread(target=buy) for _ in range(50)]
    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    assert errors == []
    assert stock(base_conn) == pytest.approx(50.00)
    assert elapsed < 2


def test_tc04_duplicate_inventory_rejected(base_conn):
    """FR-02: the composite primary key rejects a second row for the same store and product."""
    base_conn.execute('INSERT INTO inventario VALUES (1, 1, 100.00)')
    base_conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        base_conn.execute('INSERT INTO inventario VALUES (1, 1, 50.00)')
    base_conn.rollback()

    assert base_conn.execute('SELECT COUNT(*) FROM inventario').fetchone()[0] == 1


def test_tc05_register_order(base_conn):
    """FR-03: a valid order gets a unique id; the header and its line keep the linked values."""
    pedido_id = add_order(base_conn, 1, 2.50)
    base_conn.commit()

    header = base_conn.execute('SELECT fecha_exacta, cliente_id, tienda_id FROM pedido WHERE pedido_id = ?',
                               (pedido_id,)).fetchone()
    line = base_conn.execute('SELECT producto_id, cantidad, precio_unitario FROM detalle_pedido '
                             'WHERE pedido_id = ?', (pedido_id,)).fetchone()
    assert pedido_id == 1
    assert header == ('2026-11-16 10:30:00', 1, 1)
    assert line == (1, 2.50, 2.80)


def test_tc06_order_with_missing_customer(base_conn):
    """FR-03: an order for customer 9999 is rejected by the foreign key."""
    with pytest.raises(sqlite3.IntegrityError, match='FOREIGN KEY'):
        add_order(base_conn, 9999, 2.50)
    base_conn.rollback()

    assert base_conn.execute('SELECT COUNT(*) FROM pedido').fetchone()[0] == 0


@pytest.mark.parametrize('cantidad', [0, -1.00])
def test_tc07_order_quantity_must_be_positive(base_conn, cantidad):
    """FR-03: the CHECK constraint of detalle_pedido rejects quantities of 0 and -1.00."""
    with pytest.raises(sqlite3.IntegrityError, match='ck_detalle_pedido_cantidad_positiva'):
        add_order(base_conn, 1, cantidad)
    base_conn.rollback()

    assert base_conn.execute('SELECT COUNT(*) FROM pedido').fetchone()[0] == 0
    assert base_conn.execute('SELECT COUNT(*) FROM detalle_pedido').fetchone()[0] == 0


def test_tc08_customer_order_history(base_conn):
    """FR-04: the history of customer 1 has only their 3 orders, newest first."""
    base_conn.execute("INSERT INTO cliente (nombre_completo, correo_electronico) "
                      "VALUES ('Carlos Andrade', 'carlos.andrade@example.com')")
    add_order(base_conn, 1, 1.00, '2026-11-01 09:00:00')
    add_order(base_conn, 1, 2.00, '2026-11-10 12:00:00')
    add_order(base_conn, 2, 4.00, '2026-11-12 08:00:00')
    add_order(base_conn, 1, 3.00, '2026-11-05 18:30:00')
    base_conn.commit()

    rows = base_conn.execute(
        'SELECT p.pedido_id, p.fecha_exacta, pr.nombre, t.nombre_sucursal, d.cantidad '
        'FROM pedido p '
        'JOIN detalle_pedido d ON d.pedido_id = p.pedido_id '
        'JOIN producto pr ON pr.producto_id = d.producto_id '
        'JOIN tienda t ON t.tienda_id = p.tienda_id '
        'WHERE p.cliente_id = ? '
        'ORDER BY p.fecha_exacta DESC', (1,)).fetchall()

    assert len(rows) == 3
    assert [r[1] for r in rows] == ['2026-11-10 12:00:00', '2026-11-05 18:30:00', '2026-11-01 09:00:00']
    assert rows[0][2:4] == ('Detergente líquido', 'Sucursal Centro')


def test_tc09_order_updates_stock(base_conn):
    """FR-05: saving the order and subtracting the stock in one transaction leaves 97.50."""
    base_conn.execute('INSERT INTO inventario VALUES (1, 1, 100.00)')
    base_conn.commit()

    with base_conn:
        add_order(base_conn, 1, 2.50)
        base_conn.execute('UPDATE inventario SET cantidad_stock = cantidad_stock - 2.50 '
                          'WHERE tienda_id = 1 AND producto_id = 1')

    assert stock(base_conn) == pytest.approx(97.50)
    assert base_conn.execute('SELECT COUNT(*) FROM pedido').fetchone()[0] == 1


def test_tc10_order_without_enough_stock_rolls_back(base_conn):
    """FR-05: an order of 500 with only 97.50 in stock is rolled back completely."""
    base_conn.execute('INSERT INTO inventario VALUES (1, 1, 97.50)')
    base_conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match='ck_inventario_cantidad_stock_no_negativa'):
        with base_conn:
            add_order(base_conn, 1, 500)
            base_conn.execute('UPDATE inventario SET cantidad_stock = cantidad_stock - 500 '
                              'WHERE tienda_id = 1 AND producto_id = 1')

    assert base_conn.execute('SELECT COUNT(*) FROM pedido').fetchone()[0] == 0
    assert base_conn.execute('SELECT COUNT(*) FROM detalle_pedido').fetchone()[0] == 0
    assert stock(base_conn) == pytest.approx(97.50)


def test_tc11_low_stock_report(base_conn):
    """FR-06: only the row with stock under 10.00 shows up in the low stock report."""
    base_conn.execute("INSERT INTO producto (nombre, unidad_medida) VALUES ('Avena', 'kg')")
    base_conn.execute('INSERT INTO inventario VALUES (1, 1, 5.00)')
    base_conn.execute('INSERT INTO inventario VALUES (1, 2, 80.00)')
    base_conn.commit()

    rows = base_conn.execute(
        'SELECT t.nombre_sucursal, pr.nombre, i.cantidad_stock '
        'FROM inventario i '
        'JOIN tienda t ON t.tienda_id = i.tienda_id '
        'JOIN producto pr ON pr.producto_id = i.producto_id '
        'WHERE i.cantidad_stock < 10.00').fetchall()

    assert rows == [('Sucursal Centro', 'Detergente líquido', 5.00)]


def test_tc12_duplicate_email_rejected(base_conn):
    """NFR-02: a second customer with the same email is rejected by the unique constraint."""
    with pytest.raises(sqlite3.IntegrityError, match='UNIQUE'):
        base_conn.execute('INSERT INTO cliente (nombre_completo, correo_electronico) VALUES (?, ?)',
                          ('Ana P. Duplicada', ANA[1]))
    base_conn.rollback()

    assert base_conn.execute('SELECT COUNT(*) FROM cliente').fetchone()[0] == 1


def test_tc13_schema_script_creates_everything(conn):
    """NFR-03: the schema script builds the 6 tables with their keys, constraints and indexes."""
    tables = {name: sql for name, sql in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
    assert set(tables) == {'cliente', 'tienda', 'producto', 'inventario', 'pedido', 'detalle_pedido'}

    pk_columns = {
        'cliente': ['cliente_id'],
        'tienda': ['tienda_id'],
        'producto': ['producto_id'],
        'inventario': ['tienda_id', 'producto_id'],
        'pedido': ['pedido_id'],
        'detalle_pedido': ['pedido_id', 'producto_id'],
    }
    for table, expected in pk_columns.items():
        info = conn.execute(f'PRAGMA table_info({table})').fetchall()
        pk = [row[1] for row in sorted(info, key=lambda r: r[5]) if row[5] > 0]
        assert pk == expected
        assert f'pk_{table}' in tables[table]

    fks = {table: {(row[3], row[2]) for row in conn.execute(f'PRAGMA foreign_key_list({table})')}
           for table in ('inventario', 'pedido', 'detalle_pedido')}
    assert fks['inventario'] == {('tienda_id', 'tienda'), ('producto_id', 'producto')}
    assert fks['pedido'] == {('cliente_id', 'cliente'), ('tienda_id', 'tienda')}
    assert fks['detalle_pedido'] == {('pedido_id', 'pedido'), ('producto_id', 'producto')}
    for row in conn.execute('PRAGMA foreign_key_list(pedido)'):
        assert row[6] == 'RESTRICT'
    on_delete = {row[3]: row[6] for row in conn.execute('PRAGMA foreign_key_list(detalle_pedido)')}
    assert on_delete == {'pedido_id': 'CASCADE', 'producto_id': 'RESTRICT'}

    assert 'uq_cliente_correo_electronico' in tables['cliente']
    assert 'ck_cliente_puntos_ecologicos_no_negativo' in tables['cliente']
    assert 'ck_inventario_cantidad_stock_no_negativa' in tables['inventario']
    assert 'ck_producto_precio_unitario_no_negativo' in tables['producto']
    assert 'ck_detalle_pedido_cantidad_positiva' in tables['detalle_pedido']
    assert 'ck_detalle_pedido_precio_unitario_no_negativo' in tables['detalle_pedido']
    for name in ('fk_inventario_tienda', 'fk_inventario_producto'):
        assert name in tables['inventario']
    for name in ('fk_pedido_cliente', 'fk_pedido_tienda'):
        assert name in tables['pedido']
    for name in ('pk_detalle_pedido', 'fk_detalle_pedido_pedido', 'fk_detalle_pedido_producto'):
        assert name in tables['detalle_pedido']

    indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {'idx_pedido_cliente_id', 'idx_pedido_tienda_id', 'idx_pedido_fecha_exacta',
            'idx_detalle_pedido_producto_id'} <= indexes
    assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1


def test_tc14_order_with_several_lines_and_total(base_conn):
    """FR-03: one order holds several products (detalle_pedido) and its total is the sum of the lines."""
    base_conn.execute("INSERT INTO producto (nombre, unidad_medida, precio_unitario) VALUES ('Avena', 'kg', 3.20)")
    pedido_id = add_order(base_conn, 1, 2.50)                    # 2.50 x 2.80 = 7.00
    add_line(base_conn, pedido_id, 2, 1.25, 3.20)                # 1.25 x 3.20 = 4.00
    base_conn.commit()

    row = base_conn.execute('SELECT COUNT(*), ROUND(SUM(cantidad * precio_unitario), 2) '
                            'FROM detalle_pedido WHERE pedido_id = ?', (pedido_id,)).fetchone()
    assert row == (2, 11.00)


def test_tc15_same_product_twice_in_an_order_rejected(base_conn):
    """The composite key (pedido_id, producto_id) allows one line per product in each order."""
    pedido_id = add_order(base_conn, 1, 2.50)
    with pytest.raises(sqlite3.IntegrityError, match='UNIQUE'):
        add_line(base_conn, pedido_id, 1, 1.00)
    base_conn.rollback()


def test_tc16_deleting_an_order_deletes_its_lines(base_conn):
    """ON DELETE CASCADE: the lines belong to the order, so cancelling it removes them too."""
    pedido_id = add_order(base_conn, 1, 2.50)
    base_conn.commit()
    base_conn.execute('DELETE FROM pedido WHERE pedido_id = ?', (pedido_id,))
    base_conn.commit()
    assert base_conn.execute('SELECT COUNT(*) FROM detalle_pedido').fetchone()[0] == 0


def test_tc17_product_with_order_lines_cannot_be_deleted(base_conn):
    """ON DELETE RESTRICT: a product that appears in an order keeps the sales history."""
    add_order(base_conn, 1, 2.50)
    base_conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match='FOREIGN KEY'):
        base_conn.execute('DELETE FROM producto WHERE producto_id = 1')
    base_conn.rollback()
