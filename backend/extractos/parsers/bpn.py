import pandas as pd
import logging
import re
import unicodedata
from .base_parser import BaseParser

logger = logging.getLogger(__name__)

def _norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip().upper()

class BPNParser(BaseParser):
    BANK_NAME = "BPN"
    PREFER_TABLES = True

    DETECTION_KEYWORDS = [
        "BPN", "BANCO PROVINCIA NEUQUEN", "BANCO PROVINCIA DEL NEUQUEN", "BPN.COM.AR"
    ]

    def detect(self, text: str, filename: str = "") -> bool:
        haystack = _norm(f"{text} {filename}")
        return any(k in haystack for k in self.DETECTION_KEYWORDS)

    def parse(self, raw_data, filename="") -> pd.DataFrame:
        logger.info(f"Procesando {self.BANK_NAME} - {filename}")

        # Si viene lista de DataFrames (Camelot/pdfplumber tablas)
        if isinstance(raw_data, list) and len(raw_data) > 0 and hasattr(raw_data[0], "columns"):
            dfs = []
            for t in raw_data:
                try:
                    dfs.append(self._parse_dataframe(t))
                except Exception:
                    continue
            out = pd.concat(
                [d for d in dfs if d is not None and len(d) > 0],
                ignore_index=True
            ) if dfs else pd.DataFrame()
            return self.finalize(out) if not out.empty else self.finalize(pd.DataFrame(columns=self.REQUIRED_COLUMNS))

        # Si es texto plano
        if isinstance(raw_data, str):
            return self._parse_text_lines(raw_data.splitlines())
        elif isinstance(raw_data, list) and all(isinstance(x, str) for x in raw_data):
            return self._parse_text_lines(raw_data)

        return pd.DataFrame(columns=self.REQUIRED_COLUMNS)

    # ---------- Helpers de tablas ----------
    def _headers_from_first_row(self, df: pd.DataFrame) -> pd.DataFrame:
        if all(isinstance(c, int) for c in df.columns):
            first = df.iloc[0].astype(str).tolist()
            norm_first = [_norm(x) for x in first]
            if any(x in " ".join(norm_first) for x in ["FECHA", "DEBITO", "CREDITO", "SALDO", "DESCRIPCION", "COMPROBANTE"]):
                df = df.copy()
                df.columns = [
                    str(c) if str(c).strip() != "" else f"COL{idx}"
                    for idx, c in enumerate(first)
                ]
                df = df.iloc[1:].reset_index(drop=True)
        return df

    def _parse_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=self.REQUIRED_COLUMNS)

        df = self._headers_from_first_row(df)
        colmap = {c: _norm(c) for c in df.columns}
        inv = {v: c for c, v in colmap.items()}

        def pick(*cands):
            for c in cands:
                if c in inv:
                    return inv[c]
            return None

        c_fecha = pick("FECHA")
        c_desc = pick("DESCRIPCION")
        c_debito = pick("DEBITO")
        c_credit = pick("CREDITO")
        c_saldo = pick("SALDO")

        cols = list(df.columns)
        if not all([c_fecha, c_desc, c_debito, c_credit, c_saldo]) and len(cols) >= 5:
            c_fecha = c_fecha or cols[0]
            c_desc = c_desc or cols[1]
            c_debito = c_debito or cols[-3]
            c_credit = c_credit or cols[-2]
            c_saldo = c_saldo or cols[-1]

        out = pd.DataFrame()
        out["fecha"] = df[c_fecha].astype(str) if c_fecha in df.columns else ""
        out["detalle"] = df[c_desc].astype(str) if c_desc in df.columns else ""
        out["debito"] = df[c_debito].apply(self._to_amount) if c_debito in df.columns else 0.0
        out["credito"] = df[c_credit].apply(self._to_amount) if c_credit in df.columns else 0.0
        out["saldo"] = df[c_saldo].apply(self._to_amount) if c_saldo in df.columns else 0.0
        out["referencia"] = ""
        return out

    # ---------- Regex por texto ----------
    def _parse_text_lines(self, lines: list) -> pd.DataFrame:
        rows = []
        pat = re.compile(
            r'^\s*(?P<fecha>\d{1,2}/\d{1,2}/\d{4})\s+(?P<detalle>[A-ZÁÉÍÓÚÑ0-9\s\.\-\&]+?)\s+(?P<val1>\d[\d\.\,]*)\s+(?P<val2>\d[\d\.\,]*)\s*$',
            re.IGNORECASE
        )

        for line in lines:
            s = line.strip()
            if not s:
                continue
            S = s.upper()
            if any(k in S for k in ["FECHA DESCRIPCION", "TOTAL", "SALDO ANTERIOR", "PAGINA", "FOLIO", "===="]):
                continue

            m = pat.match(s)
            if not m:
                continue

            g = m.groupdict()
            detalle = g["detalle"].strip()
            val1 = self._to_amount(g["val1"])
            val2 = self._to_amount(g["val2"])

            if any(w in detalle.upper() for w in ["ACRED", "TRANSF", "DEPOSITO", "INGRESO"]):
                debito = 0.0
                credito = val1
            else:
                debito = val1
                credito = 0.0

            rows.append({
                "fecha": self.normalize_date(g["fecha"]),
                "detalle": detalle,
                "referencia": "",
                "debito": debito,
                "credito": credito,
                "saldo": val2
            })

        return pd.DataFrame(rows)

    def _to_amount(self, val) -> float:
        """Convierte montos tipo '4.218,60' en float 4218.60"""
        if val is None or str(val).strip() == "":
            return 0.0
        s = str(val).strip().replace(".", "").replace(",", ".")
        try:
            return float(s)
        except Exception:
            return 0.0
