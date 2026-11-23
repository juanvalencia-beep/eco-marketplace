from decimal import ROUND_HALF_UP, Decimal

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
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False, default=0, server_default='0')

    __table_args__ = (
        db.PrimaryKeyConstraint('producto_id', name='pk_producto'),
        db.CheckConstraint('precio_unitario >= 0', name='ck_producto_precio_unitario_no_negativo'),
        {'sqlite_autoincrement': True},
    )

    def to_dict(self):
        return {
            'producto_id': self.producto_id,
            'nombre': self.nombre,
            'unidad_medida': self.unidad_medida,
            'precio_unitario': money(self.precio_unitario),
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
    """Order header: who bought, where and when. The products are in DetallePedido."""
    __tablename__ = 'pedido'

    pedido_id = db.Column(db.Integer)
    fecha_exacta = db.Column(db.DateTime, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.cliente_id', name='fk_pedido_cliente',
                                                     ondelete='RESTRICT'), nullable=False)
    tienda_id = db.Column(db.Integer, db.ForeignKey('tienda.tienda_id', name='fk_pedido_tienda',
                                                    ondelete='RESTRICT'), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint('pedido_id', name='pk_pedido'),
        db.Index('idx_pedido_cliente_id', 'cliente_id'),
        db.Index('idx_pedido_tienda_id', 'tienda_id'),
        db.Index('idx_pedido_fecha_exacta', 'fecha_exacta'),
        {'sqlite_autoincrement': True},
    )

    cliente = db.relationship('Cliente')
    tienda = db.relationship('Tienda')
    detalles = db.relationship('DetallePedido', back_populates='pedido', cascade='all, delete-orphan',
                               passive_deletes=True, order_by='DetallePedido.producto_id')

    @property
    def total(self):
        return sum((d.subtotal for d in self.detalles), Decimal('0'))

    @property
    def cantidad_total(self):
        return sum((d.cantidad for d in self.detalles), Decimal('0'))

    def to_dict(self, with_detalles=True):
        data = {
            'pedido_id': self.pedido_id,
            'fecha_exacta': self.fecha_exacta.isoformat(timespec='seconds'),
            'cliente_id': self.cliente_id,
            'tienda_id': self.tienda_id,
            'nombre_completo': self.cliente.nombre_completo,
            'nombre_sucursal': self.tienda.nombre_sucursal,
            'num_productos': len(self.detalles),
            'cantidad_total': money(self.cantidad_total),
            'total': money(self.total),
            'puntos_ganados': sum(d.puntos for d in self.detalles),
        }
        if with_detalles:
            data['detalles'] = [d.to_dict() for d in self.detalles]
        return data


class DetallePedido(db.Model):
    """Order line: one product of an order. The price is copied from the product when the
    order is made, so changing a product price later does not change old orders."""
    __tablename__ = 'detalle_pedido'

    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.pedido_id', name='fk_detalle_pedido_pedido',
                                                    ondelete='CASCADE'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.producto_id', name='fk_detalle_pedido_producto',
                                                      ondelete='RESTRICT'), nullable=False)
    cantidad = db.Column(db.Numeric(10, 2), nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint('pedido_id', 'producto_id', name='pk_detalle_pedido'),
        db.CheckConstraint('cantidad > 0', name='ck_detalle_pedido_cantidad_positiva'),
        db.CheckConstraint('precio_unitario >= 0', name='ck_detalle_pedido_precio_unitario_no_negativo'),
        db.Index('idx_detalle_pedido_producto_id', 'producto_id'),
    )

    pedido = db.relationship('Pedido', back_populates='detalles')
    producto = db.relationship('Producto')

    @property
    def subtotal(self):
        # rounded half up to cents, the same rule the reports use in SQL
        return (Decimal(self.cantidad) * Decimal(self.precio_unitario)).quantize(Decimal('0.01'), ROUND_HALF_UP)

    @property
    def puntos(self):
        return points_for(self.cantidad)

    def to_dict(self):
        return {
            'pedido_id': self.pedido_id,
            'producto_id': self.producto_id,
            'nombre_producto': self.producto.nombre,
            'unidad_medida': self.producto.unidad_medida,
            'cantidad': money(self.cantidad),
            'precio_unitario': money(self.precio_unitario),
            'subtotal': money(self.subtotal),
            'puntos': self.puntos,
        }
