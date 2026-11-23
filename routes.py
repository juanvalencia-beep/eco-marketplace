from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, jsonify, request

from models import db, money, Cliente, Tienda, Producto, Inventario, Pedido, DetallePedido, points_for

api = Blueprint('api', __name__)

MAX_AMOUNT = Decimal('99999999.99')  # biggest value that fits in DECIMAL(10,2)
MAX_LINE_QTY = Decimal('10000')      # biggest quantity of one product in one order
MAX_POINTS = 2147483647             # biggest value of a signed INT (puntos_ecologicos)


def get_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, 'El cuerpo de la petición debe ser un objeto JSON')
    return data


def text_value(data, name, max_len):
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        abort(400, f"El campo '{name}' es obligatorio y no puede estar vacío")
    value = value.strip()
    if len(value) > max_len:
        abort(400, f"El campo '{name}' admite máximo {max_len} caracteres")
    return value


def int_value(data, name):
    value = data.get(name)
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        abort(400, f"El campo '{name}' es obligatorio y debe ser un número entero")
    return value


def decimal_value(data, name):
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        abort(400, f"El campo '{name}' es obligatorio y debe ser un número")
    try:
        number = Decimal(str(value).strip())
        if not number.is_finite() or abs(number) > MAX_AMOUNT:
            raise InvalidOperation
        return number.quantize(Decimal('0.01'))
    except InvalidOperation:
        abort(400, f"El campo '{name}' debe ser un número entre -{MAX_AMOUNT} y {MAX_AMOUNT}")


def price_value(data):
    price = decimal_value(data, 'precio_unitario')
    if price < 0:
        abort(400, "El campo 'precio_unitario' no puede ser negativo")
    return price


def date_value(data, name):
    try:
        return datetime.fromisoformat(str(data[name])).replace(microsecond=0, tzinfo=None)
    except ValueError:
        abort(400, f"El campo '{name}' debe ser una fecha con formato AAAA-MM-DDTHH:MM:SS")


def email_value(data):
    email = text_value(data, 'correo_electronico', 120).lower()
    if '@' not in email or '.' not in email.split('@')[-1]:
        abort(400, 'El correo electrónico no es válido')
    return email


def find_inventory(tienda_id, producto_id, lock=False):
    query = db.select(Inventario).filter_by(tienda_id=tienda_id, producto_id=producto_id)
    if lock:
        query = query.with_for_update()
    return db.session.execute(query).scalar_one_or_none()


def count(model, **filters):
    query = db.select(db.func.count()).select_from(model).filter_by(**filters)
    return db.session.execute(query).scalar()


@api.route('/clientes', methods=['GET'])
def list_clientes():
    query = db.select(Cliente).order_by(Cliente.cliente_id)
    q = request.args.get('q', '').strip()
    if q:
        pattern = f'%{q}%'
        query = query.where(Cliente.nombre_completo.ilike(pattern) | Cliente.correo_electronico.ilike(pattern))
    clientes = db.session.execute(query).scalars().all()
    return jsonify([c.to_dict() for c in clientes]), 200


@api.route('/clientes/<int:cliente_id>', methods=['GET'])
def get_cliente(cliente_id):
    cliente = db.get_or_404(Cliente, cliente_id, description=f'No existe el cliente {cliente_id}')
    return jsonify(cliente.to_dict()), 200


@api.route('/clientes', methods=['POST'])
def create_cliente():
    data = get_body()
    cliente = Cliente(
        nombre_completo=text_value(data, 'nombre_completo', 100),
        correo_electronico=email_value(data),
        puntos_ecologicos=0,
    )
    db.session.add(cliente)
    db.session.commit()
    return jsonify(cliente.to_dict()), 201


@api.route('/clientes/<int:cliente_id>', methods=['PUT'])
def update_cliente(cliente_id):
    cliente = db.get_or_404(Cliente, cliente_id, description=f'No existe el cliente {cliente_id}')
    data = get_body()
    if 'nombre_completo' in data:
        cliente.nombre_completo = text_value(data, 'nombre_completo', 100)
    if 'correo_electronico' in data:
        cliente.correo_electronico = email_value(data)
    if 'puntos_ecologicos' in data:
        puntos = int_value(data, 'puntos_ecologicos')
        if puntos < 0:
            abort(400, "El campo 'puntos_ecologicos' no puede ser negativo")
        cliente.puntos_ecologicos = puntos
    db.session.commit()
    return jsonify(cliente.to_dict()), 200


