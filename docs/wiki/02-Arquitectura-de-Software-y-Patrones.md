# 02. Arquitectura de Software y Patrones de Diseño de FlowTM

**FlowTM** implementa los principios de **Clean Architecture (Arquitectura Hexagonal / Puertos y Adaptadores)** combinados con un pipeline in-memory de alto rendimiento basado en **Apache Arrow, Polars y SimPy** sobre Python 3.12+.

---

## 1. Estilo Arquitectónico Global (Clean Architecture)

El sistema está diseñado en capas concéntricas con estricta regla de dependencia unidireccional hacia adentro:

```
┌─────────────────────────────────────────────────────────────┐
│           PRESENTATION (Frontend React 19 / MapLibre GL)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ consume contratos JSON / GTFS
┌──────────────────────────────▼──────────────────────────────┐
│           OPTIMIZATION (Simulated Annealing / Utility U(S)) │
└──────────────────────────────┬──────────────────────────────┘
                               │ orquesta y evalúa
┌──────────────────────────────▼──────────────────────────────┐
│           SIMULATION (CorridorSimulator / SimPy Engine)     │
└──────────────────────────────┬──────────────────────────────┘
                               │ opera sobre
┌──────────────────────────────▼──────────────────────────────┐
│           DOMAIN (Passenger, Station, Bus, ScheduleState)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ alimentado por
┌──────────────────────────────▼──────────────────────────────┐
│           INFRASTRUCTURE (ParquetDataRepository / Polars)   │
└─────────────────────────────────────────────────────────────┘
```

### Principio de Independencia del Dominio
El paquete `flowtm.domain` contiene los modelos puros del negocio (dataclasses de Python). Tiene **cero dependencias externas** de frameworks web, motores de bases de datos o librerías de visualización. El motor físico de eventos discretos opera sobre estas entidades puras, lo que garantiza que cualquier cambio en la interfaz gráfica no impacta el núcleo computacional.

---

## 2. Estructura de Módulos del Núcleo (`src/flowtm/`)

```text
src/flowtm/
├── domain/                          # Entidades puras del dominio de transporte
│   ├── models.py                    # Passenger, Station, Bus, SimulationResult
│   └── state.py                     # ScheduleState (Vector H de frecuencias)
├── simulation/                      # Motor estocástico por eventos discretos
│   ├── engine.py                    # CorridorSimulator (Orquestador SimPy)
│   ├── collector.py                 # SimulationCollector (Patrón Observer)
│   └── dwell_time.py                # Modelo no lineal TCQSM de dwell time
├── optimization/                    # Inteligencia Artificial Heurística
│   ├── simulated_annealing.py       # SimulatedAnnealingOptimizer (Recocido)
│   └── utility.py                   # UtilityCalculator (Función multicriterio U(S))
├── infrastructure/                  # Adaptadores de persistencia y estándares
│   ├── gtfs_exporter.py             # Exportador de frecuencias estándar GTFS
│   └── repositories/
│       └── data_repository.py       # DataRepository (Patrón Repositorio)
└── presentation/                    # Capa de presentación legacy y exportación
    └── dashboard/
        └── app.py                   # Prototipo analítico en Streamlit
```

---

## 3. Patrones de Diseño de Software Implementados

