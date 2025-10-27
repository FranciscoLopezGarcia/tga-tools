from flask import Blueprint, jsonify, request
import uuid
import threading
from services.consolidador_service import procesar_consolidador

consolidador_bp = Blueprint("consolidador_bp", __name__)

JOBS = {}

@consolidador_bp.route("/upload", methods=["POST"])
def upload_consolidador():
    files = request.files.getlist("files[]")
    if not files:
        return jsonify({"error": "No se enviaron archivos"}), 400

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "queued", "progress": 0, "message": "Iniciando..."}

    thread = threading.Thread(target=procesar_consolidador, args=(job_id, files, JOBS))
    thread.start()

    return jsonify({"job_id": job_id, "message": "Archivos recibidos", "files_count": len(files)}), 200


@consolidador_bp.route("/status/<job_id>", methods=["GET"])
def job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job no encontrado"}), 404
    return jsonify(job)


@consolidador_bp.route("/download/<job_id>", methods=["GET"])
def download_result(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "completed":
        return jsonify({"error": "El procesamiento aún no ha terminado"}), 400

    from flask import send_file
    return send_file(job["result_file"], as_attachment=True)
