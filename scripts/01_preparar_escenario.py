# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
scripts/01_preparar_escenario.py
================================
Extracts full-day dynamic arrival rates (04:00 to 23:00) and metric distances
for the Autopista Norte - Caracas pilot trunk corridor.
"""

import math
from pathlib import Path

import polars as pl

# 1. Project directories with canonical clean Parquet inputs
ROOT_DIR = Path(__file__).resolve().parent.parent
clean_val_dir = ROOT_DIR / "data/processed/validaciones_salidas/validacion_troncal"
clean_sal_dir = ROOT_DIR / "data/processed/validaciones_salidas/salidas_troncal"
scenario_dir = ROOT_DIR / "data/scenarios/piloto"
scenario_dir.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("EXTRACTOR: FULL DAY DEMAND (04:00 - 23:00) AND GEODETIC TOPOLOGY - FlowTM")
print("=" * 80)

# 2. Topology and Real Metric Distances from Infrastructure Coordinates
STATIONS_GEO = [
    {
        "codigo": "02000",
        "nombre": "PORTAL NORTE",
        "secuencia": 1,
        "lat": 4.754623,
        "lon": -74.046045,
    },
    {
        "codigo": "02101",
        "nombre": "TOBERIN",
        "secuencia": 2,
        "lat": 4.746185,
        "lon": -74.047255,
    },
    {
        "codigo": "02102",
        "nombre": "CALLE 161",
        "secuencia": 3,
        "lat": 4.741915,
        "lon": -74.048000,
    },
    {
        "codigo": "02103",
        "nombre": "MAZUREN",
        "secuencia": 4,
        "lat": 4.734589,
        "lon": -74.049226,
    },
    {
        "codigo": "02104",
        "nombre": "CALLE 146",
        "secuencia": 5,
        "lat": 4.730891,
        "lon": -74.049811,
    },
    {
        "codigo": "02200",
        "nombre": "ALCALA",
        "secuencia": 6,
        "lat": 4.721158,
        "lon": -74.051459,
    },
    {
        "codigo": "02201",
        "nombre": "PRADO",
        "secuencia": 7,
        "lat": 4.714558,
        "lon": -74.052558,
    },
    {
        "codigo": "02204",
        "nombre": "PEPE SIERRA",
        "secuencia": 8,
        "lat": 4.698127,
        "lon": -74.055309,
    },
    {
        "codigo": "02205",
        "nombre": "CALLE 106",
        "secuencia": 9,
        "lat": 4.692983,
        "lon": -74.056182,
    },
    {
        "codigo": "02300",
        "nombre": "CALLE 100",
        "secuencia": 10,
        "lat": 4.683949,
        "lon": -74.057712,
    },
    {
        "codigo": "02302",
        "nombre": "VIRREY",
        "secuencia": 11,
        "lat": 4.675997,
        "lon": -74.059020,
    },
    {
        "codigo": "02303",
        "nombre": "CALLE 85",
        "secuencia": 12,
        "lat": 4.672313,
        "lon": -74.059644,
    },
    {
        "codigo": "02304",
        "nombre": "HEROES",
        "secuencia": 13,
        "lat": 4.668136,
        "lon": -74.060310,
    },
    {
        "codigo": "09122",
        "nombre": "CALLE 72",
        "secuencia": 14,
        "lat": 4.658238,
        "lon": -74.062068,
    },
    {
        "codigo": "09127",
        "nombre": "FLORES",
        "secuencia": 15,
        "lat": 4.652761,
        "lon": -74.063996,
    },
    {
        "codigo": "09120",
        "nombre": "CALLE 63",
        "secuencia": 16,
        "lat": 4.648404,
        "lon": -74.064871,
    },
    {
        "codigo": "09117",
        "nombre": "CALLE 45",
        "secuencia": 17,
        "lat": 4.631452,
        "lon": -74.067879,
    },
]


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in meters."""
    r_earth = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r_earth * math.atan2(math.sqrt(a), math.sqrt(1 - a))


