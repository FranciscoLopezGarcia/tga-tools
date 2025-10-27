import os
import zipfile
import logging
from pathlib import Path
import pandas as pd
from config import Config
import traceback

logger = logging.getLogger(__name__)

def procesar_extractos(job_id, files, JOBS):
    """Procesa extractos bancarios usando UniversalExtractor."""
    try:
        logger.info(f"🚀 Iniciando procesamiento - Job {job_id} ({len(files)} archivos)")

        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)

        JOBS[job_id]["state"] = "PROGRESS"
        JOBS[job_id]["status"] = "Inicializando extractor..."
        JOBS[job_id]["progress"] = 5

        # Importar extractor
        logger.info("📦 Importando UniversalExtractor...")
        from extractors.universal_extractor import UniversalExtractor
        from extractors.unificador import consolidate
        logger.info("✅ Imports completados")

        extractor = UniversalExtractor()
        JOBS[job_id]["progress"] = 10

        total = len(files)
        resultados = []
        errores = []

        # Procesar cada archivo
        for i, file_dict in enumerate(files, 1):
            filename = file_dict["filename"]
            content = file_dict["content"]
            
            logger.info(f"📄 Procesando {i}/{total}: {filename}")
            JOBS[job_id]["status"] = f"Procesando {i}/{total}: {filename}"
            JOBS[job_id]["progress"] = 10 + int((i / total) * 70)

            try:
                # Guardar temporalmente
                temp_path = os.path.join(Config.UPLOAD_FOLDER, f"{job_id}_{filename}")
                content.seek(0)
                with open(temp_path, "wb") as f:
                    f.write(content.read())
                
                logger.info(f"  💾 Guardado en: {temp_path}")
                logger.info(f"  🔍 Llamando a extract_from_pdf()...")
                
                # PROCESAR CON UNIVERSAL EXTRACTOR
                result = extractor.extract_from_pdf(temp_path, filename_hint=filename)
                
                logger.info(f"  ✅ extract_from_pdf() completado")
                logger.info(f"  📊 Resultado keys: {list(result.keys())}")
                
                metadata = result.get("metadata", {})
                tables = result.get("tables", [])
                bank_hint = result.get("bank_hint", "DESCONOCIDO")
                
                logger.info(f"  🏦 Banco detectado: {bank_hint}")
                logger.info(f"  📋 Tablas encontradas: {len(tables)}")
                
                if tables and len(tables) > 0:
                    logger.info(f"  📊 Primera tabla es DataFrame: {isinstance(tables[0], pd.DataFrame)}")
                    if isinstance(tables[0], pd.DataFrame):
                        df = tables[0]
                        logger.info(f"  📊 DataFrame shape: {df.shape}")
                        
                        if not df.empty:
                            resultados.append({
                                "df": df,
                                "meta": {
                                    "bank": bank_hint,
                                    "filename": filename,
                                    "empresa": metadata.get("empresa", ""),
                                    "periodo": metadata.get("periodo", "")
                                }
                            })
                            logger.info(f"  ✅ {filename}: {len(df)} movimientos | {bank_hint}")
                        else:
                            errores.append({"name": filename, "status": "empty", "error": "Sin movimientos"})
                            logger.warning(f"  ⚠️ DataFrame vacío")
                    else:
                        logger.warning(f"  ⚠️ Tabla no es DataFrame, es: {type(tables[0])}")
                        errores.append({"name": filename, "status": "no_data", "error": "Tabla no es DataFrame"})
                else:
                    errores.append({"name": filename, "status": "no_data", "error": "Sin tablas"})
                    logger.warning(f"  ⚠️ No se extrajeron tablas")

                # Limpiar temporal
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info(f"  🗑️ Archivo temporal eliminado")

            except Exception as e:
                error_msg = str(e)
                error_trace = traceback.format_exc()
                logger.error(f"  ❌ ERROR procesando {filename}:")
                logger.error(f"  {error_msg}")
                logger.error(f"  Traceback:\n{error_trace}")
                errores.append({"name": filename, "status": "error", "error": error_msg})

        # CONSOLIDAR
        logger.info("📊 Iniciando consolidación...")
        JOBS[job_id]["status"] = "Consolidando resultados..."
        JOBS[job_id]["progress"] = 85

        output_zip_path = os.path.join(Config.OUTPUT_FOLDER, f"{job_id}_extractos.zip")

        if resultados:
            try:
                logger.info(f"📊 Consolidando {len(resultados)} extractos...")
                
                # Crear ZIP
                with zipfile.ZipFile(output_zip_path, "w") as zipf:
                    # 1️⃣ AGREGAR EXCEL INDIVIDUALES
                    for idx, resultado in enumerate(resultados, 1):
                        df_individual = resultado["df"]
                        meta = resultado["meta"]
                        filename = meta.get("filename", f"extracto_{idx}.pdf")
                        
                        # Nombre del Excel individual (sin .pdf)
                        excel_name = filename.replace(".pdf", ".xlsx").replace(".PDF", ".xlsx")
                        
                        # Guardar Excel individual temporalmente
                        temp_excel = os.path.join(Config.OUTPUT_FOLDER, f"{job_id}_{excel_name}")
                        df_individual.to_excel(temp_excel, index=False, sheet_name=meta.get("banco", "Extracto"))
                        
                        # Agregar al ZIP
                        zipf.write(temp_excel, arcname=excel_name)
                        
                        # Limpiar temporal
                        os.remove(temp_excel)
                        logger.info(f"  ✅ Agregado al ZIP: {excel_name}")
                    
                    # 2️⃣ AGREGAR CONSOLIDADO
                    consolidated_excel = os.path.join(Config.OUTPUT_FOLDER, f"{job_id}_consolidado.xlsx")
                    df_consolidado = consolidate(resultados, output_path=consolidated_excel)
                    
                    logger.info(f"📊 DataFrame consolidado: {len(df_consolidado)} filas")
                    
                    # Agregar consolidado al ZIP
                    zipf.write(consolidated_excel, arcname="00_CONSOLIDADO.xlsx")
                    
                    # Limpiar consolidado temporal
                    os.remove(consolidated_excel)
                
                logger.info(f"✅ ZIP creado con {len(resultados)} individuales + 1 consolidado")
                
            except Exception as e:
                logger.error(f"❌ Error consolidando: {e}", exc_info=True)
                with zipfile.ZipFile(output_zip_path, "w") as zipf:
                    pass
        else:
            logger.warning("⚠️ No hay resultados para consolidar")
            with zipfile.ZipFile(output_zip_path, "w") as zipf:
                pass

        # COMPLETADO
        JOBS[job_id]["state"] = "SUCCESS"
        JOBS[job_id]["result_file"] = output_zip_path
        JOBS[job_id]["progress"] = 100
        
        success_count = len(resultados)
        error_count = len(errores)
        
        if error_count > 0:
            JOBS[job_id]["status"] = f"✅ Completado con advertencias: {success_count} OK, {error_count} errores"
        else:
            JOBS[job_id]["status"] = f"✅ Completado: {success_count} extractos procesados"
        
        JOBS[job_id]["results"] = {
            "total": total,
            "success": success_count,
            "errors": error_count,
            "results": [
                {"name": r["meta"]["filename"], "status": "success", "banco": r["meta"]["bank"]}
                for r in resultados
            ] + errores
        }

        logger.info(f"🎉 Job {job_id} completado: {success_count} OK, {error_count} errores")

    except Exception as e:
        logger.error(f"❌ ERROR FATAL en job {job_id}:")
        logger.error(f"  {str(e)}")
        logger.error(f"  Traceback completo:\n{traceback.format_exc()}")
        
        JOBS[job_id]["state"] = "FAILURE"
        JOBS[job_id]["status"] = f"❌ Error: {str(e)}"
        JOBS[job_id]["progress"] = 0