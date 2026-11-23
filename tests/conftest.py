import os
import sqlite3
from decimal import Decimal

import pytest

from app import create_app
from models import db, Cliente, Tienda, Producto, Inventario

SCHEMA = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema_sqlite.sql')


def open_db(path):
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA foreign_keys = ON')
    with open(SCHEMA, encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / 'eco_test.db')


@pytest.fixture
def conn(db_path):
    """Fresh database created from schema_sqlite.sql, no rows."""
    connection = open_db(db_path)
    yield connection
    connection.close()


@pytest.fixture
def base_conn(conn):
    """Database with the common test data: customer 1, store 1, products 1 and 2."""
    conn.execute("INSERT INTO cliente (nombre_completo, correo_electronico) "
                 "VALUES ('Ana Pérez', 'ana.perez@example.com')")
    conn.execute("INSERT INTO tienda (nombre_sucursal, direccion) "
                 "VALUES ('Sucursal Centro', 'Av. Amazonas N24-03')")
    conn.execute("INSERT INTO producto (nombre, unidad_medida, precio_unitario) "
                 "VALUES ('Detergente líquido', 'liters', 2.80)")
    conn.execute("INSERT INTO producto (nombre, unidad_medida, precio_unitario) VALUES ('Avena', 'kg', 3.20)")
    conn.commit()
    return conn


@pytest.fixture
def app(tmp_path):
    app = create_app('sqlite:///' + (tmp_path / 'api_test.db').as_posix())
    app.config['TESTING'] = True

    with app.app_context():
        db.session.add_all([
            Cliente(nombre_completo='Ana Pérez', correo_electronico='ana.perez@example.com'),
            Cliente(nombre_completo='Carlos Andrade', correo_electronico='carlos.andrade@example.com'),
            Tienda(nombre_sucursal='Sucursal Centro', direccion='Av. Amazonas N24-03'),
            Tienda(nombre_sucursal='Sucursal Norte', direccion='Av. de la Prensa N45-120'),
            Producto(nombre='Detergente líquido', unidad_medida='liters', precio_unitario=Decimal('2.80')),
            Producto(nombre='Avena', unidad_medida='kg', precio_unitario=Decimal('3.20')),
        ])
        db.session.flush()
        db.session.add_all([
            Inventario(tienda_id=1, producto_id=1, cantidad_stock=Decimal('100.00')),
            Inventario(tienda_id=1, producto_id=2, cantidad_stock=Decimal('5.00')),
            Inventario(tienda_id=2, producto_id=1, cantidad_stock=Decimal('40.00')),
        ])
        db.session.commit()

    yield app

    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()
