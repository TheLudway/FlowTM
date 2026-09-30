# FlowTM: Gemelo Digital y Centro de Control Operativo (OCC)

![FlowTM OCC](https://img.shields.io/badge/FlowTM-Simulador%20Avanzado-0E1117?style=for-the-badge&logo=python&logoColor=58A6FF)
![Status](https://img.shields.io/badge/Estado-Operativo-43A047?style=for-the-badge)

**FlowTM** es un simulador avanzado impulsado por Inteligencia Artificial y agentes racionales diseñado para el modelamiento matemático riguroso de sistemas BRT (Bus Rapid Transit). Este proyecto incluye un **Centro de Control de Operaciones (OCC)** en tiempo real que permite auditar telemetría geoespacial, reproducir la evolución de colas en andenes y visualizar la flota de buses de manera interactiva.

---

## 📐 Arquitectura y Modelamiento Matemático

A diferencia de los modelos basados en mallas celulares simples, **FlowTM** garantiza la fidelidad de sus simulaciones a través de un ecosistema de 7 modelos matemáticos y físicos acoplados. A continuación, documentamos la fundamentación teórica de nuestro motor de simulación en **SimPy**.

### 1. Generación de Pasajeros: Proceso de Poisson No Homogéneo (NHPP)
**La Ecuación (Transformada Inversa de la Exponencial):**
$$\Delta t = - \frac{\ln(U)}{\lambda(s, t)}, \quad \text{donde } U \sim \text{Uniforme}(0, 1)$$

* **¿Por qué?** Las personas no llegan a una estación en intervalos de tiempo fijos, ni tampoco llegan todos de golpe. Llegan en ráfagas aleatorias e independientes. Al ser "no homogéneo", la tasa de intensidad $\lambda(s, t)$ varía según la hora del día (ej. picos de demanda a las 07:00 a.m.).
* **Uso en el motor:** Dentro del bucle de SimPy (`yield env.timeout(delta_t)`), esta fórmula calcula cuántos segundos esperar antes de inyectar al siguiente pasajero virtual al andén.

### 2. Dinámica de Colas en Andén: Ecuación en Diferencias Finitas ($Q(t)$)
**La Ecuación (Balance de Masa / Colas de Vickrey-Newell):**
$$\frac{dQ_s(t)}{dt} = \lambda_s(t) - \mu_s(t) \quad \longrightarrow \quad Q_s(k + 1) = \max\Big(0, \; Q_s(k) + \text{Llegadas}_s(k) - \text{Abordajes}_s(k)\Big)$$

* **¿Por qué?** Ley de conservación de flujo en un sistema abierto: la fila actual es igual a la fila anterior, más los usuarios que pasaron los torniquetes, menos los que lograron abordar un bus. Operamos con $\max(0, \dots)$ dado que físicamente no existen "personas negativas".
* **Uso en el motor:** Se actualiza la memoria del andén y se acumula el tiempo total de espera para obtener el promedio: $\bar{W} = \frac{\sum Q_s(k) \cdot \Delta t_k}{N_{\text{pax}}}$

### 3. Matriz Origen-Destino: Modelo de Atracción Proporcional
**La Ecuación:**
$$P(\text{bajar en estación } j \mid \text{subió en } i) = \frac{\text{Salidas\_S}_j}{\sum_{k > i} \text{Salidas\_S}_k}$$

* **¿Por qué?** Los buses BRT no cuentan con torniquetes a bordo. La inferencia física asume que una estación atrae descensos proporcionalmente a su volumen histórico de desocupación (validaciones de salida).
* **Uso en el motor:** Al entrar al sistema, se asigna al agente pasajero un destino inmutable siguiendo esta distribución probabilística. Al llegar a dicha estación, el pasajero desciende automáticamente.

### 4. Elección de Ruta: Algoritmo de Líneas Atractivas (Spiess & Florian)
**La Lógica:**
$$\text{Capacidad Disponible: } C_{\text{disp}} = \max(0, \; C_{\text{max}} - \text{Pax\_a\_bordo})$$
$$\text{Abordan: } \min(\text{Pax\_Aptos\_en\_Cola}, \; C_{\text{disp}})$$

* **¿Por qué?** Permite distinguir entre *pasajeros cautivos* (que se dirigen a estaciones donde solo operan rutas corrientes) y *pasajeros con opción* (que abordan el primer bus expreso con cupo).
* **Uso en el motor:** El bus filtra la cola del andén para abordar únicamente a quienes les sirve esa ruta, hasta agotar su cupo nominal ($160$ pax).

### 5. Tiempo de Detención en Plataforma (Dwell Time)
**La Ecuación:**
$$T_{\text{dwell}} = t_{\text{puertas}} + \max(\beta_{\text{sub}} \cdot P_{\text{suben}}, \; \beta_{\text{baj}} \cdot P_{\text{bajan}})$$
$$\text{Parámetros: } t_{\text{puertas}} = 10.0\text{ s}, \quad \beta_{\text{sub}} = 1.2\text{ s/pax}, \quad \beta_{\text{baj}} = 1.0\text{ s/pax}$$

* **¿Por qué?** La detención de un bus no es un tiempo fijo aleatorio. Se compone del tiempo mecánico de apertura de puertas más el flujo paralelo de personas subiendo y bajando.
* **Uso en el motor:** Modela la retención temporal de los recursos físicos limitados de las estaciones (`simpy.Resource`). Si un abordaje masivo dura demasiado, se bloquea la bahía, desencadenando propagación de retrasos (Bus Bunching).

### 6. Cinemática Geodésica: Fórmula de Haversine
**La Ecuación:**
$$d(i, i+1) = 2 R \cdot \operatorname{atan2}(\sqrt{a}, \sqrt{1 - a}), \quad R = 6.371.000\text{ m}$$
$$\Delta t_{\text{viaje}} = \frac{d}{v_{\text{comercial}}} + t_{\text{semáforos}} = \frac{d}{6.11\text{ m/s}} + 15.0\text{ s}$$

* **¿Por qué?** Sustituye las distancias arbitrarias por cálculos geodésicos precisos considerando la curvatura terrestre, usando las coordenadas GPS oficiales (GeoJSON).
* **Uso en el motor:** Determina los tiempos de viaje interpolados entre paradas basados en la velocidad comercial metropolitana real de 22 km/h.

### 7. El Optimizador: Recocido Simulado (Simulated Annealing)
**Las Ecuaciones:**
$$\text{Función de Utilidad: } U(S) = - \Big[ w_1 \bar{W} + w_2 (\text{Sobrecupo}_{95\%})^{1.5} + w_3 Q_{\text{remanente}} + w_4 B_{\text{usados}} \Big]$$
$$\text{Criterio Metrópolis: } P(\text{aceptar}) = \exp\left(\frac{\Delta U}{T_k}\right) \quad \mid \quad \text{Enfriamiento: } T_{k+1} = 0.88 \cdot T_k$$

* **¿Por qué?** La programación de frecuencias de flota es un problema NP-Duro que no admite derivadas directas.
* **Uso en el motor:** Es el "cerebro" del Agente Racional. Modifica heurísticamente los horarios de despacho y castiga severamente el hacinamiento extremo, escapando de mínimos locales para reducir drásticamente los tiempos de espera con la misma capacidad instalada.

---

## 🏛️ Arquitectura de Software y Patrones de Diseño

Implementamos una Arquitectura Híbrida de Datos apoyada en los principios de Clean Architecture. 

### 1. Desacoplamiento Estricto
La lógica de negocio y las ecuaciones físicas (`domain` y `simulation`) son completamente agnósticas de la interfaz gráfica (`presentation`). Si en el futuro se reemplaza Streamlit por una aplicación web en React o Vue, el motor del simulador (SimPy) correrá exactamente igual. Toda la carga de datos se realiza a través del **Repository Pattern** In-Memory, consumiendo archivos `.parquet` comprimidos con Zstandard (ZSTD) y operados nativamente por `polars`.

### 2. Árbol de Directorios (Módulos Principales)
```text
src/flowtm/
├── domain/                          # Entidades puras de negocio
│   ├── models.py                    # Dataclasses: Pasajero, Bus, Estacion
│   └── state.py                     # ScheduleState (Vector de frecuencias)
├── simulation/                      # Física y eventos discretos (SimPy)
│   ├── engine.py                    # SimuladorCorredor (Procesos)
│   ├── collector.py                 # Colector de telemetría (Observer)
│   └── dwell_time.py                # Modelo empírico de tiempo de parada
├── optimization/                    # Inteligencia Artificial
│   ├── simulated_annealing.py       # Optimizador con enfriamiento geométrico
│   └── utility.py                   # Función de utilidad multiobjetivo U(S)
├── infrastructure/                  # Persistencia y acceso a datos
│   └── repositories/                
│       └── data_repository.py       # Patrón Repositorio (ParquetDataRepository)
└── presentation/                    # Interfaz de usuario
    └── dashboard/
        └── app.py                   # Centro de Control de Operaciones (OCC)
```

### 3. Patrones de Diseño Implementados

* **Observer Pattern (Patrón Observador):**
  * *Dónde:* `MetricsCollector` en `src/flowtm/simulation/collector.py`.
  * *Cómo funciona:* El motor de SimPy ejecuta la física de buses y pasajeros de forma pura. Cada vez que un bus arriba, sube gente o cambia de coordenada, emite un evento al Collector, que registra la telemetría en series temporales sin interferir ni hacer más lenta la física.

* **Repository Pattern (Patrón Repositorio):**
  * *Dónde:* `DataRepository` en `infrastructure/repositories/`.
  * *Cómo funciona:* El Dashboard y el Simulador nunca abren rutas de disco directamente ni hacen queries crudas. Invocan a la interfaz del repositorio, abstrayendo si la telemetría viene de Pandas, Polars, o un servicio en la nube.

* **State Pattern & Inmutabilidad:**
  * *Dónde:* `ScheduleState` en `src/flowtm/domain/state.py`.
  * *Cómo funciona:* El vector de frecuencias se encapsula en un objeto inmutable. El optimizador genera transiciones de estado ($S \to S'$) mediante copias clonadas con perturbación estocástica, permitiendo descartar ramificaciones fallidas sin alterar la memoria del proceso.

* **Strategy Pattern:**
  * *Dónde:* En la política de evaluación `SimuladorCorredor.simular()`.
  * *Cómo funciona:* El motor de eventos discretos recibe un diccionario genérico de frecuencias. Ejecuta ciegamente la estrategia oficial (GTFS actual) o la estrategia perturbada (IA) sin tener que modificar una sola línea del motor físico de los buses.

* **Resource Pooling (Gestión Concurrente):**
  * *Dónde:* `simpy.Resource(capacity=2)` en la definición de Estaciones.
  * *Cómo funciona:* Modela las bahías físicas de parada como semáforos de exclusión mutua limitados. Garantiza que si dos buses están abordando en plataforma, un tercer bus tendrá que formar cola en el carril exclusivo (Bus Bunching real).

---
*Desarrollado y optimizado como componente núcleo de FlowTM.*
