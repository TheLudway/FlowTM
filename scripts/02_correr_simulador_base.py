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

simulator = CorridorSimulator(scenario_dir)
# Current operation: mean AM-peak headways published in the GTFS.
base_state = simulator.scenario.base_schedule()

print(f"[INFO] Intervalos GTFS de las rutas optimizables (min): {base_state.headways}")
print(
    f"[INFO] Servicios de fondo con frecuencia GTFS: "
    f"{', '.join(simulator.scenario.background_routes)}"
)
print(
    f"[INFO] Flota requerida: {base_state.total_fleet_used()} buses "
    f"(cota B_max = {base_state.max_fleet})\n"
)
print("[INFO] Ejecutando simulación de 3 horas de hora pico (06:00 - 09:00 AM)...")

results = simulator.simulate(base_state.headways)

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
print(f"[INFO] Despachos totales           : {results.total_dispatched_buses}")
print(f"[INFO] Retraso medio de despacho   : {results.avg_dispatch_delay_min:.2f} min")
print("=" * 80)

# Export telemetry for OCC Dashboard and visualization layers
telemetry_dir = scenario_dir / "telemetria_base"
simulator.collector.export_telemetry(telemetry_dir)
export_summary_metrics(results, telemetry_dir)

print(
    "[INFO] Telemetría de buses, colas y metricas_resumen.json exportadas para el OCC."
)
