# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Shared pytest fixtures.

The real pilot scenario (``data/scenarios/piloto``) is generated from GTFS and
fare-system data by ``scripts/01_preparar_escenario.py`` and is git-ignored, so
tests build a small synthetic scenario with the same schema instead.
"""

import json
import math
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

SYNTHETIC_STATION_CODES: list[str] = [f"0{index:04d}" for index in range(1, 9)]
SYNTHETIC_ARRIVAL_RATE_PER_SEC = 0.03

# route -> (role, stops, headway_min, cycle_min, continues_after)
SYNTHETIC_SERVICES: dict[str, tuple[str, list[str], float, float, bool]] = {
    "R1": ("optimizable", SYNTHETIC_STATION_CODES, 4.0, 60.0, True),
    "R2": ("optimizable", ["00001", "00004", "00008"], 5.0, 50.0, True),
    "R3": ("optimizable", SYNTHETIC_STATION_CODES[1:6], 5.0, 40.0, False),
    "BG1": ("fondo", SYNTHETIC_STATION_CODES, 6.0, 70.0, True),
}
SYNTHETIC_BASE_HEADWAYS = {
    route: spec[2]
    for route, spec in SYNTHETIC_SERVICES.items()
    if spec[0] == "optimizable"
}


def build_synthetic_scenario(
    scenario_dir: Path, cycle_override_min: dict[str, float] | None = None
) -> Path:
    """Write every input expected by ``CorridorScenario.load``."""
    scenario_dir.mkdir(parents=True, exist_ok=True)
    codes = SYNTHETIC_STATION_CODES
    count = len(codes)
    services = {
        route: (
            role,
            stops,
            headway,
            (cycle_override_min or {}).get(route, cycle),
            cont,
        )
        for route, (role, stops, headway, cycle, cont) in SYNTHETIC_SERVICES.items()
    }

    pl.DataFrame(
        {
            "codigo": codes,
            "nombre": [f"ESTACION {code}" for code in codes],
            "secuencia": list(range(1, count + 1)),
            "lat": [4.75 - 0.005 * index for index in range(count)],
            "lon": [-74.05] * count,
            "distancia_siguiente_m": [800.0] * (count - 1) + [0.0],
            "tiempo_viaje_seg": [120.0] * (count - 1) + [0.0],
            "bahias": [2] * count,
            "codigo_recaudo": codes,
            "cuota_sur": [1.0] * count,
        }
    ).write_parquet(scenario_dir / "estaciones_piloto.parquet")

    pl.DataFrame(
        [
            {
                "CODIGO_ESTACION": code,
                "hora_del_dia": hour,
                "franja_15m": datetime(2026, 8, 24, hour, minute),
                "lambda_segundo": SYNTHETIC_ARRIVAL_RATE_PER_SEC,
            }
            for hour in range(6, 9)
            for minute in (0, 15, 30, 45)
            for code in codes
        ]
    ).with_columns(pl.col("hora_del_dia").cast(pl.Int8)).write_parquet(
        scenario_dir / "demanda_lambda_dia_completo.parquet"
    )

    pl.DataFrame(
        {
            "CODIGO_ESTACION": [*codes, "SUR"],
            "peso_atraccion": [1.0 / (count + 1)] * (count + 1),
        }
    ).write_parquet(scenario_dir / "pesos_descenso.parquet")

    pl.DataFrame(
        [
            {
                "ruta": route,
                "nombre": f"Servicio {route}",
                "color": "#1976D2",
                "rol": role,
                "paradas": stops,
                "headway_gtfs_min": headway,
                "viajes_pico": int(180 / headway),
                "recorrido_corredor_min": 15.0,
                "tiempo_ciclo_min": cycle,
                "contraparte": None,
                "continua_al_salir": cont,
                "capacidad": 160,
            }
            for route, (role, stops, headway, cycle, cont) in services.items()
        ]
    ).write_parquet(scenario_dir / "servicios_corredor.parquet")

    max_fleet = sum(
        math.ceil(cycle / headway)
        for role, _, headway, cycle, _ in services.values()
        if role == "optimizable"
    )
    (scenario_dir / "escenario.json").write_text(
        json.dumps(
            {"flota_maxima": max_fleet, "rutas_optimizables": ["R1", "R2", "R3"]}
        ),
        encoding="utf-8",
    )
    return scenario_dir


@pytest.fixture(scope="session")
def synthetic_scenario_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-wide synthetic pilot scenario directory."""
    return build_synthetic_scenario(tmp_path_factory.mktemp("piloto"))
