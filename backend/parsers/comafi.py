import re
import pandas as pd
from datetime import datetime

class ComafiParser:
    """Parser limpio para Banco Comafi - elimina información no pertinente y saldos repetidos"""

    BANK_NAME = "COMAFI"
    DETECTION_KEYWORDS = ["COMAFI"]

    def detect(self, text: str, filename: str = "") -> bool:
        return "COMAFI" in f"{text} {filename}".upper()

    def parse(self, raw_data, filename: str = ""):
        # Obtener líneas desde el orquestador
        if isinstance(raw_data, dict):
            lines = raw_data.get("text_lines", []) or raw_data.get("text_lines_raw", [])
        elif isinstance(raw_data, list):
            lines = raw_data
        elif isinstance(raw_data, str):
            lines = raw_data.splitlines()
        else:
            lines = []

        # Limpiar líneas base
        lines = [re.sub(r"\s{2,}", " ", l.strip()) for l in lines if l and str(l).strip()]

        # 🔎 DEBUG: dump de líneas crudas ya limpias
        print("\n===== DEBUG COMAFI RAW LINES =====")
        for i, l in enumerate(lines):
            print(f"{i:02d}: {repr(l)}")
        print("==================================\n")

        # -------------------------------------------------------
        # 1) Recorte del bloque de movimientos correcto (PESOS)
        # -------------------------------------------------------
        movimientos = []
        en_bloque = False
        bloque_pesos_cerrado = False

        for line in lines:
            up = line.upper().strip()

            # INICIO de bloque válido (cabecera o encabezado de tabla)
            if not en_bloque:
                if ("DETALLE DE MOVIMIENTOS" in up) or re.match(r"^FECHA\s+CONCEPTOS", up):
                    if not bloque_pesos_cerrado:
                        en_bloque = True
                    continue
                else:
                    continue

            # FIN del bloque válido (cambio de sección / producto)
            if any(pat in up for pat in [
                "IMPUESTOS DEBITADOS EN EL PERIODO",
                "IMPUESTOS DEBITADOS EN EL PERÍODO",
                "CUENTA CORRIENTE ESPECIAL",
                "COMAFI EMPRESAS CLASSIC CUENTA CORRIENTE ESPECIAL",
                "CUENTA CORRIENTE ESPECIAL EN DOLARES",
                "CUENTA CORRIENTE ESPECIAL EN DÓLARES",
                "TRANSFERENCIAS ELECTRONICAS",
                "TRANSFERENCIAS ELECTRÓNICAS",
            ]):
                en_bloque = False
                bloque_pesos_cerrado = True
                continue

            # Filtrar basura evidente dentro del bloque
            if any(x in up for x in [
                "SE RUEGA FORMULAR", "LOS DEPOSITOS EN PESOS", "LOS DEPÓSITOS EN PESOS",
                "LEY 26.361", "CIRCULAR OPASI", "BENEFICIOS FISCALES",
                "BASE IMPONIBLE", "TOTAL AL:", "NRO.", "NÚMERO", "CBU:",
                "SIN MOVIMIENTOS"
            ]):
                continue

            # Criterios de inclusión al bloque de movimientos
            tiene_fecha = bool(re.search(r"\d{2}/\d{2}/\d{2,4}", line))
            es_saldo = "SALDO" in up
            tiene_referencia_larga = bool(re.search(r"\b\d{10,}\b", line))
            tiene_monto = bool(re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", line))
            subdetalle_keyword = bool(re.match(r"^\s*(SERVICIOS|INTEL|SOLUCIONES|Y\s+SOLUCIONES)\b", line, re.IGNORECASE))

            if not (tiene_fecha or es_saldo or tiene_referencia_larga or tiene_monto or subdetalle_keyword):
                continue

            movimientos.append(line)

        # 🔎 DEBUG: qué quedó como movimiento
        print("\n===== DEBUG MOVIMIENTOS DETECTADOS =====")
        for i, l in enumerate(movimientos):
            print(f"{i:02d}: {repr(l)}")
        print("========================================\n")

        if not movimientos:
            # No hay nada que parsear
            return pd.DataFrame(columns=["fecha","detalle","referencia","debito","credito","saldo","mes","año","moneda"])

        # -------------------------------------------------------
        # 2) Unificar renglones partidos (p.ej., subdetalle INTEL)
        #    Una línea sin fecha al inicio se concatena a la anterior
        # -------------------------------------------------------
        movimientos_unidos = []
        buffer = ""
        
        for line in movimientos:
            # Normalizar primero (corrige espacios en montos)
            line_norm = self._normalize_numbers(line)
            
            # Si la línea empieza con fecha, es un movimiento nuevo
            if re.match(r"^\d{2}/\d{2}/\d{2,4}\b", line_norm):
                # Guardar el buffer anterior si existe
                if buffer:
                    movimientos_unidos.append(buffer.strip())
                buffer = line_norm
            else:
                # Si no empieza con fecha pero es "Saldo al:" o similar, cerrar buffer y agregar por separado
                up = line_norm.upper()
                if "SALDO AL" in up or "SALDO ANTERIOR" in up:
                    if buffer:
                        movimientos_unidos.append(buffer.strip())
                        buffer = ""
                    movimientos_unidos.append(line_norm)
                else:
                    # Es continuación del movimiento anterior
                    if buffer:
                        buffer += " " + line_norm
                    else:
                        # Línea suelta sin contexto (raro, pero incluir)
                        buffer = line_norm

        # Agregar el último buffer
        if buffer:
            movimientos_unidos.append(buffer.strip())

        movimientos = movimientos_unidos

        # 🔎 DEBUG: movimientos luego de unir sublíneas
        print("\n===== DEBUG MOVIMIENTOS UNIDOS =====")
        for i, l in enumerate(movimientos):
            print(f"{i:02d}: {repr(l)}")
        print("====================================\n")

        # Diccionarios de clasificación forzada
        FORCE_DEBIT = [
            "IMPUESTO", "IVA", "PERCEPCION", "PERCEPCIÓN", "DEBITO", "DÉBITO",
            "SERVICIO", "TASA", "CANON", "LEASING", "MANTENIMIENTO", "COMISION", 
            "COMISIÓN", "COBRO DE CANON"
        ]
        FORCE_CREDIT = [
            "TRANSFERENCIA RECIBIDA", "SERVICIOS Y SOLUCIONES",
            "ACREDITACION", "ACREDITACIÓN", "DEPOSITO", "DEPÓSITO", 
            "DEVOLUCION", "DEVOLUCIÓN"
        ]

        # -------------------------------------------------------
        # 3) Parseo línea a línea
        # -------------------------------------------------------
        data = []
        saldo_anterior_agregado = False
        saldo_final_agregado = False

        for line in movimientos:
            # La línea ya viene normalizada del paso anterior
            fecha = self._extract_fecha(line)
            
            # Extraer montos (ya normalizados)
            montos_raw = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", line)
            montos = [self._to_float(m) for m in montos_raw]

            # Detalle limpio (sin montos ni fecha)
            detalle = line
            for m in montos_raw:
                detalle = detalle.replace(m, "")
            detalle = re.sub(r"\d{2}/\d{2}/\d{2,4}", "", detalle)
            detalle = re.sub(r"\s{2,}", " ", detalle).strip()

            # Referencia larga (10+ dígitos)
            referencia = ""
            ref_match = re.search(r"\b(\d{10,})\b", detalle)
            if ref_match:
                referencia = ref_match.group(1)
                detalle = re.sub(r"\b" + re.escape(referencia) + r"\b", "", detalle).strip()
                detalle = re.sub(r"\s{2,}", " ", detalle).strip()

            up = detalle.upper()

            # Tipos de saldo
            es_saldo_ini = "SALDO ANTERIOR" in up
            es_saldo_fin = "SALDO FINAL" in up or "SALDO AL" in up
            
            # "Saldo al: …" → forzar como Saldo Final
            if "SALDO AL" in up:
                detalle = "Saldo Final"
                es_saldo_fin = True

            # Clasificación forzada (débito vs crédito)
            es_deb = any(k in up for k in FORCE_DEBIT)
            es_cre = any(k in up for k in FORCE_CREDIT)
            if es_deb and es_cre:
                # Si dice "Transferencia recibida", priorizar crédito
                if "TRANSFERENCIA RECIBIDA" in up:
                    es_deb = False
                else:
                    es_cre = False  # prioriza débito

            # Inicializar montos
            deb, cre, sal = 0.0, 0.0, 0.0

            # Si la línea es de saldo, no debe tener débitos/créditos
            if es_saldo_ini or es_saldo_fin:
                deb = 0.0
                cre = 0.0

            # -------------------------------------------------------
            # Asignar montos según cantidad encontrada
            # -------------------------------------------------------
            if len(montos) == 1:
                m = montos[0]
                if es_saldo_ini:
                    # Solo el primer Saldo Anterior válido (>0)
                    if saldo_anterior_agregado or abs(m) < 0.01:
                        continue
                    detalle = "Saldo Anterior"
                    sal = m
                    saldo_anterior_agregado = True

                elif es_saldo_fin:
                    # Solo el primer Saldo Final válido (>0)
                    if saldo_final_agregado or abs(m) < 0.01:
                        continue
                    detalle = "Saldo Final"
                    sal = m
                    saldo_final_agregado = True

                elif es_cre:
                    cre = m
                elif es_deb:
                    deb = m
                else:
                    # Default: débito para 1 monto no identificado
                    deb = m

            elif len(montos) == 2:
                # Típico: importe + saldo
                imp, sal = montos
                if es_saldo_ini or es_saldo_fin:
                    # Si es saldo, ignorar imp y tomar solo sal
                    deb = cre = 0.0
                else:
                    # Asignar el importe según clasificación
                    if es_cre:
                        cre = imp
                    elif es_deb:
                        deb = imp
                    else:
                        # Heurísticas adicionales
                        if any(x in up for x in ["COBRO DE CANON", "LEASING", "CANON LEAS"]):
                            deb = imp
                        elif "SERVICIOS Y SOLUCIONES" in up:
                            cre = imp
                        else:
                            # Default: débito
                            deb = imp

            elif len(montos) >= 3:
                # Formato con 3 columnas: débito, crédito, saldo
                deb, cre, sal = montos[-3:]

            # Validaciones finales
            if not detalle or len(detalle) < 3:
                continue
            if any(x in up for x in ["SIN MOVIMIENTOS", "CAPTADOS A TASA"]):
                continue

            data.append({
                "fecha": fecha,
                "detalle": detalle.strip(),
                "referencia": referencia,
                "debito": round(deb, 2),
                "credito": round(cre, 2),
                "saldo": round(sal, 2),
                "mes": fecha.month if fecha else None,
                "año": fecha.year if fecha else None,
                "moneda": "ARS",
            })

        df = pd.DataFrame(data)
        if df.empty:
            return df

        # Eliminar duplicados exactos (por seguridad)
        df = df.drop_duplicates(subset=["detalle", "fecha", "debito", "credito", "saldo"], keep='first')

        # Ordenar por fecha (solo las que tienen fecha)
        df_sin_fecha = df[df['fecha'].isna()].copy()
        df_con_fecha = df[df['fecha'].notna()].copy()
        if not df_con_fecha.empty:
            df_con_fecha = df_con_fecha.sort_values('fecha').reset_index(drop=True)

        # Reconstruir: Saldo Anterior (si existe) + movimientos + Saldo Final (si existe)
        frames = []
        saldo_ant = df_sin_fecha[df_sin_fecha['detalle'].str.upper() == 'SALDO ANTERIOR']
        saldo_fin = df_sin_fecha[df_sin_fecha['detalle'].str.upper() == 'SALDO FINAL']

        if not saldo_ant.empty:
            frames.append(saldo_ant.iloc[[0]])
        if not df_con_fecha.empty:
            frames.append(df_con_fecha)
        if not saldo_fin.empty:
            frames.append(saldo_fin.iloc[[0]])

        if frames:
            df = pd.concat(frames, ignore_index=True)

        # 🔎 DEBUG: DF final
        print("\n===== DEBUG DATAFRAME FINAL =====")
        try:
            print(df.to_string())
        except Exception:
            print(df.head())
        print("=================================\n")

        # -------------------------------------------------------
        # Validaciones inline (casos de prueba)
        # -------------------------------------------------------
        print("\n===== VALIDACIONES =====")
        
        # 1. Verificar que no hay montos en detalle
        for idx, row in df.iterrows():
            if re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", str(row['detalle'])):
                print(f"⚠️  Fila {idx}: monto en detalle: {row['detalle']}")
        
        # 2. Verificar saldos únicos
        saldo_ant_count = len(df[df['detalle'].str.upper() == 'SALDO ANTERIOR'])
        saldo_fin_count = len(df[df['detalle'].str.upper() == 'SALDO FINAL'])
        print(f"✓ Saldo Anterior: {saldo_ant_count} (esperado: 1)")
        print(f"✓ Saldo Final: {saldo_fin_count} (esperado: 1)")
        
        # 3. Verificar casos específicos
        transferencia = df[df['detalle'].str.contains('SERVICIOS Y SOLUCIONES', case=False, na=False)]
        if not transferencia.empty:
            t = transferencia.iloc[0]
            print(f"✓ Transferencia: credito={t['credito']} (esperado: 1300000.00)")
        
        comision = df[df['detalle'].str.contains('Comisión Mantenimiento', case=False, na=False)]
        if not comision.empty:
            c = comision.iloc[0]
            print(f"✓ Comisión: debito={c['debito']} (esperado: 49082.00)")
        
        print("========================\n")

        return df

    # --------------------- Helpers ---------------------

    def _normalize_numbers(self, line: str) -> str:
        """
        Normaliza espacios en números para que el OCR ruidoso no afecte la extracción.
        Ejemplos:
          "49.082 ,00" → "49.082,00"
          "10. 307,22" → "10.307,22"
          "1.300.000, 00" → "1.300.000,00"
        """
        # Quitar espacio entre punto de miles y los 3 dígitos siguientes
        line = re.sub(r"(?<=\d)\.\s+(?=\d{3}\b)", ".", line)
        
        # Quitar espacio antes de la coma decimal
        line = re.sub(r"\s+(?=,\d{2}\b)", "", line)
        
        # Quitar espacio después de la coma decimal
        line = re.sub(r"(?<=,)\s+(?=\d{2}\b)", "", line)
        
        # Colapsar múltiples espacios
        line = re.sub(r"\s{2,}", " ", line)
        
        return line.strip()

    def _extract_fecha(self, line):
        """Extrae fecha en formato dd/mm/yy o dd/mm/yyyy"""
        f = re.search(r"(\d{2}/\d{2}/\d{2,4})", line)
        if not f:
            return None
        for fmt in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(f.group(1), fmt)
            except:
                continue
        return None

    def _to_float(self, t: str) -> float:
        """Convierte string con formato argentino a float"""
        try:
            return float(t.replace(".", "").replace(",", "."))
        except:
            return 0.0