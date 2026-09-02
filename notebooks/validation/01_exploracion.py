import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Validation and Output Exploration")


@app.cell(hide_code=True)
def _():
    from pathlib import Path

    import marimo as mo
    import polars as pl

    return Path, mo, pl


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 🚍 Exploración de Validaciones y Salidas Troncales
    Análisis exploratorio de la demanda de pasajeros y flujo en torniquetes del sistema TransMilenio.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. Muestra de Validaciones (Demanda de Pasajeros)
    Muestra de los registros individuales de acceso al componente troncal.
    """)
    return


@app.cell(hide_code=True)
def _(Path, pl):
    # Locate validation files directly in their subfolder
    val_files = sorted(
        [
            str(p)
            for p in Path(
                "data/processed/validaciones_salidas/validacion_troncal"
            ).rglob("*.parquet")
        ]
    )

    validaciones = pl.read_parquet(val_files[0]) if val_files else None
    validaciones
    return (validaciones,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Top 15 Estaciones con Mayor Volumen de Validaciones
    Ranking de las estaciones con mayor afluencia de pasajeros en el día.
    """)
    return


@app.cell(hide_code=True)
def _(pl, validaciones):
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
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Distribución por Perfil de Tarjeta
    Desglose de usuarios según su categoría tarifaria (Adulto, Sisbén, Adulto Mayor, etc.).
    """)
    return


@app.cell(hide_code=True)
def _(pl, validaciones):
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
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Muestra de Salidas y Torniquetes
    Registros de conteo de torniquetes por cuarto de hora en accesos de estación.
    """)
    return


@app.cell(hide_code=True)
def _(Path, pl):
    # Locate turnstile output files directly in their subfolder
    sal_files = sorted(
        [
            str(p)
            for p in Path("data/processed/validaciones_salidas/salidas_troncal").rglob(
                "*.parquet"
            )
        ]
    )

    salidas = pl.read_parquet(sal_files[0]) if sal_files else None
    salidas
    return


if __name__ == "__main__":
    app.run()
