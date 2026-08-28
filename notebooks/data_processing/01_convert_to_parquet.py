import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Exploración GTFS")


@app.cell
def _():
    from pathlib import Path

    import polars as pl

    return Path, pl


@app.cell
def _(Path):
    Path.cwd()
    return


@app.cell(hide_code=True)
def _(Path, pl):
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


    def convert_file(input_path: Path) -> None:
        relative_path = input_path.relative_to(raw_dir)
        output_path = processed_dir / relative_path.with_suffix(".parquet")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"{input_path} -> {output_path}")

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
        columns = [
            column
            for column in date_columns
            if column in df.columns
        ]

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
        columns = [
            column
            for column in time_columns
            if column in df.columns
        ]

        if columns:
            df = df.with_columns(
                [
                    gtfs_time_to_seconds(column).alias(column)
                    for column in columns
                ]
            )

        df.write_parquet(output_path)


    for input_path in raw_dir.rglob("*.txt"):
        convert_file(input_path)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
