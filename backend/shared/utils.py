# -*- coding: utf-8 -*-
"""
Utilidades compartidas
"""
import os
import shutil
from pathlib import Path
from werkzeug.utils import secure_filename
import logging

logger = logging.getLogger(__name__)


def allowed_file(filename, allowed_extensions=None):
    """Verificar si el archivo tiene una extensión permitida"""
    if allowed_extensions is None:
        allowed_extensions = {'pdf'}
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def ensure_dir(directory):
    """Crear directorio si no existe"""
    Path(directory).mkdir(parents=True, exist_ok=True)


def clean_directory(directory):
    """Limpiar todos los archivos de un directorio"""
    try:
        for file_path in Path(directory).glob("*"):
            if file_path.is_file():
                file_path.unlink()
        logger.info(f"Directorio limpiado: {directory}")
    except Exception as e:
        logger.error(f"Error limpiando directorio {directory}: {e}")


def save_uploaded_files(files, upload_folder):
    """
    Guardar archivos subidos y retornar lista de paths
    
    Args:
        files: Lista de FileStorage objects
        upload_folder: Carpeta donde guardar
    
    Returns:
        Lista de paths de archivos guardados
    """
    ensure_dir(upload_folder)
    saved_files = []
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            saved_files.append(filepath)
            logger.info(f"Archivo guardado: {filename}")
    
    return saved_files


def format_file_size(size_bytes):
    """Formatear tamaño de archivo a formato legible"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def get_file_info(filepath):
    """Obtener información de un archivo"""
    path = Path(filepath)
    return {
        'name': path.name,
        'size': path.stat().st_size,
        'size_formatted': format_file_size(path.stat().st_size),
        'extension': path.suffix,
        'exists': path.exists()
    }