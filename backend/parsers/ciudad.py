# parsers/ciudad.py
import re
from typing import List, Dict, Optional
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CiudadParser:
    BANK_NAME = "CIUDAD"
    PREFER_TABLES = False  # Ciudad viene mejor en texto
    DETECTION_KEYWORDS = [
        "BANCO CIUDAD", 
        "BANCO CIUDAD DE BUENOS AIRES",
        "RESUMEN DE CUENTA DOCUMENTACION COMERCIAL"
    ]
    
    # Meses en español
    MESES = {
        'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4,
        'MAY': 5, 'JUN': 6, 'JUL': 7, 'AGO': 8,
        'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
    }
    
    def detect(self, text: str, filename: str = "") -> bool:
        haystack = f"{text} {filename}".upper()
        return any(kw in haystack for kw in self.DETECTION_KEYWORDS)
    
    def parse(self, raw_data, filename: str = ""):
        """Parser para Banco Ciudad."""
        # Extraer líneas
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
        """Parsea líneas de Banco Ciudad."""
        rows = []
        saldo_anterior = None
        
        # Patrones
        DATE_PATTERN = re.compile(r'\b(\d{1,2}-[A-Z]{3}-\d{4})\b', re.I)
        AMOUNT_PATTERN = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')
        SALDO_ANTERIOR_PATTERN = re.compile(r'SALDO\s+ANTERIOR', re.I)
        SALDO_FINAL_PATTERN = re.compile(r'SALDO\s+AL\s+\d{1,2}', re.I)
        
        for line in lines:
            if not line or len(line.strip()) < 5:
                continue
            
            # Capturar SALDO ANTERIOR
            if SALDO_ANTERIOR_PATTERN.search(line):
                amounts = AMOUNT_PATTERN.findall(line)
                if amounts:
                    saldo_anterior = self._parse_amount(amounts[-1])
                continue
            
            # Saltar líneas de headers y footers
            lower = line.lower()
            if any(skip in lower for skip in [
                'fecha concepto', 'debito credito saldo', 
                'descripcion de movimiento', 'hoja nro',
                'cuit:', 'domicilio:', 'iva responsable'
            ]):
                continue
            
            # Buscar fecha (indica transacción)
            date_match = DATE_PATTERN.search(line)
            if not date_match:
                continue
            
            fecha_str = date_match.group(1)
            fecha = self._normalize_date(fecha_str)
            
            # Extraer montos
            amounts_str = AMOUNT_PATTERN.findall(line)
            if not amounts_str:
                continue
            
            amounts = [self._parse_amount(a) for a in amounts_str]
            
            # Extraer detalle (entre fecha y primer monto)
            fecha_end = line.find(fecha_str) + len(fecha_str)
            first_amount_pos = line.find(amounts_str[0])
            detalle = line[fecha_end:first_amount_pos].strip() if first_amount_pos > fecha_end else ""
            
            # Clasificar montos según estructura Ciudad
            row = self._categorize_ciudad(fecha, detalle, amounts)
            if row:
                rows.append(row)
        
        # Agregar SALDO ANTERIOR al inicio si existe
        if saldo_anterior is not None:
            rows.insert(0, {
                'fecha': '',
                'detalle': 'SALDO ANTERIOR',
                'referencia': '',
                'debito': 0.0,
                'credito': 0.0,
                'saldo': saldo_anterior
            })
        
        return rows
    
    def _categorize_ciudad(self, fecha: str, detalle: str, amounts: List[float]) -> Optional[Dict]:
        """
        Categoriza montos según estructura de Banco Ciudad.
        
        Ciudad tiene: DÉBITO | CRÉDITO | SALDO
        - 1 monto: puede ser débito, crédito o saldo
        - 2 montos: débito+saldo O crédito+saldo
        - 3 montos: débito, crédito, saldo
        """
        if not amounts:
            return None
        
        debito = 0.0
        credito = 0.0
        saldo = 0.0
        
        if len(amounts) == 1:
            # Solo un monto - probablemente saldo
            saldo = amounts[0]
        
        elif len(amounts) == 2:
            # Dos montos: movimiento + saldo
            # Determinar si es débito o crédito por contexto
            lower = detalle.lower()
            
            debit_keywords = ['comision', 'debito', 'retencion', 'impuesto', 'iva']
            is_debit = any(kw in lower for kw in debit_keywords)
            
            if is_debit:
                debito = abs(amounts[0])
                saldo = amounts[1]
            else:
                credito = abs(amounts[0])
                saldo = amounts[1]
        
        elif len(amounts) >= 3:
            # Tres montos: débito, crédito, saldo
            debito = abs(amounts[0])
            credito = abs(amounts[1])
            saldo = amounts[2]
        
        return {
            'fecha': fecha,
            'detalle': detalle[:200],
            'referencia': '',
            'debito': debito,
            'credito': credito,
            'saldo': saldo
        }
    
    def _normalize_date(self, date_str: str) -> str:
        """
        Normaliza fecha de formato DD-MMM-YYYY a DD/MM/YYYY.
        Ejemplo: 28-FEB-2025 → 28/02/2025
        """
        if not date_str:
            return ""
        
        try:
            # Parsear formato DD-MMM-YYYY
            parts = date_str.split('-')
            if len(parts) != 3:
                return date_str
            
            day = int(parts[0])
            month_str = parts[1].upper()
            year = int(parts[2])
            
            # Convertir mes
            month = self.MESES.get(month_str[:3])
            if not month:
                return date_str
            
            # Crear fecha
            dt = datetime(year, month, day)
            return dt.strftime('%d/%m/%Y')
        
        except:
            return date_str
    
    def _parse_amount(self, amount_str: str) -> float:
        """Convierte string de monto a float."""
        if not amount_str:
            return 0.0
        
        try:
            clean = amount_str.strip().replace('.', '').replace(',', '.')
            
            # Detectar negativos con sufijo (27.556,64-)
            if clean.endswith('-'):
                clean = '-' + clean[:-1]
            
            return float(clean)
        except:
            return 0.0
    
    def _to_dataframe(self, rows: List[Dict]) -> pd.DataFrame:
        """Convierte a DataFrame final."""
        if not rows:
            return pd.DataFrame(columns=['fecha', 'mes', 'año', 'detalle', 'referencia', 'debito', 'credito', 'saldo'])
        
        df = pd.DataFrame(rows)
        
        # Agregar mes y año
        def extract_date_parts(fecha_str):
            if not fecha_str:
                return 0, 0
            try:
                dt = datetime.strptime(fecha_str, '%d/%m/%Y')
                return dt.month, dt.year
            except:
                return 0, 0
        
        df[['mes', 'año']] = df['fecha'].apply(
            lambda x: pd.Series(extract_date_parts(x))
        )
        
        # Orden final
        return df[['fecha', 'mes', 'año', 'detalle', 'referencia', 'debito', 'credito', 'saldo']]