@api.route('/clientes/<int:cliente_id>', methods=['DELETE'])
def delete_cliente(cliente_id):
    cliente = db.get_or_404(Cliente, cliente_id, description=f'No existe el cliente {cliente_id}')
    if count(Pedido, cliente_id=cliente_id) > 0:
        return jsonify({'error': f'El cliente {cliente_id} tiene pedidos y no se puede eliminar'}), 409
    db.session.delete(cliente)
    db.session.commit()
    return jsonify({'message': f'Cliente {cliente_id} eliminado'}), 200


@api.route('/clientes/<int:cliente_id>/pedidos', methods=['GET'])
def cliente_pedidos(cliente_id):
    db.get_or_404(Cliente, cliente_id, description=f'No existe el cliente {cliente_id}')
    query = (db.select(Pedido).filter_by(cliente_id=cliente_id)
             .order_by(Pedido.fecha_exacta.desc(), Pedido.pedido_id.desc()))
    pedidos = db.session.execute(query).scalars().all()
    return jsonify([p.to_dict() for p in pedidos]), 200


@api.route('/tiendas', methods=['GET'])
def list_tiendas():
    tiendas = db.session.execute(db.select(Tienda).order_by(Tienda.tienda_id)).scalars().all()
    return jsonify([t.to_dict() for t in tiendas]), 200


@api.route('/tiendas/<int:tienda_id>', methods=['GET'])
def get_tienda(tienda_id):
    tienda = db.get_or_404(Tienda, tienda_id, description=f'No existe la tienda {tienda_id}')
    return jsonify(tienda.to_dict()), 200


@api.route('/tiendas', methods=['POST'])
def create_tienda():
    data = get_body()
    tienda = Tienda(
        nombre_sucursal=text_value(data, 'nombre_sucursal', 100),
        direccion=text_value(data, 'direccion', 200),
    )
    db.session.add(tienda)
    db.session.commit()
    return jsonify(tienda.to_dict()), 201


@api.route('/tiendas/<int:tienda_id>', methods=['PUT'])
def update_tienda(tienda_id):
    tienda = db.get_or_404(Tienda, tienda_id, description=f'No existe la tienda {tienda_id}')
    data = get_body()
    if 'nombre_sucursal' in data:
        tienda.nombre_sucursal = text_value(data, 'nombre_sucursal', 100)
    if 'direccion' in data:
        tienda.direccion = text_value(data, 'direccion', 200)
    db.session.commit()
    return jsonify(tienda.to_dict()), 200


@api.route('/tiendas/<int:tienda_id>', methods=['DELETE'])
def delete_tienda(tienda_id):
    tienda = db.get_or_404(Tienda, tienda_id, description=f'No existe la tienda {tienda_id}')
    if count(Inventario, tienda_id=tienda_id) > 0 or count(Pedido, tienda_id=tienda_id) > 0:
        return jsonify({'error': f'La tienda {tienda_id} tiene inventario o pedidos y no se puede eliminar'}), 409
    db.session.delete(tienda)
    db.session.commit()
    return jsonify({'message': f'Tienda {tienda_id} eliminada'}), 200


@api.route('/productos', methods=['GET'])
def list_productos():
    productos = db.session.execute(db.select(Producto).order_by(Producto.producto_id)).scalars().all()
    return jsonify([p.to_dict() for p in productos]), 200


@api.route('/productos/<int:producto_id>', methods=['GET'])
def get_producto(producto_id):
    producto = db.get_or_404(Producto, producto_id, description=f'No existe el producto {producto_id}')
    return jsonify(producto.to_dict()), 200


@api.route('/productos', methods=['POST'])
def create_producto():
    data = get_body()
    producto = Producto(
        nombre=text_value(data, 'nombre', 100),
        unidad_medida=text_value(data, 'unidad_medida', 20),
        precio_unitario=price_value(data),
    )
    db.session.add(producto)
    db.session.commit()
    return jsonify(producto.to_dict()), 201


