# -*- coding: utf-8 -*-

import pandas as pd
from pathlib import Path
from logger_config import setup_logger
from parser_tablas import procesar_pdf

logger = setup_logger("siradig")

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def procesar_pdfs():
    pdfs = list(INPUT_DIR.glob("*.pdf"))
    if not pdfs:
        logger.warning("⚠️ No se encontraron PDFs en input/")
        return

    for pdf_path in pdfs:
        logger.info(f"📄 Procesando {pdf_path.name}")
        output_xlsx = OUTPUT_DIR / f"{pdf_path.stem}.xlsx"

        try:
            # Procesar PDF con pdfplumber
            df_final = procesar_pdf(pdf_path)

            if not df_final.empty:
                # Guardar a Excel
                df_final.to_excel(output_xlsx, index=False, sheet_name="SIRADIG")
                logger.info(f"💾 Archivo Excel generado: {output_xlsx.name}")
            else:
                logger.warning(f"⚠️ No se generaron datos para {pdf_path.name}")

        except Exception as e:
            logger.error(f"❌ Error procesando {pdf_path.name}: {e}", exc_info=True)

    logger.info("🏁 Extracción completa de todos los PDFs.")