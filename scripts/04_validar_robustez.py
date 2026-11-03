# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
scripts/04_validar_robustez.py
==============================
Monte Carlo robustness check of the optimized schedule.

The optimizer scores every candidate with a single simulation seed, so its reported
improvement may be partially overfitted to that seed. This script re-simulates the
baseline and optimized headways (read from ai_optimization_log.json) over 30 seeds
and reports the mean wait time, 95% confidence intervals and the paired difference.
"""

import json
import statistics
from pathlib import Path

from flowtm.simulation.engine import CorridorSimulator

ROOT_DIR = Path(__file__).resolve().parent.parent
scenario_dir = ROOT_DIR / "data/scenarios/piloto"
optimization_log_path = scenario_dir / "telemetria_opt/ai_optimization_log.json"

SEEDS = range(42, 72)
# Two-sided 95% Student t critical value for 29 degrees of freedom (n = 30).
T_CRITICAL_95 = 2.045


def confidence_interval(values: list[float]) -> tuple[float, float, float]:
    """Return (mean, lower, upper) of the 95% confidence interval of the mean."""
    mean = statistics.mean(values)
    half_width = T_CRITICAL_95 * statistics.stdev(values) / len(values) ** 0.5
    return mean, mean - half_width, mean + half_width


def simulate_wait_times(headways: dict[str, float]) -> list[float]:
    """Simulate the 06:00-09:00 peak once per seed and collect mean wait times."""
    simulator = CorridorSimulator(scenario_dir)
    return [
        simulator.simulate(headways, seed=seed).avg_waiting_time_min for seed in SEEDS
    ]


print("=" * 80)
print(f"VALIDACIÓN MONTE CARLO: BASE vs OPTIMIZADO ({len(SEEDS)} SEMILLAS)")
print("=" * 80)

optimization_log = json.loads(optimization_log_path.read_text(encoding="utf-8"))
wait_times = {
    scenario: simulate_wait_times(optimization_log[scenario]["headways"])
    for scenario in ("baseline", "optimized")
}

for scenario, label in (("baseline", "Base"), ("optimized", "Optimizado")):
    mean, lower, upper = confidence_interval(wait_times[scenario])
    print(
        f"[INFO] {label:<10}: espera media {mean:.3f} min | "
        f"IC 95% [{lower:.3f}, {upper:.3f}] | "
        f"rango {min(wait_times[scenario]):.3f} - {max(wait_times[scenario]):.3f}"
    )

paired_differences = [
    optimized - baseline
    for optimized, baseline in zip(
        wait_times["optimized"], wait_times["baseline"], strict=True
    )
]
mean_difference, lower, upper = confidence_interval(paired_differences)
relative_change = mean_difference / statistics.mean(wait_times["baseline"]) * 100
wins = sum(difference < 0 for difference in paired_differences)

print(
    f"[INFO] Diferencia pareada (opt - base): {mean_difference:+.3f} min "
    f"({relative_change:+.2f}%) | IC 95% [{lower:+.3f}, {upper:+.3f}]"
)
print(f"[INFO] El horario optimizado reduce la espera en {wins}/{len(SEEDS)} semillas")
if upper < 0:
    print("[INFO] La mejora en espera es estadísticamente significativa (IC < 0).")
else:
    print("[ADVERTENCIA] El IC de la diferencia incluye 0: mejora no concluyente.")
print("=" * 80)
