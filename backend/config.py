"""Backend configuration helpers."""
import os
import sys
import logging
from pathlib import Path

class Config:
    # Configuración Flask existente
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # Carpetas
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
    OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "output")
    LOG_FOLDER = os.path.join(os.path.dirname(__file__), "logs")
    
    # Límites
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max
    
    # CORS
    CORS_ORIGINS = ["http://localhost:5000", "http://127.0.0.1:5000"]

# 🔧 DETECCIÓN AUTOMÁTICA DE ENTORNO PARA OCR
def _detect_environment():
    """Detecta si estamos en Docker, Windows o Linux/Mac."""
    is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true"
    is_windows = sys.platform.startswith("win")
    
    if is_docker:
        return "docker"
    elif is_windows:
        return "windows"
    else:
        return "linux"

ENVIRONMENT = _detect_environment()

# 🔧 PATHS DE TESSERACT Y POPPLER SEGÚN ENTORNO
if ENVIRONMENT == "docker":
    DEFAULT_TESSERACT_PATH = "/usr/bin/tesseract"
    DEFAULT_POPPLER_PATH = "/usr/bin"

elif ENVIRONMENT == "windows":
    # 🔧 Ruta en carpeta de usuario (sin permisos de admin)
    DEFAULT_TESSERACT_PATH = r"C:\tools\tesseract\tesseract.exe"
    DEFAULT_POPPLER_PATH = r"C:\tools\poppler\poppler-25.07.0\Library\bin"







else:
    DEFAULT_TESSERACT_PATH = "/usr/bin/tesseract"
    DEFAULT_POPPLER_PATH = "/usr/bin"

# Variables de entorno (override manual si es necesario)
TESSERACT_PATH = os.getenv("TESSERACT_PATH", DEFAULT_TESSERACT_PATH)
POPPLER_PATH = os.getenv("POPPLER_PATH", DEFAULT_POPPLER_PATH)

# 🔍 Debug visual directo en consola
print(f"🧠 [DEBUG] Cargando config.py (entorno detectado={ENVIRONMENT})")
print(f"🧠 [DEBUG] TESSERACT_PATH = {TESSERACT_PATH}")
print(f"🧠 [DEBUG] POPPLER_PATH = {POPPLER_PATH}")

# Log de configuración
logger = logging.getLogger(__name__)
logger.info(f"🔧 Entorno detectado: {ENVIRONMENT}")
logger.info(f"📍 TESSERACT_PATH: {TESSERACT_PATH}")
logger.info(f"📍 POPPLER_PATH: {POPPLER_PATH}")
