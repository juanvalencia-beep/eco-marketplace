# Eco-Marketplace

Simplified Management System for Eco-Marketplace and Local Refill Stations.

Databases course project. Team: Jonatan Vazques, Juan Valencia, David Guanoluisa.

The system manages a small network of stores that sell eco-friendly products in bulk (detergent, oats, rice, shampoo...). It keeps the product catalog, the stock of each product in each store, the registered customers with their eco-points, and the refill orders.

## Structure

```
database/        SQL scripts to create the schema (SQLite and MySQL)
models.py        the 5 tables as SQLAlchemy models
routes.py        the API routes (/api/...)
app.py           Flask app, it also serves the GUI
seed.py          creates the tables and loads sample data
static/          the GUI (HTML, CSS and JavaScript)
tests/           test cases (database and API)
docs/API.md      list of all the endpoints
docs/report/     LaTeX source of the project advance report
```

## Database

Five tables: `cliente`, `tienda`, `producto`, `inventario` and `pedido`. `inventario` resolves the many-to-many relation between stores and products, and `pedido` links a customer, a store and a product. The schema is in 3NF and all the constraints have the names defined in the design document (`pk_`, `fk_`, `uq_`, `ck_`, `idx_`).

SQLite is the default engine. The same schema for MySQL is in `database/schema_mysql.sql`.

## How to run it

```
pip install -r requirements.txt
python seed.py
python app.py
```

Then open http://127.0.0.1:5000 in the browser. The API is at http://127.0.0.1:5000/api.

To use MySQL instead of SQLite (for example with the Docker container of the labs):

```
docker start mysqlcontainer
docker exec -i mysqlcontainer mysql -uroot -p123456 < database/schema_mysql.sql
set DATABASE_URL=mysql+pymysql://root:123456@127.0.0.1:3306/eco_marketplace
python seed.py
python app.py
```

## Tests

```
python -m pytest -v
```

`tests/test_database.py` has the 13 test cases of the design document (TC-01 to TC-13), run directly on the SQL schema. `tests/test_api.py` tests the CRUD operations of the API.

## Endpoints

| Resource | Routes |
|----------|--------|
| Customers | `GET/POST /api/clientes`, `GET/PUT/DELETE /api/clientes/<id>`, `GET /api/clientes/<id>/pedidos` |
| Stores | `GET/POST /api/tiendas`, `GET/PUT/DELETE /api/tiendas/<id>` |
| Products | `GET/POST /api/productos`, `GET/PUT/DELETE /api/productos/<id>` |
| Inventory | `GET/POST /api/inventario`, `GET/PUT/DELETE /api/inventario/<tienda_id>/<producto_id>`, `GET /api/inventario/stock-bajo` |
| Orders | `GET/POST /api/pedidos`, `GET/DELETE /api/pedidos/<id>` |
| Dashboard | `GET /api/resumen` |

More detail in `docs/API.md`.
