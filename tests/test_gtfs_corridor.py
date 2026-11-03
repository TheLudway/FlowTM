# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import polars as pl
import pytest

from flowtm.infrastructure import gtfs_corridor as gc

# Three corridor stations (north -> south) and one station after the corridor.
STATIONS = [
    ("2000", "Portal Norte - Unicervantes", 4.755),
    ("2101", "Toberín- Foundever", 4.747),
    ("2102", "Calle 161", 4.742),
    ("9118", "Marly", 4.637),
    ("9200", "Calle 26", 4.616),
]


def make_feed() -> gc.GtfsFeed:
    station_rows = [
        {
            "stop_id": sid,
            "stop_name": name,
            "stop_lat": lat,
            "stop_lon": -74.05,
            "location_type": 1,
            "parent_station": None,
        }
        for sid, name, lat in STATIONS
    ]
    platform_rows = [
        {
            "stop_id": f"{sid}{suffix}",
            "stop_name": f"{name} {suffix}",
            "stop_lat": lat,
            "stop_lon": -74.05,
            "location_type": 0,
            "parent_station": sid,
        }
        for sid, name, lat in STATIONS
        for suffix in ("A", "B")
    ]
    routes = pl.DataFrame(
        {
            "route_id": ["1", "2", "3"],
            "agency_id": [1, 1, 2],
            "route_short_name": ["H13", "B13", "2-5"],
            "route_long_name": ["P. Tunal", "Portal Norte", "Alimentador"],
            "route_color": ["E53935", "E53935", "00FF00"],
        }
    )
    stop_times, trips = [], []
    # 6 southbound H13 trips every 10 min from 06:00, all stops, continuing to Calle 26.
    for k in range(6):
        trip = f"H13_{k}"
        trips.append({"trip_id": trip, "route_id": "1", "service_id": "1"})
        start = 6 * 3600 + k * 600
        for seq, (sid, offset) in enumerate(
            [
                ("2000A", 0),
                ("2101A", 180),
                ("2102B", 300),
                ("9118A", 900),
                ("9200A", 1200),
            ]
        ):
            stop_times.append(
                {
                    "trip_id": trip,
                    "stop_id": sid,
                    "stop_sequence": seq,
                    "arrival_time": start + offset,
                    "departure_time": start + offset,
                }
            )
    # 2 northbound B13 trips (return), 40 minutes end to end.
    for k in range(2):
        trip = f"B13_{k}"
        trips.append({"trip_id": trip, "route_id": "2", "service_id": "1"})
        start = 6 * 3600 + k * 900
        for seq, (sid, offset) in enumerate(
            [("9118B", 0), ("2101B", 1800), ("2000B", 2400)]
        ):
            stop_times.append(
                {
                    "trip_id": trip,
                    "stop_id": sid,
                    "stop_sequence": seq,
                    "arrival_time": start + offset,
                    "departure_time": start + offset,
                }
            )
    return gc.GtfsFeed(
        routes=routes,
        trips=pl.DataFrame(trips),
        stop_times=pl.DataFrame(stop_times),
        stops=pl.DataFrame(station_rows + platform_rows),
        calendar=pl.DataFrame(
            {
                "service_id": ["1"],
                **{
                    d: [1]
                    for d in ("monday", "tuesday", "wednesday", "thursday", "friday")
                },
            }
        ),
    )


@pytest.fixture(scope="module")
def corridor():
    feed = make_feed()
    events = gc.trunk_stop_events(feed)
    topology = gc.corridor_topology(feed, events, "02000", "09118")
    passages = gc.corridor_passages(events, topology)
    return feed, events, topology, passages


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("TEMPORAL FLORES", "FLORES"),
        ("Calle 100 - Marketmedios", "CALLE 100"),
        ("TEMPORAL AVENIDA 39", "AV 39"),
        ("Av. 39", "AV 39"),
        ("Toberín- Foundever", "TOBERIN FOUNDEVER"),
    ],
)
def test_normalize_station_name(raw: str, expected: str):
    assert gc.normalize_station_name(raw) == expected


def test_topology_keeps_served_trunk_stations_in_order(corridor):
    _, _, topology, _ = corridor
    # Feeder-only or out-of-range stations are excluded; order is north -> south.
    assert topology["codigo"].to_list() == ["02000", "02101", "02102", "09118"]
    assert topology["secuencia"].to_list() == [1, 2, 3, 4]


def test_peak_services_derive_headway_and_pattern(corridor):
    _, _, _, passages = corridor
    southbound = gc.peak_services(passages, "N->S", 6 * 3600, 9 * 3600)

    row = southbound.row(0, named=True)
    assert row["route_short_name"] == "H13"
    assert row["viajes_pico"] == 6
    assert row["headway_gtfs_min"] == 30.0  # 180 min window / 6 trips
    assert row["paradas"] == ["02000", "02101", "02102", "09118"]
    assert row["continua_al_salir"] is True


def test_cycle_time_uses_counterpart_return_trip(corridor):
    _, events, _, passages = corridor
    northbound = gc.peak_services(passages, "S->N", 6 * 3600, 9 * 3600)
    counterpart = gc.counterpart_route("H13", northbound["route_short_name"].to_list())

    assert counterpart == "B13"
    # 20 min outbound + 40 min return + 2 x 5 min layovers.
    assert gc.cycle_time_minutes(events, "H13", counterpart) == 70.0


def test_segment_running_times_subtract_modeled_dwell(corridor):
    _, _, topology, passages = corridor
    running = gc.segment_running_times(passages, topology)

    assert running[0] == 180.0 - gc.MODELED_MIN_DWELL_SEC
    assert running[-1] == 0.0


def test_platform_counts_and_stations_after_corridor(corridor):
    _, events, _, passages = corridor
    assert gc.platform_counts(events, passages, "N->S")["02102"] == 1
    assert gc.stations_after_corridor(events, passages, "N->S") == ["09200"]
