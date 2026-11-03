# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.simulation.scenario
==========================
Loads a corridor scenario produced by ``scripts/01_preparar_escenario.py``: the
GTFS-derived topology and services plus the fare-system demand. It is the single
source of truth for routes, stop patterns, cycle times and the fleet bound.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from flowtm.domain.state import ScheduleState

# Aggregated destination for trips that continue south of the corridor.
SOUTH_SINK_CODE = "SUR"

ROLE_OPTIMIZABLE = "optimizable"
ROLE_BACKGROUND = "fondo"


@dataclass(frozen=True)
class ServiceSpec:
    """A trunk service crossing the corridor, as published in the GTFS."""

    route: str
    name: str
    color: str
    role: str
    stops: tuple[str, ...]
    headway_gtfs_min: float
    cycle_time_min: float
    corridor_run_min: float
    continues_after: bool
    capacity: int
    leg_time_min: float = 0.0
    return_fleet: int = 0
    counterpart: str | None = None

    @property
    def is_optimizable(self) -> bool:
        return self.role == ROLE_OPTIMIZABLE

    @property
    def served_destinations(self) -> tuple[str, ...]:
        """Destinations a passenger can reach on this service."""
        sink = (SOUTH_SINK_CODE,) if self.continues_after else ()
        return (*self.stops, *sink)


@dataclass(frozen=True)
class CorridorScenario:
    """Topology, demand and supply of the pilot corridor."""

    topology: pl.DataFrame
    demand: pl.DataFrame
    attraction_weights: dict[str, float]
    services: dict[str, ServiceSpec]
    metadata: dict[str, Any]

    @classmethod
    def load(cls, scenario_dir: Path) -> "CorridorScenario":
        scenario_dir = Path(scenario_dir)
        weights = pl.read_parquet(scenario_dir / "pesos_descenso.parquet")
        services_df = pl.read_parquet(scenario_dir / "servicios_corredor.parquet")
        services = {
            row["ruta"]: ServiceSpec(
                route=row["ruta"],
                name=row["nombre"],
                color=row["color"],
                role=row["rol"],
                stops=tuple(row["paradas"]),
                headway_gtfs_min=float(row["headway_gtfs_min"]),
                cycle_time_min=float(row["tiempo_ciclo_min"]),
                corridor_run_min=float(row["recorrido_corredor_min"]),
                continues_after=bool(row["continua_al_salir"]),
                capacity=int(row["capacidad"]),
                leg_time_min=float(row.get("tiempo_tramo_min") or 0.0),
                return_fleet=int(row.get("flota_regreso") or 0),
                counterpart=row.get("contraparte"),
            )
            for row in services_df.iter_rows(named=True)
        }
        return cls(
            topology=pl.read_parquet(scenario_dir / "estaciones_piloto.parquet").sort(
                "secuencia"
            ),
            demand=pl.read_parquet(
                scenario_dir / "demanda_lambda_dia_completo.parquet"
            ),
            attraction_weights=dict(
                zip(
                    weights["CODIGO_ESTACION"],
                    weights["peso_atraccion"],
                    strict=True,
                )
            ),
            services=services,
            metadata=json.loads(
                (scenario_dir / "escenario.json").read_text(encoding="utf-8")
            ),
        )

    @property
    def optimizable_routes(self) -> list[str]:
        return [r for r, s in self.services.items() if s.is_optimizable]

    @property
    def background_routes(self) -> list[str]:
        return [r for r, s in self.services.items() if not s.is_optimizable]

    @property
    def max_fleet(self) -> int:
        """Fleet TransMilenio currently assigns to the optimizable routes."""
        return int(self.metadata["flota_maxima"])

    def base_headways(self) -> dict[str, float]:
        """GTFS peak headways of the optimizable routes (current operation)."""
        return {r: self.services[r].headway_gtfs_min for r in self.optimizable_routes}

    def base_schedule(self) -> ScheduleState:
        """Schedule state of the current GTFS operation."""
        routes = self.optimizable_routes
        return ScheduleState(
            headways=self.base_headways(),
            leg_times={r: self.services[r].leg_time_min for r in routes},
            max_fleet=self.max_fleet,
            fixed_fleet={r: self.services[r].return_fleet for r in routes},
        )
