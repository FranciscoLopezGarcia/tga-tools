# parsers/sanjuan_strict.py
import re
from typing import List, Dict, Any
from parsers.strict_base import StrictBankParser, AMOUNT_ANY, DATE_PREFIX

SKIP_LC = (
    "movimientos de cuenta", "banco san juan", "home banking",
    "cuenta corriente", "periodo", "hoja:", "subtotal", "transporte",
)

class SanJuanParser(StrictBankParser):
    BANK_NAME = "SANJUAN"
    PREFER_TABLES = True

    def detect(self, text: str, filename: str = "") -> bool:
        hay = f"{text} {filename}".upper()
        return ("BANCO SAN JUAN" in hay) or (" SAN JUAN " in hay)

    def parse(self, raw_data, filename: str = ""):
        tables = []
        lines: List[str] = []
        if isinstance(raw_data, dict):
            tables = [df for df in (raw_data.get("tables") or []) if hasattr(df, "columns")]
            lines = [str(x) for x in (raw_data.get("text_lines") or [])]
        elif isinstance(raw_data, list):
            if len(raw_data) and hasattr(raw_data[0], "columns"):
                tables = list(raw_data)
            else:
                lines = [str(x) for x in raw_data]
        elif isinstance(raw_data, str):
            lines = raw_data.splitlines()

        rows: List[Dict[str, Any]] = []
        rows.extend(self._from_tables(tables))
        rows.extend(self._from_lines(lines))
        return self._finalize_rows(rows)

    def _from_tables(self, tables) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for df in tables:
            for i in range(len(df)):
                rec = df.iloc[i].astype(str).fillna("").tolist()
                if not any(x.strip() for x in rec):
                    continue
                line = " ".join(rec).strip()
                if not line or self._looks_like_header(line):
                    continue
                m = DATE_PREFIX.match(line)
                if not m:
                    continue
                fecha_txt = m.group(0)
                rest = line[len(fecha_txt):].strip()
                nums = [x.group(0) for x in AMOUNT_ANY.finditer(rest)]
                deb = cre = saldo = 0.0
                detalle = rest
                if len(nums) >= 3:
                    saldo = self._to_amount(nums[-1])
                    cre = self._to_amount(nums[-2])
                    deb = self._to_amount(nums[-3])
                    detalle = rest[:rest.rfind(nums[-3])].strip()
                elif len(nums) == 2:
                    saldo = self._to_amount(nums[-1])
                    mov = self._to_amount(nums[-2])
                    if mov < 0: deb = abs(mov)
                    else: cre = mov
                    detalle = rest[:rest.rfind(nums[-2])].strip()
                fecha = self._norm_date(fecha_txt)
                anio, mes = self._split_year_month(fecha)
                out.append({
                    "fecha": fecha, "mes": mes, "año": anio,
                    "detalle": self._clean_detalle(detalle),
                    "referencia": "", "debito": max(0.0, deb), "credito": max(0.0, cre),
                    "saldo": saldo
                })
        return out

    def _from_lines(self, lines: List[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for s in lines:
            low = s.lower().strip()
            if any(k in low for k in SKIP_LC):
                continue
            m = DATE_PREFIX.match(s)
            if not m:
                continue
            fecha_txt = m.group(0)
            rest = s[len(fecha_txt):].strip()
            nums = [x.group(0) for x in AMOUNT_ANY.finditer(rest)]
            deb = cre = saldo = 0.0
            detalle = rest
            if len(nums) >= 3:
                saldo = self._to_amount(nums[-1])
                cre = self._to_amount(nums[-2])
                deb = self._to_amount(nums[-3])
                detalle = rest[:rest.rfind(nums[-3])].strip()
            elif len(nums) == 2:
                saldo = self._to_amount(nums[-1])
                mov = self._to_amount(nums[-2])
                if mov < 0: deb = abs(mov)
                else: cre = mov
                detalle = rest[:rest.rfind(nums[-2])].strip()
            fecha = self._norm_date(fecha_txt)
            anio, mes = self._split_year_month(fecha)
            out.append({
                "fecha": fecha, "mes": mes, "año": anio,
                "detalle": self._clean_detalle(detalle),
                "referencia": "", "debito": max(0.0, deb), "credito": max(0.0, cre),
                "saldo": saldo
            })
        return out

    def _clean_detalle(self, s: str) -> str:
        s = re.sub(r"\s+", " ", s or "").strip()
        s = re.sub(r"\d{11}", "", s)              # cuit
        s = re.sub(r"NRO\.\d+", "", s, flags=re.I)
        return s[:200]
