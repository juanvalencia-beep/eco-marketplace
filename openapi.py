"""OpenAPI 3 description of the API. Served at /api/openapi.json and shown with Swagger UI at /api/docs."""


def ref(name):
    return {'$ref': f'#/components/schemas/{name}'}


def array(name):
    return {'type': 'array', 'items': ref(name)}


def body(schema, example=None):
    content = {'schema': schema}
    if example is not None:
        content['example'] = example
    return {'required': True, 'content': {'application/json': content}}


def ok(schema, code='200', text='OK'):
    return {code: {'description': text, 'content': {'application/json': {'schema': schema}}}}


def errors(*codes):
    text = {'400': 'Invalid or missing field', '404': 'Not found',
            '409': 'Conflict with a constraint (duplicate, not enough stock, delete blocked)'}
    return {c: {'description': text[c], 'content': {'application/json': {'schema': ref('Error')}}} for c in codes}


def path_id(name, text):
    return {'name': name, 'in': 'path', 'required': True, 'schema': {'type': 'integer'}, 'description': text}


def query(name, schema, text):
    return {'name': name, 'in': 'query', 'required': False, 'schema': schema, 'description': text}


def op(tag, summary, responses, params=None, request=None, description=None):
    data = {'tags': [tag], 'summary': summary, 'responses': responses}
    if params:
        data['parameters'] = params
    if request:
        data['requestBody'] = request
    if description:
        data['description'] = description
    return data


MESSAGE = ok({'type': 'object', 'properties': {'message': {'type': 'string'}}})
NUM = {'type': 'number', 'format': 'double'}
INT = {'type': 'integer'}
STR = {'type': 'string'}
DATES = [query('desde', {'type': 'string', 'format': 'date'}, 'From this day (YYYY-MM-DD)'),
         query('hasta', {'type': 'string', 'format': 'date'}, 'Until this day, included (YYYY-MM-DD)')]
LIMIT = query('limite', {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 5}, 'How many rows')

C, T, P = path_id('cliente_id', 'Customer id'), path_id('tienda_id', 'Store id'), path_id('producto_id', 'Product id')
O = path_id('pedido_id', 'Order id')


def obj(required=(), **props):
    data = {'type': 'object', 'properties': props}
    if required:
        data['required'] = list(required)
    return data


SCHEMAS = {
    'Error': obj(error=STR),
    'Cliente': obj(cliente_id=INT, nombre_completo=STR, correo_electronico=STR, puntos_ecologicos=INT),
    'ClienteInput': obj(['nombre_completo', 'correo_electronico'], nombre_completo=STR,
                        correo_electronico={'type': 'string', 'format': 'email'}),
    'ClienteUpdate': obj(nombre_completo=STR, correo_electronico=STR, puntos_ecologicos=INT),
    'Tienda': obj(tienda_id=INT, nombre_sucursal=STR, direccion=STR),
    'TiendaInput': obj(['nombre_sucursal', 'direccion'], nombre_sucursal=STR, direccion=STR),
    'Producto': obj(producto_id=INT, nombre=STR, unidad_medida=STR, precio_unitario=NUM),
    'ProductoInput': obj(['nombre', 'unidad_medida', 'precio_unitario'], nombre=STR, unidad_medida=STR, precio_unitario=NUM),
    'Inventario': obj(tienda_id=INT, producto_id=INT, cantidad_stock=NUM, nombre_sucursal=STR,
                      nombre_producto=STR, unidad_medida=STR),
    'InventarioInput': obj(['tienda_id', 'producto_id', 'cantidad_stock'], tienda_id=INT, producto_id=INT,
                           cantidad_stock=NUM),
    'Detalle': obj(pedido_id=INT, producto_id=INT, nombre_producto=STR, unidad_medida=STR, cantidad=NUM,
                   precio_unitario=NUM, subtotal=NUM, puntos=INT),
    'DetalleInput': obj(['producto_id', 'cantidad'], producto_id=INT,
                        cantidad={'type': 'number', 'minimum': 0.01, 'maximum': 10000}),
    'Pedido': obj(pedido_id=INT, fecha_exacta={'type': 'string', 'format': 'date-time'}, cliente_id=INT,
                  tienda_id=INT, nombre_completo=STR, nombre_sucursal=STR, num_productos=INT,
                  cantidad_total=NUM, total=NUM, puntos_ganados=INT, detalles=array('Detalle')),
    'PedidoInput': obj(['cliente_id', 'tienda_id', 'detalles'], cliente_id=INT, tienda_id=INT,
                       fecha_exacta={'type': 'string', 'format': 'date-time'},
                       detalles={'type': 'array', 'minItems': 1, 'maxItems': 50, 'items': ref('DetalleInput')}),
    'Resumen': obj(clientes=INT, tiendas=INT, productos=INT, pedidos=INT, stock_bajo=INT, ingresos=NUM,
                   puntos_ecologicos=INT),
    'VentasTienda': obj(tienda_id=INT, nombre_sucursal=STR, pedidos=INT, ingresos=NUM, ticket_promedio=NUM),
    'ProductoVendido': obj(producto_id=INT, nombre=STR, unidad_medida=STR, cantidad_vendida=NUM, ingresos=NUM,
                           pedidos=INT),
    'TopCliente': obj(cliente_id=INT, nombre_completo=STR, puntos_ecologicos=INT, pedidos=INT, total_gastado=NUM),
    'VentaDiaria': obj(fecha={'type': 'string', 'format': 'date'}, pedidos=INT, ingresos=NUM),
}

