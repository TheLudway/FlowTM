# Arquitectura de Software y Patrones de Diseño de FlowTM

FlowTM implementa una combinación de **Clean Architecture (Arquitectura Hexagonal / Puertos y Adaptadores)** y un motor analítico in-memory de alto rendimiento basado en **Polars** y **SimPy** sobre Python 3.12+, acoplado a un Centro de Control de Operaciones en **React 19** y **MapLibre GL**.

---

## 1. Estilo Arquitectónico Global

El sistema se estructura en capas desacopladas con dependencias unidireccionales:

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

### Regla de Oro del Dominio
El paquete `flowtm.domain` contiene modelos puros de negocio (dataclasses inmutables) con **cero dependencias externas de frameworks web o librerías gráficas**. Esta regla de oro de Clean Architecture garantizó que la migración del frontend hacia React 19 y MapLibre GL no requiriera modificar una sola línea del núcleo computacional de simulación ni del optimizador.

---

## 2. Árbol de Módulos del Núcleo (`src/flowtm/`)

```text
src/flowtm/
├── domain/                          # Entidades de dominio puras
│   ├── models.py                    # Passenger, Station, Bus, SimulationResult
│   └── state.py                     # ScheduleState (Vector H de frecuencias)
├── simulation/                      # Motor estocástico por eventos discretos
│   ├── engine.py                    # CorridorSimulator (Orquestador SimPy)
│   ├── collector.py                 # SimulationCollector (Patrón Observer)
│   └── dwell_time.py                # Modelo dinámico TCQSM de dwell time
├── optimization/                    # Inteligencia Artificial y Optimización
│   ├── simulated_annealing.py       # SimulatedAnnealingOptimizer (Recocido Simulado)
│   └── utility.py                   # UtilityCalculator (Función multicriterio U(S))
├── infrastructure/                  # Persistencia, exportación y repositorios
│   ├── gtfs_exporter.py             # Exportador de frecuencias estándar GTFS
│   └── repositories/
│       └── data_repository.py       # DataRepository / ParquetDataRepository
└── presentation/                    # Interfaces de usuario y visualización
    └── dashboard/
        └── app.py                   # Prototipo analítico en Streamlit (legacy)
```

---

## 3. Patrones de Diseño Implementados

### A. Repository Pattern (Patrón Repositorio)
* **Ubicación:** `src/flowtm/infrastructure/repositories/data_repository.py`.
* **Propósito:** Abstrae la lectura física de archivos Parquet comprimidos con Zstandard (ZSTD).
* **Beneficio:** Ni el simulador ni la interfaz interactúan con rutas de archivos directas; consumen la interfaz abstracta `DataRepository`.

### B. Observer Pattern (Patrón Observador)
* **Ubicación:** `src/flowtm/simulation/collector.py` (`SimulationCollector`).
* **Propósito:** Registrar telemetría paso a paso (posiciones geodésicas de buses, ocupación porcentual y colas de andenes).
* **Beneficio:** Desacopla la recolección de métricas de la física de simulación, permitiendo exportar telemetría a disco sin degradar el rendimiento computacional.

### C. State Pattern & Inmutabilidad
* **Ubicación:** `src/flowtm/domain/state.py` (`ScheduleState`).
* **Propósito:** Representar el vector de frecuencias de despacho de las 6 rutas:
  $$H = \{h_{B13}, h_{B18}, h_{B23}, h_{B27}, h_{B74}, h_{B75}\}$$
* **Beneficio:** Las transiciones de estado en el optimizador operan sobre estados clonados e inmutables, garantizando la idempotencia del proceso estocástico.

### D. Strategy Pattern (Patrón Estrategia)
* **Ubicación:** `src/flowtm/optimization/` y `src/flowtm/simulation/engine.py`.
* **Propósito:** Intercambiar de forma transparente la política de despacho evaluada: despacho estático (GTFS vigente) o despacho adaptativo guiado por el vector óptimo $\mathbf{h}^*$ del agente.

### E. Resource Pooling (Gestión Concurrente de Bahías)
* **Ubicación:** Bahías físicas de parada modeladas con `simpy.Resource(env, capacity=2)` en cada estación.
* **Propósito:** Reproducir fielmente la capacidad física de las estaciones de TransMilenio (máximo 2 buses articulados en plataforma simultáneamente).
* **Beneficio:** Modela fenómenos reales de congestión y colas de buses en fila india (*Bus Bunching*).

---

## 4. Evolución del Frontend: Migración a React 19 y MapLibre GL (Resolución Issue #19)

Siguiendo la hoja de ruta del proyecto (Issue #19: *"Migración de interfaz gráfica hacia stack web moderno React/Mapbox"*), la capa de presentación evolucionó de una app en Streamlit hacia un **Centro de Control de Operaciones (OCC)** completo en React 19 + MapLibre GL:

* **Rendimiento Gráfico:** 60 FPS sostenidos renderizando shaders WebGL vectoriales frente a los re-renders pesados de Streamlit.
* **Telemetría Bidireccional:** Visualización en pantalla dividida (*Split-Screen*) sincronizada espacial y temporalmente.
* **Desacoplamiento Estricto:** El frontend consume directamente contratos de datos en Apache Parquet y JSON generados por el pipeline de simulación.
