# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.infrastructure.gtfs_corridor
===================================
Derives the corridor supply side directly from the official TransMilenio GTFS:

* Corridor topology (operating trunk stations between two boundary stations).
* Southbound trunk services crossing the corridor during the AM peak, with their
  real stop patterns, mean headways and corridor running times.
* Segment running times between consecutive corridor stations.
* Route cycle times (outbound trip + paired return trip + terminal layovers).

Every value is computed from ``stop_times``/``trips``/``routes``/``stops``; nothing
about routes or schedules is hardcoded.
"""

import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import polars as pl

TRUNK_AGENCY_ID = 1
TRUNK_ROUTE_PATTERN = r"^[A-Z][0-9]+$"
TERMINAL_LAYOVER_MIN = 5.0
# Minimum dwell already modeled by the simulator; GTFS arrival == departure, so
# scheduled segment times implicitly include part of the dwell at each stop.
MODELED_MIN_DWELL_SEC = 12.0
FREE_FLOW_SPEED_MPS = 6.11  # 22 km/h, fallback when a segment has no GTFS sample
EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class GtfsFeed:
    """Subset of GTFS tables needed to derive the corridor supply."""

    routes: pl.DataFrame
    trips: pl.DataFrame
    stop_times: pl.DataFrame
    stops: pl.DataFrame
    calendar: pl.DataFrame


def load_gtfs(gtfs_dir: Path) -> GtfsFeed:
    """Load the processed GTFS Parquet tables from ``gtfs_dir``."""
    return GtfsFeed(
        routes=pl.read_parquet(gtfs_dir / "routes.parquet").with_columns(
            pl.col("route_id").cast(pl.Utf8)
        ),
        trips=pl.read_parquet(gtfs_dir / "trips.parquet").with_columns(
            pl.col("route_id").cast(pl.Utf8), pl.col("service_id").cast(pl.Utf8)
        ),
        stop_times=pl.read_parquet(gtfs_dir / "stop_times.parquet"),
        stops=pl.read_parquet(gtfs_dir / "stops.parquet"),
        calendar=pl.read_parquet(gtfs_dir / "calendar.parquet").with_columns(
            pl.col("service_id").cast(pl.Utf8)
        ),
    )


def normalize_station_name(name: str) -> str:
    """Canonical station name used to match GTFS stations with fare-system stations."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = text.upper().split(" - ")[0]
    text = re.sub(r"\bTEMPORAL\b", " ", text)
    text = re.sub(r"\bAVENIDA\b|\bAV\.", "AV", text)
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def weekday_service_ids(calendar: pl.DataFrame) -> list[str]:
    """Service ids active on every weekday (Monday to Friday)."""
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    return calendar.filter(pl.all_horizontal(pl.col(d) == 1 for d in weekdays))[
        "service_id"
    ].to_list()


def trunk_stop_events(feed: GtfsFeed) -> pl.DataFrame:
    """
    Weekday stop events of trunk services, resolved to 5-digit station codes.

    Platform stops carry the station id in ``parent_station`` without the leading
    zero (``2102`` -> ``02102``).
    """
    platform_station = feed.stops.filter(pl.col("parent_station").is_not_null()).select(
        "stop_id", pl.col("parent_station").str.zfill(5).alias("station_code")
    )
    trunk_routes = feed.routes.filter(
        (pl.col("agency_id") == TRUNK_AGENCY_ID)
        & pl.col("route_short_name").str.contains(TRUNK_ROUTE_PATTERN)
    ).select("route_id", "route_short_name", "route_long_name", "route_color")
    weekday_trips = feed.trips.filter(
        pl.col("service_id").is_in(weekday_service_ids(feed.calendar))
    ).select("trip_id", "route_id")
    return (
        feed.stop_times.select(
            "trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"
        )
        .join(platform_station, on="stop_id")
        .join(weekday_trips, on="trip_id")
        .join(trunk_routes, on="route_id")
        .sort(["trip_id", "stop_sequence"])
    )


