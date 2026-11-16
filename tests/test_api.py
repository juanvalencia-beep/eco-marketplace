def order(client, cantidad, cliente_id=1, tienda_id=1, producto_id=1, **extra):
    body = {'cliente_id': cliente_id, 'tienda_id': tienda_id, 'producto_id': producto_id,
            'cantidad_comprada': cantidad, **extra}
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
    res = client.post('/api/productos', json={'nombre': 'Shampoo sólido', 'unidad_medida': 'units'})
    assert res.status_code == 201
    producto_id = res.get_json()['producto_id']
    assert client.get(f'/api/productos/{producto_id}').get_json()['nombre'] == 'Shampoo sólido'

    res = client.put(f'/api/productos/{producto_id}', json={'unidad_medida': 'bars'})
    assert res.get_json()['unidad_medida'] == 'bars'

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
    assert data['cantidad_comprada'] == 2.5
    assert data['puntos_ganados'] == 25
    assert data['nombre_completo'] == 'Ana Pérez'
    assert data['nombre_producto'] == 'Detergente líquido'
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
    assert client.post('/api/pedidos', json={'cliente_id': 1}).status_code == 400
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
    assert [p['cantidad_comprada'] for p in history] == [2.0, 3.0, 1.0]
    assert all(p['cliente_id'] == 1 for p in history)
    assert client.get('/api/clientes/999/pedidos').status_code == 404


def test_resumen(client):
    order(client, 1)
    assert client.get('/api/resumen').get_json() == {
        'clientes': 2, 'tiendas': 2, 'productos': 2, 'pedidos': 1, 'stock_bajo': 1,
    }


def test_unknown_route_returns_json_error(client):
    res = client.get('/api/nothing-here')
    assert res.status_code == 404
    assert 'error' in res.get_json()
