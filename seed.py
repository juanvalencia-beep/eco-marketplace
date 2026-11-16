from datetime import datetime, timedelta
from decimal import Decimal

from app import create_app
from models import db, Cliente, Tienda, Producto, Inventario, Pedido, points_for

TIENDAS = [
    ('Sucursal Centro', 'Av. Amazonas N24-03 y Wilson, Quito'),
    ('Sucursal Norte', 'Av. de la Prensa N45-120 y Vaca de Castro, Quito'),
    ('Sucursal Cumbayá', 'Av. Interoceánica km 12.5 y Pampite, Cumbayá'),
]

PRODUCTOS = [
    ('Detergente líquido', 'liters'),
    ('Avena', 'kg'),
    ('Arroz integral', 'kg'),
    ('Jabón de manos', 'liters'),
    ('Shampoo sólido', 'units'),
    ('Aceite de girasol', 'liters'),
    ('Granola', 'kg'),
    ('Suavizante de ropa', 'liters'),
]

CLIENTES = [
    ('Ana Pérez', 'ana.perez@example.com'),
    ('Carlos Andrade', 'carlos.andrade@example.com'),
    ('María José Villacís', 'mariajose.villacis@example.com'),
    ('Diego Salazar', 'diego.salazar@example.com'),
    ('Gabriela Torres', 'gabriela.torres@example.com'),
    ('Luis Chiriboga', 'luis.chiriboga@example.com'),
]

# (tienda, producto): stock before the orders below
STOCK = {
    (1, 1): '120.00', (1, 2): '45.00', (1, 3): '60.00', (1, 4): '35.00',
    (1, 5): '40.00', (1, 6): '50.00', (1, 7): '25.00', (1, 8): '80.00',
    (2, 1): '90.00', (2, 2): '30.00', (2, 3): '55.00', (2, 4): '12.00',
    (2, 5): '10.00', (2, 7): '18.00', (2, 8): '40.00',
    (3, 1): '70.00', (3, 2): '15.00', (3, 3): '28.00', (3, 5): '22.00',
    (3, 6): '30.00',
}

# (days ago, hour, cliente, tienda, producto, cantidad)
PEDIDOS = [
    (26, 10, 1, 1, 1, '2.50'),
    (23, 17, 2, 2, 3, '3.00'),
    (21, 9, 3, 1, 4, '1.50'),
    (19, 12, 1, 1, 2, '1.25'),
    (16, 18, 4, 3, 2, '7.00'),
    (14, 11, 5, 2, 5, '3.00'),
    (12, 16, 2, 1, 8, '4.00'),
    (9, 10, 6, 3, 1, '5.00'),
    (7, 13, 3, 2, 4, '2.00'),
    (5, 19, 1, 2, 5, '2.00'),
    (3, 9, 4, 1, 6, '1.75'),
    (1, 15, 5, 3, 3, '2.50'),
]


def seed():
    db.drop_all()
    db.create_all()

    for nombre, direccion in TIENDAS:
        db.session.add(Tienda(nombre_sucursal=nombre, direccion=direccion))
    for nombre, unidad in PRODUCTOS:
        db.session.add(Producto(nombre=nombre, unidad_medida=unidad))
    for nombre, correo in CLIENTES:
        db.session.add(Cliente(nombre_completo=nombre, correo_electronico=correo, puntos_ecologicos=0))
    db.session.flush()

    stock = {key: Decimal(value) for key, value in STOCK.items()}
    puntos = {i: 0 for i in range(1, len(CLIENTES) + 1)}
    today = datetime.now().replace(minute=0, second=0, microsecond=0)

    # apply every order to the stock and points the same way the API does
    for days, hour, cliente_id, tienda_id, producto_id, cantidad in PEDIDOS:
        cantidad = Decimal(cantidad)
        stock[(tienda_id, producto_id)] -= cantidad
        puntos[cliente_id] += points_for(cantidad)
        fecha = (today - timedelta(days=days)).replace(hour=hour, minute=(days * 7) % 60)
        db.session.add(Pedido(fecha_exacta=fecha, cantidad_comprada=cantidad, cliente_id=cliente_id,
                              tienda_id=tienda_id, producto_id=producto_id))

    for (tienda_id, producto_id), cantidad in stock.items():
        db.session.add(Inventario(tienda_id=tienda_id, producto_id=producto_id, cantidad_stock=cantidad))
    for cliente_id, total in puntos.items():
        db.session.get(Cliente, cliente_id).puntos_ecologicos = total

    db.session.commit()

    low = [key for key, value in stock.items() if value < 10]
    print(f'Seeded {len(TIENDAS)} stores, {len(PRODUCTOS)} products, {len(CLIENTES)} customers, '
          f'{len(stock)} inventory rows and {len(PEDIDOS)} orders')
    print(f'Low stock rows (< 10): {low}')


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed()
