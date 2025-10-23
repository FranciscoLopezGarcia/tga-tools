# -*- coding: utf-8 -*-
import re
import pandas as pd
from parsers.base_parser import BaseParser

class CredicoopParser(BaseParser):
    """
    Parser para Banco Credicoop.
    Estructura muy similar al Supervielle, pero con una columna COMBTE (referencia)
    y bloques de texto adicionales que deben filtrarse.
    """

    BANK_NAME = "CREDICOOP"

    # ---------- patrones ----------
    _LINE_PATTERN = re.compile(
        r"(?P<fecha>\d{2}/\d{2}/\d{2,4})\s+"
        r"(?P<referencia>\d+)?\s*"
        r"(?P<detalle>[A-Za-zÁÉÍÓÚÑÜáéíóúñü0-9\.\-\(\)/%:,°\s]+?)\s+"
        r"(?P<debito>-?\d{1,3}(?:\.\d{3})*,\d{2})?\s*"
        r"(?P<credito>-?\d{1,3}(?:\.\d{3})*,\d{2})?\s*"
        r"(?P<saldo>-?\d{1,3}(?:\.\d{3})*,\d{2})?$"
    )

    _SKIP_PATTERNS = [
        re.compile(p, re.I)
        for p in [
            "PÁGINA", "TOTAL", "TOTALES", "IMPUESTO LEY",
            "DEBITOS AUTOMATICOS", "TRANSFERENCIAS PESOS",
            "CONTINUA EN PAGINA", "VIENE DE PAGINA",
            "USTED PUEDE", "MOVIMIENTOS DE CUENTA",
        ]
    ]

    # ---------- helpers ----------
    @staticmethod
    def _to_amount(s):
        if not s or not isinstance(s, str):
            return 0.0
        s = s.replace(".", "").replace(",", ".").replace("$", "").strip()
        try:
            return float(s)
        except:
            return 0.0

    @staticmethod
    def _is_skip(line: str) -> bool:
        if not line.strip():
            return True
        for pat in CredicoopParser._SKIP_PATTERNS:
            if pat.search(line):
                return True
        return False

    # ---------- método principal ----------
    def parse(self, raw_data, filename="") -> pd.DataFrame:
        # Determinar tipo de entrada
        if isinstance(raw_data, list):
            lines = [ln for ln in raw_data if isinstance(ln, str)]
        elif isinstance(raw_data, str):
            lines = raw_data.splitlines()
        else:
            return pd.DataFrame(columns=self.REQUIRED_COLUMNS)

        rows = []
        for ln in lines:
            ln = ln.strip()
            if self._is_skip(ln):
                continue

            # detectar límites de tabla
            if "SALDO ANTERIOR" in ln or "SALDO AL" in ln:
                m_saldo = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2})", ln)
                if m_saldo:
                    rows.append({
                        "fecha": "",
                        "detalle": "SALDO ANTERIOR" if "ANTERIOR" in ln else "SALDO FINAL",
                        "referencia": "",
                        "debito": 0.0,
                        "credito": 0.0,
                        "saldo": self._to_amount(m_saldo.group(1))
                    })
                continue

            m = self._LINE_PATTERN.search(ln)
            if not m:
                continue

            g = m.groupdict()
            fecha = self.normalize_date(g.get("fecha", ""))
            ref = (g.get("referencia") or "").strip()
            detalle = (g.get("detalle") or "").strip()
            deb = self._to_amount(g.get("debito"))
            cred = self._to_amount(g.get("credito"))
            saldo = self._to_amount(g.get("saldo"))

            # filtrar líneas donde todo está vacío o sin número
            if not fecha or not detalle:
                continue

            rows.append({
                "fecha": fecha,
                "detalle": detalle[:200],
                "referencia": ref,
                "debito": deb,
                "credito": cred,
                "saldo": saldo
            })

        df = pd.DataFrame(rows, columns=self.REQUIRED_COLUMNS)
        return self.finalize(df)
