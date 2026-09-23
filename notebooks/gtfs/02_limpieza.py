import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # GTFS Data Cleaning
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Library and Data Import
    """)
    return


@app.cell
def _():
    from pathlib import Path

    import marimo as mo
    import polars as pl

    return Path, mo, pl


@app.cell
def _(Path):
    # Locate the project root directory safely depending on the execution context.
    root_dir = (
        Path(__file__).resolve().parents[2] if "__file__" in globals() else Path.cwd()
    )
    if not (root_dir / "data").exists() and (Path.cwd() / "data").exists():
        root_dir = Path.cwd()

    base_gtfs = root_dir / "data" / "processed" / "gtfs" / "gtfs_20260727"
    return (base_gtfs,)


@app.cell
def _(base_gtfs, pl):
    agency_dataframe = pl.read_parquet(base_gtfs / "agency.parquet")
    calendar_dataframe = pl.read_parquet(base_gtfs / "calendar.parquet")
    calendar_dates_dataframe = pl.read_parquet(base_gtfs / "calendar_dates.parquet")
    frequencies_dataframe = pl.read_parquet(base_gtfs / "frequencies.parquet")
    routes_dataframe = pl.read_parquet(base_gtfs / "routes.parquet")
    shapes_dataframe = pl.read_parquet(base_gtfs / "shapes.parquet")
    stop_times_dataframe = pl.read_parquet(base_gtfs / "stop_times.parquet")
    stops_dataframe = pl.read_parquet(base_gtfs / "stops.parquet")
    trips_dataframe = pl.read_parquet(base_gtfs / "trips.parquet")
    return (
        agency_dataframe,
        calendar_dataframe,
        calendar_dates_dataframe,
        frequencies_dataframe,
        routes_dataframe,
        shapes_dataframe,
        stop_times_dataframe,
        stops_dataframe,
        trips_dataframe,
    )


@app.cell
def _(
    agency_dataframe,
    base_gtfs,
    calendar_dataframe,
    calendar_dates_dataframe,
    frequencies_dataframe,
    routes_dataframe,
    shapes_dataframe,
    stop_times_dataframe,
    stops_dataframe,
    trips_dataframe,
):
    (
        agency_dataframe,
        base_gtfs,
        calendar_dataframe,
        frequencies_dataframe,
        routes_dataframe,
        shapes_dataframe,
        stop_times_dataframe,
        stops_dataframe,
        trips_dataframe,
        calendar_dates_dataframe,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Agency Cleaning
    """)
    return


@app.cell
def _(agency_dataframe, pl):
    # Isolate the main agency (agency_id = 1) and drop metadata.
    clean_agency_lazy = (
        agency_dataframe.lazy()
        .filter(pl.col("agency_id") == 1)
        .unique(subset=["agency_id"])
        .drop(
            [
                "agency_url",
                "agency_timezone",
                "agency_lang",
                "agency_phone",
                "agency_fare_url",
            ]
        )
    )
    return (clean_agency_lazy,)


@app.cell
def _(clean_agency_lazy):
    clean_agency_dataframe = clean_agency_lazy.collect()
    return (clean_agency_dataframe,)


@app.cell
def _(agency_dataframe, clean_agency_dataframe):
    original_agency_count = agency_dataframe.height
    clean_agency_count = clean_agency_dataframe.height
    removed_agency_count = original_agency_count - clean_agency_count
    return clean_agency_count, original_agency_count, removed_agency_count


@app.cell
def _(clean_agency_count, original_agency_count, removed_agency_count):
    print("\n[INFO] --- LIMPIEZA: AGENCY ---")
    print(f"[INFO] Registros originales:  {original_agency_count:,}")
    print(f"[INFO] Registros conservados: {clean_agency_count:,}")
    print(f"[INFO] Registros eliminados:  {removed_agency_count:,}")
    print("-----------------------------------\n")
    return


@app.cell
def _(clean_agency_dataframe):
    clean_agency_dataframe
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Export to Parquet
    """)
    return


@app.cell
def _(base_gtfs, clean_agency_dataframe):
    clean_agency_dataframe.write_parquet(base_gtfs / "agency_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Routes Cleaning
    """)
    return


@app.cell
def _(clean_agency_lazy, routes_dataframe):
    # Keep only routes belonging to the valid agency (Transmilenio troncal).
    clean_routes_lazy = (
        routes_dataframe.lazy()
        .drop_nulls(subset=["route_id", "agency_id"])
        .join(clean_agency_lazy, on="agency_id", how="semi")
        .drop(["route_color", "route_text_color"])
    )
    return (clean_routes_lazy,)


