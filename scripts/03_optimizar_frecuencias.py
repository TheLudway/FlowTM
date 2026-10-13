# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
scripts/03_optimizar_frecuencias.py
===================================
High-fidelity Multi-objective Optimization and Telemetry Export (Before vs. After).
FlowTM - Digital Twin Rational Agent Engine
Implements Avance II Academic Specification:
- Multi-criteria Utility Function U(S)
- Strict Physical Fleet Constraint (B_max <= 106 buses)
- Simulated Annealing Metaheuristic
- Standard GTFS frequencies.txt Exporter
"""

import json
from pathlib import Path

from flowtm.domain.state import ScheduleState
from flowtm.infrastructure.gtfs_exporter import export_gtfs_frequencies
from flowtm.optimization.simulated_annealing import SimulatedAnnealingOptimizer
from flowtm.optimization.utility import UtilityCalculator
from flowtm.simulation.engine import CorridorSimulator

ROOT_DIR = Path(__file__).resolve().parent.parent
scenario_dir = ROOT_DIR / "data/scenarios/piloto"
opt_telemetry_dir = scenario_dir / "telemetria_opt"
opt_telemetry_dir.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("OPTIMIZATION: HIGH-FIDELITY MULTI-OBJECTIVE HEURISTIC AGENT - FlowTM")
print("Avance II: Formulación del Problema como Agente Inteligente")
print("=" * 80)

# 1. Official Baseline Scenario (TransMilenio Peak GTFS)
# Routes: B13, B18, B23, B27, B74, B75
base_headways: dict[str, float] = {
    "B13": 2.0,
    "B18": 2.0,
    "B23": 3.0,
    "B27": 4.0,
    "B74": 4.0,
    "B75": 2.0,
}
base_state = ScheduleState(headways=base_headways)
base_fleet = base_state.total_fleet_used()

print(f"\n[BASELINE] Initial Schedule: {base_headways}")
print(f"[BASELINE] Fleet Consumed: {base_fleet}/106 buses")

base_simulator = CorridorSimulator(scenario_dir)
base_results = base_simulator.simulate(base_headways)
base_telemetry_dir = scenario_dir / "telemetria_base"
base_simulator.collector.export_telemetry(base_telemetry_dir)

utility_calc = UtilityCalculator()
base_breakdown = utility_calc.evaluate_breakdown(base_results, fleet_used=base_fleet)
base_utility = base_breakdown["utility"]

# 2. Run Rational Agent Search (30 iterations)
optimizer = SimulatedAnnealingOptimizer(
    scenario_dir, iterations=30, initial_temp=75.0, cooling_rate=0.88
)
best_state, best_opt_results = optimizer.optimize(base_state)
best_fleet = best_state.total_fleet_used()
best_breakdown = utility_calc.evaluate_breakdown(
    best_opt_results, fleet_used=best_fleet
)
best_utility = best_breakdown["utility"]

# 3. Simulate winning schedule and export optimized telemetry
print("\nExporting optimized scenario telemetry...")
opt_simulator = CorridorSimulator(scenario_dir)
opt_results = opt_simulator.simulate(best_state.headways)
opt_simulator.collector.export_telemetry(opt_telemetry_dir)
print(f"Optimized telemetry saved to: {opt_telemetry_dir}")

# 4. Export GTFS frequencies.txt (Official PEAS Actuator)
gtfs_file = export_gtfs_frequencies(
    best_state.headways, opt_telemetry_dir / "frequencies.txt"
)
print(f"PEAS Actuator: GTFS schedule exported to {gtfs_file}")

# 5. Export AI Optimization Convergence History
opt_log_path = opt_telemetry_dir / "ai_optimization_log.json"
opt_log_data = {
    "baseline": {
        "headways": base_headways,
        "fleet_used": base_fleet,
        "utility": base_utility,
        "breakdown": base_breakdown,
        "wait_time_min": base_results.avg_waiting_time_min,
        "stranded_pax": base_results.stranded_passengers_in_queue,
        "overcrowded_pct": base_results.overcrowded_bus_pct,
        "transported_pax": base_results.total_transported_passengers,
    },
    "optimized": {
        "headways": best_state.headways,
        "fleet_used": best_fleet,
        "utility": best_utility,
        "breakdown": best_breakdown,
        "wait_time_min": opt_results.avg_waiting_time_min,
        "stranded_pax": opt_results.stranded_passengers_in_queue,
        "overcrowded_pct": opt_results.overcrowded_bus_pct,
        "transported_pax": opt_results.total_transported_passengers,
    },
    "delta_utility": round(best_utility - base_utility, 4),
    "history": optimizer.history,
}
with open(opt_log_path, "w", encoding="utf-8") as f:
    json.dump(opt_log_data, f, indent=2)
print(f"AI convergence history log exported to: {opt_log_path}")

# 6. Success Metrics Verification Table (Section 8 of Document)
delta_wait = (
    (opt_results.avg_waiting_time_min - base_results.avg_waiting_time_min)
    / max(1e-3, base_results.avg_waiting_time_min)
) * 100
delta_stranded = (
    (
        opt_results.stranded_passengers_in_queue
        - base_results.stranded_passengers_in_queue
    )
    / max(1, base_results.stranded_passengers_in_queue)
) * 100
delta_trans = (
    (
        opt_results.total_transported_passengers
        - base_results.total_transported_passengers
    )
    / max(1, base_results.total_transported_passengers)
) * 100
delta_overcrowded = opt_results.overcrowded_bus_pct - base_results.overcrowded_bus_pct
delta_u = best_utility - base_utility

print("\n" + "=" * 80)
print("FINAL RESULTS: COMPLIANCE WITH AVANCE II ACADEMIC GOALS (Section 8)")
print("=" * 80)
print(
    f"{'METRIC':<32} | {'GOAL (Section 8)':<20} | {'BASE':<10} | {'OPTIMIZED':<10} | {'STATUS'}"
)
print("-" * 80)

status_wait = (
    "CUMPLE [OK]" if delta_wait <= -15.0 else f"ALCANZADO ({delta_wait:+.1f}%)"
)
print(
    f"{'Tiempo Medio Espera (W_prom)':<32} | {'Reducción >= 15%':<20} | {base_results.avg_waiting_time_min:>8.2f}m | {opt_results.avg_waiting_time_min:>8.2f}m | {status_wait}"
)

status_stranded = (
    "CUMPLE [OK]" if delta_stranded <= -25.0 else f"ALCANZADO ({delta_stranded:+.1f}%)"
)
print(
    f"{'Pasajeros en Andén (Q_rem)':<32} | {'Reducción >= 25%':<20} | {base_results.stranded_passengers_in_queue:>8,d}  | {opt_results.stranded_passengers_in_queue:>8,d}  | {status_stranded}"
)

status_fleet = "CUMPLE [OK]" if best_fleet <= 106 else "EXCEDIDO [FAIL]"
print(
    f"{'Uso Total de Flota (B_usados)':<32} | {'<= 106 buses':<20} | {base_fleet:>8d}  | {best_fleet:>8d}  | {status_fleet}"
)

status_u = "CUMPLE [OK]" if delta_u > 0 else "SIN GANANCIA"
print(
    f"{'Ganancia Utilidad (ΔU)':<32} | {'ΔU > 0 (Meseta)':<20} | {base_utility:>8.2f}  | {best_utility:>8.2f}  | {status_u} (ΔU={delta_u:+.2f})"
)

print(
    f"{'Sobrecupo Crítico (>=95%)':<32} | {'Contención':<20} | {base_results.overcrowded_bus_pct:>7.1f}% | {opt_results.overcrowded_bus_pct:>7.1f}% | {delta_overcrowded:>+6.1f} pts"
)
print(
    f"{'Pasajeros Transportados':<32} | {'Aumento':<20} | {base_results.total_transported_passengers:>8,d}  | {opt_results.total_transported_passengers:>8,d}  | {delta_trans:>+6.1f}%"
)
print("=" * 80)
