import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Limpieza GTFS
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Importación librerias / datos
    """)
    return


@app.cell
def _():
    import marimo as mo
    import polars as pl

    return mo, pl


@app.cell
def _(pl):
    agencias = pl.read_parquet("../../data/processed/gtfs/gtfs_20260727/agency.parquet")
    routes = pl.read_parquet("../../data/processed/gtfs/gtfs_20260727/routes.parquet")
    shapes = pl.read_parquet("../../data/processed/gtfs/gtfs_20260727/shapes.parquet")
    stop_times = pl.read_parquet("../../data/processed/gtfs/gtfs_20260727/stop_times.parquet")
    stops = pl.read_parquet("../../data/processed/gtfs/gtfs_20260727/stops.parquet")
    trips = pl.read_parquet("../../data/processed/gtfs/gtfs_20260727/trips.parquet")
    return agencias, routes, shapes, stop_times, stops, trips


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Limpieza agency
    """)
    return


@app.cell
def _(agencias, pl):
    agencias_clean_lazy = (
        agencias.lazy()
        .filter(pl.col("agency_id") == 1)
        .unique(subset=["agency_id"])
        .drop([
            "agency_url",
            "agency_timezone",
            "agency_lang",
            "agency_phone",
            "agency_fare_url"
        ])
    )
    return (agencias_clean_lazy,)


@app.cell
def _(agencias_clean_lazy):
    df_agencias_preview = agencias_clean_lazy.collect()
    return (df_agencias_preview,)


@app.cell
def _(agencias, df_agencias_preview):
    total_original = agencias.height
    total_limpio = df_agencias_preview.height
    total_eliminado = total_original - total_limpio
    return total_eliminado, total_limpio, total_original


@app.cell
def _(total_eliminado, total_limpio, total_original):
    print("\n--- LIMPIEZA: AGENCY ---")
    print(f"Registros originales:  {total_original}")
    print(f"Registros conservados: {total_limpio}")
    print(f"Registros eliminados:  {total_eliminado}")
    print("-----------------------------------\n")
    return


@app.cell
def _(df_agencias_preview):
    df_agencias_preview
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### creacion archivo .parquet
    """)
    return


@app.cell
def _(df_agencias_preview):
    df_agencias_preview.write_parquet ("../../data/processed/gtfs/gtfs_20260727/agency_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Limpieza routes
    """)
    return


@app.cell
def _(agencias_clean_lazy, routes):
    routes_clean_lazy = (
        routes.lazy()
        .drop_nulls(subset=["route_id", "agency_id"])
        .join(agencias_clean_lazy, on="agency_id", how="semi")
        .drop(["route_color", "route_text_color"])
    )
    return (routes_clean_lazy,)


@app.cell
def _(routes_clean_lazy):
    df_routes_clean = routes_clean_lazy.collect()
    return (df_routes_clean,)


@app.cell
def _(df_routes_clean, routes):
    total_rutas_original = routes.height
    total_rutas_limpias = df_routes_clean.height
    total_rutas_eliminadas = total_rutas_original - total_rutas_limpias
    return total_rutas_eliminadas, total_rutas_limpias, total_rutas_original


@app.cell
def _(total_rutas_eliminadas, total_rutas_limpias, total_rutas_original):
    print("\n--- LIMPIEZA: ROUTES ---")
    print(f"Registros originales:  {total_rutas_original:,}")
    print(f"Registros conservadas: {total_rutas_limpias:,}")
    print(f"Registros eliminadas:  {total_rutas_eliminadas:,}")
    print("-----------------------------------\n")
    return


@app.cell
def _(df_routes_clean):
    df_routes_clean
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Creacion archivo .parquet
    """)
    return


@app.cell
def _(df_routes_clean):
    df_routes_clean.write_parquet("../../data/processed/gtfs/gtfs_20260727/routes_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Limpieza stops
    """)
    return


@app.cell
def _(pl, routes_clean_lazy, stop_times, stops, trips):
    trips_agencia1_lazy = (
        trips.lazy()
        .drop_nulls(subset=["trip_id", "route_id"])
        .join(routes_clean_lazy, on="route_id", how="semi")
    )

    stop_times_agencia1_lazy = (
        stop_times.lazy()
        .drop_nulls(subset=["trip_id", "stop_id"])
        .join(trips_agencia1_lazy, on="trip_id", how="semi")
    )

    active_stops = (
        stops.lazy()
        .drop_nulls(subset=["stop_id"])
        .unique(subset=["stop_id"])
        .join(stop_times_agencia1_lazy, on="stop_id", how="semi")
    )

    parent_ids = active_stops.select("parent_station").drop_nulls().unique()

    parent_stops = (
        stops.lazy()
        .drop_nulls(subset=["stop_id"])
        .unique(subset=["stop_id"])
        .join(parent_ids, left_on="stop_id", right_on="parent_station", how="semi")
    )

    stops_clean_lazy = (
        pl.concat([active_stops, parent_stops])
        .unique(subset=["stop_id"])
        .drop(["zone_id"])
    )
    return (stops_clean_lazy,)


@app.cell
def _(stops_clean_lazy):
    df_stops_clean = stops_clean_lazy.collect()
    return (df_stops_clean,)


@app.cell
def _(df_stops_clean, stops):
    total_stops_original = stops.height
    total_stops_limpios = df_stops_clean.height
    total_stops_eliminados = total_stops_original - total_stops_limpios
    return total_stops_eliminados, total_stops_limpios, total_stops_original


