import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Validation Exploration")


@app.cell(hide_code=True)
def _():
    from pathlib import Path

    import polars as pl

    return Path, pl


@app.cell(hide_code=True)
def _(Path, pl):
    # 1. Load validation sample (Tullave card entries)
    archivos_val = sorted(
        [
            str(p)
            for p in Path("data/processed").rglob("*.parquet")
            if p.stem.isdigit() and "20260825" not in p.name
        ]
    )

    validaciones = pl.read_parquet(archivos_val[0])
    validaciones
    return archivos_val, validaciones


@app.cell(hide_code=True)
def _(pl, validaciones):
    # 2. Top 15 Stations with highest passenger demand
    col_estacion = next(
        (c for c in validaciones.columns if "estacion" in c.lower()),
        "Estacion_Parada",
    )
    top_estaciones = (
        validaciones.group_by(col_estacion)
        .agg(pl.len().alias("total_validaciones"))
        .sort("total_validaciones", descending=True)
        .head(15)
    )
    top_estaciones
    return col_estacion, top_estaciones


@app.cell(hide_code=True)
def _(pl, validaciones):
    # 3. Distribution by Card Profile (Adult, Subsidized, Senior, etc.)
    col_perfil = next(
        (c for c in validaciones.columns if "perfil" in c.lower()),
        "Nombre_Perfil",
    )
    perfiles = (
        validaciones.group_by(col_perfil)
        .agg(pl.len().alias("cantidad_usuarios"))
        .sort("cantidad_usuarios", descending=True)
    )
    perfiles
    return col_perfil, perfiles


@app.cell(hide_code=True)
def _(Path, pl):
    # 4. Load turnstile output sample (Quarter-hour counts)
    archivos_sal = sorted(
        [
            str(p)
            for p in Path("data/processed").rglob("*.parquet")
            if "20260825" in p.name or "salida" in p.name.lower()
        ]
    )

    salidas = pl.read_parquet(archivos_sal[0]) if archivos_sal else None
    salidas
    return archivos_sal, salidas


if __name__ == "__main__":
    app.run()
