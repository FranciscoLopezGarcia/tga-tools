import pandas as pd
import camelot
import re
from datetime import datetime


class ProvinciaParser:
    BANK_NAME = "PROVINCIA"

    def parse(self, raw_data, filename=""):
        print(f"[DEBUG] Iniciando parser Provincia — {filename}")

        pdf_path = f"examples/{filename}" if not filename.lower().startswith("examples/") else filename

        try:
            tables = camelot.read_pdf(pdf_path, flavor="stream", pages="all", strip_text="\n")
            print(f"[DEBUG] Camelot detectó {tables.n} tablas (modo stream)")
        except Exception as e:
            print(f"[ERROR] Camelot falló: {e}")
            return pd.DataFrame()

        if not tables or tables.n == 0:
            print("[DEBUG] No se detectaron tablas válidas")
            return pd.DataFrame()

        df = pd.concat([t.df for t in tables], ignore_index=True)
        df.columns = [str(c).strip().lower() for c in df.columns]
        print(f"[DEBUG] Filas crudas totales: {len(df)}")

        # Unir columnas si Camelot no separó bien
        if df.shape[1] == 1:
            df.columns = ["detalle"]
        else:
            df["detalle"] = df.apply(lambda row: " ".join([str(x) for x in row if str(x).strip() not in ["nan", ""]]), axis=1)

        # Limpieza general
        df["detalle"] = df["detalle"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()

        # Filtrar solo líneas útiles
        df = df[df["detalle"].str.contains(
            r"(SALDO|COMISION|IMPUESTO|TRANSFERENCIA|DEBITO|CREDITO|PAGO|PERCEP|IVA|I\.B|SIRCREB|MANTENIM|RETENCION)",
            flags=re.IGNORECASE, regex=True
        )]

        # =====================================================
        # 🔍 Extracción de datos
        # =====================================================
        pattern_monto = r"-?\d{1,3}(?:\.\d{3})*,\d{2}"
        pattern_fecha = r"(\d{2}[-/]\d{2}[-/]\d{2,4})"

        movimientos = []
        for _, row in df.iterrows():
            linea = row["detalle"]
            montos = re.findall(pattern_monto, linea)
            fecha_match = re.search(pattern_fecha, linea)

            fecha = fecha_match.group(1) if fecha_match else None
            detalle = re.sub(pattern_fecha, "", linea).strip()

            # Eliminar montos del texto descriptivo
            for m in montos:
                detalle = detalle.replace(m, "")
            detalle = detalle.strip()

            debito = credito = saldo = 0.0

            # Caso especial: si es línea de saldo
            if "SALDO" in detalle.upper():
                if len(montos) > 0:
                    saldo = self._to_float(montos[-1])
                movimientos.append([fecha, detalle, 0.0, 0.0, saldo])
                continue

            # Clasificación por cantidad de montos
            if len(montos) == 1:
                monto = self._to_float(montos[0])
                if monto < 0:
                    debito = abs(monto)
                else:
                    credito = monto
            elif len(montos) == 2:
                monto_mov = self._to_float(montos[0])
                saldo = self._to_float(montos[1])
                if monto_mov < 0:
                    debito = abs(monto_mov)
                else:
                    credito = monto_mov
            elif len(montos) >= 3:
                debito = abs(self._to_float(montos[-3]))
                credito = self._to_float(montos[-2])
                saldo = self._to_float(montos[-1])

            movimientos.append([fecha, detalle, debito, credito, saldo])

        df_out = pd.DataFrame(movimientos, columns=["fecha", "detalle", "debito", "credito", "saldo"])
        df_out["moneda"] = "ARS"
        df_out = self._clean_df(df_out)

        # ✅ Reordenamos columnas
        df_out = df_out[["fecha", "mes", "año", "detalle", "debito", "credito", "saldo", "moneda"]]

        print(f"[DEBUG] Filas finales limpias: {len(df_out)}")
        return df_out

    # =====================================================
    # 🧹 Limpieza
    # =====================================================
    def _clean_df(self, df):
        df = df.dropna(subset=["detalle"], how="all")
        for col in ["debito", "credito", "saldo"]:
            df[col] = df[col].apply(self._to_float)
        df["fecha"] = df["fecha"].apply(self._normalize_date)
        df["mes"] = df["fecha"].apply(lambda x: x.month if isinstance(x, datetime) else None)
        df["año"] = df["fecha"].apply(lambda x: x.year if isinstance(x, datetime) else None)
        return df

    def _normalize_date(self, s):
        try:
            if not isinstance(s, str):
                return None
            s = s.strip().replace("-", "/")
            if len(s.split("/")) == 2:
                s = f"{s}/{datetime.now().year}"
            fmt = "%d/%m/%y" if len(s.split("/")[-1]) == 2 else "%d/%m/%Y"
            return datetime.strptime(s, fmt)
        except:
            return None

    def _to_float(self, val):
        try:
            val = str(val).strip()
            if val.count(",") == 1 and val.count(".") >= 1:
                val = val.replace(".", "").replace(",", ".")
            elif val.count(",") == 1 and val.count(".") == 0:
                val = val.replace(",", ".")
            return float(val)
        except:
            return 0.0
