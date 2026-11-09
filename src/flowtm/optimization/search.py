# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.optimization.search
==========================
Local-search agents over the schedule space, sharing one interface so they can be
compared with the same evaluation budget:

* ``random_search``: uniform random feasible schedules (reference baseline).
* ``hill_climbing``: stochastic first-improvement local search.
* ``simulated_annealing``: Metropolis acceptance with a temperature calibrated
  from the observed utility differences (Kirkpatrick: the initial temperature
  accepts ~80% of worsening moves) and geometric cooling to 1% of T0.

The budget counts *distinct* schedule evaluations (each one runs the simulator
once per evaluator seed); revisiting a cached schedule is free.
"""

import math
import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from flowtm.domain.state import ScheduleState
from flowtm.optimization.evaluator import Evaluation, ScheduleEvaluator

IterationCallback = Callable[[dict[str, Any]], None]

INITIAL_ACCEPTANCE = 0.8
FINAL_TEMPERATURE_RATIO = 0.01
CALIBRATION_SAMPLES = 6


@dataclass
class SearchResult:
    """Outcome of one search run."""

    algorithm: str
    initial: Evaluation
    best: Evaluation
    best_state: ScheduleState
    history: list[dict[str, Any]] = field(default_factory=list)
    evaluations: int = 0
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def delta_utility(self) -> float:
        return self.best.utility - self.initial.utility


def _record(
    history: list[dict[str, Any]],
    on_iteration: IterationCallback | None,
    *,
    iteration: int,
    current: Evaluation,
    candidate: Evaluation,
    best: Evaluation,
    accepted: bool,
    is_new_best: bool,
    evaluations: int,
    temperature: float | None = None,
) -> None:
    entry = {
        "iteration": iteration,
        "temperature": None if temperature is None else round(temperature, 6),
        "headways": dict(current.headways),
        "utility": round(current.utility, 4),
        "delta_u": round(candidate.utility - current.utility, 4) if iteration else 0.0,
        "accepted": accepted,
        "is_new_best": is_new_best,
        "best_utility": round(best.utility, 4),
        "wait_time_min": round(current.metrics["avg_waiting_time_min"], 3),
        "stranded_pax": round(current.metrics["stranded_passengers_in_queue"]),
        "overcrowded_pct": round(current.metrics["overcrowded_bus_pct"], 2),
        "fleet_used": current.fleet_used,
        "breakdown": current.breakdown,
        "candidate_headways": dict(candidate.headways),
        "candidate_utility": round(candidate.utility, 4),
        "candidate_utility_se": round(candidate.standard_error(), 4),
        "evaluations": evaluations,
    }
    history.append(entry)
    if on_iteration is not None:
        on_iteration(entry)


def _budget_left(evaluator: ScheduleEvaluator, start: int, budget: int) -> bool:
    return evaluator.n_evaluations - start < budget


def random_search(
    evaluator: ScheduleEvaluator,
    initial_state: ScheduleState,
    budget: int,
    seed: int = 42,
    on_iteration: IterationCallback | None = None,
) -> SearchResult:
    """Sample uniform random feasible schedules and keep the best one."""
    rng = random.Random(seed)
    start = evaluator.n_evaluations
    initial = evaluator.evaluate(initial_state)
    best, best_state = initial, initial_state
    history: list[dict[str, Any]] = []
    _record(
        history,
        on_iteration,
        iteration=0,
        current=initial,
        candidate=initial,
        best=best,
        accepted=True,
        is_new_best=True,
        evaluations=1,
    )

    iteration = 0
    while _budget_left(evaluator, start, budget) and iteration < 5 * budget:
        iteration += 1
        state = initial_state.random_feasible(rng)
        candidate = evaluator.evaluate(state)
        is_new_best = candidate.utility > best.utility
        if is_new_best:
            best, best_state = candidate, state
        _record(
            history,
            on_iteration,
            iteration=iteration,
            current=best,
            candidate=candidate,
            best=best,
            accepted=is_new_best,
            is_new_best=is_new_best,
            evaluations=evaluator.n_evaluations - start,
        )

    return SearchResult(
        "busqueda_aleatoria",
        initial,
        best,
        best_state,
        history,
        evaluator.n_evaluations - start,
        {"budget": budget, "seed": seed},
    )


def hill_climbing(
    evaluator: ScheduleEvaluator,
    initial_state: ScheduleState,
    budget: int,
    seed: int = 42,
    step_min: float = 0.5,
    on_iteration: IterationCallback | None = None,
) -> SearchResult:
    """Stochastic first-improvement hill climbing (only accepts improvements)."""
    rng = random.Random(seed)
    start = evaluator.n_evaluations
    current_state = initial_state
    current = initial = evaluator.evaluate(initial_state)
    history: list[dict[str, Any]] = []
    _record(
        history,
        on_iteration,
        iteration=0,
        current=current,
        candidate=current,
        best=current,
        accepted=True,
        is_new_best=True,
        evaluations=1,
    )

    iteration = 0
    while _budget_left(evaluator, start, budget) and iteration < 5 * budget:
        iteration += 1
        neighbor_state = current_state.generate_neighbor(step_min=step_min, rng=rng)
        candidate = evaluator.evaluate(neighbor_state)
        accepted = candidate.utility > current.utility
        if accepted:
            current_state, current = neighbor_state, candidate
        _record(
            history,
            on_iteration,
            iteration=iteration,
            current=current,
            candidate=candidate,
            best=current,
            accepted=accepted,
            is_new_best=accepted,
            evaluations=evaluator.n_evaluations - start,
        )

    return SearchResult(
        "hill_climbing",
        initial,
        current,
        current_state,
        history,
        evaluator.n_evaluations - start,
        {"budget": budget, "seed": seed, "step_min": step_min},
    )


def calibrate_temperature(
    evaluator: ScheduleEvaluator,
    state: ScheduleState,
    initial: Evaluation,
    rng: random.Random,
    step_min: float,
    samples: int = CALIBRATION_SAMPLES,
) -> float:
    """
    Initial temperature such that a typical worsening move is accepted with
    probability ``INITIAL_ACCEPTANCE``: T0 = -mean(|dU_worse|) / ln(p0).
    """
    worsening = []
    for _ in range(samples):
        neighbor = evaluator.evaluate(
            state.generate_neighbor(step_min=step_min, rng=rng)
        )
        if neighbor.utility < initial.utility:
            worsening.append(initial.utility - neighbor.utility)
    scale = statistics.fmean(worsening) if worsening else max(1e-3, initial.utility_std)
    return -scale / math.log(INITIAL_ACCEPTANCE)


def simulated_annealing(
    evaluator: ScheduleEvaluator,
    initial_state: ScheduleState,
    budget: int,
    seed: int = 42,
    step_min: float = 0.5,
    initial_temperature: float | None = None,
    on_iteration: IterationCallback | None = None,
) -> SearchResult:
    """
    Simulated annealing with Metropolis acceptance P = exp(dU / T).

    If ``initial_temperature`` is None it is calibrated from the utility
    differences of a few neighbors (those evaluations count against the budget).
    Cooling is geometric so that T reaches 1% of T0 when the budget is spent.
    """
    if not initial_state.is_fleet_feasible():
        raise ValueError(
            f"El estado inicial requiere {initial_state.total_fleet_used()} buses y "
            f"supera la flota máxima de {initial_state.max_fleet}."
        )
    rng = random.Random(seed)
    start = evaluator.n_evaluations
    current_state = best_state = initial_state
    current = best = initial = evaluator.evaluate(initial_state)

    temperature = initial_temperature or calibrate_temperature(
        evaluator, initial_state, initial, rng, step_min
    )
    initial_temperature_used = temperature
    remaining = max(1, budget - (evaluator.n_evaluations - start))
    cooling_rate = FINAL_TEMPERATURE_RATIO ** (1 / remaining)

    history: list[dict[str, Any]] = []
    _record(
        history,
        on_iteration,
        iteration=0,
        current=current,
        candidate=current,
        best=best,
        accepted=True,
        is_new_best=True,
        evaluations=evaluator.n_evaluations - start,
        temperature=temperature,
    )

    iteration = 0
    while _budget_left(evaluator, start, budget) and iteration < 5 * budget:
        iteration += 1
        neighbor_state = current_state.generate_neighbor(step_min=step_min, rng=rng)
        before = evaluator.n_evaluations
        candidate = evaluator.evaluate(neighbor_state)
        delta = candidate.utility - current.utility
        accepted = delta > 0 or rng.random() < math.exp(delta / max(1e-12, temperature))
        if accepted:
            current_state, current = neighbor_state, candidate
        is_new_best = current.utility > best.utility
        if is_new_best:
            best_state, best = current_state, current
        _record(
            history,
            on_iteration,
            iteration=iteration,
            current=current,
            candidate=candidate,
            best=best,
            accepted=accepted,
            is_new_best=is_new_best,
            evaluations=evaluator.n_evaluations - start,
            temperature=temperature,
        )
        # Cool only when a new schedule was actually simulated.
        if evaluator.n_evaluations > before:
            temperature *= cooling_rate

    return SearchResult(
        "recocido_simulado",
        initial,
        best,
        best_state,
        history,
        evaluator.n_evaluations - start,
        {
            "budget": budget,
            "seed": seed,
            "step_min": step_min,
            "initial_temperature": initial_temperature_used,
            "cooling_rate": cooling_rate,
            "initial_acceptance": INITIAL_ACCEPTANCE,
        },
    )


ALGORITHMS: dict[str, Callable[..., SearchResult]] = {
    "busqueda_aleatoria": random_search,
    "hill_climbing": hill_climbing,
    "recocido_simulado": simulated_annealing,
}