@api.route('/productos/<int:producto_id>', methods=['PUT'])
def update_producto(producto_id):
    producto = db.get_or_404(Producto, producto_id, description=f'No existe el producto {producto_id}')
    data = get_body()
    if 'nombre' in data:
        producto.nombre = text_value(data, 'nombre', 100)
    if 'unidad_medida' in data:
        producto.unidad_medida = text_value(data, 'unidad_medida', 20)
    if 'precio_unitario' in data:
        producto.precio_unitario = price_value(data)
    db.session.commit()
    return jsonify(producto.to_dict()), 200


@api.route('/productos/<int:producto_id>', methods=['DELETE'])
def delete_producto(producto_id):
    producto = db.get_or_404(Producto, producto_id, description=f'No existe el producto {producto_id}')
    if count(Inventario, producto_id=producto_id) > 0 or count(DetallePedido, producto_id=producto_id) > 0:
        return jsonify({'error': f'El producto {producto_id} tiene inventario o pedidos y no se puede eliminar'}), 409
    db.session.delete(producto)
    db.session.commit()
    return jsonify({'message': f'Producto {producto_id} eliminado'}), 200


@api.route('/inventario', methods=['GET'])
def list_inventario():
    query = db.select(Inventario).order_by(Inventario.tienda_id, Inventario.producto_id)
    tienda_id = request.args.get('tienda_id', type=int)
    if tienda_id is not None:
        query = query.filter_by(tienda_id=tienda_id)
    rows = db.session.execute(query).scalars().all()
    return jsonify([r.to_dict() for r in rows]), 200


@api.route('/inventario/stock-bajo', methods=['GET'])
def low_stock():
    limite = request.args.get('limite', '10.00')
    limite = decimal_value({'limite': limite}, 'limite')
    query = (db.select(Inventario).where(Inventario.cantidad_stock < limite)
             .order_by(Inventario.cantidad_stock, Inventario.tienda_id, Inventario.producto_id))
    rows = db.session.execute(query).scalars().all()
    return jsonify([r.to_dict() for r in rows]), 200


@api.route('/inventario/<int:tienda_id>/<int:producto_id>', methods=['GET'])
def get_inventario(tienda_id, producto_id):
    row = find_inventory(tienda_id, producto_id)
    if row is None:
        abort(404, f'La tienda {tienda_id} no tiene inventario del producto {producto_id}')
    return jsonify(row.to_dict()), 200


@api.route('/inventario', methods=['POST'])
def create_inventario():
    data = get_body()
    tienda_id = int_value(data, 'tienda_id')
    producto_id = int_value(data, 'producto_id')
    stock = decimal_value(data, 'cantidad_stock')
    if stock < 0:
        abort(400, "El campo 'cantidad_stock' no puede ser negativo")
    db.get_or_404(Tienda, tienda_id, description=f'No existe la tienda {tienda_id}')
    db.get_or_404(Producto, producto_id, description=f'No existe el producto {producto_id}')
    if find_inventory(tienda_id, producto_id) is not None:
        return jsonify({'error': f'La tienda {tienda_id} ya tiene inventario del producto {producto_id}'}), 409

    row = Inventario(tienda_id=tienda_id, producto_id=producto_id, cantidad_stock=stock)
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict()), 201


@api.route('/inventario/<int:tienda_id>/<int:producto_id>', methods=['PUT'])
def update_inventario(tienda_id, producto_id):
    row = find_inventory(tienda_id, producto_id)
    if row is None:
        abort(404, f'La tienda {tienda_id} no tiene inventario del producto {producto_id}')
    stock = decimal_value(get_body(), 'cantidad_stock')
    if stock < 0:
        abort(400, "El campo 'cantidad_stock' no puede ser negativo")
    row.cantidad_stock = stock
    db.session.commit()
    return jsonify(row.to_dict()), 200


@api.route('/inventario/<int:tienda_id>/<int:producto_id>', methods=['DELETE'])
def delete_inventario(tienda_id, producto_id):
    row = find_inventory(tienda_id, producto_id)
    if row is None:
        abort(404, f'La tienda {tienda_id} no tiene inventario del producto {producto_id}')
    db.session.delete(row)
    db.session.commit()
    return jsonify({'message': f'Inventario ({tienda_id}, {producto_id}) eliminado'}), 200


# ---------------------------------------------------------------- orders
#
# An order (pedido) is the header: customer, store and date. Its products are
# the lines in detalle_pedido. Every change below that touches stock or points
# runs in one transaction: either all of it is saved or nothing is.