@app.cell
def _(clean_routes_lazy):
    clean_routes_dataframe = clean_routes_lazy.collect()
    return (clean_routes_dataframe,)


@app.cell
def _(clean_routes_dataframe, routes_dataframe):
    original_routes_count = routes_dataframe.height
    clean_routes_count = clean_routes_dataframe.height
    removed_routes_count = original_routes_count - clean_routes_count
    return clean_routes_count, original_routes_count, removed_routes_count


@app.cell
def _(clean_routes_count, original_routes_count, removed_routes_count):
    print("\n[INFO] --- LIMPIEZA: ROUTES ---")
    print(f"[INFO] Registros originales:  {original_routes_count:,}")
    print(f"[INFO] Registros conservados: {clean_routes_count:,}")
    print(f"[INFO] Registros eliminados:  {removed_routes_count:,}")
    print("-----------------------------------\n")
    return


@app.cell
def _(clean_routes_dataframe):
    clean_routes_dataframe
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Export to Parquet
    """)
    return


@app.cell
def _(base_gtfs, clean_routes_dataframe):
    clean_routes_dataframe.write_parquet(base_gtfs / "routes_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Stops Cleaning
    """)
    return


@app.cell
def _(
    clean_routes_lazy,
    pl,
    stop_times_dataframe,
    stops_dataframe,
    trips_dataframe,
):
    # Filter stop times using valid routes to identify actively used stops.
    filtered_trips_lazy = (
        trips_dataframe.lazy()
        .drop_nulls(subset=["trip_id", "route_id"])
        .join(clean_routes_lazy, on="route_id", how="semi")
    )

    filtered_stop_times_lazy = (
        stop_times_dataframe.lazy()
        .drop_nulls(subset=["trip_id", "stop_id"])
        .join(filtered_trips_lazy, on="trip_id", how="semi")
    )

    active_stops_lazy = (
        stops_dataframe.lazy()
        .drop_nulls(subset=["stop_id"])
        .unique(subset=["stop_id"])
        .join(filtered_stop_times_lazy, on="stop_id", how="semi")
    )

    # Retain parent stations that group the active stops.
    parent_station_ids_lazy = (
        active_stops_lazy.select("parent_station").drop_nulls().unique()
    )

    parent_stops_lazy = (
        stops_dataframe.lazy()
        .drop_nulls(subset=["stop_id"])
        .unique(subset=["stop_id"])
        .join(
            parent_station_ids_lazy,
            left_on="stop_id",
            right_on="parent_station",
            how="semi",
        )
    )

    # Combine active stops and parents, removing duplicates and unused zones.
    clean_stops_lazy = (
        pl.concat([active_stops_lazy, parent_stops_lazy])
        .unique(subset=["stop_id"])
        .drop(["zone_id"])
    )
    return (clean_stops_lazy,)


@app.cell
def _(clean_stops_lazy):
    clean_stops_dataframe = clean_stops_lazy.collect()
    return (clean_stops_dataframe,)


@app.cell
def _(clean_stops_dataframe, stops_dataframe):
    original_stops_count = stops_dataframe.height
    clean_stops_count = clean_stops_dataframe.height
    removed_stops_count = original_stops_count - clean_stops_count
    return clean_stops_count, original_stops_count, removed_stops_count


@app.cell
def _(clean_stops_count, original_stops_count, removed_stops_count):
    print("\n[INFO] --- LIMPIEZA: STOPS ---")
    print(f"[INFO] Registros originales:  {original_stops_count:,}")
    print(f"[INFO] Registros conservados: {clean_stops_count:,}")
    print(f"[INFO] Registros eliminados:  {removed_stops_count:,}")
    print("----------------------------------\n")
    return


@app.cell
def _(clean_stops_dataframe):
    clean_stops_dataframe
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Export to Parquet
    """)
    return


@app.cell
def _(base_gtfs, clean_stops_dataframe):
    clean_stops_dataframe.write_parquet(base_gtfs / "stops_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Calendar Cleaning
    """)
    return


@app.cell
def _(calendar_dataframe, pl):
    # Available only on weekdays (Monday to Friday).
    clean_calendar_lazy = calendar_dataframe.lazy().filter(
        (pl.col("monday") == 1)
        & (pl.col("tuesday") == 1)
        & (pl.col("wednesday") == 1)
        & (pl.col("thursday") == 1)
        & (pl.col("friday") == 1)
    )
    return (clean_calendar_lazy,)


