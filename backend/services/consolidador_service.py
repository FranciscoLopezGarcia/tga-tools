import time
import os
import zipfile
from config import Config

def procesar_consolidador(job_id, files, JOBS):
    try:
        JOBS[job_id]["status"] = "processing"
        total = len(files)

        output_zip_path = os.path.join(Config.OUTPUT_FOLDER, f"{job_id}_consolidado.zip")
        with zipfile.ZipFile(output_zip_path, "w") as zipf:
            for i, file in enumerate(files, 1):
                temp_path = os.path.join(Config.UPLOAD_FOLDER, file.filename)
                file.save(temp_path)

                # Simular procesamiento (espera breve)
                time.sleep(2)
                JOBS[job_id]["progress"] = int((i / total) * 100)
                JOBS[job_id]["message"] = f"Procesando {i}/{total}: {file.filename}"

                zipf.write(temp_path, arcname=file.filename)
                os.remove(temp_path)

        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["result_file"] = output_zip_path
        JOBS[job_id]["message"] = "Consolidación completada"
        JOBS[job_id]["progress"] = 100

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["message"] = f"Error: {str(e)}"
