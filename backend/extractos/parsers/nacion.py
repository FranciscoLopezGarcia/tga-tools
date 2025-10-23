import re
import pandas as pd
from typing import List, Dict

class NacionParser:
    BANK_NAME = "NACION"
    DETECTION_KEYWORDS = ["NACION", "BANCO DE LA NACION", "BANCO NACION"]

    def detect(self, text: str, filename: str = "") -> bool:
        return any(k in f"{text} {filename}".upper() for k in self.DETECTION_KEYWORDS)

    def parse(self, lines: List[str], filename: str = "") -> pd.DataFrame:
        movimientos = self._parse_movimientos(lines)
        df = pd.DataFrame(movimientos)
        if df.empty:
            raise ValueError("No se detectaron movimientos válidos en el PDF de Nación.")
        return df

    # ---------------------------------------------------------

    def _parse_movimientos(self, lines: List[str]) -> List[Dict]:
        rows = []
        fecha_actual = None
        DATE_PATTERN = re.compile(r"\b(\d{2})/(\d{2})/(\d{2,4})\b")

        for raw in lines:
            line = raw.strip()
            if len(line) < 8:
                continue
            low = line.lower()

            # Filtrar basura, encabezados y totales no deseados
            if any(x in low for x in [
                "fecha concepto", "resumen de cuenta", "hoja:",
                "total imp", "total ley", "información sobre su cuenta",
                "transporte", "saldo anterior", "saldo final",
                "movimientos del período", "total grav", "total reg rec", "del mes de",
            ]):
                continue

            # Detectar fecha
            date_match = DATE_PATTERN.search(line)
            if date_match:
                d, m, y = date_match.groups()
                if len(y) == 2:
                    y = f"20{y}"
                fecha_actual = f"{d}/{m}/{y}"

            if not fecha_actual:
                continue

            # Detectar montos
            amounts_raw = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}-?", line)
            if not amounts_raw:
                continue

            importe_txt = amounts_raw[0]
            saldo_txt = amounts_raw[-1]
            importe = self._to_float(importe_txt)
            saldo = self._to_float(saldo_txt)

            # Detectar referencia
            ref_match = re.search(r"\b\d{3,10}\b", line)
            referencia = ref_match.group(0) if ref_match else ""

            # Detalle (entre fecha y primer monto)
            start_det = date_match.end() if date_match else 0
            end_det = line.find(importe_txt)
            detalle = line[start_det:end_det].strip()
            detalle = re.sub(r"\s+", " ", detalle)

            # Clasificación robusta
            tipo = self._clasificar(detalle)
            debito = credito = 0.0
            if tipo == "DEBITO":
                debito = abs(importe)
            elif tipo == "CREDITO":
                credito = abs(importe)
            else:
                debito = abs(importe) if importe_txt.endswith("-") else 0.0
                credito = abs(importe) if not importe_txt.endswith("-") else 0.0

            # Descartar filas sin texto real
            if len(detalle) < 5 or detalle == "$":
                continue

            rows.append({
                "fecha": fecha_actual,
                "detalle": detalle[:200],
                "referencia": referencia,
                "debito": debito,
                "credito": credito,
                "saldo": saldo,
            })

        # Insertar saldos
        saldo_ini = self._extract_saldo_inicial(lines)
        saldo_fin = self._extract_saldo_final(lines)
        if saldo_ini:
            rows.insert(0, {"fecha": "", "detalle": "SALDO ANTERIOR", "referencia": "", "debito": 0.0, "credito": 0.0, "saldo": saldo_ini})
        if saldo_fin:
            rows.append({"fecha": "", "detalle": "SALDO FINAL", "referencia": "", "debito": 0.0, "credito": 0.0, "saldo": saldo_fin})

        return rows

    # ---------------------------------------------------------

    def _to_float(self, txt: str) -> float:
        return float(txt.replace(".", "").replace(",", ".").replace("-", "")) if txt else 0.0

    def _extract_saldo_inicial(self, lines: List[str]) -> float:
        for l in lines[:25]:
            if "saldo" in l.lower() and "anterior" in l.lower():
                m = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", l)
                if m:
                    return self._to_float(m.group(0))
        return 0.0

    def _extract_saldo_final(self, lines: List[str]) -> float:
        for l in reversed(lines):
            if "saldo" in l.lower() and "final" in l.lower():
                m = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", l)
                if m:
                    return self._to_float(m.group(0))
        return 0.0

    def _clasificar(self, detalle: str) -> str:
        d = detalle.upper()

        # Créditos reales
        credit_kw = ["S/CRED", "CREDITO", "ACRED", "TRANSF", "DEPOSITO"]
        # Débitos reales
        debit_kw = [
            "S/DEB", "DEBITO", "DEB.", "COMISION", "RETENCION",
            "GRAVAMEN", "IMPUESTO", "IVA", "I.V.A", "VARIOS", "PAGO",
            "GASTO", "INTERES", "INGRESOS BRUTOS", "I.V.A. BASE", "COMIS.", "COMPENSACION",
            "COMISION"
        ]

        # Excepciones: GRAVAMEN / INGRESOS BRUTOS se toman SIEMPRE como débito
        if any(k in d for k in debit_kw):
            return "DEBITO"
        if any(k in d for k in credit_kw) and not any(x in d for x in debit_kw):
            return "CREDITO"
        return ""