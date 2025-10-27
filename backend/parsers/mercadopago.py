import re
import pandas as pd
from datetime import datetime


class MercadoPagoParser:
    """
    Parser OCR final para extractos de Mercado Pago.
    Convierte 'valor' en columnas estándar: debito / credito.
    """

    def parse(self, text_lines):
        movimientos = []
        dentro_tabla = False

        for line in text_lines:
            line = line.strip()

            # 🔹 Detectar comienzo del bloque
            if "DETALLE DE MOVIMIENTOS" in line.upper():
                dentro_tabla = True
                continue

            if not dentro_tabla:
                continue

            # 🔹 Saltar encabezados o líneas vacías
            if not line or "FECHA" in line.upper() or "DESCRIPCION" in line.upper():
                continue

            # 🔹 Buscar fecha (dd-mm-yyyy)
            fecha_match = re.search(r"(\d{2}[-/]\d{2}[-/]\d{4})", line)
            if not fecha_match:
                continue
            fecha_txt = fecha_match.group(1).replace("/", "-")
            try:
                fecha = datetime.strptime(fecha_txt, "%d-%m-%Y")
            except ValueError:
                continue

            # 🔹 Buscar referencia numérica larga (ID)
            ref_match = re.search(r"\b(\d{10,15})\b", line)
            referencia = ref_match.group(1) if ref_match else ""

            # 🔹 Buscar montos (pueden tener signo y símbolo $)
            montos_raw = re.findall(r"[-+]?\$?\s?\d{1,3}(?:\.\d{3})*,\d{2}", line)
            montos = [
                float(m.replace("$", "").replace(".", "").replace(",", ".").strip())
                for m in montos_raw
            ]

            valor = saldo = 0.0
            if len(montos) == 1:
                valor = montos[0]
            elif len(montos) >= 2:
                valor, saldo = montos[-2], montos[-1]

            # 🔹 Determinar signo automáticamente según palabras
            txt_upper = line.upper()
            if any(p in txt_upper for p in ["PAGO", "COMPRA", "EXTRACCION", "ENVIADA", "ENVIA", "SALIDA"]):
                valor = -abs(valor)
            elif any(p in txt_upper for p in ["TRANSFERENCIA RECIBIDA", "ACREDITACION", "ENTRADA", "RENDIMIENTOS", "CARGA SALDO", "INGRESO"]):
                valor = abs(valor)

            # 🔹 Limpiar detalle
            detalle = line
            detalle = re.sub(r"(\d{2}[-/]\d{2}[-/]\d{4})", "", detalle)
            detalle = re.sub(r"\b\d{10,15}\b", "", detalle)
            detalle = re.sub(r"[-+]?\$?\s?\d{1,3}(?:\.\d{3})*,\d{2}", "", detalle)
            detalle = re.sub(r"\s{2,}", " ", detalle).strip()

            movimientos.append({
                "fecha": fecha,
                "detalle": detalle,
                "referencia": referencia,
                "valor": round(valor, 2),
                "saldo": round(saldo, 2),
                "moneda": "ARS"
            })

        if not movimientos:
            raise ValueError("⚠️ No se detectaron movimientos válidos en el texto OCR.")

        # 🔹 Convertir a DataFrame
        df = pd.DataFrame(movimientos)

        # 🔹 Crear columnas de débito / crédito a partir del valor
        df["debito"] = df["valor"].apply(lambda x: abs(x) if x < 0 else 0.0)
        df["credito"] = df["valor"].apply(lambda x: x if x > 0 else 0.0)
        df["mes"] = df["fecha"].dt.month
        df["año"] = df["fecha"].dt.year

        # 🔹 Reordenar columnas
        df = df[
            ["fecha", "mes", "año", "detalle", "referencia", "debito", "credito", "saldo", "moneda"]
        ]

        # 🔹 Limpiar duplicados y ordenar
        df = df.drop_duplicates(subset=["fecha", "detalle", "referencia", "debito", "credito"])
        df = df.sort_values("fecha").reset_index(drop=True)

        return df
