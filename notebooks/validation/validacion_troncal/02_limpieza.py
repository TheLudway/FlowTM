from pathlib import Path

import polars as pl

# --- ETL Processing (Phase 5) - Validacion troncal ---

def normalizar_estaciones(columna: str) -> list[pl.Expr]:
    """Apply vectorized Polars expressions to extract keys and normalize station names."""
    return [
        # 1. Extract exact 5-digit station code O(1)
        pl.col(columna)
        .str.extract(r"\((\d{5})\)", 1)
        .alias("CODIGO_ESTACION"),
        # 2. Extract 2-digit trunk code
        pl.col(columna)
        .str.extract(r"\((\d{2})\d{3}\)", 1)
        .alias("CODIGO_TRONCAL"),
        # 3. Clean canonical station name
        (
            pl.col(columna)
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


def ejecutar_etl_validaciones():
    """Execute the Phase 5 ETL batch pipeline for validation Parquet files."""
    project_root = Path(__file__).resolve().parents[3]
    ruta_val = (
        project_root / "data/processed/validaciones_salidas/validacion_troncal"
    )

    # Phase 1: Discover original Parquet files (excluding previous _clean files)
    try:
        archivos_val = [
            p
            for p in sorted(ruta_val.rglob("*.parquet"))
            if not p.stem.endswith("_clean")
        ]
        print(
            f"[INFO] Discovered {len(archivos_val)} original parquet files in {ruta_val}"
        )
    except Exception as e:
        print(f"[ERROR] Failed to scan directory {ruta_val}: {e}")
        return

    cols_utiles_val = [
        "Fecha_Transaccion",
        "Hora_Pico_SN",
        "Day_Group_Type",
        "Linea",
        "Nombre_Perfil",
        "Acceso_Estacion",
    ]

    for p in archivos_val:
        try:
            print(f"[PROCESSING] Starting processing for file: {p.name}")

            # Lazy evaluation reading
            lf = pl.scan_parquet(p)
            cols_existentes = lf.collect_schema().names()

            # Identify station column dynamically
            col_est = (
                "Estacion_Parada"
                if "Estacion_Parada" in cols_existentes
                else next(
                    (c for c in cols_existentes if "estacion" in c.lower()),
                    None,
                )
            )

            if not col_est:
                raise ValueError(
                    f"No station column found in schema for file {p.name}"
                )

            # Phase 2 & 3: Select target columns based on architectural design
            cols_a_conservar = [
                c for c in cols_utiles_val if c in cols_existentes
            ]

            # Phase 4: Apply vectorized normalization expressions
            lf_clean = lf.select(
                cols_a_conservar + normalizar_estaciones(col_est)
            )

            # Collect lazy computation into eager DataFrame
            df_clean = lf_clean.collect()

            # Target output path definition with _clean suffix
            ruta_salida = p.with_name(f"{p.stem}_clean.parquet")

            # Phase 5: Export processed clean data with ZSTD compression
            df_clean.write_parquet(ruta_salida, compression="zstd")

            print(
                f"[SUCCESS] Cleaned validation data saved to: {ruta_salida.name} | Rows: {len(df_clean)}"
            )

        except Exception as e:
            print(f"[ERROR] Failed to process file {p.name}: {e}")

    print("[COMPLETED] Validation data ETL pipeline execution finished.")


if __name__ == "__main__":

    ejecutar_etl_validaciones()
