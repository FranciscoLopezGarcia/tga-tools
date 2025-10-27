import re
import pandas as pd
from datetime import datetime

class MacroParser:
    """
    Parser final Banco Macro.
    Corrige:
      - Clasificación débito/crédito (N/D, PRISMA, etc.)
      - Saldos con signo correcto
      - Orden correcto: Saldo anterior → Movimientos → Saldo final
    """

    BANK_NAME = "MACRO"
    DETECTION_KEYWORDS = ["MACRO"]

    CREDIT_HINTS = (
        "N/C", "ACRED", "ACREDIT", "DEPOSITO", "DEPOSITO CANJE", "CR ",
        "PRISMA", "LIQ COMER", "TRANSFERENCIA", "TRANSF", "MACRONLINE", "MACROLINE",
        "CCERR", "VAR VARIOS"
    )
    DEBIT_HINTS = (
        "N/D", "DEBITO", "DB ", "DBCR", "RETENCION", "SIRCREB", "IMPUESTO",
        "COMISION", "MANTENIMIENTO", "IVA", "SELLOS", "PAGO DE CHEQUE"
    )
    NOISE_PATTERNS = (
        "TOTAL COBRADO DEL IMP", "IIBB SIRCREB", "D. 409/2018", "IMPUESTO LEY",
        "S.E.U.O.", "Casa Central", "Hoja Nro", "Información de su/s Cuenta/s",
        "Desde el 01/", "______"
    )
    ID_CREDITO_RE = re.compile(r"\b5730\d{4,}\b")
    AMOUNT_RE = re.compile(r"(-?\d{1,3}(?:\.\d{3})*,\d{2})")

    def detect(self, text: str, filename: str = "") -> bool:
        return "MACRO" in f"{text} {filename}".upper()

    def parse(self, raw_data, filename: str = "") -> pd.DataFrame:
        # --- preparar líneas ---
        if isinstance(raw_data, dict):
            lines = raw_data.get("text_lines", []) or raw_data.get("text_lines_raw", [])
        elif isinstance(raw_data, list):
            lines = raw_data
        elif isinstance(raw_data, str):
            lines = raw_data.splitlines()
        else:
            lines = []

        lines = [re.sub(r"\s{2,}", " ", l.strip()) for l in lines if l.strip()]
        data, seq = [], 0
        saldo_anterior, saldo_final = None, None

        for line in lines:
            upper = line.upper()
            if any(x in upper for x in self.NOISE_PATTERNS):
                continue
            if upper.startswith("*") or upper.startswith("- - -"):
                continue
            if any(x in upper for x in [
                "CUENTA CORRIENTE", "CLAVE BANCARIA", "DETALLE DE MOVIMIENTO",
                "PERIODO DEL EXTRACTO", "SALDOS CONSOLIDADOS", "TIPO CUENTA", "SUCURSAL", "MONEDA"
            ]):
                continue

            # --- saldos ---
            if "SALDO ULTIMO EXTRACTO" in upper or "SALDO ANTERIOR" in upper:
                saldo_anterior = self._last_amount(line)
                data.append(self._saldo_row("Saldo Anterior", saldo_anterior, seq))
                seq += 1
                continue

            if "SALDO FINAL" in upper or "SALDO AL" in upper:
                saldo_final = self._last_amount(line)
                data.append(self._saldo_row("Saldo Final", saldo_final, seq))
                seq += 1
                continue

            # --- movimientos ---
            f_match = re.search(r"(\d{2}/\d{2}/\d{2,4})", line)
            if not f_match:
                continue
            fecha = self._parse_date(f_match.group(1))
            if not fecha:
                continue

            amts_raw = self.AMOUNT_RE.findall(line)
            if not amts_raw:
                continue
            amts = [self._to_float(a) for a in amts_raw]

            deb, cre, sal = 0.0, 0.0, 0.0
            if len(amts) >= 3:
                deb, cre, sal = amts[-3], amts[-2], amts[-1]
            elif len(amts) == 2:
                mov, sal = amts
                up = upper
                looks_credit = any(h in up for h in self.CREDIT_HINTS) or bool(self.ID_CREDITO_RE.search(line))
                looks_debit = any(h in up for h in self.DEBIT_HINTS)
                if "N/D DBCR" in up:
                    deb = mov
                elif "PRISMA" in up or "LIQ COMER" in up:
                    cre = mov
                elif looks_credit and not looks_debit:
                    cre = mov
                elif looks_debit and not looks_credit:
                    deb = mov
                else:
                    if abs(mov) < abs(sal):
                        cre = mov
                    else:
                        deb = mov
            else:
                sal = amts[0]

            detalle = re.sub(r"\d{2}/\d{2}/\d{2,4}", "", line)
            for a in amts_raw:
                detalle = detalle.replace(a, "")
            detalle = re.sub(r"\s{2,}", " ", detalle).strip()

            ref = ""
            ref_match = re.search(r"\s(\d{6,})\s*$", detalle)
            if ref_match:
                ref = ref_match.group(1)
                detalle = detalle[:ref_match.start()].strip()

            data.append({
                "fecha": fecha, "detalle": detalle, "referencia": ref,
                "debito": round(deb, 2), "credito": round(cre, 2), "saldo": round(sal, 2),
                "mes": fecha.month, "año": fecha.year, "moneda": "ARS", "__seq": seq
            })
            seq += 1

        df = pd.DataFrame(data)
        if df.empty:
            print("⚠️ No se detectaron movimientos")
            return df

        # --- orden final ---
        saldo_ant = df[df["detalle"] == "Saldo Anterior"].copy()
        saldo_fin = df[df["detalle"] == "Saldo Final"].copy()
        otros = df[~df["detalle"].isin(["Saldo Anterior", "Saldo Final"])].copy()

        if "__seq" in df.columns:
            saldo_ant = saldo_ant.sort_values("__seq")
            saldo_fin = saldo_fin.sort_values("__seq")
            otros = otros.sort_values("__seq")

        frames = []
        if not saldo_ant.empty:
            frames.append(saldo_ant.iloc[[0]])
        if not otros.empty:
            frames.append(otros)
        if not saldo_fin.empty:
            frames.append(saldo_fin.iloc[[-1]])

        df = pd.concat(frames, ignore_index=True)
        df["__order"] = range(len(df))
        df = df.sort_values("__order").drop(columns="__order", errors="ignore").reset_index(drop=True)

        print(f"[DEBUG] Filas finales: {len(df)} | Débitos: {sum(df['debito']>0)} | Créditos: {sum(df['credito']>0)}")
        return df

    # --- helpers ---
    def _saldo_row(self, tipo, valor, seq):
        fake_date = None
        if tipo == "Saldo Anterior":
            fake_date = datetime(1900, 1, 1)
        elif tipo == "Saldo Final":
            fake_date = datetime(2100, 1, 1)
        return {
            "fecha": fake_date,
            "detalle": tipo,
            "referencia": "",
            "debito": 0,
            "credito": 0,
            "saldo": valor,
            "mes": None,
            "año": None,
            "moneda": "ARS",
            "__seq": seq
        }

    def _parse_date(self, txt):
        for fmt in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(txt, fmt)
            except:
                pass
        return None

    def _to_float(self, txt: str) -> float:
        try:
            txt = txt.strip().replace("–", "-").replace("−", "-").replace("—", "-")
            txt = re.sub(r"^[^\d-]+", "", txt)
            return float(txt.replace(".", "").replace(",", "."))
        except:
            return 0.0

    def _last_amount(self, line: str) -> float:
        clean = line.replace("–", "-").replace("−", "-").replace("—", "-")
        amts = self.AMOUNT_RE.findall(clean)
        if not amts:
            return 0.0
        val = self._to_float(amts[-1])
        if "SALDO" in clean.upper() and "-" in clean and val > 0:
            return -abs(val)
        return val
