# Guía para la demostración (VS Code)

Guía paso a paso para mostrar el proyecto al profesor desde Visual Studio Code.
Ábrala con **Ctrl+Shift+V** (vista previa): los enlaces llevan directo al archivo y a la línea.

**En una frase:** Eco-Marketplace es un sistema para administrar estaciones de recarga en Quito.
El cliente trae su propio envase y compra productos a granel (detergente, avena, arroz...), y el
sistema lleva el inventario de cada tienda, los pedidos con su detalle, los eco-puntos del cliente
y los reportes de ventas.

---

## 0. Antes de empezar (una sola vez)

1. **Archivo > Abrir carpeta...** y elija la carpeta `eco_marketplace`.
2. VS Code sugerirá instalar las extensiones recomendadas (Python, Python Debugger y SQLite Viewer). Acepte.
3. **Terminal > Ejecutar tarea... > Instalar dependencias**.
4. Panel **Ejecutar y depurar** (Ctrl+Shift+D), elija **1. Cargar datos de ejemplo** y presione **F5**.
   Crea `eco_marketplace.db` con 3 tiendas, 8 productos, 8 clientes y 28 pedidos con 57 líneas.
5. En el mismo panel elija **2. Ejecutar la app** y presione **F5**. El navegador se abre solo en http://127.0.0.1:5000.

| Dirección | Qué es |
|-----------|--------|
| http://127.0.0.1:5000 | La aplicación (GUI) |
| http://127.0.0.1:5000/presentation | La presentación (flechas para avanzar, **F** para pantalla completa) |
| http://127.0.0.1:5000/api/docs | Documentación de la API en Swagger |
| https://ecomarketplace.vercel.app | La misma app publicada en internet |

---

## 1. Diseño de la base de datos  *(criterio: Database Design)*

- Diagrama ER: [docs/report/img/er_diagram_final.png](docs/report/img/er_diagram_final.png)
  (también en el [README](README.md), dibujado con Mermaid).
