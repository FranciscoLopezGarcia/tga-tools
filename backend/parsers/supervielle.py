# parsers/supervielle.py
import re
from typing import List, Dict
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SupervielleParser:
    BANK_NAME = "SUPERVIELLE"
    PREFER_TABLES = False
    DETECTION_KEYWORDS = [
        "SUPERVIELLE",
        "BANCO SUPERVIELLE"
    ]
    
    def detect(self, text: str, filename: str = "") -> bool:
        haystack = f"{text} {filename}".upper()
        return any(kw in haystack for kw in self.DETECTION_KEYWORDS)
    
    def parse(self, raw_data, filename: str = ""):
        """Parser único para Supervielle (pesos y dólares)."""
        if isinstance(raw_data, dict):
            lines = raw_data.get("text_lines_raw", []) or raw_data.get("text_lines", [])
        elif isinstance(raw_data, list):
            lines = raw_data
        elif isinstance(raw_data, str):
            lines = raw_data.splitlines()
        else:
            lines = []
        
        # Detectar moneda automáticamente
        text_upper = " ".join(lines).upper()
        is_usd = "U$S" in text_upper or "DOLARES" in text_upper
        currency = "USD" if is_usd else "ARS"
        
        rows = self._parse_lines(lines, currency)
        return self._to_dataframe(rows)
    
    def _parse_lines(self, lines: List[str], currency: str) -> List[Dict]:
        """Parsea líneas de Supervielle."""
        rows = []
        saldo_anterior = None
        current_concepto_extra = []  # Para líneas adicionales de concepto
        
        # Patrones
        DATE_PATTERN = re.compile(r'^(\d{2}/\d{2}/\d{2})\s+')
        AMOUNT_PATTERN = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')
        
        for line in lines:
            if not line or len(line.strip()) < 5:
                continue
            
            lower = line.lower()
            
            # Capturar Saldo del período anterior
            if 'saldo del período anterior' in lower or 'saldo del periodo anterior' in lower:
                amounts = AMOUNT_PATTERN.findall(line)
                if amounts:
                    saldo_anterior = self._parse_amount(amounts[-1])
                    rows.append({
                        'fecha': None,
                        'concepto': 'SALDO ANTERIOR',
                        'referencia': '',
                        'debito': None,
                        'credito': None,
                        'saldo': saldo_anterior,
                        'moneda': currency
                    })
                continue
            
            # Saltar headers y líneas informativas
            if any(skip in lower for skip in [
                'detalle de movimientos', 'clave bancaria', 'responsable inscripto',
                'cantidad total', 'importante:', 'los depósitos', 'garantía',
                'régimen de transparencia', 'monotributistas', 'imp ley 25413',
                'reg de recaudacion'
            ]):
                continue
            
            # Si la línea dice "Fecha Concepto Débito Crédito Saldo", saltarla
            if re.search(r'fecha\s+concepto\s+d[ée]bito\s+cr[ée]dito\s+saldo', lower):
                continue
            
            # Detectar SUBTOTAL
            if lower.strip().startswith('subtotal'):
                amounts = AMOUNT_PATTERN.findall(line)
                if amounts:
                    saldo = self._parse_amount(amounts[-1])
                    if '-' in line:
                        saldo = -abs(saldo)
                    rows.append({
                        'fecha': None,
                        'concepto': 'SUBTOTAL',
                        'referencia': '',
                        'debito': None,
                        'credito': None,
                        'saldo': saldo,
                        'moneda': currency
                    })
                continue
            
            # Detectar SALDO PERIODO ACTUAL (final)
            if 'saldo periodo actual' in lower or 'saldo período actual' in lower:
                amounts = AMOUNT_PATTERN.findall(line)
                if amounts:
                    saldo_final = self._parse_amount(amounts[-1])
                    if '-' in line:
                        saldo_final = -abs(saldo_final)
                    rows.append({
                        'fecha': None,
                        'concepto': 'SALDO FINAL',
                        'referencia': '',
                        'debito': None,
                        'credito': None,
                        'saldo': saldo_final,
                        'moneda': currency
                    })
                continue
            
            # Buscar fecha AL INICIO de la línea
            date_match = DATE_PATTERN.match(line)
            
            # Si no hay fecha, puede ser continuación del concepto anterior
            if not date_match:
                # Revisar si es una línea de detalle adicional (Pres:, Id:, Ref:, etc)
                if any(x in line for x in ['Pres:', 'Id:', 'Ref:', 'Operación', 'Generada']):
                    current_concepto_extra.append(line.strip())
                continue
            
            fecha_str = date_match.group(1)
            rest_of_line = line[date_match.end():].strip()
            
            # Extraer todos los montos de la línea
            amounts = AMOUNT_PATTERN.findall(rest_of_line)
            if not amounts:
                continue
            
            # Encontrar posición del primer monto
            first_amount_pos = rest_of_line.find(amounts[0])
            
            # Extraer concepto (todo antes del primer monto)
            concepto = rest_of_line[:first_amount_pos].strip()
            
            # Agregar detalles extra si hay
            if current_concepto_extra:
                concepto = concepto + " " + " ".join(current_concepto_extra)
                current_concepto_extra = []
            
            # Extraer referencia (número entre concepto y montos)
            referencia = self._extract_referencia(concepto)
            
            # Limpiar concepto
            concepto = self._clean_concepto(concepto)
            
            # Extraer parte después de los montos para buscar saldo negativo
            rest_after_amounts = rest_of_line[first_amount_pos:]
            
            # Determinar débito, crédito y saldo según cantidad de montos
            debito = None
            credito = None
            saldo = None
            
            if len(amounts) == 1:
                # Un solo monto: puede ser débito O crédito, con saldo implícito
                # O puede ser solo el saldo
                monto = self._parse_amount(amounts[0])
                
                # Determinar si es débito o crédito por el contexto
                concepto_lower = concepto.lower()
                if any(word in concepto_lower for word in [
                    'pago', 'débito', 'impuesto', 'comis', 'iva', 'percep',
                    'cargo', 'trf', 'transferencia', 'debin'
                ]):
                    debito = monto
                elif any(word in concepto_lower for word in [
                    'crédito', 'acredit', 'depósito', 'cobr', 'ingreso'
                ]):
                    credito = monto
                else:
                    # Si no podemos determinar, dejar en saldo
                    saldo = monto
                    
            elif len(amounts) == 2:
                # Dos montos: monto1 (débito o crédito) + saldo
                monto1 = self._parse_amount(amounts[0])
                saldo = self._parse_amount(amounts[1])
                
                # Determinar si monto1 es débito o crédito
                concepto_lower = concepto.lower()
                if any(word in concepto_lower for word in [
                    'pago', 'débito', 'impuesto', 'comis', 'iva', 'percep',
                    'db.aut', 'trf masiva'
                ]):
                    debito = monto1
                else:
                    credito = monto1
                    
            elif len(amounts) >= 3:
                # Tres montos: débito + crédito + saldo
                debito = self._parse_amount(amounts[0])
                credito = self._parse_amount(amounts[1])
                saldo = self._parse_amount(amounts[2])
            
            # Verificar signo del saldo (buscar '-' después del último monto)
            if saldo is not None:
                # Buscar el último monto en la línea
                last_amount_match = list(re.finditer(AMOUNT_PATTERN, rest_of_line))[-1]
                text_after_last = rest_of_line[last_amount_match.end():]
                if '-' in text_after_last:
                    saldo = -abs(saldo)
            
            rows.append({
                'fecha': fecha_str,
                'concepto': concepto,
                'referencia': referencia,
                'debito': debito,
                'credito': credito,
                'saldo': saldo,
                'moneda': currency
            })
        
        return rows
    
    def _clean_concepto(self, concepto: str) -> str:
        """Limpia el concepto de textos innecesarios."""
        # Remover códigos largos (más de 10 dígitos consecutivos)
        concepto = re.sub(r'\b\d{11,}\b', '', concepto)
        # Remover espacios múltiples
        concepto = re.sub(r'\s+', ' ', concepto)
        return concepto.strip()
    
    def _extract_referencia(self, text: str) -> str:
        """Extrae números de referencia."""
        # Buscar números de 6-10 dígitos
        refs = re.findall(r'\b\d{6,10}\b', text)
        return refs[0] if refs else ''
    
    def _parse_amount(self, amount_str: str) -> float:
        """Convierte string de monto a float."""
        try:
            clean = amount_str.replace('.', '').replace(',', '.')
            return float(clean)
        except:
            return 0.0
    
    def _parse_date(self, date_str: str) -> tuple:
        """Convierte DD/MM/YY a (fecha_completa, mes, año)."""
        try:
            day, month, year = date_str.split('/')
            full_year = f"20{year}" if int(year) <= 50 else f"19{year}"
            fecha = f"{day}/{month}/{full_year}"
            return fecha, int(month), int(full_year)
        except:
            return date_str, None, None
    
    def _to_dataframe(self, rows: List[Dict]) -> pd.DataFrame:
        """Convierte lista de registros a DataFrame."""
        if not rows:
            return pd.DataFrame(columns=[
                'fecha', 'mes', 'año', 'detalle', 'referencia',
                'debito', 'credito', 'saldo', 'moneda'
            ])
        
        df = pd.DataFrame(rows)
        
        # Parsear fechas
        df[['fecha', 'mes', 'año']] = df.apply(
            lambda row: self._parse_date(row['fecha']) if row['fecha'] else (None, None, None),
            axis=1, result_type='expand'
        )
        
        # Renombrar concepto a detalle
        df.rename(columns={'concepto': 'detalle'}, inplace=True)
        
        # Reordenar columnas
        df = df[['fecha', 'mes', 'año', 'detalle', 'referencia', 
                 'debito', 'credito', 'saldo', 'moneda']]
        
        return df