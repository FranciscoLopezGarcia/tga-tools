from flask import Blueprint, request, jsonify, send_file
import uuid
import threading
from services.extractos_service import procesar_extractos
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

extractos_bp = Blueprint("extractos_bp", __name__)

# Diccionario compartido de JOBS
JOBS = {}

@extractos_bp.route("/upload", methods=["POST", "OPTIONS"])
def upload_extractos():
    # Manejar preflight CORS
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        # CRÍTICO: El frontend envía 'files', no 'files[]'
        files = request.files.getlist("files")
        
        if not files:
            logger.warning("⚠️ No se recibieron archivos en la petición")
            return jsonify({"error": "No se enviaron archivos"}), 400

        logger.info(f"📦 Extractos - Recibidos {len(files)} archivos: {[f.filename for f in files]}")

        # Copiar archivos en memoria para evitar que se cierren
        files_copy = []
        for f in files:
            file_data = f.read()
            files_copy.append({
                "filename": f.filename,
                "content": BytesIO(file_data)
            })
            logger.info(f"  ✓ {f.filename} ({len(file_data)} bytes)")

        # Generar job_id
        job_id = str(uuid.uuid4())
        JOBS[job_id] = {
            "state": "PENDING",
            "progress": 0,
            "status": "Archivos recibidos, iniciando procesamiento..."
        }

        # Lanzar procesamiento en thread
        thread = threading.Thread(target=procesar_extractos, args=(job_id, files_copy, JOBS))
        thread.daemon = True
        thread.start()

        logger.info(f"🚀 Job {job_id} iniciado")

        return jsonify({
            "job_id": job_id,
            "message": "Archivos recibidos correctamente",
            "files_count": len(files)
        }), 200

    except Exception as e:
        logger.error(f"❌ Error en upload_extractos: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error al procesar archivos: {str(e)}"}), 500


@extractos_bp.route("/status/<job_id>", methods=["GET"])
def job_status(job_id):
    try:
        job = JOBS.get(job_id)
        if not job:
            logger.warning(f"⚠️ Job {job_id} no encontrado")
            return jsonify({"error": "Job no encontrado"}), 404
        
        return jsonify({
            "state": job.get("state", "PENDING"),
            "progress": job.get("progress", 0),
            "status": job.get("status", "Procesando..."),
            "results": job.get("results")
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error en job_status: {str(e)}")
        return jsonify({"error": str(e)}), 500


@extractos_bp.route("/download/<job_id>", methods=["GET"])
def download_result(job_id):
    try:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "Job no encontrado"}), 404
        
        if job.get("state") != "SUCCESS":
            return jsonify({"error": "El procesamiento aún no ha terminado"}), 400

        result_file = job.get("result_file")
        if not result_file:
            return jsonify({"error": "Archivo de resultado no disponible"}), 404

        logger.info(f"📥 Descargando resultado del job {job_id}")
        return send_file(
            result_file, 
            as_attachment=True, 
            download_name="extractos_resultado.zip"
        )
        
    except Exception as e:
        logger.error(f"❌ Error en download_result: {str(e)}")
        return jsonify({"error": str(e)}), 500


@extractos_bp.route("/log/<job_id>", methods=["GET"])
def download_log(job_id):
    try:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "Job no encontrado"}), 404
        
        log_file = job.get("log_file")
        if not log_file:
            # Crear log simple si no existe
            log_content = f"Job ID: {job_id}\nEstado: {job.get('state')}\nMensaje: {job.get('status')}\n"
            log_buffer = BytesIO(log_content.encode('utf-8'))
            return send_file(
                log_buffer,
                as_attachment=True,
                download_name=f"extractos_log_{job_id}.txt",
                mimetype='text/plain'
            )

        return send_file(
            log_file, 
            as_attachment=True, 
            download_name="extractos_log.txt"
        )
        
    except Exception as e:
        logger.error(f"❌ Error en download_log: {str(e)}")
        return jsonify({"error": str(e)}), 500