- **6 tablas en 3FN:** `cliente`, `tienda`, `producto`, `inventario`, `pedido` y `detalle_pedido`.
- **Lo que pidió el profesor en el avance, "Detalle de Pedido":**
  - Antes, `pedido` tenía un solo producto.
  - Ahora [`pedido`](database/schema_sqlite.sql#L53) es solo la cabecera: quién compra, en qué tienda y cuándo.
  - [`detalle_pedido`](database/schema_sqlite.sql#L69) tiene una línea por producto.
  - Clave primaria compuesta `(pedido_id, producto_id)`: el mismo producto no se repite en un pedido.
  - `precio_unitario` se copia al comprar: si el precio cambia después, los pedidos viejos no cambian. Esta columna (en `producto` y en `detalle_pedido`) es una extensión sobre el documento de diseño, agregada para calcular totales y reportes de ventas.
  - La cantidad se guarda en `cantidad_comprada`, con el CHECK `ck_detalle_pedido_cantidad_comprada_positiva`.
  - Todas las llaves foráneas son `ON DELETE RESTRICT`, como pide el documento de diseño. No se puede borrar un producto que ya se vendió. Para anular un pedido, la API borra primero sus líneas y después la cabecera, en la misma transacción.
- [`inventario`](database/schema_sqlite.sql#L40) resuelve la relación N:M entre tiendas y productos.

## 2. Implementación de la base de datos  *(criterio: Database Implementation)*

- Script SQLite: [database/schema_sqlite.sql](database/schema_sqlite.sql). Script MySQL: [database/schema_mysql.sql](database/schema_mysql.sql).
- Todas las restricciones tienen nombre: `pk_`, `fk_`, `uq_`, `ck_` e `idx_` (por ejemplo [los índices](database/schema_sqlite.sql#L83)).
- Los mismos modelos en SQLAlchemy:
  - [`Pedido`](models.py#L112)
  - [`DetallePedido`](models.py#L163)
- **Ver los datos:** haga clic en `eco_marketplace.db` en el explorador (necesita SQLite Viewer). Se abren las tablas con sus filas.
- Detalle técnico: SQLite ignora las llaves foráneas si no se activan en cada conexión. Ver [app.py](app.py#L21).

## 3. Diseño de la API  *(criterio: API Design and Functionality)*

- Abra http://127.0.0.1:5000/api/docs (Swagger). Están todas las rutas, agrupadas por tabla, con sus JSON de ejemplo.
- Para probar en vivo: **POST /pedidos > Try it out > Execute**. Se crea un pedido con 2 productos.
- Respuestas: 200, 201, 400 (dato inválido), 404 (no existe) y 409 (conflicto: sin stock, correo duplicado o borrado bloqueado). Los errores siempre llegan como `{"error": "mensaje"}`.
- Lista completa de rutas: [docs/API.md](docs/API.md). La especificación OpenAPI está en [openapi.py](openapi.py).

## 4. Implementación de la API y CRUD  *(criterio: API Implementation and CRUD Operations)*

Todo está en [routes.py](routes.py). Los puntos importantes:

| Qué mostrar | Dónde |
|-------------|-------|
| CRUD de clientes (crear, listar, editar, borrar) | [create_cliente](routes.py#L105), [list_clientes](routes.py#L88), [update_cliente](routes.py#L118), [delete_cliente](routes.py#L135) |
| Registrar un pedido con varios productos **en una sola transacción** | [create_pedido](routes.py#L396) |
| Descontar stock sin que dos ventas a la vez se pisen (`stock = stock - x` en SQL) | [take_stock](routes.py#L324), [línea clave](routes.py#L338) |
| CRUD del detalle del pedido (agregar, cambiar y quitar líneas) | [create_detalle](routes.py#L481), [update_detalle](routes.py#L500), [delete_detalle](routes.py#L522) |
| Anular un pedido: devuelve el stock y quita los puntos | [cancel_pedido](routes.py#L450) |
| Reportes con SQL (JOIN, GROUP BY, SUM) | [ventas por tienda](routes.py#L570), [ventas diarias](routes.py#L624), [regla de redondeo](routes.py#L543) |

## 5. Pruebas  *(test cases)*

- Abra el panel **Pruebas**, con el ícono del matraz en la barra izquierda, y presione **▶ Ejecutar pruebas**. Las **71** quedan en verde.
- Otra opción: en **Ejecutar y depurar**, elija **3. Ejecutar todas las pruebas** y presione F5.
- Los 15 casos de prueba del documento de diseño (*Database Design Specification*) están en [tests/test_database.py](tests/test_database.py), con los mismos pasos y resultados esperados:
  - TC-01 a TC-15. Por ejemplo, [TC-03: 50 transacciones concurrentes](tests/test_database.py#L57) y [TC-10: rollback sin stock](tests/test_database.py#L204).
  - Nuevos de detalle de pedido: [TC-05 con dos productos](tests/test_database.py#L114) y [TC-14 y TC-15](tests/test_database.py#L295).
- Pruebas de la API en [tests/test_api.py](tests/test_api.py), por ejemplo:
  - [si una línea no tiene stock, no se guarda nada](tests/test_api.py#L322)
  - [CRUD del detalle](tests/test_api.py#L346)
  - [reportes](tests/test_api.py#L426)

## 6. GUI: diseño y experiencia de uso  *(criteria: GUI Design / GUI Functionality)*

Demo sugerida en http://127.0.0.1:5000, unos 5 minutos:

1. **Panel:** ingresos, pedidos, eco-puntos, gráfico de ventas por día y alertas de stock bajo.
2. **Pedidos > Nuevo pedido:**
   1. Elija cliente y tienda.
   2. Agregue 2 o 3 productos. Se ven el stock disponible, el subtotal, el total y los eco-puntos que va a ganar.
   3. Registre el pedido.
3. En la tabla de pedidos, botón **Ver**:
   1. Cambie la cantidad de una línea y quite otra (el stock se ajusta solo).
   2. Al final, anule el pedido.
4. **Clientes:**
   1. Cree un cliente con un correo que ya existe. Aparece el error 409 de la API, en español.
   2. Vea el historial de un cliente.
5. **Inventario:** edite un stock y vea cómo se marca el stock bajo.
6. **Reportes:** filtre por fechas, **Exportar CSV** e **Imprimir**.
7. Reduzca la ventana: la interfaz se adapta a celular.

Código de la GUI:
- Página principal: [static/index.html](static/index.html).
- Lógica por sección:
  - [orders.js](static/js/orders.js): pedidos y detalle
  - [reports.js](static/js/reports.js): reportes
  - [catalog.js](static/js/catalog.js): clientes, tiendas, productos e inventario
  - [dashboard.js](static/js/dashboard.js): panel
- Conexión con la API: [api.js](static/js/api.js), que usa `fetch` contra `/api/...`.

## 7. Repositorio, documentación e informe  *(criterio: Repository, Documentation and Project Report)*

- GitHub: https://github.com/juanvalencia-beep/eco-marketplace
- [README.md](README.md): cómo instalar y ejecutar, la estructura del proyecto y el diagrama ER.
- Informe final en PDF: [docs/report/project_report.pdf](docs/report/project_report.pdf).
  Incluye diseño, implementación, pruebas, retos y mejoras futuras.
- Despliegue en Vercel: [vercel.json](vercel.json) e [index.py](index.py).

---

### Si algo falla durante la demo

| Problema | Solución |
|----------|----------|
| "No module named flask" | **Terminal > Ejecutar tarea... > Instalar dependencias** |
| La app muestra datos viejos o error de columnas | Ejecute **1. Cargar datos de ejemplo** otra vez. Recrea la base con el diseño nuevo |
| "Address already in use" (puerto 5000 ocupado) | Detenga la ejecución anterior con el botón rojo ■ o con Shift+F5 |
| No hay internet | La app funciona igual en local. Swagger, las tipografías y las animaciones de la presentación se cargan de internet (sin conexión la presentación igual avanza, pero sin animaciones) |
