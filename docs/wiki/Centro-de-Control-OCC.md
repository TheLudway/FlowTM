# 04. Centro de Control de Operaciones (OCC) & Frontend Web

El componente visual de **FlowTM** es un **Centro de Control de Operaciones (Operations Control Center - OCC)** interactivo en tiempo real de grado industrial. Proporciona a ingenieros de transporte, despachadores y directores de operaciones una representación espacial e interactiva de alta fidelidad de la dinámica vehicular en el corredor Caracas-Autonorte.

---

## 1. Filosofía de Diseño y Principios UI/UX

La interfaz fue diseñada bajo estándares de ingeniería visual inspirados en centros de control aeroespaciales y ferroviarios modernos, combinando tres disciplinas estéticas fundamentales:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   SISTEMA DE DISEÑO VISUAL OCC                         │
│                                                                        │
│   taste-skill                     impeccable              emil-kowalski │
│   ┌─────────────────────────┐     ┌─────────────────────┐ ┌───────────┐│
│   │ • Tipografía Outfit     │     │ • HSL Tokens        │ │ • Spring  ││
│   │ • Bento Grid Layout     │     │ • Dark & Light Mode │ │   Physics ││
│   │ • Micro-datos densos    │     │ • Sin colores planos│ │ • Docked  ││
│   │ • Jerarquía visual clara│     │ • Glassmorphism sutil│ │   Modals  ││
│   └─────────────────────────┘     └─────────────────────┘ └───────────┘│
└────────────────────────────────────────────────────────────────────────┘
```

1. **Jerarquía Tipográfica y Espaciado (`taste-skill`):** Empleo de la fuente geométrica moderna **Outfit** para títulos y métricas clave, combinada con **Inter** para telemetría densa y etiquetas tabulares. Los márgenes y paddings utilizan una escala proporcional basada en múltiplos de 4px/8px para garantizar orden matemático.
2. **Coherencia Cromática y Contraste (`impeccable`):** Paleta de colores formulada exclusivamente en HSL semántico. Se evitan azules, verdes o rojos planos por defecto; en su lugar, se utilizan gradientes esmeralda (`hsl(160, 84%, 39%)`), ámbar preventivo (`hsl(38, 92%, 50%)`) y crimson crítico (`hsl(0, 84%, 60%)`), optimizados tanto para modo oscuro de alta inmersión como para modo claro de alta luminosidad.
3. **Física de Interacción y Micro-Animaciones (`emil-kowalski`):** Transiciones fluidas gobernadas por resortes con amortiguamiento crítico ($\zeta \approx 1.0$), eliminando rebotes toscos. El modal del inspector vehicular se acopla dinámicamente con transiciones suaves en CSS y `framer-motion`.

---

## 2. Stack Tecnológico de la Capa de Presentación

* **Framework Base:** [React 19](https://react.dev/) + [TypeScript 5.8](https://www.typescriptlang.org/) con tipado estricto en modo `strict`.
* **Empaquetador y HMR:** [Vite 6](https://vitejs.dev/) con compilador esbuild ultra-rápido y tiempo de recarga en caliente < 50ms.
* **Motor Cartográfico WebGL:** [MapLibre GL JS 5.x](https://maplibre.org/) ejecutando shaders de hardware para renderizar vectores geodésicos a 60 cuadros por segundo sostenidos.
* **Gestión de Estilos:** Vanilla CSS con variables CSS nativas (`CSS Custom Properties`), garantizando cero overhead de runtime y compatibilidad completa con temas claro y oscuro.
* **Iconografía:** [Lucide React](https://lucide.dev/) optimizada con importaciones nombradas en árbol (tree-shaking).
* **Gestor de Paquetes:** [Bun](https://bun.sh/) para instalación determinista y ejecución en milisegundos.

---

## 3. Arquitectura del Motor de Animación e Interpolación (60 FPS)

Los datos generados por el simulador de eventos discretos SimPy consisten en registros temporales con intervalos discretos de evento. Para convertir estos datos en una experiencia visual continua y suave sobre el mapa, el frontend implementa un **motor de interpolación cinemática continua**:

```
Telemetría SimPy (Eventos Discretos)
  │ (t_k, lat_k, lon_k, vel_k)
  ▼
