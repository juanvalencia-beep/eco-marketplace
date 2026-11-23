from datetime import datetime, timedelta
from decimal import Decimal

from app import create_app
from models import db, Cliente, Tienda, Producto, Inventario, Pedido, DetallePedido, points_for

TIENDAS = [
    ('Sucursal Centro', 'Av. Amazonas N24-03 y Wilson, Quito'),
    ('Sucursal Norte', 'Av. de la Prensa N45-120 y Vaca de Castro, Quito'),
    ('Sucursal Cumbayá', 'Av. Interoceánica km 12.5 y Pampite, Cumbayá'),
]

# (name, unit, price per unit in USD)
PRODUCTOS = [
    ('Detergente líquido', 'liters', '2.80'),
    ('Avena', 'kg', '3.20'),
    ('Arroz integral', 'kg', '2.10'),
    ('Jabón de manos', 'liters', '4.50'),
    ('Shampoo sólido', 'units', '6.90'),
    ('Aceite de girasol', 'liters', '3.60'),
    ('Granola', 'kg', '7.40'),
    ('Suavizante de ropa', 'liters', '2.40'),
]

CLIENTES = [
    ('Ana Pérez', 'ana.perez@example.com'),
    ('Carlos Andrade', 'carlos.andrade@example.com'),
    ('María José Villacís', 'mariajose.villacis@example.com'),
    ('Diego Salazar', 'diego.salazar@example.com'),
    ('Gabriela Torres', 'gabriela.torres@example.com'),
    ('Luis Chiriboga', 'luis.chiriboga@example.com'),
    ('Sofía Cevallos', 'sofia.cevallos@example.com'),
    ('Andrés Moncayo', 'andres.moncayo@example.com'),
]

# (tienda, producto): stock before the orders below
STOCK = {
    (1, 1): '140.00', (1, 2): '60.00', (1, 3): '80.00', (1, 4): '40.00',
    (1, 5): '45.00', (1, 6): '55.00', (1, 7): '30.00', (1, 8): '90.00',
    (2, 1): '100.00', (2, 2): '35.00', (2, 3): '60.00', (2, 4): '13.00',
    (2, 5): '14.00', (2, 7): '20.00', (2, 8): '45.00',
    (3, 1): '80.00', (3, 2): '15.00', (3, 3): '35.00', (3, 5): '26.00',
    (3, 6): '35.00',
}

# (days ago, hour, cliente, tienda, [(producto, cantidad), ...])
PEDIDOS = [
    (29, 10, 1, 1, [(1, '2.50'), (2, '1.00')]),
    (28, 17, 2, 2, [(3, '3.00')]),
    (27, 9, 3, 1, [(4, '1.50'), (5, '2.00'), (7, '0.50')]),
    (26, 12, 1, 1, [(2, '1.25'), (6, '1.00')]),
    (24, 18, 4, 3, [(2, '4.00'), (3, '2.00')]),
    (23, 11, 5, 2, [(5, '3.00'), (1, '2.00')]),
    (22, 16, 2, 1, [(8, '4.00'), (1, '3.00')]),
    (21, 10, 6, 3, [(1, '5.00')]),
    (20, 13, 3, 2, [(4, '2.00'), (7, '1.00')]),
    (19, 19, 7, 1, [(7, '1.50'), (2, '2.00'), (6, '1.00')]),
    (18, 9, 4, 1, [(6, '1.75')]),
    (17, 15, 5, 3, [(3, '2.50'), (5, '1.00')]),
    (16, 11, 8, 2, [(1, '4.00'), (8, '3.00')]),
    (15, 17, 1, 2, [(5, '2.00'), (4, '1.00')]),
    (13, 10, 6, 1, [(3, '3.00'), (2, '1.50'), (1, '2.00')]),
    (12, 14, 2, 3, [(6, '2.00'), (2, '1.00')]),
    (11, 18, 7, 2, [(2, '2.50'), (7, '1.25')]),
    (10, 9, 3, 1, [(5, '1.00'), (4, '2.00')]),
    (9, 12, 8, 3, [(1, '3.50'), (3, '2.00')]),
    (8, 16, 4, 2, [(4, '2.50'), (5, '2.00')]),
    (7, 11, 5, 1, [(8, '2.50'), (1, '2.00'), (7, '0.75')]),
    (6, 19, 1, 3, [(5, '3.00'), (2, '2.00')]),
    (5, 10, 6, 2, [(3, '4.00')]),
    (4, 15, 7, 1, [(6, '1.50'), (3, '2.00')]),
    (3, 13, 2, 2, [(7, '1.50'), (2, '1.50')]),
    (2, 17, 3, 3, [(6, '2.00'), (1, '1.50')]),
    (1, 10, 8, 1, [(2, '2.00'), (4, '1.00'), (5, '1.00')]),
    (0, 9, 5, 2, [(5, '1.50'), (1, '1.00')]),
]


def seed():
    db.drop_all()
    db.create_all()

    for nombre, direccion in TIENDAS:
        db.session.add(Tienda(nombre_sucursal=nombre, direccion=direccion))
    for nombre, unidad, precio in PRODUCTOS:
        db.session.add(Producto(nombre=nombre, unidad_medida=unidad, precio_unitario=Decimal(precio)))
    for nombre, correo in CLIENTES:
        db.session.add(Cliente(nombre_completo=nombre, correo_electronico=correo, puntos_ecologicos=0))
    db.session.flush()

    precios = {i: Decimal(p[2]) for i, p in enumerate(PRODUCTOS, start=1)}
    stock = {key: Decimal(value) for key, value in STOCK.items()}
    puntos = {i: 0 for i in range(1, len(CLIENTES) + 1)}
    now = datetime.now().replace(second=0, microsecond=0)

    # apply every order to the stock and points the same way the API does
    for days, hour, cliente_id, tienda_id, lineas in PEDIDOS:
        fecha = (now - timedelta(days=days)).replace(hour=hour, minute=(days * 7) % 60)
        if fecha > now:  # today's order can't be in the future
            fecha = now
        pedido = Pedido(fecha_exacta=fecha, cliente_id=cliente_id, tienda_id=tienda_id)
        for producto_id, cantidad in lineas:
            cantidad = Decimal(cantidad)
            stock[(tienda_id, producto_id)] -= cantidad
            assert stock[(tienda_id, producto_id)] >= 0, (tienda_id, producto_id)
            puntos[cliente_id] += points_for(cantidad)
            pedido.detalles.append(DetallePedido(producto_id=producto_id, cantidad=cantidad,
                                                 precio_unitario=precios[producto_id]))
        db.session.add(pedido)

    for (tienda_id, producto_id), cantidad in stock.items():
        db.session.add(Inventario(tienda_id=tienda_id, producto_id=producto_id, cantidad_stock=cantidad))
    for cliente_id, total in puntos.items():
        db.session.get(Cliente, cliente_id).puntos_ecologicos = total

    db.session.commit()

    lineas = sum(len(p[4]) for p in PEDIDOS)
    low = [key for key, value in stock.items() if value < 10]
    print(f'Seeded {len(TIENDAS)} stores, {len(PRODUCTOS)} products, {len(CLIENTES)} customers, '
          f'{len(stock)} inventory rows, {len(PEDIDOS)} orders with {lineas} order lines')
    print(f'Low stock rows (< 10): {low}')


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed()
