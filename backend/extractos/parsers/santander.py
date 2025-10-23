# parsers/santander.py
import re
from typing import List, Dict, Optional
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SantanderParser:
    BANK_NAME = "SANTANDER"
    PREFER_TABLES = False  # Funciona bien con texto
    DETECTION_KEYWORDS = [
        "SANTANDER",
        "BANCO SANTANDER",
        "RESUMEN DE CUENTA"
    ]
    
    def detect(self, text: str, filename: str = "") -> bool:
        haystack = f"{text} {filename}".upper()
        return any(kw in haystack for kw in self.DETECTION_KEYWORDS)
    
    def parse(self, raw_data, filename: str = ""):
        """Parser para Santander."""
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
        """Parsea líneas de Santander."""
        rows = []
        saldo_inicial = None
        
        # Patrones
        DATE_PATTERN = re.compile(r'\b(\d{2}/\d{2}/\d{2})\b')
        AMOUNT_PATTERN = re.compile(r'\$\s*\d{1,3}(?:\.\d{3})*,\d{2}')
        
        for line in lines:
            if not line or len(line.strip()) < 5:
                continue
            
            lower = line.lower()
            
            # Capturar Saldo Inicial
            if 'saldo inicial' in lower:
                amounts = AMOUNT_PATTERN.findall(line)
                if amounts:
                    saldo_inicial = self._parse_amount(amounts[-1])
                continue
            
            # Saltar headers y footers
            if any(skip in lower for skip in [
                'fecha comprobante movimiento', 'debito credito saldo',
                'cuenta corriente nº', 'saldo total', 'periodo',
                'detalle impositivo', 'salvo error'
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
            
            # Limpiar detalle (remover info extra como "Del XX/XX/XX al XX/XX/XX")
            detalle = re.sub(r'Del\s+\d{2}/\d{2}/\d{2}\s+al\s+\d{2}/\d{2}/\d{2}', '', detalle, flags=re.I).strip()
            
            # Clasificar montos
            row = self._categorize_santander(fecha, detalle, amounts)
            if row:
                rows.append(row)
        
        # Agregar Saldo Inicial al principio
        if saldo_inicial is not None:
            rows.insert(0, {
                'fecha': '',
                'detalle': 'SALDO INICIAL',
                'referencia': '',
                'debito': 0.0,
                'credito': 0.0,
                'saldo': saldo_inicial
            })
        
        return rows
    
    def _categorize_santander(self, fecha: str, detalle: str, amounts: List[float]) -> Optional[Dict]:
        """
        Categoriza montos según estructura Santander.
        
        Columnas: DÉBITO | CRÉDITO | SALDO
        - 1 monto: solo saldo
        - 2 montos: débito/crédito + saldo
        - 3 montos: débito, crédito, saldo
        """
        if not amounts:
            return None
        
        debito = 0.0
        credito = 0.0
        saldo = 0.0
        
        if len(amounts) == 1:
            # Solo saldo
            saldo = amounts[0]
        
        elif len(amounts) == 2:
            # Movimiento + saldo
            movement = amounts[0]
            saldo = amounts[1]
            
            # Clasificar por contexto
            lower = detalle.lower()
            debit_keywords = ['comision', 'iva', 'impuesto', 'percepcion', 'interes', 'sello']
            
            if any(kw in lower for kw in debit_keywords):
                debito = abs(movement)
            else:
                # Por defecto, si no hay keywords de débito, asumir crédito
                credito = abs(movement)
        
        elif len(amounts) >= 3:
            # Débito, crédito, saldo
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
        Normaliza fecha DD/MM/YY a DD/MM/YYYY.
        """
        if not date_str:
            return ""
        
        try:
            # Formato DD/MM/YY
            parts = date_str.split('/')
            if len(parts) == 3:
                day, month, year = parts
                year = int(year)
                
                # Convertir año de 2 dígitos a 4
                if year < 100:
                    year = 2000 + year
                
                dt = datetime(year, int(month), int(day))
                return dt.strftime('%d/%m/%Y')
            
            return date_str
        except:
            return date_str
    
    def _parse_amount(self, amount_str: str) -> float:
        """Convierte '$ 53.300,00' a float."""
        if not amount_str:
            return 0.0
        
        try:
            # Remover $ y espacios
            clean = amount_str.replace('$', '').strip()
            
            # Detectar negativos
            negative = clean.startswith('-')
            clean = clean.replace('-', '')
            
            # Convertir formato argentino
            clean = clean.replace('.', '').replace(',', '.')
            result = float(clean)
            
            return -result if negative else result
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
        
        return df[['fecha', 'mes', 'año', 'detalle', 'referencia', 'debito', 'credito', 'saldo']]