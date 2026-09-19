import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # ETL (Fase 5): Validación Troncal
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Importación de librerías y dependencias
    """)
    return


@app.cell
def _():
    from pathlib import Path

    import marimo as mo
    import polars as pl

    return Path, mo, pl


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Configuración de rutas
    Detecta dinámicamente la raíz del proyecto buscando la carpeta `data`.
    """)
    return


@app.cell
def _(Path):
    current_dir = Path.cwd()
    root_dir = current_dir

    while root_dir != root_dir.parent and not (root_dir / "data").exists():
        root_dir = root_dir.parent

    validations_path = (
        root_dir / "data" / "processed" / "validaciones_salidas" / "validacion_troncal"
    )
    return (validations_path,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Funciones utilitarias
    Aplica expresiones vectorizadas en Polars para extraer el código de 5 dígitos (`CODIGO_ESTACION`), el código de troncal (`CODIGO_TRONCAL`) y limpiar el nombre canónico de la estación.
    """)
    return


@app.cell
def _(pl):
    def normalize_stations(column_name: str) -> list[pl.Expr]:
        """Applies vectorized Polars expressions to extract keys and normalize station names."""
        return [
            # 1. Extract exact 5-digit station code O(1)
            pl.col(column_name)
            .str.extract(r"\((\d{5})\)", 1)
            .alias("CODIGO_ESTACION"),
            # 2. Extract 2-digit trunk code
            pl.col(column_name)
            .str.extract(r"\((\d{2})\d{3}\)", 1)
            .alias("CODIGO_TRONCAL"),
            # 3. Clean canonical station name
            (
                pl.col(column_name)
                .str.replace(r"^\(\d+\)\s*", "")
                .str.to_uppercase()
                .str.replace_all(r"[ÁÀÄÂ]", "A")
                .str.replace_all(r"[ÉÈËÊ]", "E")
                .str.replace_all(r"[ÍÌÏÎ]", "I")
                .str.replace_all(r"[ÓÒÖÔ]", "O")
                .str.replace_all(r"[ÚÙÜÛ]", "U")
                .str.replace_all(r"[\u2013\u2014]", "-")
                .str.replace_all(r"\s+", " ")
                .str.strip_chars()
                .alias("NOMBRE_ESTACION_CANONICO")
            ),
        ]

    return (normalize_stations,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Descubrimiento de archivos
    """)
    return


@app.cell
def _(validations_path):
    try:
        validation_files = [
            file_path
            for file_path in sorted(validations_path.rglob("*.parquet"))
            if not file_path.stem.endswith("_clean")
        ]
        print(
            f"[INFO] Se encontraron {len(validation_files)} archivos parquet originales en: {validations_path}"
        )
    except Exception as e:
        validation_files = []
        print(f"[ERROR] Falló el escaneo del directorio {validations_path}: {e}")

    return (validation_files,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Procesamiento, Normalización y Exportación
    """)
    return


@app.cell
def _(normalize_stations, pl, validation_files):
    target_columns = [
        "Fecha_Transaccion",
        "Hora_Pico_SN",
        "Day_Group_Type",
        "Linea",
        "Nombre_Perfil",
        "Acceso_Estacion",
    ]

    processed_results = []
    total_original_rows = 0
    total_clean_rows = 0

    for file_path in validation_files:
        try:
            print(f"[PROCESANDO] Iniciando procesamiento para el archivo: {file_path.name}")

            # Lazy evaluation reading
            lazy_df = pl.scan_parquet(file_path)
            existing_columns = lazy_df.collect_schema().names()

            # Dynamic station column identification
            station_col = (
                "Estacion_Parada"
                if "Estacion_Parada" in existing_columns
                else next(
                    (col for col in existing_columns if "estacion" in col.lower()),
                    None,
                )
            )

            if not station_col:
                raise ValueError(
                    f"No se encontró la columna de estación en el esquema de {file_path.name}"
                )

            cols_to_keep = [col for col in target_columns if col in existing_columns]

            # Length calculation
            original_len = lazy_df.select(pl.len()).collect().item()

            # Normalization transformation
            lazy_df_clean = lazy_df.select(
                cols_to_keep + normalize_stations(station_col)
            )
            df_clean = lazy_df_clean.collect()
            clean_len = df_clean.height

            # Target output path definition
            clean_output_path = file_path.with_name(f"{file_path.stem}_clean.parquet")

            # Immediate write to disk
            df_clean.write_parquet(clean_output_path, compression="zstd")

            print(
                f"[ÉXITO] Datos de validaciones limpios guardados en: {clean_output_path.name} | Filas: {clean_len}"
            )

            # Metrics collection
            total_original_rows += original_len
            total_clean_rows += clean_len

            processed_results.append({
                "file_path": file_path,
                "clean_output_path": clean_output_path,
                "df_clean": df_clean,
                "original_rows": original_len,
                "clean_rows": clean_len,
            })

        except Exception as e:
            print(f"[ERROR] Falló el procesamiento del archivo {file_path.name}: {e}")

    return processed_results, total_clean_rows, total_original_rows


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Reporte de Limpieza
    """)
    return


@app.cell
def _(total_clean_rows, total_original_rows):
    total_rows_deleted = total_original_rows - total_clean_rows

    print("\n--- LIMPIEZA: VALIDACIÓN TRONCAL ---")
    print(f"Registros originales:  {total_original_rows:,}")
    print(f"Registros conservados: {total_clean_rows:,}")
    print(f"Registros eliminados:  {total_rows_deleted:,}")
    print("------------------------------------\n")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Vista previa de datos
    """)
    return


@app.cell
def _(mo, processed_results):
    sample_df = processed_results[0]["df_clean"] if processed_results else None

    if sample_df is not None:
        table_view = mo.ui.table(sample_df.head(10))
    else:
        table_view = mo.md("No hay datos disponibles para mostrar.")

    table_view
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Resumen de Ejecución
    """)
    return


@app.cell
def _(processed_results):
    print(
        f"[COMPLETADO] Finalizó la ejecución del pipeline ETL de validaciones. Se generaron {len(processed_results)} archivos _clean.parquet."
    )
    return


if __name__ == "__main__":
    app.run()
