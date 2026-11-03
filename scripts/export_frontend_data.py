# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
scripts/export_frontend_data.py
===============================
Transforms raw scenario parquets and simulated telemetry into optimized JSON
assets ready for consumption by the React / Deck.gl web interface.
Exports both:
- Baseline TransMilenio GTFS Scenario (telemetria_base)
- Optimized FlowTM Rational Agent Scenario (telemetria_opt)
- AI Optimization Convergence Log & PEAS frequencies.txt
"""

import json
import shutil
from pathlib import Path

import polars as pl

from flowtm.infrastructure import frontend_payload as payload
from flowtm.simulation.collector import SUMMARY_METRICS_FILENAME
from flowtm.simulation.scenario import CorridorScenario

ROOT_DIR = Path(__file__).resolve().parent.parent
SCENARIO_DIR = ROOT_DIR / "data/scenarios/piloto"
INFRA_DIR = ROOT_DIR / "data/infra_troncal"
OUTPUT_DIR = ROOT_DIR / "frontend/public/data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("EXPORTADOR DE DATOS DEL FRONTEND - GEMELO DIGITAL FlowTM")
print("=" * 80)

# Load official station infrastructure properties if available
official_est_map = {}
if (INFRA_DIR / "estaciones.geojson").exists():
    with open(INFRA_DIR / "estaciones.geojson", encoding="utf-8") as f:
        data = json.load(f)
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            num = str(p.get("num_est", ""))
            if num:
                official_est_map[num] = p

# 1. Enriched Stations
df_stations = pl.read_parquet(SCENARIO_DIR / "estaciones_piloto.parquet").sort(
    "secuencia"
)
stations = []
for row in df_stations.iter_rows(named=True):
    code = str(row["codigo"])
    off_props = official_est_map.get(code, {})
    stations.append(
        {
            "code": code,
            "name": str(row["nombre"]),
            "official_name": off_props.get("nom_est", str(row["nombre"])),
            "sequence": int(row["secuencia"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "distance_next_m": float(row["distancia_siguiente_m"]),
            "travel_time_sec": float(row["tiempo_viaje_seg"]),
            "bays": int(row["bahias"]),
            "ub_est": off_props.get("ub_est"),
            "num_vag": off_props.get("num_vag"),
            "cap_biart": off_props.get("cap_biart"),
            "cap_art": off_props.get("cap_art"),
            "area_est": off_props.get("area_est"),
        }
    )

with open(OUTPUT_DIR / "stations.json", "w", encoding="utf-8") as f:
    json.dump(stations, f, indent=2, ensure_ascii=False)
print(f"[INFO] {len(stations)} estaciones enriquecidas exportadas a stations.json")

# 2. Corridor GeoJSON
features = []
coords = [[s["lon"], s["lat"]] for s in stations]
features.append(
    {
        "type": "Feature",
        "properties": {
            "id": "corridor-trunk-lane",
            "name": "Corredor Troncal Portal Norte - Marly (sentido sur)",
            "stations_count": len(stations),
        },
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
    }
)

for s in stations:
    features.append(
        {
            "type": "Feature",
            "properties": {
                "code": s["code"],
                "name": s["name"],
                "official_name": s["official_name"],
                "sequence": s["sequence"],
                "ub_est": s["ub_est"],
                "num_vag": s["num_vag"],
                "cap_biart": s["cap_biart"],
                "cap_art": s["cap_art"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [s["lon"], s["lat"]],
            },
        }
    )

corridor_geojson = {
    "type": "FeatureCollection",
    "features": features,
}

with open(OUTPUT_DIR / "corridor.geojson", "w", encoding="utf-8") as f:
    json.dump(corridor_geojson, f, indent=2, ensure_ascii=False)
print("[INFO] corridor.geojson exportado")

# 3. Routes configuration (every GTFS service crossing the corridor)
scenario = CorridorScenario.load(SCENARIO_DIR)
ROUTES_CONFIG = [
    {
        "id": service.route,
        "name": f"Ruta {service.route}",
        "service": service.name,
        "color": service.color,
        "role": service.role,
        "counterpart": service.counterpart,
        "headway_min": service.headway_gtfs_min,
        "cycle_time_min": service.cycle_time_min,
        "stops": list(service.stops),
        "stops_count": len(service.stops),
        "capacity": service.capacity,
    }
    for service in scenario.services.values()
]
with open(OUTPUT_DIR / "routes.json", "w", encoding="utf-8") as f:
    json.dump(ROUTES_CONFIG, f, indent=2, ensure_ascii=False)
print(f"[INFO] routes.json exportado ({len(ROUTES_CONFIG)} servicios)")


def process_telemetry_directory(telemetry_dir: Path, suffix: str = ""):
    """Writes trajectory, queue and summary JSON files for one telemetry directory."""
    buses_parquet = telemetry_dir / "telemetria_buses.parquet"
    queues_parquet = telemetry_dir / "historial_colas.parquet"
    if not buses_parquet.exists() or not queues_parquet.exists():
        print(f"[ADVERTENCIA] Se omite {telemetry_dir} (faltan archivos parquet)")
        return

    trajectories = payload.bus_trajectories(pl.read_parquet(buses_parquet).to_dicts())
    traj_filename = f"bus_trajectories{suffix}.json"
    with open(OUTPUT_DIR / traj_filename, "w", encoding="utf-8") as f:
        json.dump(trajectories, f, separators=(",", ":"))
    print(
        f"[INFO] {len(trajectories)} trayectorias de buses exportadas a {traj_filename}"
    )

    queues_df = pl.read_parquet(queues_parquet)
    timeline = payload.queue_timeline(queues_df.to_dicts())
    queues_filename = f"station_queues{suffix}.json"
    with open(OUTPUT_DIR / queues_filename, "w", encoding="utf-8") as f:
        json.dump(timeline, f, separators=(",", ":"))
    print(f"[INFO] {len(timeline)} instantes de colas exportados a {queues_filename}")

    # KPIs come from the simulator run (metricas_resumen.json written by scripts
    # 02/03), never from hardcoded fallbacks.
    metrics_path = telemetry_dir / SUMMARY_METRICS_FILENAME
    if not metrics_path.exists():
        raise SystemExit(
            f"[ERROR] Falta {metrics_path}. Ejecute "
            "scripts/02_correr_simulador_base.py y scripts/03_optimizar_frecuencias.py "
            "antes de exportar."
        )
    run_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    summary = payload.summary_payload(
        run_metrics, int(queues_df["queue_size"].max()), scenario
    )
    summary_filename = f"summary{suffix}.json"
    with open(OUTPUT_DIR / summary_filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[INFO] {summary_filename} exportado")


# 4. Export Baseline Telemetry
process_telemetry_directory(SCENARIO_DIR / "telemetria_base", suffix="")

# 5. Export Optimized Telemetry
process_telemetry_directory(SCENARIO_DIR / "telemetria_opt", suffix="_opt")

# 6. Copy AI Optimization Log and GTFS Exporter
opt_log_src = SCENARIO_DIR / "telemetria_opt/ai_optimization_log.json"
if opt_log_src.exists():
    shutil.copyfile(opt_log_src, OUTPUT_DIR / "ai_optimization_log.json")
    print("[INFO] ai_optimization_log.json exportado a frontend/public")

gtfs_src = SCENARIO_DIR / "telemetria_opt/frequencies.txt"
if gtfs_src.exists():
    shutil.copyfile(gtfs_src, OUTPUT_DIR / "frequencies.txt")
    print("[INFO] frequencies.txt exportado a frontend/public")

print("\n[INFO] Todos los recursos del OCC y del agente se exportaron correctamente.")
