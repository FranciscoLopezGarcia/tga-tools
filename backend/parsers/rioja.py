import pandas as pd
import camelot
import re
from datetime import datetime


class RiojaParser:
    BANK_NAME = "RIOJA"

    def parse(self, raw_data, filename=""):
        print(f"[DEBUG] Iniciando parser Banco Rioja — {filename}")

        pdf_path = f"examples/{filename}" if not filename.lower().startswith("examples/") else filename

        try:
            tables = camelot.read_pdf(
                pdf_path,
                flavor="stream",
                pages="all",
                strip_text="\n",
                row_tol=5,
                edge_tol=150
            )
            print(f"[DEBUG] Camelot detectó {tables.n} tablas (modo stream)")
        except Exception as e:
            print(f"[ERROR] Camelot falló: {e}")
            return pd.DataFrame()

        if not tables or tables.n == 0:
            print("[DEBUG] No se detectaron tablas válidas")
            return pd.DataFrame()

        # Unir todas las tablas
        df = pd.concat([t.df for t in tables], ignore_index=True)
        df.columns = [str(c).strip().lower() for c in df.columns]
        print(f"[DEBUG] Filas crudas totales: {len(df)}")

        # Unir columnas si Camelot no las detecta bien
        if df.shape[1] == 1:
            df.columns = ["detalle"]
        else:
            df["detalle"] = df.apply(
                lambda row: " ".join(
                    [str(x) for x in row if str(x).strip() not in ["nan", ""]]
                ),
                axis=1,
            )

        # Limpieza inicial
        df["detalle"] = df["detalle"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()

        # Eliminar encabezados, totales, textos no contables
        filtros_excluir = [
            "Tipo de Cuenta",
            "CUENTA",
            "IVA",
            "Mes:",
            "Total",
            "TOTALES",
            "Página",
            "Lo indicado",
            "SANCHEZ",
            "Responsable",
            "Domicilio",
            "Sucursal",
        ]
        df = df[~df["detalle"].str.contains("|".join(filtros_excluir), flags=re.IGNORECASE, regex=True)]
        df = df[df["detalle"].str.contains(r"\d{1,2}/\d{1,2}/\d{4}", regex=True)]

        # =====================================================
        # 🔍 Extracción de datos
        # Estructura: FECHA | CONCEPTO | REF | DEBITO | CREDITO | SALDO
        # =====================================================
        pattern = r"(\d{1,2}/\d{1,2}/\d{4})\s+(.*?)\s+(\d+)\s+(-?[\d.,]+)\s+(-?[\d.,]+)\s+(-?[\d.,]+)"
        movimientos = []

        for _, row in df.iterrows():
            linea = row["detalle"]
            match = re.search(pattern, linea)
            if not match:
                continue

            fecha_raw, concepto, ref, debito_raw, credito_raw, saldo_raw = match.groups()
            fecha = self._normalize_date(fecha_raw)
            referencia = ref.strip()
            detalle = concepto.strip()

            debito = self._to_float(debito_raw)
            credito = self._to_float(credito_raw)
            saldo = self._to_float(saldo_raw)

            movimientos.append([fecha, detalle, referencia, debito, credito, saldo])

        df_out = pd.DataFrame(movimientos, columns=["fecha", "detalle", "referencia", "debito", "credito", "saldo"])
        df_out["moneda"] = "ARS"
        df_out["mes"] = df_out["fecha"].apply(lambda x: x.month if isinstance(x, datetime) else None)
        df_out["año"] = df_out["fecha"].apply(lambda x: x.year if isinstance(x, datetime) else None)

        # Reordenar columnas
        df_out = df_out[["fecha", "mes", "año", "detalle", "referencia", "debito", "credito", "saldo", "moneda"]]

        print(f"[DEBUG] Filas finales limpias: {len(df_out)}")
        return df_out

    # =====================================================
    # 🔧 Utilidades
    # =====================================================
    def _normalize_date(self, s):
        try:
            s = s.strip().replace("-", "/")
            return datetime.strptime(s, "%d/%m/%Y")
        except:
            return None

    def _to_float(self, val):
        try:
            val = str(val).strip()
            if val in ["", "nan", "None"]:
                return 0.0
            # eliminar puntos de miles y convertir coma decimal
            val = val.replace(".", "").replace(",", ".")
            return float(val)
        except:
            return 0.0
