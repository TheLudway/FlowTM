# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
scripts/02_correr_simulador_base.py
===================================
Executes the baseline scenario simulation using TransMilenio GTFS peak dispatch headways.
FlowTM - Digital Twin Engine
"""

from pathlib import Path

from flowtm.simulation.collector import export_summary_metrics
from flowtm.simulation.engine import CorridorSimulator

ROOT_DIR = Path(__file__).resolve().parent.parent
scenario_dir = ROOT_DIR / "data/scenarios/piloto"

print("=" * 80)
print("SIMULACIÓN: ESCENARIO BASE OFICIAL (GTFS HORA PICO TRANSMILENIO)")
print("=" * 80)

# Reference: Official TransMilenio GTFS schedule for morning peak hour (06:00 - 09:00 AM)
# Computed from data/processed/gtfs/gtfs_20260727 trip frequency analysis.
base_headways: dict[str, float] = {
    "B13": 2.0,  # Express Tunal -> Portal Norte (GTFS ~1.96 min)
    "B18": 2.0,  # Express 20 de Julio -> Terminal (GTFS ~1.82 min)
    "B23": 3.0,  # Express Eldorado -> Alcala (GTFS ~2.95 min)
    "B27": 4.0,  # Express Tunal -> Portal Norte (GTFS ~3.91 min)
    "B74": 4.0,  # Express Universidades -> Portal Norte (GTFS ~4.09 min)
    "B75": 2.0,  # Express Usme -> Portal Norte (GTFS ~1.54 min)
}

print(f"[INFO] Intervalos base de despacho (minutos): {base_headways}\n")
print("[INFO] Ejecutando simulación de 3 horas de hora pico (06:00 - 09:00 AM)...")

simulator = CorridorSimulator(scenario_dir)
results = simulator.simulate(base_headways, duration_hours=3.0)

print("\n" + "=" * 80)
print("RESULTADOS: ESCENARIO BASE (REFERENCIA OFICIAL TRANSMILENIO)")
print("=" * 80)
print(
    f"[INFO] Tiempo medio de espera      : {results.avg_waiting_time_min:.2f} minutos"
)
print(f"[INFO] Ocupación promedio          : {results.avg_occupancy_rate * 100:.1f}%")
print(
    f"[INFO] Buses con sobrecupo         : {results.overcrowded_bus_pct:.1f}% (>= 95% de carga)"
)
print(f"[INFO] Pasajeros transportados     : {results.total_transported_passengers:,}")
print(f"[INFO] Pasajeros varados en andén  : {results.stranded_passengers_in_queue:,}")
print(f"[INFO] Despachos totales          : {results.total_dispatched_buses}")
print("=" * 80)

# Export telemetry for OCC Dashboard and visualization layers
telemetry_dir = scenario_dir / "telemetria_base"
simulator.collector.export_telemetry(telemetry_dir)
export_summary_metrics(results, telemetry_dir)

print(
    "[INFO] Telemetría de buses, colas y metricas_resumen.json exportadas para el OCC."
)
