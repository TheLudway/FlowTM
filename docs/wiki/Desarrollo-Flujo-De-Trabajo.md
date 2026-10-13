# Flujo de trabajo de desarrollo

## Python

Esta sección define las convenciones y el flujo de trabajo para desarrollar código Python en FlowTM. El objetivo es mantener un código consistente, legible, mantenible y compatible con las herramientas utilizadas por el proyecto.

### 1. Versión de Python

FlowTM utiliza **Python 3.12** como versión objetivo.

El código debe ser compatible con Python 3.12 y aprovechar las características modernas del lenguaje cuando mejoren la claridad o mantenibilidad del código.

La versión objetivo está definida en `pyproject.toml` mediante Ruff:

```toml
[tool.ruff]
target-version = "py312"
```

### 2. Convenciones de idioma

El código fuente utiliza **inglés** como idioma principal.

Esto aplica a:

* Funciones.
* Variables.
* Clases.
* Constantes.
* Módulos.
* Comentarios.
* Docstrings.

Los **logs y mensajes mostrados durante la ejecución** deben estar en español.

Por ejemplo:

```python
def convert_something(variable_important: int) -> int:
    """Convert an important variable."""
    print("[ERROR] No se puede convertir")
    return 2
```

En este caso:

* `convert_something` está en inglés.
* `variable_important` está en inglés.
* El docstring está en inglés.
* El mensaje mostrado al usuario está en español.

Esta separación debe mantenerse de manera consistente en todo el proyecto.

### 3. Nombres de funciones

Los nombres de las funciones deben estar en inglés y utilizar `snake_case`.

Los nombres deben describir claramente la operación que realiza la función.

Correcto:

```python
def normalize_station_name(station_name: str) -> str: ...


def load_gtfs_data(file_path: str): ...


def validate_station_ids(station_ids): ...
```

Evitar:

```python
def normalizar_nombre_estacion(nombre_estacion: str) -> str: ...


def cargar_datos_gtfs(ruta_archivo: str): ...
```

También se deben evitar abreviaciones innecesarias:

```python
# Preferible
station_count = len(stations)

# Evitar
sc = len(stations)
```

Las abreviaciones ampliamente establecidas en el dominio pueden utilizarse cuando aporten claridad, por ejemplo `gtfs`, `id`, `api`, `url` o `df`.

### 4. Nombres de variables

Las variables deben estar en inglés y utilizar `snake_case`.

Correcto:

```python
station_id = 123
station_name = "Portal Norte"
route_name = "B14"
station_count = 42
```

Evitar:

```python
id_estacion = 123
nombre_estacion = "Portal Norte"
nombre_ruta = "B14"
cantidad_estaciones = 42
```

Los nombres deben representar el contenido de la variable y evitar nombres genéricos cuando exista una descripción más precisa.

Por ejemplo:

```python
# Preferible
station_dataframe = pl.read_parquet(file_path)

# Evitar
data = pl.read_parquet(file_path)
```

cuando el contexto no permita determinar claramente qué contiene `data`.

### 5. Funciones pequeñas y responsabilidades claras

Las funciones deben tener una responsabilidad bien definida.

Preferir varias funciones especializadas:

```python
def extract_station_ids(dataframe: pl.DataFrame) -> pl.Series: ...


def normalize_station_names(station_names: pl.Series) -> pl.Series: ...


def validate_station_ids(station_ids: pl.Series) -> bool: ...
```

en lugar de concentrar múltiples responsabilidades en una única función extensa.

Una función debe intentar:

1. Recibir datos claramente definidos.
2. Realizar una operación concreta.
3. Retornar un resultado claramente definido.
4. Evitar efectos secundarios innecesarios.

### 6. Type hints

Las funciones deben utilizar **type hints** para documentar los tipos de sus parámetros y valores de retorno.

Preferir:

```python
def calculate_distance(
    latitude: float,
    longitude: float,
) -> float: ...
```

sobre:

```python
def calculate_distance(latitude, longitude): ...
```

Los type hints también deben utilizarse para variables cuando mejoren la legibilidad o sean necesarios para aclarar estructuras complejas.

### 7. Docstrings

Los docstrings deben escribirse en inglés.

Deben explicar el propósito de una función cuando este no sea evidente por su nombre y firma.

```python
def normalize_station_name(station_name: str) -> str:
    """Normalize a station name for consistent comparisons."""
    ...
```

Para funciones más complejas, el docstring puede documentar parámetros, valores de retorno o comportamiento relevante.

No es necesario escribir docstrings que simplemente repitan de manera obvia el nombre de la función.

### 8. Comentarios

Los comentarios deben estar escritos en inglés.

Deben explicar **por qué** se realiza una operación cuando el motivo no sea evidente, en lugar de describir literalmente lo que hace el código.

Preferible:

```python
# Keep only the latest record because GTFS snapshots may contain duplicates.
latest_records = dataframe.unique(
    subset=["station_id"],
    keep="last",
)
```

Evitar comentarios redundantes:

```python
# Filter the dataframe
dataframe = dataframe.filter(...)
```

El código debe ser suficientemente claro para que los comentarios no tengan que explicar operaciones triviales.

### 9. Logs y mensajes

Los logs y mensajes destinados al usuario deben estar en **español**.

Se recomienda utilizar etiquetas consistentes para identificar el nivel del mensaje:

```python
print("[INFO] Cargando datos de estaciones...")
print("[INFO] Validación completada")
print("[ADVERTENCIA] Se encontraron estaciones duplicadas")
print("[ERROR] No se pudo cargar el archivo")
```

La convención es:

```text
[INFO]
[ADVERTENCIA]
[ERROR]
```

