# -*- coding: utf-8 -*-
"""
Celery Worker para procesamiento asíncrono
"""
from celery import Celery
from pathlib import Path
import sys

# Agregar path del shared
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import get_config

# Configuración
config = get_config()

# Crear instancia de Celery
celery = Celery(
    'extractos',
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND
)

# Configuración adicional
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Argentina/Buenos_Aires',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos
    task_soft_time_limit=25 * 60,  # 25 minutos
)

# Auto-discover tasks
celery.autodiscover_tasks(['tasks'])


if __name__ == '__main__':
    celery.start()