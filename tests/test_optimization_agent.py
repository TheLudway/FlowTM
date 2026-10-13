# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from pathlib import Path

from flowtm.domain.models import SimulationResult
from flowtm.domain.state import ScheduleState
from flowtm.infrastructure.gtfs_exporter import export_gtfs_frequencies
from flowtm.optimization.utility import UtilityCalculator


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

    for _ in range(20):
        neighbor = state.generate_neighbor(step_min=0.5)
        # Verify bounds [2.0, 15.0]
        for _r, h in neighbor.headways.items():
            assert 2.0 <= h <= 15.0
        # Verify fleet feasibility
        assert neighbor.total_fleet_used() <= 106


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
