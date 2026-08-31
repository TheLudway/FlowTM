import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Exploración de Validaciones y Salidas")


@app.cell(hide_code=True)
def _():
    from pathlib import Path

    import polars as pl

    return Path, pl


@app.cell(hide_code=True)
def _(Path):
    processed_dir = Path("data/processed")

    # Filtro blindado: Excluye GTFS y solo busca archivos de validaciones y salidas
    archivos_val = sorted(
        [
            str(p)
            for p in processed_dir.rglob("*.parquet")
            if "gtfs" not in str(p).lower() and "valida" in str(p).lower()
        ]
    )

    archivos_sal = sorted(
        [
            str(p)
            for p in processed_dir.rglob("*.parquet")
            if "gtfs" not in str(p).lower() and "salida" in str(p).lower()
        ]
    )

    return archivos_sal, archivos_val, processed_dir


@app.cell
def _(archivos_val, pl):
    # 1. Cargar y visualizar muestra de Validaciones Troncales
    df_validaciones = None
    muestra_validaciones = None

    if archivos_val:
        df_validaciones = pl.scan_parquet(archivos_val)
        muestra_validaciones = df_validaciones.head(10).collect()

    muestra_validaciones
    return df_validaciones, muestra_validaciones


@app.cell
def _(df_validaciones, pl):
    # 2. Top 15 Estaciones con mayor volumen de validaciones (Demanda de usuarios)
    top_estaciones = None

    if df_validaciones is not None:
        col_estacion = next(
            (c for c in df_validaciones.columns if "estacion" in c.lower()),
            None,
        )
        if col_estacion:
            top_estaciones = (
                df_validaciones.group_by(col_estacion)
                .agg(pl.len().alias("total_validaciones"))
                .sort("total_validaciones", descending=True)
                .head(15)
                .collect()
            )

    top_estaciones
    return (top_estaciones,)


@app.cell
def _(df_validaciones, pl):
    # 3. Distribución por Perfil de Tarjeta (Adulto, Sisbén, Adulto Mayor, etc.)
    perfiles = None

    if df_validaciones is not None:
        col_perfil = next(
            (c for c in df_validaciones.columns if "perfil" in c.lower()),
            None,
        )
        if col_perfil:
            perfiles = (
                df_validaciones.group_by(col_perfil)
                .agg(pl.len().alias("cantidad_transacciones"))
                .sort("cantidad_transacciones", descending=True)
                .collect()
            )

    perfiles
    return (perfiles,)


@app.cell
def _(archivos_sal, pl):
    # 4. Cargar y visualizar muestra de Salidas y Torniquetes
    df_salidas = None
    muestra_salidas = None

    if archivos_sal:
        df_salidas = pl.scan_parquet(archivos_sal)
        muestra_salidas = df_salidas.head(10).collect()

    muestra_salidas
    return df_salidas, muestra_salidas


@app.cell
def _(df_salidas, pl):
    # 5. Resumen de Entradas vs Salidas totales registradas en torniquetes
    balance_torniquetes = None

    if df_salidas is not None:
        cols = df_salidas.columns
        col_entradas = next((c for c in cols if "entradas" in c.lower()), None)
        col_salidas = next((c for c in cols if "salidas" in c.lower()), None)

        if col_entradas and col_salidas:
            balance_torniquetes = df_salidas.select(
                [
                    pl.col(col_entradas).sum().alias("total_entradas"),
                    pl.col(col_salidas).sum().alias("total_salidas"),
                ]
            ).collect()

    balance_torniquetes
    return (balance_torniquetes,)


if __name__ == "__main__":
    app.run()
