# backend/extractors/camelot_utils.py
"""
Utilidad para extraer tablas de PDFs usando Camelot.
Se separa de pdf2xls/universal_extractor para evitar imports circulares.
"""

import camelot
import logging

logger = logging.getLogger(__name__)

def extract_tables_with_camelot(pdf_path: str, max_pages: int = None):
    """
    Intenta extraer tablas de un PDF usando Camelot (flavor=lattice).
    
    Args:
        pdf_path: Ruta al archivo PDF
        max_pages: Número máximo de páginas a procesar (None = todas)
        
    Returns:
        Lista de DataFrames de pandas o lista vacía si falla
    """
    try:
        # Determinar qué páginas procesar
        if max_pages is not None and max_pages > 0:
            pages_arg = f"1-{max_pages}"
            logger.info(f"📄 Camelot limitado a primeras {max_pages} páginas")
        else:
            pages_arg = "all"
            logger.warning("⚠️  Camelot sin límite de páginas (puede consumir mucha RAM)")
        
        # Ejecutar Camelot
        tables = camelot.read_pdf(pdf_path, pages=pages_arg, flavor="lattice")
        
        if tables and len(tables) > 0:
            logger.info(f"✅ Camelot detectó {len(tables)} tablas")
            return [t.df for t in tables]
        else:
            logger.info("ℹ️  Camelot no detectó tablas")
            return []
            
    except Exception as e:
        logger.warning(f"⚠️  Camelot falló: {e}")
        return []