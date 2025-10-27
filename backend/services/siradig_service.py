import time
import os
import zipfile
import traceback
import logging
from config import Config

logger = logging.getLogger(__name__)

def procesar_siradig(job_id, files, JOBS):
    try:
        logger.info(f"🚀 Iniciando procesamiento Siradig del job {job_id} ({len(files)} archivos)")

        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)

        JOBS[job_id]["state"] = "PROGRESS"
        JOBS[job_id]["status"] = "Procesando formularios F.572..."
        total = len(files)

        output_zip_path = os.path.join(Config.OUTPUT_FOLDER, f"{job_id}_siradig.zip")

        with zipfile.ZipFile(output_zip_path, "w") as zipf:
            for i, file in enumerate(files, 1):
                filename = file["filename"]
                temp_path = os.path.join(Config.UPLOAD_FOLDER, f"{job_id}_{filename}")
                logger.info(f"  📄 Procesando formulario {i}/{total}: {filename}")

                # Guardar archivo desde memoria
                file["content"].seek(0)
                with open(temp_path, "wb") as f:
                    f.write(file["content"].read())

                # AQUÍ VA TU LÓGICA REAL DE SIRADIG
                time.sleep(0.5)
                
                progress = int((i / total) * 100)
                JOBS[job_id]["progress"] = progress
                JOBS[job_id]["status"] = f"Procesando formulario {i}/{total}: {filename}"

                # Agregar al ZIP
                zipf.write(temp_path, arcname=filename)
                os.remove(temp_path)

        JOBS[job_id]["state"] = "SUCCESS"
        JOBS[job_id]["result_file"] = output_zip_path
        JOBS[job_id]["status"] = "✅ Procesamiento de formularios completado"
        JOBS[job_id]["progress"] = 100
        
        JOBS[job_id]["results"] = {
            "total": total,
            "success": total,
            "errors": 0,
            "results": [{"name": f["filename"], "status": "success"} for f in files]
        }

        logger.info(f"🎉 Job Siradig {job_id} completado: {output_zip_path}")

    except Exception as e:
        logger.error(f"❌ Error en job Siradig {job_id}: {e}")
        traceback.print_exc()
        
        JOBS[job_id]["state"] = "FAILURE"
        JOBS[job_id]["status"] = f"❌ Error: {str(e)}"
        JOBS[job_id]["progress"] = 0