# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import polars as pl

from flowtm.presentation.dashboard.incidents import (
    aggregate_bus_incidents,
    aggregate_station_incidents,
)


def test_aggregate_station_incidents() -> None:
    # Mock platform queue telemetry (Q >= 150)
    data = [
        {"station_code": "EST_01", "queue_size": 120, "time_sec": 0},
        {"station_code": "EST_01", "queue_size": 155, "time_sec": 30},
        {"station_code": "EST_01", "queue_size": 180, "time_sec": 60},
        {"station_code": "EST_01", "queue_size": 140, "time_sec": 90},
        {"station_code": "EST_02", "queue_size": 150, "time_sec": 30},
        {"station_code": "EST_02", "queue_size": 150, "time_sec": 120},
        {"station_code": "EST_03", "queue_size": 40, "time_sec": 30},
    ]
    queues_df = pl.DataFrame(data)

    station_history = aggregate_station_incidents(queues_df)

    # Stations that never reach the threshold are excluded.
    assert station_history["station_code"].to_list() == ["EST_01", "EST_02"]

    est_01_result = station_history.filter(pl.col("station_code") == "EST_01").row(
        0, named=True
    )
    assert est_01_result["peak_queue"] == 180
    assert est_01_result["collapse_start"] == 30
    assert est_01_result["collapse_end"] == 60

    est_02_result = station_history.filter(pl.col("station_code") == "EST_02").row(
        0, named=True
    )
    assert est_02_result["peak_queue"] == 150
    assert est_02_result["collapse_start"] == 30
    assert est_02_result["collapse_end"] == 120


def test_aggregate_bus_incidents() -> None:
    # Mock bus telemetry (passengers >= 152)
    data = [
        {"bus_id": "B_01", "route": "B13", "passengers": 151, "time_sec": 0},
        {"bus_id": "B_01", "route": "B13", "passengers": 155, "time_sec": 30},
        {"bus_id": "B_01", "route": "B13", "passengers": 160, "time_sec": 60},
        {"bus_id": "B_02", "route": "B27", "passengers": 90, "time_sec": 30},
    ]
    buses_df = pl.DataFrame(data)

    bus_history = aggregate_bus_incidents(buses_df)

    assert bus_history.height == 1

    b_01_result = bus_history.filter(pl.col("bus_id") == "B_01").row(0, named=True)
    assert b_01_result["route"] == "B13"
    assert b_01_result["peak_passengers"] == 160
    assert b_01_result["overcrowding_start"] == 30
    assert b_01_result["overcrowding_end"] == 60


def test_aggregate_incidents_with_no_events_returns_empty() -> None:
    queues_df = pl.DataFrame(
        {"station_code": ["EST_01"], "queue_size": [10], "time_sec": [0.0]}
    )
    buses_df = pl.DataFrame(
        {"bus_id": ["B_01"], "route": ["B13"], "passengers": [20], "time_sec": [0.0]}
    )

    assert aggregate_station_incidents(queues_df).is_empty()
    assert aggregate_bus_incidents(buses_df).is_empty()
