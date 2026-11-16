from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, jsonify, request

from models import db, Cliente, Tienda, Producto, Inventario, Pedido, points_for

api = Blueprint('api', __name__)

MAX_AMOUNT = Decimal('99999999.99')  # biggest value that fits in DECIMAL(10,2)


def get_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, 'Request body must be a JSON object')
    return data


def text_value(data, name, max_len):
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        abort(400, f"Field '{name}' is required and must be a non-empty text")
    value = value.strip()
    if len(value) > max_len:
        abort(400, f"Field '{name}' can have at most {max_len} characters")
    return value


def int_value(data, name):
    value = data.get(name)
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        abort(400, f"Field '{name}' is required and must be an integer")
    return value


def decimal_value(data, name):
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        abort(400, f"Field '{name}' is required and must be a number")
    try:
        number = Decimal(str(value).strip())
        if not number.is_finite() or abs(number) > MAX_AMOUNT:
            raise InvalidOperation
        return number.quantize(Decimal('0.01'))
    except InvalidOperation:
        abort(400, f"Field '{name}' must be a number between -{MAX_AMOUNT} and {MAX_AMOUNT}")


def email_value(data):
    email = text_value(data, 'correo_electronico', 120).lower()
    if '@' not in email or '.' not in email.split('@')[-1]:
        abort(400, 'Invalid email address')
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
    cliente = db.get_or_404(Cliente, cliente_id, description=f'Customer {cliente_id} not found')
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
    cliente = db.get_or_404(Cliente, cliente_id, description=f'Customer {cliente_id} not found')
    data = get_body()
    if 'nombre_completo' in data:
        cliente.nombre_completo = text_value(data, 'nombre_completo', 100)
    if 'correo_electronico' in data:
        cliente.correo_electronico = email_value(data)
    if 'puntos_ecologicos' in data:
        puntos = int_value(data, 'puntos_ecologicos')
        if puntos < 0:
            abort(400, "Field 'puntos_ecologicos' cannot be negative")
        cliente.puntos_ecologicos = puntos
    db.session.commit()
    return jsonify(cliente.to_dict()), 200


@api.route('/clientes/<int:cliente_id>', methods=['DELETE'])
def delete_cliente(cliente_id):
    cliente = db.get_or_404(Cliente, cliente_id, description=f'Customer {cliente_id} not found')
    if count(Pedido, cliente_id=cliente_id) > 0:
        return jsonify({'error': f'Customer {cliente_id} has orders and cannot be deleted'}), 409
    db.session.delete(cliente)
    db.session.commit()
    return jsonify({'message': f'Customer {cliente_id} deleted'}), 200


@api.route('/clientes/<int:cliente_id>/pedidos', methods=['GET'])
def cliente_pedidos(cliente_id):
    db.get_or_404(Cliente, cliente_id, description=f'Customer {cliente_id} not found')
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
    tienda = db.get_or_404(Tienda, tienda_id, description=f'Store {tienda_id} not found')
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
    tienda = db.get_or_404(Tienda, tienda_id, description=f'Store {tienda_id} not found')
    data = get_body()
    if 'nombre_sucursal' in data:
        tienda.nombre_sucursal = text_value(data, 'nombre_sucursal', 100)
    if 'direccion' in data:
        tienda.direccion = text_value(data, 'direccion', 200)
    db.session.commit()
    return jsonify(tienda.to_dict()), 200


@api.route('/tiendas/<int:tienda_id>', methods=['DELETE'])
def delete_tienda(tienda_id):
    tienda = db.get_or_404(Tienda, tienda_id, description=f'Store {tienda_id} not found')
    if count(Inventario, tienda_id=tienda_id) > 0 or count(Pedido, tienda_id=tienda_id) > 0:
        return jsonify({'error': f'Store {tienda_id} has inventory or orders and cannot be deleted'}), 409
    db.session.delete(tienda)
    db.session.commit()
    return jsonify({'message': f'Store {tienda_id} deleted'}), 200


