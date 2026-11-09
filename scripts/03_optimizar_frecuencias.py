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
Rational agent (Simulated Annealing) over the GTFS-grounded corridor scenario.

1. The agent maximizes the expected utility U(S) over 5 *training* seeds
   (common random numbers), subject to the physical fleet bound B_max.
2. The best schedule is validated out of sample on 30 *holdout* seeds that the
   search never saw (paired difference, 95% CI, wins).
3. Exports the optimized telemetry (seed 42, for the OCC replay), the GTFS
   ``frequencies.txt`` actuator and ``ai_optimization_log.json``.
"""

import json
from pathlib import Path

from flowtm.infrastructure.gtfs_exporter import export_gtfs_frequencies
from flowtm.optimization.evaluator import holdout_comparison
from flowtm.optimization.simulated_annealing import (
    DEFAULT_TRAINING_SEEDS,
    SimulatedAnnealingOptimizer,
)
from flowtm.simulation.collector import export_summary_metrics
from flowtm.simulation.engine import CorridorSimulator

ROOT_DIR = Path(__file__).resolve().parent.parent
SCENARIO_DIR = ROOT_DIR / "data/scenarios/piloto"
OPT_TELEMETRY_DIR = SCENARIO_DIR / "telemetria_opt"
BASE_TELEMETRY_DIR = SCENARIO_DIR / "telemetria_base"

BUDGET = 150  # distinct schedule evaluations (x 5 seeds each)
REPLAY_SEED = 42
HOLDOUT_SEEDS = tuple(range(42, 72))


def evaluation_summary(evaluation) -> dict:
    """Expected KPIs of a schedule over the training seeds."""
    metrics = evaluation.metrics
    return {
        "headways": evaluation.headways,
        "fleet_used": evaluation.fleet_used,
        "utility": round(evaluation.utility, 4),
        "utility_se": round(evaluation.standard_error(), 4),
        "breakdown": evaluation.breakdown,
        "wait_time_min": round(metrics["avg_waiting_time_min"], 3),
        "stranded_pax": round(metrics["stranded_passengers_in_queue"]),
        "overcrowded_pct": round(metrics["overcrowded_bus_pct"], 2),
        "transported_pax": round(metrics["total_transported_passengers"]),
        "dispatch_delay_min": round(metrics["avg_dispatch_delay_min"], 3),
    }


def main() -> None:
    print("=" * 80)
    print("OPTIMIZACIÓN: AGENTE RACIONAL (RECOCIDO SIMULADO) - FlowTM")
    print("=" * 80)
    OPT_TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)

    simulator = CorridorSimulator(SCENARIO_DIR)
    scenario = simulator.scenario
    base_state = scenario.base_schedule()
    print(f"[INFO] Horario inicial (GTFS): {base_state.headways}")
    print(f"[INFO] Flota: {base_state.total_fleet_used()}/{base_state.max_fleet} buses")

    # 1. Search on the training seeds.
    optimizer = SimulatedAnnealingOptimizer(
        SCENARIO_DIR, budget=BUDGET, seeds=DEFAULT_TRAINING_SEEDS
    )
    best_state, _ = optimizer.optimize(base_state)
    search = optimizer.result
    assert search is not None

    # 2. Out-of-sample validation on unseen seeds.
    print(f"\n[INFO] Validación fuera de muestra con {len(HOLDOUT_SEEDS)} semillas...")
    holdout = holdout_comparison(SCENARIO_DIR, base_state, best_state, HOLDOUT_SEEDS)

    # 3. Replay telemetry (one seed) for the OCC and the GTFS actuator.
    for state, directory in (
        (base_state, BASE_TELEMETRY_DIR),
        (best_state, OPT_TELEMETRY_DIR),
    ):
        replay = CorridorSimulator(SCENARIO_DIR)
        result = replay.simulate(state.headways, seed=REPLAY_SEED)
        replay.collector.export_telemetry(directory)
        export_summary_metrics(result, directory)
    gtfs_file = export_gtfs_frequencies(
        best_state.headways, OPT_TELEMETRY_DIR / "frequencies.txt"
    )
    print(f"[INFO] Actuador PEAS: horario GTFS exportado en {gtfs_file}")

    log = {
        "algorithm": search.algorithm,
        "config": {
            **search.params,
            "training_seeds": list(DEFAULT_TRAINING_SEEDS),
            "evaluations": search.evaluations,
            "simulations": search.evaluations * len(DEFAULT_TRAINING_SEEDS),
        },
        "baseline": evaluation_summary(search.initial),
        "optimized": evaluation_summary(search.best),
        "delta_utility": round(search.delta_utility, 4),
        "holdout": holdout,
        "max_fleet": base_state.max_fleet,
        "optimizable_routes": scenario.optimizable_routes,
        "background_routes": scenario.background_routes,
        "history": search.history,
    }
    log_path = OPT_TELEMETRY_DIR / "ai_optimization_log.json"
    log_path.write_text(
        json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"[INFO] Historial del agente exportado en: {log_path}")

    # 4. Results table (training expectation and out-of-sample validation).
    wait = holdout["espera_min"]
    utility = holdout["utilidad"]
    print("\n" + "=" * 80)
    print("RESULTADOS: ENTRENAMIENTO (5 SEMILLAS) Y VALIDACIÓN (30 SEMILLAS NUEVAS)")
    print("=" * 80)
    print(f"[INFO] Horario óptimo: {best_state.headways}")
    print(
        f"[INFO] Flota: {search.initial.fleet_used} -> {search.best.fleet_used} (cota {base_state.max_fleet})"
    )
    print(
        f"[INFO] Entrenamiento: U(S) {search.initial.utility:.4f} -> {search.best.utility:.4f} "
        f"(ΔU = {search.delta_utility:+.4f})"
    )
    print(
        f"[INFO] Validación espera: {wait['base']:.3f} -> {wait['candidato']:.3f} min "
        f"({wait['diferencia_pct']:+.2f}%), IC 95% {wait['ic95']}, "
        f"mejor en {wait['semillas_mejor']}/{wait['semillas']} semillas"
    )
    print(
        f"[INFO] Validación utilidad: ΔU = {utility['diferencia']:+.4f}, IC 95% {utility['ic95']}, "
        f"{'significativa' if utility['significativo'] else 'no significativa'}"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
