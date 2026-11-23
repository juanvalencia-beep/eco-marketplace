# Eco-Marketplace

Simplified Management System for Eco-Marketplace and Local Refill Stations.

Databases course project. Team: Jonatan Vazques, Juan Valencia, David Guanoluisa.

The system manages a small network of stores that sell eco-friendly products in bulk (detergent, oats, rice, shampoo...). It keeps the product catalog with prices, the stock of each product in each store, the registered customers with their eco-points, and the refill orders with their order lines. It also generates sales reports.

Online demo: https://ecomarketplace.vercel.app
API docs (Swagger): https://ecomarketplace.vercel.app/api/docs
Presentation: https://ecomarketplace.vercel.app/presentation

The online version uses SQLite in the temporary folder of Vercel and loads the sample data when it starts, so the changes made there are not permanent.

## Project report

Final report (PDF): [docs/report/project_report.pdf](docs/report/project_report.pdf) (LaTeX source: `docs/report/project_report.tex`). The project advance report is in `docs/report/project_advance.pdf`.

Demo guide in Spanish for Visual Studio Code (how to run it and what to show for each evaluation criterion): [GUIA_DEMO.md](GUIA_DEMO.md).

## Structure

```
database/        SQL scripts to create the schema (SQLite and MySQL)
models.py        the 6 tables as SQLAlchemy models
routes.py        the API routes (/api/...), including the reports
openapi.py       OpenAPI 3 spec, shown with Swagger UI at /api/docs
app.py           Flask app, it also serves the GUI and the presentation
seed.py          creates the tables and loads sample data
static/          the GUI (HTML, CSS and JavaScript)
static/presentation/  the project presentation (served at /presentation)
tests/           test cases (database and API)
docs/API.md      list of all the endpoints
docs/report/     LaTeX source of the project advance report
index.py         entry point for Vercel
vercel.json      Vercel configuration
```

## Database

Six tables: `cliente`, `tienda`, `producto`, `inventario`, `pedido` and `detalle_pedido`.

- `inventario` resolves the many-to-many relation between stores and products (composite key `tienda_id, producto_id`).
- An order is split in a header and its lines: `pedido` keeps who bought, in which store and when, and `detalle_pedido` has one row per product with the quantity bought (`cantidad_comprada`) and the unit price at the moment of the purchase (composite key `pedido_id, producto_id`). Copying the price keeps old orders correct when a product price changes later. Every foreign key is `ON DELETE RESTRICT`, as in the design document: to cancel an order the API deletes its lines and then the header in the same transaction, and a product that appears in an order can't be deleted.

The schema follows the team's Database Design Specification (3NF, naming rules of its Annex B). `precio_unitario` (in `producto` and `detalle_pedido`) is an extension added for the totals and sales reports. All the constraints have names (`pk_`, `fk_`, `uq_`, `ck_`, `idx_`).

```mermaid
erDiagram
    CLIENTE ||--o{ PEDIDO : places
    TIENDA ||--o{ PEDIDO : receives
    PEDIDO ||--|{ DETALLE_PEDIDO : contains
    PRODUCTO ||--o{ DETALLE_PEDIDO : "appears in"
    TIENDA ||--o{ INVENTARIO : stocks
    PRODUCTO ||--o{ INVENTARIO : "stocked as"

    CLIENTE {
        int cliente_id PK
        varchar nombre_completo
        varchar correo_electronico UK
        int puntos_ecologicos "CHECK >= 0"
    }
    TIENDA {
        int tienda_id PK
        varchar nombre_sucursal
        varchar direccion
    }
    PRODUCTO {
        int producto_id PK
        varchar nombre
        varchar unidad_medida
        decimal precio_unitario "CHECK >= 0"
    }
    INVENTARIO {
        int tienda_id PK,FK
        int producto_id PK,FK
        decimal cantidad_stock "CHECK >= 0"
    }
    PEDIDO {
        int pedido_id PK
        datetime fecha_exacta
        int cliente_id FK
        int tienda_id FK
    }
    DETALLE_PEDIDO {
        int pedido_id PK,FK
        int producto_id PK,FK
        decimal cantidad_comprada "CHECK > 0"
        decimal precio_unitario "CHECK >= 0"
    }
```

SQLite is the default engine. The same schema for MySQL is in `database/schema_mysql.sql`.

If you already had an `eco_marketplace.db` from the project advance, run `python seed.py` again: it drops and creates the tables with the new design.

## How to run it

```
pip install -r requirements.txt
python seed.py
python app.py
```

Then open http://127.0.0.1:5000 in the browser. The API is at http://127.0.0.1:5000/api, its Swagger documentation at http://127.0.0.1:5000/api/docs and the presentation at http://127.0.0.1:5000/presentation.

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

`tests/test_database.py` has the 15 test cases of the Database Design Specification (TC-01 to TC-15, including the ones for `detalle_pedido`), run directly on the SQL schema, plus two extra checks (order total and `ON DELETE RESTRICT`). `tests/test_api.py` tests every CRUD operation of the API, the order lines, the transactions (a failing line rolls back the whole order) and the reports.

## Endpoints

| Resource | Routes |
|----------|--------|
| Customers | `GET/POST /api/clientes`, `GET/PUT/DELETE /api/clientes/<id>`, `GET /api/clientes/<id>/pedidos` |
| Stores | `GET/POST /api/tiendas`, `GET/PUT/DELETE /api/tiendas/<id>` |
| Products | `GET/POST /api/productos`, `GET/PUT/DELETE /api/productos/<id>` |
| Inventory | `GET/POST /api/inventario`, `GET/PUT/DELETE /api/inventario/<tienda_id>/<producto_id>`, `GET /api/inventario/stock-bajo` |
| Orders | `GET/POST /api/pedidos`, `GET/PUT/DELETE /api/pedidos/<id>` |
| Order lines | `GET/POST /api/pedidos/<id>/detalles`, `GET/PUT/DELETE /api/pedidos/<id>/detalles/<producto_id>` |
| Reports | `GET /api/reportes/ventas-por-tienda`, `/productos-mas-vendidos`, `/top-clientes`, `/ventas-diarias`, `GET /api/resumen` |
| Docs | `GET /api/docs` (Swagger UI), `GET /api/openapi.json` |

More detail in `docs/API.md` and in Swagger at `/api/docs`.
