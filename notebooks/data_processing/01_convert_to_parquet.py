import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Conversión a Parquet")


@app.cell
def _():
    import contextlib
    from pathlib import Path

    import polars as pl

    return Path, contextlib, pl


@app.cell
def _(Path):
    Path.cwd()
    return


@app.cell(hide_code=True)
def _(Path, contextlib, pl):
    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")

    date_columns = [
        "date",
        "start_date",
        "end_date",
        "feed_start_date",
        "feed_end_date",
    ]

    time_columns = [
        "start_time",
        "end_time",
        "arrival_time",
        "departure_time",
    ]

    def gtfs_time_to_seconds(column: str) -> pl.Expr:
        parts = pl.col(column).str.split_exact(":", 2)

        return (
            parts.struct.field("field_0").cast(pl.Int64) * 3600
            + parts.struct.field("field_1").cast(pl.Int64) * 60
            + parts.struct.field("field_2").cast(pl.Int64)
        )

    def convert_gtfs_file(input_path: Path) -> None:
        relative_path = input_path.relative_to(raw_dir)
        output_path = processed_dir / relative_path.with_suffix(".parquet")

        # Si el archivo parquet ya existe, no gastar tiempo re-procesándolo
        if output_path.exists():
            print(f"Saltando GTFS (ya existe): {output_path}")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Convirtiendo GTFS: {input_path} -> {output_path}")

        df = pl.read_csv(
            input_path,
            encoding="utf-8",
            schema_overrides={
                # GTFS identifiers
                "route_id": pl.String,
                "shape_id": pl.String,
                "stop_id": pl.String,
                # Dates
                "date": pl.String,
                "start_date": pl.String,
                "end_date": pl.String,
                "feed_start_date": pl.String,
                "feed_end_date": pl.String,
                # Times
                "start_time": pl.String,
                "end_time": pl.String,
                "arrival_time": pl.String,
                "departure_time": pl.String,
            },
        )

        # Convert date columns
        columns = [column for column in date_columns if column in df.columns]

        if columns:
            df = df.with_columns(
                [
                    pl.col(column).str.strptime(
                        pl.Date,
                        format="%Y%m%d",
                        strict=False,
                    )
                    for column in columns
                ]
            )

        # Convert GTFS time columns to seconds since midnight
        columns = [column for column in time_columns if column in df.columns]

        if columns:
            df = df.with_columns(
                [gtfs_time_to_seconds(column).alias(column) for column in columns]
            )

        df.write_parquet(output_path)

    def convert_csv_file(input_path: Path) -> None:
        relative_path = input_path.relative_to(raw_dir)
        output_path = processed_dir / relative_path.with_suffix(".parquet")

        # Si el archivo parquet ya existe, no gastar tiempo re-procesándolo
        if output_path.exists():
            print(f"Saltando CSV (ya existe): {output_path}")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Convirtiendo CSV: {input_path} -> {output_path}")

        # Lectura con inferencia amplia de tipos para validaciones y salidas
        df = pl.read_csv(
            input_path,
            infer_schema_length=10000,
            ignore_errors=True,
            null_values=["", "NA", "N/A", "null", "NULL"],
        )

        # Convertir columnas que contengan fechas o marcas de tiempo
        for column in df.columns:
            col_lower = column.lower().strip()
            if "fecha" in col_lower:
                with contextlib.suppress(Exception):
                    df = df.with_columns(
                        pl.col(column).str.to_datetime(strict=False).alias(column)
                    )

        df.write_parquet(output_path)

    # Convert GTFS text files
    for input_path in raw_dir.rglob("*.txt"):
        convert_gtfs_file(input_path)

    # Convert CSV files (Validaciones y Salidas)
    for input_path in raw_dir.rglob("*.csv"):
        convert_csv_file(input_path)

    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
