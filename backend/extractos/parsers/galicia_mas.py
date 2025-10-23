import re
import pandas as pd
from parsers.base_parser import BaseParser

class GaliciaMasParser(BaseParser):
    BANK_NAME = "GALICIA MAS"
    DETECTION_KEYWORDS = ["GALICIA MAS", "DETALLE DE OPERACIONES"]

    _MONTHS = {
        "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
        "JUL": "07", "AGO": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12"
    }

    # montos: con coma decimal, máximo 15 caracteres
    _AMOUNT_RE = re.compile(r"(-?\d{1,3}(?:\.\d{3})*,\d{2})")

    def _parse_date(self, text):
        """Busca una fecha tipo '06-MAR' o '6/MAR'."""
        m = re.search(r"(\d{1,2})[-/](ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)", text, re.I)
        if not m:
            return None
        d, mth = m.groups()
        return f"{d.zfill(2)}/{self._MONTHS[mth[:3].upper()]}/2025"

    def _to_float(self, s):
        s = s.strip().replace(".", "").replace(",", ".").replace("$", "")
        try:
            return float(s)
        except ValueError:
            return 0.0

    def parse(self, raw_data, filename=""):
        if isinstance(raw_data, str):
            lines = raw_data.splitlines()
        else:
            lines = [str(x) for x in raw_data if str(x).strip()]
        lines = [ln.strip() for ln in lines if ln.strip()]

        rows = []
        buffer = []
        last_date = None

        for ln in lines:
            date = self._parse_date(ln)
            if date:
                last_date = date

            amts = self._AMOUNT_RE.findall(ln)
            # ignorar si no hay montos válidos
            if not amts:
                buffer.append(ln)
                continue

            # hay montos → cerramos bloque
            detalle = " ".join(buffer).strip()
            buffer = []

            # montos válidos
            vals = [self._to_float(a) for a in amts]
            deb, cred, saldo = 0.0, 0.0, 0.0
            if len(vals) == 3:
                deb, cred, saldo = vals
            elif len(vals) == 2:
                cred, saldo = vals
            elif len(vals) == 1:
                saldo = vals[0]

            rows.append({
                "fecha": last_date or "",
                "detalle": detalle[:250],
                "referencia": "",
                "debito": deb,
                "credito": cred,
                "saldo": saldo
            })

        # agregar último bloque si quedó algo
        if buffer:
            rows.append({
                "fecha": last_date or "",
                "detalle": " ".join(buffer).strip(),
                "referencia": "",
                "debito": 0.0,
                "credito": 0.0,
                "saldo": 0.0
            })

        df = pd.DataFrame(rows, columns=self.REQUIRED_COLUMNS)
        return self.finalize(df)
