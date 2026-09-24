"""
src/flowtm/optimization/simulated_annealing.py
Algoritmo de Búsqueda Heurística con Monitoreo en Vivo
FlowTM - Digital Twin Engine
"""

import math
import random
from pathlib import Path
from flowtm.domain.state import ScheduleState
from flowtm.optimization.utility import UtilityCalculator
from flowtm.simulation.engine import SimuladorCorredor

class SimulatedAnnealingOptimizer:
    def __init__(self, ruta_escenario: Path, iteraciones: int = 30, temp_inicial: float = 80.0, cooling_rate: float = 0.90):
        self.simulador = SimuladorCorredor(ruta_escenario)
        self.calc_utilidad = UtilityCalculator()
        self.iteraciones = iteraciones
        self.temp_inicial = temp_inicial
        self.cooling_rate = cooling_rate

    def optimizar(self, estado_inicial: ScheduleState):
        estado_actual = estado_inicial
        resultado_actual = self.simulador.simular(estado_actual.frecuencias)
        utilidad_actual = self.calc_utilidad.evaluar(resultado_actual)

        mejor_estado = estado_actual
        mejor_resultado = resultado_actual
        mejor_utilidad = utilidad_actual

        temperatura = self.temp_inicial

        print(f"🔄 BÚSQUEDA DEL AGENTE RACIONAL ({self.iteraciones} iteraciones):")
        print(f"   [Base] Espera: {resultado_actual.tiempo_espera_promedio_min:.2f}m | Varados: {resultado_actual.pasajeros_quedados_en_cola:,} | Horario: {estado_actual.frecuencias}\n")

        for i in range(1, self.iteraciones + 1):
            vecino = estado_actual.generar_vecino(paso_min=0.5)
            res_vecino = self.simulador.simular(vecino.frecuencias)
            utilidad_vecino = self.calc_utilidad.evaluar(res_vecino)

            delta_u = utilidad_vecino - utilidad_actual

            # Criterio de Metrópolis
            aceptado = False
            if delta_u > 0 or random.random() < math.exp(delta_u / max(1e-5, temperatura)):
                estado_actual = vecino
                resultado_actual = res_vecino
                utilidad_actual = utilidad_vecino
                aceptado = True

                if utilidad_actual > mejor_utilidad:
                    mejor_estado = estado_actual
                    mejor_resultado = resultado_actual
                    mejor_utilidad = utilidad_actual
                    print(f"   ⭐ Iteración {i:2d} | ¡NUEVO ÓPTIMO! | Espera: {mejor_resultado.tiempo_espera_promedio_min:.2f}m | Varados: {mejor_resultado.pasajeros_quedados_en_cola:,} | Horario: {mejor_estado.frecuencias}")
                else:
                    print(f"   ✓  Iteración {i:2d} | Aceptado       | Espera: {resultado_actual.tiempo_espera_promedio_min:.2f}m | Varados: {resultado_actual.pasajeros_quedados_en_cola:,} | Horario: {estado_actual.frecuencias}")
            else:
                print(f"   ✗  Iteración {i:2d} | Rechazado      | Espera: {res_vecino.tiempo_espera_promedio_min:.2f}m | Varados: {res_vecino.pasajeros_quedados_en_cola:,} | Horario: {vecino.frecuencias}")

            temperatura *= self.cooling_rate

        return mejor_estado, mejor_resultado