# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from dataclasses import replace
from pathlib import Path

from flowtm.optimization.evaluator import ScheduleEvaluator, holdout_comparison
from flowtm.simulation.scenario import CorridorScenario


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


def test_holdout_comparison_reports_paired_statistics(synthetic_scenario_dir: Path):
    base = CorridorScenario.load(synthetic_scenario_dir).base_schedule()
    candidate = replace(base, headways={"R1": 4.5, "R2": 5.0, "R3": 5.0})
    report = holdout_comparison(
        synthetic_scenario_dir, base, candidate, [7, 8, 9], workers=1
    )

    wait = report["espera_min"]
    assert wait["semillas"] == 3
    assert wait["ic95"][0] <= wait["diferencia"] <= wait["ic95"][1]
    assert report["flota"]["candidato"] <= report["flota"]["base"]
