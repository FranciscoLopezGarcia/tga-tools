# parsers/strict_base.py
import re
from datetime import datetime
from typing import Tuple, Union
import logging
import pandas as pd
from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

DATE_PREFIX = re.compile(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?")

AMOUNT_ANY = re.compile(
    r"\(?-?\$?\s*\d{1,3}(?:[.\s]\d{3})*,\d{2}\)?-?"
)

HEADER_TOKENS = ("fecha", "concepto", "detalle", "debito", "débito", "credito", "crédito", "saldo")

class StrictBankParser(BaseParser):
    """
    Base utilitaria para parsers “estrictos” dirigidos por reglas hardcodeadas (sin JSON).
    Provee normalización de fechas/montos y helpers de filas/tablas/texto.
    """

    def _norm_date(self, raw: str) -> str:
        if not raw:
            return ""
        s = raw.strip().replace(".", "/").replace("-", "/")
        m = DATE_PREFIX.match(s)
        if not m:
            return raw.strip()
        d, mo, y = m.groups()
        y = int(y) if y else datetime.today().year
        if y < 100:
            y += 2000
        try:
            return datetime(int(y), int(mo), int(d)).strftime("%d/%m/%Y")
        except Exception:
            return raw.strip()

    def _to_amount(self, s: Union[str, float, int]) -> float:
        if s is None:
            return 0.0
        if isinstance(s, (int, float)):
            return float(s)
        t = str(s).strip()
        if not t:
            return 0.0
        neg = t.startswith("-") or t.endswith("-") or (t.startswith("(") and t.endswith(")"))
        t = t.replace("(", "").replace(")", "").replace("-", "")
        t = t.replace("$", "").replace(" ", "").replace("\u00a0", "")
        t = t.replace(".", "").replace(",", ".")
        try:
            v = float(t)
            return -v if neg else v
        except Exception:
            logger.debug("No se pudo parsear monto: %r", s)
            return 0.0

    def _split_year_month(self, fecha: str) -> Tuple[str, str]:
        if not fecha or len(fecha) < 8:
            return "", ""
        try:
            d = datetime.strptime(fecha, "%d/%m/%Y")
            return str(d.year), f"{d.month:02d}"
        except Exception:
            return "", ""

    def _looks_like_header(self, s: str) -> bool:
        low = (s or "").lower()
        return any(k in low for k in HEADER_TOKENS)

    def _finalize_rows(self, rows):
        df = pd.DataFrame(rows, columns=[
            "fecha", "mes", "año", "detalle", "referencia", "debito", "credito", "saldo"
        ])
        return self.finalize(df)
