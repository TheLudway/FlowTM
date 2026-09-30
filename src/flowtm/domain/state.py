"""
src/flowtm/domain/state.py
Representación del Espacio de Estados y Acciones del Agente Racional
FlowTM - Digital Twin Engine
"""

import random
from dataclasses import dataclass
from typing import Dict

@dataclass
class ScheduleState:
    """
    Estado del Agente:
    Diccionario con el intervalo de despacho en minutos por ruta.
    Ejemplo: {'B10': 3.5, 'B27': 4.0, 'H20': 4.5}
    """
    frecuencias: Dict[str, float]

    def generar_vecino(self, paso_min: float = 0.5) -> "ScheduleState":
        """
        Acción del Agente:
        Genera un estado vecino perturbando las frecuencias.
        Para mantener la flota total balanceada, si reduce el intervalo a una ruta,
        aumenta ligeramente el de otra.
        """
        nuevas = self.frecuencias.copy()
        rutas = list(nuevas.keys())
        
        r_mejora = random.choice(rutas)
        r_cede = random.choice([r for r in rutas if r != r_mejora])
        
        # Reducir intervalo a una (más buses) y aumentar a otra (menos buses)
        nuevas[r_mejora] = max(2.0, min(8.0, nuevas[r_mejora] - paso_min))
        nuevas[r_cede] = max(2.0, min(8.0, nuevas[r_cede] + paso_min))
        
        return ScheduleState(frecuencias=nuevas)