@api.route('/productos', methods=['GET'])
def list_productos():
    productos = db.session.execute(db.select(Producto).order_by(Producto.producto_id)).scalars().all()
    return jsonify([p.to_dict() for p in productos]), 200


@api.route('/productos/<int:producto_id>', methods=['GET'])
def get_producto(producto_id):
    producto = db.get_or_404(Producto, producto_id, description=f'Product {producto_id} not found')
    return jsonify(producto.to_dict()), 200


@api.route('/productos', methods=['POST'])
def create_producto():
    data = get_body()
    producto = Producto(
        nombre=text_value(data, 'nombre', 100),
        unidad_medida=text_value(data, 'unidad_medida', 20),
    )
    db.session.add(producto)
    db.session.commit()
    return jsonify(producto.to_dict()), 201


@api.route('/productos/<int:producto_id>', methods=['PUT'])
def update_producto(producto_id):
    producto = db.get_or_404(Producto, producto_id, description=f'Product {producto_id} not found')
    data = get_body()
    if 'nombre' in data:
        producto.nombre = text_value(data, 'nombre', 100)
    if 'unidad_medida' in data:
        producto.unidad_medida = text_value(data, 'unidad_medida', 20)
    db.session.commit()
    return jsonify(producto.to_dict()), 200


@api.route('/productos/<int:producto_id>', methods=['DELETE'])
def delete_producto(producto_id):
    producto = db.get_or_404(Producto, producto_id, description=f'Product {producto_id} not found')
    if count(Inventario, producto_id=producto_id) > 0 or count(Pedido, producto_id=producto_id) > 0:
        return jsonify({'error': f'Product {producto_id} has inventory or orders and cannot be deleted'}), 409
    db.session.delete(producto)
    db.session.commit()
    return jsonify({'message': f'Product {producto_id} deleted'}), 200


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
        abort(404, f'Store {tienda_id} has no inventory row for product {producto_id}')
    return jsonify(row.to_dict()), 200


@api.route('/inventario', methods=['POST'])
def create_inventario():
    data = get_body()
    tienda_id = int_value(data, 'tienda_id')
    producto_id = int_value(data, 'producto_id')
    stock = decimal_value(data, 'cantidad_stock')
    if stock < 0:
        abort(400, "Field 'cantidad_stock' cannot be negative")
    db.get_or_404(Tienda, tienda_id, description=f'Store {tienda_id} not found')
    db.get_or_404(Producto, producto_id, description=f'Product {producto_id} not found')
    if find_inventory(tienda_id, producto_id) is not None:
        return jsonify({'error': f'Store {tienda_id} already has an inventory row for product {producto_id}'}), 409

    row = Inventario(tienda_id=tienda_id, producto_id=producto_id, cantidad_stock=stock)
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict()), 201


@api.route('/inventario/<int:tienda_id>/<int:producto_id>', methods=['PUT'])
def update_inventario(tienda_id, producto_id):
    row = find_inventory(tienda_id, producto_id)
    if row is None:
        abort(404, f'Store {tienda_id} has no inventory row for product {producto_id}')
    stock = decimal_value(get_body(), 'cantidad_stock')
    if stock < 0:
        abort(400, "Field 'cantidad_stock' cannot be negative")
    row.cantidad_stock = stock
    db.session.commit()
    return jsonify(row.to_dict()), 200


@api.route('/inventario/<int:tienda_id>/<int:producto_id>', methods=['DELETE'])
def delete_inventario(tienda_id, producto_id):
    row = find_inventory(tienda_id, producto_id)
    if row is None:
        abort(404, f'Store {tienda_id} has no inventory row for product {producto_id}')
    db.session.delete(row)
    db.session.commit()
    return jsonify({'message': f'Inventory row ({tienda_id}, {producto_id}) deleted'}), 200


@api.route('/pedidos', methods=['GET'])
def list_pedidos():
    query = db.select(Pedido).order_by(Pedido.fecha_exacta.desc(), Pedido.pedido_id.desc())
    pedidos = db.session.execute(query).scalars().all()
    return jsonify([p.to_dict() for p in pedidos]), 200


