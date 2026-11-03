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
from flowtm.domain.state import ScheduleState
from flowtm.infrastructure.gtfs_exporter import export_gtfs_frequencies
from flowtm.optimization.evaluator import ScheduleEvaluator, holdout_comparison
from flowtm.optimization.search import ALGORITHMS, calibrate_temperature
from flowtm.optimization.simulated_annealing import SimulatedAnnealingOptimizer
from flowtm.optimization.utility import UtilityCalculator
from flowtm.simulation.scenario import CorridorScenario

LEG_TIMES = {"R1": 60.0, "R2": 50.0, "R3": 40.0}
BASE_HEADWAYS = {"R1": 4.0, "R2": 5.0, "R3": 5.0}
BASE_FLEET = 15 + 10 + 8


def make_state(headways: dict[str, float] | None = None, max_fleet: int = BASE_FLEET):
    return ScheduleState(
        headways=dict(headways or BASE_HEADWAYS),
        leg_times=LEG_TIMES,
        max_fleet=max_fleet,
    )


def test_schedule_state_fleet_formula():
    state = make_state()

    assert state.fleet_used_by_route() == {"R1": 15, "R2": 10, "R3": 8}
    assert state.total_fleet_used() == BASE_FLEET
    assert state.is_fleet_feasible() is True
    assert make_state(max_fleet=BASE_FLEET - 1).is_fleet_feasible() is False


def test_fleet_includes_fixed_return_leg():
    # Return leg runs at its own GTFS headway: its vehicles do not change with h.
    state = ScheduleState(
        headways={"R1": 4.0},
        leg_times={"R1": 60.0},
        max_fleet=40,
        fixed_fleet={"R1": 20},
    )
    assert state.fleet_used_by_route() == {"R1": 15 + 20}
    state.headways["R1"] = 6.0
    assert state.fleet_used_by_route() == {"R1": 10 + 20}


def test_scenario_base_schedule_matches_fleet_bound(synthetic_scenario_dir: Path):
    scenario = CorridorScenario.load(synthetic_scenario_dir)
    base = scenario.base_schedule()

    assert scenario.optimizable_routes == ["R1", "R2", "R3"]
    assert scenario.background_routes == ["BG1"]
    assert base.headways == BASE_HEADWAYS
    assert base.total_fleet_used() == scenario.max_fleet == BASE_FLEET


def test_neighbor_preserves_fleet_feasibility():
    state = make_state()
    rng = random.Random(0)

    for _ in range(200):
        neighbor = state.generate_neighbor(step_min=0.5, rng=rng)
        assert all(2.0 <= h <= 15.0 for h in neighbor.headways.values())
        assert neighbor.total_fleet_used() <= state.max_fleet


def test_neighbor_returns_unchanged_state_when_no_feasible_candidate():
    # Two symmetric routes at exactly the fleet limit: any swap adds one bus
    # (ceil(60/9.5) + ceil(60/10.5) = 7 + 6 = 13 > 12).
    state = ScheduleState(
        headways={"R1": 10.0, "R2": 10.0},
        leg_times={"R1": 60.0, "R2": 60.0},
        max_fleet=12,
    )
    neighbor = state.generate_neighbor(step_min=0.5, rng=random.Random(1), move="swap")

    assert neighbor.headways == state.headways
    assert neighbor is not state


def test_single_move_can_free_fleet():
    state = make_state()
    rng = random.Random(4)
    fleets = {
        state.generate_neighbor(rng=rng, move="single").total_fleet_used()
        for _ in range(50)
    }
    # Single-route moves can release vehicles (swaps keep fleet roughly constant).
    assert min(fleets) < state.total_fleet_used()


def test_random_feasible_respects_bounds_and_fleet():
    state = make_state()
    rng = random.Random(0)
    for _ in range(50):
        sample = state.random_feasible(rng)
        assert sample.is_fleet_feasible()
        assert all(2.0 <= h <= 15.0 for h in sample.headways.values())


def test_neighbor_generation_is_reproducible_with_seed():
    state = make_state()
    first = state.generate_neighbor(rng=random.Random(123))
    second = state.generate_neighbor(rng=random.Random(123))
    assert first.headways == second.headways


def test_evaluator_uses_common_seeds_and_cache(synthetic_scenario_dir: Path):
    base = CorridorScenario.load(synthetic_scenario_dir).base_schedule()
    with ScheduleEvaluator(
        synthetic_scenario_dir, seeds=[1, 2], workers=1
    ) as evaluator:
        first = evaluator.evaluate(base)
        again = evaluator.evaluate(base.copy())
        assert again is first  # cached: same schedule is not simulated twice
        assert evaluator.n_evaluations == 1
        assert evaluator.n_simulations == 2
        assert len(first.per_seed_utility) == 2
    with ScheduleEvaluator(synthetic_scenario_dir, seeds=[1, 2], workers=1) as other:
        # Common random numbers: same seeds give exactly the same expectation.
        assert other.evaluate(base).utility == first.utility


