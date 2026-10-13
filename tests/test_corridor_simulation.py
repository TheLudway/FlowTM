# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from pathlib import Path

from flowtm.domain.models import Passenger, Station
from flowtm.domain.state import ScheduleState
from flowtm.simulation.dwell_time import calculate_dwell_time_sec
from flowtm.simulation.engine import CorridorSimulator


def test_dwell_time_bounds():
    # Lower bound clamp: 10 + 0 = 10 -> clamped to 12.0s
    assert calculate_dwell_time_sec(boarding_count=0, alighting_count=0) == 12.0
    # Moderate load: 10 + max(10*1.2, 5*1.0) = 22.0s
    assert calculate_dwell_time_sec(boarding_count=10, alighting_count=5) == 22.0
    # Upper bound clamp: 10 + 100*1.2 = 130 -> clamped to 75.0s
    assert calculate_dwell_time_sec(boarding_count=100, alighting_count=10) == 75.0


def test_station_queue_and_boarding():
    station = Station(
        station_code="02000",
        name="PORTAL NORTE",
        sequence=1,
        lat=4.7544,
        lon=-74.0460,
        next_distance_m=1000.0,
        travel_time_sec=120.0,
    )

    p1 = Passenger(
        passenger_id=1,
        origin_station="02000",
        destination_station="02101",
        arrival_time_sec=10.0,
    )
    p2 = Passenger(
        passenger_id=2,
        origin_station="02000",
        destination_station="09117",
        arrival_time_sec=15.0,
    )

    station.register_arrival(p1)
    station.register_arrival(p2)
    assert len(station.waiting_queue) == 2
    assert station.total_arrivals == 2

    # Bus serving only 02101 with capacity 1
    boarded = station.board_passengers(
        bus_scheduled_stops=["02101"], available_capacity=1
    )
    assert len(boarded) == 1
    assert boarded[0].passenger_id == 1
    assert len(station.waiting_queue) == 1
    assert station.waiting_queue[0].passenger_id == 2


def test_schedule_state_neighbor_generation():
    headways = {"B13": 2.0, "B18": 2.0, "B23": 3.0, "B27": 4.0, "B74": 4.0, "B75": 2.0}
    state = ScheduleState(headways=headways)
    neighbor = state.generate_neighbor(step_min=0.5)

    assert len(neighbor.headways) == 6
    # Verify all headways respect operational bounds [2.0, 15.0]
    for r, h in neighbor.headways.items():
        assert 2.0 <= h <= 15.0, f"Route {r} headway {h} out of bounds"


def test_corridor_simulation_6_routes():
    scenario_dir = Path("data/scenarios/piloto")
    if not scenario_dir.exists():
        return

    simulator = CorridorSimulator(scenario_dir)
    headways = {"B13": 2.0, "B18": 2.0, "B23": 3.0, "B27": 4.0, "B74": 4.0, "B75": 2.0}
    results = simulator.simulate(headways, duration_hours=1.0)

    assert results.total_dispatched_buses > 0
    assert results.total_transported_passengers >= 0
    assert len(results.station_metrics) == 17
    assert set(results.route_load_profiles.keys()) == set(headways.keys())
