# unificador.py
from __future__ import annotations
from typing import List, Dict, Optional, Tuple
import re
import pandas as pd

# Nombres de meses (para parsing y/o uso general)
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

# ------------------------------------------------------------
# Normalización de banco (robusta ante variantes y ruido OCR)
# ------------------------------------------------------------
def normalize_bank(bank_raw: Optional[str]) -> str:
    if not bank_raw:
        return "DESCONOCIDO"
    s = str(bank_raw).upper()
    # Limpieza básica y alias comunes
    s = re.sub(r"\s+", " ", s).strip()
    if "COMAFI" in s:
        return "COMAFI"
    if "ICBC" in s:
        return "ICBC"
    if "MACRO" in s:
        return "MACRO"
    if "GALICIA" in s:
        return "GALICIA"
    if "SANTANDER" in s:
        return "SANTANDER"
    if "BBVA" in s:
        return "BBVA"
    if "HSBC" in s:
        return "HSBC"
    return s

# -------------------------------------------------------------------
# Inferencia de periodo (año, mes) desde DF y/o líneas crudas (OCR)
# -------------------------------------------------------------------
def infer_period(df: pd.DataFrame, raw_lines: Optional[List[str]] = None) -> Tuple[Optional[int], Optional[int]]:
    """
    Intenta inferir (año, mes) con este orden:
    1) Si hay 'fecha' en DF: usa el min(fecha) válido para deducir año/mes.
    2) Busca patrones en raw_lines (OCR), p.ej. "JULIO - 2025", "Saldo al: 31/07/2025".
    3) Devuelve (None, None) si no se puede inferir.
    """
    # 1) Tomar de 'fecha' si existe
    if "fecha" in df.columns:
        # 🔹 CRÍTICO: Intentar parsear fecha si viene como string dd/mm/yyyy
        f = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True, format="%d/%m/%Y")
        if f.notna().any():
            first = f.min()
            return int(first.year), int(first.month)

    # 2) Raw lines
    if raw_lines:
        # A) "MES - YYYY"
        patron_mes_yyyy = re.compile(rf"\b({'|'.join(m.upper() for m in MESES)})\s*[-—]\s*(\d{{4}})\b", re.IGNORECASE)
        for line in raw_lines:
            m = patron_mes_yyyy.search(line)
            if m:
                mes_txt = m.group(1).strip().lower()
                anio = int(m.group(2))
                if mes_txt in MESES:
                    return anio, MESES.index(mes_txt) + 1

        # B) Fechas tipo dd/mm/yyyy (ej: "Saldo al: 31/07/2025")
        patron_fecha = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
        for line in raw_lines:
            m = patron_fecha.search(line)
            if m:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                y = 2000 + y if y < 100 else y
                # Validación mínima de mes
                if 1 <= mo <= 12:
                    return y, mo

    return None, None

# ------------------------------------------------------------
# Tipificación y columnas de orden
# ------------------------------------------------------------
def _coerce_period_cols(df: pd.DataFrame) -> pd.DataFrame:
    df["año"] = pd.to_numeric(df.get("año"), errors="coerce")
    df["mes"] = pd.to_numeric(df.get("mes"), errors="coerce")

    # 🔹 Si fecha viene como string dd/mm/yyyy, parsear correctamente
    if "fecha" in df.columns and (df["año"].isna().any() or df["mes"].isna().any()):
        f = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True, format="%d/%m/%Y")
        df.loc[df["año"].isna() & f.notna(), "año"] = f.dt.year
        df.loc[df["mes"].isna() & f.notna(), "mes"] = f.dt.month

    df["año"] = df["año"].astype("Int64")
    df["mes"] = df["mes"].astype("Int64")
    return df

def _build_period_and_order_date(df: pd.DataFrame) -> pd.DataFrame:
    # periodo = primer día del mes (para ordenar por mes aún si falta 'fecha')
    # 🔧 Rellenar NA en año/mes ANTES de convertir a Int64
    df["año"] = pd.to_numeric(df["año"], errors="coerce").fillna(2025)
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce").fillna(1)
    
    df["periodo_sort"] = pd.to_datetime(
        dict(
            year=df["año"].astype("int"),
            month=df["mes"].astype("int"),
            day=1,
        ),
        errors="coerce",
    )

    # 🔹 fecha_orden: parsear fecha correctamente si es string
    if "fecha" in df.columns:
        fecha_dt = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True, format="%d/%m/%Y")
    else:
        fecha_dt = pd.Series(pd.NaT, index=df.index)

    # fecha_orden = usa fecha si existe, sino periodo_sort
    df["fecha_orden"] = fecha_dt.where(fecha_dt.notna(), df["periodo_sort"])
    return df

