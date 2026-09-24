"""
scripts/03_optimizar_frecuencias.py
Optimización de Alta Fidelidad y Exportación de Telemetría (Antes vs. Después)
FlowTM - Digital Twin Engine
"""

from pathlib import Path
from flowtm.domain.state import ScheduleState
from flowtm.simulation.engine import SimuladorCorredor
from flowtm.optimization.simulated_annealing import SimulatedAnnealingOptimizer

ROOT_DIR = Path(__file__).resolve().parent.parent
escenario_dir = ROOT_DIR / "data/scenarios/piloto"

print("=" * 80)
print("🧠 OPTIMIZACIÓN MULTIOBJETIVO DE ALTA FIDELIDAD - FlowTM")
print("=" * 80)

# 1. Escenario Base (Línea Base)
frecuencias_base = {"B10": 4.5, "B27": 6.0, "H20": 5.0}
estado_base = ScheduleState(frecuencias=frecuencias_base)

simulador_base = SimuladorCorredor(escenario_dir)
kpis_base = simulador_base.simular(frecuencias_base)
simulador_base.collector.exportar_telemetria(escenario_dir / "telemetria_base")

# 2. Correr la búsqueda del Agente Racional (30 iteraciones)
optimizador = SimulatedAnnealingOptimizer(escenario_dir, iteraciones=30, temp_inicial=75.0, cooling_rate=0.88)
mejor_estado, _ = optimizador.optimizar(estado_base)

# 3. Simular el escenario ganador y exportar su telemetría
print("\n🎬 Exportando telemetría del escenario optimizado...")
simulador_opt = SimuladorCorredor(escenario_dir)
kpis_opt = simulador_opt.simular(mejor_estado.frecuencias)
simulador_opt.collector.exportar_telemetria(escenario_dir / "telemetria_opt")
print("📍 Telemetría optimizada guardada en: data/scenarios/piloto/telemetria_opt/")

# 4. Tabla Comparativa de Impacto Definitiva
print("\n" + "=" * 80)
print("📊 RESULTADOS FINALES: IMPACTO ANTES vs. DESPUÉS (FlowTM)")
print("=" * 80)
print(f"{'MÉTRICA':<35} | {'ANTES (Base)':<18} | {'DESPUÉS (FlowTM)':<18} | {'IMPACTO'}")
print("-" * 80)

delta_espera = ((kpis_opt.tiempo_espera_promedio_min - kpis_base.tiempo_espera_promedio_min) / kpis_base.tiempo_espera_promedio_min) * 100
delta_varados = ((kpis_opt.pasajeros_quedados_en_cola - kpis_base.pasajeros_quedados_en_cola) / max(1, kpis_base.pasajeros_quedados_en_cola)) * 100
delta_trans = ((kpis_opt.total_pasajeros_transportados - kpis_base.total_pasajeros_transportados) / max(1, kpis_base.total_pasajeros_transportados)) * 100
delta_sobre = kpis_opt.porcentaje_buses_sobrecupo - kpis_base.porcentaje_buses_sobrecupo

print(f"{'Horarios de Despacho':<35} | {str(frecuencias_base):<18} | {str(mejor_estado.frecuencias):<18} | {'Optimizados'}")
print(f"{'Tiempo promedio de espera':<35} | {kpis_base.tiempo_espera_promedio_min:>15.2f} m | {kpis_opt.tiempo_espera_promedio_min:>15.2f} m | {delta_espera:>+6.1f}%")
print(f"{'Pasajeros varados en andén':<35} | {kpis_base.pasajeros_quedados_en_cola:>15,}   | {kpis_opt.pasajeros_quedados_en_cola:>15,}   | {delta_varados:>+6.1f}%")
print(f"{'Pasajeros transportados':<35} | {kpis_base.total_pasajeros_transportados:>15,}   | {kpis_opt.total_pasajeros_transportados:>15,}   | {delta_trans:>+6.1f}%")
print(f"{'Buses con sobrecupo (≥95%)':<35} | {kpis_base.porcentaje_buses_sobrecupo:>14.1f}% | {kpis_opt.porcentaje_buses_sobrecupo:>14.1f}% | {delta_sobre:>+6.1f} pts")
print(f"{'Buses despachados':<35} | {kpis_base.total_buses_despachados:>15}   | {kpis_opt.total_buses_despachados:>15}   | {kpis_opt.total_buses_despachados - kpis_base.total_buses_despachados:>+3d} buses")
print(f"{'Ocupación promedio de flota':<35} | {kpis_base.factor_ocupacion_promedio * 100:>14.1f}% | {kpis_opt.factor_ocupacion_promedio * 100:>14.1f}% | {'Balanceado'}")
print("=" * 80)