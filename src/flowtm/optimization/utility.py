"""
src/flowtm/optimization/utility.py
Función de Utilidad Multicriterio U(S) del Agente Racional
FlowTM - Digital Twin Engine
"""

from flowtm.domain.models import ResultadoSimulacion

class UtilityCalculator:
    def __init__(self, w_espera: float = 0.45, w_quedados: float = 0.35, w_sobrecupo: float = 0.20):
        self.w1 = w_espera
        self.w2 = w_quedados
        self.w3 = w_sobrecupo

    def evaluar(self, res: ResultadoSimulacion) -> float:
        """
        Calcula la utilidad del estado. Entre más alta (más cercana a cero), mejor.
        Penaliza severamente los pasajeros varados y los tiempos de espera prolongados.
        """
        penalizacion_espera = res.tiempo_espera_promedio_min
        penalizacion_quedados = (res.pasajeros_quedados_en_cola / 1000.0) ** 1.2
        penalizacion_sobrecupo = res.porcentaje_buses_sobrecupo

        costo_total = (
            self.w1 * penalizacion_espera +
            self.w2 * penalizacion_quedados +
            self.w3 * penalizacion_sobrecupo
        )
        return -costo_total