@app.cell
def _(clean_calendar_lazy):
    clean_calendar_dataframe = clean_calendar_lazy.collect()
    return (clean_calendar_dataframe,)


@app.cell
def _(calendar_dataframe, clean_calendar_dataframe):
    original_calendar_count = calendar_dataframe.height
    clean_calendar_count = clean_calendar_dataframe.height
    removed_calendar_count = original_calendar_count - clean_calendar_count
    return (
        clean_calendar_count,
        original_calendar_count,
        removed_calendar_count,
    )


@app.cell
def _(clean_calendar_count, original_calendar_count, removed_calendar_count):
    print("\n[INFO] --- LIMPIEZA CALENDAR (DÍAS HÁBILES) ---")
    print(f"[INFO] Calendarios originales:  {original_calendar_count:,}")
    print(f"[INFO] Calendarios conservados: {clean_calendar_count:,}")
    print(f"[INFO] Calendarios eliminados:  {removed_calendar_count:,}")
    print("----------------------------------------------------\n")
    return


@app.cell
def _(clean_calendar_dataframe):
    clean_calendar_dataframe
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Export to Parquet
    """)
    return


@app.cell
def _(base_gtfs, clean_calendar_dataframe):
    clean_calendar_dataframe.write_parquet(base_gtfs / "calendar_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Calendar Dates Cleaning
    """)
    return


@app.cell
def _(calendar_dates_dataframe, clean_calendar_lazy):
    # Remove orphaned date exceptions linked to discarded weekend schedules.
    clean_calendar_dates_lazy = calendar_dates_dataframe.lazy().join(
        clean_calendar_lazy, on="service_id", how="semi"
    )
    return (clean_calendar_dates_lazy,)


@app.cell
def _(clean_calendar_dates_lazy):
    clean_calendar_dates_dataframe = clean_calendar_dates_lazy.collect()
    return (clean_calendar_dates_dataframe,)


@app.cell
def _(calendar_dates_dataframe, clean_calendar_dates_dataframe):
    original_calendar_dates_count = calendar_dates_dataframe.height
    clean_calendar_dates_count = clean_calendar_dates_dataframe.height
    removed_calendar_dates_count = (
        original_calendar_dates_count - clean_calendar_dates_count
    )
    return (
        clean_calendar_dates_count,
        original_calendar_dates_count,
        removed_calendar_dates_count,
    )


@app.cell
def _(
    clean_calendar_dates_count,
    original_calendar_dates_count,
    removed_calendar_dates_count,
):
    print("\n[INFO] --- LIMPIEZA CALENDAR DATES ---")
    print(f"[INFO] Registros originales:  {original_calendar_dates_count:,}")
    print(f"[INFO] Registros conservados: {clean_calendar_dates_count:,}")
    print(f"[INFO] Registros eliminados:  {removed_calendar_dates_count:,}")
    print("---------------------------------------------------------\n")
    return


@app.cell
def _(clean_calendar_dates_dataframe):
    clean_calendar_dates_dataframe
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Export to Parquet
    """)
    return


@app.cell
def _(base_gtfs, clean_calendar_dates_dataframe):
    clean_calendar_dates_dataframe.write_parquet(
        base_gtfs / "calendar_dates_clean.parquet"
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Trips Cleaning
    """)
    return


@app.cell
def _(clean_calendar_lazy, clean_routes_lazy, trips_dataframe):
    # Cascade filter: isolate trips linked to active weekday schedules and valid routes.
    clean_trips_lazy = (
        trips_dataframe.lazy()
        .drop_nulls(subset=["trip_id", "route_id", "service_id"])
        .unique(subset=["trip_id"])
        .join(clean_routes_lazy, on="route_id", how="semi")
        .join(clean_calendar_lazy, on="service_id", how="semi")
        .drop(["trip_headsign"])
    )
    return (clean_trips_lazy,)


@app.cell
def _(clean_trips_lazy):
    clean_trips_dataframe = clean_trips_lazy.collect()
    return (clean_trips_dataframe,)


@app.cell
def _(clean_trips_dataframe, trips_dataframe):
    original_trips_count = trips_dataframe.height
    clean_trips_count = clean_trips_dataframe.height
    removed_trips_count = original_trips_count - clean_trips_count
    return clean_trips_count, original_trips_count, removed_trips_count


