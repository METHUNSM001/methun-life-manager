from vercel_wsgi import make_handler
from app import app as flask_app

# Vercel's Python serverless runtime will call the `handler` object.
handler = make_handler(flask_app)