# ------------------------------------------------------------
# CONSOLIDADO (una sola hoja)
# ------------------------------------------------------------
def consolidate(inputs: List[Dict], output_path: Optional[str] = None) -> pd.DataFrame:
    """
    Consolida dataframes de extractos bancarios.
    Orden final garantizado: banco → año → mes → fecha.
    Genera UNA sola hoja "Consolidado" si se pasa output_path.
    inputs: lista de dicts con al menos {"df": DataFrame, "meta": {...opcional...}}
            meta puede contener: bank, year, month, currency
    """
    items = []

    for item in inputs:
        df = item["df"].copy()
        meta = item.get("meta") or {}

        # Banco (meta/attrs o de columnas)
        bank = df.get("banco", pd.Series([""])).iloc[0] if "banco" in df.columns else ""
        if not bank:
            bank = meta.get("bank") or df.attrs.get("bank") or df.attrs.get("source", "")
        bank = normalize_bank(bank)

        # Periodo (meta o inferencia o de columnas)
        year = df.get("año", pd.Series([None])).iloc[0] if "año" in df.columns else None
        month = df.get("mes", pd.Series([None])).iloc[0] if "mes" in df.columns else None
        
        if not (year and month):
            year = meta.get("year")
            month = meta.get("month")
        
        if not (year and month):
            raw_lines = df.attrs.get("raw_lines")
            year, month = infer_period(df, raw_lines)

        # 🔹 Tipos y columnas numéricas
        # Si fecha viene como string dd/mm/yyyy, NO convertir a datetime para Excel
        # Solo validar que esté en formato correcto
        if "fecha" in df.columns:
            # Mantener como string, solo limpiar
            df["fecha"] = df["fecha"].astype(str).replace("NaT", "").replace("nan", "")

        for col in ("debito", "credito", "saldo"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Completar columnas de control
        df["banco"] = bank
        if "año" not in df.columns or df["año"].isna().all():
            df["año"] = year
        if "mes" not in df.columns or df["mes"].isna().all():
            df["mes"] = month
        if "moneda" not in df.columns:
            df["moneda"] = meta.get("currency", "ARS")

        df = _coerce_period_cols(df)
        df = _build_period_and_order_date(df)

        items.append(df)

    if not items:
        # Nada que consolidar
        empty = pd.DataFrame()
        if output_path:
            with pd.ExcelWriter(output_path, engine="openpyxl") as xw:
                empty.to_excel(xw, index=False, sheet_name="Consolidado")
        return empty

    df_all = pd.concat(items, ignore_index=True)
    # --- mantener orden interno del parser ---
    if "__seq" in df_all.columns:
        df_all = df_all.sort_values(
            ["banco", "año", "mes", "__seq"],
            kind="stable",
            na_position="last",
        )
    elif "__order" in df_all.columns:
        df_all = df_all.sort_values(
            ["banco", "año", "mes", "__order"],
            kind="stable",
            na_position="last",
        )


    # 🔹 CRÍTICO: Orden estable: banco → año → mes → fecha_orden
    # Esto garantiza que COMAFI-JUNIO vaya antes que COMAFI-JULIO
    df_all = df_all.sort_values(
        ["banco", "año", "mes", "fecha_orden"],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)

    # 🔹 Volver fecha a formato string dd/mm/yyyy para Excel
    if "fecha" in df_all.columns:
        df_all["fecha"] = df_all["fecha"].astype(str).replace("NaT", "").replace("nan", "")

    # Exporta SOLO una hoja "Consolidado"
    if output_path:
        out = df_all.drop(columns=["fecha_orden", "periodo_sort"], errors="ignore")
        with pd.ExcelWriter(output_path, engine="openpyxl") as xw:
            out.to_excel(xw, index=False, sheet_name="Consolidado")

    return df_all

# --- Camelot tables → list[pd.DataFrame] (helper esperado por UniversalExtractor) ---
def unify_camelot_tables(camelot_tables) -> list[pd.DataFrame]:
    """
    Recibe la lista que devuelve camelot.read_pdf(...) y devuelve
    una lista de DataFrames limpios (uno por tabla encontrada).
    Si ya vienen como DataFrames, los deja pasar.
    No toca tu consolidado ni agrega side-effects.
    """
    dfs: list[pd.DataFrame] = []
    if not camelot_tables:
        return dfs

    try:
        # Caso típico: objetos Camelot (cada item tiene .df)
        for tbl in camelot_tables:
            if hasattr(tbl, "df"):
                df = tbl.df.copy()
            else:
                # Por si por algún wrapper ya vienen como DataFrame
                df = pd.DataFrame(tbl).copy()

            # Limpiezas MUY suaves para evitar romper parsers específicos
            df.columns = [str(c).strip() for c in df.columns]
            # Quitar filas totalmente vacías
            df = df.dropna(how="all").reset_index(drop=True)
            dfs.append(df)
    except Exception:
        # Ante cualquier cosa rara, mejor devolver vacío que romper el arranque
        dfs = []

    return dfs