"""Test cases TC-01 to TC-15 of the Database Design Specification (Nov 16, 2026),
run directly on database/schema_sqlite.sql. Common test data: customer 1 (Ana Pérez),
store 1 (Sucursal Centro), product 1 (Detergente líquido, liters) and product 2 (Avena, kg)."""
import sqlite3
import threading
import time

import pytest

ANA = ('Ana Pérez', 'ana.perez@example.com')


def stock(conn, tienda_id=1, producto_id=1):
    row = conn.execute('SELECT cantidad_stock FROM inventario WHERE tienda_id = ? AND producto_id = ?',
                       (tienda_id, producto_id)).fetchone()
    return row[0] if row else None


def add_header(conn, cliente_id, fecha='2026-11-16 10:30:00', tienda_id=1):
    """Inserts an order header (pedido) and returns its id."""
    cur = conn.execute('INSERT INTO pedido (fecha_exacta, cliente_id, tienda_id) VALUES (?, ?, ?)',
                       (fecha, cliente_id, tienda_id))
    return cur.lastrowid


def add_line(conn, pedido_id, producto_id, cantidad, precio=2.80):
    """Inserts one order line (detalle_pedido)."""
    conn.execute('INSERT INTO detalle_pedido (pedido_id, producto_id, cantidad_comprada, precio_unitario) '
                 'VALUES (?, ?, ?, ?)', (pedido_id, producto_id, cantidad, precio))


def subtract_stock(conn, tienda_id, producto_id, cantidad):
    conn.execute('UPDATE inventario SET cantidad_stock = cantidad_stock - ? '
                 'WHERE tienda_id = ? AND producto_id = ?', (cantidad, tienda_id, producto_id))


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


def test_tc05_register_order_with_two_products(base_conn):
    """FR-03: one order (header) with two detail lines linked to it."""
    cur = base_conn.execute("INSERT INTO pedido (fecha_exacta, cliente_id, tienda_id) "
                            "VALUES (datetime('now'), 1, 1)")
    pedido_id = cur.lastrowid
    add_line(base_conn, pedido_id, 1, 2.50)
    add_line(base_conn, pedido_id, 2, 1.00)
    base_conn.commit()

    rows = base_conn.execute(
        'SELECT p.pedido_id, p.cliente_id, p.tienda_id, d.producto_id, d.cantidad_comprada '
        'FROM pedido p JOIN detalle_pedido d ON d.pedido_id = p.pedido_id '
        'WHERE p.pedido_id = ? ORDER BY d.producto_id', (pedido_id,)).fetchall()
    assert base_conn.execute('SELECT COUNT(*) FROM pedido').fetchone()[0] == 1
    assert rows == [(pedido_id, 1, 1, 1, 2.50), (pedido_id, 1, 1, 2, 1.00)]


def test_tc06_order_with_missing_customer(base_conn):
    """FR-03: an order for customer 9999 is rejected by fk_pedido_cliente."""
    with pytest.raises(sqlite3.IntegrityError, match='FOREIGN KEY'):
        base_conn.execute("INSERT INTO pedido (fecha_exacta, cliente_id, tienda_id) "
                          "VALUES ('2026-11-16 10:30:00', 9999, 1)")
    base_conn.rollback()

    assert base_conn.execute('SELECT COUNT(*) FROM pedido').fetchone()[0] == 0


def test_tc07_detail_quantity_must_be_positive(base_conn):
    """FR-03: ck_detalle_pedido_cantidad_comprada_positiva rejects 0 and -1.00."""
    pedido_id = add_header(base_conn, 1)
    base_conn.commit()

    for cantidad in (0, -1.00):
        with pytest.raises(sqlite3.IntegrityError, match='ck_detalle_pedido_cantidad_comprada_positiva'):
            add_line(base_conn, pedido_id, 1, cantidad)
        base_conn.rollback()

    assert base_conn.execute('SELECT COUNT(*) FROM detalle_pedido').fetchone()[0] == 0


