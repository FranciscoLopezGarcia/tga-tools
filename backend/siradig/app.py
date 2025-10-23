# -*- coding: utf-8 -*-
"""
Siradig - Flask App Principal
"""
from flask import Flask
from pathlib import Path
import sys

# Agregar path del shared al PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import get_config
from shared.middleware import setup_cors, setup_logging, error_handler

# Crear app
app = Flask(__name__)

# Configuración
config = get_config()
app.config.from_object(config)

# Configurar carpetas
app.config['UPLOAD_FOLDER'] = Path(app.root_path) / 'uploads'
app.config['OUTPUT_FOLDER'] = Path(app.root_path) / 'output'

# Crear carpetas si no existen
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)
app.config['OUTPUT_FOLDER'].mkdir(exist_ok=True)

# Setup middleware
setup_cors(app)
setup_logging(app)
error_handler(app)

# Importar y registrar blueprints
from routes.upload import upload_bp
from routes.download import download_bp

app.register_blueprint(upload_bp, url_prefix='/api')
app.register_blueprint(download_bp, url_prefix='/api')


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'service': 'siradig'}


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])