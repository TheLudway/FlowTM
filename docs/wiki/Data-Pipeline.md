# Pipeline de la data (Procesamiento y Transformación)


Esta página documenta la lógica del pipeline ETL de producción diseñado para transformar los archivos en bruto en tablas canónicas optimizadas.

---

<br>

## Datos de Validaciones / Salidas Troncal

## 1. Arquitectura de Ingesta y Limpieza



El pipeline procesa en lote los archivos `.parquet` ubicados en `data/processed/validaciones_salidas/` mediante la API de evaluación perezosa (*Lazy Evaluation*) de Polars (`scan_parquet`), aplicando la reducción dimensional estricta y exportando las tablas canónicas a data/processed/clean/

---

<br>

## 2. Reducción Dimensional de Columnas

Para optimizar el rendimiento computacional del modelo, se aplicó un filtro estricto de variables:

### A. Validaciones Troncal
* **Reducción:** De 22 a 9 columnas clave (`Fecha_Transaccion`, `Hora_Pico_SN`, `Day_Group_Type`, `Linea`, `Nombre_Perfil`, `Acceso_Estacion`, `CODIGO_ESTACION`, `CODIGO_TRONCAL`, `NOMBRE_ESTACION_CANONICO`).
* **Variables descartadas:** Campos 100% nulos (`ID_Vehiculo`, `Ruta`, `Tipo_Vehiculo`) y variables de recaudo bancario (`Saldo_Previo_a_Transaccion`, `Saldo_Despues_Transaccion`, `Valor`, `Fecha_Clearing`, `Dispositivo`, `Emisor`, `Sistema`, `Fase`, `Tipo_Tarifa`, `Tipo_Tarjeta`).

### B. Salidas Troncal / Torniquetes
* **Reducción:** Conservación y estandarización de las 8 columnas de origen (`Fecha_Transaccion`, `Tiempo`, `Linea`, `Acceso_Estacion`, `Entradas_E`, `Salidas_S`, `CODIGO_ESTACION`, `CODIGO_TRONCAL`, `NOMBRE_ESTACION_CANONICO`)[cite: 1].

---

<br>

## 3. Función Vectorizada de Normalización de Estaciones

Se formuló una función Regex en Polars que realiza la estandarización sin requerir joins de texto ni procesamiento difuso (*fuzzy matching*):

1. **`CODIGO_ESTACION`:** Extrae el código numérico exacto de 5 dígitos que actúa como llave primaria determinista $O(1)$.
2. **`CODIGO_TRONCAL`:** Extrae los primeros 2 dígitos para identificar la zona u escala geográfica.
3. **`NOMBRE_ESTACION_CANONICO`:** Remueve el código inicial, transforma el texto a mayúsculas sostenidas, remueve diacríticos (`Á`, `É`, `Í`, `Ó`, `Ú`, `Ü`), estandariza guiones tipográficos (`–`, `—`) y elimina espacios sobrantes.

---

<br>

## 4. Script de Automatización ETL en Producción

La lógica de limpieza está diseñada para ser empaquetada en un script ejecutable dentro del repositorio (`src/flowtm/etl/clean_validaciones_salidas.py`). Al ejecutarse, este módulo realiza la lectura, transformación y persistencia automática de los datos limpios.

### Flujo de Ejecución del Script:
1. Escaneo lazy iterativo de los conjuntos en `data/processed/validaciones_salidas/validacion_troncal` y `salidas_troncal`.
2. Identificación dinámica de la columna de estación (`Estacion_Parada` o `Estacion`).
3. Aplicación de las expresiones vectorizadas de normalización y reducción dimensional.
4. Ejecución del plan de consulta mediante `collect()` y guardado automático en formato Parquet con compresión `zstd` en `data/processed/clean/`.

---




---

<br>

## Diagrama de Arquitectura ETL

```mermaid
graph TD
    A[Validaciones - 22 columnas] --> C[Worker Ingesta Parquet]
    B[Salidas / Torniquetes - 8 columnas] --> C

    C --> D

    subgraph D [Pipeline Vectorizado en Polars - Lazy Evaluation]
        D1[1. Reducción dimensional: Selección de columnas indispensables]
        --> D2[2. Normalización de estaciones: Extracción del código de 5 dígitos]
        --> D3[3. Generación de Nombre Canónico: Eliminación de tildes y caracteres]
    end

    D --> E[Exportación a Parquet Compreso - algoritmo zstd]
    E --> F[Ruta: data/processed/clean/tabla/*.parquet]
