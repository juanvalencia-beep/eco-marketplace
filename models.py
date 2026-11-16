from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def money(value):
    return round(float(value), 2) if value is not None else None


def points_for(cantidad):
    # 10 eco-points per unit bought, rounded down
    return int(cantidad * 10)


class Cliente(db.Model):
    __tablename__ = 'cliente'

    cliente_id = db.Column(db.Integer)
    nombre_completo = db.Column(db.String(100), nullable=False)
    correo_electronico = db.Column(db.String(120), nullable=False)
    puntos_ecologicos = db.Column(db.Integer, nullable=False, default=0, server_default='0')

    __table_args__ = (
        db.PrimaryKeyConstraint('cliente_id', name='pk_cliente'),
        db.UniqueConstraint('correo_electronico', name='uq_cliente_correo_electronico'),
        db.CheckConstraint('puntos_ecologicos >= 0', name='ck_cliente_puntos_ecologicos_no_negativo'),
        {'sqlite_autoincrement': True},
    )

    def to_dict(self):
        return {
            'cliente_id': self.cliente_id,
            'nombre_completo': self.nombre_completo,
            'correo_electronico': self.correo_electronico,
            'puntos_ecologicos': self.puntos_ecologicos,
        }


class Tienda(db.Model):
    __tablename__ = 'tienda'

    tienda_id = db.Column(db.Integer)
    nombre_sucursal = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint('tienda_id', name='pk_tienda'),
        {'sqlite_autoincrement': True},
    )

    def to_dict(self):
        return {
            'tienda_id': self.tienda_id,
            'nombre_sucursal': self.nombre_sucursal,
            'direccion': self.direccion,
        }


class Producto(db.Model):
    __tablename__ = 'producto'

    producto_id = db.Column(db.Integer)
    nombre = db.Column(db.String(100), nullable=False)
    unidad_medida = db.Column(db.String(20), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint('producto_id', name='pk_producto'),
        {'sqlite_autoincrement': True},
    )

    def to_dict(self):
        return {
            'producto_id': self.producto_id,
            'nombre': self.nombre,
            'unidad_medida': self.unidad_medida,
        }


class Inventario(db.Model):
    __tablename__ = 'inventario'

    tienda_id = db.Column(db.Integer, db.ForeignKey('tienda.tienda_id', name='fk_inventario_tienda',
                                                    ondelete='RESTRICT'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.producto_id', name='fk_inventario_producto',
                                                      ondelete='RESTRICT'), nullable=False)
    cantidad_stock = db.Column(db.Numeric(10, 2), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint('tienda_id', 'producto_id', name='pk_inventario'),
        db.CheckConstraint('cantidad_stock >= 0', name='ck_inventario_cantidad_stock_no_negativa'),
    )

    tienda = db.relationship('Tienda')
    producto = db.relationship('Producto')

    def to_dict(self):
        return {
            'tienda_id': self.tienda_id,
            'producto_id': self.producto_id,
            'cantidad_stock': money(self.cantidad_stock),
            'nombre_sucursal': self.tienda.nombre_sucursal,
            'nombre_producto': self.producto.nombre,
            'unidad_medida': self.producto.unidad_medida,
        }


class Pedido(db.Model):
    __tablename__ = 'pedido'

    pedido_id = db.Column(db.Integer)
    fecha_exacta = db.Column(db.DateTime, nullable=False)
    cantidad_comprada = db.Column(db.Numeric(10, 2), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.cliente_id', name='fk_pedido_cliente',
                                                     ondelete='RESTRICT'), nullable=False)
    tienda_id = db.Column(db.Integer, db.ForeignKey('tienda.tienda_id', name='fk_pedido_tienda',
                                                    ondelete='RESTRICT'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.producto_id', name='fk_pedido_producto',
                                                      ondelete='RESTRICT'), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint('pedido_id', name='pk_pedido'),
        db.CheckConstraint('cantidad_comprada > 0', name='ck_pedido_cantidad_comprada_positiva'),
        db.Index('idx_pedido_cliente_id', 'cliente_id'),
        db.Index('idx_pedido_tienda_id', 'tienda_id'),
        db.Index('idx_pedido_producto_id', 'producto_id'),
        {'sqlite_autoincrement': True},
    )

    cliente = db.relationship('Cliente')
    tienda = db.relationship('Tienda')
    producto = db.relationship('Producto')

    def to_dict(self):
        return {
            'pedido_id': self.pedido_id,
            'fecha_exacta': self.fecha_exacta.isoformat(timespec='seconds'),
            'cantidad_comprada': money(self.cantidad_comprada),
            'cliente_id': self.cliente_id,
            'tienda_id': self.tienda_id,
            'producto_id': self.producto_id,
            'nombre_completo': self.cliente.nombre_completo,
            'nombre_sucursal': self.tienda.nombre_sucursal,
            'nombre_producto': self.producto.nombre,
            'unidad_medida': self.producto.unidad_medida,
            'puntos_ganados': points_for(self.cantidad_comprada),
        }
