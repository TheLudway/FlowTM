# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.presentation.dashboard.incidents
=======================================
Post-mortem incident aggregation for the OCC dashboard, implemented with Polars
expressions so the dashboard and its tests share the same logic.
"""

import polars as pl

STATION_COLLAPSE_THRESHOLD_PAX: int = 150
BUS_OVERCROWDING_THRESHOLD_PAX: int = 152  # 95% of a 160-passenger articulated bus


def aggregate_station_incidents(
    queues_df: pl.DataFrame,
    threshold: int = STATION_COLLAPSE_THRESHOLD_PAX,
) -> pl.DataFrame:
    """
    Summarize platform collapse episodes per station.

    Args:
        queues_df: Queue telemetry with ``station_code``, ``queue_size`` and
            ``time_sec`` columns.
        threshold: Minimum queue size (passengers) considered a collapse.

    Returns:
        One row per station with ``peak_queue``, ``collapse_start`` and
        ``collapse_end`` (simulation seconds), sorted by ``station_code``.
    """
    return (
        queues_df.filter(pl.col("queue_size") >= threshold)
        .group_by("station_code")
        .agg(
            pl.col("queue_size").max().alias("peak_queue"),
            pl.col("time_sec").min().alias("collapse_start"),
            pl.col("time_sec").max().alias("collapse_end"),
        )
        .sort("station_code")
    )


def aggregate_bus_incidents(
    buses_df: pl.DataFrame,
    threshold: int = BUS_OVERCROWDING_THRESHOLD_PAX,
) -> pl.DataFrame:
    """
    Summarize critical overcrowding episodes per bus.

    Args:
        buses_df: Bus telemetry with ``bus_id``, ``route``, ``passengers`` and
            ``time_sec`` columns.
        threshold: Minimum onboard passengers considered critical overcrowding.

    Returns:
        One row per bus with ``peak_passengers``, ``overcrowding_start`` and
        ``overcrowding_end`` (simulation seconds), sorted by ``bus_id``.
    """
    return (
        buses_df.filter(pl.col("passengers") >= threshold)
        .group_by(["bus_id", "route"])
        .agg(
            pl.col("passengers").max().alias("peak_passengers"),
            pl.col("time_sec").min().alias("overcrowding_start"),
            pl.col("time_sec").max().alias("overcrowding_end"),
        )
        .sort("bus_id")
    )