@app.cell
def _(clean_trips_count, original_trips_count, removed_trips_count):
    print("\n[INFO] --- LIMPIEZA: TRIPS ---")
    print(f"[INFO] Registros originales:  {original_trips_count:,}")
    print(f"[INFO] Registros conservados: {clean_trips_count:,}")
    print(f"[INFO] Registros eliminados:  {removed_trips_count:,}")
    print("-----------------------------------\n")
    return


@app.cell
def _(clean_trips_dataframe):
    clean_trips_dataframe
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Export to Parquet
    """)
    return


@app.cell
def _(base_gtfs, clean_trips_dataframe):
    clean_trips_dataframe.write_parquet(base_gtfs / "trips_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Stop Times Cleaning
    """)
    return


@app.cell
def _(clean_stops_lazy, clean_trips_lazy, stop_times_dataframe):
    # Remove orphaned scheduling data to guarantee that the simulation engine only processes valid weekday events.
    clean_stop_times_lazy = (
        stop_times_dataframe.lazy()
        .join(clean_trips_lazy.select("trip_id"), on="trip_id", how="semi")
        .join(clean_stops_lazy.select("stop_id"), on="stop_id", how="semi")
        .drop(["timepoint"])
    )
    return (clean_stop_times_lazy,)


@app.cell
def _(clean_stop_times_lazy):
    clean_stop_times_dataframe = clean_stop_times_lazy.collect()
    return (clean_stop_times_dataframe,)


@app.cell
def _(clean_stop_times_dataframe, stop_times_dataframe):
    original_stop_times_count = stop_times_dataframe.height
    clean_stop_times_count = clean_stop_times_dataframe.height
    removed_stop_times_count = original_stop_times_count - clean_stop_times_count
    return (
        clean_stop_times_count,
        original_stop_times_count,
        removed_stop_times_count,
    )


@app.cell
def _(
    clean_stop_times_count,
    original_stop_times_count,
    removed_stop_times_count,
):
    print("\n[INFO] --- LIMPIEZA: STOP_TIMES ---")
    print(f"[INFO] Registros originales:  {original_stop_times_count:,}")
    print(f"[INFO] Registros conservados: {clean_stop_times_count:,}")
    print(f"[INFO] Registros eliminados:  {removed_stop_times_count:,}")
    print("---------------------------------------\n")
    return


@app.cell
def _(clean_stop_times_dataframe):
    clean_stop_times_dataframe
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Export to Parquet
    """)
    return


@app.cell
def _(base_gtfs, clean_stop_times_dataframe):
    clean_stop_times_dataframe.write_parquet(base_gtfs / "stop_times_clean.parquet")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Shapes Cleaning
    """)
    return


@app.cell
def _(clean_trips_lazy):
    valid_shapes_lazy = clean_trips_lazy.select("shape_id").drop_nulls().unique()
    return (valid_shapes_lazy,)


@app.cell
def _(shapes_dataframe, valid_shapes_lazy):
    # Identify the unique paths required by the active weekday trips.
    clean_shapes_lazy = (
        shapes_dataframe.lazy()
        .drop_nulls(subset=["shape_id"])
        .join(valid_shapes_lazy, on="shape_id", how="semi")
    )
    return (clean_shapes_lazy,)


@app.cell
def _(clean_shapes_lazy):
    clean_shapes_dataframe = clean_shapes_lazy.collect()
    return (clean_shapes_dataframe,)


@app.cell
def _(clean_shapes_dataframe, shapes_dataframe):
    original_shapes_count = shapes_dataframe.height
    clean_shapes_count = clean_shapes_dataframe.height
    removed_shapes_count = original_shapes_count - clean_shapes_count
    return clean_shapes_count, original_shapes_count, removed_shapes_count


@app.cell
def _(clean_shapes_count, original_shapes_count, removed_shapes_count):
    print("\n[INFO] --- LIMPIEZA: SHAPES ---")
    print(f"[INFO] Registros originales:  {original_shapes_count:,}")
    print(f"[INFO] Registros conservados: {clean_shapes_count:,}")
    print(f"[INFO] Registros eliminados:  {removed_shapes_count:,}")
    print("-----------------------------------\n")
    return


@app.cell
def _(clean_shapes_dataframe):
    clean_shapes_dataframe
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Export to Parquet
    """)
    return


@app.cell
def _(base_gtfs, clean_shapes_dataframe):
    clean_shapes_dataframe.write_parquet(base_gtfs / "shapes_clean.parquet")
    return


if __name__ == "__main__":
    app.run()
