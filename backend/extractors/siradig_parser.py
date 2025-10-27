# -*- coding: utf-8 -*-
"""
Parser de tablas SIRADIG - Versión híbrida (tablas + regex)
------------------------------------------------------------
Parser robusto que intenta primero tablas, luego regex como fallback.
"""

import re
import pandas as pd
import pdfplumber
from pathlib import Path
import logging
logger = logging.getLogger(__name__)


def extraer_texto_completo(pdf_path):
    """Extrae todo el texto del PDF con pdfplumber."""
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            texto = page.extract_text() or ""
            texto_completo += texto + "\n"
    return texto_completo


def extraer_todas_tablas(pdf_path):
    """Extrae todas las tablas del PDF."""
    todas_tablas = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            tablas = page.extract_tables()
            if tablas:
                for j, tabla in enumerate(tablas):
                    todas_tablas.append({
                        'pagina': i + 1,
                        'tabla_num': j + 1,
                        'datos': tabla
                    })
    return todas_tablas


def extraer_cuil_nombre(texto):
    """Extrae CUIL y Nombre del ENCABEZADO."""
    cuil = ""
    nombre = ""
    
    match_cuil = re.search(r"(?:CUIL|CUIT)[:\s]+(\d{11})", texto, re.MULTILINE)
    if match_cuil:
        cuil = match_cuil.group(1)
    
    match_nombre = re.search(
        r"Apellido y Nombre[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s,.-]+?)(?:\n|Domicilio)",
        texto,
        re.MULTILINE | re.IGNORECASE
    )
    if match_nombre:
        nombre = match_nombre.group(1).strip()
    
    logger.debug(f"CUIL extraido: {cuil}")
    logger.debug(f"Nombre extraido: {nombre}")
    
    return cuil, nombre


def extraer_secciones(texto):
    """Divide el texto en secciones basándose en los títulos numerados."""
    secciones = {}
    
    patron_seccion = re.compile(r"^([1-5])\s*[-–—]\s*(.*?)$", re.MULTILINE)
    matches = list(patron_seccion.finditer(texto))
    
    for i, match in enumerate(matches):
        num_seccion = match.group(1)
        inicio = match.end()
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        contenido_seccion = texto[inicio:fin]
        
        nombres_estandar = {
            "1": "Detalles de las cargas de familia",
            "2": "Importe de las ganancias liquidadas en el transcurso del período fiscal por otros empleadores o entidades",
            "3": "Deducciones y desgravaciones",
            "4": "Otras Retenciones, Percepciones y Pagos a Cuenta",
            "5": "Beneficios"
        }
        
        seccion_std = nombres_estandar.get(num_seccion, match.group(2).strip())
        secciones[seccion_std] = contenido_seccion
        
        logger.debug(f"Seccion {num_seccion} extraida: {seccion_std} ({len(contenido_seccion)} caracteres)")
    
    return secciones


