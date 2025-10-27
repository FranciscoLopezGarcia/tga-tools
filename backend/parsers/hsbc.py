# -*- coding: utf-8 -*-
"""Parser para Banco HSBC Argentina."""

import re
import pandas as pd
from parsers.base_parser import BaseParser
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class HSBCParser(BaseParser):
    BANK_NAME = "HSBC"
    PREFER_TABLES = False
    DETECTION_KEYWORDS = ("HSBC", "HSBC ARGENTINA", "HSBC BANK")

    # Mapeo de meses
    MONTH_MAP = {
        'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12,
    }

    def detect(self, text: str, filename: str = "") -> bool:
        haystack = f"{text} {filename}".upper()
        return any(kw in haystack for kw in self.DETECTION_KEYWORDS)

    def parse(self, raw_data, filename="") -> pd.DataFrame:
        """Parser para HSBC con fechas DD-MMM"""
        
        # Extraer líneas del diccionario
        if isinstance(raw_data, dict):
            lines = raw_data.get("text_lines_raw", [])
            if not lines:
                lines = raw_data.get("text_lines", [])
        elif isinstance(raw_data, list):
            lines = raw_data
        else:
            lines = str(raw_data).splitlines()

        logger.info(f"📄 Iniciando parse de {len(lines)} líneas")

        # Inferir año
        full_text = "\n".join(lines)
        year = self._infer_year(full_text, filename)
        logger.info(f"📅 Año inferido: {year}")

        rows = []
        saldo_anterior = None
        saldo_final = None
        current_detail = None

        # Regex para fecha: DD-MMM (con guion)
        date_pattern = re.compile(r"^(\d{2}-[A-Z]{3})\s+-\s+(.+)$", re.I)
        
        # Regex para montos
        amount_pattern = re.compile(r"\d{1,3}(?:[.,]\d{3})*[.,]\d{2}")

        def parse_amount(s):
            if not s:
                return 0.0
            s = s.replace(".", "").replace(",", ".")
            try:
                return float(s)
            except:
                return 0.0

        def parse_date(date_str, default_year):
            """Convierte DD-MMM a YYYY-MM-DD"""
            date_str = date_str.strip().upper()
            parts = date_str.split('-')
            
            if len(parts) != 2:
                return date_str
            
            try:
                day = int(parts[0])
                month_str = parts[1][:3]
                month = self.MONTH_MAP.get(month_str)
                
                if not month:
                    return date_str
                
                return datetime(default_year, month, day).strftime("%Y-%m-%d")
            except:
                return date_str

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Capturar SALDO ANTERIOR
            if "SALDO ANTERIOR" in line.upper():
                amounts = amount_pattern.findall(line)
                if amounts:
                    saldo_anterior = parse_amount(amounts[-1])
                    logger.debug(f"✅ Saldo anterior: {saldo_anterior}")
                continue

            # Capturar SALDO FINAL
            if "SALDO FINAL" in line.upper():
                amounts = amount_pattern.findall(line)
                if amounts:
                    saldo_final = parse_amount(amounts[-1])
                    logger.debug(f"✅ Saldo final: {saldo_final}")
                continue

            # Saltar headers y footers MÁS ESTRICTO
            line_upper = line.upper()
            if any(x in line_upper for x in [
                "FECHA REFERENCIA NRO",
                "DETALLE DE OPERACIONES",
                "HOJA",
                "DE 18",
                "3960568-A",
                "ATENCION AL CLIENTE",
                "HSBC BANK ARGENTINA",
                "BOUCHARD 557",
                "DETALLE DE IMPUESTOS",
                "DETALLE DE CUOTAS",
                "REGIMEN DE GARANTIAS",
                "FONDOS COMUNES",
                "DEBITOS AUTOMATICOS",
                "LEY 2709",
                "PRESTAMOS PRENDARIOS",
                "CUENTAS SUELDO",
                "REFINANCIACION",
                "ACLARACIONES:",
                "CFT ",
                "TNA ",
            ]):
                current_detail = None  # Resetear detalle al encontrar footer
                continue

            # Buscar línea con fecha
            match = date_pattern.match(line)
            if not match:
                # Continuación de detalle: SOLO si hay detalle abierto Y no es basura
                if current_detail is not None:
                    # NO agregar si tiene muchos montos (es otra transacción)
                    if len(amount_pattern.findall(line)) > 0:
                        continue
                    # NO agregar si es muy larga o tiene palabras clave de footer
                    if len(line) > 150 or any(x in line_upper for x in ["HOJA", "DETALLE DE", "PAGINA"]):
                        continue
                    # Agregar máximo 50 caracteres extra
                    extra = line[:50].strip()
                    if len(extra) > 3:
                        current_detail["detalle"] += " " + extra
                continue

            fecha_str = match.group(1)
            resto = match.group(2)

            # Parsear fecha
            fecha = parse_date(fecha_str, year)

            # Encontrar montos
            amounts = amount_pattern.findall(resto)
            
            # VALIDACIÓN: necesitamos al menos 2 montos
            if len(amounts) < 2:
                logger.debug(f"Línea {i} saltada: solo {len(amounts)} montos")
                continue

            # Extraer REFERENCIA primero (antes de procesar montos)
            # En HSBC el formato es: DD-MMM - DESCRIPCION REFERENCIA MONTO SALDO
            # La referencia suele ser el primer número de 5 dígitos
            first_amount_pos = resto.find(amounts[0]) if len(amounts) > 0 else len(resto)
            texto_antes_montos = resto[:first_amount_pos]
            
            # Buscar referencia: número de 5 dígitos exactamente (no 6+ que pueden ser CUITs)
            ref_matches = re.findall(r"\b(\d{5})\b", texto_antes_montos)
            referencia = ref_matches[-1] if ref_matches else ""

            # LÓGICA HSBC: siempre [monto, saldo]
            saldo = parse_amount(amounts[-1])
            monto = parse_amount(amounts[-2])

            # Determinar si es débito o crédito
            debito = 0.0
            credito = 0.0
            
            # Heurística mejorada
            resto_upper = resto.upper()
            if any(kw in resto_upper for kw in ["DEBITO", "DB ", "N/D", "TRANSF. ENTRE CUENTAS"]):
                debito = monto
            elif any(kw in resto_upper for kw in ["INTERBANKING", "TRANSF.CAJ.AUTOM", "TEF DATANET"]):
                credito = monto
            else:
                # Fallback: asumir crédito
                credito = monto

            # Extraer detalle (remover montos y referencia)
            detalle_temp = resto
            for amt in amounts:
                detalle_temp = detalle_temp.replace(amt, " ")
            
            if referencia:
                detalle_temp = detalle_temp.replace(referencia, " ")

            # Limpiar
            detalle = re.sub(r"^\s*-\s*", "", detalle_temp)
            detalle = re.sub(r"\s+", " ", detalle).strip()

            current_detail = {
                "fecha": fecha,
                "detalle": detalle,
                "referencia": referencia,
                "debito": debito,
                "credito": credito,
                "saldo": saldo,
            }
            
            rows.append(current_detail)

            if len(rows) % 50 == 0:
                logger.info(f"✨ Procesadas {len(rows)} transacciones")

        logger.info(f"✅ Total extraído: {len(rows)} transacciones")

        # Crear DataFrame
        df = pd.DataFrame(rows, columns=self.REQUIRED_COLUMNS)

        # Agregar saldos
        extras = []
        if saldo_anterior is not None:
            extras.append({
                "fecha": "", "detalle": "SALDO ANTERIOR", "referencia": "",
                "debito": 0.0, "credito": 0.0, "saldo": saldo_anterior
            })

        if extras:
            df = pd.concat([
                pd.DataFrame(extras, columns=self.REQUIRED_COLUMNS),
                df
            ], ignore_index=True)

        if saldo_final is not None:
            df = pd.concat([
                df,
                pd.DataFrame([{
                    "fecha": "", "detalle": "SALDO FINAL", "referencia": "",
                    "debito": 0.0, "credito": 0.0, "saldo": saldo_final
                }], columns=self.REQUIRED_COLUMNS)
            ], ignore_index=True)

        return self.finalize(df)