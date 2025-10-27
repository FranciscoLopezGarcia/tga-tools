# -*- coding: utf-8 -*-
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import pandas as pd

from .camelot_utils import extract_tables_with_camelot
from .ocr_extractor import ocr_extract_pages
from .unificador import unify_camelot_tables
from pdf_reader import PDFReader

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# ✅ Configuración de bancos
FORCE_OCR_BANKS = {"ICBC", "COMAFI", "MERCADOPAGO", "SUPERVIELLE", "GALICIA"}
SKIP_CAMELOT_BANKS = {"MACRO"}
CAMELOT_MAX_PAGES = 5

_NOISE_PATTERNS = [
    r"^\s*hoja\s*\d+(\s*/\s*\d+)?\s*$",
    r"^\s*p[aáà]gina\s*\d+(\s*/\s*\d+)?\s*$",
    r"^\s*fecha de descarga\s*$",
    r"^\s*home banking\s*$",
    r"^\s*contact( center)?\s*$",
]
_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS), re.IGNORECASE)


def _is_probably_noise(line: str) -> bool:
    if not line or len(line) < 3:
        return True
    if _NOISE_RE.search(line):
        return True
    return False


def _lightline(line: str) -> str:
    line = re.sub(r"[ \t]+", " ", (line or "")).strip()
    line = line.replace("\u00A0", " ")
    return line


def _preclean_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    for ln in lines:
        ln = _lightline(ln)
        if not ln:
            continue
        if _is_probably_noise(ln):
            continue
        out.append(ln)
    return out


# ---------------------------------------------------------------------
# 🔹 Nueva función: parse_filename_metadata
# ---------------------------------------------------------------------
def parse_filename_metadata(filename: str) -> dict:
    """
    Parsea nombres con formato:
      EMPRESA-BANCO-[EXTRAS...]-PERIODO.pdf
    Donde:
      - EMPRESA, BANCO y PERIODO son obligatorios
      - Los EXTRAS (nro cuenta, tipo, etc.) son opcionales
      - PERIODO puede ser: MES, AÑO, MES+AÑO o combinaciones (SEP+OCT+NOV2025, ENE-JUNIO2025)
    """

    name = Path(filename).stem.upper().replace("_", "-").replace(" ", "-")
    parts = [p for p in name.split("-") if p]
    if len(parts) < 3:
        return {"empresa": "", "banco": "", "extras": [], "periodo": ""}

    banks = [
        "BBVA", "BPN", "CIUDAD", "CREDICOOP", "GALICIA", "HIPOTECARIO", "HSBC",
        "ICBC", "ITAU", "MACRO", "MERCADOPAGO", "NACION", "PATAGONIA",
        "PROVINCIA", "RIOJA", "SANJUAN", "SANTANDER", "SUPERVIELLE", "COMAFI"
    ]

    banco_idx = None
    for i, part in enumerate(parts):
        if part in banks:
            banco_idx = i
            break

    if banco_idx is None or banco_idx >= len(parts) - 1:
        return {"empresa": "", "banco": "", "extras": [], "periodo": ""}

    empresa = "-".join(parts[:banco_idx])
    banco = parts[banco_idx]
    extras = parts[banco_idx + 1:-1] if len(parts) > banco_idx + 2 else []
    periodo_raw = parts[-1]

    periodo_clean = periodo_raw.replace("+", "/").replace("_", "/")
    periodo_clean = re.sub(r"[-/]{2,}", "/", periodo_clean)

    meses = [
        "ENE", "ENERO", "FEB", "FEBRERO", "MAR", "MARZO", "ABR", "ABRIL",
        "MAY", "MAYO", "JUN", "JUNIO", "JUL", "JULIO", "AGO", "AGOSTO",
        "SEP", "SEPT", "SEPTIEMBRE", "OCT", "OCTUBRE", "NOV", "NOVIEMBRE",
        "DIC", "DICIEMBRE"
    ]
    contiene_mes = any(m in periodo_clean for m in meses)
    contiene_año = re.search(r"\d{4}", periodo_clean)
    if not contiene_mes and not contiene_año and len(parts) > banco_idx + 1:
        periodo_clean = parts[-2] + "-" + parts[-1]

    return {
        "empresa": empresa.title(),
        "banco": banco.upper(),
        "extras": extras,
        "periodo": periodo_clean.title(),
    }


