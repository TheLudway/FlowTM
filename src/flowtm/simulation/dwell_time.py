"""
src/flowtm/simulation/dwell_time.py
Cálculo del Tiempo de Permanencia en Plataforma (Dwell Time)
FlowTM - Digital Twin Engine
"""

def calcular_tiempo_parada_seg(suben: int, bajan: int) -> float:
    """
    Ecuación de ingeniería de transporte:
    T_dwell = T_puertas + max(beta_sub * suben, beta_baj * bajan)
    - T_puertas: 10 segundos (abrir, pitar y cerrar).
    - beta: 1.2 segundos por persona subiendo o bajando.
    """
    t_puertas = 10.0
    t_flujo = max(suben * 1.2, bajan * 1.0)
    # Un bus no para menos de 12 segundos ni más de 75 segundos por norma
    return min(75.0, max(12.0, t_puertas + t_flujo))