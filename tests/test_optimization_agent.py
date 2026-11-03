# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import random
from pathlib import Path

import pytest

from flowtm.domain.models import SimulationResult
from flowtm.domain.state import MAX_FLEET_CAPACITY, ScheduleState
from flowtm.infrastructure.gtfs_exporter import export_gtfs_frequencies
from flowtm.optimization.simulated_annealing import SimulatedAnnealingOptimizer
from flowtm.optimization.utility import UtilityCalculator

BASE_HEADWAYS: dict[str, float] = {
    "B13": 2.0,
    "B18": 2.0,
    "B23": 3.0,
    "B27": 4.0,
    "B74": 4.0,
    "B75": 2.0,
}


def test_schedule_state_fleet_constraint():
    base_headways = {
        "B13": 2.0,
        "B18": 2.0,
        "B23": 3.0,
        "B27": 4.0,
        "B74": 4.0,
        "B75": 2.0,
    }
    state = ScheduleState(headways=base_headways)

    fleet_usage = state.fleet_used_by_route()
    assert fleet_usage["B13"] == 25
    assert fleet_usage["B18"] == 20
    assert fleet_usage["B23"] == 15
    assert fleet_usage["B27"] == 12
    assert fleet_usage["B74"] == 12
    assert fleet_usage["B75"] == 22

    total_fleet = state.total_fleet_used()
    assert total_fleet == 106, f"Expected 106 buses, got {total_fleet}"
    assert state.is_fleet_feasible() is True


def test_neighbor_preserves_fleet_feasibility():
    base_headways = {
        "B13": 2.0,
        "B18": 2.0,
        "B23": 3.0,
        "B27": 4.0,
        "B74": 4.0,
        "B75": 2.0,
    }
    state = ScheduleState(headways=base_headways)
    rng = random.Random(0)

    for _ in range(200):
        neighbor = state.generate_neighbor(step_min=0.5, rng=rng)
        # Verify bounds [2.0, 15.0]
        for _r, h in neighbor.headways.items():
            assert 2.0 <= h <= 15.0
        # Verify fleet feasibility
        assert neighbor.total_fleet_used() <= MAX_FLEET_CAPACITY


def test_neighbor_returns_unchanged_state_when_no_feasible_candidate():
    # Two symmetric routes at exactly the fleet limit: any boost/trim pair adds one
    # bus (ceil(60/9.5) + ceil(60/10.5) = 7 + 6 = 13 > 12), so every candidate is
    # infeasible and the current state must be returned unchanged.
    state = ScheduleState(
        headways={"R1": 10.0, "R2": 10.0},
        cycle_times={"R1": 60.0, "R2": 60.0},
        max_fleet=12,
    )
    assert state.is_fleet_feasible()

    neighbor = state.generate_neighbor(step_min=0.5, rng=random.Random(1))

    assert neighbor.headways == state.headways
    assert neighbor is not state
    assert neighbor.is_fleet_feasible()


def test_neighbor_generation_is_reproducible_with_seed():
    state = ScheduleState(headways=BASE_HEADWAYS)
    first = state.generate_neighbor(rng=random.Random(123))
    second = state.generate_neighbor(rng=random.Random(123))
    assert first.headways == second.headways


def test_optimizer_rejects_infeasible_initial_state(synthetic_scenario_dir: Path):
    optimizer = SimulatedAnnealingOptimizer(
        synthetic_scenario_dir, iterations=1, verbose=False
    )
    infeasible_state = ScheduleState(headways=BASE_HEADWAYS, max_fleet=50)

    with pytest.raises(ValueError, match="supera la flota"):
        optimizer.optimize(infeasible_state)


def test_optimizer_returns_feasible_best_state(synthetic_scenario_dir: Path):
    optimizer = SimulatedAnnealingOptimizer(
        synthetic_scenario_dir, iterations=3, seed=42, verbose=False
    )
    initial_state = ScheduleState(headways=BASE_HEADWAYS)

    best_state, best_result = optimizer.optimize(initial_state)

    assert best_state.is_fleet_feasible()
    assert best_result.total_dispatched_buses > 0
    assert len(optimizer.history) == 4
    assert all(entry["fleet_used"] <= MAX_FLEET_CAPACITY for entry in optimizer.history)
    assert optimizer.history[-1]["best_utility"] >= optimizer.history[0]["utility"]


def test_optimizer_is_reproducible_with_seed(synthetic_scenario_dir: Path):
    initial_state = ScheduleState(headways=BASE_HEADWAYS)

    runs = []
    for _ in range(2):
        optimizer = SimulatedAnnealingOptimizer(
            synthetic_scenario_dir, iterations=3, seed=2026, verbose=False
        )
        best_state, _ = optimizer.optimize(initial_state)
        runs.append((best_state.headways, optimizer.history))

    assert runs[0][0] == runs[1][0]
    assert [entry["headways"] for entry in runs[0][1]] == [
        entry["headways"] for entry in runs[1][1]
    ]
    assert [entry["accepted"] for entry in runs[0][1]] == [
        entry["accepted"] for entry in runs[1][1]
    ]


def test_multicriteria_utility_function():
    calc = UtilityCalculator(
        w_wait=0.40,
        w_overcrowding=0.30,
        w_stranded=0.15,
        w_fleet=0.15,
        max_fleet=106,
    )

    res_good = SimulationResult(
        avg_waiting_time_min=2.5,
        avg_occupancy_rate=0.45,
        overcrowded_bus_pct=5.0,
        total_transported_passengers=52000,
        stranded_passengers_in_queue=500,
        total_dispatched_buses=420,
    )

    res_bad = SimulationResult(
        avg_waiting_time_min=5.0,
        avg_occupancy_rate=0.75,
        overcrowded_bus_pct=35.0,
        total_transported_passengers=45000,
        stranded_passengers_in_queue=2500,
        total_dispatched_buses=420,
    )

    u_good = calc.evaluate(res_good, fleet_used=106)
    u_bad = calc.evaluate(res_bad, fleet_used=106)

    # U(S) is negative cost; better performance gives higher (less negative) utility
    assert u_good > u_bad

    # Test hard penalty on fleet violation
    u_violation = calc.evaluate(res_good, fleet_used=110)
    assert u_violation < u_good - 50.0  # severely penalized


def test_gtfs_exporter(tmp_path: Path):
    headways = {"B13": 2.0, "B18": 2.5, "B23": 3.0}
    out_file = tmp_path / "frequencies.txt"
    export_gtfs_frequencies(headways, out_file)

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    assert lines[0] == "route_id,trip_id,start_time,end_time,headway_secs,exact_times"
    assert len(lines) == 4
    assert "B13,TRIP_B13_PEAK,06:00:00,09:00:00,120,0" in lines
