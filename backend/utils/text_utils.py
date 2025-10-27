# -*- coding: utf-8 -*-
"""
Utilidades de limpieza de texto para SIRADIG
"""

import re


def limpiar_texto(texto):
    """
    Limpia y normaliza texto extraído de PDFs.
    
    - Elimina espacios múltiples
    - Normaliza saltos de línea
    - Remueve caracteres de control
    """
    if not texto or not isinstance(texto, str):
        return ""
    
    # Eliminar caracteres de control excepto espacios y saltos de línea
    texto = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", texto)
    
    # Normalizar espacios múltiples
    texto = re.sub(r"[ \t]+", " ", texto)
    
    # Normalizar saltos de línea múltiples
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    
    return texto.strip()