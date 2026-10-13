# 01. Fundamentación Matemática y Modelado Físico del Gemelo Digital

**FlowTM** se fundamenta en un modelamiento analítico riguroso que abandona las aproximaciones estáticas y los modelos macroscópicos agregados. El comportamiento del corredor troncal emerge a través del acoplamiento de **ocho modelos matemáticos y físicos** ejecutados en tiempo continuo sobre el motor de eventos discretos **SimPy**.

---

## 1. Generación Estocástica de Pasajeros: Proceso de Poisson No Homogéneo (NHPP)

### Formulación Analítica
Los arribos de usuarios a cada estación troncal constituyen un Proceso de Poisson No Homogéneo (**Non-Homogeneous Poisson Process - NHPP**), caracterizado por una función de intensidad de llegadas dependiente del espacio y del tiempo $\lambda(s, t)$ (expresada en pasajeros por segundo).

El tiempo entre llegadas sucesivas $\Delta t$ se genera computacionalmente mediante el método de la **Transformada Inversa de la Función de Distribución Acumulada**:

$$\Delta t = - \frac{\ln(U)}{\lambda(s, t)}$$

* **Donde:**
  * $\Delta t$: Intervalo de tiempo estocástico hasta el arribo del siguiente usuario (segundos).
  * $U \sim \text{Uniforme}(0, 1)$: Variable aleatoria continua generada por el generador pseudoaleatorio Mersenne Twister.
  * $\lambda(s, t)$: Tasa empírica de llegadas en la estación $s$ durante la franja horaria de 15 minutos en la que se encuentra el reloj de simulación $t$.

### Demostración de la Transformada Inversa
Dado que la probabilidad de que el tiempo entre eventos sea menor o igual a $\Delta t$ bajo una tasa constante local $\lambda$ sigue una distribución exponencial:
$$F(\Delta t) = 1 - e^{-\lambda \Delta t} = U$$
Despejando $\Delta t$:
$$e^{-\lambda \Delta t} = 1 - U$$
$$-\lambda \Delta t = \ln(1 - U)$$
Dado que si $U \sim \text{Uniforme}(0, 1)$, entonces $(1 - U) \sim \text{Uniforme}(0, 1)$, se obtiene:
$$\Delta t = - \frac{\ln(U)}{\lambda}$$

### Calibración Empírica desde Big Data (*tullave*)
A partir de 44.93 millones de registros de validaciones en torniquetes, la tasa $\lambda(s, t)$ se extrae discretizada en bloques de 15 minutos entre las 04:00 y las 23:00. Para un intervalo de 15 minutos (900 segundos):
$$\lambda(s, t) = \frac{\text{ValidacionesPromedio}_{15\text{m}}(s, t)}{900\text{ segundos}}$$

---

## 2. Dinámica de Acumulación en Andén: Conservación de Flujo ($Q(t)$)

### Ecuación Diferencial Continua y Aproximación en Diferencias Finitas
La evolución de la cola de espera de pasajeros $Q_s(t)$ en el andén de la estación $s$ se modela mediante la ley de conservación de masa de Vickrey-Newell:

$$\frac{dQ_s(t)}{dt} = \lambda_s(t) - \mu_s(t)$$

En el espacio de simulación por eventos discretos de FlowTM, la actualización en cada instante de evento $k$ se rige por:

$$Q_s(k + 1) = \max\Big(0, \; Q_s(k) + \text{Llegadas}_s(k) - \text{Abordajes}_s(k)\Big)$$

* **Donde:**
  * $Q_s(t)$: Número entero de pasajeros esperando físicamente en la plataforma.
  * $\lambda_s(t)$: Tasa instantánea de entrada por torniquetes.
  * $\mu_s(t)$: Tasa de evacuación efectiva al momento de detenerse un bus y habilitar sus puertas.
  * El operador $\max(0, \dots)$ garantiza el cumplimiento del principio de no negatividad física del andén.

### Métrica de Espera Media Ponderada ($\bar{W}$)
El tiempo medio de espera que experimenta un usuario en el sistema se calcula a través de la integral de Riemann discreta de la cola sobre el tiempo:

$$\bar{W} = \frac{\sum_{k} Q_s(k) \cdot \Delta t_k}{N_{\text{total\_pasajeros}}}$$

---

## 3. Matriz Origen-Destino: Probabilidad Condicional de Atracción

