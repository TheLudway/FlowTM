import React, { useMemo, useState } from 'react';
import {
  ArrowRight,
  ArrowsLeftRight,
  Bus,
  CheckCircle,
  Clock,
  Columns,
  Database,
  DownloadSimple,
  Gauge,
  ShieldCheck,
  Sparkle,
  TrendUp,
  Users,
} from '@phosphor-icons/react';
import { MetricTooltip } from './MetricTooltip';
import type {
  AIOptimizationIteration,
  AIOptimizationLog,
  InterpolatedBus,
  RouteConfig,
  Station,
  SummaryKPIs,
} from '../types';

/** Physical fleet bound B_max (buses) enforced by the optimizer. */
const MAX_FLEET = 106;
/** Avance II, Section 8: target reduction of mean platform wait time. */
const WAIT_REDUCTION_GOAL_PCT = 15;
const PLACEHOLDER = '—';

const EMPTY_ITERATION: AIOptimizationIteration = {
  iteration: 0,
  temperature: 0,
  headways: {},
  utility: 0,
  delta_u: 0,
  accepted: false,
  is_new_best: false,
  best_utility: 0,
  wait_time_min: 0,
  stranded_pax: 0,
  overcrowded_pct: 0,
  fleet_used: 0,
};

const percentChange = (base?: number, value?: number): number | undefined =>
  base !== undefined && value !== undefined && base !== 0 ? ((value - base) / base) * 100 : undefined;

const formatSigned = (value: number | undefined, digits: number, suffix = ''): string =>
  value === undefined ? PLACEHOLDER : `${value >= 0 ? '+' : ''}${value.toFixed(digits)}${suffix}`;

const formatFixed = (value: number | undefined, digits: number): string =>
  value === undefined ? PLACEHOLDER : value.toFixed(digits);

interface AnalyticsViewProps {
  isSplitView: boolean;
  onToggleSplitView?: () => void;
  summary: SummaryKPIs | null;
  summaryOpt: SummaryKPIs | null;
  aiLog: AIOptimizationLog | null;
  routes: RouteConfig[];
  stations: Station[];
  activeBuses?: InterpolatedBus[];
  activeBusesOptimized?: InterpolatedBus[];
  currentQueues: Record<string, number>;
  currentQueuesOptimized: Record<string, number>;
  simTimeSec?: number;
}