PATHS = {
    '/clientes': {
        'get': op('Clientes', 'List customers', ok(array('Cliente')),
                  [query('q', STR, 'Filter by name or email')]),
        'post': op('Clientes', 'Create a customer (starts with 0 eco-points)',
                   {**ok(ref('Cliente'), '201', 'Created'), **errors('400', '409')},
                   request=body(ref('ClienteInput'), {'nombre_completo': 'Ana Pérez',
                                                      'correo_electronico': 'ana.perez@example.com'})),
    },
    '/clientes/{cliente_id}': {
        'get': op('Clientes', 'Get a customer', {**ok(ref('Cliente')), **errors('404')}, [C]),
        'put': op('Clientes', 'Update a customer', {**ok(ref('Cliente')), **errors('400', '404', '409')}, [C],
                  body(ref('ClienteUpdate'))),
        'delete': op('Clientes', 'Delete a customer (409 if they have orders)', {**MESSAGE, **errors('404', '409')},
                     [C]),
    },
    '/clientes/{cliente_id}/pedidos': {
        'get': op('Clientes', 'Order history of a customer, newest first', {**ok(array('Pedido')), **errors('404')},
                  [C]),
    },
    '/tiendas': {
        'get': op('Tiendas', 'List stores', ok(array('Tienda'))),
        'post': op('Tiendas', 'Create a store', {**ok(ref('Tienda'), '201', 'Created'), **errors('400')},
                   request=body(ref('TiendaInput'))),
    },
    '/tiendas/{tienda_id}': {
        'get': op('Tiendas', 'Get a store', {**ok(ref('Tienda')), **errors('404')}, [T]),
        'put': op('Tiendas', 'Update a store', {**ok(ref('Tienda')), **errors('400', '404')}, [T],
                  body(ref('TiendaInput'))),
        'delete': op('Tiendas', 'Delete a store (409 if it has inventory or orders)',
                     {**MESSAGE, **errors('404', '409')}, [T]),
    },
    '/productos': {
        'get': op('Productos', 'List products', ok(array('Producto'))),
        'post': op('Productos', 'Create a product', {**ok(ref('Producto'), '201', 'Created'), **errors('400')},
                   request=body(ref('ProductoInput'), {'nombre': 'Granola', 'unidad_medida': 'kg',
                                                       'precio_unitario': 7.4})),
    },
    '/productos/{producto_id}': {
        'get': op('Productos', 'Get a product', {**ok(ref('Producto')), **errors('404')}, [P]),
        'put': op('Productos', 'Update a product', {**ok(ref('Producto')), **errors('400', '404')}, [P],
                  body(ref('ProductoInput'))),
        'delete': op('Productos', 'Delete a product (409 if it has inventory or order lines)',
                     {**MESSAGE, **errors('404', '409')}, [P]),
    },
    '/inventario': {
        'get': op('Inventario', 'List stock rows', ok(array('Inventario')),
                  [query('tienda_id', INT, 'Only this store')]),
        'post': op('Inventario', 'Add a product to a store', {**ok(ref('Inventario'), '201', 'Created'),
                                                              **errors('400', '404', '409')},
                   request=body(ref('InventarioInput'))),
    },
    '/inventario/stock-bajo': {
        'get': op('Inventario', 'Low stock report (stock below the limit)', ok(array('Inventario')),
                  [query('limite', NUM, 'Limit, default 10.00')]),
    },
    '/inventario/{tienda_id}/{producto_id}': {
        'get': op('Inventario', 'Get one stock row', {**ok(ref('Inventario')), **errors('404')}, [T, P]),
        'put': op('Inventario', 'Set the stock', {**ok(ref('Inventario')), **errors('400', '404')}, [T, P],
                  body(obj(['cantidad_stock'], cantidad_stock=NUM))),
        'delete': op('Inventario', 'Remove the product from the store', {**MESSAGE, **errors('404')}, [T, P]),
    },
    '/pedidos': {
        'get': op('Pedidos', 'List orders with their lines, newest first', ok(array('Pedido')),
                  [query('cliente_id', INT, 'Only this customer'), query('tienda_id', INT, 'Only this store')]),
        'post': op('Pedidos', 'Register an order with one or more products',
                   {**ok(ref('Pedido'), '201', 'Created'), **errors('400', '404', '409')},
                   request=body(ref('PedidoInput'), {'cliente_id': 1, 'tienda_id': 1, 'detalles': [
                       {'producto_id': 1, 'cantidad': 2.5}, {'producto_id': 2, 'cantidad': 1}]}),
                   description='One transaction: saves the header and the lines, subtracts the stock of every '
                               'line and adds 10 eco-points per unit. If one line has no stock nothing is saved. '
                               'The price of each line is taken from the product, not from the request.'),
    },
    '/pedidos/{pedido_id}': {
        'get': op('Pedidos', 'Get an order with its lines', {**ok(ref('Pedido')), **errors('404')}, [O]),
        'put': op('Pedidos', 'Change the date of an order', {**ok(ref('Pedido')), **errors('400', '404')}, [O],
                  body(obj(['fecha_exacta'], fecha_exacta={'type': 'string', 'format': 'date-time'}))),
        'delete': op('Pedidos', 'Cancel an order (stock goes back, points are removed)',
                     {**MESSAGE, **errors('404')}, [O]),
    },
    '/pedidos/{pedido_id}/detalles': {
        'get': op('Detalle de pedido', 'List the lines of an order', {**ok(array('Detalle')), **errors('404')}, [O]),
        'post': op('Detalle de pedido', 'Add a product to an order',
                   {**ok(ref('Detalle'), '201', 'Created'), **errors('400', '404', '409')}, [O],
                   body(ref('DetalleInput'))),
    },
    '/pedidos/{pedido_id}/detalles/{producto_id}': {
        'get': op('Detalle de pedido', 'Get one line', {**ok(ref('Detalle')), **errors('404')}, [O, P]),
        'put': op('Detalle de pedido', 'Change the quantity of a line (stock and points are adjusted)',
                  {**ok(ref('Detalle')), **errors('400', '404', '409')}, [O, P],
                  body(obj(['cantidad'], cantidad=NUM))),
        'delete': op('Detalle de pedido', 'Remove a line (409 if it is the last one)',
                     {**MESSAGE, **errors('404', '409')}, [O, P]),
    },
    '/reportes/ventas-por-tienda': {
        'get': op('Reportes', 'Orders, revenue and average ticket per store', ok(array('VentasTienda')), DATES),
    },
    '/reportes/productos-mas-vendidos': {
        'get': op('Reportes', 'Best-selling products by revenue', ok(array('ProductoVendido')), [LIMIT, *DATES]),
    },
    '/reportes/top-clientes': {
        'get': op('Reportes', 'Customers who spent the most', ok(array('TopCliente')), [LIMIT, *DATES]),
    },
    '/reportes/ventas-diarias': {
        'get': op('Reportes', 'Orders and revenue per day', ok(array('VentaDiaria')),
                  [query('dias', {'type': 'integer', 'minimum': 1, 'maximum': 366, 'default': 30}, 'Last N days'),
                   *DATES]),
    },
    '/resumen': {
        'get': op('Reportes', 'Dashboard counters', ok(ref('Resumen'))),
    },
}