### Formulación Bayesiana de Descenso
Cuando un pasajero es generado en la estación origen $i$, su estación destino $j$ se determina de forma probabilística utilizando la distribución empírica de descensos observada en los torniquetes de salida (*tap-out*):

$$P(\text{descenso en } j \mid \text{ascenso en } i) = \frac{\text{Salidas}_j}{\sum_{k > i} \text{Salidas}_k}, \quad \forall j > i$$

* **Donde:**
  * $\text{Salidas}_j$: Suma histórica de validaciones de salida en la estación $j$.
  * La condición $j > i$ refleja la unidireccionalidad del corredor modelado (sentido Sur $\rightarrow$ Norte en la punta matutina).
  * Al ingresar, cada pasajero es instanciado como un objeto inmutable `Passenger` portando su tupla de atributos `(id, origin_station, destination_station, arrival_time_sec)`.

---

## 4. Segregación de Colas: Demanda Corriente vs. Servicios Expresos

### Mecanismo de Selección de Servicio
En un sistema BRT troncal de alta capacidad, no todos los buses sirven a todas las estaciones. FlowTM modela dos sub-colas en cada estación $s$:
1. **$Q_{\text{corriente}}$:** Pasajeros que esperan rutas con parada local en la estación siguiente o inmediata.
2. **$Q_{\text{expreso}}$:** Pasajeros que tienen como destino estaciones lejanas o terminales y esperan exclusivamente servicios troncales semidirectos (`B18`, `B23`, `B27`, `B74`, `B75`).

Al arribar un bus de la ruta $r$ con itinerario de paradas programado $\mathcal{S}_r \subset \mathcal{S}_{\text{todas}}$, el conjunto de pasajeros elegibles para abordar es estrictamente:

$$Q_{\text{aptos}}(s, r) = \Big\{ p \in Q_s \;\mid\; p.\text{destination\_station} \in \mathcal{S}_r \Big\}$$

Los pasajeros cuyos destinos no estén incluidos en $\mathcal{S}_r$ **no abordan el bus**, permaneciendo en el andén bajo disciplina de servicio FIFO (*First-In, First-Out*).

---

## 5. Dinámica No Lineal de Permanencia en Bahía (*Dwell Time*)

### Modelo Estándar TCQSM (Transit Capacity and Quality of Service Manual)
El tiempo que un bus permanece detenido en la bahía de parada de una estación troncal no es una constante fija. Depende no linealmente de los flujos simultáneos de pasajeros que abordan y descienden a través de las puertas dobles del vehículo:

$$T_{\text{dwell}} = t_{\text{puertas}} + \max\Big(\beta_{\text{sub}} \cdot P_{\text{suben}}, \; \beta_{\text{baj}} \cdot P_{\text{bajan}}\Big)$$

* **Parámetros Calibrados:**
  * $t_{\text{puertas}} = 10.0\text{ s}$: Tiempo mecánico de apertura, advertencia sonora y cierre neumático de puertas.
  * $\beta_{\text{sub}} = 1.2\text{ s/pasajero}$: Tasa marginal de abordaje a través de puertas dobles a nivel de plataforma.
  * $\beta_{\text{baj}} = 1.0\text{ s/pasajero}$: Tasa marginal de descenso.
  * $P_{\text{suben}}$: Pasajeros que logran abordar el vehículo según la capacidad remanente.
  * $P_{\text{bajan}}$: Pasajeros que descienden en la estación actual.

### Acotamiento Operativo
Para evitar distorsiones numéricas y representar las condiciones físicas de despacho de TransMilenio, el tiempo de permanencia se acota a un intervalo operacional estricto:

$$T_{\text{dwell\_efectivo}} = \min\Big(75.0\text{ s}, \; \max(12.0\text{ s}, \; T_{\text{dwell}})\Big)$$

* Un bus sin movimiento de pasajeros requiere un mínimo de $12.0\text{ s}$ para detenerse y reiniciar la marcha.
* Por política de control operativo, ningún bus permanece más de $75.0\text{ s}$ bloqueando una bahía troncal.

---

## 6. Cinemática Geodésica Inter-Estación (Haversine)

### Cálculo de Distancia Geodésica WGS-84
Para garantizar que la simulación refleje con exactitud métrica el recorrido sobre la infraestructura de la Autopista Norte y la Avenida Caracas, la distancia física entre dos estaciones consecutivas $s_i$ y $s_{i+1}$ se calcula mediante la fórmula de Haversine:

