# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.domain.state
===================
State space representation and neighborhood search actions for the Rational Agent.
Encapsulates dispatch headways for the 6 trunk corridor routes:
B13, B18, B23, B27, B74, B75.

Mathematical Formulation (from Avance II Project Document):
    Decision: H = { h_B13, h_B18, h_B23, h_B27, h_B74, h_B75 } in [2.0, 15.0]^6 subset R^6
    Constraint: sum_r B_used(h_r) <= B_max = 106 buses
    where B_used(h_r) = ceil(TiempoCiclo_r / h_r)
"""

import math
import random
from dataclasses import dataclass, field

# Calibrated cycle times (in minutes) for the 6 trunk services operating
# on the Autopista Norte - Caracas corridor (round-trip + terminal regulation)
OFFICIAL_CYCLE_TIMES_MIN: dict[str, float] = {
    "B13": 50.0,
    "B18": 40.0,
    "B23": 45.0,
    "B27": 48.0,
    "B74": 48.0,
    "B75": 44.0,
}

MAX_FLEET_CAPACITY: int = 106


@dataclass
class ScheduleState:
    """
    Rational Agent State:
    Dictionary mapping route codes to dispatch headways (intervals between buses) in minutes.

    Example for the 6 official corridor services (Peak Hour):
        {
            'B13': 2.0,
            'B18': 2.0,
            'B23': 3.0,
            'B27': 4.0,
            'B74': 4.0,
            'B75': 2.0
        }
    """

    headways: dict[str, float]
    cycle_times: dict[str, float] = field(
        default_factory=lambda: OFFICIAL_CYCLE_TIMES_MIN.copy()
    )
    max_fleet: int = MAX_FLEET_CAPACITY

    def fleet_used_by_route(self) -> dict[str, int]:
        """
        Calculates fleet consumed by each route according to the formula:
        B_used(h_r) = ceil(TiempoCiclo_r / h_r)
        """
        usage: dict[str, int] = {}
        for route, h in self.headways.items():
            c_time = self.cycle_times.get(route, 45.0)
            usage[route] = math.ceil(c_time / max(0.1, h))
        return usage

    def total_fleet_used(self) -> int:
        """Total buses required across all routes: sum_r B_used(h_r)."""
        return sum(self.fleet_used_by_route().values())

    def is_fleet_feasible(self) -> bool:
        """Checks if total fleet does not exceed B_max = 106."""
        return self.total_fleet_used() <= self.max_fleet

    def generate_neighbor(self, step_min: float = 0.5) -> "ScheduleState":
        """
        Agent Action:
        Generates an adjacent candidate state by perturbing dispatch headways.
        To respect the physical fleet capacity constraint (106 buses), reducing the interval
        on one route (increasing frequency) requires compensating by increasing the interval
        on another route.

        Args:
            step_min: Headway perturbation step in minutes (default 0.5 min).

        Returns:
            A new ScheduleState representing the perturbed schedule.
        """
        new_headways = self.headways.copy()
        routes = list(new_headways.keys())

        if len(routes) < 2:
            return ScheduleState(headways=new_headways, cycle_times=self.cycle_times)

        # Try a few candidate neighbor perturbations to find one respecting or nearing fleet capacity
        best_candidate = None
        for _ in range(10):
            cand = new_headways.copy()
            route_boost = random.choice(routes)
            route_trim = random.choice([r for r in routes if r != route_boost])

            cand[route_boost] = max(
                2.0, min(15.0, round(cand[route_boost] - step_min, 2))
            )
            cand[route_trim] = max(
                2.0, min(15.0, round(cand[route_trim] + step_min, 2))
            )

            cand_state = ScheduleState(
                headways=cand, cycle_times=self.cycle_times, max_fleet=self.max_fleet
            )
            if cand_state.total_fleet_used() <= self.max_fleet:
                return cand_state
            if (
                best_candidate is None
                or cand_state.total_fleet_used() < best_candidate.total_fleet_used()
            ):
                best_candidate = cand_state

        return best_candidate or ScheduleState(
            headways=new_headways,
            cycle_times=self.cycle_times,
            max_fleet=self.max_fleet,
        )

    # Backward compatibility aliases
    @property
    def frecuencias(self) -> dict[str, float]:
        return self.headways

    @frecuencias.setter
    def frecuencias(self, value: dict[str, float]) -> None:
        self.headways = value

    def generar_vecino(self, paso_min: float = 0.5) -> "ScheduleState":
        return self.generate_neighbor(step_min=paso_min)
