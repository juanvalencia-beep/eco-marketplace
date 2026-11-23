-- Eco-Marketplace - schema for SQLite
-- Run with: sqlite3 eco_marketplace.db < database/schema_sqlite.sql
-- Remember: SQLite needs PRAGMA foreign_keys = ON in every connection.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS detalle_pedido;
DROP TABLE IF EXISTS pedido;
DROP TABLE IF EXISTS inventario;
DROP TABLE IF EXISTS producto;
DROP TABLE IF EXISTS tienda;
DROP TABLE IF EXISTS cliente;

CREATE TABLE cliente (
    cliente_id          INTEGER      NOT NULL,
    nombre_completo     VARCHAR(100) NOT NULL,
    correo_electronico  VARCHAR(120) NOT NULL,
    puntos_ecologicos   INTEGER      NOT NULL DEFAULT 0,
    CONSTRAINT pk_cliente PRIMARY KEY (cliente_id AUTOINCREMENT),
    CONSTRAINT uq_cliente_correo_electronico UNIQUE (correo_electronico),
    CONSTRAINT ck_cliente_puntos_ecologicos_no_negativo CHECK (puntos_ecologicos >= 0)
);

CREATE TABLE tienda (
    tienda_id        INTEGER      NOT NULL,
    nombre_sucursal  VARCHAR(100) NOT NULL,
    direccion        VARCHAR(200) NOT NULL,
    CONSTRAINT pk_tienda PRIMARY KEY (tienda_id AUTOINCREMENT)
);

CREATE TABLE producto (
    producto_id      INTEGER       NOT NULL,
    nombre           VARCHAR(100)  NOT NULL,
    unidad_medida    VARCHAR(20)   NOT NULL,
    precio_unitario  DECIMAL(10,2) NOT NULL DEFAULT 0,
    CONSTRAINT pk_producto PRIMARY KEY (producto_id AUTOINCREMENT),
    CONSTRAINT ck_producto_precio_unitario_no_negativo CHECK (precio_unitario >= 0)
);

CREATE TABLE inventario (
    tienda_id       INTEGER        NOT NULL,
    producto_id     INTEGER        NOT NULL,
    cantidad_stock  DECIMAL(10,2)  NOT NULL,
    CONSTRAINT pk_inventario PRIMARY KEY (tienda_id, producto_id),
    CONSTRAINT fk_inventario_tienda FOREIGN KEY (tienda_id)
        REFERENCES tienda (tienda_id) ON DELETE RESTRICT,
    CONSTRAINT fk_inventario_producto FOREIGN KEY (producto_id)
        REFERENCES producto (producto_id) ON DELETE RESTRICT,
    CONSTRAINT ck_inventario_cantidad_stock_no_negativa CHECK (cantidad_stock >= 0)
);

-- Order header: who bought, in which store and when.
CREATE TABLE pedido (
    pedido_id     INTEGER        NOT NULL,
    fecha_exacta  DATETIME       NOT NULL,
    cliente_id    INTEGER        NOT NULL,
    tienda_id     INTEGER        NOT NULL,
    CONSTRAINT pk_pedido PRIMARY KEY (pedido_id AUTOINCREMENT),
    CONSTRAINT fk_pedido_cliente FOREIGN KEY (cliente_id)
        REFERENCES cliente (cliente_id) ON DELETE RESTRICT,
    CONSTRAINT fk_pedido_tienda FOREIGN KEY (tienda_id)
        REFERENCES tienda (tienda_id) ON DELETE RESTRICT
);

-- Order lines (detalle de pedido): one row per product of an order.
-- precio_unitario is copied from producto when the order is made, so a later
-- price change does not rewrite old orders. Deleting an order deletes its lines.
CREATE TABLE detalle_pedido (
    pedido_id        INTEGER        NOT NULL,
    producto_id      INTEGER        NOT NULL,
    cantidad         DECIMAL(10,2)  NOT NULL,
    precio_unitario  DECIMAL(10,2)  NOT NULL,
    CONSTRAINT pk_detalle_pedido PRIMARY KEY (pedido_id, producto_id),
    CONSTRAINT fk_detalle_pedido_pedido FOREIGN KEY (pedido_id)
        REFERENCES pedido (pedido_id) ON DELETE CASCADE,
    CONSTRAINT fk_detalle_pedido_producto FOREIGN KEY (producto_id)
        REFERENCES producto (producto_id) ON DELETE RESTRICT,
    CONSTRAINT ck_detalle_pedido_cantidad_positiva CHECK (cantidad > 0),
    CONSTRAINT ck_detalle_pedido_precio_unitario_no_negativo CHECK (precio_unitario >= 0)
);

CREATE INDEX idx_pedido_cliente_id          ON pedido (cliente_id);
CREATE INDEX idx_pedido_tienda_id           ON pedido (tienda_id);
CREATE INDEX idx_pedido_fecha_exacta        ON pedido (fecha_exacta);
CREATE INDEX idx_detalle_pedido_producto_id ON detalle_pedido (producto_id);
