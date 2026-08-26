import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path

    import polars as pl

    return Path, pl


@app.cell
def _(Path):
    Path.cwd()


@app.cell
def _(Path, pl):
    RAW_DIR = Path("data/raw")
    PROCESSED_DIR = Path("data/processed")

    def convert_file(input_path: Path) -> None:
        relative_path = input_path.relative_to(RAW_DIR)
        output_path = PROCESSED_DIR / relative_path.with_suffix(".parquet")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"{input_path} -> {output_path}")

        df = pl.read_csv(
            input_path,
            encoding="utf-8",
            schema_overrides={
                "route_id": pl.String,
                "shape_id": pl.String,
                "stop_id": pl.String,
            },
        )
        df.write_parquet(output_path)

    for input_path in RAW_DIR.rglob("*.txt"):
        convert_file(input_path)


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
