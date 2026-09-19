from pathlib import Path

import polars as pl

# --- ETL Processing (Phase 5) - Validacion troncal ---

def normalize_stations(column_name: str) -> list[pl.Expr]:
    """Apply vectorized Polars expressions to extract keys and normalize station names."""
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
            .str.replace(r"[ÁÀÄÂ]", "A")
            .str.replace(r"[ÉÈËÊ]", "E")
            .str.replace(r"[ÍÌÏÎ]", "I")
            .str.replace(r"[ÓÒÖÔ]", "O")
            .str.replace(r"[ÚÙÜÛ]", "U")
            .str.replace(r"[\u2013\u2014]", "-")
            .str.strip_chars()
            .alias("NOMBRE_ESTACION_CANONICO")
        ),
    ]


def run_validations_etl():
    """Execute the Phase 5 ETL batch pipeline for validation Parquet files."""
    project_root = Path(__file__).resolve().parents[3]
    validations_path = (
        project_root / "data/processed/validaciones_salidas/validacion_troncal"
    )

    # Phase 1: Discover original Parquet files (excluding previous _clean files)
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
        print(f"[ERROR] Falló el escaneo del directorio {validations_path}: {e}")
        return

    target_columns = [
        "Fecha_Transaccion",
        "Hora_Pico_SN",
        "Day_Group_Type",
        "Linea",
        "Nombre_Perfil",
        "Acceso_Estacion",
    ]

    for file_path in validation_files:
        try:
            print(f"[PROCESANDO] Iniciando procesamiento para el archivo: {file_path.name}")

            # Lazy evaluation reading
            lazy_df = pl.scan_parquet(file_path)
            existing_columns = lazy_df.collect_schema().names()

            # Identify station column dynamically
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

            # Phase 2 & 3: Select target columns based on architectural design
            cols_to_keep = [
                col for col in target_columns if col in existing_columns
            ]

            # Phase 4: Apply vectorized normalization expressions
            lazy_df_clean = lazy_df.select(
                cols_to_keep + normalize_stations(station_col)
            )

            # Collect lazy computation into eager DataFrame
            df_clean = lazy_df_clean.collect()

            # Target output path definition with _clean suffix
            output_path = file_path.with_name(f"{file_path.stem}_clean.parquet")

            # Phase 5: Export processed clean data with ZSTD compression
            df_clean.write_parquet(output_path, compression="zstd")

            print(
                f"[ÉXITO] Datos de validaciones limpios guardados en: {output_path.name} | Filas: {len(df_clean)}"
            )

        except Exception as e:
            print(f"[ERROR] Falló el procesamiento del archivo {file_path.name}: {e}")

    print("[COMPLETADO] Finalizó la ejecución del pipeline ETL de validaciones.")


if __name__ == "__main__":

    run_validations_etl()
