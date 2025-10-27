import os
import zipfile
import logging
from pathlib import Path
import pandas as pd
from config import Config

logger = logging.getLogger(__name__)

def procesar_siradig(job_id, files, JOBS):
    """Procesa formularios F.572 SIRADIG."""
    try:
        logger.info(f"🚀 Iniciando SIRADIG - Job {job_id} ({len(files)} archivos)")

        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)

        JOBS[job_id]["state"] = "PROGRESS"
        JOBS[job_id]["status"] = "Inicializando parser SIRADIG..."
        JOBS[job_id]["progress"] = 5

        # Importar parser SIRADIG
        from extractors.siradig_parser import procesar_pdf

        JOBS[job_id]["progress"] = 10
        total = len(files)
        all_dataframes = []
        errores = []

        # Procesar cada PDF
        for i, file_dict in enumerate(files, 1):
            filename = file_dict["filename"]
            content = file_dict["content"]
            
            logger.info(f"📄 Procesando F.572 {i}/{total}: {filename}")
            JOBS[job_id]["status"] = f"Procesando {i}/{total}: {filename}"
            JOBS[job_id]["progress"] = 10 + int((i / total) * 80)

            try:
                # Guardar temporalmente
                temp_path = os.path.join(Config.UPLOAD_FOLDER, f"{job_id}_{filename}")
                content.seek(0)
                with open(temp_path, "wb") as f:
                    f.write(content.read())
                
                # PROCESAR CON SIRADIG PARSER
                df_result = procesar_pdf(temp_path)
                
                if not df_result.empty:
                    all_dataframes.append(df_result)
                    logger.info(f"  ✅ {filename}: {len(df_result)} registros extraídos")
                else:
                    errores.append({"name": filename, "status": "empty", "error": "Sin datos"})
                    logger.warning(f"  ⚠️ {filename}: Sin datos")

                # Limpiar temporal
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            except Exception as e:
                logger.error(f"  ❌ Error: {filename}: {str(e)}", exc_info=True)
                errores.append({"name": filename, "status": "error", "error": str(e)})

        # CONSOLIDAR TODOS
        JOBS[job_id]["status"] = "Consolidando formularios..."
        JOBS[job_id]["progress"] = 90
        
        output_zip_path = os.path.join(Config.OUTPUT_FOLDER, f"{job_id}_siradig.zip")
        
        if all_dataframes:
            try:
                # Consolidar todos los DataFrames
                df_consolidado = pd.concat(all_dataframes, ignore_index=True)
                
                # Guardar Excel consolidado
                consolidated_excel = os.path.join(Config.OUTPUT_FOLDER, f"{job_id}_siradig_consolidado.xlsx")
                df_consolidado.to_excel(consolidated_excel, index=False, sheet_name="SIRADIG")
                
                # Crear ZIP
                with zipfile.ZipFile(output_zip_path, "w") as zipf:
                    zipf.write(consolidated_excel, arcname="siradig_consolidado.xlsx")
                
                os.remove(consolidated_excel)
                logger.info(f"✅ Consolidado SIRADIG: {len(df_consolidado)} registros")
                
            except Exception as e:
                logger.error(f"❌ Error consolidando SIRADIG: {e}", exc_info=True)
                with zipfile.ZipFile(output_zip_path, "w") as zipf:
                    pass
        else:
            with zipfile.ZipFile(output_zip_path, "w") as zipf:
                pass

        # COMPLETADO
        JOBS[job_id]["state"] = "SUCCESS"
        JOBS[job_id]["result_file"] = output_zip_path
        JOBS[job_id]["progress"] = 100
        
        success_count = len(all_dataframes)
        error_count = len(errores)
        
        if error_count > 0:
            JOBS[job_id]["status"] = f"✅ Completado con advertencias: {success_count} OK, {error_count} errores"
        else:
            JOBS[job_id]["status"] = f"✅ Completado: {success_count} formularios procesados"
        
        JOBS[job_id]["results"] = {
            "total": total,
            "success": success_count,
            "errors": error_count,
            "results": [
                {"name": "Formulario procesado", "status": "success"}
                for _ in all_dataframes
            ] + errores
        }

        logger.info(f"🎉 Job SIRADIG {job_id} completado: {success_count} OK, {error_count} errores")

    except Exception as e:
        logger.error(f"❌ Error fatal SIRADIG: {e}", exc_info=True)
        JOBS[job_id]["state"] = "FAILURE"
        JOBS[job_id]["status"] = f"❌ Error: {str(e)}"
        JOBS[job_id]["progress"] = 0