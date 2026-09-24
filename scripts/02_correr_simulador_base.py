"""
scripts/02_correr_simulador_base.py
Ejecuta la Simulación del Escenario Base (GTFS Actual de TransMilenio)
FlowTM - Digital Twin Engine
"""

from pathlib import Path
from flowtm.simulation.engine import SimuladorCorredor

ROOT_DIR = Path(__file__).resolve().parent.parent
escenario_dir = ROOT_DIR / "data/scenarios/piloto"

print("=" * 75)
print("🚦 SIMULANDO ESCENARIO BASE (GTFS ACTUAL DE TRANSMILENIO)")
print("=" * 75)

# Frecuencias actuales aproximadas del sistema en hora pico (en minutos)
frecuencias_base = {
    "B10": 4.5,   # Un bus cada 4.5 minutos
    "B27": 6.0,   # Expreso cada 6 minutos
    "H20": 5.0    # Un bus cada 5 minutos
}

print(f"📋 Frecuencias de despacho base: {frecuencias_base}\n")
print("⏳ Corriendo simulación de 3 horas de hora pico (06:00 - 09:00 AM)...")

simulador = SimuladorCorredor(escenario_dir)
kpis = simulador.simular(frecuencias_base, duracion_horas=3.0)

print("\n" + "=" * 75)
print("📊 RESULTADOS DEL ESCENARIO BASE (LÍNEA BASE DE TRANSMILENIO)")
print("=" * 75)
print(f"⏱️  Tiempo promedio de espera      : {kpis.tiempo_espera_promedio_min:.2f} minutos")
print(f"🚌 Nivel de ocupación promedio     : {kpis.factor_ocupacion_promedio * 100:.1f}%")
print(f"🚨 Porcentaje de buses con sobrecupo: {kpis.porcentaje_buses_sobrecupo:.1f}% (≥ 95% de carga)")
print(f"👥 Pasajeros transportados         : {kpis.total_pasajeros_transportados:,}")
print(f"🧍 Pasajeros esperando en andén    : {kpis.pasajeros_quedados_en_cola:,}")
print(f"🚍 Total buses despachados         : {kpis.total_buses_despachados}")
print("=" * 75)

# Agrega una línea para que guarde la telemetría del mapa
simulador.collector.exportar_telemetria(escenario_dir / "telemetria_base")
print("📍 Telemetría de buses y colas exportada para el Dashboard.")