def take_stock(tienda_id, producto_id, cantidad):
    """Subtracts cantidad from the store stock, or aborts with 409 if it is not enough."""
    row = find_inventory(tienda_id, producto_id, lock=True)
    if row is None:
        db.session.rollback()
        abort(409, f'La tienda {tienda_id} no vende el producto {producto_id}')
    if row.cantidad_stock < cantidad:
        message = (f'No hay suficiente stock de {row.producto.nombre}: '
                   f'disponible {row.cantidad_stock}, solicitado {cantidad}')
        db.session.rollback()
        abort(409, message)
    # Subtract in SQL (stock = stock - x) instead of writing a value computed in
    # Python, so two orders at the same time can't overwrite each other. If the
    # stock would go negative the CHECK constraint stops it.
    row.cantidad_stock = Inventario.cantidad_stock - cantidad


def return_stock(tienda_id, producto_id, cantidad):
    row = find_inventory(tienda_id, producto_id, lock=True)
    if row is None:
        # the inventory row was removed after the order, so create it again
        db.session.add(Inventario(tienda_id=tienda_id, producto_id=producto_id, cantidad_stock=cantidad))
    else:
        row.cantidad_stock = Inventario.cantidad_stock + cantidad


def change_points(cliente, delta):
    if delta > 0 and cliente.puntos_ecologicos + delta > MAX_POINTS:
        db.session.rollback()
        abort(409, 'El cliente superaría el máximo de eco-puntos permitido')
    if delta >= 0:
        cliente.puntos_ecologicos = Cliente.puntos_ecologicos + delta
    else:
        # points never go below 0 (an admin may have lowered them by hand)
        cliente.puntos_ecologicos = db.case(
            (Cliente.puntos_ecologicos + delta < 0, 0), else_=Cliente.puntos_ecologicos + delta)


def line_values(data):
    producto_id = int_value(data, 'producto_id')
    cantidad = decimal_value(data, 'cantidad_comprada')
    if cantidad <= 0 or cantidad > MAX_LINE_QTY:
        abort(400, f"El campo 'cantidad_comprada' debe ser mayor que 0 y como máximo {MAX_LINE_QTY}")
    producto = db.get_or_404(Producto, producto_id, description=f'No existe el producto {producto_id}')
    return producto, cantidad


def get_line(pedido_id, producto_id):
    line = db.session.get(DetallePedido, (pedido_id, producto_id))
    if line is None:
        abort(404, f'El pedido {pedido_id} no tiene una línea del producto {producto_id}')
    return line


@api.route('/pedidos', methods=['GET'])
def list_pedidos():
    query = db.select(Pedido).order_by(Pedido.fecha_exacta.desc(), Pedido.pedido_id.desc())
    for field in ('cliente_id', 'tienda_id'):
        value = request.args.get(field, type=int)
        if value is not None:
            query = query.filter_by(**{field: value})
    pedidos = db.session.execute(query).scalars().all()
    return jsonify([p.to_dict() for p in pedidos]), 200


@api.route('/pedidos/<int:pedido_id>', methods=['GET'])
def get_pedido(pedido_id):
    pedido = db.get_or_404(Pedido, pedido_id, description=f'No existe el pedido {pedido_id}')
    return jsonify(pedido.to_dict()), 200


