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
    where (Little's law per direction)
        B_used(h_r) = ceil((T_r^ida + L) / h_r) + B_r^regreso
    T_r^ida is the GTFS peak trip time of the optimized (southbound) leg, L the
    terminal layover, and B_r^regreso the vehicles the return route needs at its
    own GTFS headway (fixed, not optimized). B_max is the fleet the current GTFS
    operation requires for those routes.

Leg times, return fleets and B_max come from the scenario
(``CorridorScenario.base_schedule``), never from constants.
"""

import math
import random
from dataclasses import dataclass, field

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
        headways: Route code -> headway in minutes of the optimized leg.
        leg_times: Route code -> trip time + terminal layover (minutes) of the
            optimized leg.
        max_fleet: Physical fleet bound B_max.
        fixed_fleet: Route code -> vehicles of the return leg (fixed GTFS headway).
    """

    headways: dict[str, float]
    leg_times: dict[str, float]
    max_fleet: int
    fixed_fleet: dict[str, int] = field(default_factory=dict)

    def fleet_used_by_route(self) -> dict[str, int]:
        """Buses per route: ceil(leg_time / h) + fixed return-leg fleet."""
        return {
            route: math.ceil(self.leg_times[route] / max(0.1, headway))
            + self.fixed_fleet.get(route, 0)
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
            leg_times=self.leg_times.copy(),
            max_fleet=self.max_fleet,
            fixed_fleet=self.fixed_fleet.copy(),
        )

    def with_headways(self, headways: dict[str, float]) -> "ScheduleState":
        """Same routes, leg times and fleet bound with different headways."""
        return ScheduleState(
            headways=dict(headways),
            leg_times=self.leg_times,
            max_fleet=self.max_fleet,
            fixed_fleet=self.fixed_fleet,
        )

    def generate_neighbor(
        self,
        step_min: float = 0.5,
        rng: random.Random | None = None,
        max_attempts: int = 10,
        move: str = "mixed",
    ) -> "ScheduleState":
        """
        Agent Action: an adjacent candidate obtained by perturbing headways.

        Move types:
            * ``swap``: one route gains frequency (-step) and another loses it
              (+step), redistributing fleet between routes.
            * ``single``: one route changes by +/-step, freeing or using fleet.
            * ``mixed``: each attempt picks ``swap`` or ``single`` at random.

        The fleet constraint holds by construction: only candidates with
        ``total_fleet_used() <= max_fleet`` are returned; if none is found within
        ``max_attempts``, an unchanged copy of the current state is returned.

        Args:
            step_min: Headway perturbation step in minutes.
            rng: Random generator; pass a seeded ``random.Random`` to reproduce.
            max_attempts: Number of random perturbations to try.
            move: ``swap``, ``single`` or ``mixed``.
        """
        if move not in {"swap", "single", "mixed"}:
            raise ValueError(f"Movimiento desconocido: {move}")
        rng = rng or random.Random()
        routes = list(self.headways.keys())
        if not routes or (move == "swap" and len(routes) < 2):
            return self.copy()

        for _ in range(max_attempts):
            kind = move
            if move == "mixed":
                kind = "swap" if len(routes) >= 2 and rng.random() < 0.5 else "single"

            candidate_headways = self.headways.copy()
            if kind == "swap":
                route_boost = rng.choice(routes)
                route_trim = rng.choice([r for r in routes if r != route_boost])
                candidate_headways[route_boost] = clip_headway(
                    candidate_headways[route_boost] - step_min
                )
                candidate_headways[route_trim] = clip_headway(
                    candidate_headways[route_trim] + step_min
                )
            else:
                route = rng.choice(routes)
                candidate_headways[route] = clip_headway(
                    candidate_headways[route] + rng.choice((-step_min, step_min))
                )

            if candidate_headways == self.headways:
                continue
            candidate_state = self.with_headways(candidate_headways)
            if candidate_state.is_fleet_feasible():
                return candidate_state

        return self.copy()

    def random_feasible(
        self, rng: random.Random, max_attempts: int = 200
    ) -> "ScheduleState":
        """
        Uniform random schedule in [2, 15]^n (0.5-minute grid) that satisfies the
        fleet bound; returns a copy of the current state if none is found.
        """
        grid = [
            MIN_HEADWAY_MIN + 0.5 * k
            for k in range(int((MAX_HEADWAY_MIN - MIN_HEADWAY_MIN) / 0.5) + 1)
        ]
        for _ in range(max_attempts):
            candidate = self.with_headways({r: rng.choice(grid) for r in self.headways})
            if candidate.is_fleet_feasible():
                return candidate
        return self.copy()

    def repaired_to_fleet(self, step_min: float = 0.5) -> "ScheduleState":
        """
        Closest feasible schedule obtained by greedily lengthening the headway of
        the route that frees the most vehicles per step. Used when the fleet bound
        is set below the fleet the current schedule needs.
        """
        state = self.copy()
        while not state.is_fleet_feasible():
            best_route, best_gain = None, 0.0
            for route, headway in state.headways.items():
                longer = clip_headway(headway + step_min)
                if longer <= headway:
                    continue
                # Continuous fleet freed (T/h): ceil() plateaus would stall a
                # purely integer greedy rule.
                gain = self.leg_times[route] / headway - self.leg_times[route] / longer
                if gain > best_gain:
                    best_route, best_gain = route, gain
            if best_route is None:
                # Even the sparsest schedule cannot meet the bound.
                raise ValueError(
                    f"La cota de {self.max_fleet} buses no es alcanzable: el horario "
                    f"más espaciado requiere {state.total_fleet_used()} buses."
                )
            state = state.with_headways(
                {
                    **state.headways,
                    best_route: clip_headway(state.headways[best_route] + step_min),
                }
            )
        return state