Scrubber / Reloj Virtual (06:00:00 -> 09:00:00)
  │ time_cursor = base_time + elapsed * speed_multiplier
  ▼
Búsqueda Binaria de Fotogramas Clave (O(log N))
  │ Frame Anterior (t_a) <---> Frame Posterior (t_b)
  ▼
Interpolación Lineal Geodésica (lerp)
  │ α = (time_cursor - t_a) / (t_b - t_a)
  │ lat = lat_a + α * (lat_b - lat_a)
  │ lon = lon_a + α * (lon_b - lon_a)
  ▼
MapLibre GL Source Update (requestAnimationFrame @ 60 FPS)
```

### Barra de Control Temporal (`PlaybackBar.tsx`)
Permite a los operadores navegar con precisión por las 3 horas de simulación matutina:
* **Play / Pausa:** Conmutador del bucle `requestAnimationFrame`.
* **Multiplicadores de Velocidad:** `1x` (tiempo real), `2x`, `5x`, `10x` y `30x` (modo alta velocidad para análisis macro).
* **Scrubber Interactivo:** Deslizador de alta sensibilidad temporal que permite arrastrar el cursor y posicionar el reloj en cualquier instante entre las 06:00:00 y las 09:00:00 AM.
* **Etiqueta Temporal Digital:** Reloj en formato `HH:MM:SS` sincronizado con la hora pico oficial de Bogotá.

---

## 4. Modos de Visualización del OCC

### 4.1. Vista Individual de Centro de Control (Single View)
Es la disposición estándar de monitoreo. Incluye:
* **Lienzo Cartográfico Central:** Visualiza las 17 estaciones troncales de la Autopista Norte y Caracas con marcadores codificados por color según la cola acumulada $Q_s(t)$.
* **Buses en Tránsito:** Cada bus se renderiza como un vector direccional apuntando hacia su rumbo geodésico, con el color de su ruta respectiva y un aro luminoso perimetral cuyo grosor indica el factor de ocupación a bordo ($LF$).
* **Panel de KPIs Flotante (`KpiPanel.tsx`):** Tarjetas Bento flotantes en la esquina superior izquierda con lectura en tiempo real de:
  * Tiempo medio de espera en andén ($\bar{W}$).
  * Total de pasajeros transportados y en espera.
  * Flota activa en circulación.
  * Ocupación promedio del sistema.

### 4.2. Vista Comparativa en Pantalla Dividida (Split-Screen / Dual Viewport)
Permite realizar una **auditoría visual y comparativa directa entre dos realidades operativas concurrentes**:

```
┌───────────────────────────────────────┬───────────────────────────────────────┐
│        ESCENARIO BASE (GTFS VIGENTE)  │    ESCENARIO OPTIMIZADO FLOWTM        │
│                                       │    [PRE-BINDING IA ACTIVO]            │
│ ┌───────────────────────────────────┐ │ ┌───────────────────────────────────┐ │
│ │ MapLibre Viewport A               │ │ │ MapLibre Viewport B               │ │
│ │ • Frecuencias estáticas           │ │ │ • Frecuencias optimizadas por IA  │ │
│ │ • 106 buses físicos requeridos    │ │ │ • 96 buses físicos (-10 flota)    │ │
│ │ • Mayor acumulación en Calle 45   │ │ │ • Flujo uniforme y sin colapso    │ │
│ └───────────────────────────────────┘ │ └───────────────────────────────────┘ │
└───────────────────────────────────────┴───────────────────────────────────────┘
```

* **Cámaras Vinculadas:** Al hacer zoom o paneo en cualquiera de los dos lados, la cámara del lado opuesto replica exactamente las coordenadas geográficas y el nivel de zoom mediante listeners bidireccionales sincronizados.
* **Banners de Alto Contraste:** Rótulos semánticos flotantes en la parte superior de cada viewport con fondos adaptativos (`rgba` con desenfoque de fondo y bordes distintivos) legibles en cualquier tema.

---

## 5. Componentes Principales de la UI

### 5.1. Barra de Navegación Principal (`Header.tsx`)
Barra superior responsiva que concentra la consola de mando:
* **Identidad de Marca:** Logotipo FlowTM y badge de versión del gemelo digital.
* **Selector de Rutas (`RouteSelectDropdown.tsx`):** Menú desplegable con estilos premium que permite aislar visualmente una ruta específica (`B13`, `B18`, `B23`, `B27`, `B74`, `B75`) o ver todas en conjunto.
* **Selector de Vista Activa:** Botones tipo *pill* para alternar instantáneamente entre la vista de **Simulador OCC** y la vista de **Analítica y KPIs**.
* **Switch de Pantalla Dividida:** Habilita o deshabilita la comparación dual en tiempo real.
* **Alternador de Tema:** Interruptor con icono interactivo entre modo oscuro (Dark OCC) y modo claro (Light OCC).

### 5.2. Inspector Vehicular Flotante (`InspectorModal.tsx`)
Al hacer clic sobre cualquier bus en movimiento sobre el mapa, se despliega una ventana flotante de telemetría detallada:
* **ID Vehicular y Código de Ruta:** Ejemplo: `BUS-B13-04` (Ruta B13, Portal Tunal $\rightarrow$ Portal Norte).
* **Velocidad Instantánea:** Lectura en km/h calculada a partir de la distancia Haversine recorrida entre fotogramas.
* **Retardo en Andén (Dwell Time):** Segundos consumidos en la última parada según la ecuación TCQSM.
* **Ocupación a Bordo:** Barra de progreso dinámica que cambia de color verde $\rightarrow$ amarillo $\rightarrow$ rojo según el umbral de capacidad ($N_{\text{pax}} / C_{\text{veh}}$).
* **Próxima Estación y Distancia Restante:** Estimación de tiempo de arribo (ETA) a la siguiente parada.
* **Alerta de Bunching:** Detección automática si la distancia respecto al bus precedente de la misma ruta cae por debajo del umbral crítico de 90 segundos.

---

## 6. Módulo Pedagógico de Analítica y KPIs (`AnalyticsView.tsx`)

Diseñado específicamente para auditoría de jurados y presentaciones académicas, la vista de analítica se organiza en un **flujo procedimental de 4 fases lógicas y secuenciales**:

```
FASE 1: Diagnóstico de la Operación Base (GTFS Vigente)
  └─ Radiografía de cuellos de botella, sobreoferta en B18/B74 y colapso en Calle 45.
  ▼
FASE 2: Comparativa Visual Split-Screen en Tiempo Real
  └─ Panel interactivo que invita al usuario a observar la sincronización de flotas.
  ▼
FASE 3: Evaluación del Agente Racional IA (Recocido Simulado & Utilidad U(S))
  └─ Métricas consolidadas: ΔU = +0.0734, -5.17% espera, 96 buses vs 106 cota dura.
  ▼
FASE 4: Exportación de la Solución Óptima (frequencies.txt GTFS)
  └─ Botón de descarga directa con validación de hash y tabla de headways por ruta.
```

### Tabla de Despachos vs. Flota Física en la UI
La interfaz analítica incorpora una tarjeta explicativa interactiva que resuelve formalmente la relación entre despachos (347) y flota (96 buses), desglosando la rotación de ciclo ($T_{\text{ciclo}} \approx 40$ min, ~3.6 viajes por bus en la ventana de 3 horas), asegurando que cualquier evaluador comprenda con total claridad la viabilidad física del modelo.
