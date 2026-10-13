# 05. Guía de Instalación, Pipelines y Reproducibilidad

Esta guía proporciona los procedimientos detallados para clonar, configurar, ejecutar y validar el Gemelo Digital **FlowTM** de forma completamente reproducible desde cualquier terminal compatible.

---

## 1. Requisitos del Sistema y Entorno

Para garantizar un rendimiento óptimo en el procesamiento de datos y la simulación física, se recomienda el siguiente entorno:

| Componente | Requisito Mínimo | Requisito Recomendado |
| :--- | :--- | :--- |
| **Sistema Operativo** | Linux (Ubuntu 22.04 LTS) o Windows 10/11 con WSL2 | Ubuntu 24.04 LTS nativo / WSL2 |
| **Python** | Python 3.12.x | Python 3.12+ gestionado con [`uv`](https://docs.astral.sh/uv/) |
| **Node / JavaScript** | Node.js 20.x o superior | [`Bun`](https://bun.sh/) 1.1+ (o Node.js 22 LTS con `npm`) |
| **Memoria RAM** | 4 GB | 8 GB o superior (para operaciones in-memory en Polars) |
| **Almacenamiento** | 2 GB de espacio libre en disco | SSD con soporte NVMe |

---

## 2. Instalación y Configuración del Entorno

### 2.1. Clonación del Repositorio
```bash
git clone https://github.com/KevinAPN/FlowTM.git
cd FlowTM
```

### 2.2. Configuración del Backend con `uv` (Recomendado)
[`uv`](https://docs.astral.sh/uv/) es el gestor de paquetes y entornos virtuales de Python de ultra-alto rendimiento desarrollado en Rust.

```bash
# 1. Instalar uv (si no está instalado en el sistema)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Sincronizar el entorno virtual e instalar todas las dependencias del proyecto
uv sync

# 3. Verificar que el entorno virtual está activo y funcional
uv run python --version
```

*(Alternativa tradicional con pip)*:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2.3. Configuración del Frontend con `bun`
```bash
cd frontend
bun install

# O alternativamente con npm:
# npm install

cd ..
```

---

## 3. Flujo de Ejecución de Pipelines y Simulación

La reproducción completa del Gemelo Digital se estructura en tres scripts secuenciales numerados en la carpeta `scripts/`:

```
┌─────────────────────────────────┐
│ 01_preparar_escenario.py       │ ──> Ingesta Big Data TuLlave y GTFS Oficial
└────────────────┬────────────────┘     Genera Parquets comprimidos ZSTD en data/processed/
                 ▼
┌─────────────────────────────────┐
│ 02_correr_simulador_base.py     │ ──> Ejecuta SimPy sobre Escenario Base (106 buses)
└────────────────┬────────────────┘     Genera telemetría base en frontend/public/data/
                 ▼
┌─────────────────────────────────┐
│ 03_optimizar_frecuencias.py     │ ──> Agente Racional IA: Recocido Simulado (96 buses)
└────────────────┬────────────────┘     Genera telemetría opt, kpis_comparativa y frequencies.txt
                 ▼
┌─────────────────────────────────┐
│ frontend/ (Bun Dev)             │ ──> Centro de Control de Operaciones OCC a 60 FPS
└─────────────────────────────────┘
```

---

### Paso 1: Preparación del Escenario y Limpieza de Datos
Procesa las validaciones empíricas del sistema de recaudo (*tullave*) y los shapes/estaciones del GTFS oficial de TransMilenio, generando los artefactos Parquet con compresión Zstandard:

```bash
uv run python scripts/01_preparar_escenario.py
```
* **Entradas:** Archivos brutos en `data/raw/` o tablas de demanda histórica.
* **Salidas generadas:** 
  * `data/processed/tasas_arribo_15m.parquet` ($\lambda(s, t)$ en ventanas de 15 minutos).
  * `data/processed/probabilidades_descenso.parquet` (Matriz OD empírica).
  * `data/processed/estaciones_calibradas.parquet` (Geometrías y nombres normalizados).

---

### Paso 2: Ejecución del Simulador en Escenario Base (GTFS Vigente)
Ejecuta la simulación física de 3 horas de operación continua (06:00 a 09:00 AM) bajo las frecuencias actuales estáticas:

```bash
uv run python scripts/02_correr_simulador_base.py
```
* **Parámetros del escenario:** Frecuencias de despacho según `frequencies.txt` base (consumo total de 106 buses físicos).
* **Salidas generadas:**
  * `frontend/public/data/telemetria_base/telemetria_optimizada.parquet` (7,800+ registros de telemetría vehicular continua).
  * Reporte tabular en consola de tiempo medio de espera, factor de ocupación y colas en andén.

---

### Paso 3: Optimización Heurística con el Agente Racional IA
Ejecuta el algoritmo de Recocido Simulado para maximizar la función de utilidad $U(S)$ bajo la restricción física de flota $B_{\text{total}} \le 106$:

```bash
uv run python scripts/03_optimizar_frecuencias.py
```
* **Proceso de optimización:**
  * Búsqueda estocástica en $\mathbb{R}^6$ sobre el vector de headways $\mathbf{h}$.
  * Enfriamiento geométrico con criterio de aceptación Metropolis-Hastings.
  * Evaluación por simulación estocástica en tiempo real de cada propuesta candidata.
* **Salidas generadas:**
  * `frontend/public/data/telemetria_opt/telemetria_optimizada.parquet` (Telemetría de alta resolución del escenario optimizado).
  * `frontend/public/data/kpis_comparativa.json` (Matriz comparativa de KPIs base vs optimizado para el dashboard de analítica).
  * `data/processed/frequencies_optimizado.txt` (Archivo GTFS oficial listo para despliegue operacional).

---

### Paso 4: Exportación Específica del Estándar GTFS (Opcional)
Si se desea regenerar o validar únicamente el archivo estándar de frecuencias:

```bash
uv run python scripts/exportar_gtfs_ia.py
```
* Valida la estructura de columnas requerida por MobilityData:
  `trip_id,start_time,end_time,headway_secs,exact_times`.

---

## 4. Puesta en Marcha del Frontend OCC

Una vez generados los datos de telemetría, se inicia el servidor de desarrollo local del Centro de Control:

```bash
cd frontend
bun run dev
```

La consola mostrará:
```text
  VITE v6.x.x  ready in 180 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

Abra su navegador web en `http://localhost:5173/`. Desde allí podrá:
1. Navegar por el corredor Caracas-Autonorte con el visor MapLibre GL a 60 FPS.
2. Controlar la barra de reproducción temporal (`Play`, `Pausa`, `Velocidad 1x-30x`, `Scrubber`).
3. Activar el modo de **Pantalla Dividida (Split-Screen)** para contrastar el escenario base contra el optimizado por IA.
4. Inspeccionar la telemetría vehicular en vivo haciendo clic sobre cualquier bus.
5. Consultar la pestaña de **Analítica y KPIs** para revisar el reporte pedagógico de 4 fases y descargar el archivo `frequencies.txt`.

---

## 5. Ejecución de la Suite de Pruebas Automatizadas

El proyecto cuenta con una batería de pruebas unitarias y de integración desarrolladas con `pytest`, asegurando que todas las ecuaciones físicas, modelos estocásticos y restricciones de negocio mantengan su integridad:

```bash
uv run pytest tests -v
```

### Cobertura de las Pruebas
* `test_models.py`: Validación de tipos de datos, dataclasses de dominio y cálculo de factores de ocupación vehicular.
* `test_poisson.py`: Verificación estadística del proceso de Poisson no homogéneo (generación de intervalos $\Delta t$ con la transformada inversa).
* `test_dwell_time.py`: Comprobación del modelo TCQSM de dwell time (tiempos mínimos de apertura de puertas y tasa de abordaje de 1.2 s/pax).
* `test_simulated_annealing.py`: Verificación de la convergencia del algoritmo heurístico y respeto estricto de la cota $B \le 106$.
* `test_gtfs_exporter.py`: Validación sintáctica del formato GTFS exportado contra las especificaciones internacionales.

Resultado esperado:
```text
======================== 10 passed in 0.45s =========================
```

---

## 6. Estructura de Directorios del Repositorio

```text
FlowTM/
├── data/
│   ├── processed/                   # Datasets procesados en formato Parquet ZSTD
│   │   ├── estaciones_calibradas.parquet
│   │   ├── probabilidades_descenso.parquet
│   │   ├── tasas_arribo_15m.parquet
│   │   └── frequencies_optimizado.txt
│   └── raw/                         # Archivos fuente GTFS y validaciones TuLlave
├── docs/
│   └── wiki/                        # Documentación académica oficial para GitHub Wiki
│       ├── Home.md                  # Portada y ficha técnica
│       ├── 01-Fundamentacion-Matematica-y-Modelado-Fisico.md
│       ├── 02-Arquitectura-de-Software-y-Patrones.md
│       ├── 03-Agente-IA-y-Optimizacion-Heuristica.md
│       ├── 04-Centro-de-Control-OCC-y-Frontend-Web.md
│       ├── 05-Guia-de-Instalacion-y-Reproducibilidad.md
│       ├── _Sidebar.md              # Menú lateral para la Wiki de GitHub
│       └── _Footer.md               # Pie de página y créditos
├── frontend/                        # Interfaz gráfica React 19 + MapLibre GL
│   ├── public/
│   │   └── data/                    # Telemetría Parquet consumida por la app web
│   │       ├── telemetria_base/
│   │       ├── telemetria_opt/
│   │       └── kpis_comparativa.json
│   ├── src/
│   │   ├── components/              # Header, MapViewport, InspectorModal, KpiPanel, etc.
│   │   ├── App.tsx                  # Orquestador del estado y vistas
│   │   └── App.css                  # Sistema de diseño con tokens CSS HSL
│   ├── package.json
│   └── vite.config.ts
├── scripts/                         # Pipelines de datos, simulación y optimización
│   ├── 01_preparar_escenario.py
│   ├── 02_correr_simulador_base.py
│   ├── 03_optimizar_frecuencias.py
│   └── exportar_gtfs_ia.py
├── src/
│   └── flowtm/                      # Paquete Python del núcleo (Clean Architecture)
│       ├── domain/                  # Entidades puras (models, state)
│       ├── simulation/              # Motor SimPy (engine, collector, dwell_time)
│       ├── optimization/            # IA Heurística (simulated_annealing, utility)
│       └── infrastructure/          # Repositorios y exportadores GTFS
├── tests/                           # Suite de pruebas automatizadas con pytest
├── pyproject.toml                   # Especificación de dependencias del proyecto (uv/pip)
└── README.md                        # Presentación principal del repositorio en GitHub
```