### A. Patrón Repositorio (*Repository Pattern*)
* **Ubicación:** [`src/flowtm/infrastructure/repositories/data_repository.py`](file:///home/kevin/FlowTM/src/flowtm/infrastructure/repositories/data_repository.py)
* **Objetivo:** Desacopla la lógica de simulación del acceso físico a los datos tabulares en disco.
* **Implementación:**
  * Interfaz abstracta `DataRepository` con métodos `get_topology()` y `get_telemetry(scenario)`.
  * Clase concreta `ParquetDataRepository` que utiliza escaneo perezoso (*lazy scanning*) de **Polars** para leer archivos Parquet comprimidos con Zstandard (ZSTD) y convertirlos eficientemente en memoria.

```python
class DataRepository(ABC):
    @abstractmethod
    def get_topology(self) -> pd.DataFrame: ...

    @abstractmethod
    def get_telemetry(
        self, scenario: str
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None]: ...
```

### B. Patrón Observador (*Observer Pattern*)
* **Ubicación:** [`src/flowtm/simulation/collector.py`](file:///home/kevin/FlowTM/src/flowtm/simulation/collector.py)
* **Objetivo:** Registrar en tiempo real la telemetría espacio-temporal de cada vehículo y la longitud de cola en cada andén sin acoplar el bucle de simulación con el almacenamiento.
* **Implementación:**
  * La clase `SimulationCollector` intercepta eventos de la simulación mediante `record_bus_position(...)` y `record_station_queue(...)`.
  * Al culminar la ejecución, exporta directamente a estructuras columnares optimizadas (`telemetria_buses.parquet` e `historial_colas.parquet`).

### C. Patrón Estrategia (*Strategy Pattern*)
* **Ubicación:** [`src/flowtm/simulation/dwell_time.py`](file:///home/kevin/FlowTM/src/flowtm/simulation/dwell_time.py) y [`src/flowtm/optimization/utility.py`](file:///home/kevin/FlowTM/src/flowtm/optimization/utility.py)
* **Objetivo:** Permitir el intercambio dinámico de algoritmos de cálculo sin modificar el flujo de eventos.
* **Implementación:**
  * El cálculo del tiempo de parada en andén `calculate_dwell_time_sec(...)` puede sustituirse por modelos lineales o no lineales.
  * La función de utilidad `UtilityCalculator` permite reconfigurar los pesos multi-criterio ($w_1, w_2, w_3, w_4$) y la función de castigo de barrera de flota.

### D. Patrón Estado (*State Pattern*)
* **Ubicación:** [`src/flowtm/domain/state.py`](file:///home/kevin/FlowTM/src/flowtm/domain/state.py)
* **Objetivo:** Encapsular el estado del agente inteligente (vector de intervalos de despacho $H$) y gobernar las transiciones válidas hacia estados vecinos en $\mathbb{R}^6$.
* **Implementación:**
  * La clase inmutable `ScheduleState` calcula la flota consumida mediante $B_r = \lceil T_r / h_r \rceil$.
  * El método `generate_neighbor(...)` aplica perturbaciones controladas asegurando que cada nuevo estado cumpla las cotas físicas $[2.0, 15.0]\text{ min}$ y respete la cota presupuestal de 106 buses.

---

## 4. Pipeline Analítico In-Memory con Polars y Apache Arrow

Para procesar más de **44.93 millones de registros** de validaciones de torniquetes (*tap-in*) y descensos (*tap-out*), FlowTM prescinde de bases de datos relacionales tradicionales (PostgreSQL / MySQL) que introducirían latencia de I/O innecesaria.

```mermaid
graph LR
    A["Parquet ZSTD (44.93M filas)"] --> B["Polars LazyScan (Zero-Copy)"]
    B --> C["Filtro Corredor + Franjas 15m"]
    C --> D["Cálculo λ(s, t) y Matriz OD"]
    D --> E["SimPy Discrete Event Engine"]
```

* **Zero-Copy Memory:** Aprovecha el formato columnar de Apache Arrow para realizar operaciones vectorizadas directamente en la memoria RAM.
* **Compresión Zstandard (ZSTD):** Reduce el consumo de almacenamiento en disco en un 82% manteniendo velocidades de descompresión de varios gigabytes por segundo.
* **Tiempos de Ejecución:** La extracción y agregación de todo el día operativo toma **menos de 3 segundos** en una estación de trabajo convencional.

---

## 5. Contrato de Integración y Desacoplamiento Frontend

El simulador backend y el frontend moderno de visualización se comunican mediante artefactos de datos estandarizados generados por [`scripts/export_frontend_data.py`](file:///home/kevin/FlowTM/scripts/export_frontend_data.py):

| Archivo Exportado | Formato | Contenido y Propósito |
| :--- | :--- | :--- |
| `corridor.geojson` | GeoJSON | Topología de estaciones y geometría de la calzada troncal. |
| `routes.json` | JSON | Definición de las 6 rutas, códigos de parada, colores y tipologías. |
| `bus_trajectories.json` | JSON Keyframes | Trayectorias interpolables a 60 FPS del escenario base (GTFS oficial). |
| `bus_trajectories_opt.json`| JSON Keyframes | Trayectorias del escenario optimizado generado por FlowTM-Scheduler. |
| `station_queues.json` | JSON Time-Series| Longitud de cola $Q(t)$ por estación en el escenario base. |
| `station_queues_opt.json` | JSON Time-Series| Longitud de cola $Q(t)$ en el escenario optimizado. |
| `summary.json` / `_opt.json`| JSON | KPIs agregados de servicio (espera, ocupación, sobrecupo, flota). |
| `ai_optimization_log.json`| JSON | Historial completo de las 30 iteraciones del Recocido Simulado. |
| `frequencies.txt` | Formato GTFS | Archivo oficial de frecuencias conforme al estándar internacional. |
