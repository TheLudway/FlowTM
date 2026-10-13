# Información General y Modelamiento Físico-Matemático de FlowTM

**FlowTM** es un simulador físico-estocástico por eventos discretos (DES) impulsado por Inteligencia Artificial y agentes racionales, diseñado para el modelamiento matemático riguroso de sistemas BRT (*Bus Rapid Transit*).

A diferencia de modelos basados en mallas celulares agregadas o macrosimulaciones estáticas, **FlowTM** garantiza la fidelidad operacional a través de un ecosistema de **ocho modelos matemáticos y físicos acoplados** dentro de su motor de eventos discretos en **SimPy**.

---

## 1. Generación de Pasajeros: Proceso de Poisson No Homogéneo (NHPP)

### La Ecuación (Transformada Inversa de la Exponencial)

$$\Delta t = - \frac{\ln(U)}{\lambda(s, t)}$$

* **Donde:**
  * $\Delta t$: Intervalo de tiempo entre llegadas consecutivas de usuarios a la estación (segundos).
  * $U \sim \text{Uniforme}(0, 1)$: Variable aleatoria continua generada estocásticamente con Mersenne Twister.
  * $\lambda(s, t)$: Tasa empírica de intensidad de llegadas en la estación $s$ durante la ventana de 15 minutos en la que se encuentra el reloj $t$ (pasajeros/segundo).

### Demostración Matemática de la Transformada Inversa
La probabilidad acumulada de que el tiempo entre arribos sea menor o igual a $\Delta t$ bajo una tasa Poisson $\lambda$ sigue una distribución exponencial:
$$F(\Delta t) = 1 - e^{-\lambda \Delta t} = U$$
Despejando $\Delta t$:
$$e^{-\lambda \Delta t} = 1 - U \implies -\lambda \Delta t = \ln(1 - U)$$
Dado que si $U \sim \text{Uniforme}(0, 1)$, entonces $(1 - U) \sim \text{Uniforme}(0, 1)$, se obtiene:
$$\Delta t = - \frac{\ln(U)}{\lambda}$$

### Justificación Física y Operacional
Los usuarios del sistema de transporte masivo no ingresan en intervalos equidistantes ni en bloques rígidos. Llegan en ráfagas aleatorias e independientes. La tasa $\lambda(s, t)$ se calibra empíricamente en ventanas de 15 minutos a partir de 44.93 millones de registros de validaciones en torniquetes (*tullave*).

---

## 2. Dinámica de Colas en Andén: Balance de Masa ($Q(t)$)

### La Ecuación (Conservación de Flujo / Vickrey-Newell)

$$\frac{dQ_s(t)}{dt} = \lambda_s(t) - \mu_s(t)$$

En el espacio discreto de eventos de FlowTM, la actualización en cada instante de evento $k$ se formula como:

$$Q_s(k + 1) = \max\Big(0, \; Q_s(k) + \text{Llegadas}_s(k) - \text{Abordajes}_s(k)\Big)$$

* **Donde:**
  * $Q_s(t)$: Longitud instantánea de la fila de espera en la plataforma de la estación $s$.
  * $\lambda_s(t)$: Tasa instantánea de ingreso de usuarios por torniquetes.
  * $\mu_s(t)$: Tasa de evacuación efectiva por abordaje vehicular.
  * La función $\max(0, \dots)$ garantiza la no negatividad física del andén.

### Métrica de Espera Acumulada
El tiempo medio de espera de los usuarios en el corredor se computa mediante la integral de Riemann discreta de la cola:

$$\bar{W} = \frac{\sum_{k} Q_s(k) \cdot \Delta t_k}{N_{\text{pax}}}$$

Donde $N_{\text{pax}}$ es el volumen total de pasajeros arribados durante la ventana operacional de 3 horas.

---

## 3. Matriz Origen-Destino: Inferencia Empírica de Atracción

### La Ecuación

$$P(\text{descenso en estación } j \mid \text{ascenso en } i) = \frac{\text{Salidas}_j}{\sum_{k > i} \text{Salidas}_k}$$

* **Donde:**
  * $P(j \mid i)$: Probabilidad condicional de que un usuario que abordó en la estación $i$ elija descender en la estación $j$ ubicada aguas abajo ($j > i$).
  * $\text{Salidas}_j$: Volumen histórico de descensos registrado en los torniquetes externos de la estación $j$ (*tap-out*).

### Justificación Física
Los buses troncales de TransMilenio no disponen de torniquetes de desabordaje a bordo. Por tanto, se asume que una estación aguas abajo atrae descensos de forma directamente proporcional a su volumen empírico de salidas netas observadas en infraestructura.

---

## 4. Elección de Servicio y Capacidad Residual

### Formulación

$$C_{\text{disp}} = \max(0, \; C_{\text{max}} - P_{\text{bordo}})$$

$$\text{Abordajes} = \min(Q_{\text{aptos}}, \; C_{\text{disp}})$$

