from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from config import Config
import os
import logging
from routes.extractos import extractos_bp
from routes.siradig import siradig_bp
from routes.consolidador import consolidador_bp
from dotenv import load_dotenv


load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    # El frontend debe estar en ../frontend relativo al backend
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    app.config.from_object(Config)

    # Crear carpetas necesarias
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    os.makedirs(app.config['LOG_FOLDER'], exist_ok=True)

    # CORS - permite requests desde el mismo origen
    CORS(app, 
         origins=["http://localhost:5000", "http://127.0.0.1:5000", "*"],
         allow_headers=["Content-Type"],
         methods=["GET", "POST", "OPTIONS"],
         supports_credentials=True)

    # Registrar blueprints
    app.register_blueprint(extractos_bp, url_prefix='/api/extractos')
    app.register_blueprint(siradig_bp, url_prefix='/api/siradig')
    app.register_blueprint(consolidador_bp, url_prefix='/api/consolidador')

    # Servir frontend
    @app.route('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')
    
    @app.route('/<path:path>')
    def serve_static(path):
        file_path = os.path.join(app.static_folder, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory(app.static_folder, path)
        # Si no existe el archivo, servir index.html (para SPA routing)
        return send_from_directory(app.static_folder, 'index.html')

    # Health check
    @app.route("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "version": "1.0.0",
            "message": "TGA Tools API funcionando correctamente"
        })

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        logger.error(f"404: {request.url}")
        return jsonify({"error": "Endpoint no encontrado"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"500: {str(e)}")
        return jsonify({"error": "Error interno del servidor", "message": str(e)}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    
    logger.info("=" * 60)
    logger.info("🚀 TGA TOOLS - Servidor iniciando")
    logger.info("=" * 60)
    logger.info(f"🌐 URL: http://localhost:{port}")
    logger.info(f"📁 Frontend: {app.static_folder}")
    logger.info(f"📂 Uploads: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"📂 Outputs: {app.config['OUTPUT_FOLDER']}")
    logger.info(f"📂 Logs: {app.config['LOG_FOLDER']}")
    logger.info("=" * 60)
    
    app.run(
        host="0.0.0.0", 
        port=port, 
        debug=app.config['DEBUG'],
        threaded=True  # CRÍTICO para threads
    )