@api.route('/pedidos', methods=['POST'])
def create_pedido():
    """Body: {cliente_id, tienda_id, fecha_exacta?, detalles: [{producto_id, cantidad_comprada}, ...]}"""
    data = get_body()
    cliente_id = int_value(data, 'cliente_id')
    tienda_id = int_value(data, 'tienda_id')
    detalles = data.get('detalles')
    if not isinstance(detalles, list) or not detalles:
        abort(400, "El campo 'detalles' es obligatorio y debe ser una lista no vacía de {producto_id, cantidad_comprada}")
    if len(detalles) > 50:
        abort(400, 'Un pedido puede tener máximo 50 líneas')
    if not all(isinstance(d, dict) for d in detalles):
        abort(400, "Cada elemento de 'detalles' debe ser un objeto con producto_id y cantidad_comprada")
    fecha = date_value(data, 'fecha_exacta') if data.get('fecha_exacta') else datetime.now().replace(microsecond=0)

    cliente = db.get_or_404(Cliente, cliente_id, description=f'No existe el cliente {cliente_id}')
    db.get_or_404(Tienda, tienda_id, description=f'No existe la tienda {tienda_id}')
    lines = [line_values(d) for d in detalles]
    ids = [producto.producto_id for producto, _ in lines]
    if len(set(ids)) != len(ids):
        abort(400, 'Cada producto puede aparecer una sola vez por pedido; cambie la cantidad')

    try:
        pedido = Pedido(fecha_exacta=fecha, cliente_id=cliente_id, tienda_id=tienda_id)
        db.session.add(pedido)
        puntos = 0
        for producto, cantidad in lines:
            take_stock(tienda_id, producto.producto_id, cantidad)
            pedido.detalles.append(DetallePedido(producto_id=producto.producto_id, cantidad_comprada=cantidad,
                                                 precio_unitario=producto.precio_unitario))
            puntos += points_for(cantidad)
        change_points(cliente, puntos)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(pedido.to_dict()), 201


@api.route('/pedidos/<int:pedido_id>', methods=['PUT'])
def update_pedido(pedido_id):
    """Only the date of the header can change; the products are changed through the lines."""
    pedido = db.get_or_404(Pedido, pedido_id, description=f'No existe el pedido {pedido_id}')
    data = get_body()
    if 'cliente_id' in data or 'tienda_id' in data:
        abort(400, 'No se puede cambiar el cliente ni la tienda de un pedido; anúlelo y cree uno nuevo')
    if not data.get('fecha_exacta'):
        abort(400, "El campo 'fecha_exacta' es obligatorio")
    pedido.fecha_exacta = date_value(data, 'fecha_exacta')
    db.session.commit()
    return jsonify(pedido.to_dict()), 200


@api.route('/pedidos/<int:pedido_id>', methods=['DELETE'])
def cancel_pedido(pedido_id):
    pedido = db.get_or_404(Pedido, pedido_id, description=f'No existe el pedido {pedido_id}')
    try:
        puntos = 0
        for line in pedido.detalles:
            return_stock(pedido.tienda_id, line.producto_id, line.cantidad_comprada)
            puntos += line.puntos
        change_points(pedido.cliente, -puntos)
        db.session.delete(pedido)  # the ORM deletes its lines first (the FK is ON DELETE RESTRICT)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify({'message': f'Pedido {pedido_id} anulado'}), 200


# ------------------------------------------------------- order lines (CRUD)

@api.route('/pedidos/<int:pedido_id>/detalles', methods=['GET'])
def list_detalles(pedido_id):
    pedido = db.get_or_404(Pedido, pedido_id, description=f'No existe el pedido {pedido_id}')
    return jsonify([d.to_dict() for d in pedido.detalles]), 200


@api.route('/pedidos/<int:pedido_id>/detalles/<int:producto_id>', methods=['GET'])
def get_detalle(pedido_id, producto_id):
    db.get_or_404(Pedido, pedido_id, description=f'No existe el pedido {pedido_id}')
    return jsonify(get_line(pedido_id, producto_id).to_dict()), 200


@api.route('/pedidos/<int:pedido_id>/detalles', methods=['POST'])
def create_detalle(pedido_id):
    pedido = db.get_or_404(Pedido, pedido_id, description=f'No existe el pedido {pedido_id}')
    producto, cantidad = line_values(get_body())
    if db.session.get(DetallePedido, (pedido_id, producto.producto_id)) is not None:
        abort(409, f'El pedido {pedido_id} ya tiene el producto {producto.producto_id}; modifique esa línea')
    try:
        take_stock(pedido.tienda_id, producto.producto_id, cantidad)
        line = DetallePedido(pedido_id=pedido_id, producto_id=producto.producto_id, cantidad_comprada=cantidad,
                             precio_unitario=producto.precio_unitario)
        db.session.add(line)
        change_points(pedido.cliente, points_for(cantidad))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify(line.to_dict()), 201


