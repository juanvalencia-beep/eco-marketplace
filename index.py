# Entry point for Vercel.
# On Vercel only /tmp can be written, so the SQLite file goes there and it is
# filled with the sample data the first time. The data resets when Vercel
# starts a new instance, which is fine for the demo.
import os

if os.environ.get('VERCEL') and not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:////tmp/eco_marketplace.db'

from app import create_app
from models import db, Tienda
from seed import seed

app = create_app()

with app.app_context():
    if db.session.query(Tienda).count() == 0:
        seed()