* **Donde:**
  * $C_{\text{disp}}$: Capacidad residual disponible en el vehículo al detenerse en la bahía.
  * $C_{\text{max}} = 160$: Capacidad nominal máxima para buses articulados de 18 metros (o 250 para biarticulados).
  * $P_{\text{bordo}}$: Cantidad de pasajeros a bordo antes de habilitar puertas.
  * $Q_{\text{aptos}}$: Pasajeros en andén cuyo destino coincide con el itinerario de paradas de la ruta en cuestión.

---

## 5. Tiempo de Permanencia en Plataforma (*Dwell Time*)

### La Ecuación (Modelo Estándar TCQSM)

$$T_{\text{dwell}} = t_{\text{puertas}} + \max(\beta_{\text{sub}} \cdot P_{\text{suben}}, \; \beta_{\text{baj}} \cdot P_{\text{bajan}}) + \epsilon$$

* **Parámetros Calibrados:**
  * $t_{\text{puertas}} = 10.0\text{ s}$ (tiempo mecánico de apertura, advertencia acústica y cierre neumático).
  * $\beta_{\text{sub}} = 1.2\text{ s/pax}$ (tasa marginal de ascenso por puertas dobles).
  * $\beta_{\text{baj}} = 1.0\text{ s/pax}$ (tasa marginal de descenso).
  * Límite inferior operacional: $12.0\text{ s}$.
  * Límite superior operacional: $75.0\text{ s}$.
  * $\epsilon \sim \mathcal{N}(0, \sigma^2)$: Ruido estocástico por fricción de pasajeros.

### Justificación Física
La detención de un bus no es constante. Modela la ocupación de las bahías físicas de parada (`simpy.Resource(capacity=2)`). Si un abordaje masivo satura la plataforma, el vehículo retiene la bahía, forzando al bus que viene detrás a esperar en fila sobre el carril exclusivo (*Bus Bunching*).

---

## 6. Cinemática Geodésica Inter-Estación (Haversine)

### La Ecuación

$$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)$$

$$d(i, i+1) = 2 R \cdot \operatorname{atan2}(\sqrt{a}, \; \sqrt{1 - a})$$

$$\Delta t_{\text{viaje}} = \frac{d(i, i+1)}{v_{\text{comercial}}} + t_{\text{demora}}$$

* **Donde:**
  * $R = 6.371.000\text{ m}$: Radio medio de la Tierra.
  * $\phi_1, \phi_2$ y $\lambda_1, \lambda_2$: Coordenadas geodésicas oficiales de las estaciones.
  * $v_{\text{comercial}} = 6.11\text{ m/s}$ ($22\text{ km/h}$): Velocidad de crucero en carril exclusivo.
  * $t_{\text{demora}} = 15.0\text{ s}$: Penalización por aceleración, desaceleración e intersecciones semafóricas.

---

## 7. Dinámica Ondulatoria de *Bus Bunching*

### Mecanismo de Propagación de Retardo
Sea $h_0$ el intervalo programado entre dos buses consecutivos $B_1$ y $B_2$. Si $B_1$ experimenta una perturbación aleatoria $\delta t$ en una estación:
1. El intervalo entre buses aumenta: $h(B_1, B_2) = h_0 + \delta t$.
2. Durante el lapso adicional $\delta t$, arriban más pasajeros al andén: $\Delta Q = \lambda \cdot \delta t$.
3. El bus retrasado $B_1$ debe atender más pasajeros, aumentando su dwell time: $\Delta T_d = \beta \cdot \Delta Q = \beta \lambda \delta t$.
4. El siguiente bus $B_2$ encuentra menos pasajeros, atiende más rápido y alcanza a $B_1$, formando un convoy ineficiente.

FlowTM captura esta no linealidad permitiendo evaluar estrategias de mitigación en tiempo continuo.

---

## 8. Dinámica de Flota Cíclica y Ley de Conservación ($B_r = \lceil T_r / h_r \rceil$)

### Conservación de Flota por Servicio
Para una ruta $r$ con un tiempo promedio de viaje ida y vuelta (tiempo de ciclo) $T_r$ y un intervalo entre despachos sucesivos $h_r$, el número de vehículos físicos requeridos para operar el servicio sin huecos temporales es:

$$B_r = \left\lceil \frac{T_r}{h_r} \right\rceil$$

### Flota Total del Corredor
$$B_{\text{total}} = \sum_{r=1}^{6} B_r = \sum_{r=1}^{6} \left\lceil \frac{T_r}{h_r} \right\rceil \le 106$$

### Relación entre Despachos Totales (347) y Flota Física (96 buses)
Durante la ventana de simulación pico matutina de 3 horas (180 minutos):
* Cada bus físico completa múltiples ciclos continuos ($T_{\text{ciclo}} \approx 35 - 45$ min).
* Promedio de rotaciones por bus: $\frac{180 \text{ min}}{T_{\text{promedio}}} \approx 3.61 \text{ viajes/bus}$.
* Total de despachos acumulados: $96 \text{ buses} \times 3.61 \approx 347 \text{ despachos}$.
