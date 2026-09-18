from pathlib import Path

import polars as pl

# --- ETL Processing (Phase 5) - Salida troncal ---

def normalize_stations(column_name: str) -> list[pl.Expr]:
    """Applies Polars vectorized expressions to extract keys and normalize stations."""
    return [
        # 1. Extract exact 5-digit station code O(1)
        pl.col(column_name)
        .str.extract(r"\((\d{5})\)", 1)
        .alias("CODIGO_ESTACION"),
        # 2. Extract 2-digit trunk code (primeros 2 dígitos dentro del paréntesis de 5 dígitos)
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


def run_outputs_etl():
    """Execute the Phase 5 ETL batch pipeline exclusively for turnstile output Parquet files."""
    project_root = Path(__file__).resolve().parents[3]
    outputs_path = (
        project_root / "data/processed/validaciones_salidas/salidas_troncal"
    )

    try:
        output_files = [
            p
            for p in sorted(outputs_path.rglob("*.parquet"))
            if not p.stem.endswith("_clean")
        ]
        print(
            f"[INFO] Se encontraron {len(output_files)} archivos parquet originales en: {outputs_path}"
        )
    except Exception as e:
        print(f"[ERROR] Falló el escaneo del directorio {outputs_path}: {e}")
        return

    target_columns = [
        "Fecha_Transaccion",
        "Tiempo",
        "Linea",
        "Acceso_Estacion",
        "Entradas_E",
        "Salidas_S",
    ]

    for file_path in output_files:
        try:
            print(
                f"[PROCESANDO] Iniciando procesamiento para el archivo: {file_path.name}"
            )

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

            cols_to_keep = [
                c for c in target_columns if c in existing_columns
            ]

            lazy_df_clean = lazy_df.select(
                cols_to_keep + normalize_stations(station_col)
            )

            df_clean = lazy_df_clean.collect()

            clean_output_path = file_path.with_name(
                f"{file_path.stem}_clean.parquet"
            )

            df_clean.write_parquet(clean_output_path, compression="zstd")

            print(
                f"[ÉXITO] Datos de torniquetes limpios guardados en: {clean_output_path.name} | Filas: {len(df_clean)}"
            )

        except Exception as e:
            print(f"[ERROR] Falló el procesamiento del archivo {file_path.name}: {e}")

    print("[COMPLETADO] Finalizó la ejecución del pipeline ETL de salidas.")


if __name__ == "__main__":
    run_outputs_etl()
