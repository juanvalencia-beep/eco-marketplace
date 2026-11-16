-- Eco-Marketplace - schema for MySQL 8.0.16 or higher
-- (CHECK constraints are only enforced from 8.0.16)
-- Run with: mysql -u root -p < database/schema_mysql.sql

CREATE DATABASE IF NOT EXISTS eco_marketplace
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE eco_marketplace;

DROP TABLE IF EXISTS pedido;
DROP TABLE IF EXISTS inventario;
DROP TABLE IF EXISTS producto;
DROP TABLE IF EXISTS tienda;
DROP TABLE IF EXISTS cliente;

CREATE TABLE cliente (
    cliente_id          INT          NOT NULL AUTO_INCREMENT,
    nombre_completo     VARCHAR(100) NOT NULL,
    correo_electronico  VARCHAR(120) NOT NULL,
    puntos_ecologicos   INT          NOT NULL DEFAULT 0,
    CONSTRAINT pk_cliente PRIMARY KEY (cliente_id),
    CONSTRAINT uq_cliente_correo_electronico UNIQUE (correo_electronico),
    CONSTRAINT ck_cliente_puntos_ecologicos_no_negativo CHECK (puntos_ecologicos >= 0)
) ENGINE = InnoDB;

CREATE TABLE tienda (
    tienda_id        INT          NOT NULL AUTO_INCREMENT,
    nombre_sucursal  VARCHAR(100) NOT NULL,
    direccion        VARCHAR(200) NOT NULL,
    CONSTRAINT pk_tienda PRIMARY KEY (tienda_id)
) ENGINE = InnoDB;

CREATE TABLE producto (
    producto_id    INT          NOT NULL AUTO_INCREMENT,
    nombre         VARCHAR(100) NOT NULL,
    unidad_medida  VARCHAR(20)  NOT NULL,
    CONSTRAINT pk_producto PRIMARY KEY (producto_id)
) ENGINE = InnoDB;

CREATE TABLE inventario (
    tienda_id       INT           NOT NULL,
    producto_id     INT           NOT NULL,
    cantidad_stock  DECIMAL(10,2) NOT NULL,
    CONSTRAINT pk_inventario PRIMARY KEY (tienda_id, producto_id),
    CONSTRAINT fk_inventario_tienda FOREIGN KEY (tienda_id)
        REFERENCES tienda (tienda_id) ON DELETE RESTRICT,
    CONSTRAINT fk_inventario_producto FOREIGN KEY (producto_id)
        REFERENCES producto (producto_id) ON DELETE RESTRICT,
    CONSTRAINT ck_inventario_cantidad_stock_no_negativa CHECK (cantidad_stock >= 0)
) ENGINE = InnoDB;

CREATE TABLE pedido (
    pedido_id          INT           NOT NULL AUTO_INCREMENT,
    fecha_exacta       DATETIME      NOT NULL,
    cantidad_comprada  DECIMAL(10,2) NOT NULL,
    cliente_id         INT           NOT NULL,
    tienda_id          INT           NOT NULL,
    producto_id        INT           NOT NULL,
    CONSTRAINT pk_pedido PRIMARY KEY (pedido_id),
    CONSTRAINT fk_pedido_cliente FOREIGN KEY (cliente_id)
        REFERENCES cliente (cliente_id) ON DELETE RESTRICT,
    CONSTRAINT fk_pedido_tienda FOREIGN KEY (tienda_id)
        REFERENCES tienda (tienda_id) ON DELETE RESTRICT,
    CONSTRAINT fk_pedido_producto FOREIGN KEY (producto_id)
        REFERENCES producto (producto_id) ON DELETE RESTRICT,
    CONSTRAINT ck_pedido_cantidad_comprada_positiva CHECK (cantidad_comprada > 0)
) ENGINE = InnoDB;

CREATE INDEX idx_pedido_cliente_id  ON pedido (cliente_id);
CREATE INDEX idx_pedido_tienda_id   ON pedido (tienda_id);
CREATE INDEX idx_pedido_producto_id ON pedido (producto_id);
