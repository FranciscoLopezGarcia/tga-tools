# parsers/icbc.py
import re
from typing import List, Dict, Optional, Tuple
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ICBCParser:
    BANK_NAME = "ICBC"
    DETECTION_KEYWORDS = [
        "ICBC",
        "INDUSTRIAL AND COMMERCIAL BANK OF CHINA"
    ]
    
    def detect(self, text: str, filename: str = "") -> bool:
        haystack = f"{text} {filename}".upper()
        return any(kw in haystack for kw in self.DETECTION_KEYWORDS)
    
    def parse(self, raw_data, filename: str = ""):
        """
        Parser para ICBC - nuevo formato.
        
        Columnas: Fecha (sin año), Concepto, F.Valor, Comprobante, Origen, Canal, 
                  Débitos, Créditos, Saldos
        
        Saldos:
        - Inicial: "SALDO ULTIMO EXTRACTO AL 31/08/2025"
        - Final: "SALDO FINAL AL 30/09/2025"
        """
        if isinstance(raw_data, dict):
            lines = raw_data.get("text_lines_raw", []) or raw_data.get("text_lines", [])
        elif isinstance(raw_data, list):
            lines = raw_data
        elif isinstance(raw_data, str):
            lines = raw_data.splitlines()
        else:
            lines = []
        
        if not lines:
            logger.warning(f"[{self.BANK_NAME}] No se encontraron líneas para procesar.")
            return pd.DataFrame()
        
        # Extraer año del período
        year = self._extract_year(lines)
        
        # Extraer saldos CON sus fechas
        saldo_inicial, fecha_inicial = self._extract_saldo_inicial(lines)
        saldo_final, fecha_final = self._extract_saldo_final(lines)
        
        # Parsear movimientos
        movimientos = self._parse_movimientos(lines, year)
        
        # Construir resultado
        rows = []
        
        # 🔧 Saldo anterior CON fecha
        if saldo_inicial is not None:
            rows.append({
                "fecha": fecha_inicial or "",
                "detalle": "SALDO ANTERIOR",
                "referencia": "",
                "debito": 0.0,
                "credito": 0.0,
                "saldo": saldo_inicial
            })
        
        rows.extend(movimientos)
        
        # 🔧 Saldo final CON fecha
        if saldo_final is not None:
            rows.append({
                "fecha": fecha_final or "",
                "detalle": "SALDO FINAL",
                "referencia": "",
                "debito": 0.0,
                "credito": 0.0,
                "saldo": saldo_final
            })
        
        return self._to_dataframe(rows)
    
    def _extract_year(self, lines: List[str]) -> int:
        """Extrae el año del período del extracto."""
        for line in lines:
            # Buscar "PERIODO 01-09-2025 AL 30-09-2025"
            match = re.search(r'PERIODO.*?(\d{4})', line, re.I)
            if match:
                return int(match.group(1))
            
            # También buscar en fechas completas
            match = re.search(r'(\d{2})/(\d{2})/(\d{4})', line)
            if match:
                return int(match.group(3))
        
        return datetime.now().year
    
    def _extract_saldo_inicial(self, lines: List[str]) -> Tuple[Optional[float], Optional[str]]:
        """
        Extrae saldo inicial del extracto CON su fecha.
        Retorna: (monto, fecha_str) o (None, None)
        """
        for line in lines:
            lower = line.lower()
            
            # Buscar "SALDO ULTIMO EXTRACTO AL 31/08/2025"
            if "saldo ultimo extracto" in lower or "saldo anterior" in lower:
                # Extraer fecha completa DD/MM/YYYY
                fecha_match = re.search(r'(\d{2})[/-](\d{2})[/-](\d{4})', line)
                fecha_str = None
                if fecha_match:
                    d, m, y = fecha_match.groups()
                    fecha_str = f"{d}/{m}/{y}"
                
                # Extraer monto
                monto = self._parse_amount_from_line(line)
                
                if monto is not None:
                    return monto, fecha_str
        
        return None, None
    
    def _extract_saldo_final(self, lines: List[str]) -> Tuple[Optional[float], Optional[str]]:
        """
        Extrae saldo final del extracto CON su fecha.
        Retorna: (monto, fecha_str) o (None, None)
        """
        for line in lines:
            lower = line.lower()
            
            # Buscar "SALDO FINAL AL 30/09/2025" o "(+) SALDO FINAL AL 30/09/2025"
            if "saldo final" in lower:
                # Extraer fecha completa DD/MM/YYYY
                fecha_match = re.search(r'(\d{2})[/-](\d{2})[/-](\d{4})', line)
                fecha_str = None
                if fecha_match:
                    d, m, y = fecha_match.groups()
                    fecha_str = f"{d}/{m}/{y}"
                
                # Extraer monto (el último de la línea)
                monto = self._parse_amount_from_line(line)
                
                if monto is not None:
                    return monto, fecha_str
        
        return None, None
    
    def _parse_movimientos(self, lines: List[str], year: int) -> List[Dict]:
        """
        Parser mejorado para ICBC con mayor tolerancia a OCR defectuoso.
        
        Estrategia:
        1. Primera pasada: captura movimientos con fecha explícita
        2. Segunda pasada: recupera líneas "huérfanas" con keywords o montos válidos
        3. Ordena por índice original del PDF para mantener secuencia
        """
        rows = []
        rows_with_index = []  # 🔧 Para mantener orden original: (row, idx_linea)
        DATE_PATTERN = re.compile(r'\b(\d{2})[-/](\d{2})\b')
        last_fecha = ""
        last_mov_idx = None
        no_date_count = 0
        
        # Keywords que indican movimientos válidos (aunque no tengan fecha)
        MOVEMENT_KEYWORDS = [
            "percepcion", "percepció", "iva", "rg 2408", "rg2408",
            "trans pag prov", "transa pag", "transf", "transferencia",
            "pago cuota", "prestamo", "préstamo",
            "debito", "credito", "crédito",
            "compra", "venta", "extraccion", "extracción",
            "imp.", "retencion", "retención",
            "comision", "comisión", "cargos"
        ]

        def is_header_or_total(s: str) -> bool:
            s = s.lower()
            bad = [
                "fecha concepto", "comprobante", "origen", "canal",
                "resumen", "hoja", "informacion sobre su cuenta",
                "total debitos", "total creditos", "total créditos",
                "subtotal", "servicios", "cuotas", "^total$"
            ]
            return any(k in s for k in bad)

        def has_movement_keyword(s: str) -> bool:
            """Verifica si la línea contiene keywords de movimiento bancario."""
            s = s.lower()
            return any(kw in s for kw in MOVEMENT_KEYWORDS)

        def preprocess_line(line: str) -> str:
            """Pre-limpieza optimizada para OCR ICBC."""
            # Normaliza espacios múltiples
            line = re.sub(r'\s{3,}', '  ', line)
            
            # Separa montos pegados a números (ej: 008803780712324,20 -> 0088037807 12324,20)
            line = re.sub(r'(\d{7,})(\d{1,3}(?:\.\d{3})*,\d{2})', r'\1 \2', line)
            
            # Correcciones OCR específicas de ICBC
            correcciones = {
                "TRANSA PAG PRO V": "TRANS PAG PROV",
                "TRANS PAG PRO V": "TRANS PAG PROV",
                "TRANS PAGPROV": "TRANS PAG PROV",
                "PERCEPCIO N": "PERCEPCION",
                "PERCEPCIÓ N": "PERCEPCION",
                "PAGO CUO TA": "PAGO CUOTA",
                "PRESTA MO": "PRESTAMO",
                "RG240 8": "RG 2408",
                "RG 240 8": "RG 2408",
            }
            for malo, bueno in correcciones.items():
                line = line.replace(malo, bueno)
            
            return line

        # ==== PRIMERA PASADA: Movimientos con fecha explícita ====
        processed_indices = set()
        
        for idx, raw_line in enumerate(lines):
            line = raw_line.strip()
            if len(line) < 10:
                continue
            
            line = preprocess_line(line)
            lower = line.lower()
            
            if is_header_or_total(lower):
                continue
            
            if "saldo final" in lower or "saldo ultimo" in lower or "saldo anterior" in lower:
                continue

            # ¿Hay fecha en esta línea?
            date_match = DATE_PATTERN.search(line)
            
            if date_match:
                d, m = date_match.groups()
                last_fecha = f"{d}/{m}/{year}"
                no_date_count = 0
                processed_indices.add(idx)
            else:
                no_date_count += 1
                if no_date_count > 4:  # Ampliado de 3 a 4
                    last_fecha = ""

            amounts = self._extract_all_amounts(line)
            
            if not amounts:
                continue

            # Si NO hay fecha pero tengo movimiento pendiente sin saldo
            if (
                not date_match and
                last_mov_idx is not None and
                len(amounts) == 1 and
                not any(k in lower for k in ["debito", "crédito", "credito", "transf", "compra", "venta", "pago"])
            ):
                rows[last_mov_idx]["saldo"] = amounts[0]
                last_mov_idx = None
                processed_indices.add(idx)
                continue

            # Para crear movimiento NUEVO exijo fecha (en primera pasada)
            if not date_match or not last_fecha:
                continue

            # Extraer detalle
            first_amount_pos = self._find_first_amount_pos(line)
            fecha_end = date_match.end()
            detalle = line[fecha_end:first_amount_pos].strip() if first_amount_pos > fecha_end else line
            detalle = re.sub(r'\s+', ' ', detalle)
            detalle = re.sub(r'\d{1,3}(?:\.\d{3})*,\d{2}\s?-?', '', detalle)
            detalle = detalle.strip()[:200]

            # Extraer referencia
            ref_match = re.match(r'^(\d{3,10})\s+', line[fecha_end:])
            referencia = ref_match.group(1) if ref_match else ""

            debito, credito, saldo = self._categorize_amounts(amounts)

            new_row = {
                "fecha": last_fecha,
                "detalle": detalle,
                "referencia": referencia,
                "debito": debito,
                "credito": credito,
                "saldo": saldo
            }
            
            rows.append(new_row)
            rows_with_index.append((new_row, idx))  # 🔧 Guardar con índice original

            if saldo == 0.0:
                last_mov_idx = len(rows) - 1
            else:
                last_mov_idx = None

        # ==== SEGUNDA PASADA: Recuperar líneas huérfanas con contenido válido ====
        for idx, raw_line in enumerate(lines):
            if idx in processed_indices:
                continue
            
            line = raw_line.strip()
            if len(line) < 10:
                continue
            
            line = preprocess_line(line)
            lower = line.lower()
            
            if is_header_or_total(lower):
                continue
            
            if "saldo final" in lower or "saldo ultimo" in lower or "saldo anterior" in lower:
                continue
            
            amounts = self._extract_all_amounts(line)
            
            # Para rescatar una línea sin fecha, debe cumplir AL MENOS UNO de:
            # 1. Tener keyword de movimiento + monto
            # 2. Tener 2+ montos (probablemente movimiento + saldo)
            # 3. Tener un monto grande (>1000) + texto descriptivo (>15 chars)
            
            tiene_keyword = has_movement_keyword(lower)
            tiene_montos = len(amounts) > 0
            tiene_monto_grande = any(abs(amt) > 1000 for amt in amounts) if amounts else False
            texto_descriptivo = len(re.sub(r'[\d\s,.\-/]', '', line)) > 15
            
            es_valida = (
                (tiene_keyword and tiene_montos) or
                (len(amounts) >= 2) or
                (tiene_monto_grande and texto_descriptivo)
            )
            
            if not es_valida:
                continue
            
            # Intentar heredar fecha del último movimiento válido
            fecha_heredada = rows[-1]["fecha"] if rows else f"01/{year%100:02d}/{year}"
            
            # Extraer detalle (toda la línea menos los montos)
            first_amount_pos = self._find_first_amount_pos(line)
            detalle = line[:first_amount_pos].strip()
            detalle = re.sub(r'\s+', ' ', detalle)
            detalle = detalle.strip()[:200]
            
            # Buscar posible referencia al inicio
            ref_match = re.match(r'^(\d{3,10})\s+', detalle)
            referencia = ref_match.group(1) if ref_match else ""
            if ref_match:
                detalle = detalle[ref_match.end():].strip()
            
            debito, credito, saldo = self._categorize_amounts(amounts)
            
            new_row = {
                "fecha": fecha_heredada,
                "detalle": detalle,
                "referencia": referencia,
                "debito": debito,
                "credito": credito,
                "saldo": saldo
            }
            
            rows.append(new_row)
            rows_with_index.append((new_row, idx))  # 🔧 Guardar con índice original
            processed_indices.add(idx)

        # 🔧 ORDENAR por índice original del PDF para mantener secuencia
        rows_with_index.sort(key=lambda x: x[1])
        rows = [row for row, _ in rows_with_index]

        return rows
    
    def _parse_amount_from_line(self, line: str) -> Optional[float]:
        """Extrae el último monto de una línea."""
        pattern = r'([\d\.]+,\d{2})'
        matches = re.findall(pattern, line)
        
        if not matches:
            return None
        
        # Tomar el ÚLTIMO monto (suele ser el saldo)
        amount_str = matches[-1]
        clean = amount_str.replace('.', '').replace(',', '.')
        
        try:
            value = float(clean)
            # 🔧 Detectar signo negativo
            if '-' in line[:line.find(amount_str)]:
                return -value
            return value
        except:
            return None
    
    def _extract_all_amounts(self, line: str) -> List[float]:
        """
        Extrae importes estrictos en formato AR:
        9.000,00   -8.500,20   9.000,00-   -200,00
        Requiere SIEMPRE coma y dos decimales (evita confundir refs/fechas).
        Tolera guion al inicio o al final y espacios alrededor del guion.
        """
        amounts: List[float] = []
        # estricto: debe tener ,dd
        pattern = r"(?<!\d)-?\s?\d{1,3}(?:\.\d{3})*,\d{2}\s?-?(?!\d)"
        for m in re.finditer(pattern, line):
            raw = m.group(0)
            negative = raw.strip().startswith('-') or raw.strip().endswith('-')
            clean = raw.replace(' ', '').replace('-', '')
            clean = clean.replace('.', '').replace(',', '.')
            try:
                val = float(clean)
                if negative:
                    val = -val
                amounts.append(val)
            except ValueError:
                continue
        return amounts


    
    def _find_first_amount_pos(self, line: str) -> int:
        """
        Inicio del primer monto (formato estricto con coma).
        """
        m = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}\s?-?", line)
        return m.start() if m else len(line)


    
    def _categorize_amounts(self, amounts: List[float]) -> tuple:
        """
        Clasifica montos ICBC correctamente:
        - 1 monto  → movimiento sin saldo
        - 2 montos → movimiento + saldo
        - 3+ montos → suma todos los previos excepto el último como movimiento, el último como saldo
        """
        debito, credito, saldo = 0.0, 0.0, 0.0
        if not amounts:
            return debito, credito, saldo

        if len(amounts) == 1:
            mov = amounts[0]
            if mov < 0:
                debito = abs(mov)
            else:
                credito = mov
            return debito, credito, saldo

        if len(amounts) == 2:
            mov, sal = amounts
            if mov < 0:
                debito = abs(mov)
            else:
                credito = mov
            saldo = sal
            return debito, credito, saldo

        # más de dos montos
        saldo = amounts[-1]
        movimiento_total = sum(amounts[:-1])
        if movimiento_total < 0:
            debito = abs(movimiento_total)
        else:
            credito = movimiento_total
        return debito, credito, saldo




    def _to_dataframe(self, rows: List[Dict]) -> pd.DataFrame:
        """Convierte a DataFrame final."""
        if not rows:
            return pd.DataFrame(columns=[
                "fecha", "mes", "año", "detalle", "referencia",
                "debito", "credito", "saldo"
            ])
        
        df = pd.DataFrame(rows)
        
        # Parsear fechas
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
        df["mes"] = df["fecha"].dt.month.fillna(0).astype(int)
        df["año"] = df["fecha"].dt.year.fillna(0).astype(int)
        df["fecha"] = df["fecha"].dt.strftime("%d/%m/%Y").fillna("")
        
        return df[[
            "fecha", "mes", "año", "detalle", "referencia",
            "debito", "credito", "saldo"
        ]]