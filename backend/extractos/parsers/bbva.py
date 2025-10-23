# parsers/bbva.py
import re
from typing import List, Dict
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class BBVAParser:
    BANK_NAME = "BBVA"
    PREFER_TABLES = False
    DETECTION_KEYWORDS = [
        "BBVA",
        "BANCO BBVA",
        "BBVA FRANCES",
        "BBVA ARGENTINA"
    ]
    
    def detect(self, text: str, filename: str = "") -> bool:
        haystack = f"{text} {filename}".upper()
        return any(kw in haystack for kw in self.DETECTION_KEYWORDS)
    
    def parse(self, raw_data, filename: str = ""):
        """Parser para BBVA - solo tabla de movimientos."""
        if isinstance(raw_data, dict):
            lines = raw_data.get("text_lines_raw", []) or raw_data.get("text_lines", [])
        elif isinstance(raw_data, list):
            lines = raw_data
        elif isinstance(raw_data, str):
            lines = raw_data.splitlines()
        else:
            lines = []
        
        rows = self._parse_lines(lines)
        return self._to_dataframe(rows)
    
    def _parse_lines(self, lines: List[str]) -> List[Dict]:
        """Parsea solo la tabla de movimientos en cuentas."""
        rows = []
        in_movements_section = False
        saldo_anterior = None
        
        # Patrones
        DATE_PATTERN = re.compile(r'^(\d{2}/\d{2})\s+')
        AMOUNT_PATTERN = re.compile(r'-?\d{1,3}(?:\.\d{3})*,\d{2}')
        
        for line in lines:
            if not line or len(line.strip()) < 5:
                continue
            
            lower = line.lower()
            
            # Detectar inicio de sección de movimientos
            if 'movimientos en cuentas' in lower:
                in_movements_section = True
                continue
            
            # Detectar fin de sección de movimientos
            if in_movements_section and any(end in lower for end in [
                'saldo al ', 'total movimientos', 'impuesto a los débitos',
                'transferencias', 'débitos automáticos', 'recibidas',
                'enviadas', 'otros productos', 'legales'
            ]):
                in_movements_section = False
                continue
            
            # Solo procesar si estamos en la sección de movimientos
            if not in_movements_section:
                continue
            
            # Saltar headers
            if any(skip in lower for skip in [
                'fecha', 'origen', 'concepto', 'débito', 'crédito', 'saldo',
                'clave bancaria', 'responsable inscripto'
            ]):
                continue
            
            # Capturar Saldo Anterior
            if 'saldo anterior' in lower:
                amounts = AMOUNT_PATTERN.findall(line)
                if amounts:
                    saldo_anterior = self._parse_amount(amounts[-1])
                    rows.append({
                        'fecha': None,
                        'concepto': 'SALDO ANTERIOR',
                        'referencia': '',
                        'debito': None,
                        'credito': None,
                        'saldo': saldo_anterior
                    })
                continue
            
            # Detectar fecha al inicio
            date_match = DATE_PATTERN.match(line)
            if not date_match:
                continue
            
            fecha_str = date_match.group(1)
            rest_of_line = line[date_match.end():].strip()
            
            # Extraer montos
            amounts = AMOUNT_PATTERN.findall(rest_of_line)
            if not amounts:
                continue
            
            # Extraer concepto (todo antes del primer monto)
            first_amount_pos = rest_of_line.find(amounts[0])
            concepto_raw = rest_of_line[:first_amount_pos].strip()
            
            # Limpiar origen "D" si está al inicio
            if concepto_raw.startswith('D '):
                concepto_raw = concepto_raw[2:].strip()
            
            concepto = self._clean_concepto(concepto_raw)
            referencia = self._extract_referencia(concepto_raw)
            
            # Determinar débito, crédito y saldo
            debito = None
            credito = None
            saldo = None
            
            if len(amounts) == 1:
                monto = self._parse_amount(amounts[0])
                if monto < 0:
                    debito = abs(monto)
                else:
                    credito = monto
            elif len(amounts) == 2:
                monto1 = self._parse_amount(amounts[0])
                saldo = self._parse_amount(amounts[1])
                
                if monto1 < 0:
                    debito = abs(monto1)
                else:
                    credito = monto1
            elif len(amounts) >= 3:
                val1 = self._parse_amount(amounts[0])
                val2 = self._parse_amount(amounts[1])
                saldo = self._parse_amount(amounts[2])
                
                if val1 < 0:
                    debito = abs(val1)
                if val2 > 0:
                    credito = val2
            
            rows.append({
                'fecha': fecha_str,
                'concepto': concepto,
                'referencia': referencia,
                'debito': debito,
                'credito': credito,
                'saldo': saldo
            })
        
        return rows
    
    def _clean_concepto(self, concepto: str) -> str:
        """Limpia el concepto."""
        concepto = re.sub(r'\b\d{10,}\b', '', concepto)
        concepto = re.sub(r'\s+', ' ', concepto)
        return concepto.strip()
    
    def _extract_referencia(self, text: str) -> str:
        """Extrae referencia."""
        refs = re.findall(r'\b\d{6,10}\b', text)
        return refs[0] if refs else ''
    
    def _parse_amount(self, amount_str: str) -> float:
        """Convierte monto a float."""
        try:
            clean = amount_str.replace('.', '').replace(',', '.')
            return float(clean)
        except:
            return 0.0
    
    def _parse_date(self, date_str: str) -> tuple:
        """Convierte DD/MM a (fecha_completa, mes, año)."""
        try:
            day, month = date_str.split('/')
            current_year = datetime.now().year
            fecha = f"{day}/{month}/{current_year}"
            return fecha, int(month), current_year
        except:
            return date_str, None, None
    
    def _to_dataframe(self, rows: List[Dict]) -> pd.DataFrame:
        """Convierte a DataFrame."""
        if not rows:
            return pd.DataFrame(columns=[
                'fecha', 'mes', 'año', 'detalle', 'referencia',
                'debito', 'credito', 'saldo'
            ])
        
        df = pd.DataFrame(rows)
        
        df[['fecha', 'mes', 'año']] = df.apply(
            lambda row: self._parse_date(row['fecha']) if row['fecha'] else (None, None, None),
            axis=1, result_type='expand'
        )
        
        df.rename(columns={'concepto': 'detalle'}, inplace=True)
        
        df = df[['fecha', 'mes', 'año', 'detalle', 'referencia', 
                 'debito', 'credito', 'saldo']]
        
        return df