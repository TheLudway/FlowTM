# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.optimization.evaluator
=============================
Stochastic evaluation of a schedule over several simulation seeds.

The simulator is stochastic, so a single run per candidate rewards schedules that
happen to be lucky with that seed (we measured -6.1% on the optimization seed vs
-1.9% out of sample). The evaluator scores each candidate as the *expected*
utility over a fixed set of seeds, reusing the same seeds for every candidate
(common random numbers), which reduces the variance of the comparison between
two schedules. Seeds run in parallel worker processes and results are cached.
"""

import math
import multiprocessing
import os
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flowtm.domain.models import SimulationResult
from flowtm.domain.state import ScheduleState
from flowtm.optimization.utility import UtilityCalculator
from flowtm.simulation.engine import CorridorSimulator

METRIC_FIELDS = (
    "avg_waiting_time_min",
    "avg_occupancy_rate",
    "overcrowded_bus_pct",
    "total_transported_passengers",
    "stranded_passengers_in_queue",
    "total_dispatched_buses",
    "avg_dispatch_delay_min",
)

_worker_simulator: CorridorSimulator | None = None


def _init_worker(scenario_dir: str) -> None:
    global _worker_simulator
    _worker_simulator = CorridorSimulator(Path(scenario_dir))


def _simulate_metrics(
    simulator: CorridorSimulator, headways: dict[str, float], seed: int
) -> dict[str, float]:
    result = simulator.simulate(headways, seed=seed)
    return {name: float(getattr(result, name)) for name in METRIC_FIELDS}


def _worker_run(headways: dict[str, float], seed: int) -> dict[str, float]:
    assert _worker_simulator is not None
    return _simulate_metrics(_worker_simulator, headways, seed)


def _as_result(metrics: dict[str, float]) -> SimulationResult:
    return SimulationResult(
        avg_waiting_time_min=metrics["avg_waiting_time_min"],
        avg_occupancy_rate=metrics["avg_occupancy_rate"],
        overcrowded_bus_pct=metrics["overcrowded_bus_pct"],
        total_transported_passengers=round(metrics["total_transported_passengers"]),
        stranded_passengers_in_queue=round(metrics["stranded_passengers_in_queue"]),
        total_dispatched_buses=round(metrics["total_dispatched_buses"]),
        avg_dispatch_delay_min=metrics["avg_dispatch_delay_min"],
    )


@dataclass(frozen=True)
class Evaluation:
    """Expected performance of a schedule over the evaluator seeds."""

    headways: dict[str, float]
    fleet_used: int
    utility: float
    utility_std: float
    metrics: dict[str, float]
    breakdown: dict[str, Any]
    per_seed_utility: list[float] = field(default_factory=list)
    per_seed_metrics: list[dict[str, float]] = field(default_factory=list)

    @property
    def wait_time_min(self) -> float:
        return self.metrics["avg_waiting_time_min"]

    def standard_error(self) -> float:
        n = len(self.per_seed_utility)
        return self.utility_std / math.sqrt(n) if n > 1 else 0.0


class ScheduleEvaluator:
    """Scores schedules by their expected utility over a fixed set of seeds."""

    def __init__(
        self,
        scenario_dir: Path,
        seeds: Sequence[int],
        utility: UtilityCalculator | None = None,
        workers: int | None = None,
    ) -> None:
        self.scenario_dir = Path(scenario_dir)
        self.seeds = list(seeds)
        self.simulator = CorridorSimulator(self.scenario_dir)
        self.utility = utility or UtilityCalculator(
            max_fleet=self.simulator.scenario.max_fleet
        )
        self.workers = min(len(self.seeds), workers or os.cpu_count() or 1)
        self._pool: ProcessPoolExecutor | None = None
        self._cache: dict[tuple[tuple[str, float], ...], Evaluation] = {}
        self.n_evaluations = 0
        self.n_simulations = 0

    def __enter__(self) -> "ScheduleEvaluator":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown()
            self._pool = None

    def _run_seeds(self, headways: dict[str, float]) -> list[dict[str, float]]:
        if self.workers <= 1:
            return [_simulate_metrics(self.simulator, headways, s) for s in self.seeds]
        if self._pool is None:
            # "spawn": forking a process that already runs Polars threads can
            # deadlock, so workers start from a clean interpreter. Scripts that
            # use the evaluator must guard their entry point with __main__.
            self._pool = ProcessPoolExecutor(
                max_workers=self.workers,
                mp_context=multiprocessing.get_context("spawn"),
                initializer=_init_worker,
                initargs=(str(self.scenario_dir),),
            )
        return list(
            self._pool.map(_worker_run, [headways] * len(self.seeds), self.seeds)
        )

    def evaluate(self, state: ScheduleState) -> Evaluation:
        """Expected utility of ``state`` (cached: identical schedules are free)."""
        key = tuple(sorted(state.headways.items()))
        if key in self._cache:
            return self._cache[key]

        fleet = state.total_fleet_used()
        runs = self._run_seeds(dict(state.headways))
        self.n_evaluations += 1
        self.n_simulations += len(runs)

        utilities = [
            self.utility.evaluate(_as_result(run), fleet_used=fleet) for run in runs
        ]
        mean_metrics = {
            name: statistics.fmean(run[name] for run in runs) for name in METRIC_FIELDS
        }
        evaluation = Evaluation(
            headways=dict(state.headways),
            fleet_used=fleet,
            utility=statistics.fmean(utilities),
            utility_std=statistics.stdev(utilities) if len(utilities) > 1 else 0.0,
            metrics=mean_metrics,
            breakdown=self.utility.evaluate_breakdown(
                _as_result(mean_metrics), fleet_used=fleet
            ),
            per_seed_utility=utilities,
            per_seed_metrics=runs,
        )
        self._cache[key] = evaluation
        return evaluation


# Two-sided 95% Student t critical values by degrees of freedom.
_T_CRITICAL_95 = {1: 12.706, 2: 4.303, 4: 2.776, 9: 2.262, 19: 2.093, 29: 2.045}


def _t_critical(degrees_of_freedom: int) -> float:
    eligible = [df for df in _T_CRITICAL_95 if df <= degrees_of_freedom]
    return _T_CRITICAL_95[max(eligible)] if eligible else _T_CRITICAL_95[1]


def holdout_comparison(
    scenario_dir: Path,
    baseline_state: ScheduleState,
    candidate_state: ScheduleState,
    seeds: Sequence[int],
    workers: int | None = None,
) -> dict[str, Any]:
    """
    Out-of-sample check on seeds never used during the search: paired difference
    of the expected utility and the mean wait time, with 95% CI and wins.
    """
    with ScheduleEvaluator(scenario_dir, seeds, workers=workers) as evaluator:
        base = evaluator.evaluate(baseline_state)
        cand = evaluator.evaluate(candidate_state)

    def series(evaluation: Evaluation, name: str) -> list[float]:
        return [run[name] for run in evaluation.per_seed_metrics]

    def paired(
        base_values: list[float], cand_values: list[float], better_if_higher: bool
    ):
        diffs = [c - b for b, c in zip(base_values, cand_values, strict=True)]
        mean = statistics.fmean(diffs)
        half = (
            _t_critical(len(diffs) - 1)
            * statistics.stdev(diffs)
            / math.sqrt(len(diffs))
            if len(diffs) > 1
            else 0.0
        )
        wins = sum((d > 0) if better_if_higher else (d < 0) for d in diffs)
        return {
            "base": round(statistics.fmean(base_values), 4),
            "candidato": round(statistics.fmean(cand_values), 4),
            "diferencia": round(mean, 4),
            "diferencia_pct": (
                round(mean / base_mean * 100, 2)
                if (base_mean := statistics.fmean(base_values))
                else 0.0
            ),
            "ic95": [round(mean - half, 4), round(mean + half, 4)],
            "semillas_mejor": wins,
            "semillas": len(diffs),
            # The 95% CI excludes zero (in either direction).
            "significativo": (mean - half > 0) or (mean + half < 0),
            "mejora": (mean > 0) if better_if_higher else (mean < 0),
        }

    return {
        "semillas": list(seeds),
        "utilidad": paired(base.per_seed_utility, cand.per_seed_utility, True),
        "espera_min": paired(
            series(base, "avg_waiting_time_min"),
            series(cand, "avg_waiting_time_min"),
            False,
        ),
        "sobrecupo_pct": paired(
            series(base, "overcrowded_bus_pct"),
            series(cand, "overcrowded_bus_pct"),
            False,
        ),
        "varados": paired(
            series(base, "stranded_passengers_in_queue"),
            series(cand, "stranded_passengers_in_queue"),
            False,
        ),
        "transportados": paired(
            series(base, "total_transported_passengers"),
            series(cand, "total_transported_passengers"),
            True,
        ),
        "flota": {"base": base.fleet_used, "candidato": cand.fleet_used},
    }
