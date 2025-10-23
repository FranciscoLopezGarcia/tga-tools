# -*- coding: utf-8 -*-
"""
Upload endpoint - Subir y procesar PDFs
"""
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from pathlib import Path
import sys

# Agregar paths necesarios
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.middleware import validate_file_upload
from shared.utils import save_uploaded_files, clean_directory

upload_bp = Blueprint('upload', __name__)


@upload_bp.route('/upload', methods=['POST'])
@validate_file_upload(allowed_extensions={'pdf'}, max_size=100*1024*1024)
def upload_files():
    """
    Endpoint para subir y procesar PDFs
    
    Puede ser:
    - Síncrono: procesa y devuelve resultados directamente
    - Asíncrono: devuelve task_id para polling (si Celery está disponible)
    """
    try:
        # Limpiar carpetas
        clean_directory(current_app.config['UPLOAD_FOLDER'])
        clean_directory(current_app.config['OUTPUT_FOLDER'])
        
        # Obtener archivos
        files = request.files.getlist('files[]')
        
        # Guardar archivos
        saved_files = save_uploaded_files(files, current_app.config['UPLOAD_FOLDER'])
        
        if not saved_files:
            return jsonify({'error': 'No se guardaron archivos válidos'}), 400
        
        # Intentar usar Celery si está disponible
        try:
            from tasks.process_pdf import process_pdfs_task
            from celery_worker import celery
            
            # Procesamiento asíncrono con Celery
            task = process_pdfs_task.delay(saved_files, str(current_app.config['OUTPUT_FOLDER']))
            
            return jsonify({
                'success': True,
                'task_id': task.id,
                'message': 'Archivos en procesamiento',
                'total_files': len(saved_files)
            })
        
        except ImportError:
            # Celery no disponible, procesar síncronamente
            from tasks.process_pdf import process_pdfs_sync
            
            result = process_pdfs_sync(saved_files, str(current_app.config['OUTPUT_FOLDER']))
            
            return jsonify({
                'success': True,
                **result
            })
    
    except Exception as e:
        current_app.logger.error(f"Error en upload: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500