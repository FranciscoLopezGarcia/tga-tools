# -*- coding: utf-8 -*-
"""
Middleware compartido para todas las apps
"""
from flask import request, jsonify
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def setup_cors(app):
    """Configurar CORS en la app"""
    from flask_cors import CORS
    
    CORS(app, resources={
        r"/*": {
            "origins": app.config.get('CORS_ORIGINS', '*'),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Disposition"],
            "supports_credentials": True
        }
    })


def setup_logging(app):
    """Configurar logging en la app"""
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    log_format = app.config.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format
    )
    
    # Request logging
    @app.before_request
    def log_request():
        logger.info(f"{request.method} {request.path} - {request.remote_addr}")
    
    @app.after_request
    def log_response(response):
        logger.info(f"{request.method} {request.path} - {response.status_code}")
        return response


def validate_file_upload(allowed_extensions=None, max_size=None):
    """Decorator para validar archivos subidos"""
    if allowed_extensions is None:
        allowed_extensions = {'pdf'}
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar que hay archivos
            if 'files[]' not in request.files:
                return jsonify({'error': 'No se enviaron archivos'}), 400
            
            files = request.files.getlist('files[]')
            
            if not files or files[0].filename == '':
                return jsonify({'error': 'No se seleccionaron archivos'}), 400
            
            # Validar cada archivo
            for file in files:
                # Validar extensión
                if '.' not in file.filename:
                    return jsonify({'error': f'Archivo sin extensión: {file.filename}'}), 400
                
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in allowed_extensions:
                    return jsonify({
                        'error': f'Extensión no permitida: {ext}. Permitidas: {", ".join(allowed_extensions)}'
                    }), 400
                
                # Validar tamaño (si se especifica)
                if max_size:
                    file.seek(0, 2)  # Ir al final
                    size = file.tell()
                    file.seek(0)  # Volver al inicio
                    
                    if size > max_size:
                        max_mb = max_size / (1024 * 1024)
                        return jsonify({
                            'error': f'Archivo muy grande: {file.filename}. Máximo {max_mb}MB'
                        }), 400
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def error_handler(app):
    """Configurar manejo de errores global"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Solicitud inválida', 'message': str(error)}), 400
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'No encontrado', 'message': str(error)}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Error interno: {error}", exc_info=True)
        return jsonify({'error': 'Error interno del servidor'}), 500
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({'error': 'Archivo muy grande'}), 413