def procesar_cargas_con_tablas(tablas):
    """Intenta extraer cargas familiares de las tablas extraídas."""
    registros = []
    
    for tabla_info in tablas:
        tabla = tabla_info['datos']
        if not tabla or len(tabla) < 2:
            continue
        
        # Verificar si es tabla de cargas familiares
        encabezados = [str(cell).lower() if cell else "" for cell in tabla[0]]
        encabezados_texto = " ".join(encabezados)
        
        if not ("apellido" in encabezados_texto and "parentesco" in encabezados_texto):
            continue
        
        logger.debug(f"Tabla de cargas encontrada - Encabezados: {tabla[0]}")
        
        # Identificar índices de columnas
        idx_nombre = -1
        idx_fecha = -1
        idx_periodo = -1
        idx_documento = -1
        idx_parentesco = -1
        idx_porcentaje = -1
        
        for i, enc in enumerate(encabezados):
            enc_lower = enc.lower()
            if "apellido" in enc_lower or "nombre" in enc_lower:
                idx_nombre = i
            elif "fecha" in enc_lower:
                idx_fecha = i
            elif "periodo" in enc_lower or "período" in enc_lower:
                idx_periodo = i
            elif "documento" in enc_lower or "tipo" in enc_lower:
                idx_documento = i
            elif "parentesco" in enc_lower:
                idx_parentesco = i
            elif "deducción" in enc_lower or "%" in enc_lower:
                idx_porcentaje = i
        
        logger.debug(f"Indices: nombre={idx_nombre}, fecha={idx_fecha}, periodo={idx_periodo}, doc={idx_documento}, parentesco={idx_parentesco}, %={idx_porcentaje}")
        
        # Procesar filas de datos
        for fila in tabla[1:]:
            if not fila or len(fila) < 4:
                continue
            
            # Extraer por índice identificado
            apellido_nombre = str(fila[idx_nombre]).strip() if idx_nombre >= 0 and idx_nombre < len(fila) and fila[idx_nombre] else ""
            fecha_nac = str(fila[idx_fecha]).strip() if idx_fecha >= 0 and idx_fecha < len(fila) and fila[idx_fecha] else ""
            periodo = str(fila[idx_periodo]).strip() if idx_periodo >= 0 and idx_periodo < len(fila) and fila[idx_periodo] else "Enero - Diciembre"
            doc_info = str(fila[idx_documento]).strip() if idx_documento >= 0 and idx_documento < len(fila) and fila[idx_documento] else ""
            parentesco = str(fila[idx_parentesco]).strip() if idx_parentesco >= 0 and idx_parentesco < len(fila) and fila[idx_parentesco] else ""
            porcentaje = str(fila[idx_porcentaje]).strip() if idx_porcentaje >= 0 and idx_porcentaje < len(fila) and fila[idx_porcentaje] else ""
            
            # Extraer CUIL del documento
            cuil_carga = ""
            if doc_info:
                match_cuil = re.search(r"(\d{11})", doc_info)
                if match_cuil:
                    cuil_carga = match_cuil.group(1)
            
            # Limpiar valores "None"
            if apellido_nombre == "None":
                apellido_nombre = ""
            if fecha_nac == "None":
                fecha_nac = ""
            if periodo == "None":
                periodo = "Enero - Diciembre"
            if parentesco == "None":
                parentesco = ""
            if porcentaje == "None":
                porcentaje = ""
            
            # Validar que tengamos datos mínimos
            if apellido_nombre and parentesco:
                registros.append({
                    "apellido_nombre": apellido_nombre,
                    "fecha_nac": fecha_nac,
                    "cuil_carga": cuil_carga,
                    "parentesco": parentesco,
                    "periodo": periodo,
                    "porcentaje": porcentaje
                })
                logger.debug(f"  -> Carga extraida (tabla): {apellido_nombre} ({cuil_carga}) - {parentesco} - {porcentaje}")
    
    return registros


