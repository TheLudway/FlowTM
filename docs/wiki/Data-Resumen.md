# Resumen Data

Esta página documenta la arquitectura de ingeniería de datos, el flujo ETL y los scripts de exploración técnica desarrollados para el componente de Ingesta, Limpieza y Estandarización de Datos Abiertos de TransMilenio.

FlowTM combina dos familias de datos para que el Agente Racional pueda proponer ajustes a la planificación GTFS de TransMilenio:

1. **Datos de demanda** (Validaciones y Salidas Troncal): describen cuántos pasajeros entran y salen de cada estación, minuto a minuto.

2. **Datos de oferta** (GTFS): describen qué rutas y frecuencias están programadas actualmente.

<br>

---

<br>

## Datos de Validaciones / Salidas Troncal

**Fuente:** [Portal de Datos Abiertos de TransMilenio](https://datosabiertos-transmilenio.hub.arcgis.com/)


## 1. Alcance Técnico del Componente

El componente de datos procesa y estandariza los conjuntos de datos abiertos de TransMilenio. Para que el Agente Racional de Inteligencia Artificial (FlowTM) tome decisiones óptimas de despacho y calcule con precisión la tasa de llegada de pasajeros ($\lambda$) por estación y franja horaria, es imperativo contar con datos limpios, consistentes y formalmente tipados.

A continuación se detalla la metodología científica y los resultados de la auditoría de calidad de datos, la exploración de patrones empíricos, el diagnóstico de valores nulos e inconsistencias, la formulación de la función de estandarización canónica y el pipeline definitivo de limpieza implementado sobre los conjuntos de datos.

---

<br>

## 2. Fuentes de Información

| Dataset | Qué mide | Columnas originales | Volumen | Ubicación en Repositorio |
|---|---|:---:|:---:|---|
| **Validación Troncal (Abordajes)** | Cada tap de entrada de un usuario a una estación (transacción individual) | 22 | ~1.233.383 filas / día | `data/processed/validaciones_salidas/validacion_troncal` |
| **Salidas Troncal (Torniquetes)** | Conteo de entradas y salidas por estación, agregado por minuto | 8 | ~132.856 filas / archivo | `data/processed/validaciones_salidas/salidas_troncal` |


