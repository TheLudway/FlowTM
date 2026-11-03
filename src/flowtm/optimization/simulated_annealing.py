# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.optimization.simulated_annealing
=======================================
Rational agent based on Simulated Annealing.

Thin, stateful wrapper over :func:`flowtm.optimization.search.simulated_annealing`
that owns a :class:`ScheduleEvaluator` (expected utility over several seeds) and
keeps the search history for reporting.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from flowtm.domain.models import SimulationResult
from flowtm.domain.state import ScheduleState
from flowtm.optimization.evaluator import ScheduleEvaluator
from flowtm.optimization.search import (
    IterationCallback,
    SearchResult,
    simulated_annealing as run_annealing,
)

DEFAULT_TRAINING_SEEDS = (1001, 1002, 1003, 1004, 1005)


class SimulatedAnnealingOptimizer:
    """
    Optimizes dispatch headways maximizing the expected utility U(S) under the
    physical fleet bound of the schedule state.
    """

    def __init__(
        self,
        scenario_dir: Path,
        budget: int = 120,
        seeds: Sequence[int] = DEFAULT_TRAINING_SEEDS,
        step_min: float = 0.5,
        initial_temperature: float | None = None,
        seed: int = 42,
        verbose: bool = True,
        workers: int | None = None,
    ) -> None:
        self.scenario_dir = Path(scenario_dir)
        self.budget = budget
        self.seeds = tuple(seeds)
        self.step_min = step_min
        self.initial_temperature = initial_temperature
        self.seed = seed
        self.verbose = verbose
        self.workers = workers
        self.history: list[dict[str, Any]] = []
        self.result: SearchResult | None = None

    def _log(self, entry: dict[str, Any]) -> None:
        if not self.verbose:
            return
        label = (
            "Nuevo óptimo"
            if entry["is_new_best"]
            else ("Aceptado" if entry["accepted"] else "Rechazado")
        )
        temperature = entry["temperature"] or 0.0
        print(
            f"[INFO] {label:<12} Iter {entry['iteration']:3d} | T: {temperature:8.5f} | "
            f"U(S): {entry['candidate_utility']:.4f} ± {entry['candidate_utility_se']:.4f} | "
            f"Mejor: {entry['best_utility']:.4f} | Espera: {entry['wait_time_min']:.2f}m | "
            f"Flota: {entry['fleet_used']} | Evals: {entry['evaluations']}"
        )

    def optimize(
        self,
        initial_state: ScheduleState,
        on_iteration: IterationCallback | None = None,
    ) -> tuple[ScheduleState, SimulationResult]:
        """
        Run the search from ``initial_state``.

        Returns:
            (best_state, simulation of best_state with the first training seed).

        Raises:
            ValueError: If ``initial_state`` exceeds its fleet capacity.
        """

        def callback(entry: dict[str, Any]) -> None:
            self._log(entry)
            if on_iteration is not None:
                on_iteration(entry)

        if self.verbose:
            print(
                f"[INFO] Recocido simulado: presupuesto {self.budget} evaluaciones x "
                f"{len(self.seeds)} semillas | paso {self.step_min} min"
            )
        with ScheduleEvaluator(
            self.scenario_dir, self.seeds, workers=self.workers
        ) as evaluator:
            self.result = run_annealing(
                evaluator,
                initial_state,
                budget=self.budget,
                seed=self.seed,
                step_min=self.step_min,
                initial_temperature=self.initial_temperature,
                on_iteration=callback,
            )
            best_simulation = evaluator.simulator.simulate(
                self.result.best_state.headways, seed=self.seeds[0]
            )
        self.history = self.result.history
        return self.result.best_state, best_simulation
