"""
src/flowtm/domain/models.py
Entidades de Dominio con Analítica Granular por Estación y Bus
FlowTM - Digital Twin Engine
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class Pasajero:
    id_pasajero: int
    estacion_origen: str
    estacion_destino: str
    tiempo_llegada_seg: float
    tiempo_abordaje_seg: Optional[float] = None

@dataclass
class Estacion:
    codigo: str
    nombre: str
    secuencia: int
    lat: float
    lon: float
    distancia_siguiente_m: float
    tiempo_viaje_seg: float
    lambda_actual: float = 0.05
    cola_pasajeros: List[Pasajero] = field(default_factory=list)
    tiempo_espera_acumulado_seg: float = 0.0
    total_llegadas: int = 0
    total_abordajes: int = 0
    total_descensos: int = 0

    def registrar_llegada(self, pasajero: Pasajero):
        self.cola_pasajeros.append(pasajero)
        self.total_llegadas += 1

    def obtener_pasajeros_aptos(self, paradas_bus: List[str], cupo_disponible: int) -> List[Pasajero]:
        aptos = []
        no_aptos = []
        for p in self.cola_pasajeros:
            if len(aptos) < cupo_disponible and p.estacion_destino in paradas_bus:
                aptos.append(p)
            else:
                no_aptos.append(p)
        self.cola_pasajeros = no_aptos
        self.total_abordajes += len(aptos)
        return aptos

    @property
    def cola_corriente(self) -> int:
        """Pasajeros esperando estaciones intermedias (solo corriente)."""
        paradas_expreso = ["01000", "01001", "01006", "02204", "02200", "02000", "08106", "08008"]
        return sum(1 for p in self.cola_pasajeros if p.estacion_destino not in paradas_expreso)

    @property
    def cola_expreso(self) -> int:
        """Pasajeros que pueden tomar expreso o corriente."""
        paradas_expreso = ["01000", "01001", "01006", "02204", "02200", "02000", "08106", "08008"]
        return sum(1 for p in self.cola_pasajeros if p.estacion_destino in paradas_expreso)

@dataclass
class Bus:
    id_bus: str
    ruta: str
    capacidad_maxima: int = 160
    pasajeros_a_bordo: List[Pasajero] = field(default_factory=list)
    paradas_programadas: List[str] = field(default_factory=list)
    historial_ocupacion: List[float] = field(default_factory=list)
    perfil_pasajeros_por_parada: List[Dict] = field(default_factory=list)

    @property
    def total_pasajeros(self) -> int:
        return len(self.pasajeros_a_bordo)

    @property
    def capacidad_disponible(self) -> int:
        return max(0, self.capacidad_maxima - self.total_pasajeros)

    @property
    def factor_ocupacion(self) -> float:
        return self.total_pasajeros / self.capacidad_maxima

@dataclass
class ResultadoSimulacion:
    tiempo_espera_promedio_min: float
    factor_ocupacion_promedio: float
    porcentaje_buses_sobrecupo: float
    total_pasajeros_transportados: int
    pasajeros_quedados_en_cola: int
    total_buses_despachados: int
    metricas_estaciones: List[Dict] = field(default_factory=list)
    perfil_carga_rutas: Dict[str, List[Dict]] = field(default_factory=dict)