export const AnalyticsView: React.FC<AnalyticsViewProps> = ({
  isSplitView,
  onToggleSplitView,
  summary,
  summaryOpt,
  aiLog,
  routes,
  stations,
  currentQueues,
  currentQueuesOptimized,
}) => {
  const [hoveredIteration, setHoveredIteration] = useState<AIOptimizationIteration | null>(null);

  // Convergence history comes only from the optimizer log; nothing is shown
  // until it loads, so the chart never displays invented values.
  const history = useMemo<AIOptimizationIteration[]>(() => aiLog?.history ?? [], [aiLog]);
  const totalIterations = Math.max(0, history.length - 1);

  // Selected iteration to display in inspection bar (hovered or winning optimum)
  const activeInspectorIteration = useMemo<AIOptimizationIteration>(() => {
    if (hoveredIteration) return hoveredIteration;
    const bestIterations = history.filter((h) => h.is_new_best);
    return bestIterations[bestIterations.length - 1] ?? history[0] ?? EMPTY_ITERATION;
  }, [hoveredIteration, history]);

  // Scenario comparison derived from the exported simulation outputs.
  const baseFleet = aiLog?.baseline?.fleet_used;
  const optFleet = aiLog?.optimized?.fleet_used;
  const fleetSaved = baseFleet !== undefined && optFleet !== undefined ? baseFleet - optFleet : undefined;
  const baseWait = summary?.avg_waiting_time_min;
  const optWait = summaryOpt?.avg_waiting_time_min;
  const waitDeltaPct = percentChange(baseWait, optWait);
  const baseOvercrowd = summary?.overcrowded_buses_pct;
  const optOvercrowd = summaryOpt?.overcrowded_buses_pct;
  const optDispatches = summaryOpt?.total_dispatched_buses;
  const waitGoalMet = waitDeltaPct !== undefined && waitDeltaPct <= -WAIT_REDUCTION_GOAL_PCT;
  const overcrowdContained =
    baseOvercrowd !== undefined && optOvercrowd !== undefined && optOvercrowd <= baseOvercrowd;

  // SVG Chart bounds
  const chartMetrics = useMemo(() => {
    const utils = history.map((h: AIOptimizationIteration) => h.utility);
    const minU = Math.min(-2.4, ...utils);
    const maxU = Math.max(-1.85, ...utils);
    return { minU, maxU, range: Math.max(0.1, maxU - minU) };
  }, [history]);

  const svgWidth = 840;
  const svgHeight = 220;
  const padX = 54;
  const padY = 32;

  const getSvgX = (iter: number) => {
    return padX + (iter / Math.max(1, history.length - 1)) * (svgWidth - 2 * padX);
  };

  const getSvgY = (u: number) => {
    const norm = (u - chartMetrics.minU) / chartMetrics.range;
    return svgHeight - padY - norm * (svgHeight - 2 * padY);
  };

  // Build SVG path
  const pointsPath = useMemo(() => {
    if (!history.length) return '';
    return history
      .map((h: AIOptimizationIteration, i: number) => `${i === 0 ? 'M' : 'L'} ${getSvgX(h.iteration).toFixed(1)} ${getSvgY(h.utility).toFixed(1)}`)
      .join(' ');
  }, [history, chartMetrics]);

  // Area path for gradient fill
  const areaPath = useMemo(() => {
    if (!history.length) return '';
    const baseY = svgHeight - padY;
    const startX = getSvgX(history[0].iteration).toFixed(1);
    const endX = getSvgX(history[history.length - 1].iteration).toFixed(1);
    return `${pointsPath} L ${endX} ${baseY} L ${startX} ${baseY} Z`;
  }, [pointsPath, history]);

  const baseU = aiLog?.baseline?.utility;
  const optU = aiLog?.optimized?.utility;
  const deltaU = aiLog?.delta_utility ?? (baseU !== undefined && optU !== undefined ? optU - baseU : undefined);
  // Keep the chart scale stable while the log is loading.
  const baseULine = baseU ?? chartMetrics.minU;

  // GTFS Frequencies data (optimized vector H* from the optimizer log)
  const gtfsHeadways = useMemo<Record<string, number>>(() => aiLog?.optimized?.headways ?? {}, [aiLog]);
  const baseHeadways = useMemo<Record<string, number>>(() => aiLog?.baseline?.headways ?? {}, [aiLog]);

  const handleDownloadGtfs = () => {
    const link = document.createElement('a');
    link.href = '/data/frequencies.txt';
    link.download = 'frequencies.txt';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const renderScenarioDashboard = (isOptimized: boolean) => {
    const s = isOptimized ? summaryOpt : summary;
    const currentQ = isOptimized ? currentQueuesOptimized : currentQueues;
    const waitTime = s ? s.avg_waiting_time_min.toFixed(2) : PLACEHOLDER;
    const totalPax = s ? s.total_passengers_served.toLocaleString() : PLACEHOLDER;
    const occPct = s ? s.avg_occupancy_pct.toFixed(1) : PLACEHOLDER;
    const strandedPax = s?.stranded_passengers_in_queue?.toLocaleString() ?? PLACEHOLDER;
    const fleetUsed = (isOptimized ? optFleet : baseFleet) ?? PLACEHOLDER;

    const activeHeadways = isOptimized ? gtfsHeadways : baseHeadways;

    return (
      <div className={`analytics-scenario-column ${isOptimized ? 'optimized-column' : 'baseline-column'}`}>
        {/* Scenario Header Banner */}
        <div className="scenario-header-banner">
          <div className="scenario-badge-group">
            <span className={`scenario-type-badge ${isOptimized ? 'badge-opt' : 'badge-base'}`}>
              {isOptimized ? 'ESCENARIO OPTIMIZADO (FLOWTM-SCHEDULER)' : 'ESCENARIO BASE (GTFS VIGENTE)'}
            </span>
            {isOptimized ? (
              <span className="scenario-status-tag opt-tag">
                <Sparkle size={13} weight="fill" /> IA HEURÍSTICA ACTIVA ({optFleet ?? PLACEHOLDER} BUSES)
              </span>
            ) : (
              <span className="scenario-status-tag base-tag">
                <ShieldCheck size={13} weight="fill" /> LÍNEA BASE OFICIAL ({baseFleet ?? PLACEHOLDER} BUSES)
              </span>
            )}
          </div>
          <p className="scenario-desc">
            {isOptimized
              ? `Frecuencias redistribuidas por Recocido Simulado respetando la cota de ${MAX_FLEET} buses y maximizando U(S).`
              : `Despachos históricos oficiales TransMilenio GTFS (06:00 - 09:00 AM) con ${baseFleet ?? PLACEHOLDER} buses asignados.`}
          </p>
        </div>

        {/* Top 5 Metric KPI Cards (Responsive Bento) */}
        <div className="analytics-kpi-grid">
          <div className="analytics-card">
            <div className="card-top">
              <span className="card-title">TIEMPO MEDIO ESPERA</span>
              <Clock size={16} color="var(--accent-blue)" />
            </div>
            <div className="card-val-row">
              <span className="card-val tabular-nums font-mono">{waitTime}</span>
              <span className="card-unit">min</span>
              {isOptimized && waitDeltaPct !== undefined && (
                <span className={`delta-pill ${waitDeltaPct < 0 ? 'delta-good' : 'delta-neutral'}`}>
                  {formatSigned(waitDeltaPct, 1, '%')}
                </span>
              )}
            </div>
            <span className="card-sub">Espera promedio en andén</span>
          </div>

          <div className="analytics-card">
            <div className="card-top">
              <span className="card-title">PASAJEROS EN ANDÉN</span>
              <Users size={16} color={isOptimized ? 'var(--accent-green)' : 'var(--accent-red)'} />
            </div>
            <div className="card-val-row">
              <span className="card-val tabular-nums font-mono">{strandedPax}</span>
              <span className="card-unit">pax</span>
              {isOptimized && summary && summaryOpt && (
                <span className="delta-pill delta-neutral">
                  {formatSigned(
                    percentChange(summary.stranded_passengers_in_queue, summaryOpt.stranded_passengers_in_queue),
                    1,
                    '%',
                  )}
                </span>
              )}
            </div>
            <span className="card-sub">Cola al corte de las 09:00 AM</span>
          </div>

          <div className="analytics-card">
            <div className="card-top">
              <span className="card-title">FLOTA REQUERIDA (B_usados)</span>
              <Bus size={16} color="var(--accent-yellow)" />
            </div>
            <div className="card-val-row">
              <span className="card-val tabular-nums font-mono">{fleetUsed}</span>
              <span className="card-unit">/ {MAX_FLEET}</span>
              {isOptimized && fleetSaved !== undefined && (
                <span className="delta-pill delta-good">-{fleetSaved} buses</span>
              )}
            </div>
            <span className="card-sub">$0 costo de capital adicional</span>
          </div>

          <div className="analytics-card">
            <div className="card-top">
              <span className="card-title">TOTAL TRANSPORTADOS</span>
              <Users size={16} color="var(--text-secondary)" />
            </div>
            <div className="card-val-row">
              <span className="card-val tabular-nums font-mono">{totalPax}</span>
              <span className="card-unit">pax</span>
            </div>
            <span className="card-sub">Demanda pico 3 horas</span>
          </div>

          <div className="analytics-card">
            <div className="card-top">
              <span className="card-title">FACTOR DE OCUPACIÓN</span>
              <Gauge size={16} color="var(--accent-blue)" />
            </div>
            <div className="card-val-row">
              <span className="card-val tabular-nums font-mono">{occPct}%</span>
              <span className="card-unit">flota</span>
            </div>
            <span className="card-sub">Sobrecupo &gt;95%: {s ? s.overcrowded_buses_pct.toFixed(1) : PLACEHOLDER}%</span>
          </div>
        </div>

        {/* 2-Column Grid: Queues by Station & Route Dispatch Frequencies */}
        <div className={`analytics-sub-sections-grid ${isSplitView ? 'stacked-sub-sections' : 'side-sub-sections'}`}>
          {/* Station Platform Queues Bar List */}
          <div className="analytics-section-card">
            <div className="section-title-with-tooltip">
              <h4 className="section-card-title">DISTRIBUCIÓN DE COLAS POR ESTACIÓN</h4>
              <MetricTooltip
                title="Cola de Espera por Estación"
                description="Cantidad de pasajeros esperando en andenes a lo largo del corredor Norte-Caracas al tiempo actual."
                interpretation="Estaciones troncales críticas como Calle 161, Pepe Sierra o Calle 106 concentran aglomeración en la línea base."
                flowtmGoal="Evitar andenes colapsados redistribuyendo la capacidad de paso."
              />
            </div>
            <p className="section-card-subtitle">
              Pasajeros en andén muestreados dinámicamente en SimPy
            </p>

            <div className="station-bars-container">
              {stations.map((st: Station) => {
                const q = currentQ[st.code] || 0;
                const maxQ = Math.max(1, ...(summary ? [summary.max_queue_station] : [300]));
                const pct = Math.min(100, Math.round((q / maxQ) * 100));
                let barColor = 'var(--accent-blue)';
                if (q >= 150) barColor = 'var(--accent-red)';
                else if (q >= 80) barColor = 'var(--accent-yellow)';

                return (
                  <div key={st.code} className="station-bar-row">
                    <span className="bar-st-name">{st.name}</span>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{ width: `${pct}%`, backgroundColor: barColor }}
                      />
                    </div>
                    <span className="bar-val font-mono tabular-nums">{q} pax</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Route Dispatch Balance */}
          <div className="analytics-section-card">
            <div className="section-title-with-tooltip">
              <h4 className="section-card-title">FRECUENCIAS Y DESPACHOS POR RUTA</h4>
              <MetricTooltip
                title="Intervalo de Despacho (Headway)"
                description="Tiempo en minutos entre buses sucesivos de la misma ruta (Vector H en [2.0, 15.0]^6)."
                interpretation="Menor intervalo = mayor frecuencia. El agente ajusta H para equilibrar la oferta con la demanda real."
                flowtmGoal="Sostener la flota por debajo de 106 buses: sum_r ceil(TiempoCiclo_r / h_r) <= 106."
              />
            </div>
            <p className="section-card-subtitle">
              {isOptimized
                ? 'Vector H optimizado por FlowTM-Scheduler'
                : 'Programación estática oficial TransMilenio GTFS'}
            </p>

            <div className="route-balance-list">
              {routes.map((r: RouteConfig) => {
                const headway = (activeHeadways as any)[r.id] ?? r.headway_min;
                const baseH = (aiLog?.baseline?.headways as any)?.[r.id] ?? r.headway_min;
                const diff = headway - baseH;

                return (
                  <div key={r.id} className="route-balance-item">
                    <div className="route-balance-info">
                      <span className="route-tag" style={{ backgroundColor: r.color }}>
                        {r.id}
                      </span>
                      <div className="route-meta-stack">
                        <div className="route-name-title">{r.service}</div>
                        <div className="route-detail-sub">
                          {r.stops_count} paradas &bull; {r.bus_type === 'biarticulado' ? 'Biarticulado (250p)' : 'Articulado (160p)'}
                        </div>
                      </div>
                    </div>
                    <div className="route-headway-pill font-mono tabular-nums">
                      {headway.toFixed(1)} min
                      {isOptimized && diff !== 0 && (
                        <span className={`headway-change-tag ${diff < 0 ? 'boost' : 'trim'}`}>
                          {diff < 0 ? `+freq (${Math.abs(diff).toFixed(1)}m)` : `-freq (+${diff.toFixed(1)}m)`}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`analytics-view-container ${isSplitView ? 'split-active' : 'single-active'}`}>
      <div className="analytics-inner-container">

        {/* ==================================================================
            BARRA SUPERIOR: ENCABEZADO DE CONTROL & SELECTOR PROCEDIMENTAL
            ================================================================== */}
        <header className="analytics-master-header">
          <div className="master-header-left">
            <div className="header-breadcrumbs-row">
              <span className="breadcrumb-tag">CENTRO DE OPERACIONES TRANSMILENIO (OCC)</span>
              <span className="breadcrumb-tag corridor-tag">CORREDOR TRONCAL NORTE - CARACAS (06:00 - 09:00 AM)</span>
              {isSplitView ? (
                <span className="breadcrumb-tag active-split-tag">MODO COMPARATIVO DUAL ACTIVO</span>
              ) : (
                <span className="breadcrumb-tag baseline-tag">AUDITORÍA LÍNEA BASE GTFS VIGENTE</span>
              )}
            </div>
            <h1 className="master-header-title">Diagnóstico Operativo, Demanda & Optimización de Frecuencias</h1>
            <p className="master-header-desc">
              Evaluación estocástica sobre el Gemelo Digital en SimPy con 17 estaciones troncales y 6 servicios troncales.
              Compare la operación estática oficial frente a la reconfiguración heurística del agente FlowTM-Scheduler.
            </p>
          </div>

          <div className="master-header-actions">
            {onToggleSplitView && (
              <button
                className={`analytics-split-toggle-btn ${isSplitView ? 'active-split' : ''}`}
                onClick={onToggleSplitView}
                title="Alternar entre vista de auditoría individual y pantalla partida comparativa con la IA"
              >
                <Columns size={16} weight="bold" />
                <span>
                  {isSplitView ? 'VER SÓLO LÍNEA BASE' : 'COMPARAR CON RESULTADO DE LA IA'}
                </span>
              </button>
            )}
          </div>
        </header>

        {/* ==================================================================
            FASE 1: DIAGNÓSTICO DE DEMANDA - MATRIZ ORIGEN - DESTINO (TULLAVE)
            ================================================================== */}
        <section className="analytics-section-card">
          <div className="section-card-header">
            <div>
              <div className="section-title-with-tooltip">
                <h3 className="section-card-title">1. MATRIZ DE DESEO Y DEMANDA ORIGEN - DESTINO (VALIDADA TULLAVE)</h3>
                <MetricTooltip
                  title="Matriz Origen-Destino (Demanda TuLlave)"
                  description="Distribución real de viajes entre estaciones calculada a partir de millones de validaciones empíricas de torniquete de TransMilenio."
                  interpretation="Identifica los pares de mayor demanda masiva (como Portal Norte hacia Calle 72 o Calle 100) para asignar buses expresos de alta capacidad."
                  flowtmGoal="Dimensionar la oferta en las rutas expresas prioritarias para maximizar la velocidad comercial."
                />
              </div>
              <p className="section-card-subtitle">
                Flujos de pasajeros que ingresan al corredor (48,899 viajes durante el pico de 3 horas). Explica por qué ciertas estaciones sufren sobrecupo.
              </p>
            </div>
            <span className="badge-tullave font-mono">MATRICES TULLAVE VALIDADA</span>
          </div>

          <div className="od-flow-grid">
            <div className="od-flow-card">
              <div className="od-card-header">
                <span className="od-pair-name">Portal Norte &rarr; Calle 72 / Flores</span>
                <span className="od-pair-val font-mono tabular-nums">16,720 pax (34.2%)</span>
              </div>
              <div className="od-progress-track">
                <div className="od-progress-fill" style={{ width: '34.2%', backgroundColor: '#E53935' }} />
              </div>
              <span className="od-pair-sub">Demanda masiva troncal: atendida por B13, B74, B75</span>
            </div>

            <div className="od-flow-card">
              <div className="od-card-header">
                <span className="od-pair-name">Portal Norte &rarr; Calle 100</span>
                <span className="od-pair-val font-mono tabular-nums">11,002 pax (22.5%)</span>
              </div>
              <div className="od-progress-track">
                <div className="od-progress-fill" style={{ width: '22.5%', backgroundColor: '#1976D2' }} />
              </div>
              <span className="od-pair-sub">Punto neurálgico de transbordo hacia Suba / NQS</span>
            </div>

            <div className="od-flow-card">
              <div className="od-card-header">
                <span className="od-pair-name">Toberín / Mazurén &rarr; Calle 72</span>
                <span className="od-pair-val font-mono tabular-nums">8,850 pax (18.1%)</span>
              </div>
              <div className="od-progress-track">
                <div className="od-progress-fill" style={{ width: '18.1%', backgroundColor: '#FFA000' }} />
              </div>
              <span className="od-pair-sub">Demanda zonal norte: atendida por B18, B23, B27</span>
            </div>

            <div className="od-flow-card">
              <div className="od-card-header">
                <span className="od-pair-name">Calle 100 &rarr; Calle 45</span>
                <span className="od-pair-val font-mono tabular-nums">7,236 pax (14.8%)</span>
              </div>
              <div className="od-progress-track">
                <div className="od-progress-fill" style={{ width: '14.8%', backgroundColor: '#00897B' }} />
              </div>
              <span className="od-pair-sub">Polo universitario y financiero de Caracas Centro</span>
            </div>
          </div>
        </section>

        {/* ==================================================================
            FASE 2: RESULTADOS OPERATIVOS - LÍNEA BASE vs. HORARIO OPTIMIZADO
            ================================================================== */}
        <section className="analytics-comparison-wrapper">
          <div className="comparison-section-header">
            <div>
              <h3 className="section-card-title">
                {isSplitView
                  ? '2. COMPARATIVA OPERATIVA DIRECTA: LÍNEA BASE OFICIAL vs. HORARIO OPTIMIZADO FLOWTM'
                  : '2. AUDITORÍA OPERATIVA EN TIEMPO REAL: LÍNEA BASE (GTFS OFICIAL TRANSMILENIO)'}
              </h3>
              <p className="section-card-subtitle">
                {isSplitView
                  ? `Contraste simultáneo de telemetría física: ${baseFleet ?? PLACEHOLDER} buses estáticos vs. ${optFleet ?? PLACEHOLDER} buses reprogramados algorítmicamente.`
                  : `Indicadores de servicio actuales con ${baseFleet ?? PLACEHOLDER} buses y despachos históricos estáticos (06:00 - 09:00 AM).`}
              </p>
            </div>

            {!isSplitView && onToggleSplitView && (
              <button className="cta-compare-button" onClick={onToggleSplitView}>
                <ArrowsLeftRight size={15} weight="bold" />
                <span>ACTIVAR COMPARATIVA DUAL CON LA IA</span>
                <ArrowRight size={14} weight="bold" />
              </button>
            )}
          </div>

          {isSplitView ? (
            <div className="analytics-split-layout">
              {renderScenarioDashboard(false)}
              {renderScenarioDashboard(true)}
            </div>
          ) : (
            <div className="analytics-single-layout">
              {renderScenarioDashboard(false)}
            </div>
          )}
        </section>

        {/* ==================================================================
            FASE 3: DEMOSTRACIÓN DE LA IMPLEMENTACIÓN DE LA IA (AVANCE II)
            ================================================================== */}
        <section className="ai-engineering-master-section">
          {/* Tarjeta de Encabezado Académico */}
          <div className="ai-academic-hero-banner">
            <div className="hero-top-row">
              <div className="hero-badge-row">
                <span className="academic-tag">AVANCE II &bull; INGENIERÍA DE SISTEMAS</span>
                <span className="peas-model-tag">MODELO FORMAL PEAS &bull; AGENTE RACIONAL</span>
                <span className="fleet-bound-tag">COTA DURA: &le; {MAX_FLEET} BUSES ($0 CAPEX)</span>
                <span className="algorithm-tag">METAHEURÍSTICA: RECOCIDO SIMULADO</span>
              </div>
              <div className="hero-actions-group">
                <div className="hero-delta-pill">
                  <TrendUp size={14} weight="bold" />
                  <span>&Delta;U = {formatSigned(deltaU, 4)} GANANCIA NETA</span>
                </div>
              </div>
            </div>

            <div className="hero-text-row">
              <h2 className="hero-title">3. Ingeniería del Agente IA: FlowTM-Scheduler</h2>
              <p className="hero-subtitle">
                Demostración formal de la optimización heurística en el gemelo digital SimPy. El agente explora
                el espacio continuo de frecuencias H &isin; [2.0, 15.0]⁶ respetando la restricción presupuestal estricta
                de flota (&le; {MAX_FLEET} buses) y guiándose por la función de utilidad multi-criterio U(S).
              </p>
            </div>
          </div>

          {/* Telemetry Data Audit Card (Empirical DES Verification) */}
          <div className="ai-telemetry-audit-card">
            <div className="audit-card-left">
              <div className="audit-icon-box">
                <Database size={20} weight="bold" color="var(--accent-blue)" />
              </div>
              <div className="audit-text-stack">
                <h4 className="audit-title">Auditoría de Datos Físicos: Simulación Estocástica Real en SimPy</h4>
                <p className="audit-desc">
                  Los datos optimizados provienen de la ejecución del optimizador
                  (<code>03_optimizar_frecuencias.py</code>) acoplado al simulador de eventos discretos, que generó
                  {' '}{optDispatches?.toLocaleString() ?? PLACEHOLDER} expediciones (viajes despachados por los{' '}
                  {optFleet ?? PLACEHOLDER} buses en rotación continua) exportadas en <code>telemetria_opt/</code>.
                </p>
              </div>
            </div>
            <div className="audit-metrics-row font-mono">
              <div className="audit-pill">
                <span className="p-lbl">MOTOR:</span>
                <span className="p-val">SimPy 4.1</span>
              </div>
              <div className="audit-pill">
                <span className="p-lbl">VIAJES TOTALES (3H):</span>
                <span className="p-val">{optDispatches?.toLocaleString() ?? PLACEHOLDER} expediciones</span>
              </div>
              <div className="audit-pill">
                <span className="p-lbl">FLOTA FÍSICA:</span>
                <span className="p-val font-bold">
                  {optFleet ?? PLACEHOLDER} / {MAX_FLEET} buses (rotación cíclica)
                </span>
              </div>
              <div className="audit-pill highlight">
                <span className="p-lbl">INVERSIÓN:</span>
                <span className="p-val">$0 CAPEX</span>
              </div>
            </div>
          </div>

          {/* Mathematical Formulation U(S) and Heuristic Convergence */}
          <div className="ai-convergence-panel">
            <div className="convergence-header">
              <div>
                <div className="section-title-with-tooltip">
                  <h3 className="panel-main-title">FUNCIÓN DE UTILIDAD MULTI-CRITERIO U(S) & CONVERGENCIA HEURÍSTICA</h3>
                  <MetricTooltip
                    title="Función de Utilidad U(S)"
                    description="U(S) = - [ 0.40 * W_mean + 0.30 * (Sobrecupo_95%)^1.5 + 0.15 * Q_rem + 0.15 * B_usados ]"
                    interpretation="Valores más cercanos a cero representan una mayor calidad global del servicio con menor congestión y costo."
                    flowtmGoal="Ganancia neta ΔU > 0 con convergencia hacia una meseta estable al descender la temperatura."
                  />
                </div>
                <p className="panel-main-subtitle">
                  Evolución de la utilidad durante {totalIterations} iteraciones de exploración en ℝ⁶. Pasa el cursor por cada punto para inspeccionar el estado estocástico.
                </p>
              </div>

              <div className="convergence-summary-badges">
                <div className="summary-badge-item">
                  <span className="badge-lbl">UTILIDAD BASE U₀</span>
                  <span className="badge-val font-mono tabular-nums">{formatFixed(baseU, 4)}</span>
                </div>
                <div className="summary-badge-item opt">
                  <span className="badge-lbl">UTILIDAD OPT U*</span>
                  <span className="badge-val font-mono tabular-nums">{formatFixed(optU, 4)}</span>
                </div>
                <div className="summary-badge-item good">
                  <span className="badge-lbl">GANANCIA &Delta;U</span>
                  <span className="badge-val font-mono tabular-nums">{formatSigned(deltaU, 4)}</span>
                </div>
              </div>
            </div>

            {/* SVG Convergence Chart */}
            <div className="convergence-chart-wrapper">
              <svg
                viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                className="convergence-svg-chart"
                preserveAspectRatio="none"
              >
                <defs>
                  <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity="0.32" />
                    <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity="0.0" />
                  </linearGradient>
                </defs>

                {/* Grid horizontal reference lines */}
                {[-2.3, -2.1, -1.9].map((u) => {
                  const y = getSvgY(u);
                  return (
                    <g key={u}>
                      <line x1={padX} y1={y} x2={svgWidth - padX} y2={y} stroke="var(--border-subtle)" strokeDasharray="3 3" />
                      <text x={padX - 8} y={y + 4} fill="var(--text-tertiary)" fontSize="10" textAnchor="end" className="font-mono">
                        {u.toFixed(2)}
                      </text>
                    </g>
                  );
                })}

                {/* Baseline horizontal line */}
                <line
                  x1={padX}
                  y1={getSvgY(baseULine)}
                  x2={svgWidth - padX}
                  y2={getSvgY(baseULine)}
                  stroke="#E53935"
                  strokeWidth="1.5"
                  strokeDasharray="4 4"
                />
                <text x={svgWidth - padX} y={getSvgY(baseULine) - 6} fill="#E53935" fontSize="10.5" textAnchor="end" fontWeight="bold">
                  Línea Base U₀ = {formatFixed(baseU, 2)}
                </text>

                {/* Area under curve */}
                <path d={areaPath} fill="url(#chartGradient)" />

                {/* Convergence curve */}
                <path d={pointsPath} fill="none" stroke="var(--accent-blue)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                {/* Data point dots */}
                {history.map((h: AIOptimizationIteration) => {
                  const cx = getSvgX(h.iteration);
                  const cy = getSvgY(h.utility);
                  const isBest = h.is_new_best;

                  return (
                    <circle
                      key={h.iteration}
                      cx={cx}
                      cy={cy}
                      r={isBest ? 5 : 3.5}
                      fill={isBest ? 'var(--accent-green)' : 'var(--accent-blue)'}
                      stroke={isBest ? '#FFFFFF' : 'var(--bg-surface-solid)'}
                      strokeWidth={isBest ? 2 : 1}
                      className="chart-dot-node"
                      onMouseEnter={() => setHoveredIteration(h)}
                    />
                  );
                })}
              </svg>

              {/* Docked Iteration Inspector Strip */}
              <div className="iteration-docked-strip">
                <div className="docked-left-badge">
                  <span className="strip-title">ITERACIÓN {activeInspectorIteration.iteration} / {totalIterations}</span>
                  <span className="strip-temp font-mono">T = {activeInspectorIteration.temperature}°C</span>
                  {activeInspectorIteration.is_new_best && (
                    <span className="strip-optimum-tag">★ NUEVO ÓPTIMO</span>
                  )}
                </div>

                <div className="docked-metrics-row font-mono">
                  <div className="docked-metric">
                    <span className="m-label">Utilidad U(S):</span>
                    <span className="m-val">{activeInspectorIteration.utility.toFixed(4)}</span>
                  </div>
                  <div className="docked-metric">
                    <span className="m-label">Espera:</span>
                    <span className="m-val">{activeInspectorIteration.wait_time_min.toFixed(2)} min</span>
                  </div>
                  <div className="docked-metric">
                    <span className="m-label">Flota:</span>
                    <span className="m-val">{activeInspectorIteration.fleet_used} / {MAX_FLEET} buses</span>
                  </div>
                  <div className="docked-metric">
                    <span className="m-label">Cola corte:</span>
                    <span className="m-val">{activeInspectorIteration.stranded_pax.toLocaleString()} pax</span>
                  </div>
                </div>

                <div className="docked-headways-row font-mono">
                  <span className="m-label">Horario H:</span>
                  <span className="h-vector">
                    {Object.entries(activeInspectorIteration.headways).map(([r, h]) => `${r}:${h.toFixed(1)}m`).join(' | ')}
                  </span>
                </div>
              </div>
            </div>

            {/* 4 Multi-criteria Utility Components Cards */}
            <div className="utility-weights-breakdown-row">
              <div className="utility-term-card">
                <div className="term-top">
                  <span className="term-weight">w₁ = 0.40</span>
                  <span className="term-name">TIEMPO ESPERA (W̄)</span>
                </div>
                <div className="term-formula font-mono">0.40 &times; {formatFixed(aiLog?.optimized?.wait_time_min, 2)}m</div>
                <span className="term-sub">Minutos promedio de espera en andén</span>
              </div>

              <div className="utility-term-card">
                <div className="term-top">
                  <span className="term-weight">w₂ = 0.30</span>
                  <span className="term-name">SOBRECUPO (≥95%)^1.5</span>
                </div>
                <div className="term-formula font-mono">0.30 &times; ({formatFixed(aiLog ? aiLog.optimized.overcrowded_pct / 10 : undefined, 2)})^1.5</div>
                <span className="term-sub">Castigo exponencial al hacinamiento</span>
              </div>

              <div className="utility-term-card">
                <div className="term-top">
                  <span className="term-weight">w₃ = 0.15</span>
                  <span className="term-name">PASAJEROS ANDÉN (Q_rem)</span>
                </div>
                <div className="term-formula font-mono">0.15 &times; ({aiLog?.optimized?.stranded_pax ?? PLACEHOLDER} / 1000)</div>
                <span className="term-sub">Pasajeros no abordados al corte</span>
              </div>

              <div className="utility-term-card">
                <div className="term-top">
                  <span className="term-weight">w₄ = 0.15</span>
                  <span className="term-name">USO FLOTA (B_usados)</span>
                </div>
                <div className="term-formula font-mono">0.15 &times; ({optFleet ?? PLACEHOLDER} / {MAX_FLEET})</div>
                <span className="term-sub">Flota física consumida &le; {MAX_FLEET} buses</span>
              </div>
            </div>
          </div>

          {/* Quantitative Academic Goals Matrix (Section 8) */}
          <div className="analytics-section-card">
            <div className="section-card-header">
              <div>
                <div className="section-title-with-tooltip">
                  <h4 className="section-card-title">MATRIZ DE CUMPLIMIENTO DE METAS ACADÉMICAS (SECCIÓN 8)</h4>
                  <MetricTooltip
                    title="Metas Cuantitativas de Éxito"
                    description="Criterios formales de evaluación definidos en el Avance II del proyecto para validar el impacto operativo del agente."
                    interpretation="Verifica que la reasignación algorítmica de frecuencias mejore la oferta sin adquirir flota adicional ($0 costo de capital)."
                    flowtmGoal="Reducción de espera, contención de sobrecupo y ganancia neta positiva de utilidad."
                  />
                </div>
                <p className="section-card-subtitle">
                  Evaluación cuantitativa de los resultados frente a las cotas fijadas en el documento académico
                </p>
              </div>
              <span className="verified-badge">
                <CheckCircle size={14} weight="fill" /> CRITERIOS VERIFICADOS
              </span>
            </div>

            <div className="goals-matrix-grid">
              <div className="goal-item-card">
                <div className="goal-top">
                  <span className="goal-title">Tiempo Medio Espera (W_prom)</span>
                  <span className={`goal-status-pill ${waitGoalMet ? 'ok' : 'partial'}`}>
                    {waitGoalMet ? 'CUMPLE' : 'PARCIAL'}
                  </span>
                </div>
                <div className="goal-vals">
                  <span className="goal-target font-mono">Meta: &ge; {WAIT_REDUCTION_GOAL_PCT}% red.</span>
                  <span className="goal-achieved font-mono">
                    {formatFixed(baseWait, 2)}m &rarr; {formatFixed(optWait, 2)}m ({formatSigned(waitDeltaPct, 1, '%')})
                  </span>
                </div>
                <p className="goal-desc">
                  {waitGoalMet
                    ? 'La reducción de la espera media alcanza la meta fijada en el Avance II.'
                    : `La espera media mejora, pero aún no alcanza la meta del ${WAIT_REDUCTION_GOAL_PCT}% fijada en el Avance II.`}
                </p>
              </div>

              <div className="goal-item-card">
                <div className="goal-top">
                  <span className="goal-title">Uso Total de Flota (B_usados)</span>
                  <span className={`goal-status-pill ${optFleet !== undefined && optFleet <= MAX_FLEET ? 'ok' : 'partial'}`}>
                    {optFleet !== undefined && optFleet <= MAX_FLEET ? 'CUMPLE' : 'EXCEDIDO'}
                  </span>
                </div>
                <div className="goal-vals">
                  <span className="goal-target font-mono">Meta: &le; {MAX_FLEET} buses</span>
                  <span className="goal-achieved font-mono">
                    {optFleet ?? PLACEHOLDER} / {MAX_FLEET} buses
                    {fleetSaved !== undefined && ` (-${fleetSaved} fl.)`}
                  </span>
                </div>
                <p className="goal-desc">Respeto estricto del límite presupuestal: $0 costo de capital adicional.</p>
              </div>

              <div className="goal-item-card">
                <div className="goal-top">
                  <span className="goal-title">Ganancia de Utilidad (&Delta;U)</span>
                  <span className={`goal-status-pill ${deltaU !== undefined && deltaU > 0 ? 'ok' : 'partial'}`}>
                    {deltaU !== undefined && deltaU > 0 ? 'CUMPLE' : 'SIN GANANCIA'}
                  </span>
                </div>
                <div className="goal-vals">
                  <span className="goal-target font-mono">Meta: &Delta;U &gt; 0 (Meseta)</span>
                  <span className="goal-achieved font-mono">&Delta;U = {formatSigned(deltaU, 4)}</span>
                </div>
                <p className="goal-desc">Mejor utilidad encontrada por el Recocido Simulado frente a la línea base.</p>
              </div>

              <div className="goal-item-card">
                <div className="goal-top">
                  <span className="goal-title">Sobrecupo Crítico (&ge; 95%)</span>
                  <span className={`goal-status-pill ${overcrowdContained ? 'ok' : 'partial'}`}>
                    {overcrowdContained ? 'CONTENIDO' : 'AUMENTÓ'}
                  </span>
                </div>
                <div className="goal-vals">
                  <span className="goal-target font-mono">Meta: Contención</span>
                  <span className="goal-achieved font-mono">
                    {formatFixed(baseOvercrowd, 1)}% &rarr; {formatFixed(optOvercrowd, 1)}%
                  </span>
                </div>
                <p className="goal-desc">Evita trasladar el hacinamiento extremo a servicios paralelos.</p>
              </div>
            </div>
          </div>
        </section>

        {/* ==================================================================
            FASE 4: ENTREGABLE OFICIAL Y ACTUADOR DEL AGENTE GTFS
            ================================================================== */}
        <section className="gtfs-actuator-delivery-card">
          <div className="gtfs-delivery-content">
            <div className="gtfs-delivery-text">
              <div className="section-title-with-tooltip">
                <h3 className="gtfs-delivery-title">4. ACTUADOR PEAS: EXPORTACIÓN DEL ENTREGABLE GTFS (frequencies.txt)</h3>
                <MetricTooltip
                  title="Actuador GTFS frequencies.txt"
                  description="En la arquitectura de Inteligencia Artificial (PEAS), el actuador es el mecanismo mediante el cual el agente altera su entorno. FlowTM genera el archivo frequencies.txt cumpliendo la especificación internacional GTFS."
                  interpretation="Este archivo contiene los nuevos intervalos exactos de despacho listos para ser inyectados en la central de control de TransMilenio."
                  flowtmGoal="Garantizar compatibilidad 100% con sistemas de despacho de transporte masivo sin software propietario."
                />
              </div>
              <p className="gtfs-delivery-desc">
                Una vez validada la solución óptima en el Gemelo Digital, el agente materializa su acción en el entorno
                generando el archivo estandarizado <code>frequencies.txt</code>. Este archivo reprograma los intervalos
                de despacho de las 6 rutas troncales con cero inversión de capital.
              </p>

              {/* Optimal Vector H* Generated */}
              <div className="gtfs-vector-preview font-mono">
                <span className="vector-label">Vector Óptimo H* generado:</span>
                <span className="vector-values">
                  {Object.entries(gtfsHeadways).map(([r, h]) => `${r}: ${Number(h).toFixed(1)}m`).join('  |  ')}
                </span>
              </div>
            </div>

            <div className="gtfs-delivery-action">
              <button
                className="download-gtfs-btn prominent-btn"
                onClick={handleDownloadGtfs}
                title="Descargar frequencies.txt oficial generado por el agente FlowTM-Scheduler"
              >
                <DownloadSimple size={18} weight="bold" />
                <span>DESCARGAR frequencies.txt (GTFS OFICIAL)</span>
              </button>
              <span className="gtfs-btn-sub">Archivo conforme al estándar General Transit Feed Specification</span>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
};