def corridor_topology(
    feed: GtfsFeed,
    events: pl.DataFrame,
    north_code: str,
    south_code: str,
) -> pl.DataFrame:
    """
    Operating trunk stations between two boundary stations, ordered north to south.

    Only stations of the boundary lines (same 2-digit line prefix) that are actually
    served by trunk trips are kept, so closed stations are excluded automatically.
    """
    stations = feed.stops.filter(pl.col("location_type") == 1).select(
        pl.col("stop_id").str.zfill(5).alias("codigo"),
        pl.col("stop_name").alias("nombre_gtfs"),
        pl.col("stop_lat").alias("lat"),
        pl.col("stop_lon").alias("lon"),
    )
    north = stations.filter(pl.col("codigo") == north_code).row(0, named=True)
    south = stations.filter(pl.col("codigo") == south_code).row(0, named=True)
    served_codes = events["station_code"].unique().to_list()
    corridor = (
        stations.filter(
            pl.col("codigo").str.slice(0, 2).is_in([north_code[:2], south_code[:2]])
            & pl.col("codigo").is_in(served_codes)
            & pl.col("lat").is_between(south["lat"], north["lat"])
        )
        .sort("lat", descending=True)
        .with_row_index("secuencia", offset=1)
        .with_columns(
            pl.col("secuencia").cast(pl.Int64),
            pl.col("nombre_gtfs")
            .map_elements(normalize_station_name, return_dtype=pl.Utf8)
            .alias("nombre"),
        )
    )
    lats, lons = corridor["lat"].to_list(), corridor["lon"].to_list()
    distances = [
        haversine_m(lats[i], lons[i], lats[i + 1], lons[i + 1])
        for i in range(len(lats) - 1)
    ] + [0.0]
    return corridor.with_columns(pl.Series("distancia_siguiente_m", distances).round(1))


def corridor_passages(events: pl.DataFrame, topology: pl.DataFrame) -> pl.DataFrame:
    """
    One row per trip crossing the corridor (>= 2 corridor stops), with its ordered
    corridor stops, entry/exit times and direction.
    """
    sequence = topology.select(
        pl.col("codigo").alias("station_code"), pl.col("secuencia").alias("corr_seq")
    )
    trip_last_stop = events.group_by("trip_id").agg(
        pl.col("stop_sequence").max().alias("trip_last_stop_sequence")
    )
    in_corridor = events.join(sequence, on="station_code").sort(
        ["trip_id", "stop_sequence"]
    )
    return (
        in_corridor.group_by("trip_id", maintain_order=True)
        .agg(
            pl.col("route_short_name").first(),
            pl.col("route_long_name").first(),
            pl.col("route_color").first(),
            pl.col("station_code").alias("stops"),
            pl.col("corr_seq").alias("seqs"),
            pl.col("arrival_time").alias("arrivals"),
            pl.col("departure_time").alias("departures"),
            pl.col("departure_time").first().alias("entry_sec"),
            pl.col("arrival_time").last().alias("exit_sec"),
            pl.col("stop_sequence").last().alias("exit_stop_sequence"),
        )
        .filter(pl.col("stops").list.len() >= 2)
        .join(trip_last_stop, on="trip_id")
        .with_columns(
            pl.when(pl.col("seqs").list.last() > pl.col("seqs").list.first())
            .then(pl.lit("N->S"))
            .otherwise(pl.lit("S->N"))
            .alias("direction"),
            (pl.col("exit_stop_sequence") < pl.col("trip_last_stop_sequence")).alias(
                "continues_after"
            ),
        )
    )


def peak_services(
    passages: pl.DataFrame,
    direction: str,
    peak_start_sec: int,
    peak_end_sec: int,
) -> pl.DataFrame:
    """
    Services crossing the corridor in ``direction`` during the peak window.

    The stop pattern is the most frequent corridor pattern of the route, and the
    headway is the mean interval ``window / number of trips``.
    """
    window_min = (peak_end_sec - peak_start_sec) / 60.0
    peak = passages.filter(
        (pl.col("direction") == direction)
        & (pl.col("entry_sec") >= peak_start_sec)
        & (pl.col("entry_sec") < peak_end_sec)
    ).with_columns(pl.col("stops").list.join(",").alias("pattern"))
    modal_pattern = (
        peak.group_by(["route_short_name", "pattern"])
        .agg(pl.len().alias("pattern_trips"))
        .sort(["route_short_name", "pattern_trips"], descending=[False, True])
        .group_by("route_short_name", maintain_order=True)
        .first()
    )
    return (
        peak.group_by("route_short_name")
        .agg(
            pl.col("route_long_name").first(),
            pl.col("route_color").first(),
            pl.len().alias("viajes_pico"),
            ((pl.col("exit_sec") - pl.col("entry_sec")).median() / 60.0).alias(
                "recorrido_corredor_min"
            ),
            (pl.col("continues_after").mean() >= 0.5).alias("continua_al_salir"),
        )
        .join(
            modal_pattern.select("route_short_name", "pattern"), on="route_short_name"
        )
        .with_columns(
            (window_min / pl.col("viajes_pico")).round(2).alias("headway_gtfs_min"),
            pl.col("pattern").str.split(",").alias("paradas"),
        )
        .drop("pattern")
        .sort("viajes_pico", descending=True)
    )