# ---------------------------------------------------------------------
def _detect_bank_from_filename(filename: str) -> str:
    if not filename:
        return ""
    name = Path(filename).stem.upper().replace("_", "-").replace(" ", "-")
    parts = [p for p in name.split("-") if p]
    banks = [
        "BBVA", "BPN", "CIUDAD", "CREDICOOP", "GALICIA", "HIPOTECARIO", "HSBC",
        "ICBC", "ITAU", "MACRO", "MERCADOPAGO", "NACION", "PATAGONIA",
        "PROVINCIA", "RIOJA", "SANJUAN", "SANTANDER", "SUPERVIELLE", "COMAFI"
    ]
    for part in parts:
        for bank in banks:
            if bank in part:
                return bank
    return ""


def _detect_bank_hint(blob_text: str, filename: str) -> str:
    hay_text = blob_text.upper()
    hay_file = filename.upper()
    hints = [
        ("ITAU", ["ITAU", "ITAÚ"]),
        ("RIOJA", ["BANCO RIOJA", "LA RIOJA"]),
        ("BPN", ["BANCO PROVINCIA NEUQUEN", "BPN"]),
        ("NACION", ["BANCO DE LA NACION", "BANCO NACION", "BNA"]),
        ("MACRO", ["BANCO MACRO", "MACRO"]),
        ("PATAGONIA", ["BANCO PATAGONIA", "PATAGONIA EBANK", "PATAGONIA"]),
        ("SANJUAN", ["BANCO SAN JUAN", "SAN JUAN"]),
        ("BBVA", ["BBVA", "FRANCES", "BANCO FRANCES"]),
        ("GALICIA", ["BANCO GALICIA", "OFFICE BANKING GALICIA"]),
        ("SUPERVIELLE", ["SUPERVIELLE", "BANCO SUPERVIELLE"]),
        ("HIPOTECARIO", ["BANCO HIPOTECARIO", "HIPOTECARIO"]),
        ("ICBC", ["ICBC", "INDUSTRIAL AND COMMERCIAL BANK OF CHINA"]),
        ("HSBC", ["HSBC", "HSBC ARGENTINA"]),
        ("COMAFI", ["BANCO COMAFI", "COMAFI"]),
        ("CREDICOOP", ["BANCO CREDICOOP", "CREDICOOP"]),
        ("PROVINCIA", ["BANCO PROVINCIA", "BAPRO", "BANCO DE LA PROVINCIA"]),
        ("MERCADOPAGO", ["MERCADO PAGO", "MERCADOPAGO"]),
    ]
    for code, keys in hints:
        for k in keys:
            if k in hay_file:
                return code
    for code, keys in hints:
        for k in keys:
            if k in hay_text:
                return code
    return ""


def _is_image_based_pdf(pdf_path: str, sample_pages: int = 2) -> bool:
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            total_chars = 0
            pages_to_check = min(sample_pages, len(pdf.pages))
            for i in range(pages_to_check):
                text = pdf.pages[i].extract_text() or ""
                total_chars += len(text.strip())
            threshold = 100
            is_image = total_chars < threshold
            logger.info(f"Detección PDF tipo: {total_chars} chars en {pages_to_check} páginas → {'IMAGEN' if is_image else 'TEXTO'}")
            return is_image
    except Exception as e:
        logger.warning(f"Error detectando tipo de PDF: {e}. Asumiendo texto nativo.")
        return False


