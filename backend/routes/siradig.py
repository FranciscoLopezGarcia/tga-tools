from flask import Blueprint, request, jsonify, send_file
import uuid
import threading
from services.siradig_service import procesar_siradig
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

siradig_bp = Blueprint("siradig_bp", __name__)

JOBS = {}

@siradig_bp.route("/upload", methods=["POST", "OPTIONS"])
def upload_siradig():
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        files = request.files.getlist("files")
        
        if not files:
            logger.warning("⚠️ No se recibieron archivos en la petición")
            return jsonify({"error": "No se enviaron archivos"}), 400

        logger.info(f"📦 Siradig - Recibidos {len(files)} archivos")

        # Copiar archivos en memoria
        files_copy = []
        for f in files:
            file_data = f.read()
            files_copy.append({
                "filename": f.filename,
                "content": BytesIO(file_data)
            })
            logger.info(f"  ✓ {f.filename}")

        job_id = str(uuid.uuid4())
        JOBS[job_id] = {
            "state": "PENDING",
            "progress": 0,
            "status": "Archivos recibidos, iniciando procesamiento..."
        }

        thread = threading.Thread(target=procesar_siradig, args=(job_id, files_copy, JOBS))
        thread.daemon = True
        thread.start()

        logger.info(f"🚀 Job Siradig {job_id} iniciado")

        return jsonify({
            "job_id": job_id,
            "message": "Archivos recibidos correctamente",
            "files_count": len(files)
        }), 200

    except Exception as e:
        logger.error(f"❌ Error en upload_siradig: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error al procesar archivos: {str(e)}"}), 500


@siradig_bp.route("/status/<job_id>", methods=["GET"])
def job_status(job_id):
    try:
        job = JOBS.get(job_id)
        if not job:
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


@siradig_bp.route("/download/<job_id>", methods=["GET"])
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

        logger.info(f"📥 Descargando resultado Siradig del job {job_id}")
        return send_file(
            result_file, 
            as_attachment=True, 
            download_name="siradig_resultado.zip"
        )
        
    except Exception as e:
        logger.error(f"❌ Error en download_result: {str(e)}")
        return jsonify({"error": str(e)}), 500


@siradig_bp.route("/log/<job_id>", methods=["GET"])
def download_log(job_id):
    try:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "Job no encontrado"}), 404
        
        log_file = job.get("log_file")
        if not log_file:
            log_content = f"Job ID: {job_id}\nEstado: {job.get('state')}\nMensaje: {job.get('status')}\n"
            log_buffer = BytesIO(log_content.encode('utf-8'))
            return send_file(
                log_buffer,
                as_attachment=True,
                download_name=f"siradig_log_{job_id}.txt",
                mimetype='text/plain'
            )

        return send_file(
            log_file, 
            as_attachment=True, 
            download_name="siradig_log.txt"
        )
        
    except Exception as e:
        logger.error(f"❌ Error en download_log: {str(e)}")
        return jsonify({"error": str(e)}), 500