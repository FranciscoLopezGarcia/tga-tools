# -*- coding: utf-8 -*-
"""
Galicia Parser v4
-----------------
- Fuerza preprocessor (aunque reciba lista OCR)
- Segmenta sin “inventar”: fecha / detalle / debito / credito / saldo
- Mantiene logs de conteo y deja debugs del preprocessor en /app/debug_galicia
"""

import os
import re
import logging
import pandas as pd
from typing import Union, List
from .galicia_preprocessor import preprocess_galicia_ocr


logger = logging.getLogger("galicia_parser")
logger.setLevel(logging.INFO)

DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{2}\b")
AMOUNT_RE = re.compile(r"-?\d{1,3}(?:[ .]\d{3})*,\d{2}")

class GaliciaParser:
    BANK_NAME = "GALICIA"
    DETECTION_KEYWORDS = ["GALICIA"]

    def detect(self, text: str, filename: str = "") -> bool:
        return "GALICIA" in f"{text} {filename}".upper()

    def parse(self, raw_data: Union[str, List[str]], filename: str = "") -> pd.DataFrame:
        """
        Acepta path al PDF o texto OCR (lista[str]).
        Reorganiza fecha / detalle / debito|credito / saldo.
        """
        # ----- Entrada → forzar preprocessor -----
        if isinstance(raw_data, list):
            logger.info("⚙️ GaliciaParser: recibido OCR como lista. Forzando paso por preprocessor.")
            joined_text = "\n".join(x for x in raw_data if isinstance(x, str))
            data = preprocess_galicia_ocr(joined_text)
        else:
            if isinstance(raw_data, str) and os.path.exists(raw_data):
                logger.info("🔎 Ejecutando preprocess_galicia_ocr() desde path...")
                data = preprocess_galicia_ocr(raw_data)
            elif filename and os.path.exists(filename):
                logger.info("🔎 Ejecutando preprocess_galicia_ocr() desde filename...")
                data = preprocess_galicia_ocr(filename)
            else:
                raise ValueError("No se recibió path válido para GaliciaParser.")

        # Convertir salida del preprocessor a lista de líneas
        if isinstance(data, list):
            lines = [str(l).strip() for l in data if str(l).strip()]
        else:
            lines = [s.strip() for s in str(data).split("\n") if s.strip()]

        # ----- Segmentación -----
        parsed_rows = []
        segmented, failed = 0, 0

        for line in lines:
            fecha = ""
            detalle = line
            debito = ""
            credito = ""
            saldo = ""

            # Fecha (primera que aparezca)
            m_date = DATE_RE.search(line)
            if m_date:
                fecha = m_date.group()
                detalle = line[m_date.end():].strip()

            # Importes que haya en la línea (sin interpretar, solo ubicar)
            amounts = AMOUNT_RE.findall(line)

            if len(amounts) >= 2:
                # Heurística: primer importe = mov (débito o crédito), último = saldo
                mov, saldo_val = amounts[0], amounts[-1]
                saldo = saldo_val
                if mov.startswith("-"):
                    debito = mov
                else:
                    credito = mov
            elif len(amounts) == 1:
                val = amounts[0]
                # Si la línea sugiere que es un saldo aislado
                if "SALDO" in line.upper() and not m_date:
                    saldo = val
                elif val.startswith("-"):
                    debito = val
                else:
                    credito = val

            # Limpieza del detalle: quitar montos (no borrar texto)
            detalle = AMOUNT_RE.sub("", detalle).strip()

            if fecha or debito or credito or saldo:
                segmented += 1
            else:
                failed += 1

            parsed_rows.append({
                "fecha": fecha,
                "detalle": detalle,
                "debito": debito,
                "credito": credito,
                "saldo": saldo
            })

        logger.info(f"[GALICIA v4] Filas totales: {len(lines)} | Segmentadas: {segmented} | Sin parsear: {failed}")

        df = pd.DataFrame(parsed_rows, columns=["fecha", "detalle", "debito", "credito", "saldo"])
        return df