$$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)$$

$$d(s_i, s_{i+1}) = 2 R \cdot \operatorname{atan2}\left(\sqrt{a}, \; \sqrt{1 - a}\right)$$

* **Donde:**
  * $R = 6.371.000\text{ metros}$ (radio medio de la Tierra).
  * $\phi_1, \phi_2$: Latitudes geodésicas en radianes.
  * $\Delta \phi = \phi_2 - \phi_1$, $\Delta \lambda = \lambda_2 - \lambda_1$.

### Tiempo de Viaje en Carril Segregado
El tiempo de tránsito entre estaciones en calzada exclusiva troncal se modela como:

$$\Delta t_{\text{viaje}}(s_i, s_{i+1}) = \frac{d(s_i, s_{i+1})}{v_{\text{comercial}}} + t_{\text{demora}}$$

* **Parámetros Calibrados:**
  * $v_{\text{comercial}} = 6.11\text{ m/s} \; (22.0\text{ km/h})$: Velocidad crucero en carril segregado de TransMilenio.
  * $t_{\text{demora}} = 15.0\text{ segundos}$: Pérdida de tiempo por desaceleración, aproximación a bahía y fases semafóricas intermedias.

---

## 7. Inestabilidad Dinámica y Pegamiento de Buses (*Bus Bunching*)

### El Círculo Vicioso del Retraso
El fenómeno de pegamiento de buses (*bus bunching*) es una inestabilidad inherente a los sistemas de transporte público de alta frecuencia. Se genera por una retroalimentación positiva:

```
Despacho con ligero retraso (Δh > 0)
        │
        ▼
Mayor acumulación de pasajeros en andén (ΔQ > 0)
        │
        ▼
Mayor tiempo de dwell time en estación (ΔT_dwell > 0)
        │
        ▼
El bus se retrasa aún más mientras el siguiente lo alcanza
        │
        ▼
PEGAMIENTO (BUNCHING) EN RACIMO
```

### Criterio Espacio-Temporal de Detección
En el gemelo digital, dos buses $A$ y $B$ de la misma ruta experimentan *bunching* si su separación euclidiana geodésica desciende por debajo del umbral crítico:

$$\text{distancia}(A, B) < 420\text{ metros} \quad \land \quad \text{ruta}(A) = \text{ruta}(B)$$

Cuando esto ocurre:
* El bus líder viaja con sobrecupo extremo ($\ge 95\%$).
* El bus seguidor viaja prácticamente vacío ($< 20\%$), desperdiciando capacidad de transporte y aumentando la varianza del tiempo de espera de los usuarios.

---

## 8. Ley Universal de Frecuencias y Flota Requerida ($B_r$)

### Relación entre Tiempo de Ciclo, Intervalo y Flota
Para un servicio troncal $r$ con tiempo de ciclo completo $T_r$ (recorrido ida y vuelta incluyendo terminales y regulación) e intervalo de despacho programado $h_r$ (minutos entre salidas sucesivas), el número de buses físicos requeridos en operación simultánea se rige por:

$$B_r = \left\lceil \frac{T_r}{h_r} \right\rceil$$

### Cota Presupuestal Dura
La suma de buses en operación en las 6 rutas troncales no puede superar la disponibilidad física del patio:

$$\sum_{r \in \{\text{B13, B18, B23, B27, B74, B75}\}} \left\lceil \frac{T_r}{h_r} \right\rceil \le B_{\text{max}} = 106\text{ buses}$$

### Tiempos de Ciclo Calibrados en el Corredor
* `B13`: $T_{\text{ciclo}} = 50.0\text{ min}$
* `B18`: $T_{\text{ciclo}} = 40.0\text{ min}$
* `B23`: $T_{\text{ciclo}} = 45.0\text{ min}$
* `B27`: $T_{\text{ciclo}} = 48.0\text{ min}$
* `B74`: $T_{\text{ciclo}} = 48.0\text{ min}$
* `B75`: $T_{\text{ciclo}} = 44.0\text{ min}$

Durante las 3 horas (180 minutos) del pico matutino, los **96 buses físicos** asignados por el agente de IA completan **347 expediciones/despachos** en rotación cíclica continua.
