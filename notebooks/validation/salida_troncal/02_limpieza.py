import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # ETL (Fase 5): Salidas Troncales
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Importación librerías / paths
    """)
    return


@app.cell
def _():
    from pathlib import Path

    import marimo as mo
    import polars as pl

    return Path, mo, pl


@app.cell
def _(Path):
    current_dir = Path.cwd()
    root_dir = current_dir

    while root_dir != root_dir.parent and not (root_dir / "data").exists():
        root_dir = root_dir.parent

    outputs_path = (
        root_dir / "data" / "processed" / "validaciones_salidas" / "salidas_troncal"
    )
    return (outputs_path,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Funciones utilitarias
    De la columna de estaciones: extrae el código de 5 dígitos como llave primaria (CODIGO_ESTACION), obtiene los 2 dígitos iniciales para la zonificación geográfica (CODIGO_TRONCAL) y depura el nombre para estandarizarlo.
    """)
    return


@app.cell
def _(pl):
    def normalize_stations(column_name: str) -> list[pl.Expr]:
        """Applies Polars vectorized expressions to extract keys and normalize stations."""
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
def _(outputs_path):
    output_files = [
        p
        for p in sorted(outputs_path.rglob("*.parquet"))
        if not p.stem.endswith("_clean")
    ]

    print(
        f"[INFO] Se encontraron {len(output_files)} archivos parquet originales en: {outputs_path}"
    )
    return (output_files,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Procesamiento y Normalización
    Detecta la columna de estación, selecciona las variables objetivo y aplica la normalización; además, calcula métricas de volumen de filas (originales y procesadas) y prepara los DataFrames con sus rutas para su posterior exportación.
    """)
    return


@app.cell
def _(normalize_stations, output_files, pl):
    target_columns = [
        "Fecha_Transaccion",
        "Tiempo",
        "Linea",
        "Acceso_Estacion",
        "Entradas_E",
        "Salidas_S",
    ]

    processed_results = []
    total_original_rows = 0
    total_clean_rows = 0

    for file_path in output_files:
        try:
            print(f"[PROCESANDO] Iniciando procesamiento para el archivo: {file_path.name}")

            lazy_df = pl.scan_parquet(file_path)
            existing_columns = lazy_df.collect_schema().names()

            station_col = (
                "Estacion"
                if "Estacion" in existing_columns
                else next(
                    (c for c in existing_columns if "estacion" in c.lower()),
                    None,
                )
            )

            if not station_col:
                raise ValueError(
                    f"No se encontró la columna de estación en el esquema de {file_path.name}"
                )

            cols_to_keep = [c for c in target_columns if c in existing_columns]

            # Intake and Filtration
            original_len = lazy_df.select(pl.len()).collect().item()
            lazy_df_clean = lazy_df.select(
                cols_to_keep + normalize_stations(station_col)
            )
            df_clean = lazy_df_clean.collect()
            clean_len = df_clean.height

            # Track General Metrics
            total_original_rows += original_len
            total_clean_rows += clean_len

            clean_output_path = file_path.with_name(
                f"{file_path.stem}_clean.parquet"
            )

            df_clean.write_parquet(clean_output_path, compression="zstd")
            print(
                f"[ÉXITO] Datos de torniquetes limpios guardados en: {clean_output_path.name} | Filas: {clean_len}"
            )

            processed_results.append({
                "file_path": file_path,
                "clean_output_path": clean_output_path,
                "df_clean": df_clean,
                "original_rows": original_len,
                "clean_rows": clean_len,
            })

        except Exception as e:
            print(
                f"[ERROR] Falló el procesamiento del archivo {file_path.name}: {e}"
            )

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

    print("\n--- LIMPIEZA: SALIDAS TRONCALES ---")
    print(f"Registros originales:  {total_original_rows:,}")
    print(f"Registros conservados: {total_clean_rows:,}")
    print(f"Registros eliminados:  {total_rows_deleted:,}")
    print("-----------------------------------\n")
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
    ### Creación archivos .parquet
    """)
    return


@app.cell
def _(processed_results):
    print(
        f"[COMPLETADO] Finalizó la escritura de los archivos parquet limpios. Se generaron {len(processed_results)} archivos _clean.parquet."
    )
    return


if __name__ == "__main__":
    app.run()
