# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Shared pytest fixtures.

The real pilot scenario (``data/scenarios/piloto``) is generated from raw
TransMilenio data by ``scripts/01_preparar_escenario.py`` and is git-ignored, so
tests build a small synthetic scenario with the same schema instead. This keeps
the simulation tests meaningful in CI without depending on local data.
"""

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

PILOT_STATION_CODES: list[str] = [
    "02000",
    "02101",
    "02102",
    "02103",
    "02104",
    "02200",
    "02201",
    "02204",
    "02205",
    "02300",
    "02302",
    "02303",
    "02304",
    "09122",
    "09127",
    "09120",
    "09117",
]

SYNTHETIC_ARRIVAL_RATE_PER_SEC = 0.02


def build_synthetic_scenario(scenario_dir: Path) -> Path:
    """Write the three Parquet inputs expected by ``CorridorSimulator``."""
    scenario_dir.mkdir(parents=True, exist_ok=True)
    station_count = len(PILOT_STATION_CODES)

    pl.DataFrame(
        {
            "codigo": PILOT_STATION_CODES,
            "nombre": [f"ESTACION {code}" for code in PILOT_STATION_CODES],
            "secuencia": list(range(1, station_count + 1)),
            "lat": [4.75 - 0.005 * index for index in range(station_count)],
            "lon": [-74.05] * station_count,
            "distancia_siguiente_m": [800.0] * station_count,
            "tiempo_viaje_seg": [120.0] * station_count,
        }
    ).write_parquet(scenario_dir / "estaciones_piloto.parquet")

    demand_rows = [
        {
            "CODIGO_ESTACION": code,
            "hora_del_dia": hour,
            "franja_15m": datetime(2026, 8, 24, hour, minute),
            "lambda_segundo": SYNTHETIC_ARRIVAL_RATE_PER_SEC,
        }
        for hour in range(6, 9)
        for minute in (0, 15, 30, 45)
        for code in PILOT_STATION_CODES
    ]
    pl.DataFrame(demand_rows).with_columns(
        pl.col("hora_del_dia").cast(pl.Int8)
    ).write_parquet(scenario_dir / "demanda_lambda_dia_completo.parquet")

    pl.DataFrame(
        {
            "CODIGO_ESTACION": PILOT_STATION_CODES,
            "peso_atraccion": [1.0 / station_count] * station_count,
        }
    ).write_parquet(scenario_dir / "pesos_descenso.parquet")

    return scenario_dir


@pytest.fixture(scope="session")
def synthetic_scenario_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-wide synthetic pilot scenario directory."""
    return build_synthetic_scenario(tmp_path_factory.mktemp("piloto"))
