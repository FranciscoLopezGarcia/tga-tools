import logging
import re
import os
import sys
from typing import List, Tuple
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageOps

# 👇 Integración con config.py de tga-tools
try:
    from config import TESSERACT_PATH, POPPLER_PATH
except ImportError:
    # fallback si se ejecuta standalone
    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    POPPLER_PATH = r"C:\poppler-24.08.0\bin"

logger = logging.getLogger(__name__)

class OCRExtractor:
    def __init__(
        self,
        lang: str = "spa",
        tesseract_cmd: str = None,
        poppler_bin: str = None,
    ):
        """OCR con Tesseract (Docker / Linux / Windows)."""
        
        # 🔧 DETECCIÓN AUTOMÁTICA DE ENTORNO
        is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true"
        is_windows = sys.platform.startswith("win")
        
        # 🔧 PATHS POR DEFECTO SEGÚN ENTORNO
        if is_docker:
            default_tesseract = "/usr/bin/tesseract"
            default_poppler = "/usr/bin"
        elif is_windows:
            default_tesseract = TESSERACT_PATH
            default_poppler = POPPLER_PATH
        else:
            default_tesseract = "/usr/bin/tesseract"
            default_poppler = "/usr/bin"
        
        # 🔧 PRIORIDAD: env vars > argumentos > defaults
        self.tesseract_cmd = (
            os.getenv("TESSERACT_PATH") or 
            tesseract_cmd or 
            default_tesseract
        )
        
        self.poppler_bin = (
            os.getenv("POPPLER_PATH") or 
            poppler_bin or 
            default_poppler
        )
        
        self.lang = lang
        
        # 🔧 VALIDACIÓN
        if not os.path.exists(self.tesseract_cmd):
            logger.warning(f"⚠️  Tesseract no encontrado en: {self.tesseract_cmd}")
        
        if not os.path.exists(self.poppler_bin):
            logger.warning(f"⚠️  Poppler no encontrado en: {self.poppler_bin}")
        
        pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        self.tess_config = "--oem 1 --psm 6"
        
        self.header_keywords = {
            "fecha", "concepto", "descripción", "descripcion", "detalle",
            "importe", "saldo", "débito", "debito", "crédito", "credito",
            "n°", "nro", "comprobante", "referencia",
            "Débito", "Crédito", "Debito", "Credito"
        }
        
        self.re_fecha = re.compile(r"\b([0-3]?\d)[/-]([01]?\d)[/-](\d{2}|\d{4})\b")
        self.re_importe = re.compile(r"(?<!\w)(?:-?\$?\s?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})(?!\w)")
        
        logger.info(
            f"OCRExtractor inicializado | Entorno: {'Docker' if is_docker else 'Local'} | "
            f"Poppler: {self.poppler_bin} | Tesseract: {self.tesseract_cmd}"
        )

    def _preprocess(self, img: Image.Image, scale: float = 1.35, thr: int = 180) -> Image.Image:
        """Mejora la imagen para OCR."""
        w, h = img.size
        if scale != 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        img = img.convert("L")
        img = ImageOps.autocontrast(img)
        img = img.point(lambda p: 255 if p > thr else 0)
        return img

    def _es_pagina_relevante(self, texto: str) -> Tuple[bool, dict]:
        t = texto.lower()
        headers = sum(1 for k in self.header_keywords if k in t)
        fechas = len(self.re_fecha.findall(texto))
        importes = len(self.re_importe.findall(texto))
        relevant = (
            (headers >= 2 and (fechas >= 5 or importes >= 5)) or
            (fechas >= 8 and importes >= 6) or
            (headers >= 3)
        )
        return relevant, {"headers": headers, "fechas": fechas, "importes": importes}

    def extract_text_pages(self, pdf_path: str, dpi_quick: int = 160, dpi_full: int = 200) -> List[Tuple[int, str]]:
        """Devuelve [(page_num, texto)] SOLO de páginas relevantes."""
        logger.info(f"OCR quick pass (dpi={dpi_quick}) → {pdf_path}")
        
        try:
            imgs_quick = convert_from_path(pdf_path, dpi=dpi_quick, poppler_path=self.poppler_bin)
        except Exception as e:
            logger.error(f"❌ convert_from_path (quick) falló: {e}")
            try:
                logger.info("🔄 Reintentando sin poppler_path explícito...")
                imgs_quick = convert_from_path(pdf_path, dpi=dpi_quick)
            except Exception as e2:
                logger.error(f"❌ Fallback también falló: {e2}")
                return []

        relevantes_idx = []
        for i, img in enumerate(imgs_quick, start=1):
            try:
                img_p = self._preprocess(img, scale=1.25, thr=180)
                raw = pytesseract.image_to_string(img_p, lang=self.lang, config=self.tess_config)
                safe_text = raw.encode("latin-1", errors="ignore").decode("latin-1", errors="ignore")
                is_rel, stats = self._es_pagina_relevante(safe_text)
                logger.info(
                    f"Página {i} quick → relev={is_rel} | headers={stats['headers']} "
                    f"fechas={stats['fechas']} importes={stats['importes']} | chars={len(safe_text)}"
                )
                if is_rel:
                    relevantes_idx.append(i)
            except Exception as e:
                logger.error(f"OCR quick falló en página {i}: {e}")

        if not relevantes_idx:
            logger.warning("⚠️ Ninguna página calificada como relevante en quick pass.")
            return []

        logger.info(f"OCR full pass (dpi={dpi_full}) solo en páginas {relevantes_idx}")
        
        resultados: List[Tuple[int, str]] = []
        BATCH_SIZE = 10

        for i in range(0, len(relevantes_idx), BATCH_SIZE):
            batch = relevantes_idx[i:i + BATCH_SIZE]
            
            try:
                logger.info(f"📄 Procesando lote de páginas: {batch}")
                imgs_batch = convert_from_path(
                    pdf_path, 
                    dpi=dpi_full, 
                    poppler_path=self.poppler_bin,
                    first_page=batch[0],
                    last_page=batch[-1]
                )
                
                for idx, img in zip(batch, imgs_batch):
                    try:
                        img_p = self._preprocess(img, scale=1.35, thr=180)
                        raw = pytesseract.image_to_string(img_p, lang=self.lang, config=self.tess_config)
                        safe_text = raw.encode("latin-1", errors="ignore").decode("latin-1", errors="ignore")
                        resultados.append((idx, safe_text))
                        logger.info(f"Página {idx} full → {len(safe_text)} chars")
                    except Exception as e:
                        logger.error(f"OCR full falló en página {idx}: {e}")
                
                del imgs_batch
            except Exception as e:
                logger.error(f"❌ Error procesando lote {batch}: {e}")

        return resultados

    def extract_text(self, pdf_path: str, dpi_quick=160, dpi_full=200) -> str:
        pages = self.extract_text_pages(pdf_path, dpi_quick=dpi_quick, dpi_full=dpi_full)
        return "\n\n".join([f"--- Página {p} ---\n{t}" for p, t in pages])


def ocr_extract_pages(pdf_path: str, dpi_quick=160, dpi_full=200, max_pages: int = None):
    ocr = OCRExtractor()
    pages = ocr.extract_text_pages(pdf_path, dpi_quick=dpi_quick, dpi_full=dpi_full)
    if max_pages is not None:
        pages = [p for p in pages if p[0] <= max_pages]
    return pages
