import logging
from pathlib import Path

def setup_logger(name="siradig", level=logging.DEBUG):
    """Configura logger con salida a archivo y consola."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar múltiples handlers
    if not logger.handlers:
        # Archivo
        file_handler = logging.FileHandler(log_dir / f"{name}.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        ))

        # Consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            "%(levelname)s - %(message)s"
        ))

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger