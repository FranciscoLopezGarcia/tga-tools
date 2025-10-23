# -*- coding: utf-8 -*-
import logging
import re
from typing import Any, Dict, List, Optional

import pandas as pd

from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# Regex suaves (no agresivos) para captar filas tipo: fecha + detalle + [deb] [cred] [saldo]
_DATE = r"(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"
_AMT = r"-?\$?\s?\d{1,3}(?:[\.\s]\d{3})*(?:,\d{2})"
_LINE = re.compile(
    rf"(?P<fecha>{_DATE})\s+(?P<detalle>.+?)\s+(?P<deb>{_AMT})?\s+(?P<cred>{_AMT})?\s+(?P<saldo>{_AMT})$",
    re.IGNORECASE
)

_SALDO_ANT_PAT = re.compile(r"\bSALDO\s+(DEL\s+PER[IÍ]ODO\s+ANTERIOR|ANTERIOR|ULTIMO\s+EXTRACTO)\b", re.I)
_SALDO_FIN_PAT = re.compile(r"\bSALDO\s+(AL|FINAL|DEL\s+PER[IÍ]ODO\s+ACTUAL|ACTUAL)\b", re.I)
_AMT_STRICT = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}$")

def _to_amount(s: Optional[str]) -> float:
    if not s:
        return 0.0
    t = str(s).strip().replace("$", "").replace(" ", "")
    neg = t.startswith("-") or t.endswith("-")
    t = t.replace("-", "").replace(".", "").replace(",", ".")
    try:
        v = float(t)
        return -v if neg else v
    except Exception:
        return 0.0

class GenericParser(BaseParser):
    """
    Fallback genérico:
      - Acepta texto y/o tablas.
      - Intenta extraer movimientos básicos con regex amplia.
      - Agrega filas para SALDO ANTERIOR / FINAL si los detecta por texto.
    """
    BANK_NAME = "GENERIC"
    PREFER_TABLES = True

    def detect(self, text: str, filename: str = "") -> bool:
        return True  # siempre disponible como fallback

    def parse(self, raw_data: Any, filename: str = "") -> pd.DataFrame:
        lines: List[str] = []
        tables: List[pd.DataFrame] = []

        if isinstance(raw_data, list):
            for x in raw_data:
                if isinstance(x, pd.DataFrame):
                    tables.append(x)
                elif isinstance(x, str):
                    if x.strip():
                        lines.append(x.strip())
        elif isinstance(raw_data, pd.DataFrame):
            tables = [raw_data]
        elif isinstance(raw_data, str):
            lines = [ln.strip() for ln in raw_data.splitlines() if ln.strip()]

        rows: List[Dict[str, Any]] = []

        # 1) Tablas: intentar columnas habituales (fecha, detalle, deb/cred/saldo)
        for df in tables:
            try:
                cols = [c.lower() for c in df.columns.astype(str)]
                # heurística simple
                idx_fecha = self._find_col(cols, ["fecha", "fec", "date"])
                idx_det   = self._find_col(cols, ["concepto", "detalle", "descripcion", "movimiento"])
                idx_deb   = self._find_col(cols, ["debito", "debitos", "debe", "egreso", "cargo"])
                idx_cred  = self._find_col(cols, ["credito", "creditos", "haber", "ingreso", "abono", "deposito"])
                idx_saldo = self._find_col(cols, ["saldo", "balance", "total", "saldo actual", "saldo final"])

                for _, r in df.iterrows():
                    fecha = str(r.iloc[idx_fecha]).strip() if idx_fecha is not None else ""
                    detalle = str(r.iloc[idx_det]).strip() if idx_det is not None else ""
                    deb = _to_amount(r.iloc[idx_deb]) if idx_deb is not None else 0.0
                    cred = _to_amount(r.iloc[idx_cred]) if idx_cred is not None else 0.0
                    saldo = _to_amount(r.iloc[idx_saldo]) if idx_saldo is not None else 0.0

                    if not fecha and not detalle and (deb == 0 and cred == 0 and saldo == 0):
                        continue

                    rows.append({
                        "fecha": self.normalize_date(fecha),
                        "detalle": detalle[:200],
                        "referencia": "",
                        "debito": max(0.0, deb),
                        "credito": max(0.0, cred),
                        "saldo": saldo
                    })
            except Exception as e:
                logger.debug(f"[GENERIC] tabla ignorada: {e}")

        # 2) Texto: regex amplia para captar líneas tipo "fecha ... montos"
        saldo_ant: Optional[float] = None
        saldo_fin: Optional[float] = None

        for ln in lines:
            # saldos
            if _SALDO_ANT_PAT.search(ln):
                m = _AMT_STRICT.search(ln)
                if m:
                    saldo_ant = _to_amount(m.group(0))
                continue
            if _SALDO_FIN_PAT.search(ln):
                m = _AMT_STRICT.search(ln)
                if m:
                    saldo_fin = _to_amount(m.group(0))
                continue

            m = _LINE.search(ln)
            if not m:
                continue
            g = m.groupdict()
            fecha = self.normalize_date(g.get("fecha") or "")
            detalle = (g.get("detalle") or "").strip()
            deb = _to_amount(g.get("deb"))
            cred = _to_amount(g.get("cred"))
            saldo = _to_amount(g.get("saldo"))

            if deb < 0: deb = -deb
            if cred < 0: cred = -cred

            rows.append({
                "fecha": fecha,
                "detalle": detalle[:200],
                "referencia": "",
                "debito": deb,
                "credito": cred,
                "saldo": saldo
            })

        out = pd.DataFrame(rows, columns=self.REQUIRED_COLUMNS)

        # Agregar filas de saldo si existen (sin fecha)
        extra = []
        if saldo_ant is not None:
            extra.append({"fecha": "", "detalle": "SALDO ANTERIOR", "referencia": "", "debito": 0.0, "credito": 0.0, "saldo": saldo_ant})
        if saldo_fin is not None:
            extra.append({"fecha": "", "detalle": "SALDO FINAL", "referencia": "", "debito": 0.0, "credito": 0.0, "saldo": saldo_fin})
        if extra:
            out = pd.concat([pd.DataFrame(extra, columns=self.REQUIRED_COLUMNS), out], ignore_index=True)

        return self.finalize(out)

    # ---------- helpers ----------
    @staticmethod
    def _find_col(cols: List[str], keys: List[str]) -> Optional[int]:
        for i, c in enumerate(cols):
            for k in keys:
                if k in c:
                    return i
        return None
