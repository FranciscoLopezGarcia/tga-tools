# -*- coding: utf-8 -*-
import os
import re
import logging
from itertools import zip_longest
from datetime import datetime

logger = logging.getLogger(__name__)

DEBUG_DIR = "/app/debug_galicia"
os.makedirs(DEBUG_DIR, exist_ok=True)

# -----------------------
# Regex tolerantes (OCR)
# -----------------------
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{2}$")  # dd/mm/yy
AMT_GENERIC_RE = re.compile(r"\d{1,3}(?:[ .]\d{3})*,\d{2}")  # permite espacio o punto como miles
AMT_DEBIT_RE = re.compile(r"^-?\d{1,3}(?:[ .]\d{3})*,\d{2}$")  # débito: exige signo si viene negativo
AMT_SALDO_RE = re.compile(r"^-?\d{1,3}(?:[ .]\d{3})*,\d{2}-?$")  # saldo: permite - al inicio o al final

_saved_pages = set()

def _debug_save_page_text(page_idx, raw_text):
    """Guarda texto OCR crudo para diagnóstico (solo una vez por página)."""
    try:
        if page_idx in _saved_pages:
            return
        path = os.path.join(DEBUG_DIR, f"page_{page_idx}_ocr.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw_text)
        _saved_pages.add(page_idx)
        logger.info(f"[DEBUG] Guardado OCR crudo de página {page_idx} → {path}")
    except Exception as e:
        logger.warning(f"[DEBUG] No se pudo guardar OCR de página {page_idx}: {e}")

def _sanitize_line(s: str) -> str:
    """Normaliza pequeñas corrupciones de OCR sin alterar contenido."""
    if not s:
        return s
    s = s.replace("\u00A0", " ")  # NBSP → espacio
    s = re.sub(r"\s+", " ", s).strip()

    # Normaliza encabezados frecuentes mal leídos
    s_upper = s.upper()
    if s_upper.startswith("SA1DO"):
        s = "Saldo"
    elif s_upper.startswith("SALDO"):
        s = "Saldo"
    elif s_upper.startswith("PAGINA"):
        s = re.sub(r"(?i)^PAGINA", "Página", s)

    # Repara importes con espacio como miles: "338 849,56" → "338.849,56"
    s = re.sub(r"(?<=\d)\s(?=\d{3},\d{2})", ".", s)
    return s

def _is_header_saldo(s: str) -> bool:
    u = s.strip().upper()
    return "SALDO" == u or u.startswith("SALDO")

def _is_header_debito(s: str) -> bool:
    u = s.strip().upper()
    return u in ("DEBITO", "DÉBITO")

TRIGGER_PATTERNS = [
    r"^DEB\. AUTOM\. DE SERV\.", r"^SERVICIO PAGO A PROVEEDORES", r"^IMP\. CRE\. LEY 25413",
    r"^IMP\. DEB\. LEY 25413 GRAL\.", r"^ECHEQ 48 HS\. NRO\.", r"^TRANSFERENCIA DE CUENTA",
    r"^TRANSF\. CTAS PROPIAS", r"^TRF INMED PROVEED", r"^ANULACION DEBITOS",
    r"^DEV\.IMP\.DEB\.LEY", r"^TRANSFERENCIAS CASH", r"^PERCEP\. IVA",
    r"^IMPUESTO DE SELLOS", r"^INTERESES SOBRE SALDOS"
]
TRIGGER_RE = re.compile("|".join(TRIGGER_PATTERNS))

def preprocess_galicia_ocr(raw_text: str):
    """
    Pre-procesa Galicia cuando viene en formato columnar y reconstruye líneas:
    fecha + descripción (+ crédito embebido) + débito + saldo
    Devuelve: list[str]
    """
    # Entrada → normalización liviana
    raw_text = raw_text or ""
    lines_raw = [l for l in raw_text.split("\n")]
    lines = [_sanitize_line(l) for l in lines_raw]

    result_lines = []
    i = 0
    current_page = None
    pages_saved = set()
    summary = []  # para summary.log

    while i < len(lines):
        line = lines[i].strip()

        # Detecta y loguea página
        if line.lower().startswith("página") or line.lower().startswith("pagina"):
            try:
                current_page = int(re.search(r"\d+", line).group())
            except Exception:
                current_page = None
            if current_page in (3, 4) and current_page not in pages_saved:
                _debug_save_page_text(current_page, "\n".join(lines))
                pages_saved.add(current_page)
            i += 1
            continue

        # Detectar inicio de sección columnar por encabezado "Fecha"
        is_columnar_start = (line == "Fecha" or (line == "Fecha" and i + 1 < len(lines) and DATE_RE.match(lines[i + 1])))

        if is_columnar_start:
            logger.info(f"[COLUMNAR] Detectado inicio de sección columnar en línea {i}")

            # --- Captura fechas ---
            fechas = []
            i += 1
            while i < len(lines):
                l = lines[i].strip()
                if not l:
                    i += 1
                    continue
                if DATE_RE.match(l):
                    fechas.append(l)
                    i += 1
                else:
                    break
            logger.info(f"[COLUMNAR] Capturadas {len(fechas)} fechas")

            # --- Buscar header descripción (tolerante) ---
            found_descripcion = False
            limit = min(len(lines), i + 120)
            while i < limit:
                lu = lines[i].upper()
                if "DESCRIPCION" in lu or "DESCRIPCIÓN" in lu or "ORIGEN" in lu or "CREDITO" in lu:
                    found_descripcion = True
                    break
                i += 1

            if not found_descripcion:
                logger.warning("[COLUMNAR] No se encontró header 'Descripción' → copiando bloque crudo")
                # copia el bloque crudo para no perder info
                result_lines.extend(fechas)
                continue

            i += 1  # salta header

            # --- Captura descripciones (con crédito embebido al final de línea) ---
            descripciones, creditos_embebidos = [], []
            current_desc, credito_actual = [], None

            while i < len(lines):
                l = lines[i].strip()
                if _is_header_debito(l):
                    if current_desc:
                        descripciones.append(" ".join(current_desc).strip())
                        creditos_embebidos.append(credito_actual)
                    break

                if not l:
                    i += 1
                    continue

                # Crédito embebido al final
                cred_match = re.search(rf"({AMT_GENERIC_RE.pattern})$", l)
                if cred_match:
                    credito_actual = cred_match.group(1)
                    l = l[:cred_match.start()].strip()

                # Trigger de nuevo movimiento (al inicio de la línea)
                if TRIGGER_RE.search(l):
                    if current_desc:
                        descripciones.append(" ".join(current_desc).strip())
                        creditos_embebidos.append(credito_actual)
                    current_desc, credito_actual = [l], None
                else:
                    current_desc.append(l)

                i += 1

            if current_desc:
                descripciones.append(" ".join(current_desc).strip())
                creditos_embebidos.append(credito_actual)

            logger.info(f"[COLUMNAR] Capturadas {len(descripciones)} descripciones")

            # --- Header Débito ---
            if i < len(lines) and _is_header_debito(lines[i]):
                i += 1
            else:
                logger.warning("[COLUMNAR] No se encontró header 'Débito' → reconstrucción sin débitos")

            # --- Captura débitos (permite múltiples sub-bloques) ---
            debitos = []
            while i < len(lines):
                l = lines[i].strip()

                # Saltar headers duplicados
                if _is_header_debito(l):
                    i += 1
                    continue

                # Saldo detectado: verificar si después hay otro Débito (sub-bloque nuevo)
                if _is_header_saldo(l):
                    lookahead = [lines[j].strip() for j in range(i+1, min(i+8, len(lines)))]
                    if any(_is_header_debito(x) for x in lookahead):
                        # hay otro bloque de débitos más adelante → no cortar
                        i += 1
                        continue
                    else:
                        # último bloque → salir
                        break

                if not l:
                    i += 1
                    continue

                if re.match(r"^-\d{1,3}(?:[ .]\d{3})*,\d{2}$", l):
                    debitos.append(l)

                i += 1

            logger.info(f"[COLUMNAR] Capturados {len(debitos)} débitos (multi-bloque)")



            # --- Header Saldo ---
            if i < len(lines) and _is_header_saldo(lines[i]):
                i += 1
            else:
                logger.warning("[COLUMNAR] No se encontró header 'Saldo' → reconstrucción sin saldos")

            # --- Captura saldos (permite múltiples bloques) ---
            saldos = []
            while i < len(lines):
                l = lines[i].strip()

                if _is_header_debito(l):
                    # Otro bloque empieza: no cortar, retrocedemos un paso
                    i -= 1
                    break

                if re.match(r"^-?\d{1,3}(?:[ .]\d{3})*,\d{2}$", l):
                    saldos.append(l)

                i += 1

            logger.info(f"[COLUMNAR] Capturados {len(saldos)} saldos (multi-bloque)")


            # -------------------------
            # Alineación “safe” (v4)
            # -------------------------
            # Caso típico: 1 descripción huérfana al inicio (header suelto)
            if len(descripciones) - len(fechas) == 1 and descripciones:
                head = descripciones[0]
                if not DATE_RE.match(head) and not TRIGGER_RE.match(head):
                    logger.warning("[ALIGN] Extra descripción inicial sin fecha → eliminada")
                    descripciones.pop(0)
                    creditos_embebidos.pop(0)

            # Completar débitos/saldos a la longitud de fechas (o descripciones si aún mayor)
            target_len = max(len(fechas), len(descripciones))
            if len(debitos) < target_len:
                debitos.extend([""] * (target_len - len(debitos)))
            if len(saldos) < target_len:
                # Propaga último saldo si existe (mejor que vacío al medio)
                last = saldos[-1] if saldos else ""
                saldos.extend([last] * (target_len - len(saldos)))
            if len(creditos_embebidos) < target_len:
                creditos_embebidos.extend([""] * (target_len - len(creditos_embebidos)))

            # Reconstrucción segura
            reconstruidas = []
            for f, d, cr, db, s in zip_longest(
                fechas, descripciones, creditos_embebidos, debitos, saldos, fillvalue=""
            ):
                # Línea compacta, sin perder nada
                partes = [p for p in [f, d, cr, db, s] if str(p).strip()]
                if partes:
                    reconstruidas.append(" ".join(str(p) for p in partes if p is not None))

            # Debug de resumen por página/bloque
            summary.append(
                f"Página {current_page or '-'} → fechas={len(fechas)} desc={len(descripciones)} debitos={len(debitos)} saldos={len(saldos)} → líneas={len(reconstruidas)}"
            )

            logger.info(f"[COLUMNAR] Reconstruidas {len(reconstruidas)} líneas COMPLETAS (align-safe)")
            result_lines.extend(reconstruidas)
            continue  # sigue buscando más secciones columnar

        # No columnar → copiar tal cual
        if line:
            result_lines.append(line)
        i += 1

    # Guarda summary
    try:
        with open(os.path.join(DEBUG_DIR, "summary.log"), "a", encoding="utf-8") as f:
            for row in summary:
                f.write(row + "\n")
    except Exception:
        pass

    # Devuelve lista de líneas (no string) para evitar splits ambiguos después
    return result_lines