@pytest.mark.parametrize("algorithm", sorted(ALGORITHMS))
def test_search_algorithms_respect_budget_and_fleet(
    synthetic_scenario_dir: Path, algorithm: str
):
    base = CorridorScenario.load(synthetic_scenario_dir).base_schedule()
    with ScheduleEvaluator(
        synthetic_scenario_dir, seeds=[1, 2], workers=1
    ) as evaluator:
        result = ALGORITHMS[algorithm](evaluator, base, budget=6, seed=3)

    assert result.evaluations <= 6
    assert result.best_state.is_fleet_feasible()
    assert result.best.utility >= result.initial.utility
    assert all(entry["fleet_used"] <= base.max_fleet for entry in result.history)
    best_curve = [entry["best_utility"] for entry in result.history]
    assert best_curve == sorted(best_curve)  # best-so-far never decreases


def test_temperature_calibration_targets_initial_acceptance(
    synthetic_scenario_dir: Path,
):
    base = CorridorScenario.load(synthetic_scenario_dir).base_schedule()
    with ScheduleEvaluator(
        synthetic_scenario_dir, seeds=[1, 2], workers=1
    ) as evaluator:
        initial = evaluator.evaluate(base)
        temperature = calibrate_temperature(
            evaluator, base, initial, random.Random(0), step_min=0.5
        )
    # T0 lives on the scale of utility differences (not an arbitrary 75).
    assert 0 < temperature < 5


def test_optimizer_rejects_infeasible_initial_state(synthetic_scenario_dir: Path):
    optimizer = SimulatedAnnealingOptimizer(
        synthetic_scenario_dir, budget=2, seeds=[1], verbose=False, workers=1
    )
    with pytest.raises(ValueError, match="supera la flota"):
        optimizer.optimize(make_state(max_fleet=10))


def test_optimizer_returns_feasible_best_state(synthetic_scenario_dir: Path):
    optimizer = SimulatedAnnealingOptimizer(
        synthetic_scenario_dir, budget=8, seeds=[1, 2], verbose=False, workers=1
    )
    initial_state = CorridorScenario.load(synthetic_scenario_dir).base_schedule()

    best_state, best_result = optimizer.optimize(initial_state)

    assert best_state.is_fleet_feasible()
    assert best_result.total_dispatched_buses > 0
    assert optimizer.result is not None and optimizer.result.evaluations <= 8
    assert optimizer.history[-1]["best_utility"] >= optimizer.history[0]["utility"]


def test_optimizer_is_reproducible_with_seed(synthetic_scenario_dir: Path):
    initial_state = CorridorScenario.load(synthetic_scenario_dir).base_schedule()
    runs = []
    for _ in range(2):
        optimizer = SimulatedAnnealingOptimizer(
            synthetic_scenario_dir,
            budget=6,
            seeds=[1, 2],
            seed=2026,
            verbose=False,
            workers=1,
        )
        best_state, _ = optimizer.optimize(initial_state)
        runs.append((best_state.headways, [h["headways"] for h in optimizer.history]))
    assert runs[0] == runs[1]


def test_holdout_comparison_reports_paired_statistics(synthetic_scenario_dir: Path):
    base = CorridorScenario.load(synthetic_scenario_dir).base_schedule()
    candidate = base.with_headways({"R1": 4.5, "R2": 5.0, "R3": 5.0})
    report = holdout_comparison(
        synthetic_scenario_dir, base, candidate, [7, 8, 9], workers=1
    )

    wait = report["espera_min"]
    assert wait["semillas"] == 3
    assert wait["ic95"][0] <= wait["diferencia"] <= wait["ic95"][1]
    assert report["flota"]["candidato"] <= report["flota"]["base"]


def test_multicriteria_utility_function():
    calc = UtilityCalculator(max_fleet=100)
    good = SimulationResult(
        avg_waiting_time_min=2.5,
        avg_occupancy_rate=0.45,
        overcrowded_bus_pct=5.0,
        total_transported_passengers=52000,
        stranded_passengers_in_queue=500,
        total_dispatched_buses=420,
    )
    bad = SimulationResult(
        avg_waiting_time_min=5.0,
        avg_occupancy_rate=0.75,
        overcrowded_bus_pct=35.0,
        total_transported_passengers=45000,
        stranded_passengers_in_queue=2500,
        total_dispatched_buses=420,
    )

    # U(S) is a negative cost: better service gives a higher utility.
    assert calc.evaluate(good, fleet_used=100) > calc.evaluate(bad, fleet_used=100)
    # Exceeding the fleet bound is severely penalized.
    assert (
        calc.evaluate(good, fleet_used=104) < calc.evaluate(good, fleet_used=100) - 50.0
    )


def test_gtfs_exporter(tmp_path: Path):
    out_file = tmp_path / "frequencies.txt"
    export_gtfs_frequencies({"H13": 2.0, "H75": 2.5, "K23": 3.0}, out_file)

    lines = out_file.read_text(encoding="utf-8").strip().split("\n")
    assert lines[0] == "route_id,trip_id,start_time,end_time,headway_secs,exact_times"
    assert len(lines) == 4
    assert "H13,TRIP_H13_PEAK,06:00:00,09:00:00,120,0" in lines
