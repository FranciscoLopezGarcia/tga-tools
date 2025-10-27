import pandas as pd
import io
from openpyxl import load_workbook

def exportar_excel(df: pd.DataFrame, nombre_archivo: str, sheet_name="Datos"):
    """Exporta DataFrame a un Excel en memoria."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buffer.seek(0)
    with open(nombre_archivo, "wb") as f:
        f.write(buffer.read())
