# -*- coding: utf-8 -*-
"""
Tareas de procesamiento de PDFs
"""
from pathlib import Path
import pandas as pd
import zipfile
from datetime import datetime
import sys

# Agregar paths necesarios
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# TU CÓDIGO - importar tus parsers
# from parsers import procesar_pdf  # o como se llame tu función


def process_pdfs_sync(pdf_paths, output_folder):
    """
    Procesar PDFs de forma síncrona (sin Celery)
    
    Args:
        pdf_paths: Lista de paths de PDFs
        output_folder: Carpeta donde guardar resultados
    
    Returns:
        Dict con resultados
    """
    resultados = []
    todos_los_registros = []
    
    for pdf_path in pdf_paths:
        try:
            # AQUÍ VA TU LÓGICA DE PROCESAMIENTO
            # Ejemplo usando tu código:
            # df = procesar_pdf(pdf_path)
            
            # Por ahora, simulación:
            df = pd.DataFrame({
                'columna1': ['dato1', 'dato2'],
                'columna2': ['dato3', 'dato4']
            })
            
            if not df.empty:
                # Guardar Excel individual
                output_xlsx = Path(output_folder) / f"{Path(pdf_path).stem}.xlsx"
                df.to_excel(output_xlsx, index=False, sheet_name="EXTRACTOS")
                
                # Agregar al consolidado
                todos_los_registros.append(df)
                
                resultados.append({
                    'archivo': Path(pdf_path).name,
                    'registros': len(df),
                    'estado': 'OK'
                })
            else:
                resultados.append({
                    'archivo': Path(pdf_path).name,
                    'registros': 0,
                    'estado': 'SIN DATOS'
                })
        
        except Exception as e:
            resultados.append({
                'archivo': Path(pdf_path).name,
                'registros': 0,
                'estado': f'ERROR: {str(e)}'
            })
    
    # Generar consolidado
    if todos_los_registros:
        df_consolidado = pd.concat(todos_los_registros, ignore_index=True)
        consolidado_path = Path(output_folder) / "CONSOLIDADO.xlsx"
        df_consolidado.to_excel(consolidado_path, index=False, sheet_name="CONSOLIDADO")
    
    # Crear ZIP
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"Extractos_Procesados_{timestamp}.zip"
    zip_path = Path(output_folder) / zip_filename
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in Path(output_folder).glob("*.xlsx"):
            zipf.write(file, file.name)
    
    return {
        'resultados': resultados,
        'zip_file': zip_filename,
        'total_archivos': len(pdf_paths),
        'total_registros': len(df_consolidado) if todos_los_registros else 0
    }


# Versión con Celery (si está disponible)
try:
    from celery_worker import celery
    
    @celery.task(bind=True)
    def process_pdfs_task(self, pdf_paths, output_folder):
        """
        Tarea de Celery para procesar PDFs de forma asíncrona
        """
        total = len(pdf_paths)
        
        # Actualizar estado inicial
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': total, 'status': 'Iniciando...'}
        )
        
        resultados = []
        todos_los_registros = []
        
        for idx, pdf_path in enumerate(pdf_paths, 1):
            try:
                # Actualizar progreso
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx,
                        'total': total,
                        'status': f'Procesando {Path(pdf_path).name}...'
                    }
                )
                
                # AQUÍ VA TU LÓGICA DE PROCESAMIENTO
                # df = procesar_pdf(pdf_path)
                
                # Simulación:
                df = pd.DataFrame({
                    'columna1': ['dato1', 'dato2'],
                    'columna2': ['dato3', 'dato4']
                })
                
                if not df.empty:
                    output_xlsx = Path(output_folder) / f"{Path(pdf_path).stem}.xlsx"
                    df.to_excel(output_xlsx, index=False, sheet_name="EXTRACTOS")
                    todos_los_registros.append(df)
                    
                    resultados.append({
                        'archivo': Path(pdf_path).name,
                        'registros': len(df),
                        'estado': 'OK'
                    })
                else:
                    resultados.append({
                        'archivo': Path(pdf_path).name,
                        'registros': 0,
                        'estado': 'SIN DATOS'
                    })
            
            except Exception as e:
                resultados.append({
                    'archivo': Path(pdf_path).name,
                    'registros': 0,
                    'estado': f'ERROR: {str(e)}'
                })
        
        # Generar consolidado
        if todos_los_registros:
            df_consolidado = pd.concat(todos_los_registros, ignore_index=True)
            consolidado_path = Path(output_folder) / "CONSOLIDADO.xlsx"
            df_consolidado.to_excel(consolidado_path, index=False, sheet_name="CONSOLIDADO")
        
        # Crear ZIP
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"Extractos_Procesados_{timestamp}.zip"
        zip_path = Path(output_folder) / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in Path(output_folder).glob("*.xlsx"):
                zipf.write(file, file.name)
        
        return {
            'resultados': resultados,
            'zip_file': zip_filename,
            'total_archivos': len(pdf_paths),
            'total_registros': len(df_consolidado) if todos_los_registros else 0
        }

except ImportError:
    # Celery no disponible
    pass