def segment_running_times(
    passages: pl.DataFrame, topology: pl.DataFrame, direction: str = "N->S"
) -> list[float]:
    """
    Running time (seconds) from each corridor station to the next one.

    Uses the median scheduled time of trips stopping at both consecutive stations,
    minus the dwell the simulator models explicitly. Segments without GTFS samples
    fall back to free-flow time at 22 km/h.
    """
    codes = topology["codigo"].to_list()
    next_code = {codes[i]: codes[i + 1] for i in range(len(codes) - 1)}
    samples: dict[str, list[float]] = {code: [] for code in codes[:-1]}
    for stops, arrivals, departures in (
        passages.filter(pl.col("direction") == direction)
        .select("stops", "arrivals", "departures")
        .iter_rows()
    ):
        for k in range(len(stops) - 1):
            if next_code.get(stops[k]) == stops[k + 1]:
                samples[stops[k]].append(float(arrivals[k + 1] - departures[k]))

    distances = topology["distancia_siguiente_m"].to_list()
    running_times: list[float] = []
    for index, code in enumerate(codes[:-1]):
        free_flow = distances[index] / FREE_FLOW_SPEED_MPS
        if samples[code]:
            ordered = sorted(samples[code])
            median = ordered[len(ordered) // 2]
            running_times.append(
                round(max(free_flow, median - MODELED_MIN_DWELL_SEC), 1)
            )
        else:
            running_times.append(round(free_flow + 15.0, 1))
    return [*running_times, 0.0]


def route_trip_minutes(events: pl.DataFrame, route_short_name: str) -> float | None:
    """Median end-to-end duration (minutes) of a route's weekday trips."""
    trips = (
        events.filter(pl.col("route_short_name") == route_short_name)
        .group_by("trip_id")
        .agg(
            (
                (pl.col("arrival_time").max() - pl.col("departure_time").min()) / 60.0
            ).alias("minutes")
        )
    )
    if trips.is_empty():
        return None
    return float(trips["minutes"].median())


def counterpart_route(route_short_name: str, candidates: list[str]) -> str | None:
    """
    Return trip of a service: same route number, different destination letter
    (e.g. ``H13`` <-> ``B13``), chosen among the opposite-direction services.
    """
    number = route_short_name[1:]
    matches = [c for c in candidates if c[1:] == number and c != route_short_name]
    return matches[0] if matches else None


def cycle_time_minutes(
    events: pl.DataFrame, route_short_name: str, counterpart: str | None
) -> float:
    """Outbound trip + return trip + one layover per terminal."""
    outbound = route_trip_minutes(events, route_short_name) or 0.0
    inbound = route_trip_minutes(events, counterpart) if counterpart else None
    if inbound is None:
        inbound = outbound
    return round(outbound + inbound + 2 * TERMINAL_LAYOVER_MIN, 1)


def platform_counts(
    events: pl.DataFrame, passages: pl.DataFrame, direction: str
) -> dict[str, int]:
    """Distinct GTFS platforms used per corridor station by trips in ``direction``."""
    trip_ids = passages.filter(pl.col("direction") == direction)["trip_id"].to_list()
    corridor_codes = passages["stops"].explode(empty_as_null=True).unique().to_list()
    counts = (
        events.filter(
            pl.col("trip_id").is_in(trip_ids)
            & pl.col("station_code").is_in(corridor_codes)
        )
        .group_by("station_code")
        .agg(pl.col("stop_id").n_unique().alias("platforms"))
    )
    return dict(counts.iter_rows())


def stations_after_corridor(
    events: pl.DataFrame, passages: pl.DataFrame, direction: str
) -> list[str]:
    """Station codes visited by corridor trips after they leave the corridor."""
    exits = passages.filter(pl.col("direction") == direction).select(
        "trip_id", "exit_stop_sequence"
    )
    after = events.join(exits, on="trip_id").filter(
        pl.col("stop_sequence") > pl.col("exit_stop_sequence")
    )
    return after["station_code"].unique().sort().to_list()
