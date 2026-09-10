from pathlib import Path

import polars as pl


def normalizar_estaciones(columna: str) -> list[pl.Expr]:
    """Apply vectorized Polars expressions to extract keys and normalize station names."""
    return [
        # 1. Extract exact 5-digit station code O(1)
        pl.col(columna)
        .str.extract(r"\((\d{5})\)", 1)
        .alias("CODIGO_ESTACION"),
        # 2. Extract 2-digit trunk code
        pl.col(columna)
        .str.extract(r"\((\d{2})\)\d{3}", 1)
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


def ejecutar_etl_salidas():
    """Execute the Phase 5 ETL batch pipeline exclusively for turnstile output Parquet files."""
    project_root = Path(__file__).resolve().parents[3]
    ruta_salidas = (
        project_root / "data/processed/validaciones_salidas/salidas_troncal"
    )

    # Discover original turnstile output Parquet files (excluding previous _clean files)
    try:
        archivos_salidas = [
            p
            for p in sorted(ruta_salidas.rglob("*.parquet"))
            if not p.stem.endswith("_clean")
        ]
        print(
            f"[INFO] Discovered {len(archivos_salidas)} original parquet files in {ruta_salidas}"
        )
    except Exception as e:
        print(f"[ERROR] Failed to scan directory {ruta_salidas}: {e}")
        return

    # Specific target columns for turnstile outputs
    cols_utiles_salidas = [
        "Tiempo",
        "Entradas_E",
        "Salidas_S",
    ]

    for p in archivos_salidas:
        try:
            print(f"[PROCESSING] Starting processing for file: {p.name}")

            # Lazy evaluation reading
            lf = pl.scan_parquet(p)
            cols_existentes = lf.collect_schema().names()

            # Identify station column dynamically
            col_est = (
                "Estacion"
                if "Estacion" in cols_existentes
                else next(
                    (c for c in cols_existentes if "estacion" in c.lower()),
                    None,
                )
            )

            if not col_est:
                raise ValueError(
                    f"No station column found in schema for file {p.name}"
                )

            # Select turnstile target metrics present in the schema
            cols_a_conservar = [
                c for c in cols_utiles_salidas if c in cols_existentes
            ]

            # Apply vectorized normalization expressions alongside target metrics
            lf_clean = lf.select(
                cols_a_conservar + normalizar_estaciones(col_est)
            )

            # Collect lazy computation into eager DataFrame
            df_clean = lf_clean.collect()

            # Target output path definition with _clean suffix in salidas_troncal
            ruta_salida = p.with_name(f"{p.stem}_clean.parquet")

            # Export processed clean data with ZSTD compression
            df_clean.write_parquet(ruta_salida, compression="zstd")

            print(
                f"[SUCCESS] Cleaned turnstile data saved to: {ruta_salida.name} | Rows: {len(df_clean)}"
            )

        except Exception as e:
            print(f"[ERROR] Failed to process file {p.name}: {e}")

    print("[COMPLETED] Turnstile outputs ETL pipeline execution finished.")


if __name__ == "__main__":
    ejecutar_etl_salidas()