@api.route('/pedidos/<int:pedido_id>', methods=['GET'])
def get_pedido(pedido_id):
    pedido = db.get_or_404(Pedido, pedido_id, description=f'Order {pedido_id} not found')
    return jsonify(pedido.to_dict()), 200


@api.route('/pedidos', methods=['POST'])
def create_pedido():
    data = get_body()
    cliente_id = int_value(data, 'cliente_id')
    tienda_id = int_value(data, 'tienda_id')
    producto_id = int_value(data, 'producto_id')
    cantidad = decimal_value(data, 'cantidad_comprada')
    if cantidad <= 0:
        abort(400, "Field 'cantidad_comprada' must be greater than 0")

    fecha = datetime.now().replace(microsecond=0)
    if data.get('fecha_exacta'):
        try:
            fecha = datetime.fromisoformat(str(data['fecha_exacta'])).replace(microsecond=0, tzinfo=None)
        except ValueError:
            abort(400, "Field 'fecha_exacta' must be a date like YYYY-MM-DDTHH:MM:SS")

    cliente = db.get_or_404(Cliente, cliente_id, description=f'Customer {cliente_id} not found')
    db.get_or_404(Tienda, tienda_id, description=f'Store {tienda_id} not found')
    db.get_or_404(Producto, producto_id, description=f'Product {producto_id} not found')

    # Everything below is one transaction (FR-05): either the order is saved,
    # the stock goes down and the points go up, or nothing changes at all.
    try:
        row = find_inventory(tienda_id, producto_id, lock=True)
        if row is None:
            db.session.rollback()
            return jsonify({'error': f'Store {tienda_id} does not sell product {producto_id}'}), 409
        if row.cantidad_stock < cantidad:
            db.session.rollback()
            return jsonify({'error': f'Not enough stock: available {row.cantidad_stock}, requested {cantidad}'}), 409

        pedido = Pedido(fecha_exacta=fecha, cantidad_comprada=cantidad, cliente_id=cliente_id,
                        tienda_id=tienda_id, producto_id=producto_id)
        db.session.add(pedido)
        # Subtract in SQL (stock = stock - x) instead of writing a value computed in
        # Python, so two orders at the same time can't overwrite each other. If the
        # stock would go negative the CHECK constraint stops it.
        row.cantidad_stock = Inventario.cantidad_stock - cantidad
        cliente.puntos_ecologicos = Cliente.puntos_ecologicos + points_for(cantidad)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(pedido.to_dict()), 201


@api.route('/pedidos/<int:pedido_id>', methods=['DELETE'])
def cancel_pedido(pedido_id):
    pedido = db.get_or_404(Pedido, pedido_id, description=f'Order {pedido_id} not found')
    try:
        row = find_inventory(pedido.tienda_id, pedido.producto_id, lock=True)
        if row is None:
            # the inventory row was removed after the order, so create it again
            db.session.add(Inventario(tienda_id=pedido.tienda_id, producto_id=pedido.producto_id,
                                      cantidad_stock=pedido.cantidad_comprada))
        else:
            row.cantidad_stock = Inventario.cantidad_stock + pedido.cantidad_comprada

        cliente = pedido.cliente
        cliente.puntos_ecologicos = max(0, cliente.puntos_ecologicos - points_for(pedido.cantidad_comprada))
        db.session.delete(pedido)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({'message': f'Order {pedido_id} cancelled'}), 200


@api.route('/resumen', methods=['GET'])
def resumen():
    stock_bajo = db.session.execute(
        db.select(db.func.count()).select_from(Inventario).where(Inventario.cantidad_stock < Decimal('10.00'))
    ).scalar()
    return jsonify({
        'clientes': count(Cliente),
        'tiendas': count(Tienda),
        'productos': count(Producto),
        'pedidos': count(Pedido),
        'stock_bajo': stock_bajo,
    }), 200
