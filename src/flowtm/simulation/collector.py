"""
src/flowtm/simulation/collector.py
Patrón Observer: Colector de Series Temporales y Posiciones para el Dashboard
FlowTM - Digital Twin Engine
"""

from typing import List, Dict
import polars as pl
from pathlib import Path

class MetricsCollector:
    def __init__(self):
        self.telemetria_buses: List[Dict] = []
        self.historial_colas: List[Dict] = []

    def registrar_posicion_bus(self, tiempo_seg: float, id_bus: str, ruta: str, lat: float, lon: float, ocupacion: float, pasajeros: int):
        self.telemetria_buses.append({
            "tiempo_seg": round(tiempo_seg, 1),
            "hora_simulada": f"{int(6 + tiempo_seg // 3600):02d}:{int((tiempo_seg % 3600) // 60):02d}",
            "id_bus": id_bus,
            "ruta": ruta,
            "lat": lat,
            "lon": lon,
            "ocupacion": round(ocupacion * 100, 1),
            "pasajeros": pasajeros
        })

    def registrar_cola_estacion(self, tiempo_seg: float, codigo_estacion: str, nombre_estacion: str, cola: int):
        self.historial_colas.append({
            "tiempo_seg": round(tiempo_seg, 1),
            "codigo_estacion": codigo_estacion,
            "nombre": nombre_estacion,
            "cola_pasajeros": cola
        })

    def exportar_telemetria(self, ruta_salida: Path):
        ruta_salida.mkdir(parents=True, exist_ok=True)
        if self.telemetria_buses:
            df_buses = pl.DataFrame(self.telemetria_buses)
            df_buses.write_parquet(ruta_salida / "telemetria_buses.parquet")
        if self.historial_colas:
            df_colas = pl.DataFrame(self.historial_colas)
            df_colas.write_parquet(ruta_salida / "historial_colas.parquet")