def test_tc08_customer_order_history(base_conn):
    """FR-04: customer 1 has 3 orders (one with two products) -> 4 detail lines, newest first."""
    base_conn.execute("INSERT INTO cliente (nombre_completo, correo_electronico) "
                      "VALUES ('Carlos Andrade', 'carlos.andrade@example.com')")
    p1 = add_header(base_conn, 1, '2026-11-01 09:00:00')
    add_line(base_conn, p1, 1, 1.00)
    p2 = add_header(base_conn, 1, '2026-11-10 12:00:00')
    add_line(base_conn, p2, 1, 2.00)
    add_line(base_conn, p2, 2, 0.50)
    p3 = add_header(base_conn, 2, '2026-11-12 08:00:00')
    add_line(base_conn, p3, 1, 4.00)
    p4 = add_header(base_conn, 1, '2026-11-05 18:30:00')
    add_line(base_conn, p4, 2, 3.00)
    base_conn.commit()

    rows = base_conn.execute(
        'SELECT p.pedido_id, p.fecha_exacta, t.nombre_sucursal, pr.nombre, d.cantidad_comprada '
        'FROM pedido p '
        'JOIN detalle_pedido d ON d.pedido_id = p.pedido_id '
        'JOIN producto pr ON pr.producto_id = d.producto_id '
        'JOIN tienda t ON t.tienda_id = p.tienda_id '
        'WHERE p.cliente_id = ? '
        'ORDER BY p.fecha_exacta DESC, d.producto_id', (1,)).fetchall()

    assert len(rows) == 4
    assert {r[0] for r in rows} == {p1, p2, p4}
    assert [r[1] for r in rows] == ['2026-11-10 12:00:00', '2026-11-10 12:00:00',
                                    '2026-11-05 18:30:00', '2026-11-01 09:00:00']
    assert rows[0][2:] == ('Sucursal Centro', 'Detergente líquido', 2.00)


def test_tc09_order_with_two_products_updates_stock(base_conn):
    """FR-05: saving the order with two lines and subtracting both stocks in one transaction."""
    base_conn.execute('INSERT INTO inventario VALUES (1, 1, 100.00)')
    base_conn.execute('INSERT INTO inventario VALUES (1, 2, 50.00)')
    base_conn.commit()

    with base_conn:
        pedido_id = add_header(base_conn, 1)
        for producto_id, cantidad in ((1, 2.50), (2, 1.00)):
            add_line(base_conn, pedido_id, producto_id, cantidad)
            subtract_stock(base_conn, 1, producto_id, cantidad)

    assert base_conn.execute('SELECT COUNT(*) FROM pedido').fetchone()[0] == 1
    assert base_conn.execute('SELECT COUNT(*) FROM detalle_pedido WHERE pedido_id = ?',
                             (pedido_id,)).fetchone()[0] == 2
    assert stock(base_conn, 1, 1) == pytest.approx(97.50)
    assert stock(base_conn, 1, 2) == pytest.approx(49.00)


def test_tc10_one_product_without_stock_rolls_back_the_whole_order(base_conn):
    """FR-05: product 2 has not enough stock, so the order, its lines and both stocks are rolled back."""
    base_conn.execute('INSERT INTO inventario VALUES (1, 1, 97.50)')
    base_conn.execute('INSERT INTO inventario VALUES (1, 2, 49.00)')
    base_conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match='ck_inventario_cantidad_stock_no_negativa'):
        with base_conn:
            pedido_id = add_header(base_conn, 1)
            for producto_id, cantidad in ((1, 1.00), (2, 500.00)):
                add_line(base_conn, pedido_id, producto_id, cantidad)
                subtract_stock(base_conn, 1, producto_id, cantidad)

    assert base_conn.execute('SELECT COUNT(*) FROM pedido').fetchone()[0] == 0
    assert base_conn.execute('SELECT COUNT(*) FROM detalle_pedido').fetchone()[0] == 0
    assert stock(base_conn, 1, 1) == pytest.approx(97.50)
    assert stock(base_conn, 1, 2) == pytest.approx(49.00)