@app.cell
def _(total_stops_eliminados, total_stops_limpios, total_stops_original):
    print("\n--- LIMPIEZA: STOPS ---")
    print(f"Registros originales:  {total_stops_original:,}")
    print(f"Registros conservadas: {total_stops_limpios:,}")
    print(f"Registros eliminadas:  {total_stops_eliminados:,}")
    print("----------------------------------\n")
    return


@app.cell
def _(df_stops_clean):
    df_stops_clean
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### creacion .parquet
    """)
    return


@app.cell
def _(df_stops_clean):
    df_stops_clean.write_parquet("../../data/processed/gtfs/gtfs_20260727/stops_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Limpieza trips
    """)
    return


@app.cell
def _(routes_clean_lazy, trips):
    trips_clean_lazy = (
        trips.lazy()
        .drop_nulls(subset=["trip_id", "route_id"])
        .unique(subset=["trip_id"])
        .join(routes_clean_lazy, on="route_id", how="semi")
        .drop(["trip_headsign"])
    )
    return (trips_clean_lazy,)


@app.cell
def _(trips_clean_lazy):
    df_trips_clean = trips_clean_lazy.collect()
    return (df_trips_clean,)


@app.cell
def _(df_trips_clean, trips):
    total_trips_original = trips.height
    total_trips_limpios = df_trips_clean.height
    total_trips_eliminados = total_trips_original - total_trips_limpios
    return total_trips_eliminados, total_trips_limpios, total_trips_original


@app.cell
def _(total_trips_eliminados, total_trips_limpios, total_trips_original):
    print("\n--- LIMPIEZA: TRIPS ---")
    print(f"Registros originales:  {total_trips_original:,}")
    print(f"Registros conservados: {total_trips_limpios:,}")
    print(f"Registros eliminados:  {total_trips_eliminados:,}")
    print("-----------------------------------\n")
    return


@app.cell
def _(df_trips_clean):
    df_trips_clean
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### creacion .parquet
    """)
    return


@app.cell
def _(df_trips_clean):
    df_trips_clean.write_parquet("../../data/processed/gtfs/gtfs_20260727/trips_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Limpieza stop_times
    """)
    return


@app.cell
def _(stop_times, stops_clean_lazy, trips_clean_lazy):
    stop_times_clean_lazy = (
        stop_times.lazy()
        .join(trips_clean_lazy.select("trip_id"), on="trip_id", how="semi")
        .join(stops_clean_lazy.select("stop_id"), on="stop_id", how="semi")
        .drop(["timepoint"])
    )
    return (stop_times_clean_lazy,)


@app.cell
def _(stop_times_clean_lazy):
    df_stop_times_clean = stop_times_clean_lazy.collect()
    return (df_stop_times_clean,)


@app.cell
def _(df_stop_times_clean, stop_times):
    total_stop_times_original = stop_times.height
    total_stop_times_limpios = df_stop_times_clean.height
    total_stop_times_eliminados = total_stop_times_original - total_stop_times_limpios
    return (
        total_stop_times_eliminados,
        total_stop_times_limpios,
        total_stop_times_original,
    )


@app.cell
def _(
    total_stop_times_eliminados,
    total_stop_times_limpios,
    total_stop_times_original,
):
    print("\n--- LIMPIEZA: STOP_TIMES ---")
    print(f"Registros originales:  {total_stop_times_original:,}")
    print(f"Registros conservados: {total_stop_times_limpios:,}")
    print(f"Registros eliminados:  {total_stop_times_eliminados:,}")
    print("---------------------------------------\n")
    return


@app.cell
def _(df_stop_times_clean):
    df_stop_times_clean
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### creacion .parquet
    """)
    return


@app.cell
def _(df_stop_times_clean):
    df_stop_times_clean.write_parquet("../../data/processed/gtfs/gtfs_20260727/stop_times_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Limpieza shapes
    """)
    return


@app.cell
def _(trips_clean_lazy):
    valid_shapes_lazy = trips_clean_lazy.select("shape_id").drop_nulls().unique()
    return (valid_shapes_lazy,)


@app.cell
def _(shapes, valid_shapes_lazy):
    shapes_clean_lazy = (
        shapes.lazy()
        .drop_nulls(subset=["shape_id"])
        .join(valid_shapes_lazy, on="shape_id", how="semi")
    )
    return (shapes_clean_lazy,)


@app.cell
def _(shapes_clean_lazy):
    df_shapes_clean = shapes_clean_lazy.collect()
    return (df_shapes_clean,)


@app.cell
def _(df_shapes_clean, shapes):
    total_shapes_original = shapes.height
    total_shapes_limpios = df_shapes_clean.height
    total_shapes_eliminados = total_shapes_original - total_shapes_limpios
    return total_shapes_eliminados, total_shapes_limpios, total_shapes_original


@app.cell
def _(total_shapes_eliminados, total_shapes_limpios, total_shapes_original):
    print("\n--- LIMPIEZA: SHAPES ---")
    print(f"Registros originales:  {total_shapes_original:,}")
    print(f"Registros conservados: {total_shapes_limpios:,}")
    print(f"Registros eliminados:  {total_shapes_eliminados:,}")
    print("-----------------------------------\n")
    return


@app.cell
def _(df_shapes_clean):
    df_shapes_clean
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### creacion .parquet
    """)
    return


@app.cell
def _(df_shapes_clean):
    df_shapes_clean.write_parquet("../../data/processed/gtfs/gtfs_20260727/shapes_clean.parquet")
    return


if __name__ == "__main__":
    app.run()
