# -*- coding: utf-8 -*-
"""
Galicia Cleaner v1.0
--------------------
Limpieza básica del DataFrame ya segmentado.
- No altera la lógica del parser
- Estandariza importes, fechas y textos
"""

import re
import logging
import pandas as pd

logger = logging.getLogger(__name__)

AMOUNT_RE = re.compile(r"-?\d{1,3}(?:[ .]\d{3})*,\d{2}")
DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{2,4}\b")

def _clean_amount(val: str) -> float:
    """Convierte string tipo '1.234.567,89' o '- 3 000,00' a float (-3000.00)"""
    if not val or not isinstance(val, str):
        return None
    s = val.strip().replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def _clean_date(val: str):
    """Devuelve fecha como datetime.date (o string limpio si falla)"""
    if not val or not isinstance(val, str):
        return None
    m = DATE_RE.search(val)
    if not m:
        return None
    try:
        return pd.to_datetime(m.group(), dayfirst=True, errors="coerce").date()
    except Exception:
        return val

def clean_galicia_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recibe el DataFrame del parser y devuelve versión limpia
    sin alterar estructura lógica.
    """
    logger.info("🧽 Iniciando limpieza Galicia...")

    df = df.copy()

    # --- Normalización básica ---
    for col in ["detalle", "debito", "credito", "saldo"]:
        df[col] = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})

    # --- Limpieza de texto redundante ---
    df["detalle"] = (
        df["detalle"]
        .str.replace(r"\bSALDO( ANTERIOR| ACTUAL)?\b", "", flags=re.I)
        .str.replace(r"PÁGINA \d+", "", flags=re.I)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # --- Parseo de fechas ---
    df["fecha"] = df["fecha"].apply(_clean_date)

    # --- Conversión de importes ---
    for col in ["debito", "credito", "saldo"]:
        df[col] = df[col].apply(_clean_amount)

    # --- Eliminación de filas vacías o ruido puro ---
    df = df[
        df[["fecha", "detalle", "debito", "credito", "saldo"]]
        .apply(lambda r: any(pd.notnull(x) and str(x).strip() != "" for x in r), axis=1)
    ].reset_index(drop=True)

    # --- Orden lógico opcional (solo si hay fechas válidas) ---
    if df["fecha"].notnull().any():
        df = df.sort_values(by=["fecha"]).reset_index(drop=True)

    # --- Log resumen ---
    logger.info(
        f"✅ Limpieza completada: {len(df)} filas finales | "
        f"{df['debito'].notnull().sum()} débitos | {df['credito'].notnull().sum()} créditos"
    )

    return df
