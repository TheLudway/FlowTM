# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import json
from pathlib import Path

from conftest import (
    SYNTHETIC_BASE_HEADWAYS,
    SYNTHETIC_STATION_CODES,
    build_synthetic_scenario,
)

from flowtm.domain.models import Passenger, Station
from flowtm.simulation.collector import (
    SUMMARY_METRICS_FILENAME,
    export_summary_metrics,
)
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


def test_corridor_simulation_runs_all_services(synthetic_scenario_dir: Path):
    simulator = CorridorSimulator(synthetic_scenario_dir)
    results = simulator.simulate(SYNTHETIC_BASE_HEADWAYS, duration_hours=1.0)

    assert results.total_dispatched_buses > 0
    assert results.total_transported_passengers > 0
    assert len(results.station_metrics) == len(SYNTHETIC_STATION_CODES)
    assert set(results.route_load_profiles) == set(SYNTHETIC_BASE_HEADWAYS)
    # Background service runs at its GTFS headway even though it is not optimized.
    assert any(bus.route == "BG1" for bus in simulator.simulated_buses)


def test_express_service_only_stops_at_its_pattern(synthetic_scenario_dir: Path):
    simulator = CorridorSimulator(synthetic_scenario_dir)
    simulator.simulate(SYNTHETIC_BASE_HEADWAYS, duration_hours=1.0)

    express_profiles = {
        record["secuencia"]
        for bus in simulator.simulated_buses
        if bus.route == "R2"
        for record in bus.passenger_profile_by_stop
    }
    assert express_profiles <= {1, 4, 8}


def test_passengers_only_board_buses_serving_their_destination(
    synthetic_scenario_dir: Path,
):
    simulator = CorridorSimulator(synthetic_scenario_dir)
    simulator.simulate(SYNTHETIC_BASE_HEADWAYS, duration_hours=1.0)
    served = {
        route: set(spec.served_destinations)
        for route, spec in simulator.scenario.services.items()
    }
    for bus in simulator.simulated_buses:
        for passenger in bus.onboard_passengers:
            assert passenger.destination_station in served[bus.route]


def test_physical_fleet_causes_dispatch_delays_when_cycle_is_too_short(
    tmp_path: Path,
):
    # A cycle shorter than the corridor run means vehicles cannot be back in time.
    scenario_dir = build_synthetic_scenario(tmp_path / "corto", {"R1": 5.0})
    simulator = CorridorSimulator(scenario_dir)
    result = simulator.simulate({"R1": 4.0, "R2": 5.0, "R3": 5.0}, duration_hours=1.0)

    assert result.avg_dispatch_delay_min > 0
    r1_vehicles = {b.vehicle_id for b in simulator.simulated_buses if b.route == "R1"}
    assert len(r1_vehicles) == 2  # ceil(5 / 4) physical buses reused across trips


def test_corridor_simulation_is_reproducible_with_seed(synthetic_scenario_dir: Path):
    first = CorridorSimulator(synthetic_scenario_dir).simulate(
        SYNTHETIC_BASE_HEADWAYS, duration_hours=1.0, seed=7
    )
    second = CorridorSimulator(synthetic_scenario_dir).simulate(
        SYNTHETIC_BASE_HEADWAYS, duration_hours=1.0, seed=7
    )

    assert first.avg_waiting_time_min == second.avg_waiting_time_min
    assert first.total_transported_passengers == second.total_transported_passengers
    assert first.stranded_passengers_in_queue == second.stranded_passengers_in_queue


def test_export_summary_metrics_matches_simulation(
    synthetic_scenario_dir: Path, tmp_path: Path
):
    result = CorridorSimulator(synthetic_scenario_dir).simulate(
        SYNTHETIC_BASE_HEADWAYS, duration_hours=1.0
    )

    metrics_file = export_summary_metrics(result, tmp_path / "telemetria_opt")
    metrics = json.loads(metrics_file.read_text(encoding="utf-8"))

    assert metrics_file.name == SUMMARY_METRICS_FILENAME
    assert metrics["avg_waiting_time_min"] == round(result.avg_waiting_time_min, 2)
    assert metrics["total_dispatched_buses"] == result.total_dispatched_buses
    assert metrics["avg_dispatch_delay_min"] == round(result.avg_dispatch_delay_min, 2)
