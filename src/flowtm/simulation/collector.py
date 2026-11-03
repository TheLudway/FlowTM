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

from pathlib import Path

import polars as pl


class SimulationCollector:
    """
    Collects discrete-event simulation records for historical export and OCC visualization.
    """

    def __init__(self) -> None:
        self.bus_telemetry: list[dict] = []
        self.queue_history: list[dict] = []

    def record_bus_position(
        self,
        time_sec: float,
        bus_id: str,
        route: str,
        lat: float,
        lon: float,
        occupancy: float,
        passengers: int,
    ) -> None:
        """Records an instantaneous snapshot of a vehicle traversing a station or link."""
        simulated_hour = int(6 + time_sec // 3600)
        simulated_minute = int((time_sec % 3600) // 60)
        simulated_second = int(time_sec % 60)

        self.bus_telemetry.append(
            {
                "tiempo_seg": round(time_sec, 1),
                "time_sec": round(time_sec, 1),
                "hora_simulada": f"{simulated_hour:02d}:{simulated_minute:02d}",
                "simulated_time": f"{simulated_hour:02d}:{simulated_minute:02d}:{simulated_second:02d}",
                "id_bus": bus_id,
                "bus_id": bus_id,
                "ruta": route,
                "route": route,
                "lat": lat,
                "lon": lon,
                "ocupacion": round(occupancy * 100, 1),
                "occupancy_pct": round(occupancy * 100, 1),
                "pasajeros": passengers,
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
                "tiempo_seg": round(time_sec, 1),
                "time_sec": round(time_sec, 1),
                "codigo_estacion": station_code,
                "station_code": station_code,
                "nombre": station_name,
                "station_name": station_name,
                "cola_pasajeros": queue_size,
                "queue_size": queue_size,
            }
        )

    def export_telemetry(self, output_path: Path) -> None:
        """Exports collected telemetry to Parquet files for OCC consumption."""
        output_path.mkdir(parents=True, exist_ok=True)
        if self.bus_telemetry:
            df_buses = pl.DataFrame(self.bus_telemetry)
            df_buses.write_parquet(output_path / "telemetria_buses.parquet")
        if self.queue_history:
            df_queues = pl.DataFrame(self.queue_history)
            df_queues.write_parquet(output_path / "historial_colas.parquet")
