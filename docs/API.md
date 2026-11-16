# API (APIDB) - Eco-Marketplace

Base URL: `http://127.0.0.1:5000/api`

All requests and responses use JSON. Errors always come as `{"error": "message"}`.

| Code | When |
|------|------|
| 200 | OK |
| 201 | Created |
| 400 | Missing field, wrong type, or invalid value (for example quantity <= 0) |
| 404 | The record (or a referenced record) does not exist |
| 409 | Conflict with a constraint: duplicate email, duplicate inventory row, not enough stock, or delete blocked by `ON DELETE RESTRICT` |

Decimals (`cantidad_stock`, `cantidad_comprada`) are returned as numbers with 2 decimals.
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
| POST | `/productos` | `nombre`, `unidad_medida` |
| PUT | `/productos/<id>` | any of `nombre`, `unidad_medida` |
| DELETE | `/productos/<id>` | - (409 if it has inventory or orders) |

```json
{"producto_id": 1, "nombre": "Detergente líquido", "unidad_medida": "liters"}
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

| Method | Route | Body | Notes |
|--------|-------|------|-------|
| GET | `/pedidos` | - | Newest first |
| GET | `/pedidos/<id>` | - | |
| POST | `/pedidos` | `cliente_id`, `tienda_id`, `producto_id`, `cantidad_comprada`, optional `fecha_exacta` | One transaction: checks the stock, saves the order, subtracts the stock (FR-05) and adds eco-points |
| DELETE | `/pedidos/<id>` | - | Cancels the order: gives the stock back and removes the points |

Orders are not updated with PUT, because changing an order after the stock was moved would break the inventory history. To fix an order it is cancelled and created again.

Eco-points rule: the customer earns 10 points for each unit bought, rounded down (`int(cantidad_comprada * 10)`). 2.50 liters = 25 points.

POST errors: 404 if the customer, store or product does not exist; 409 if the store has no inventory row for that product or the stock is not enough; 400 if `cantidad_comprada <= 0`.

```json
{"pedido_id": 1, "fecha_exacta": "2026-11-16T10:30:00", "cantidad_comprada": 2.5,
 "cliente_id": 1, "tienda_id": 1, "producto_id": 1,
 "nombre_completo": "Ana Pérez", "nombre_sucursal": "Sucursal Centro",
 "nombre_producto": "Detergente líquido", "unidad_medida": "liters", "puntos_ganados": 25}
```

## Other

| Method | Route | Notes |
|--------|-------|-------|
| GET | `/resumen` | Counts for the dashboard: `clientes`, `tiendas`, `productos`, `pedidos`, `stock_bajo` |
