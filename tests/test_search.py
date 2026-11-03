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

from flowtm.domain.state import ScheduleState
from flowtm.optimization.evaluator import ScheduleEvaluator
from flowtm.optimization.search import ALGORITHMS, calibrate_temperature
from flowtm.simulation.scenario import CorridorScenario

LEG_TIMES = {"R1": 60.0, "R2": 50.0, "R3": 40.0}
BASE_HEADWAYS = {"R1": 4.0, "R2": 5.0, "R3": 5.0}
BASE_FLEET = 15 + 10 + 8


def make_state() -> ScheduleState:
    return ScheduleState(
        headways=dict(BASE_HEADWAYS), leg_times=LEG_TIMES, max_fleet=BASE_FLEET
    )


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
