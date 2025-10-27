# parsers/patagonia.py
import re
from typing import List, Dict, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class PatagoniaParser:
    BANK_NAME = "PATAGONIA"
    PREFER_TABLES = False
    
    def detect(self, text: str, filename: str = "") -> bool:
        haystack = f"{text} {filename}".upper()
        return "BANCO PATAGONIA" in haystack or "PATAGONIA EBANK" in haystack
    
    def parse(self, raw_data, filename: str = ""):
        """
        Acepta raw_data de tu UniversalExtractor actual:
        - dict con "text_lines", "tables", etc.
        - o lista de líneas
        - o string
        """
        # Extraer líneas según el tipo de raw_data
        if isinstance(raw_data, dict):
            lines = raw_data.get("text_lines_raw", []) or raw_data.get("text_lines_raw", [])
        elif isinstance(raw_data, list):
            lines = raw_data
        elif isinstance(raw_data, str):
            lines = raw_data.splitlines()
        else:
            lines = []
        
        rows = self._parse_lines(lines)
        return self._to_dataframe(rows)
    
    def _parse_lines(self, lines: List[str]) -> List[Dict]:
        """Parsea líneas de Patagonia."""
        DATE_PATTERN = re.compile(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b')
        AMOUNT_PATTERN = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')

         # DEBUG: Ver qué líneas llegan
        print(f"Total líneas recibidas: {len(lines)}")
        for i, line in enumerate(lines):
            if '27/08' in line or '30/08' in line:
                print(f"Línea {i}: {line}")

    
        rows = []
    
        for line in lines:
            if not line or len(line.strip()) < 5:
                continue

            lower = line.lower()

        # SOLO SALTAR headers, NO los saldos
            skip_keywords = [
            'debitos automaticos realizados',
            'transferencias recibidas',
            'transferencias enviadas',
            'situacion impositiva', 
            'fecha concepto', 
            'estimado cliente'
        ]
            if any(kw in lower for kw in skip_keywords):
                continue

        # Buscar fecha O líneas de saldo
            date_match = DATE_PATTERN.search(line)
        
        # Capturar SALDO ANTERIOR/ACTUAL aunque no tenga fecha
            is_saldo_line = 'saldo anterior' in lower or 'saldo actual' in lower
        
            if not date_match and not is_saldo_line:
                continue
        
            if date_match:
                fecha = date_match.group(1)
            else:
                fecha = ''  # Para líneas de saldo sin fecha
        
        # Extraer montos
            amounts_str = AMOUNT_PATTERN.findall(line)
            if not amounts_str:
                continue
        
            amounts = [self._parse_amount(a) for a in amounts_str]
        
        # EXTRAER DETALLE
            if date_match:
                fecha_pos = line.find(fecha)
                fecha_end = fecha_pos + len(fecha)
                first_amount_pos = line.find(amounts_str[0])
            
                if first_amount_pos > fecha_end:
                    detalle = line[fecha_end:first_amount_pos].strip()
                else:
                    detalle = line
                    detalle = DATE_PATTERN.sub('', detalle, count=1)
                    for amt_str in amounts_str:
                        detalle = detalle.replace(amt_str, '', 1)
            else:
            # Línea sin fecha (saldo)
                detalle = line
                for amt_str in amounts_str:
                    detalle = detalle.replace(amt_str, '', 1)
        
        # Limpiar
            detalle = re.sub(r'\s+', ' ', detalle).strip()
            detalle = re.sub(r'REFER\.\s*\d*', '', detalle, flags=re.I).strip()
            detalle = re.sub(r'FECHA VALOR\s*', '', detalle, flags=re.I).strip()
        
            row = self._categorize(fecha, detalle, amounts)
            if row:
                rows.append(row)
    
        return rows


    def _categorize(self, fecha: str, detalle: str, amounts: List[float]) -> Optional[Dict]:
        """Clasifica débitos/créditos según estructura de Patagonia."""
        if not amounts:
            return None
    
        lower = detalle.lower()
    
    # KEYWORDS CORREGIDAS - más específicas
        credit_keywords = [
        'credito interpyme',  # Más específico
        'transferencia entre cuentas',
        'transferencia recib',
        'deposito',
        'acreditacion'
    ]
    
        debit_keywords = [
        'debito automatico',
        'ret.iibb',
        'ret.',
        'imp.',  # Impuestos SIEMPRE son débitos
        'transf. prop',
        'comision',
        'pago'
    ]
    
        saldo_keywords = ['saldo anterior', 'saldo actual', 'saldo final']
    
        is_credit = any(kw in lower for kw in credit_keywords)
        is_debit = any(kw in lower for kw in debit_keywords)
        is_saldo = any(kw in lower for kw in saldo_keywords)
    
        debito = 0.0
        credito = 0.0
        saldo = 0.0
    
        if len(amounts) == 1:
            amount = abs(amounts[0])
        
            if is_saldo:
                saldo = amount
            elif is_credit:
                credito = amount
            elif is_debit:
                debito = amount
            else:
            # Sin contexto: asumir saldo
                saldo = amount
    
        elif len(amounts) == 2:
            movement = abs(amounts[0])
            saldo = amounts[1]
        
            if is_credit:
                credito = movement
            elif is_debit:
                debito = movement
            else:
                # Default: si tiene "credito interpyme" específico
                if 'credito interpyme' in lower or 'entre cuentas' in lower:
                    credito = movement
                else:
                    debito = movement
    
        elif len(amounts) >= 3:
            movement = abs(amounts[0])
            saldo = amounts[-1]
        
            if is_credit:
                credito = movement
            else:
                debito = movement
    
        return {
        'fecha': fecha,
        'detalle': detalle,
        'debito': debito,
        'credito': credito,
        'saldo': saldo
    }
    
    def _parse_amount(self, s: str) -> float:
        """Convierte '1.234,56' a float."""
        try:
            clean = s.replace('.', '').replace(',', '.')
            return float(clean)
        except:
            return 0.0
    
    def _to_dataframe(self, rows: List[Dict]) -> pd.DataFrame:
        """Convierte a DataFrame con formato final."""
        if not rows:
            return pd.DataFrame(columns=['fecha', 'mes', 'año', 'detalle', 'referencia', 'debito', 'credito', 'saldo'])
        
        df = pd.DataFrame(rows)
        
        # Agregar columnas faltantes
        df['referencia'] = ''
        
        # Extraer mes/año
        try:
            dates = pd.to_datetime(df['fecha'], format='%d/%m/%Y', errors='coerce')
            df['mes'] = dates.dt.month.fillna(0).astype(int)
            df['año'] = dates.dt.year.fillna(0).astype(int)
        except:
            df['mes'] = 0
            df['año'] = 0
        
        # Orden final
        return df[['fecha', 'mes', 'año', 'detalle', 'referencia', 'debito', 'credito', 'saldo']]