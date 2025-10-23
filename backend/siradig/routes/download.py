# -*- coding: utf-8 -*-
"""
Download endpoint - Descargar archivos procesados
"""
from flask import Blueprint, send_file, current_app, jsonify
from pathlib import Path

download_bp = Blueprint('download', __name__)


@download_bp.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """
    Descargar archivo procesado
    """
    try:
        file_path = Path(current_app.config['OUTPUT_FOLDER']) / filename
        
        if not file_path.exists():
            return jsonify({'error': 'Archivo no encontrado'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        current_app.logger.error(f"Error descargando archivo: {e}")
        return jsonify({'error': str(e)}), 500