# ---------------------------------------------------------------------
class UniversalExtractor:
    def __init__(self, ocr_if_image: bool = True, max_ocr_pages: int = 100):
        self.ocr_if_image = ocr_if_image
        self.max_ocr_pages = max_ocr_pages
        self.reader = PDFReader()

    def extract_from_pdf(self, pdf_path: str, filename_hint: str = "") -> Dict[str, Any]:
        logger.info(f"📄 Iniciando extracción: {pdf_path}")
        raw_data, text_raw = self.reader.extract_all(pdf_path)
        if isinstance(text_raw, list):
            text_lines_raw = text_raw
        else:
            text_lines_raw = [ln for ln in (text_raw or "").splitlines()]

        text_lines_clean = _preclean_lines(text_lines_raw)
        pages_count = raw_data.get('pages_count', 0) if isinstance(raw_data, dict) else 0

        # 🔹 Extraer metadata PRIMERO desde filename
        meta = parse_filename_metadata(filename_hint)
        logger.info(f"📋 Metadata extraída desde filename: {meta}")

        bank_hint = meta.get("banco") or _detect_bank_from_filename(filename_hint) or _detect_bank_hint("\n".join(text_lines_raw[:250]), filename_hint) or "GENÉRICO"
        logger.info(f"🏦 Banco detectado: {bank_hint}")

        skip_camelot = False
        if bank_hint in FORCE_OCR_BANKS or _is_image_based_pdf(pdf_path):
            skip_camelot = True
            logger.info(f"⭐️ Saltando Camelot (OCR o imagen-based)")

        camelot_tables = []
        if not skip_camelot:
            try:
                logger.info(f"📊 Ejecutando Camelot (máx {CAMELOT_MAX_PAGES} páginas)...")
                camelot_tables = extract_tables_with_camelot(pdf_path, max_pages=CAMELOT_MAX_PAGES) or []
            except Exception as e:
                logger.warning(f"⚠️ Camelot falló: {e}")
                camelot_tables = []
        tables = unify_camelot_tables(camelot_tables) if camelot_tables else []

        used_ocr = False
        should_use_ocr = False
        if self.ocr_if_image and (bank_hint in FORCE_OCR_BANKS or not text_lines_clean or len(text_lines_clean) < 5):
            should_use_ocr = True

        if should_use_ocr:
            try:
                ocr_text = ocr_extract_pages(pdf_path, max_pages=self.max_ocr_pages)
                if ocr_text:
                    used_ocr = True
                    if isinstance(ocr_text, list):
                        ocr_lines_raw = []
                        for item in ocr_text:
                            if isinstance(item, str):
                                ocr_lines_raw.extend(item.splitlines())
                        text_lines_raw.extend(ocr_lines_raw)
                        text_lines_clean = _preclean_lines(text_lines_raw)
            except Exception as e:
                logger.error(f"OCR falló: {e}")

        try:
            from parser_factory import get_parser
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from parser_factory import get_parser
        try:
            parser = get_parser(bank_hint)
            if parser:
                logger.info(f"🔄 Ejecutando parser para {bank_hint}...")
                df = parser.parse(text_lines_clean)
                
                # 🔹 FORZAR columnas de metadata desde filename (NUNCA del PDF)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    # Convertir fecha a formato dd/mm/yyyy SIN hora
                    if "fecha" in df.columns:
                        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
                        df["fecha"] = df["fecha"].dt.strftime("%d/%m/%Y").fillna("")
                    
                    # Forzar metadata desde filename
                    df["empresa"] = meta.get("empresa", "")
                    df["banco"] = meta.get("banco", bank_hint)
                    df["periodo"] = meta.get("periodo", "")
                    df["archivo"] = Path(filename_hint).name
                    
                    # Moneda default
                    if "moneda" not in df.columns or df["moneda"].isna().all():
                        df["moneda"] = "ARS"

                    # 🔹 Orden final de columnas
                    ordered_cols = [
                        "fecha", "mes", "año", "periodo", "detalle", "referencia",
                        "debito", "credito", "saldo", "moneda", "empresa", "banco", "archivo"
                    ]
                    for col in ordered_cols:
                        if col not in df.columns:
                            df[col] = ""
                    df = df[ordered_cols]
                    tables = [df]

        except Exception as e:
            logger.error(f"Error ejecutando parser {bank_hint}: {e}", exc_info=True)

        result = {
            "text_lines": text_lines_clean,
            "tables": tables,
            "bank_hint": bank_hint,
            "metadata": meta,
            "method": {"ocr": used_ocr},
            "pages_count": pages_count,
        }

        logger.info(f"✅ Extracción completa ({len(text_lines_clean)} líneas, {len(tables)} tablas)")
        return result