SPEC = {
    'openapi': '3.0.3',
    'info': {
        'title': 'Eco-Marketplace API',
        'version': '2.0',
        'description': 'REST API (Flask + Flask-SQLAlchemy) for the Eco-Marketplace refill stations. '
                       'All bodies are JSON and errors come as {"error": "message"}.',
    },
    'servers': [{'url': '/api'}],
    'tags': [{'name': n} for n in ('Clientes', 'Tiendas', 'Productos', 'Inventario', 'Pedidos',
                                   'Detalle de pedido', 'Reportes')],
    'paths': PATHS,
    'components': {'schemas': SCHEMAS},
}

SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Eco-Marketplace API docs</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css"
        integrity="sha384-wxLW6kwyHktdDGr6Pv1zgm/VGJh99lfUbzSn6HNHBENZlCN7W602k9VkGdxuFvPn" crossorigin="anonymous">
  <style>body { margin: 0; } .topbar { display: none; }</style>
</head>
<body>
  <div id="swagger"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"
          integrity="sha384-wmyclcVGX/WhUkdkATwhaK1X1JtiNrr2EoYJ+diV3vj4v6OC5yCeSu+yW13SYJep" crossorigin="anonymous"></script>
  <script>
    SwaggerUIBundle({ url: "/api/openapi.json", dom_id: "#swagger", deepLinking: true,
                      defaultModelsExpandDepth: 0, docExpansion: "list" });
  </script>
</body>
</html>
"""