@api.route('/pedidos/<int:pedido_id>/detalles/<int:producto_id>', methods=['PUT'])
def update_detalle(pedido_id, producto_id):
    pedido = db.get_or_404(Pedido, pedido_id, description=f'No existe el pedido {pedido_id}')
    line = get_line(pedido_id, producto_id)
    cantidad = decimal_value(get_body(), 'cantidad_comprada')
    if cantidad <= 0 or cantidad > MAX_LINE_QTY:
        abort(400, f"El campo 'cantidad_comprada' debe ser mayor que 0 y como máximo {MAX_LINE_QTY}")
    old = Decimal(line.cantidad_comprada)
    try:
        if cantidad > old:
            take_stock(pedido.tienda_id, producto_id, cantidad - old)
        elif cantidad < old:
            return_stock(pedido.tienda_id, producto_id, old - cantidad)
        change_points(pedido.cliente, points_for(cantidad) - points_for(old))
        line.cantidad_comprada = cantidad
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify(line.to_dict()), 200


@api.route('/pedidos/<int:pedido_id>/detalles/<int:producto_id>', methods=['DELETE'])
def delete_detalle(pedido_id, producto_id):
    pedido = db.get_or_404(Pedido, pedido_id, description=f'No existe el pedido {pedido_id}')
    line = get_line(pedido_id, producto_id)
    if len(pedido.detalles) == 1:
        abort(409, 'Un pedido necesita al menos un producto; anule el pedido completo')
    try:
        return_stock(pedido.tienda_id, producto_id, line.cantidad_comprada)
        change_points(pedido.cliente, -line.puntos)
        db.session.delete(line)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify({'message': f'Producto {producto_id} quitado del pedido {pedido_id}'}), 200


# ---------------------------------------------------------------- reports

# Subtotal of one line rounded to cents, the same as DetallePedido.subtotal in Python, so an order
# total and the reports always agree. SQLite keeps decimals as floats (0.015 is 0.01499...), so a
# tiny amount is added before ROUND to round halves up like Python and MySQL do.
SUBTOTAL = db.func.round(DetallePedido.cantidad_comprada * DetallePedido.precio_unitario + 0.000001, 2)


def report_dates():
    """Optional ?desde=YYYY-MM-DD&hasta=YYYY-MM-DD filter on the order date (both days included)."""
    filters = []
    for name in ('desde', 'hasta'):
        value = request.args.get(name)
        if value:
            try:
                day = date.fromisoformat(value)
            except ValueError:
                abort(400, f"El parámetro '{name}' debe ser una fecha con formato AAAA-MM-DD")
            start = datetime.combine(day, datetime.min.time())
            filters.append(Pedido.fecha_exacta >= start if name == 'desde'
                           else Pedido.fecha_exacta < start + timedelta(days=1))
    return filters


def limit_value(default=5):
    limite = request.args.get('limite', default, type=int)
    if limite is None or limite < 1 or limite > 100:
        abort(400, "El parámetro 'limite' debe ser un entero entre 1 y 100")
    return limite


@api.route('/reportes/ventas-por-tienda', methods=['GET'])
def report_store_sales():
    ingresos = db.func.coalesce(db.func.sum(SUBTOTAL), 0)
    query = (db.select(Tienda.tienda_id, Tienda.nombre_sucursal,
                       db.func.count(db.distinct(Pedido.pedido_id)), ingresos)
             .select_from(Tienda)
             .outerjoin(Pedido, db.and_(Pedido.tienda_id == Tienda.tienda_id, *report_dates()))
             .outerjoin(DetallePedido, DetallePedido.pedido_id == Pedido.pedido_id)
             .group_by(Tienda.tienda_id, Tienda.nombre_sucursal)
             .order_by(ingresos.desc(), Tienda.tienda_id))
    rows = db.session.execute(query).all()
    return jsonify([{
        'tienda_id': r[0], 'nombre_sucursal': r[1], 'pedidos': r[2], 'ingresos': money(r[3]),
        'ticket_promedio': money(Decimal(str(r[3])) / r[2]) if r[2] else 0.0,
    } for r in rows]), 200


