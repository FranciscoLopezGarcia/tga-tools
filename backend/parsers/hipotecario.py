import pandas as pd
import re
import logging
from .base_parser import BaseParser

logger = logging.getLogger(__name__)

class HipotecarioParser(BaseParser):
    BANK_NAME = "HIPOTECARIO"
    PREFER_TABLES = True

    DETECTION_KEYWORDS = [
        "BANCO HIPOTECARIO", "HIPOTECARIO S.A.", "RECONQUISTA 101", "BH"
    ]

    def detect(self, text: str, filename: str = "") -> bool:
        text_upper = text.upper()
        return any(k in text_upper for k in self.DETECTION_KEYWORDS)

    def parse(self, raw_data, filename="") -> pd.DataFrame:
        logger.info(f"Procesando {self.BANK_NAME} - {filename}")

        if isinstance(raw_data, list) and all(isinstance(x, str) for x in raw_data):
            return self._parse_text_lines(raw_data)
        elif isinstance(raw_data, str):
            return self._parse_text_lines(raw_data.splitlines())

        return pd.DataFrame(columns=self.REQUIRED_COLUMNS)

    # -----------------------------------------------------
    def _parse_text_lines(self, lines: list) -> pd.DataFrame:
        """
        Cada línea suele tener:
        FECHA DESCRIPCION SUC. REFERENCIA DEBITOS CREDITOS SALDO
        Ejemplo:
        02/01/2024 N/D - DB TRF TERCEROS OB BH - 30709159182 - YACOPINI SUD SA 16 1652 Comp. 285 19,502,812.00
        """
        pat = re.compile(
            r'(?P<fecha>\d{2}/\d{2}/\d{4})\s+(?P<detalle>.+?)\s+(?P<suc>\d{1,3})\s+(?P<ref>\d{1,5})\s+(?:Comp\.\s*\d+)?\s*(?P<debito>\d[\d\.\,]*)?\s*(?P<credito>\d[\d\.\,]*)?$',
            re.IGNORECASE
        )

        rows = []
        last_fecha = ""

        for line in lines:
            s = line.strip()
            if not s or "FECHA DESCRIPCION" in s.upper() or "SALDO FINAL" in s.upper():
                continue

            # A veces el detalle continúa en la siguiente línea (sin fecha)
            if not re.match(r"^\d{2}/\d{2}/\d{4}", s):
                # concatenar a la línea anterior si es descripción extendida
                if rows:
                    rows[-1]["detalle"] += " " + s
                continue

            m = pat.match(s)
            if not m:
                continue

            g = m.groupdict()
            last_fecha = g["fecha"] or last_fecha

            detalle = g.get("detalle", "").strip()
            deb = self._to_amount(g.get("debito"))
            cred = self._to_amount(g.get("credito"))

            # Heurística: si detalle empieza con "N/D" es débito, si empieza con "N/C" es crédito
            if detalle.startswith("N/D"):
                debito = deb if deb != 0 else 0.0
                credito = 0.0
            elif detalle.startswith("N/C"):
                credito = cred if cred != 0 else 0.0
                debito = 0.0
            else:
                # fallback: usar el campo no vacío
                if cred > 0 and deb == 0:
                    credito, debito = cred, 0.0
                elif deb > 0 and cred == 0:
                    debito, credito = deb, 0.0
                else:
                    debito, credito = 0.0, 0.0

            rows.append({
                "fecha": self.normalize_date(last_fecha),
                "detalle": detalle,
                "referencia": g.get("ref", ""),
                "debito": debito,
                "credito": credito,
                "saldo": 0.0,  # no se repite saldo por línea
            })

        return self.finalize(pd.DataFrame(rows))

    # -----------------------------------------------------
    def _to_amount(self, val) -> float:
        if not val:
            return 0.0
        s = str(val).replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0