def procesar_cargas_con_regex_v2(contenido):
    """
    Versión mejorada que parsea cada línea que contiene CUIL.
    """
    registros = []
    
    if re.search(r"(No se informaron?|Ninguno)\.?", contenido, re.I):
        return registros
    
    # Dividir en líneas
    lineas = contenido.split('\n')
    
    # Buscar todas las líneas que contengan CUIL
    indices_cuil = []
    for i, linea in enumerate(lineas):
        if re.search(r'CUIL\s+\d{11}', linea):
            indices_cuil.append(i)
    
    logger.debug(f"  -> Encontrados {len(indices_cuil)} CUILs en el texto")
    
    # Procesar cada CUIL encontrado
    for idx_cuil in indices_cuil:
        linea_cuil = lineas[idx_cuil]
        
        # DEBUG: Mostrar línea completa
        logger.debug(f"\n{'='*60}")
        logger.debug(f"Procesando línea {idx_cuil}: {linea_cuil}")
        logger.debug(f"{'='*60}")
        
        # ESTRATEGIA: TODO está en la misma línea, parsear de izquierda a derecha
        
        # 1. Extraer CUIL
        match_cuil = re.search(r'CUIL\s+(\d{11})', linea_cuil)
        if not match_cuil:
            continue
        cuil_carga = match_cuil.group(1)
        cuil_pos = match_cuil.start()  # Posición del CUIL en la línea
        
        # 2. Extraer lo que está ANTES del CUIL (contiene: Nombre + Fecha)
        texto_antes_cuil = linea_cuil[:cuil_pos].strip()
        
        # 3. Extraer fecha de nacimiento (último patrón de fecha antes del CUIL)
        fechas = re.findall(r'\d{2}/\d{2}/\d{4}', texto_antes_cuil)
        fecha_nac = fechas[-1] if fechas else ""  # Tomar la última fecha encontrada
        
        # 4. Extraer nombre (todo lo que está antes de la fecha)
        if fecha_nac:
            apellido_nombre = texto_antes_cuil.split(fecha_nac)[0].strip()
        else:
            # Si no hay fecha, todo el texto antes del CUIL es el nombre
            apellido_nombre = texto_antes_cuil.strip()
        
        # Limpiar nombre (quitar espacios múltiples)
        apellido_nombre = re.sub(r'\s+', ' ', apellido_nombre)
        
        # Si el nombre está vacío o es muy corto, marcarlo
        if len(apellido_nombre) < 3:
            apellido_nombre = "NOMBRE NO DETECTADO"
        
        # 5. Extraer lo que está DESPUÉS del CUIL (contiene: Parentesco + Porcentaje)
        texto_despues_cuil = linea_cuil[match_cuil.end():].strip()
        
        # 6. Extraer parentesco
        match_parentesco = re.search(
            r'(Unión convivencial|Hijo/?a?\s+menor\s+de\s+18\s+años|Hijastro/?a?\s+menor\s+de\s+18\s+años|Hijo/?a?\s+incapacitado|Cónyuge)',
            texto_despues_cuil,
            re.IGNORECASE
        )
        parentesco = re.sub(r'\s+', ' ', match_parentesco.group(1).strip()) if match_parentesco else "Parentesco no detectado"
        
        # 7. Extraer porcentaje
        match_porcentaje = re.search(r'(\d+)\s*%', texto_despues_cuil)
        porcentaje = match_porcentaje.group(1) + "%" if match_porcentaje else "100%"
        
        # 8. Extraer período (buscar en líneas adyacentes)
        inicio = max(0, idx_cuil - 3)
        fin = min(len(lineas), idx_cuil + 3)
        contexto = '\n'.join(lineas[inicio:fin])
        
        # Buscar período completo (puede estar en la línea anterior o en líneas siguientes)
        match_periodo = re.search(
            r'(Enero\s*-\s*Diciembre(?:\s+y\s+próx(?:imos)?\.\s+períodos(?:\s+hasta\s+\d{2}/\d{2}/\d{4})?)?)',
            contexto,
            re.IGNORECASE
        )
        periodo = re.sub(r'\s+', ' ', match_periodo.group(1).strip()) if match_periodo else "Enero - Diciembre"
        
        # Formatear salida
        concepto_formateado = f"{apellido_nombre} | CUIL: {cuil_carga} | Nac: {fecha_nac} | {parentesco} | {periodo} | {porcentaje}"
        
        registros.append({
            "apellido_nombre": apellido_nombre,
            "fecha_nac": fecha_nac,
            "cuil_carga": cuil_carga,
            "parentesco": parentesco,
            "periodo": periodo,
            "porcentaje": porcentaje,
            "concepto_formateado": concepto_formateado
        })
        
        logger.debug(f"  ✓ Nombre: {apellido_nombre}")
        logger.debug(f"  ✓ Fecha Nac: {fecha_nac}")
        logger.debug(f"  ✓ CUIL: {cuil_carga}")
        logger.debug(f"  ✓ Parentesco: {parentesco}")
        logger.debug(f"  ✓ Período: {periodo}")
        logger.debug(f"  ✓ Porcentaje: {porcentaje}")
        logger.debug(f"  -> Carga extraida: {concepto_formateado}\n")
    
    logger.info(f"  -> {len(registros)} cargas familiares extraidas (via regex mejorado)")
    return registros

