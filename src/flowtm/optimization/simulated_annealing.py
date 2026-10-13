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
subject to physical fleet constraints (B_max <= 106 buses).
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
    minimize platform wait times, contain overcrowding, and strictly enforce
    the 106 bus physical fleet constraint.
    """

    def __init__(
        self,
        scenario_dir: Path,
        iterations: int = 30,
        initial_temp: float = 75.0,
        cooling_rate: float = 0.88,
    ) -> None:
        self.simulator = CorridorSimulator(scenario_dir)
        self.utility_calc = UtilityCalculator()
        self.iterations = iterations
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.history: list[dict[str, Any]] = []

    def optimize(
        self, initial_state: ScheduleState
    ) -> tuple[ScheduleState, SimulationResult]:
        """
        Executes the Simulated Annealing optimization loop.

        Args:
            initial_state: Baseline ScheduleState with starting route headways.

        Returns:
            Tuple of (best_state, best_simulation_result).
        """
        self.history.clear()
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
        best_fleet = current_fleet

        temperature = self.initial_temp

        print("=" * 80)
        print(f"[SEARCH] Rational Agent Optimization ({self.iterations} iterations):")
        print(
            f"   [BASE] U(S): {current_utility:.4f} | Wait: {current_result.avg_waiting_time_min:.2f}m | "
            f"Stranded: {current_result.stranded_passengers_in_queue:,} | "
            f"Fleet: {current_fleet}/106 | Schedule: {current_state.headways}"
        )
        print("=" * 80)

        # Record initial baseline at iteration 0
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
            neighbor = current_state.generate_neighbor(step_min=0.5)
            neighbor_fleet = neighbor.total_fleet_used()
            neighbor_result = self.simulator.simulate(neighbor.headways)
            neighbor_breakdown = self.utility_calc.evaluate_breakdown(
                neighbor_result, fleet_used=neighbor_fleet
            )
            neighbor_utility = neighbor_breakdown["utility"]

            delta_u = neighbor_utility - current_utility

            # Metropolis acceptance criterion
            accept = False
            if delta_u > 0:
                accept = True
            else:
                prob = math.exp(delta_u / max(1e-5, temperature))
                if random.random() < prob:
                    accept = True

            is_new_best = False
            if accept:
                current_state = neighbor
                current_result = neighbor_result
                current_utility = neighbor_utility
                current_fleet = neighbor_fleet

                if current_utility > best_utility and current_fleet <= 106:
                    best_state = current_state
                    best_result = current_result
                    best_utility = current_utility
                    best_fleet = current_fleet
                    is_new_best = True
                    print(
                        f"   [NEW OPTIMUM] Iter {i:2d} | T: {temperature:5.1f} | "
                        f"U(S): {best_utility:.4f} (ΔU: {best_utility - self.history[0]['utility']:+.4f}) | "
                        f"Wait: {best_result.avg_waiting_time_min:.2f}m | "
                        f"Stranded: {best_result.stranded_passengers_in_queue:,} | "
                        f"Fleet: {best_fleet}/106 | {best_state.headways}"
                    )
                else:
                    print(
                        f"   [ACCEPTED]    Iter {i:2d} | T: {temperature:5.1f} | "
                        f"U(S): {current_utility:.4f} | "
                        f"Wait: {current_result.avg_waiting_time_min:.2f}m | "
                        f"Stranded: {current_result.stranded_passengers_in_queue:,} | "
                        f"Fleet: {current_fleet}/106 | {current_state.headways}"
                    )
            else:
                print(
                    f"   [REJECTED]    Iter {i:2d} | T: {temperature:5.1f} | "
                    f"U(S): {neighbor_utility:.4f} | "
                    f"Wait: {neighbor_result.avg_waiting_time_min:.2f}m | "
                    f"Stranded: {neighbor_result.stranded_passengers_in_queue:,} | "
                    f"Fleet: {neighbor_fleet}/106 | {neighbor.headways}"
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
                    "breakdown": neighbor_breakdown if accept else current_breakdown,
                }
            )

            temperature *= self.cooling_rate

        return best_state, best_result

    # Backward compatibility alias
    def optimizar(
        self, estado_inicial: ScheduleState
    ) -> tuple[ScheduleState, SimulationResult]:
        return self.optimize(estado_inicial)
