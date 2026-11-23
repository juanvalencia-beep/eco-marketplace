import os
import sqlite3

from flask import Flask, jsonify, send_from_directory
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from models import db
from openapi import SPEC, SWAGGER_HTML
from routes import api

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')


# SQLite ignores foreign keys (and so ON DELETE RESTRICT) unless this is
# turned on, and it only lasts for the connection, so do it on every connect.
@event.listens_for(Engine, 'connect')
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


def integrity_message(error):
    text = str(error.orig)
    if 'correo_electronico' in text:
        return 'Ya existe un cliente con ese correo electrónico'
    if 'inventario' in text and ('UNIQUE' in text or 'Duplicate' in text or 'PRIMARY' in text):
        return 'Esa tienda ya tiene inventario de ese producto'
    if 'cantidad_stock' in text:
        return 'No hay suficiente stock para esta operación'
    if 'FOREIGN KEY' in text or 'foreign key' in text:
        return 'El registro está relacionado con otros registros o hace referencia a uno que no existe'
    return 'La operación viola una restricción de la base de datos'


def create_app(database_url=None):
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')

    default_url = 'sqlite:///' + os.path.join(BASE_DIR, 'eco_marketplace.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or os.environ.get('DATABASE_URL', default_url)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.json.sort_keys = False

    db.init_app(app)
    app.register_blueprint(api, url_prefix='/api')

    @app.route('/')
    def index():
        return send_from_directory(STATIC_DIR, 'index.html')

    @app.route('/presentation')
    @app.route('/presentation/')
    def presentation():
        return send_from_directory(os.path.join(STATIC_DIR, 'presentation'), 'index.html')

    @app.route('/api/openapi.json')
    def openapi_spec():
        return jsonify(SPEC)

    @app.route('/api/docs')
    def api_docs():
        return SWAGGER_HTML

    # Werkzeug's own messages (unknown route, wrong method...) are in English
    DEFAULT_ERRORS = {404: 'Ruta no encontrada', 405: 'Método no permitido para esta ruta'}

    @app.errorhandler(HTTPException)
    def http_error(error):
        message = error.description
        if message == type(error).description:  # not a message of ours
            message = DEFAULT_ERRORS.get(error.code, message)
        return jsonify({'error': message}), error.code

    @app.errorhandler(IntegrityError)
    def integrity_error(error):
        db.session.rollback()
        return jsonify({'error': integrity_message(error)}), 409

    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
