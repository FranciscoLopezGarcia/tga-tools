from .extractos import extractos_bp
from .siradig import siradig_bp
from .consolidador import consolidador_bp

def register_routes(app):
    app.register_blueprint(extractos_bp, url_prefix="/api/extractos")
    app.register_blueprint(siradig_bp, url_prefix="/api/siradig")
    app.register_blueprint(consolidador_bp, url_prefix="/api/consolidador")