Los nombres utilizados dentro del código siguen estando en inglés:

```python
def load_station_data(file_path: str):
    """Load station data from a file."""

    print("[INFO] Cargando datos de estaciones...")
```

### 10. Uso de Polars

FlowTM utiliza **Polars** para el procesamiento de datos. Siempre que sea posible, las transformaciones deben realizarse utilizando sus expresiones vectorizadas en lugar de iterar manualmente sobre filas.

Preferir:

```python
station_ids = dataframe.select(pl.col("station_name").str.extract(r"\[(.*?)\]", 1))
```

sobre realizar un `for` para procesar individualmente cada fila cuando la operación pueda expresarse mediante Polars.

Las expresiones vectorizadas permiten aprovechar el modelo de ejecución de Polars y mantener las transformaciones de datos declarativas.

### 11. Ruff

Ruff es la herramienta utilizada por FlowTM para **linting, organización de imports y formateo** del código Python.

La configuración se encuentra en `pyproject.toml`.

#### 11.1. Longitud de línea

El proyecto utiliza una longitud de línea de 88 caracteres:

```toml
[tool.ruff]
line-length = 88
```

La regla `E501` está deshabilitada porque el formateador de Ruff administra automáticamente el formato de las líneas.

```toml
[tool.ruff.lint]
ignore = [
    "E501",
]
```

#### 11.2. Reglas de linting

FlowTM utiliza las siguientes categorías:

```toml
[tool.ruff.lint]
select = [
    "E",
    "W",
    "F",
    "I",
    "B",
    "UP",
    "SIM",
    "N",
    "A",
    "C4",
    "RET",
    "RUF",
]
```

Estas reglas cubren, entre otros aspectos:

| Regla | Propósito                           |
| ----- | ----------------------------------- |
| `E`   | Errores de estilo                   |
| `W`   | Advertencias de estilo              |
| `F`   | Errores detectados por Pyflakes     |
| `I`   | Organización de imports             |
| `B`   | Detección de patrones problemáticos |
| `UP`  | Modernización de sintaxis Python    |
| `SIM` | Simplificación de código            |
| `N`   | Convenciones de nombres             |
| `A`   | Uso de built-ins                    |
| `C4`  | Comprensiones                       |
| `RET` | Reglas relacionadas con `return`    |
| `RUF` | Reglas específicas de Ruff          |

### 12. Formateo

El código debe formatearse utilizando Ruff.

La configuración actual establece:

```toml
[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"
docstring-code-format = true
```

Por lo tanto, el código debe utilizar:

* Comillas dobles.
* Espacios para la indentación.
* El formato de terminación de línea correspondiente al entorno.
* Formateo de ejemplos de código incluidos en docstrings.

Para formatear el proyecto:

```bash
uv run ruff format .
```

Para comprobar si el código ya está correctamente formateado:

```bash
uv run ruff format --check .
```

### 13. Linting y correcciones automáticas

Para comprobar el código:

```bash
uv run ruff check .
```

Para aplicar las correcciones automáticas disponibles:

```bash
uv run ruff check --fix .
```

El flujo habitual antes de considerar terminado un cambio de código es:

```bash
uv run ruff check --fix .
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
```

El código debe quedar sin errores de linting y correctamente formateado.

### 14. Estructura de imports

Los imports deben mantenerse organizados mediante Ruff.

Por ejemplo:

```python
import json
from pathlib import Path

import polars as pl

from flowtm.pipeline import load_data
from flowtm.validation import validate_data
```

No se deben reorganizar manualmente los imports de una manera que contradiga la configuración de Ruff.

La configuración de isort utilizada por Ruff es:

```toml
[tool.ruff.lint.isort]
combine-as-imports = true
force-wrap-aliases = true
```

### 15. Código específico de notebooks

Los scripts Python asociados a notebooks se encuentran bajo:

```text
notebooks/
```

Para estos archivos existen excepciones específicas de Ruff:

```toml
[tool.ruff.lint.per-file-ignores]
"notebooks/**/*.py" = ["N803", "B018"]
```

Estas excepciones deben limitarse a los casos contemplados por la configuración y no utilizarse como mecanismo general para evitar las reglas de calidad del proyecto.

### 16. Flujo durante el desarrollo

El desarrollo de una nueva funcionalidad o transformación de datos debe seguir, en términos generales, este ciclo:

```text
Comprender el problema
        │
        ▼
Diseñar la transformación
        │
        ▼
Implementar en Python
        │
        ▼
Aplicar type hints
        │
        ▼
Revisar nombres y documentación
        │
        ▼
Ejecutar Ruff
        │
        ▼
Ejecutar pruebas
        │
        ▼
Revisar el resultado
        │
        ▼
Documentar cuando sea necesario
```

Durante la implementación se debe priorizar código sencillo, explícito y fácil de verificar antes que soluciones excesivamente complejas.

### 17. Checklist

Antes de considerar terminado un cambio de código Python:

```text
[ ] El código es compatible con Python 3.12.
[ ] Las funciones tienen nombres en inglés.
[ ] Las variables tienen nombres en inglés.
[ ] Las clases y constantes tienen nombres en inglés.
[ ] Los comentarios están en inglés.
[ ] Los docstrings están en inglés.
[ ] Los logs están en español.
[ ] Se utilizan type hints cuando corresponde.
[ ] Las funciones tienen responsabilidades claras.
[ ] Se utilizan expresiones vectorizadas de Polars cuando corresponde.
[ ] Ruff no reporta errores.
[ ] El código está formateado con Ruff.
[ ] No existen excepciones de Ruff innecesarias.
[ ] El código es legible y mantenible.
```