def procesar_seccion_cargas_familiares(contenido, tablas):
    """
    Procesa cargas familiares usando enfoque híbrido:
    1. Intenta con tablas
    2. Si falla, usa regex mejorado
    """
    # Intento 1: Tablas
    registros = procesar_cargas_con_tablas(tablas)
    
    if registros:
        logger.info(f"  -> {len(registros)} cargas familiares extraidas (via tablas)")
        # AGREGAR concepto_formateado si viene de tablas
        for reg in registros:
            if 'concepto_formateado' not in reg:
                reg['concepto_formateado'] = f"{reg['apellido_nombre']} | CUIL: {reg['cuil_carga']} | Nac: {reg['fecha_nac']} | {reg['parentesco']} | {reg['periodo']} | {reg['porcentaje']}"
        return registros
    
    # Intento 2: Regex mejorado
    registros = procesar_cargas_con_regex_v2(contenido)
    
    if registros:
        logger.info(f"  -> {len(registros)} cargas familiares extraidas (via regex mejorado)")
    else:
        logger.info(f"  -> 0 cargas familiares extraidas")
    
    return registros


def procesar_seccion_deducciones(contenido):
    """Procesa deducciones usando regex (funciona bien actualmente)."""
    registros = []
    
    if re.search(r"(No se informaron?|Ninguno)\.?", contenido, re.I):
        return registros
    
    # Detectar conceptos principales
    patron_concepto = re.compile(
        r"(Gastos\s+de\s+Educación|"
        r"Cuotas\s+Médico\s+Asistenciales|"
        r"Gastos\s+de\s+Adquisición\s+de\s+Indumentaria[^\$\n]*?|"
        r"Beneficios\s+para\s+Locatarios[^\$\n]*?)\s+"
        r"\$\s*([\d.,]+)",
        re.MULTILINE | re.IGNORECASE | re.DOTALL
    )
    
    conceptos = []
    for match in patron_concepto.finditer(contenido):
        concepto = re.sub(r'\s+', ' ', match.group(1).strip())
        monto_total = match.group(2)
        
        if not any(c['concepto'] == concepto for c in conceptos):
            conceptos.append({
                "concepto": concepto,
                "monto_total": monto_total,
                "inicio": match.start(),
                "fin": match.end()
            })
    
    conceptos.sort(key=lambda x: x['inicio'])
    
    # Para cada concepto, extraer períodos
    for i, info in enumerate(conceptos):
        concepto = info['concepto']
        
        registros.append({
            "concepto": concepto,
            "periodo": "NA",
            "cantidad": "",
            "monto_unitario": "NA",
            "monto_total": info["monto_total"]
        })
        
        inicio_busqueda = info["fin"]
        fin_busqueda = conceptos[i + 1]["inicio"] if i + 1 < len(conceptos) else len(contenido)
        texto_detalle = contenido[inicio_busqueda:fin_busqueda]
        
        patron_periodo = re.compile(
            r"(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre)"
            r"(?:\s*-\s*(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre))?"
            r"(?:\s+(\d+)\s*x)?"
            r"(?:\s+\$)?\s*([\d.,]+)"
            r"(?:\s+\$\s*([\d.,]+))?",
            re.MULTILINE
        )
        
        for match in patron_periodo.finditer(texto_detalle):
            periodo = match.group(1)
            if match.group(2):
                periodo += f" - {match.group(2)}"
            
            cantidad = f"x{match.group(3)}" if match.group(3) else ""
            
            if match.group(5):
                monto_unitario = match.group(4)
                monto_total_periodo = match.group(5)
            else:
                monto_unitario = ""
                monto_total_periodo = match.group(4)
            
            registros.append({
                "concepto": concepto,
                "periodo": periodo,
                "cantidad": cantidad,
                "monto_unitario": monto_unitario,
                "monto_total": monto_total_periodo
            })
    
    logger.info(f"  -> {len(registros)} registros de deducciones extraidos")
    return registros


