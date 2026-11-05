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
Heuristic search metaheuristic for dispatch schedule optimization.
Applies Metropolis acceptance probability over discrete headway candidate states
subject to the physical fleet constraint (B_total <= B_max).
"""

import math
import random
from pathlib import Path
from typing import Any

from flowtm.domain.models import SimulationResult
from flowtm.domain.state import ScheduleState
from flowtm.optimization.utility import UtilityCalculator
from flowtm.simulation.engine import CorridorSimulator


class SimulatedAnnealingOptimizer:
    """
    Optimizes trunk corridor dispatch headways to maximize passenger throughput,
    minimize platform wait times and contain overcrowding while strictly enforcing
    the physical fleet constraint of the schedule state (``max_fleet``).
    """

    def __init__(
        self,
        scenario_dir: Path,
        iterations: int = 30,
        initial_temp: float = 75.0,
        cooling_rate: float = 0.88,
        seed: int | None = 42,
        verbose: bool = True,
    ) -> None:
        self.simulator = CorridorSimulator(scenario_dir)
        self.utility_calc = UtilityCalculator()
        self.iterations = iterations
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        # Dedicated generator so neighbor generation and Metropolis acceptance are
        # reproducible without touching the global `random` state.
        self.rng = random.Random(seed)
        self.verbose = verbose
        self.history: list[dict[str, Any]] = []

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)

    def _format_progress(
        self,
        label: str,
        iteration: int,
        temperature: float,
        utility: float,
        result: SimulationResult,
        state: ScheduleState,
        fleet: int,
    ) -> str:
        return (
            f"[INFO] {label:<12} Iter {iteration:2d} | T: {temperature:5.1f} | "
            f"U(S): {utility:.4f} | "
            f"Espera: {result.avg_waiting_time_min:.2f}m | "
            f"Varados: {result.stranded_passengers_in_queue:,} | "
            f"Flota: {fleet}/{state.max_fleet} | {state.headways}"
        )

    def optimize(
        self, initial_state: ScheduleState
    ) -> tuple[ScheduleState, SimulationResult]:
        """
        Executes the Simulated Annealing optimization loop.

        Args:
            initial_state: Baseline ScheduleState with starting route headways.
                It must satisfy the fleet constraint.

        Returns:
            Tuple of (best_state, best_simulation_result). ``best_state`` always
            satisfies ``is_fleet_feasible()``.

        Raises:
            ValueError: If ``initial_state`` exceeds its fleet capacity.
        """
        if not initial_state.is_fleet_feasible():
            raise ValueError(
                "El estado inicial requiere "
                f"{initial_state.total_fleet_used()} buses y supera la flota "
                f"máxima de {initial_state.max_fleet}."
            )

        self.history.clear()
        max_fleet = initial_state.max_fleet
        current_state = initial_state
        current_result = self.simulator.simulate(current_state.headways)
        current_fleet = current_state.total_fleet_used()
        current_breakdown = self.utility_calc.evaluate_breakdown(
            current_result, fleet_used=current_fleet
        )
        current_utility = current_breakdown["utility"]

        best_state = current_state
        best_result = current_result
        best_utility = current_utility

        temperature = self.initial_temp

        self._log("=" * 80)
        self._log(
            f"[INFO] Optimización del agente racional ({self.iterations} iteraciones)"
        )
        self._log(
            f"[INFO] Base: U(S): {current_utility:.4f} | "
            f"Espera: {current_result.avg_waiting_time_min:.2f}m | "
            f"Varados: {current_result.stranded_passengers_in_queue:,} | "
            f"Flota: {current_fleet}/{max_fleet} | Horario: {current_state.headways}"
        )
        self._log("=" * 80)

        self.history.append(
            {
                "iteration": 0,
                "temperature": round(temperature, 2),
                "headways": current_state.headways.copy(),
                "utility": current_utility,
                "delta_u": 0.0,
                "accepted": True,
                "is_new_best": True,
                "best_utility": best_utility,
                "wait_time_min": round(current_result.avg_waiting_time_min, 2),
                "stranded_pax": current_result.stranded_passengers_in_queue,
                "overcrowded_pct": round(current_result.overcrowded_bus_pct, 1),
                "fleet_used": current_fleet,
                "breakdown": current_breakdown,
            }
        )

        for i in range(1, self.iterations + 1):
            neighbor = current_state.generate_neighbor(step_min=0.5, rng=self.rng)
            neighbor_fleet = neighbor.total_fleet_used()
            neighbor_result = self.simulator.simulate(neighbor.headways)
            neighbor_breakdown = self.utility_calc.evaluate_breakdown(
                neighbor_result, fleet_used=neighbor_fleet
            )
            neighbor_utility = neighbor_breakdown["utility"]

            delta_u = neighbor_utility - current_utility

            # Metropolis acceptance criterion. Infeasible neighbors are never
            # accepted, so the fleet bound holds by construction and not only
            # through the utility penalty.
            accept = False
            if neighbor.is_fleet_feasible():
                if delta_u > 0:
                    accept = True
                else:
                    prob = math.exp(delta_u / max(1e-5, temperature))
                    accept = self.rng.random() < prob

            is_new_best = False
            if accept:
                current_state = neighbor
                current_result = neighbor_result
                current_utility = neighbor_utility
                current_breakdown = neighbor_breakdown
                current_fleet = neighbor_fleet

                if current_utility > best_utility:
                    best_state = current_state
                    best_result = current_result
                    best_utility = current_utility
                    is_new_best = True
                    self._log(
                        self._format_progress(
                            "Nuevo óptimo",
                            i,
                            temperature,
                            best_utility,
                            best_result,
                            best_state,
                            current_fleet,
                        )
                        + f" | ΔU total: {best_utility - self.history[0]['utility']:+.4f}"
                    )
                else:
                    self._log(
                        self._format_progress(
                            "Aceptado",
                            i,
                            temperature,
                            current_utility,
                            current_result,
                            current_state,
                            current_fleet,
                        )
                    )
            else:
                self._log(
                    self._format_progress(
                        "Rechazado",
                        i,
                        temperature,
                        neighbor_utility,
                        neighbor_result,
                        neighbor,
                        neighbor_fleet,
                    )
                )

            self.history.append(
                {
                    "iteration": i,
                    "temperature": round(temperature, 2),
                    "headways": current_state.headways.copy(),
                    "utility": current_utility,
                    "delta_u": round(delta_u, 4),
                    "accepted": accept,
                    "is_new_best": is_new_best,
                    "best_utility": round(best_utility, 4),
                    "wait_time_min": round(current_result.avg_waiting_time_min, 2),
                    "stranded_pax": current_result.stranded_passengers_in_queue,
                    "overcrowded_pct": round(current_result.overcrowded_bus_pct, 1),
                    "fleet_used": current_fleet,
                    "breakdown": current_breakdown,
                }
            )

            temperature *= self.cooling_rate

        return best_state, best_result
