# -*- coding: utf-8 -*-
"""
Upload endpoint - Subir y procesar PDFs de Siradig
"""
from flask import Blueprint, request, jsonify, current_app
from pathlib import Path
import pandas as pd
import zipfile
from datetime import datetime
import sys

# Agregar paths necesarios
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.middleware import validate_file_upload
from shared.utils import save_uploaded_files, clean_directory

# TU CÓDIGO - importar tu parser
# from parser_tablas import procesar_pdf

upload_bp = Blueprint('upload', __name__)


@upload_bp.route('/upload', methods=['POST'])
@validate_file_upload(allowed_extensions={'pdf'}, max_size=100*1024*1024)
def upload_files():
    """
    Endpoint para subir y procesar PDFs de Siradig
    Procesamiento síncrono
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
        
        # Procesar archivos
        resultados = []
        todos_los_registros = []
        
        for pdf_path in saved_files:
            try:
                current_app.logger.info(f"Procesando {Path(pdf_path).name}...")
                
                # AQUÍ VA TU LÓGICA DE PROCESAMIENTO
                # df = procesar_pdf(pdf_path)
                
                # Por ahora, simulación:
                df = pd.DataFrame({
                    'columna1': ['dato1', 'dato2'],
                    'columna2': ['dato3', 'dato4']
                })
                
                if not df.empty:
                    # Guardar Excel individual
                    output_xlsx = Path(current_app.config['OUTPUT_FOLDER']) / f"{Path(pdf_path).stem}.xlsx"
                    df.to_excel(output_xlsx, index=False, sheet_name="SIRADIG")
                    
                    # Agregar al consolidado
                    todos_los_registros.append(df)
                    
                    resultados.append({
                        'archivo': Path(pdf_path).name,
                        'registros': len(df),
                        'estado': 'OK'
                    })
                    current_app.logger.info(f"✓ {Path(pdf_path).name}: {len(df)} registros")
                else:
                    resultados.append({
                        'archivo': Path(pdf_path).name,
                        'registros': 0,
                        'estado': 'SIN DATOS'
                    })
                    current_app.logger.warning(f"⚠ {Path(pdf_path).name}: Sin datos")
            
            except Exception as e:
                resultados.append({
                    'archivo': Path(pdf_path).name,
                    'registros': 0,
                    'estado': f'ERROR: {str(e)}'
                })
                current_app.logger.error(f"✕ Error procesando {Path(pdf_path).name}: {e}")
        
        # Generar consolidado
        if todos_los_registros:
            df_consolidado = pd.concat(todos_los_registros, ignore_index=True)
            consolidado_path = Path(current_app.config['OUTPUT_FOLDER']) / "CONSOLIDADO.xlsx"
            df_consolidado.to_excel(consolidado_path, index=False, sheet_name="CONSOLIDADO")
            current_app.logger.info(f"📊 Consolidado: {len(df_consolidado)} registros")
        
        # Crear ZIP
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"SIRADIG_Procesados_{timestamp}.zip"
        zip_path = Path(current_app.config['OUTPUT_FOLDER']) / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in Path(current_app.config['OUTPUT_FOLDER']).glob("*.xlsx"):
                zipf.write(file, file.name)
        
        current_app.logger.info(f"📦 ZIP generado: {zip_filename}")
        
        return jsonify({
            'success': True,
            'zip_file': zip_filename,
            'resultados': resultados,
            'total_archivos': len(saved_files),
            'total_registros': len(df_consolidado) if todos_los_registros else 0
        })
    
    except Exception as e:
        current_app.logger.error(f"Error general: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500