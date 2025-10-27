import os
from dotenv import load_dotenv

# Cargar .env si existe
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")
    LOG_FOLDER = os.path.join(BASE_DIR, "logs")
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
