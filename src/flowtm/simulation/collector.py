# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.simulation.collector
===========================
Observer Pattern: Real-time telemetry collector for vehicle spatio-temporal positions,
passenger queues, and platform metrics across the BRT corridor.
"""

import json
from pathlib import Path

import polars as pl

from flowtm.domain.models import SimulationResult

SUMMARY_METRICS_FILENAME = "metricas_resumen.json"


def top_od_pairs(result: SimulationResult, limit: int = 8) -> list[dict]:
    """Most frequent simulated origin-destination pairs with their share."""
    total = sum(result.od_counts.values())
    ranked = sorted(result.od_counts.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "origin": origin,
            "destination": destination,
            "passengers": count,
            "share_pct": round(count / total * 100, 1) if total else 0.0,
        }
        for (origin, destination), count in ranked[:limit]
    ]


def build_summary_metrics(result: SimulationResult) -> dict[str, object]:
    """Aggregate KPIs of a simulation run in the format consumed by the OCC."""
    return {
        "avg_waiting_time_min": round(result.avg_waiting_time_min, 2),
        "avg_occupancy_pct": round(result.avg_occupancy_rate * 100, 1),
        "overcrowded_buses_pct": round(result.overcrowded_bus_pct, 1),
        "total_passengers_served": int(result.total_transported_passengers),
        "stranded_passengers_in_queue": int(result.stranded_passengers_in_queue),
        "total_dispatched_buses": int(result.total_dispatched_buses),
        "avg_dispatch_delay_min": round(result.avg_dispatch_delay_min, 2),
        "od_top": top_od_pairs(result),
    }


def export_summary_metrics(result: SimulationResult, output_path: Path) -> Path:
    """Write ``metricas_resumen.json`` next to the scenario telemetry."""
    output_path.mkdir(parents=True, exist_ok=True)
    metrics_file = output_path / SUMMARY_METRICS_FILENAME
    with open(metrics_file, "w", encoding="utf-8") as handle:
        json.dump(build_summary_metrics(result), handle, indent=2)
    return metrics_file


class SimulationCollector:
    """
    Observer that records discrete-event telemetry for export and OCC visualization.
    """

    def __init__(self, start_hour: int = 6) -> None:
        self.start_hour = start_hour
        self.bus_telemetry: list[dict] = []
        self.queue_history: list[dict] = []

    def _clock(self, time_sec: float) -> str:
        total = int(self.start_hour * 3600 + time_sec)
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"

    def record_bus_position(
        self,
        time_sec: float,
        bus_id: str,
        route: str,
        lat: float,
        lon: float,
        occupancy: float,
        passengers: int,
        vehicle_id: str = "",
    ) -> None:
        """Records an instantaneous snapshot of a vehicle at a station."""
        self.bus_telemetry.append(
            {
                "time_sec": round(time_sec, 1),
                "simulated_time": self._clock(time_sec),
                "bus_id": bus_id,
                "vehicle_id": vehicle_id,
                "route": route,
                "lat": lat,
                "lon": lon,
                "occupancy_pct": round(occupancy * 100, 1),
                "passengers": passengers,
            }
        )

    def record_station_queue(
        self,
        time_sec: float,
        station_code: str,
        station_name: str,
        queue_size: int,
    ) -> None:
        """Records the passenger queue length Q(t) standing at a platform."""
        self.queue_history.append(
            {
                "time_sec": round(time_sec, 1),
                "station_code": station_code,
                "station_name": station_name,
                "queue_size": queue_size,
            }
        )

    def export_telemetry(self, output_path: Path) -> None:
        """Exports collected telemetry to Parquet files for OCC consumption."""
        output_path.mkdir(parents=True, exist_ok=True)
        if self.bus_telemetry:
            pl.DataFrame(self.bus_telemetry).write_parquet(
                output_path / "telemetria_buses.parquet"
            )
        if self.queue_history:
            pl.DataFrame(self.queue_history).write_parquet(
                output_path / "historial_colas.parquet"
            )