def procesar_pdf(pdf_path):
    """Procesa un PDF completo usando enfoque híbrido."""
    archivo = Path(pdf_path).name
    logger.info(f"Procesando {archivo}")
    
    # Extraer texto y tablas
    texto = extraer_texto_completo(pdf_path)
    tablas = extraer_todas_tablas(pdf_path)
    
    logger.debug(f"Texto extraido: {len(texto)} caracteres")
    logger.debug(f"Tablas encontradas: {len(tablas)}")
    
    # Extraer CUIL y Nombre
    cuil, nombre = extraer_cuil_nombre(texto)
    
    if not cuil:
        logger.warning(f"No se pudo extraer CUIL de {archivo}")
        return pd.DataFrame()
    
    # Dividir en secciones
    secciones = extraer_secciones(texto)
    
    if not secciones:
        logger.warning(f"No se detectaron secciones en {archivo}")
        return pd.DataFrame()
    
    registros = []
    
    # Secciones esperadas
    secciones_esperadas = [
        "Detalles de las cargas de familia",
        "Importe de las ganancias liquidadas en el transcurso del período fiscal por otros empleadores o entidades",
        "Deducciones y desgravaciones",
        "Otras Retenciones, Percepciones y Pagos a Cuenta",
        "Beneficios"
    ]
    
    for nombre_seccion in secciones_esperadas:
        contenido = secciones.get(nombre_seccion, "")
        
        # Verificar si está vacía
        if not contenido.strip() or re.search(r"(No se informaron?|Ninguno)\.?", contenido, re.I):
            registros.append({
                "LEGAJO": "",
                "CUIL": cuil,
                "Nombre y Apellido": nombre,
                "Seccion": nombre_seccion,
                "Concepto": "-",
                "Periodo": "NA",
                "Cantidad": "",
                "Monto unitario": "NA",
                "Monto total": "NA",
                "Archivo": archivo
            })
            logger.debug(f"Seccion '{nombre_seccion}' vacia o sin datos")
            continue
        
        # Procesar según tipo
        if nombre_seccion == "Detalles de las cargas de familia":
            cargas = procesar_seccion_cargas_familiares(contenido, tablas)
            
            if not cargas:
                registros.append({
                    "LEGAJO": "",
                    "CUIL": cuil,
                    "Nombre y Apellido": nombre,
                    "Seccion": nombre_seccion,
                    "Concepto": "-",
                    "Periodo": "NA",
                    "Cantidad": "",
                    "Monto unitario": "NA",
                    "Monto total": "NA",
                    "Archivo": archivo
                })
            else:
                for carga in cargas:
                    # USAR EL CONCEPTO FORMATEADO COMPLETO
                    concepto_completo = carga.get('concepto_formateado', 
                        f"{carga['apellido_nombre']} | CUIL: {carga['cuil_carga']} | Nac: {carga['fecha_nac']} | {carga['parentesco']} | {carga['periodo']} | {carga['porcentaje']}")
                    
                    registros.append({
                        "LEGAJO": "",
                        "CUIL": cuil,
                        "Nombre y Apellido": nombre,
                        "Seccion": nombre_seccion,
                        "Concepto": concepto_completo,
                        "Periodo": carga['periodo'],
                        "Cantidad": "",
                        "Monto unitario": "",
                        "Monto total": carga['porcentaje'],
                        "Archivo": archivo
                    })
        
        elif nombre_seccion in ["Deducciones y desgravaciones", "Beneficios"]:
            detalles = procesar_seccion_deducciones(contenido)
            
            if not detalles:
                registros.append({
                    "LEGAJO": "",
                    "CUIL": cuil,
                    "Nombre y Apellido": nombre,
                    "Seccion": nombre_seccion,
                    "Concepto": "-",
                    "Periodo": "NA",
                    "Cantidad": "",
                    "Monto unitario": "NA",
                    "Monto total": "NA",
                    "Archivo": archivo
                })
            else:
                for detalle in detalles:
                    registros.append({
                        "LEGAJO": "",
                        "CUIL": cuil,
                        "Nombre y Apellido": nombre,
                        "Seccion": nombre_seccion,
                        "Concepto": detalle['concepto'],
                        "Periodo": detalle['periodo'],
                        "Cantidad": detalle['cantidad'],
                        "Monto unitario": detalle['monto_unitario'],
                        "Monto total": detalle['monto_total'],
                        "Archivo": archivo
                    })
        
        else:
            registros.append({
                "LEGAJO": "",
                "CUIL": cuil,
                "Nombre y Apellido": nombre,
                "Seccion": nombre_seccion,
                "Concepto": "-",
                "Periodo": "NA",
                "Cantidad": "",
                "Monto unitario": "NA",
                "Monto total": "NA",
                "Archivo": archivo
            })
    
    df_final = pd.DataFrame(registros)
    
    if df_final.empty:
        logger.warning(f"No se extrajeron datos de {archivo}")
    else:
        logger.info(f"{len(df_final)} registros totales extraidos de {archivo}")
    
    return df_final