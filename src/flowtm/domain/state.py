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

Mathematical formulation (Avance II):
    Decision:   H = { h_r } in [2.0, 15.0]^n for the n optimizable routes
    Constraint: sum_r B_used(h_r) <= B_max
    where B_used(h_r) = ceil(T_r / h_r), T_r is the GTFS cycle time of route r and
    B_max is the fleet the current GTFS operation assigns to those routes.

Cycle times and B_max come from the scenario (``CorridorScenario.base_schedule``),
never from constants.
"""

import math
import random
from dataclasses import dataclass

MIN_HEADWAY_MIN = 2.0
MAX_HEADWAY_MIN = 15.0


def clip_headway(headway_min: float) -> float:
    """Clamp a headway to the operational bounds [2.0, 15.0] minutes."""
    return max(MIN_HEADWAY_MIN, min(MAX_HEADWAY_MIN, round(headway_min, 2)))


@dataclass
class ScheduleState:
    """
    Rational Agent State: dispatch headway (minutes) per optimizable route.

    Attributes:
        headways: Route code -> headway in minutes.
        cycle_times: Route code -> round-trip cycle time in minutes (from GTFS).
        max_fleet: Physical fleet bound B_max.
    """

    headways: dict[str, float]
    cycle_times: dict[str, float]
    max_fleet: int

    def fleet_used_by_route(self) -> dict[str, int]:
        """Buses required per route: B_used(h_r) = ceil(T_r / h_r)."""
        return {
            route: math.ceil(self.cycle_times[route] / max(0.1, headway))
            for route, headway in self.headways.items()
        }

    def total_fleet_used(self) -> int:
        """Total buses required across all routes: sum_r B_used(h_r)."""
        return sum(self.fleet_used_by_route().values())

    def is_fleet_feasible(self) -> bool:
        """Checks if total fleet does not exceed B_max (``max_fleet``)."""
        return self.total_fleet_used() <= self.max_fleet

    def copy(self) -> "ScheduleState":
        """Return an independent copy of this state."""
        return ScheduleState(
            headways=self.headways.copy(),
            cycle_times=self.cycle_times.copy(),
            max_fleet=self.max_fleet,
        )

    def generate_neighbor(
        self,
        step_min: float = 0.5,
        rng: random.Random | None = None,
        max_attempts: int = 10,
    ) -> "ScheduleState":
        """
        Agent Action:
        Generates an adjacent candidate state by perturbing dispatch headways.
        Reducing the interval on one route (increasing frequency) is compensated by
        increasing the interval on another route.

        The fleet constraint is enforced by construction: only candidates with
        ``total_fleet_used() <= max_fleet`` are returned. If no feasible candidate
        is found within ``max_attempts``, an unchanged copy of the current state is
        returned instead.

        Args:
            step_min: Headway perturbation step in minutes (default 0.5 min).
            rng: Random generator used for the perturbation. Pass a seeded
                ``random.Random`` for reproducible searches.
            max_attempts: Number of random perturbations to try.

        Returns:
            A new ScheduleState representing the perturbed (or unchanged) schedule.
        """
        rng = rng or random.Random()
        routes = list(self.headways.keys())

        if len(routes) < 2:
            return self.copy()

        for _ in range(max_attempts):
            candidate_headways = self.headways.copy()
            route_boost = rng.choice(routes)
            route_trim = rng.choice([r for r in routes if r != route_boost])

            candidate_headways[route_boost] = clip_headway(
                candidate_headways[route_boost] - step_min
            )
            candidate_headways[route_trim] = clip_headway(
                candidate_headways[route_trim] + step_min
            )

            candidate_state = ScheduleState(
                headways=candidate_headways,
                cycle_times=self.cycle_times,
                max_fleet=self.max_fleet,
            )
            if candidate_state.is_fleet_feasible():
                return candidate_state

        return self.copy()
