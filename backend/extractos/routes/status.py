# -*- coding: utf-8 -*-
"""
Status endpoint - Verificar estado de tarea Celery
"""
from flask import Blueprint, jsonify, current_app

status_bp = Blueprint('status', __name__)


@status_bp.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    """
    Obtener estado de una tarea de Celery
    """
    try:
        from celery_worker import celery
        from celery.result import AsyncResult
        
        task = AsyncResult(task_id, app=celery)
        
        response = {
            'task_id': task_id,
            'state': task.state,
            'status': 'processing'
        }
        
        if task.state == 'PENDING':
            response['status'] = 'Esperando en cola...'
        
        elif task.state == 'STARTED':
            response['status'] = 'Procesando archivos...'
        
        elif task.state == 'PROGRESS':
            response.update({
                'status': task.info.get('status', 'Procesando...'),
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 0)
            })
        
        elif task.state == 'SUCCESS':
            response.update({
                'status': 'Completado',
                'result': task.result
            })
        
        elif task.state == 'FAILURE':
            response.update({
                'status': 'Error',
                'error': str(task.info)
            })
        
        return jsonify(response)
    
    except Exception as e:
        current_app.logger.error(f"Error obteniendo estado: {e}")
        return jsonify({'error': str(e)}), 500