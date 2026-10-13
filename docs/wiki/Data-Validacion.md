# Validación de Datos, Calidad y Diagnóstico

Esta página documenta los resultados empíricos de la auditoría de datos, la identificación de valores nulos, las inconsistencias detectadas y la guía de sustentación técnica.

---

## 1. Fase 1 — Auditoría Exhaustiva de Esquemas y Calidad

Para determinar la estructura real de los datos en bruto y evaluar la presencia de valores nulos o inconsistencias de formato, se ejecutó una inspección sobre archivos Parquet diarios de validaciones y salidas.

### 1.1 Validaciones Troncal

**Archivo:** `20260801.parquet`

| Aspecto | Resultado |
|---|---|
| **Volumen** | 1.233.383 registros por día |
| **Número de columnas** | 22 |
| **Campos 100% nulos** | `ID_Vehiculo`, `Ruta`, `Tipo_Vehiculo` |
| **Variables sin nulos** | `Fecha_Transaccion`, `Estacion_Parada`, `Linea`, `Nombre_Perfil`, `Acceso_Estacion`, `Day_Group_Type`, `Saldo_Previo_a_Transaccion`, `Saldo_Despues_Transaccion`, `Valor`, entre otras |

**Hallazgo:** Los campos `ID_Vehiculo`, `Ruta` y `Tipo_Vehiculo` se encuentran completamente vacíos en el componente troncal.

### 1.2 Salidas Troncal / Torniquetes

**Archivo:** `20260825.parquet`

| Aspecto | Resultado |
|---|---|
| **Volumen** | 132.856 registros agregados |
| **Número de columnas** | 8 |
| **Valores nulos** | 0,0% |

**Hallazgo:** Presenta una integridad del 100%, sin valores nulos en la totalidad de sus campos.

---

## 2. Fase 2 — Exploración de Patrones y Valores Categóricos

A partir de los resultados de la auditoría inicial, se ejecutó un segundo script enfocado en analizar la cardinalidad, los dominios de valores y los formatos de las columnas categóricas.

### 2.1 Hallazgos

#### `Hora_Pico_SN`

La columna `Hora_Pico_SN` no utiliza valores binarios (`S`/`N`), sino cadenas en inglés:

- `Peak Time`
- `Non Peak Time`

#### Componente del sistema

El sistema reporta el **100% de los registros con el valor `TRONCAL`**, confirmando que no existen datos mezclados correspondientes al componente zonal del SITP.

#### Inconsistencias textuales entre tablas

Se identificaron diferencias en la representación de los nombres de las estaciones.

**Tabla de Validaciones:**

```text
(08000) Portal Tunal
```

## 3. Fase 3 — Análisis de Reducción Dimensional y Matriz de Utilidad

Con base en la auditoría técnica y los requisitos del modelo, se estructuró la matriz de decisión sobre las **22 columnas de validaciones** y las **8 columnas de salidas**.

### 3.1 Matriz de Utilidad de Variables

| Columna | Origen | Estado | Decisión Técnica | Justificación para el Modelo / IA |
|---|---|---|---|---|
| `Fecha_Transaccion` | Ambas | Conservada | Indispensable | Marca temporal para construir la serie de tiempo `t`. |
| `Estacion_Parada` / `Estacion` | Ambas | Transformada | Indispensable | Se usa para extraer el código de estación `s`. |
| `Tiempo` | Salidas | Conservada | Indispensable | Franja horaria de agregación en salidas. |
| `Entradas_E` / `Salidas_S` | Salidas | Conservada | Indispensable | Conteo neto de flujo en torniquetes. |
| `Hora_Pico_SN` | Validaciones | Conservada | Secundaria | Clasificador del régimen de demanda. |
| `Day_Group_Type` | Validaciones | Conservada | Secundaria | Distinción entre días hábiles y fines de semana. |
| `Linea` / `Acceso_Estacion` | Ambas | Conservada | Secundaria | Ubicación física e infraestructura del acceso. |
| `Nombre_Perfil` | Validaciones | Conservada | Secundaria | Tipo de usuario (General, Adulto Mayor, Discapacidad). |
| `ID_Vehiculo` / `Ruta` | Validaciones | Eliminada | Inútil (`100%` Nulo) | Sin datos en el componente troncal. |
| `Saldo_Previo_a_Transaccion` | Validaciones | Eliminada | Ruidos Financieros | Variables bancarias ajenas a la física del tráfico. |
| `Valor` / `Tipo_Tarifa` | Validaciones | Eliminada | Ruidos Financieros | No aportan a la estimación de colas `Q(t)`. |

---

## 4. Fase 4 — Hallazgos Clave y Prueba de Normalización

### 4.1 Hallazgos de Arquitectura

#### Hallazgo 1 — Código de 5 Dígitos

Todas las estaciones en ambas fuentes comienzan con un patrón numérico de **5 dígitos en paréntesis**:

`(XXXXX)`

Se descartó el procesamiento de texto difuso (*fuzzy matching*) a favor de extraer esta llave primaria determinista en `O(1)`.

#### Hallazgo 2 — Convención Geográfica

Los dos primeros dígitos del código representan la zona o troncal:

| Código | Zona / Troncal |
|---|---|
| `01 / 02` | Autonorte |
| `03` | Suba |
| `04` | Calle 80 |
| `05` | Américas |
| `06` | Calle 26 |
| `07` | NQS Sur |
| `08` | Caracas Sur |
| `09 / 10` | Carrera 10 |

Además, la terminación:

`000`

corresponde a **Portales**.

### 4.2 Prueba de Normalización

Para validar la función **Regex** encargada de la extracción del código y limpieza textual, se ejecutó la siguiente prueba técnica.

#### Objetivo

La prueba busca validar la función encargada de:

1. Extraer el código de estación de 5 dígitos.
2. Separar el código del nombre de la estación.
3. Normalizar la información proveniente de las diferentes fuentes.
4. Permitir una identificación determinista de las estaciones.

> **Nota:** En la información disponible se documenta que se ejecutó la prueba técnica de Regex, pero no se incluye el código específico de la expresión regular ni el resultado detallado de la prueba.
