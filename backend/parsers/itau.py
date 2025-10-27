# -*- coding: utf-8 -*-
"""Parser para Banco Macro (archivos guardados como Itau)."""

import re
import pandas as pd
from parsers.base_parser import BaseParser
import logging

logger = logging.getLogger(__name__)


class ItauParser(BaseParser):
    BANK_NAME = "ITAU"
    PREFER_TABLES = False

    def detect(self, text: str, filename: str = "") -> bool:
        haystack = f"{text} {filename}".upper()
        return "BANCO MACRO" in haystack or "MACRO" in haystack

    def parse(self, raw_data, filename="") -> pd.DataFrame:
        """Parser para Banco Macro con formato DD/MM/YY"""
        
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

        # Regex para fecha: DD/MM/YY o DD/MM/YYYY
        date_pattern = re.compile(r"^(\d{2}/\d{2}/\d{2,4})\s+(.+)$")
        
        # Regex para montos: números con punto de miles y coma decimal
        # Puede tener signo negativo: -787.085,11
        amount_pattern = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")

        def parse_amount(s):
            if not s:
                return 0.0
            s = s.replace(".", "").replace(",", ".")
            try:
                return float(s)
            except:
                return 0.0

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Capturar SALDO ANTERIOR
            if "SALDO ULTIMO EXTRACTO" in line.upper() or "SALDO ANTERIOR" in line.upper():
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

            # Saltar headers y separadores
            if any(x in line for x in ["FECHA DESCRIPCION", "DETALLE DE MOVIMIENTO", "---", "TOTAL COBRADO"]):
                continue

            # Buscar línea con fecha
            match = date_pattern.match(line)
            if not match:
                continue

            fecha_str = match.group(1)
            resto = match.group(2)

            # Normalizar fecha
            fecha = self.normalize_date(fecha_str, year)

            # Encontrar todos los montos
            amounts = amount_pattern.findall(resto)
            
            if len(amounts) < 1:
                continue

            # EXTRAER REFERENCIA PRIMERO (antes de procesar montos)
            # La referencia está entre el detalle y los montos
            # Ejemplo: "TRF MO CCDO MISMO - 30701829898 63100901 1.600.000,00 -787.085,11"
            #                                           ^^^^^^^^ <- esta es la referencia
            
            # Buscar el último número de 5-9 dígitos ANTES del primer monto
            first_amount_pos = resto.find(amounts[0]) if amounts else len(resto)
            texto_antes_montos = resto[:first_amount_pos]
            
            # Buscar referencia: número de 5-9 dígitos (no 10+, esos son CUITs)
            ref_matches = re.findall(r"\b(\d{5,9})\b", texto_antes_montos)
            referencia = ref_matches[-1] if ref_matches else ""

            # LÓGICA DE MONTOS:
            # Formato Macro: [monto, saldo] o [debito, credito, saldo]
            saldo = parse_amount(amounts[-1])  # Último siempre es saldo
            debito = 0.0
            credito = 0.0

            if len(amounts) == 1:
                # Solo saldo, no hay movimiento
                pass
            elif len(amounts) == 2:
                # Un monto + saldo
                monto = parse_amount(amounts[0])
                
                # HEURÍSTICA MEJORADA:
                # 1. Si dice TRF, TRANSF -> débito (transferencia saliente)
                # 2. Si dice N/D, DEBITO, DB -> débito
                # 3. Si dice PAGO, LIQ -> crédito (liquidación/pago recibido)
                # 4. Si monto es negativo -> siempre débito
                
                resto_upper = resto.upper()
                if monto < 0:
                    debito = abs(monto)
                elif any(kw in resto_upper for kw in ["TRF MO", "TRANSF.", "N/D", "DEBITO", "DB "]):
                    debito = abs(monto)
                elif any(kw in resto_upper for kw in ["PAGO", "LIQ ", "TEF DATANET", "TRMIN"]):
                    credito = abs(monto)
                else:
                    # Fallback: si no está claro, asumir crédito
                    credito = abs(monto)
            else:  # 3 o más
                # Dos montos + saldo: [débito, crédito, saldo]
                debito = abs(parse_amount(amounts[-3]))
                credito = abs(parse_amount(amounts[-2]))

            # Extraer detalle (remover montos y referencia)
            detalle_temp = resto
            for amt in amounts:
                detalle_temp = detalle_temp.replace(amt, " ")
            
            if referencia:
                detalle_temp = detalle_temp.replace(referencia, " ")

            # Limpiar detalle
            detalle = re.sub(r"\s+", " ", detalle_temp).strip()

            rows.append({
                "fecha": fecha,
                "detalle": detalle,
                "referencia": referencia,
                "debito": debito,
                "credito": credito,
                "saldo": saldo,
            })

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