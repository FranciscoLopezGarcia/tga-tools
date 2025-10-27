import time
import os
import zipfile
import traceback
import logging
from config import Config

logger = logging.getLogger(__name__)

def procesar_extractos(job_id, files, JOBS):
    try:
        logger.info(f"🚀 Iniciando procesamiento del job {job_id} ({len(files)} archivos)")

        # Crear carpetas si no existen
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)

        # Actualizar estado a PROGRESS
        JOBS[job_id]["state"] = "PROGRESS"
        JOBS[job_id]["status"] = "Procesando archivos..."
        total = len(files)

        output_zip_path = os.path.join(Config.OUTPUT_FOLDER, f"{job_id}.zip")

        with zipfile.ZipFile(output_zip_path, "w") as zipf:
            for i, file in enumerate(files, 1):
                filename = file["filename"]
                temp_path = os.path.join(Config.UPLOAD_FOLDER, f"{job_id}_{filename}")
                logger.info(f"  📄 Procesando {i}/{total}: {filename}")

                # Guardar el archivo desde memoria
                file["content"].seek(0)
                with open(temp_path, "wb") as f:
                    f.write(file["content"].read())

                # AQUÍ VA TU LÓGICA REAL DE PROCESAMIENTO
                # Por ahora simulamos con sleep
                time.sleep(0.5)
                
                # Actualizar progreso
                progress = int((i / total) * 100)
                JOBS[job_id]["progress"] = progress
                JOBS[job_id]["status"] = f"Procesando {i}/{total}: {filename}"

                # Agregar al ZIP
                zipf.write(temp_path, arcname=filename)
                os.remove(temp_path)

        # Marcar como completado exitosamente
        JOBS[job_id]["state"] = "SUCCESS"
        JOBS[job_id]["result_file"] = output_zip_path
        JOBS[job_id]["status"] = "✅ Procesamiento completado exitosamente"
        JOBS[job_id]["progress"] = 100
        
        # Agregar resultados
        JOBS[job_id]["results"] = {
            "total": total,
            "success": total,
            "errors": 0,
            "results": [{"name": f["filename"], "status": "success"} for f in files]
        }

        logger.info(f"🎉 Job {job_id} completado: {output_zip_path}")

    except Exception as e:
        logger.error(f"❌ Error en job {job_id}: {e}")
        traceback.print_exc()
        
        JOBS[job_id]["state"] = "FAILURE"
        JOBS[job_id]["status"] = f"❌ Error: {str(e)}"
        JOBS[job_id]["progress"] = 0