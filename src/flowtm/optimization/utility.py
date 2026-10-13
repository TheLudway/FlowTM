# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.optimization.utility
===========================
Multi-criteria Utility Function U(S) for the Rational Agent.
Directly implements Section 3 (PEAS Model - Performance Dimension) of the official
Avance II Project Specification:

    U(S) = - [ w1 * W_mean + w2 * (Sobrecupo_95%)^1.5 + w3 * Q_remanente + w4 * B_usados ]

Exact weights from academic specification:
    w1 = 0.40  (Weighted mean passenger waiting time in minutes)
    w2 = 0.30  (Fraction of buses with occupancy >= 95%, exponential penalty 1.5)
    w3 = 0.15  (Stranded passengers at platform at the end of the peak hour)
    w4 = 0.15  (Fleet consumed out of B_max = 106 buses)
"""

from typing import Any

from flowtm.domain.models import SimulationResult


class UtilityCalculator:
    """
    Evaluates the quality of a dispatch schedule state S.
    The utility score is negative (cost formulation), where values closer to zero are optimal.
    """

    def __init__(
        self,
        w_wait: float = 0.40,
        w_overcrowding: float = 0.30,
        w_stranded: float = 0.15,
        w_fleet: float = 0.15,
        max_fleet: int = 106,
    ) -> None:
        self.w1 = w_wait
        self.w2 = w_overcrowding
        self.w3 = w_stranded
        self.w4 = w_fleet
        self.max_fleet = max_fleet

    def evaluate(
        self, result: SimulationResult, fleet_used: int | None = None
    ) -> float:
        """
        Computes the utility value U(S) from simulation outputs.

        Args:
            result: SimulationResult containing aggregate KPIs.
            fleet_used: Number of buses required by the schedule. If None, defaults to 106.

        Returns:
            Negative total cost score U(S) (higher / closer to 0 is better).
        """
        breakdown = self.evaluate_breakdown(result, fleet_used=fleet_used)
        return breakdown["utility"]

    def evaluate_breakdown(
        self, result: SimulationResult, fleet_used: int | None = None
    ) -> dict[str, Any]:
        """
        Calculates all component terms of U(S) for detailed analytics and reporting.
        """
        # 1. Waiting time component: W_mean in minutes
        w_mean = max(0.0, result.avg_waiting_time_min)
        w_wait_term = self.w1 * w_mean

        # 2. Overcrowding component: fraction of buses >= 95% capacity
        # scaled so a 20% overcrowding fraction yields balanced magnitude
        overcrowded_ratio = result.overcrowded_bus_pct / 100.0
        overcrowd_scaled = overcrowded_ratio * 10.0
        w_overcrowd_term = self.w2 * (overcrowd_scaled**1.5)

        # 3. Stranded queue component: Q_remanente normalized by 1,000 passengers
        q_remanente = max(0, result.stranded_passengers_in_queue)
        q_norm = q_remanente / 1000.0
        w_stranded_term = self.w3 * q_norm

        # 4. Fleet consumption component: B_usados normalized by B_max = 106
        actual_fleet = fleet_used if fleet_used is not None else 106
        fleet_norm = actual_fleet / float(self.max_fleet)
        w_fleet_term = self.w4 * fleet_norm

        # Hard barrier penalty if physical fleet constraint (106 buses) is violated
        hard_penalty = 0.0
        if actual_fleet > self.max_fleet:
            excess = actual_fleet - self.max_fleet
            hard_penalty = 50.0 * (excess**2)

        total_cost = (
            w_wait_term
            + w_overcrowd_term
            + w_stranded_term
            + w_fleet_term
            + hard_penalty
        )
        utility = -total_cost

        return {
            "utility": round(utility, 4),
            "cost": round(total_cost, 4),
            "w_wait_term": round(w_wait_term, 4),
            "w_overcrowd_term": round(w_overcrowd_term, 4),
            "w_stranded_term": round(w_stranded_term, 4),
            "w_fleet_term": round(w_fleet_term, 4),
            "hard_penalty": round(hard_penalty, 4),
            "w_mean": round(w_mean, 2),
            "overcrowded_pct": round(result.overcrowded_bus_pct, 1),
            "q_remanente": q_remanente,
            "fleet_used": actual_fleet,
        }

    # Backward compatibility alias
    def evaluar(self, res: SimulationResult, fleet_used: int | None = None) -> float:
        return self.evaluate(res, fleet_used=fleet_used)
