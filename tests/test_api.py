def order(client, cantidad=None, cliente_id=1, tienda_id=1, producto_id=1, lines=None, **extra):
    """Creates an order. Either one product (cantidad/producto_id) or several: lines=[(producto_id, cantidad)]."""
    lines = lines if lines is not None else [(producto_id, cantidad)]
    body = {'cliente_id': cliente_id, 'tienda_id': tienda_id,
            'detalles': [{'producto_id': p, 'cantidad': c} for p, c in lines], **extra}
    return client.post('/api/pedidos', json=body)


def stock(client, tienda_id=1, producto_id=1):
    return client.get(f'/api/inventario/{tienda_id}/{producto_id}').get_json()['cantidad_stock']


def points(client, cliente_id=1):
    return client.get(f'/api/clientes/{cliente_id}').get_json()['puntos_ecologicos']


def test_index_serves_gui(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b'<' in res.data
    res.close()


def test_list_clientes(client):
    res = client.get('/api/clientes')
    assert res.status_code == 200
    assert [c['cliente_id'] for c in res.get_json()] == [1, 2]
    assert res.get_json()[0] == {'cliente_id': 1, 'nombre_completo': 'Ana Pérez',
                                 'correo_electronico': 'ana.perez@example.com', 'puntos_ecologicos': 0}


def test_search_clientes(client):
    assert [c['nombre_completo'] for c in client.get('/api/clientes?q=andrade').get_json()] == ['Carlos Andrade']
    assert len(client.get('/api/clientes?q=example.com').get_json()) == 2


def test_create_cliente_starts_with_zero_points(client):
    res = client.post('/api/clientes', json={'nombre_completo': 'Diego Salazar',
                                             'correo_electronico': 'diego.salazar@example.com',
                                             'puntos_ecologicos': 500})
    assert res.status_code == 201
    assert res.get_json()['cliente_id'] == 3
    assert res.get_json()['puntos_ecologicos'] == 0


def test_create_cliente_missing_field(client):
    res = client.post('/api/clientes', json={'nombre_completo': 'Sin Correo'})
    assert res.status_code == 400
    assert 'correo_electronico' in res.get_json()['error']


def test_create_cliente_without_json(client):
    res = client.post('/api/clientes', data='hola', content_type='text/plain')
    assert res.status_code == 400


def test_create_cliente_duplicate_email(client):
    res = client.post('/api/clientes', json={'nombre_completo': 'Otra Ana',
                                             'correo_electronico': 'ana.perez@example.com'})
    assert res.status_code == 409
    assert 'email' in res.get_json()['error']


def test_update_cliente(client):
    res = client.put('/api/clientes/2', json={'nombre_completo': 'Carlos A. Andrade', 'puntos_ecologicos': 40})
    assert res.status_code == 200
    assert res.get_json()['nombre_completo'] == 'Carlos A. Andrade'
    assert points(client, 2) == 40


def test_update_cliente_invalid_values(client):
    assert client.put('/api/clientes/1', json={'puntos_ecologicos': -5}).status_code == 400
    assert client.put('/api/clientes/1', json={'puntos_ecologicos': 'many'}).status_code == 400
    assert client.put('/api/clientes/1', json={'correo_electronico': 'not-an-email'}).status_code == 400


def test_update_cliente_to_duplicate_email(client):
    res = client.put('/api/clientes/2', json={'correo_electronico': 'ana.perez@example.com'})
    assert res.status_code == 409
    assert client.get('/api/clientes/2').get_json()['correo_electronico'] == 'carlos.andrade@example.com'


def test_cliente_not_found(client):
    assert client.get('/api/clientes/999').status_code == 404
    assert client.put('/api/clientes/999', json={'nombre_completo': 'X'}).status_code == 404
    res = client.delete('/api/clientes/999')
    assert res.status_code == 404
    assert res.get_json() == {'error': 'Customer 999 not found'}


def test_delete_cliente(client):
    assert client.delete('/api/clientes/2').status_code == 200
    assert client.get('/api/clientes/2').status_code == 404


def test_delete_cliente_with_orders_is_blocked(client):
    order(client, 1)
    res = client.delete('/api/clientes/1')
    assert res.status_code == 409
    assert client.get('/api/clientes/1').status_code == 200


def test_tiendas_crud(client):
    res = client.post('/api/tiendas', json={'nombre_sucursal': 'Sucursal Cumbayá',
                                            'direccion': 'Av. Interoceánica km 12.5'})
    assert res.status_code == 201
    tienda_id = res.get_json()['tienda_id']

    res = client.put(f'/api/tiendas/{tienda_id}', json={'direccion': 'Av. Pampite y Chimborazo'})
    assert res.get_json() == {'tienda_id': tienda_id, 'nombre_sucursal': 'Sucursal Cumbayá',
                              'direccion': 'Av. Pampite y Chimborazo'}
    assert len(client.get('/api/tiendas').get_json()) == 3

    assert client.delete(f'/api/tiendas/{tienda_id}').status_code == 200
    assert client.get(f'/api/tiendas/{tienda_id}').status_code == 404


def test_create_tienda_missing_field(client):
    assert client.post('/api/tiendas', json={'nombre_sucursal': 'Sin dirección'}).status_code == 400
    assert client.post('/api/tiendas', json={'nombre_sucursal': '  ', 'direccion': 'x'}).status_code == 400


def test_delete_tienda_with_inventory_is_blocked(client):
    res = client.delete('/api/tiendas/1')
    assert res.status_code == 409
    assert client.get('/api/tiendas/1').status_code == 200


def test_productos_crud(client):
    res = client.post('/api/productos', json={'nombre': 'Shampoo sólido', 'unidad_medida': 'units',
                                              'precio_unitario': 6.9})
    assert res.status_code == 201
    producto_id = res.get_json()['producto_id']
    assert client.get(f'/api/productos/{producto_id}').get_json() == {
        'producto_id': producto_id, 'nombre': 'Shampoo sólido', 'unidad_medida': 'units', 'precio_unitario': 6.9}

    res = client.put(f'/api/productos/{producto_id}', json={'unidad_medida': 'bars', 'precio_unitario': '7.25'})
    assert res.get_json()['unidad_medida'] == 'bars'
    assert res.get_json()['precio_unitario'] == 7.25
    assert client.put(f'/api/productos/{producto_id}', json={'precio_unitario': -1}).status_code == 400

    assert client.delete(f'/api/productos/{producto_id}').status_code == 200
    assert client.get(f'/api/productos/{producto_id}').status_code == 404


def test_delete_producto_with_inventory_is_blocked(client):
    assert client.delete('/api/productos/1').status_code == 409
    assert client.put('/api/productos/99', json={'nombre': 'X'}).status_code == 404


def test_list_inventario_and_filter(client):
    rows = client.get('/api/inventario').get_json()
    assert len(rows) == 3
    assert rows[0] == {'tienda_id': 1, 'producto_id': 1, 'cantidad_stock': 100.0,
                       'nombre_sucursal': 'Sucursal Centro', 'nombre_producto': 'Detergente líquido',
                       'unidad_medida': 'liters'}
    assert [r['producto_id'] for r in client.get('/api/inventario?tienda_id=1').get_json()] == [1, 2]


def test_create_inventario(client):
    res = client.post('/api/inventario', json={'tienda_id': 2, 'producto_id': 2, 'cantidad_stock': 25.5})
    assert res.status_code == 201
    assert res.get_json()['cantidad_stock'] == 25.5


def test_create_inventario_duplicate(client):
    res = client.post('/api/inventario', json={'tienda_id': 1, 'producto_id': 1, 'cantidad_stock': 10})
    assert res.status_code == 409
    assert stock(client) == 100.0


def test_create_inventario_bad_references(client):
    assert client.post('/api/inventario', json={'tienda_id': 9, 'producto_id': 1,
                                                'cantidad_stock': 10}).status_code == 404
    assert client.post('/api/inventario', json={'tienda_id': 2, 'producto_id': 9,
                                                'cantidad_stock': 10}).status_code == 404
    assert client.post('/api/inventario', json={'tienda_id': 2, 'producto_id': 2,
                                                'cantidad_stock': -1}).status_code == 400


def test_update_and_delete_inventario(client):
    res = client.put('/api/inventario/1/1', json={'cantidad_stock': 80.25})
    assert res.status_code == 200
    assert stock(client) == 80.25
    assert client.put('/api/inventario/1/1', json={'cantidad_stock': -3}).status_code == 400
    assert client.put('/api/inventario/1/1', json={'cantidad_stock': 'abc'}).status_code == 400

    assert client.delete('/api/inventario/2/1').status_code == 200
    assert client.get('/api/inventario/2/1').status_code == 404
    assert client.delete('/api/inventario/2/1').status_code == 404


def test_low_stock(client):
    rows = client.get('/api/inventario/stock-bajo').get_json()
    assert [(r['tienda_id'], r['producto_id'], r['cantidad_stock']) for r in rows] == [(1, 2, 5.0)]
    assert rows[0]['nombre_sucursal'] == 'Sucursal Centro'
    assert rows[0]['nombre_producto'] == 'Avena'

    assert len(client.get('/api/inventario/stock-bajo?limite=50').get_json()) == 2
    assert client.get('/api/inventario/stock-bajo?limite=abc').status_code == 400


def test_create_pedido_updates_stock_and_points(client):
    res = order(client, 2.5)
    assert res.status_code == 201
    data = res.get_json()
    assert data['cantidad_total'] == 2.5
    assert data['total'] == 7.0
    assert data['puntos_ganados'] == 25
    assert data['nombre_completo'] == 'Ana Pérez'
    assert data['detalles'] == [{'pedido_id': data['pedido_id'], 'producto_id': 1,
                                 'nombre_producto': 'Detergente líquido', 'unidad_medida': 'liters',
                                 'cantidad': 2.5, 'precio_unitario': 2.8, 'subtotal': 7.0, 'puntos': 25}]
    assert stock(client) == 97.5
    assert points(client) == 25


def test_create_pedido_with_date(client):
    res = order(client, 1.75, fecha_exacta='2026-11-10T09:15:00')
    assert res.status_code == 201
    assert res.get_json()['fecha_exacta'] == '2026-11-10T09:15:00'
    assert res.get_json()['puntos_ganados'] == 17
    assert order(client, 1, fecha_exacta='yesterday').status_code == 400


def test_create_pedido_not_enough_stock(client):
    res = order(client, 500)
    assert res.status_code == 409
    assert 'stock' in res.get_json()['error']
    assert stock(client) == 100.0
    assert points(client) == 0
    assert client.get('/api/pedidos').get_json() == []


def test_create_pedido_invalid_quantity(client):
    assert order(client, 0).status_code == 400
    assert order(client, -1).status_code == 400
    assert order(client, 'two').status_code == 400
    assert client.post('/api/pedidos', json={'cliente_id': 1, 'tienda_id': 1}).status_code == 400
    assert order(client, lines=[]).status_code == 400
    assert client.post('/api/pedidos', json={'cliente_id': 1, 'tienda_id': 1, 'detalles': [5]}).status_code == 400
    assert stock(client) == 100.0


def test_create_pedido_missing_references(client):
    assert order(client, 1, cliente_id=9999).status_code == 404
    assert order(client, 1, tienda_id=9999).status_code == 404
    assert order(client, 1, producto_id=9999).status_code == 404
    # store 2 has no inventory row for product 2
    assert order(client, 1, tienda_id=2, producto_id=2).status_code == 409


def test_cancel_pedido_restores_stock_and_points(client):
    pedido_id = order(client, 2.5).get_json()['pedido_id']
    order(client, 1.0)
    assert points(client) == 35

    res = client.delete(f'/api/pedidos/{pedido_id}')
    assert res.status_code == 200
    assert stock(client) == 99.0
    assert points(client) == 10
    assert client.get(f'/api/pedidos/{pedido_id}').status_code == 404
    assert client.delete(f'/api/pedidos/{pedido_id}').status_code == 404


def test_cancel_pedido_points_never_negative(client):
    pedido_id = order(client, 3).get_json()['pedido_id']
    client.put('/api/clientes/1', json={'puntos_ecologicos': 10})
    assert client.delete(f'/api/pedidos/{pedido_id}').status_code == 200
    assert points(client) == 0


def test_list_pedidos_newest_first(client):
    order(client, 1, fecha_exacta='2026-11-01T10:00:00')
    order(client, 1, fecha_exacta='2026-11-12T10:00:00')
    order(client, 1, fecha_exacta='2026-11-05T10:00:00')
    fechas = [p['fecha_exacta'] for p in client.get('/api/pedidos').get_json()]
    assert fechas == ['2026-11-12T10:00:00', '2026-11-05T10:00:00', '2026-11-01T10:00:00']


def test_cliente_history(client):
    order(client, 1, fecha_exacta='2026-11-01T09:00:00')
    order(client, 2, fecha_exacta='2026-11-10T12:00:00')
    order(client, 4, cliente_id=2, tienda_id=2, fecha_exacta='2026-11-12T08:00:00')
    order(client, 3, fecha_exacta='2026-11-05T18:30:00')

    history = client.get('/api/clientes/1/pedidos').get_json()
    assert [p['cantidad_total'] for p in history] == [2.0, 3.0, 1.0]
    assert all(p['cliente_id'] == 1 for p in history)
    assert client.get('/api/clientes/999/pedidos').status_code == 404


def test_resumen(client):
    order(client, 1)
    assert client.get('/api/resumen').get_json() == {
        'clientes': 2, 'tiendas': 2, 'productos': 2, 'pedidos': 1, 'stock_bajo': 1,
        'ingresos': 2.8, 'puntos_ecologicos': 10,
    }


def test_unknown_route_returns_json_error(client):
    res = client.get('/api/nothing-here')
    assert res.status_code == 404
    assert 'error' in res.get_json()


# ------------------------------------------------------------ order detail

def test_create_pedido_with_several_lines(client):
    res = order(client, lines=[(1, 2.5), (2, 1.25)])
    assert res.status_code == 201
    data = res.get_json()
    assert data['num_productos'] == 2
    assert [(d['producto_id'], d['cantidad'], d['subtotal']) for d in data['detalles']] == [(1, 2.5, 7.0), (2, 1.25, 4.0)]
    assert data['total'] == 11.0
    assert data['puntos_ganados'] == 37  # 25 + 12
    assert stock(client, 1, 1) == 97.5
    assert stock(client, 1, 2) == 3.75
    assert points(client) == 37


def test_create_pedido_one_bad_line_rolls_back_everything(client):
    """FR-05: the second line has no stock, so the first line is not saved either."""
    res = order(client, lines=[(1, 2.5), (2, 50)])
    assert res.status_code == 409
    assert 'Avena' in res.get_json()['error']
    assert stock(client, 1, 1) == 100.0
    assert stock(client, 1, 2) == 5.0
    assert points(client) == 0
    assert client.get('/api/pedidos').get_json() == []


def test_create_pedido_duplicate_product_rejected(client):
    assert order(client, lines=[(1, 1), (1, 2)]).status_code == 400
    assert stock(client) == 100.0


def test_price_is_copied_into_the_order_line(client):
    pedido_id = order(client, 2).get_json()['pedido_id']
    client.put('/api/productos/1', json={'precio_unitario': 9.99})
    line = client.get(f'/api/pedidos/{pedido_id}/detalles/1').get_json()
    assert line['precio_unitario'] == 2.8
    assert line['subtotal'] == 5.6


def test_detalles_crud(client):
    pedido_id = order(client, 2).get_json()['pedido_id']

    # add a line
    res = client.post(f'/api/pedidos/{pedido_id}/detalles', json={'producto_id': 2, 'cantidad': 1.5})
    assert res.status_code == 201
    assert res.get_json()['subtotal'] == 4.8
    assert stock(client, 1, 2) == 3.5
    assert points(client) == 35
    assert client.post(f'/api/pedidos/{pedido_id}/detalles',
                       json={'producto_id': 2, 'cantidad': 1}).status_code == 409

    # read
    lines = client.get(f'/api/pedidos/{pedido_id}/detalles').get_json()
    assert [l['producto_id'] for l in lines] == [1, 2]
    assert client.get(f'/api/pedidos/{pedido_id}').get_json()['total'] == 10.4

    # update: more quantity takes stock, less gives it back
    res = client.put(f'/api/pedidos/{pedido_id}/detalles/1', json={'cantidad': 5})
    assert res.status_code == 200
    assert stock(client, 1, 1) == 95.0
    assert points(client) == 65
    client.put(f'/api/pedidos/{pedido_id}/detalles/1', json={'cantidad': 1})
    assert stock(client, 1, 1) == 99.0
    assert points(client) == 25
    assert client.put(f'/api/pedidos/{pedido_id}/detalles/1', json={'cantidad': 0}).status_code == 400
    assert client.put(f'/api/pedidos/{pedido_id}/detalles/1', json={'cantidad': 500}).status_code == 409
    assert stock(client, 1, 1) == 99.0

    # delete a line
    assert client.delete(f'/api/pedidos/{pedido_id}/detalles/2').status_code == 200
    assert stock(client, 1, 2) == 5.0
    assert points(client) == 10
    assert client.get(f'/api/pedidos/{pedido_id}/detalles/2').status_code == 404
    # the last line can't be removed; the order has to be cancelled instead
    assert client.delete(f'/api/pedidos/{pedido_id}/detalles/1').status_code == 409


def test_detalles_not_found(client):
    assert client.get('/api/pedidos/99/detalles').status_code == 404
    pedido_id = order(client, 1).get_json()['pedido_id']
    assert client.get(f'/api/pedidos/{pedido_id}/detalles/2').status_code == 404
    assert client.put(f'/api/pedidos/{pedido_id}/detalles/2', json={'cantidad': 1}).status_code == 404
    assert client.post(f'/api/pedidos/{pedido_id}/detalles', json={'producto_id': 99, 'cantidad': 1}).status_code == 404


def test_cancel_pedido_with_several_lines(client):
    pedido_id = order(client, lines=[(1, 2.5), (2, 1.25)]).get_json()['pedido_id']
    assert client.delete(f'/api/pedidos/{pedido_id}').status_code == 200
    assert stock(client, 1, 1) == 100.0
    assert stock(client, 1, 2) == 5.0
    assert points(client) == 0


def test_update_pedido_date(client):
    pedido_id = order(client, 1).get_json()['pedido_id']
    res = client.put(f'/api/pedidos/{pedido_id}', json={'fecha_exacta': '2026-11-02T08:30:00'})
    assert res.status_code == 200
    assert res.get_json()['fecha_exacta'] == '2026-11-02T08:30:00'
    assert client.put(f'/api/pedidos/{pedido_id}', json={'tienda_id': 2}).status_code == 400
    assert client.put(f'/api/pedidos/{pedido_id}', json={'fecha_exacta': 'soon'}).status_code == 400


def test_delete_producto_with_orders_is_blocked(client):
    client.post('/api/productos', json={'nombre': 'Granola', 'unidad_medida': 'kg', 'precio_unitario': 7.4})
    client.post('/api/inventario', json={'tienda_id': 1, 'producto_id': 3, 'cantidad_stock': 10})
    order(client, 1, producto_id=3)
    client.delete('/api/inventario/1/3')
    assert client.delete('/api/productos/3').status_code == 409


def test_filter_pedidos(client):
    order(client, 1)
    order(client, 1, cliente_id=2, tienda_id=2)
    assert [p['cliente_id'] for p in client.get('/api/pedidos?cliente_id=2').get_json()] == [2]
    assert [p['tienda_id'] for p in client.get('/api/pedidos?tienda_id=1').get_json()] == [1]


# ----------------------------------------------------------------- reports

def test_report_store_sales(client):
    order(client, lines=[(1, 2.5), (2, 1)], fecha_exacta='2026-11-10T10:00:00')  # 7.00 + 3.20
    order(client, 1, fecha_exacta='2026-11-12T10:00:00')                         # 2.80
    order(client, 5, cliente_id=2, tienda_id=2, fecha_exacta='2026-11-12T11:00:00')  # 14.00
    rows = client.get('/api/reportes/ventas-por-tienda').get_json()
    assert rows == [
        {'tienda_id': 2, 'nombre_sucursal': 'Sucursal Norte', 'pedidos': 1, 'ingresos': 14.0, 'ticket_promedio': 14.0},
        {'tienda_id': 1, 'nombre_sucursal': 'Sucursal Centro', 'pedidos': 2, 'ingresos': 13.0, 'ticket_promedio': 6.5},
    ]
    rows = client.get('/api/reportes/ventas-por-tienda?desde=2026-11-11&hasta=2026-11-12').get_json()
    assert [(r['tienda_id'], r['pedidos'], r['ingresos']) for r in rows] == [(2, 1, 14.0), (1, 1, 2.8)]
    assert client.get('/api/reportes/ventas-por-tienda?desde=ayer').status_code == 400


def test_report_top_products_and_customers(client):
    order(client, lines=[(1, 2.5), (2, 1)])
    order(client, 5, cliente_id=2, tienda_id=2)
    products = client.get('/api/reportes/productos-mas-vendidos').get_json()
    assert [(p['producto_id'], p['cantidad_vendida'], p['ingresos'], p['pedidos']) for p in products] == [
        (1, 7.5, 21.0, 2), (2, 1.0, 3.2, 1)]
    assert len(client.get('/api/reportes/productos-mas-vendidos?limite=1').get_json()) == 1
    assert client.get('/api/reportes/productos-mas-vendidos?limite=0').status_code == 400

    customers = client.get('/api/reportes/top-clientes').get_json()
    assert [(c['cliente_id'], c['pedidos'], c['total_gastado'], c['puntos_ecologicos']) for c in customers] == [
        (2, 1, 14.0, 50), (1, 1, 10.2, 35)]


def test_report_daily_sales(client):
    order(client, 1)
    order(client, 2)
    rows = client.get('/api/reportes/ventas-diarias?dias=7').get_json()
    assert len(rows) == 7
    assert rows[-1]['pedidos'] == 2
    assert rows[-1]['ingresos'] == 8.4
    assert all(r['pedidos'] == 0 for r in rows[:-1])
    assert client.get('/api/reportes/ventas-diarias?dias=0').status_code == 400


def test_api_docs(client):
    spec = client.get('/api/openapi.json').get_json()
    assert spec['openapi'].startswith('3.')
    assert '/pedidos/{pedido_id}/detalles/{producto_id}' in spec['paths']
    res = client.get('/api/docs')
    assert res.status_code == 200
    assert b'swagger-ui' in res.data


def test_order_total_and_reports_round_the_same_way(client):
    """Each line is rounded to cents (half up) and the reports add the same rounded lines."""
    client.put('/api/productos/1', json={'precio_unitario': 1.5})
    client.put('/api/productos/2', json={'precio_unitario': 1.5})
    data = order(client, lines=[(1, 0.01), (2, 0.01)]).get_json()
    assert [d['subtotal'] for d in data['detalles']] == [0.02, 0.02]
    assert data['total'] == 0.04
    assert client.get('/api/resumen').get_json()['ingresos'] == 0.04
    assert client.get('/api/reportes/ventas-por-tienda').get_json()[0]['ingresos'] == 0.04


def test_order_quantity_limits(client):
    assert order(client, 10001).status_code == 400
    client.put('/api/clientes/1', json={'puntos_ecologicos': 2147483600})
    res = order(client, 10)
    assert res.status_code == 409
    assert stock(client) == 100.0


def test_report_daily_sales_range(client):
    order(client, 1, fecha_exacta='2026-11-10T10:00:00')
    order(client, 2, fecha_exacta='2026-11-12T23:30:00')
    order(client, 3, fecha_exacta='2026-11-13T00:10:00')
    rows = client.get('/api/reportes/ventas-diarias?desde=2026-11-10&hasta=2026-11-12').get_json()
    assert [(r['fecha'], r['pedidos'], r['ingresos']) for r in rows] == [
        ('2026-11-10', 1, 2.8), ('2026-11-11', 0, 0.0), ('2026-11-12', 1, 5.6)]
    assert client.get('/api/reportes/ventas-diarias?desde=2026-11-12&hasta=2026-11-10').status_code == 400
    assert client.get('/api/reportes/ventas-diarias?desde=2020-01-01&hasta=2026-01-01').status_code == 400


def test_create_producto_requires_price(client):
    res = client.post('/api/productos', json={'nombre': 'Granola', 'unidad_medida': 'kg'})
    assert res.status_code == 400
    assert 'precio_unitario' in res.get_json()['error']
