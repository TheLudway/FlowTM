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

import json
from pathlib import Path

from flowtm.simulation.engine import CorridorSimulator

ROOT_DIR = Path(__file__).resolve().parent.parent
scenario_dir = ROOT_DIR / "data/scenarios/piloto"

print("=" * 80)
print("SIMULATION: OFFICIAL BASELINE SCENARIO (TRANSMILENIO PEAK GTFS)")
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

print(f"Dispatch base headways (minutes): {base_headways}\n")
print("Running 3-hour morning peak simulation (06:00 - 09:00 AM)...")

simulator = CorridorSimulator(scenario_dir)
results = simulator.simulate(base_headways, duration_hours=3.0)

print("\n" + "=" * 80)
print("RESULTS: BASELINE SCENARIO (TRANSMILENIO OFFICIAL BENCHMARK)")
print("=" * 80)
print(f"Average waiting time           : {results.avg_waiting_time_min:.2f} minutes")
print(f"Average occupancy rate         : {results.avg_occupancy_rate * 100:.1f}%")
print(
    f"Overcrowded bus percentage     : {results.overcrowded_bus_pct:.1f}% (>= 95% load)"
)
print(f"Total transported passengers   : {results.total_transported_passengers:,}")
print(f"Stranded passengers in queue   : {results.stranded_passengers_in_queue:,}")
print(f"Total dispatched buses         : {results.total_dispatched_buses}")
print("=" * 80)

# Export telemetry for OCC Dashboard and visualization layers
telemetria_dir = scenario_dir / "telemetria_base"
simulator.collector.export_telemetry(telemetria_dir)

# Save exact calibrated benchmark summary metrics
metricas = {
    "avg_waiting_time_min": round(results.avg_waiting_time_min, 2),
    "avg_occupancy_pct": round(results.avg_occupancy_rate * 100, 1),
    "overcrowded_buses_pct": round(results.overcrowded_bus_pct, 1),
    "total_passengers_served": int(results.total_transported_passengers),
    "stranded_passengers_in_queue": int(results.stranded_passengers_in_queue),
    "total_dispatched_buses": int(results.total_dispatched_buses),
}
with open(telemetria_dir / "metricas_resumen.json", "w", encoding="utf-8") as f:
    json.dump(metricas, f, indent=2)

print(
    "Bus and platform queue telemetry + metricas_resumen.json exported for OCC Dashboard."
)
