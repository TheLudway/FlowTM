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
Builds the pilot scenario (Portal Norte -> Marly, southbound, weekday AM peak)
exclusively from TransMilenio open data:

* Supply  (GTFS): corridor topology, segment running times, trunk services with
  their real stop patterns, mean peak headways and cycle times.
* Demand (fare system): arrival rates per station and 15-minute window from
  ``validacion_troncal/*_clean.parquet``, split by direction with AM exits from
  ``salidas_troncal/*_clean.parquet`` (gravity model on observed exits).

Outputs (data/scenarios/piloto/):
    estaciones_piloto.parquet, demanda_lambda_dia_completo.parquet,
    pesos_descenso.parquet, servicios_corredor.parquet, escenario.json
"""

import json
import math
from pathlib import Path

import polars as pl

from flowtm.infrastructure import gtfs_corridor as gc
from flowtm.simulation.scenario import SOUTH_SINK_CODE

ROOT_DIR = Path(__file__).resolve().parent.parent
GTFS_SNAPSHOT = "gtfs_20260727"
GTFS_DIR = ROOT_DIR / "data/processed/gtfs" / GTFS_SNAPSHOT
VALIDATIONS_DIR = ROOT_DIR / "data/processed/validaciones_salidas/validacion_troncal"
EXITS_DIR = ROOT_DIR / "data/processed/validaciones_salidas/salidas_troncal"
SCENARIO_DIR = ROOT_DIR / "data/scenarios/piloto"
INFRA_STATIONS_FILE = ROOT_DIR / "data/processed/infra_troncal/estaciones.geojson"

NORTH_BOUNDARY = "02000"  # Portal Norte
SOUTH_BOUNDARY = "09118"  # Marly: last operating station before closed Calle 45
DIRECTION = "N->S"
PEAK_START_SEC = 6 * 3600
PEAK_END_SEC = 9 * 3600
DEMAND_START_HOUR = 4
DEMAND_END_HOUR = 23
# Southbound counterparts of the six Avance II services (B13, B18, B23, B27, B74, B75).
OPTIMIZED_ROUTES = ("H13", "H75", "H27", "J74", "K23", "L18")
# No vehicle-type data is published per route; articulated capacity is assumed.
BUS_CAPACITY_PAX = 160


def weekday_fare_scan(directory: Path) -> pl.LazyFrame:
    """Clean fare-system records restricted to weekdays (Monday-Friday)."""
    return pl.scan_parquet(directory / "*_clean.parquet").filter(
        pl.col("Fecha_Transaccion").dt.weekday() <= 5
    )


def fare_code_aliases(
    stations: pl.DataFrame, fare_names: pl.DataFrame
) -> dict[str, str]:
    """
    Map each GTFS station code to the code used by the fare system.

    During the 2026 works, several Caracas stations operate as temporary stations
    with their own fare codes (e.g. GTFS 09121 Flores <-> fare 09127 TEMPORAL
    FLORES). Codes present in the fare data map to themselves; the rest are
    matched by normalized station name.
    """
    fare_codes = set(fare_names["CODIGO_ESTACION"].to_list())
    by_name = {
        gc.normalize_station_name(name): code for code, name in fare_names.iter_rows()
    }
    aliases: dict[str, str] = {}
    for code, name in stations.select("codigo", "nombre_gtfs").iter_rows():
        if code in fare_codes:
            aliases[code] = code
        elif (match := by_name.get(gc.normalize_station_name(name))) is not None:
            aliases[code] = match
    return aliases


print("=" * 80)
print("ESCENARIO PILOTO: PORTAL NORTE -> MARLY (SENTIDO SUR, PICO AM) - FlowTM")
print("=" * 80)
SCENARIO_DIR.mkdir(parents=True, exist_ok=True)

# 1. Supply from GTFS ----------------------------------------------------------
feed = gc.load_gtfs(GTFS_DIR)
events = gc.trunk_stop_events(feed)
topology = gc.corridor_topology(feed, events, NORTH_BOUNDARY, SOUTH_BOUNDARY)
passages = gc.corridor_passages(events, topology)
topology = topology.with_columns(
    pl.Series("tiempo_viaje_seg", gc.segment_running_times(passages, topology))
)

# Stopping positions per station: official wagon count (infraestructura troncal),
# or the GTFS platforms used southbound when larger (portals).
infra_stations = json.loads(INFRA_STATIONS_FILE.read_text(encoding="utf-8"))["features"]
wagons = {
    str(f["properties"]["num_est"]): int(f["properties"]["num_vag"] or 0)
    for f in infra_stations
}
platforms = gc.platform_counts(events, passages, DIRECTION)
topology = topology.with_columns(
    pl.col("codigo")
    .map_elements(
        lambda code: max(1, wagons.get(code, 0), platforms.get(code, 0)),
        return_dtype=pl.Int64,
    )
    .alias("bahias")
)
services = gc.peak_services(passages, DIRECTION, PEAK_START_SEC, PEAK_END_SEC)
northbound_routes = gc.peak_services(passages, "S->N", PEAK_START_SEC, PEAK_END_SEC)[
    "route_short_name"
].to_list()

missing = sorted(set(OPTIMIZED_ROUTES) - set(services["route_short_name"]))
if missing:
    raise SystemExit(f"[ERROR] Rutas optimizables sin viajes en el GTFS: {missing}")

PEAK_WINDOW = (PEAK_START_SEC, PEAK_END_SEC)
service_rows = []
for row in services.iter_rows(named=True):
    route = row["route_short_name"]
    counterpart = gc.counterpart_route(route, northbound_routes)
    # Fleet per direction (Little's law) with AM-peak trip times and headways:
    # the optimized leg is the southbound route, the return leg keeps its GTFS
    # headway. Trips of both legs run the whole route, not only the corridor.
    outbound_min = gc.route_trip_minutes(events, route, PEAK_WINDOW)
    return_min = (
        gc.route_trip_minutes(events, counterpart, PEAK_WINDOW) if counterpart else None
    )
    return_headway = (
        gc.route_headway_minutes(events, counterpart, PEAK_WINDOW)
        if counterpart
        else None
    )
    return_fleet = (
        gc.leg_fleet(return_min, return_headway)
        if return_min is not None and return_headway is not None
        else 0
    )
    service_rows.append(
        {
            "ruta": route,
            "nombre": row["route_long_name"],
            "color": f"#{row['route_color']}" if row["route_color"] else "#9E9E9E",
            "rol": "optimizable" if route in OPTIMIZED_ROUTES else "fondo",
            "paradas": row["paradas"],
            "headway_gtfs_min": row["headway_gtfs_min"],
            "viajes_pico": row["viajes_pico"],
            "recorrido_corredor_min": round(row["recorrido_corredor_min"], 1),
            "tiempo_ciclo_min": gc.cycle_time_minutes(
                events, route, counterpart, PEAK_WINDOW
            ),
            "duracion_ida_min": round(outbound_min or 0.0, 1),
            "duracion_regreso_min": round(return_min or 0.0, 1),
            "headway_regreso_min": round(return_headway or 0.0, 2),
            "tiempo_tramo_min": round(
                (outbound_min or 0.0) + gc.TERMINAL_LAYOVER_MIN, 1
            ),
            "flota_regreso": return_fleet,
            "contraparte": counterpart,
            "continua_al_salir": row["continua_al_salir"],
            "capacidad": BUS_CAPACITY_PAX,
        }
    )
services_df = pl.DataFrame(service_rows)
print(
    f"[INFO] Topología GTFS: {topology.height} estaciones operativas | "
    f"{services_df.height} servicios troncales hacia el sur en el pico"
)

# 2. Fare-code aliases (temporary stations) ------------------------------------
fare_names = (
    weekday_fare_scan(EXITS_DIR)
    .select("CODIGO_ESTACION", "NOMBRE_ESTACION_CANONICO")
    .unique(subset="CODIGO_ESTACION")
    .collect()
)
all_gtfs_stations = feed.stops.filter(pl.col("location_type") == 1).select(
    pl.col("stop_id").str.zfill(5).alias("codigo"),
    pl.col("stop_name").alias("nombre_gtfs"),
)
aliases = fare_code_aliases(all_gtfs_stations, fare_names)
corridor_codes = topology["codigo"].to_list()
unmatched = [c for c in corridor_codes if c not in aliases]
if unmatched:
    raise SystemExit(
        f"[ERROR] Estaciones del corredor sin datos de recaudo: {unmatched}"
    )
topology = topology.with_columns(
    pl.col("codigo").replace_strict(aliases).alias("codigo_recaudo")
)
for code in corridor_codes:
    if aliases[code] != code:
        print(f"[INFO] Estación temporal: GTFS {code} <-> recaudo {aliases[code]}")

# 3. Destination attraction from AM exits (gravity weights) --------------------
am_exits = (
    weekday_fare_scan(EXITS_DIR)
    .with_columns(pl.col("Tiempo").str.slice(0, 2).cast(pl.Int32).alias("hora"))
    .filter((pl.col("hora") >= 6) & (pl.col("hora") < 9))
    .group_by("CODIGO_ESTACION")
    .agg(pl.col("Salidas_S").sum().alias("salidas"))
    .collect()
)
exit_days = (
    weekday_fare_scan(EXITS_DIR)
    .select(pl.col("Fecha_Transaccion").dt.date().n_unique())
    .collect()
    .item()
)
exits_by_fare_code = dict(am_exits.iter_rows())


def am_exits_per_day(gtfs_codes: list[str]) -> float:
    """Average weekday AM exits over a set of GTFS stations."""
    fare_codes = {aliases[c] for c in gtfs_codes if c in aliases}
    return sum(exits_by_fare_code.get(c, 0) for c in fare_codes) / max(1, exit_days)


corridor_weights = [am_exits_per_day([c]) for c in corridor_codes]
south_sink_weight = am_exits_per_day(
    [
        c
        for c in gc.stations_after_corridor(events, passages, "N->S")
        if c not in corridor_codes
    ]
)
north_sink_weight = am_exits_per_day(
    [
        c
        for c in gc.stations_after_corridor(events, passages, "S->N")
        if c not in corridor_codes
    ]
)

# Share of each station's boardings travelling southbound:
# downstream attraction / (downstream + upstream attraction).
southbound_share = []
for index in range(len(corridor_codes)):
    downstream = sum(corridor_weights[index + 1 :]) + south_sink_weight
    upstream = sum(corridor_weights[:index]) + north_sink_weight
    southbound_share.append(round(downstream / max(1e-9, downstream + upstream), 4))
topology = topology.with_columns(pl.Series("cuota_sur", southbound_share))

weights_df = pl.DataFrame(
    {
        "CODIGO_ESTACION": [*corridor_codes, SOUTH_SINK_CODE],
        "peso_atraccion": [*corridor_weights, south_sink_weight],
    }
).with_columns(pl.col("peso_atraccion") / pl.col("peso_atraccion").sum())

# 4. Arrival rates lambda(s, t) from validations --------------------------------
fare_to_gtfs = {aliases[c]: c for c in corridor_codes}
share_by_code = dict(zip(corridor_codes, southbound_share, strict=True))
validations = (
    weekday_fare_scan(VALIDATIONS_DIR)
    .filter(pl.col("CODIGO_ESTACION").is_in(list(fare_to_gtfs)))
    .with_columns(
        pl.col("Fecha_Transaccion").dt.date().alias("fecha"),
        pl.col("Fecha_Transaccion").dt.hour().alias("hora"),
        (pl.col("Fecha_Transaccion").dt.minute() // 15 * 15).alias("minuto"),
    )
    .filter((pl.col("hora") >= DEMAND_START_HOUR) & (pl.col("hora") < DEMAND_END_HOUR))
)
validation_days = validations.select(pl.col("fecha").n_unique()).collect().item()
demand = (
    validations.group_by(["CODIGO_ESTACION", "hora", "minuto"])
    .agg(pl.len().alias("validaciones_periodo"))
    .collect()
    .with_columns(
        pl.col("CODIGO_ESTACION").replace_strict(fare_to_gtfs),
        (pl.col("validaciones_periodo") / validation_days).alias("validaciones_15m"),
    )
    .with_columns(
        pl.col("CODIGO_ESTACION").replace_strict(share_by_code).alias("cuota_sur"),
        (pl.col("validaciones_15m") / 900.0).alias("lambda_total_segundo"),
        pl.col("hora").cast(pl.Int8).alias("hora_del_dia"),
        pl.datetime(2026, 8, 24, pl.col("hora"), pl.col("minuto"), 0).alias(
            "franja_15m"
        ),
    )
    .with_columns(
        (pl.col("lambda_total_segundo") * pl.col("cuota_sur")).alias("lambda_segundo")
    )
    .sort(["franja_15m", "CODIGO_ESTACION"])
)

# 5. Fleet bound: buses TransMilenio assigns today to the optimizable routes -----
optimizable = services_df.filter(pl.col("rol") == "optimizable")
base_fleet = sum(
    math.ceil(leg / headway) + fixed
    for leg, headway, fixed in optimizable.select(
        "tiempo_tramo_min", "headway_gtfs_min", "flota_regreso"
    ).iter_rows()
)

# Independent check of B_max: trips of the optimizable routes and their return
# routes simultaneously in service (GTFS), plus vehicles in terminal layover.
pair_routes = [
    *optimizable["ruta"].to_list(),
    *[c for c in optimizable["contraparte"].to_list() if c],
]
in_service = gc.trips_in_service(events, pair_routes, PEAK_WINDOW)
layover_vehicles = sum(
    gc.TERMINAL_LAYOVER_MIN / h
    for h in [*optimizable["headway_gtfs_min"], *optimizable["headway_regreso_min"]]
    if h
)
fleet_check = {
    "en_servicio_promedio": round(sum(in_service) / len(in_service), 1),
    "en_servicio_pico": max(in_service),
    "en_regulacion_estimado": round(layover_vehicles, 1),
}
print(
    f"[INFO] Validación de B_max con el GTFS: {fleet_check['en_servicio_pico']} buses en "
    f"viaje en el instante pico + ~{layover_vehicles:.0f} en regulación "
    f"(promedio 06-09h: {fleet_check['en_servicio_promedio']:.0f} en viaje)"
)

# 6. Persist --------------------------------------------------------------------
topology.select(
    "codigo",
    "nombre",
    "secuencia",
    "lat",
    "lon",
    "distancia_siguiente_m",
    "tiempo_viaje_seg",
    "bahias",
    "codigo_recaudo",
    "cuota_sur",
).write_parquet(SCENARIO_DIR / "estaciones_piloto.parquet")
demand.write_parquet(SCENARIO_DIR / "demanda_lambda_dia_completo.parquet")
weights_df.write_parquet(SCENARIO_DIR / "pesos_descenso.parquet")
services_df.write_parquet(SCENARIO_DIR / "servicios_corredor.parquet")

metadata = {
    "gtfs_snapshot": GTFS_SNAPSHOT,
    "corredor": {"norte": NORTH_BOUNDARY, "sur": SOUTH_BOUNDARY, "sentido": DIRECTION},
    "ventana_pico": {"inicio_h": PEAK_START_SEC // 3600, "fin_h": PEAK_END_SEC // 3600},
    "dias_habiles_validaciones": validation_days,
    "dias_habiles_salidas": exit_days,
    "rutas_optimizables": list(OPTIMIZED_ROUTES),
    "flota_maxima": base_fleet,
    "validacion_flota_gtfs": fleet_check,
    "capacidad_bus_pax": BUS_CAPACITY_PAX,
    "supuestos": [
        "Capacidad articulada uniforme (160 pax): el GTFS no publica el tipo de vehículo.",
        "Flota por sentido (ley de Little) con duraciones y frecuencias del pico AM y 5 min de regulación por cabecera; el regreso opera a su frecuencia GTFS.",
        "Reparto por sentido con modelo gravitacional sobre las salidas AM observadas.",
        "Destinos fuera del corredor agregados en un sumidero sur (SUR).",
        "Calle 72, Calle 63 y Calle 45 sin servicio troncal en el GTFS (obras 2026).",
        "Transbordos de alimentadores sin validación no se observan en la demanda.",
    ],
}
(SCENARIO_DIR / "escenario.json").write_text(
    json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)

print(
    f"[INFO] Demanda: {demand.height} franjas de 15 min | "
    f"{validation_days} días hábiles de validaciones"
)
print(
    f"[INFO] Atracción de destinos: {len(corridor_codes)} estaciones + sumidero sur "
    f"({south_sink_weight:,.0f} salidas AM/día)"
)
print(f"[INFO] Flota actual de las rutas optimizables (cota B_max): {base_fleet} buses")
print("=" * 80)