for i in range(len(STATIONS_GEO)):
    if i < len(STATIONS_GEO) - 1:
        d = haversine_distance_m(
            STATIONS_GEO[i]["lat"],
            STATIONS_GEO[i]["lon"],
            STATIONS_GEO[i + 1]["lat"],
            STATIONS_GEO[i + 1]["lon"],
        )
        STATIONS_GEO[i]["distancia_siguiente_m"] = round(d, 1)
        STATIONS_GEO[i]["tiempo_viaje_seg"] = round((d / 6.11) + 15.0, 1)
    else:
        STATIONS_GEO[i]["distancia_siguiente_m"] = 0.0
        STATIONS_GEO[i]["tiempo_viaje_seg"] = 0.0

df_topo = pl.DataFrame(STATIONS_GEO)
df_topo.write_parquet(scenario_dir / "estaciones_piloto.parquet")

# 3. Dynamic Demand (04:00 to 23:00) with Weekdays filter and Corridor Offer Factor alpha = 0.25
pattern_val = str(clean_val_dir / "*_clean.parquet")
corridor_station_codes = [e["codigo"] for e in STATIONS_GEO]
# Calibrated Demand Factor: 1.00 captures full empirical turnstile validations matching 140 buses/hr GTFS trunk dispatch
CORRIDOR_OFFER_FACTOR = 1.00

lazy_val = (
    pl.scan_parquet(pattern_val)
    .filter(pl.col("Day_Group_Type") == "Dia 1")
    .filter(pl.col("CODIGO_ESTACION").is_in(corridor_station_codes))
    .with_columns(
        [
            pl.col("Fecha_Transaccion").dt.date().alias("fecha"),
            pl.col("Fecha_Transaccion").dt.hour().alias("hora"),
            (pl.col("Fecha_Transaccion").dt.minute() // 15 * 15).alias("minuto"),
        ]
    )
    .filter((pl.col("hora") >= 4) & (pl.col("hora") < 23))
)

# Count distinct weekdays in the clean dataset to compute average daily demand
n_weekdays = max(1, lazy_val.select(pl.col("fecha").n_unique()).collect().item())

df_demand_day = (
    lazy_val.group_by(["CODIGO_ESTACION", "hora", "minuto"])
    .agg(pl.len().alias("total_validaciones_periodo"))
    .with_columns(
        [
            (pl.col("total_validaciones_periodo") / n_weekdays).alias(
                "pasajeros_15m_totales"
            ),
            (
                (pl.col("total_validaciones_periodo") / n_weekdays)
                * CORRIDOR_OFFER_FACTOR
            ).alias("pasajeros_15m_rutas"),
            (
                (
                    (pl.col("total_validaciones_periodo") / n_weekdays)
                    * CORRIDOR_OFFER_FACTOR
                )
                / 900.0
            ).alias("lambda_segundo"),
            pl.col("hora").cast(pl.Int8).alias("hora_del_dia"),
            pl.datetime(2026, 8, 24, pl.col("hora"), pl.col("minuto"), 0).alias(
                "franja_15m"
            ),
        ]
    )
    .sort(["franja_15m", "CODIGO_ESTACION"])
    .collect()
)
df_demand_day.write_parquet(scenario_dir / "demanda_lambda_dia_completo.parquet")

# 4. Calibrated Alighting Attraction Weights from clean tap-out telemetry
pattern_sal = str(clean_sal_dir / "*_clean.parquet")
df_alightings = (
    pl.scan_parquet(pattern_sal)
    .filter(pl.col("CODIGO_ESTACION").is_in(corridor_station_codes))
    .group_by("CODIGO_ESTACION")
    .agg(pl.col("Salidas_S").sum().alias("total_salidas"))
    .collect()
)

total_alightings = max(1, df_alightings["total_salidas"].sum())
df_weights = df_alightings.with_columns(
    res_peso=(pl.col("total_salidas") / total_alightings)
).select(["CODIGO_ESTACION", pl.col("res_peso").alias("peso_atraccion")])
df_weights.write_parquet(scenario_dir / "pesos_descenso.parquet")

print(f"[SUCCESS] Corridor topology saved: {len(STATIONS_GEO)} stations included.")
print(f"[SUCCESS] Demand generated for weekdays: {len(df_demand_day)} time bins.")
print("[SUCCESS] Alighting attraction weights calibrated from clean tap-out data.")
print("=" * 80)
