import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import polars as pl

    return (pl,)


@app.cell(hide_code=True)
def _(pl):
    agencias = pl.read_parquet("data/processed/gtfs/gtfs_20260727/agency.parquet")
    agencias
    return


@app.cell(hide_code=True)
def _(pl):
    calendar = pl.read_parquet("data/processed/gtfs/gtfs_20260727/calendar.parquet")
    calendar
    return


@app.cell(hide_code=True)
def _(pl):
    calendar_dates = pl.read_parquet("data/processed/gtfs/gtfs_20260727/calendar_dates.parquet")
    calendar_dates
    return


@app.cell(hide_code=True)
def _(pl):
    fare_attributes = pl.read_parquet("data/processed/gtfs/gtfs_20260727/fare_attributes.parquet")
    fare_attributes
    return


@app.cell(hide_code=True)
def _(pl):
    feed_info = pl.read_parquet("data/processed/gtfs/gtfs_20260727/feed_info.parquet")
    feed_info
    return


@app.cell(hide_code=True)
def _(pl):
    frequencies = pl.read_parquet("data/processed/gtfs/gtfs_20260727/frequencies.parquet")
    frequencies
    return


@app.cell(hide_code=True)
def _(pl):
    routes = pl.read_parquet("data/processed/gtfs/gtfs_20260727/routes.parquet")
    routes
    return


@app.cell(hide_code=True)
def _(pl):
    shapes = pl.read_parquet("data/processed/gtfs/gtfs_20260727/shapes.parquet")
    shapes
    return


@app.cell(hide_code=True)
def _(pl):
    stop_times = pl.read_parquet("data/processed/gtfs/gtfs_20260727/stop_times.parquet")
    stop_times
    return


@app.cell(hide_code=True)
def _(pl):
    stops = pl.read_parquet("data/processed/gtfs/gtfs_20260727/stops.parquet")
    stops
    return


@app.cell(hide_code=True)
def _(pl):
    trips = pl.read_parquet("data/processed/gtfs/gtfs_20260727/trips.parquet")
    trips
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
