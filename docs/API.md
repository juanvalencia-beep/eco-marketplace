# API (APIDB) - Eco-Marketplace

Base URL: `http://127.0.0.1:5000/api`

Interactive documentation (Swagger UI): `http://127.0.0.1:5000/api/docs`. The OpenAPI 3 spec is at `/api/openapi.json` and can be imported into Postman.

All requests and responses use JSON. Errors always come as `{"error": "message"}`.

| Code | When |
|------|------|
| 200 | OK |
| 201 | Created |
| 400 | Missing field, wrong type, or invalid value (for example quantity <= 0) |
| 404 | The record (or a referenced record) does not exist |
| 409 | Conflict with a constraint: duplicate email, duplicate inventory row, not enough stock, or delete blocked by `ON DELETE RESTRICT` |

Decimals (`cantidad_stock`, `cantidad`, `precio_unitario`, `subtotal`, `total`) are returned as numbers with 2 decimals.
Dates (`fecha_exacta`) are returned as `YYYY-MM-DDTHH:MM:SS`.

## Clientes (customers)

| Method | Route | Body | Notes |
|--------|-------|------|-------|
| GET | `/clientes` | - | List all, ordered by id. Optional `?q=text` filters by name or email |
| GET | `/clientes/<id>` | - | One customer |
| POST | `/clientes` | `nombre_completo`, `correo_electronico` | `puntos_ecologicos` starts at 0 (FR-01) |
| PUT | `/clientes/<id>` | any of `nombre_completo`, `correo_electronico`, `puntos_ecologicos` | |
| DELETE | `/clientes/<id>` | - | 409 if the customer has orders |
| GET | `/clientes/<id>/pedidos` | - | Order history, newest first (FR-04) |

Customer object:
```json
{"cliente_id": 1, "nombre_completo": "Ana Pérez", "correo_electronico": "ana.perez@example.com", "puntos_ecologicos": 0}
```

## Tiendas (stores)

| Method | Route | Body |
|--------|-------|------|
| GET | `/tiendas` | - |
| GET | `/tiendas/<id>` | - |
| POST | `/tiendas` | `nombre_sucursal`, `direccion` |
| PUT | `/tiendas/<id>` | any of `nombre_sucursal`, `direccion` |
| DELETE | `/tiendas/<id>` | - (409 if it has inventory or orders) |

```json
{"tienda_id": 1, "nombre_sucursal": "Sucursal Centro", "direccion": "Av. Amazonas N24-03"}
```

## Productos (products)

| Method | Route | Body |
|--------|-------|------|
| GET | `/productos` | - |
| GET | `/productos/<id>` | - |
| POST | `/productos` | `nombre`, `unidad_medida`, `precio_unitario` |
| PUT | `/productos/<id>` | any of `nombre`, `unidad_medida`, `precio_unitario` |
| DELETE | `/productos/<id>` | - (409 if it has inventory or appears in an order line) |

```json
{"producto_id": 1, "nombre": "Detergente líquido", "unidad_medida": "liters", "precio_unitario": 2.8}
```

## Inventario (stock per store)

| Method | Route | Body | Notes |
|--------|-------|------|-------|
| GET | `/inventario` | - | Optional `?tienda_id=` filter |
| GET | `/inventario/<tienda_id>/<producto_id>` | - | |
| POST | `/inventario` | `tienda_id`, `producto_id`, `cantidad_stock` | 409 if the pair already exists (TC-04) |
| PUT | `/inventario/<tienda_id>/<producto_id>` | `cantidad_stock` | 400 if negative |
| DELETE | `/inventario/<tienda_id>/<producto_id>` | - | |
| GET | `/inventario/stock-bajo` | - | Low stock report (FR-06). `?limite=10.00` by default, returns rows with `cantidad_stock < limite` |

```json
{"tienda_id": 1, "producto_id": 1, "cantidad_stock": 100.0,
 "nombre_sucursal": "Sucursal Centro", "nombre_producto": "Detergente líquido", "unidad_medida": "liters"}
```

## Pedidos (refill orders)

An order is split in two tables: `pedido` is the header (customer, store, date) and `detalle_pedido` has one line per product (quantity and the unit price at the moment of the purchase). The price always comes from the product in the database, never from the request.

