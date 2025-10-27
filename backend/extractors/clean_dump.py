# backend/extractors/clean_dump.py
import re
from typing import Dict, List, Any


EXCLUDE_KEYWORDS_LC = set([
    # ruido genérico muy común en resúmenes bancarios
    "estimado cliente", "detalle de titulares", "detalle de las cuentas",
    "movimientos pendientes", "saldo del periodo anterior", "saldo al cierre",
    "situacion impositiva", "responsable inscripto", "ingresos brutos",
    "pagina", "hoja", "cbu", "cuit", "moneda", "tipo", "número", "operador:",
    "empresa:", "periodo del", "frecuencia", "emitido el",
])

# Mantener líneas que tengan potencial de información transaccional
KEEP_IF_REGEX = re.compile(
    r"(\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b)|"         # alguna fecha
    r"(\b\d{1,3}(?:\.\d{3})*,\d{2}-?\b)|"               # monto AR
    r"\b(saldo|anterior|final|al|actual|concepto|detalle|debito|credito)\b",
    re.IGNORECASE
)

def _should_exclude(line: str) -> bool:
    low = line.lower()
    if any(k in low for k in EXCLUDE_KEYWORDS_LC):
        # solo excluimos si la línea no contiene señales de valor (fecha/monto/etc.)
        if not KEEP_IF_REGEX.search(line):
            return True
    return False

def clean_lines(lines: List[str]) -> List[str]:
    if not lines:
        return []
    out, seen = [], set()
    for raw in lines:
        s = re.sub(r"\s+", " ", str(raw)).strip()
        if not s:
            continue
        if _should_exclude(s):
            continue
        # dedupe agresivo de líneas exactas
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out

def clean_tables(tables: List[Any]) -> List[Any]:
    """
    Limpieza leve de DataFrames (si vienen de Camelot/Plumber/OCR):
      - recortar whitespace
      - eliminar filas totalmente vacías
      - dedupe de filas idénticas
    Nota: mantener estructura; no borrar columnas.
    """
    import pandas as pd
    out = []
    for df in tables or []:
        if not hasattr(df, "columns"):
            continue
        try:
            cdf = df.copy()
            cdf = cdf.applymap(lambda x: str(x).strip() if x is not None else "")
            # borrar filas sin contenido
            cdf = cdf[cdf.apply(lambda r: any(str(x).strip() for x in r), axis=1)]
            # dedupe
            cdf = cdf.drop_duplicates()
            out.append(cdf.reset_index(drop=True))
        except Exception:
            out.append(df)
    return out

def clean_dump(dump: Dict[str, Any]) -> Dict[str, Any]:
    """
    dump esperado:
    {
      "tables": [pd.DataFrame, ...],
      "text_lines": [str, ...],
      "ocr_lines": [str, ...],
      "meta": {...}
    }
    """
    if not isinstance(dump, dict):
        return {"tables": [], "text_lines": [], "ocr_lines": [], "meta": {}}

    tables = clean_tables(dump.get("tables") or [])
    text_lines = clean_lines(dump.get("text_lines") or [])
    ocr_lines = clean_lines(dump.get("ocr_lines") or [])

    return {
        "tables": tables,
        "text_lines": text_lines,
        "ocr_lines": ocr_lines,
        "meta": dump.get("meta", {}),
    }