@api.route('/reportes/productos-mas-vendidos', methods=['GET'])
def report_top_products():
    query = (db.select(Producto.producto_id, Producto.nombre, Producto.unidad_medida,
                       db.func.sum(DetallePedido.cantidad_comprada), db.func.sum(SUBTOTAL),
                       db.func.count(DetallePedido.pedido_id))
             .select_from(DetallePedido)
             .join(Producto, Producto.producto_id == DetallePedido.producto_id)
             .join(Pedido, Pedido.pedido_id == DetallePedido.pedido_id)
             .where(*report_dates())
             .group_by(Producto.producto_id, Producto.nombre, Producto.unidad_medida)
             .order_by(db.func.sum(SUBTOTAL).desc(), Producto.producto_id)
             .limit(limit_value()))
    rows = db.session.execute(query).all()
    return jsonify([{
        'producto_id': r[0], 'nombre': r[1], 'unidad_medida': r[2], 'cantidad_vendida': money(r[3]),
        'ingresos': money(r[4]), 'pedidos': r[5],
    } for r in rows]), 200


@api.route('/reportes/top-clientes', methods=['GET'])
def report_top_customers():
    query = (db.select(Cliente.cliente_id, Cliente.nombre_completo, Cliente.puntos_ecologicos,
                       db.func.count(db.distinct(Pedido.pedido_id)), db.func.sum(SUBTOTAL))
             .select_from(Cliente)
             .join(Pedido, Pedido.cliente_id == Cliente.cliente_id)
             .join(DetallePedido, DetallePedido.pedido_id == Pedido.pedido_id)
             .where(*report_dates())
             .group_by(Cliente.cliente_id, Cliente.nombre_completo, Cliente.puntos_ecologicos)
             .order_by(db.func.sum(SUBTOTAL).desc(), Cliente.cliente_id)
             .limit(limit_value()))
    rows = db.session.execute(query).all()
    return jsonify([{
        'cliente_id': r[0], 'nombre_completo': r[1], 'puntos_ecologicos': r[2], 'pedidos': r[3],
        'total_gastado': money(r[4]),
    } for r in rows]), 200


@api.route('/reportes/ventas-diarias', methods=['GET'])
def report_daily_sales():
    """Last ?dias=N days (default 30), or the days between ?desde= and ?hasta= (hasta defaults to today)."""
    def parse(name):
        try:
            return date.fromisoformat(request.args[name])
        except ValueError:
            abort(400, f"El parámetro '{name}' debe ser una fecha con formato AAAA-MM-DD")

    last = parse('hasta') if request.args.get('hasta') else date.today()
    if request.args.get('desde'):
        first = parse('desde')
        dias = (last - first).days + 1
    else:
        dias = request.args.get('dias', 30, type=int)
        if dias is None or dias < 1 or dias > 366:
            abort(400, "El parámetro 'dias' debe ser un entero entre 1 y 366")
        first = last - timedelta(days=dias - 1)
    if dias < 1 or dias > 366:
        abort(400, "El rango debe tener entre 1 y 366 días y 'desde' no puede ser posterior a 'hasta'")

    day = db.func.date(Pedido.fecha_exacta)
    query = (db.select(day, db.func.count(db.distinct(Pedido.pedido_id)), db.func.sum(SUBTOTAL))
             .select_from(Pedido)
             .join(DetallePedido, DetallePedido.pedido_id == Pedido.pedido_id)
             .where(Pedido.fecha_exacta >= datetime.combine(first, datetime.min.time()),
                    Pedido.fecha_exacta < datetime.combine(last + timedelta(days=1), datetime.min.time()))
             .group_by(day))
    found = {str(r[0]): r for r in db.session.execute(query).all()}
    result = []
    for i in range(dias):
        key = (first + timedelta(days=i)).isoformat()
        row = found.get(key)
        result.append({'fecha': key, 'pedidos': row[1] if row else 0,
                       'ingresos': money(row[2]) if row else 0.0})
    return jsonify(result), 200


@api.route('/resumen', methods=['GET'])
def resumen():
    stock_bajo = db.session.execute(
        db.select(db.func.count()).select_from(Inventario).where(Inventario.cantidad_stock < Decimal('10.00'))
    ).scalar()
    ingresos = db.session.execute(db.select(db.func.coalesce(db.func.sum(SUBTOTAL), 0))).scalar()
    puntos = db.session.execute(db.select(db.func.coalesce(db.func.sum(Cliente.puntos_ecologicos), 0))).scalar()
    return jsonify({
        'clientes': count(Cliente),
        'tiendas': count(Tienda),
        'productos': count(Producto),
        'pedidos': count(Pedido),
        'stock_bajo': stock_bajo,
        'ingresos': money(ingresos),
        'puntos_ecologicos': int(puntos),
    }), 200