def test_tc11_low_stock_report(base_conn):
    """FR-06: only the row with stock under 10.00 shows up in the low stock report."""
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
    """NFR-02: a second customer with the same email is rejected by uq_cliente_correo_electronico."""
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
    # all foreign keys are ON DELETE RESTRICT (Annex B)
    for table in ('inventario', 'pedido', 'detalle_pedido'):
        for row in conn.execute(f'PRAGMA foreign_key_list({table})'):
            assert row[6] == 'RESTRICT'

    assert 'uq_cliente_correo_electronico' in tables['cliente']
    assert 'ck_cliente_puntos_ecologicos_no_negativo' in tables['cliente']
    assert 'ck_inventario_cantidad_stock_no_negativa' in tables['inventario']
    assert 'ck_detalle_pedido_cantidad_comprada_positiva' in tables['detalle_pedido']
    for name in ('fk_inventario_tienda', 'fk_inventario_producto'):
        assert name in tables['inventario']
    for name in ('fk_pedido_cliente', 'fk_pedido_tienda'):
        assert name in tables['pedido']
    for name in ('fk_detalle_pedido_pedido', 'fk_detalle_pedido_producto'):
        assert name in tables['detalle_pedido']

    indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {'idx_pedido_cliente_id', 'idx_pedido_tienda_id', 'idx_detalle_pedido_producto_id'} <= indexes
    assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1


def test_tc14_same_product_twice_in_an_order_rejected(base_conn):
    """FR-03: pk_detalle_pedido allows only one line per product in each order."""
    pedido_id = add_header(base_conn, 1)
    add_line(base_conn, pedido_id, 1, 2.50)
    base_conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match='UNIQUE'):
        add_line(base_conn, pedido_id, 1, 1.00)
    base_conn.rollback()

    assert base_conn.execute('SELECT COUNT(*) FROM detalle_pedido WHERE pedido_id = ?',
                             (pedido_id,)).fetchone()[0] == 1


def test_tc15_detail_line_referential_integrity(base_conn):
    """FR-03: a line for order 9999 or for product 9999 is rejected by the foreign keys."""
    pedido_id = add_header(base_conn, 1)
    base_conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match='FOREIGN KEY'):
        add_line(base_conn, 9999, 1, 1.00)      # fk_detalle_pedido_pedido
    base_conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match='FOREIGN KEY'):
        add_line(base_conn, pedido_id, 9999, 1.00)  # fk_detalle_pedido_producto
    base_conn.rollback()

    assert base_conn.execute('SELECT COUNT(*) FROM detalle_pedido').fetchone()[0] == 0


# ---- extra checks, not in the design document ----

def test_extra_order_total_is_the_sum_of_its_lines(base_conn):
    """The price is copied into each line, so the order total is SUM(cantidad_comprada * precio_unitario)."""
    pedido_id = add_header(base_conn, 1)
    add_line(base_conn, pedido_id, 1, 2.50, 2.80)   # 7.00
    add_line(base_conn, pedido_id, 2, 1.25, 3.20)   # 4.00
    base_conn.commit()

    row = base_conn.execute('SELECT COUNT(*), ROUND(SUM(cantidad_comprada * precio_unitario), 2) '
                            'FROM detalle_pedido WHERE pedido_id = ?', (pedido_id,)).fetchone()
    assert row == (2, 11.00)


def test_extra_restrict_protects_orders_and_products_with_lines(base_conn):
    """ON DELETE RESTRICT: an order with lines, or a product that was sold, can't be deleted."""
    pedido_id = add_header(base_conn, 1)
    add_line(base_conn, pedido_id, 1, 2.50)
    base_conn.commit()

    for sql in ('DELETE FROM pedido WHERE pedido_id = 1', 'DELETE FROM producto WHERE producto_id = 1'):
        with pytest.raises(sqlite3.IntegrityError, match='FOREIGN KEY'):
            base_conn.execute(sql)
        base_conn.rollback()

    # cancelling an order = delete its lines first, then the header, in one transaction
    with base_conn:
        base_conn.execute('DELETE FROM detalle_pedido WHERE pedido_id = ?', (pedido_id,))
        base_conn.execute('DELETE FROM pedido WHERE pedido_id = ?', (pedido_id,))
    assert base_conn.execute('SELECT COUNT(*) FROM pedido').fetchone()[0] == 0