| Method | Route | Body | Notes |
|--------|-------|------|-------|
| GET | `/pedidos` | - | Newest first, each order with its lines. Optional `?cliente_id=` and `?tienda_id=` |
| GET | `/pedidos/<id>` | - | |
| POST | `/pedidos` | `cliente_id`, `tienda_id`, `detalles: [{producto_id, cantidad}, ...]`, optional `fecha_exacta` | One transaction (FR-05): saves the header and every line, subtracts the stock of each line and adds the eco-points. If one line fails nothing is saved |
| PUT | `/pedidos/<id>` | `fecha_exacta` | Only the date can change. Customer and store can't (the stock already moved in that store) |
| DELETE | `/pedidos/<id>` | - | Cancels the order: gives back the stock of every line and removes the points. The lines are deleted by `ON DELETE CASCADE` |

Eco-points rule: the customer earns 10 points for each unit bought, rounded down per line (`int(cantidad * 10)`). 2.50 liters = 25 points.

POST errors: 400 if `detalles` is empty, has more than 50 lines, repeats a product, or a `cantidad` is not between 0.01 and 10000; 404 if the customer, store or a product does not exist; 409 if the store has no inventory row for a product or the stock is not enough.

Request:
```json
{"cliente_id": 1, "tienda_id": 1,
 "detalles": [{"producto_id": 1, "cantidad": 2.5}, {"producto_id": 2, "cantidad": 1.25}]}
```

Response (201):
```json
{"pedido_id": 29, "fecha_exacta": "2026-11-23T10:30:00", "cliente_id": 1, "tienda_id": 1,
 "nombre_completo": "Ana Pérez", "nombre_sucursal": "Sucursal Centro",
 "num_productos": 2, "cantidad_total": 3.75, "total": 11.0, "puntos_ganados": 37,
 "detalles": [
   {"pedido_id": 29, "producto_id": 1, "nombre_producto": "Detergente líquido", "unidad_medida": "liters",
    "cantidad": 2.5, "precio_unitario": 2.8, "subtotal": 7.0, "puntos": 25},
   {"pedido_id": 29, "producto_id": 2, "nombre_producto": "Avena", "unidad_medida": "kg",
    "cantidad": 1.25, "precio_unitario": 3.2, "subtotal": 4.0, "puntos": 12}]}
```

## Detalle de pedido (order lines)

| Method | Route | Body | Notes |
|--------|-------|------|-------|
| GET | `/pedidos/<id>/detalles` | - | Lines of the order |
| GET | `/pedidos/<id>/detalles/<producto_id>` | - | One line |
| POST | `/pedidos/<id>/detalles` | `producto_id`, `cantidad` | Adds a product: takes the stock and adds points. 409 if the product is already in the order (update that line instead) or there is not enough stock |
| PUT | `/pedidos/<id>/detalles/<producto_id>` | `cantidad` | Changes the quantity: a bigger quantity takes the difference from the stock, a smaller one gives it back. Points are adjusted |
| DELETE | `/pedidos/<id>/detalles/<producto_id>` | - | Removes the line and gives the stock back. 409 if it is the last line (cancel the order instead) |

## Reportes (reports)

`desde` and `hasta` (`YYYY-MM-DD`, both included) filter by the order date. `limite` is 5 by default (1 to 100).

| Method | Route | Returns |
|--------|-------|---------|
| GET | `/reportes/ventas-por-tienda?desde=&hasta=` | Per store: `pedidos`, `ingresos`, `ticket_promedio`. Stores without sales appear with 0 |
| GET | `/reportes/productos-mas-vendidos?limite=&desde=&hasta=` | Per product: `cantidad_vendida`, `ingresos`, `pedidos`, ordered by revenue |
| GET | `/reportes/top-clientes?limite=&desde=&hasta=` | Per customer: `pedidos`, `total_gastado`, `puntos_ecologicos` |
| GET | `/reportes/ventas-diarias?dias=30` or `?desde=&hasta=` | One row per day of the last `dias` days or of the range (up to 366 days): `fecha`, `pedidos`, `ingresos` (days without sales have 0) |
| GET | `/resumen` | Dashboard counters: `clientes`, `tiendas`, `productos`, `pedidos`, `stock_bajo`, `ingresos`, `puntos_ecologicos` |
| GET | `/inventario/stock-bajo?limite=10` | Low stock report (FR-06) |
