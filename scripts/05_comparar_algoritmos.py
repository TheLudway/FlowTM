# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
scripts/05_comparar_algoritmos.py
=================================
Controlled experiment: is Simulated Annealing better than simpler agents?

Random search, hill climbing and simulated annealing run with the *same budget*
of distinct schedule evaluations and the same training seeds, several times each
(different search seeds). Every best schedule is then validated on 30 holdout
seeds. Results are written to ``comparacion_algoritmos.json`` (scenario and
frontend) for the OCC analytics view.
"""

import json
import statistics
import time
from pathlib import Path

from flowtm.optimization.evaluator import ScheduleEvaluator, holdout_comparison
from flowtm.optimization.search import ALGORITHMS
from flowtm.optimization.simulated_annealing import DEFAULT_TRAINING_SEEDS
from flowtm.simulation.scenario import CorridorScenario

ROOT_DIR = Path(__file__).resolve().parent.parent
SCENARIO_DIR = ROOT_DIR / "data/scenarios/piloto"
OUTPUT_FILES = (
    SCENARIO_DIR / "telemetria_opt/comparacion_algoritmos.json",
    ROOT_DIR / "frontend/public/data/comparacion_algoritmos.json",
)

BUDGET = 100
RUN_SEEDS = (1, 2, 3)
HOLDOUT_SEEDS = tuple(range(42, 72))
STEP_MIN = 0.5


def main() -> None:
    print("=" * 80)
    print("EXPERIMENTO: BÚSQUEDA ALEATORIA vs HILL CLIMBING vs RECOCIDO SIMULADO")
    print("=" * 80)
    base_state = CorridorScenario.load(SCENARIO_DIR).base_schedule()
    print(
        f"[INFO] Presupuesto: {BUDGET} evaluaciones x {len(DEFAULT_TRAINING_SEEDS)} semillas "
        f"| {len(RUN_SEEDS)} corridas por algoritmo | validación: {len(HOLDOUT_SEEDS)} semillas"
    )

    runs = []
    for name, algorithm in ALGORITHMS.items():
        for run_seed in RUN_SEEDS:
            started = time.time()
            # A fresh evaluator per run: the cache must not leak between runs.
            with ScheduleEvaluator(SCENARIO_DIR, DEFAULT_TRAINING_SEEDS) as evaluator:
                kwargs = {"budget": BUDGET, "seed": run_seed}
                if name != "busqueda_aleatoria":
                    kwargs["step_min"] = STEP_MIN
                result = algorithm(evaluator, base_state, **kwargs)
            holdout = holdout_comparison(
                SCENARIO_DIR, base_state, result.best_state, HOLDOUT_SEEDS
            )
            curve = [entry["best_utility"] for entry in result.history]
            runs.append(
                {
                    "algoritmo": name,
                    "semilla_busqueda": run_seed,
                    "evaluaciones": result.evaluations,
                    "segundos": round(time.time() - started, 1),
                    "mejor_horario": result.best.headways,
                    "flota": result.best.fleet_used,
                    "delta_u_entrenamiento": round(result.delta_utility, 4),
                    "holdout": holdout,
                    "curva_mejor_utilidad": curve,
                }
            )
            print(
                f"[INFO] {name:<19} corrida {run_seed}: ΔU entrenamiento "
                f"{result.delta_utility:+.4f} | ΔU validación "
                f"{holdout['utilidad']['diferencia']:+.4f} "
                f"(IC {holdout['utilidad']['ic95']}) | espera "
                f"{holdout['espera_min']['diferencia_pct']:+.2f}% | flota {result.best.fleet_used}"
            )

    summary = {}
    for name in ALGORITHMS:
        algorithm_runs = [r for r in runs if r["algoritmo"] == name]
        holdout_deltas = [
            r["holdout"]["utilidad"]["diferencia"] for r in algorithm_runs
        ]
        summary[name] = {
            "delta_u_validacion_media": round(statistics.fmean(holdout_deltas), 4),
            "delta_u_validacion_min": round(min(holdout_deltas), 4),
            "delta_u_validacion_max": round(max(holdout_deltas), 4),
            "corridas_significativas": sum(
                r["holdout"]["utilidad"]["significativo"] for r in algorithm_runs
            ),
            "espera_pct_media": round(
                statistics.fmean(
                    r["holdout"]["espera_min"]["diferencia_pct"] for r in algorithm_runs
                ),
                2,
            ),
            "sobrecupo_pct_media": round(
                statistics.fmean(
                    r["holdout"]["sobrecupo_pct"]["diferencia_pct"]
                    for r in algorithm_runs
                ),
                2,
            ),
        }

    report = {
        "presupuesto_evaluaciones": BUDGET,
        "semillas_entrenamiento": list(DEFAULT_TRAINING_SEEDS),
        "semillas_validacion": len(HOLDOUT_SEEDS),
        "corridas_por_algoritmo": len(RUN_SEEDS),
        "resumen": summary,
        "corridas": runs,
    }
    for path in OUTPUT_FILES:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print("\n" + "=" * 80)
    print("RESUMEN (validación fuera de muestra, media de las corridas)")
    print("=" * 80)
    for name, values in summary.items():
        print(
            f"[INFO] {name:<19} ΔU {values['delta_u_validacion_media']:+.4f} "
            f"[{values['delta_u_validacion_min']:+.4f}, {values['delta_u_validacion_max']:+.4f}] | "
            f"significativas {values['corridas_significativas']}/{len(RUN_SEEDS)} | "
            f"espera {values['espera_pct_media']:+.2f}% | sobrecupo {values['sobrecupo_pct_media']:+.2f}%"
        )
    print("=" * 80)


if __name__ == "__main__":
    main()
