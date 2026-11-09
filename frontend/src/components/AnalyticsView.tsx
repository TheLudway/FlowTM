import React, { useEffect, useMemo, useState } from 'react';
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
  AlgorithmComparison,
  InterpolatedBus,
  OptimizedSource,
  PairedStat,
  RouteConfig,
  Station,
  SummaryKPIs,
} from '../types';

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

/** U(S) terms as stored in the optimizer log breakdown (utility.py). */
const UTILITY_TERMS: {
  key: string;
  label: string;
  weight: string;
  help: string;
  value: (side?: AIOptimizationLog['baseline']) => string;
}[] = [
  {
    key: 'w_wait_term',
    label: 'Tiempo de espera',
    weight: '0.40',
    help: 'Minutos promedio que un pasajero espera en el andén.',
    value: (side) => (side ? `${side.wait_time_min.toFixed(2)} min` : PLACEHOLDER),
  },
  {
    key: 'w_overcrowd_term',
    label: 'Sobrecupo (≥ 95%)',
    weight: '0.30',
    help: 'Fracción de llegadas de bus con ocupación ≥ 95%, castigada con exponente 1.5 (el hacinamiento extremo pesa más).',
    value: (side) => (side ? `${side.overcrowded_pct.toFixed(2)}%` : PLACEHOLDER),
  },
  {
    key: 'w_stranded_term',
    label: 'Pasajeros varados',
    weight: '0.15',
    help: 'Personas que siguen esperando en los andenes a las 09:00 (por miles).',
    value: (side) => (side ? `${Math.round(side.stranded_pax).toLocaleString()} pax` : PLACEHOLDER),
  },
  {
    key: 'w_fleet_term',
    label: 'Uso de flota',
    weight: '0.15',
    help: 'Buses usados respecto a la cota de flota (usar menos buses mejora la utilidad).',
    value: (side) => (side ? `${side.fleet_used} buses` : PLACEHOLDER),
  },
];

/** Headline KPI of the executive summary (paired out-of-sample difference). */
const ExecCard: React.FC<{
  label: string;
  stat: PairedStat;
  digits: number;
  unit?: string;
  absolute?: boolean;
  help: string;
}> = ({ label, stat, digits, unit = '', absolute = false, help }) => {
  const tone = !stat.significativo ? 'neutral' : stat.mejora ? 'good' : 'bad';
  const change = absolute
    ? `${stat.diferencia >= 0 ? '+' : ''}${stat.diferencia.toFixed(digits)}`
    : `${stat.diferencia_pct >= 0 ? '+' : ''}${stat.diferencia_pct.toFixed(2)}%`;
  return (
    <div className={`exec-card tone-${tone}`}>
      <span className="exec-card-label">
        {label}
        <MetricTooltip title={label} description={help} />
      </span>
      <span className="exec-card-value font-mono tabular-nums">{change}</span>
      <span className="exec-card-sub font-mono tabular-nums">
        {stat.base.toFixed(digits)}
        {unit} → {stat.candidato.toFixed(digits)}
        {unit}
      </span>
      <span className="exec-card-sub">
        {tone === 'good' ? 'mejora confirmada' : tone === 'bad' ? 'empeora (confirmado)' : 'sin cambio demostrable'} ·{' '}
        {stat.semillas_mejor}/{stat.semillas} días
      </span>
    </div>
  );
};

const ALGORITHM_NAMES: Record<string, string> = {
  recocido_simulado: 'Recocido simulado',
  hill_climbing: 'Hill climbing',
  busqueda_aleatoria: 'Búsqueda aleatoria',
};

const GoalCard: React.FC<{
  title: string;
  target: string;
  stat: PairedStat;
  digits: number;
  unit?: string;
  absolute?: boolean;
  meetsGoal: (stat: PairedStat) => boolean;
  description: (stat: PairedStat) => string;
}> = ({ title, target, stat, digits, unit = '', absolute = false, meetsGoal, description }) => {
  const met = meetsGoal(stat);
  const label = met
    ? 'CUMPLE'
    : !stat.significativo
      ? 'NO SIGNIFICATIVO'
      : stat.mejora
        ? 'PARCIAL'
        : 'EMPEORA';
  const change = absolute
    ? `${stat.diferencia >= 0 ? '+' : ''}${stat.diferencia.toFixed(digits)}`
    : `${stat.diferencia_pct >= 0 ? '+' : ''}${stat.diferencia_pct.toFixed(2)}%`;
  return (
    <div className="goal-item-card">
      <div className="goal-top">
        <span className="goal-title">{title}</span>
        <span className={`goal-status-pill ${met ? 'ok' : 'partial'}`}>{label}</span>
      </div>
      <div className="goal-vals">
        <span className="goal-target font-mono">{target}</span>
        <span className="goal-achieved font-mono">
          {stat.base.toFixed(digits)}
          {unit} &rarr; {stat.candidato.toFixed(digits)}
          {unit} ({change})
        </span>
        <span className="goal-target font-mono">
          IC 95% [{stat.ic95[0].toFixed(digits)}, {stat.ic95[1].toFixed(digits)}] · mejor en {stat.semillas_mejor}/
          {stat.semillas} semillas
        </span>
      </div>
      <p className="goal-desc">{description(stat)}</p>
    </div>
  );
};

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
  optimizedSource?: OptimizedSource;
  onRestoreOptimum?: () => void;
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
  optimizedSource = { kind: 'agente' },
  onRestoreOptimum,
}) => {
  const [hoveredIteration, setHoveredIteration] = useState<AIOptimizationIteration | null>(null);

  // Convergence history comes only from the optimizer log; nothing is shown
  // until it loads, so the chart never displays invented values.
  const history = useMemo<AIOptimizationIteration[]>(() => aiLog?.history ?? [], [aiLog]);
  const totalIterations = Math.max(0, history.length - 1);
  const optimizableCount = aiLog?.optimizable_routes?.length ?? routes.filter((r) => r.role === 'optimizable').length;
  const odPairs = summary?.od_top?.slice(0, 4) ?? [];

  // Selected iteration to display in inspection bar (hovered or winning optimum)
  const activeInspectorIteration = useMemo<AIOptimizationIteration>(() => {
    if (hoveredIteration) return hoveredIteration;
    const bestIterations = history.filter((h) => h.is_new_best);
    return bestIterations[bestIterations.length - 1] ?? history[0] ?? EMPTY_ITERATION;
  }, [hoveredIteration, history]);

  // Scenario comparison derived from the exported simulation outputs.
  // Physical fleet bound B_max of the scenario (current GTFS fleet of the routes).
  const maxFleet = aiLog?.max_fleet;
  const MAX_FLEET: number | string = maxFleet ?? PLACEHOLDER;
  const baseFleet = aiLog?.baseline?.fleet_used;
  const optFleet = aiLog?.optimized?.fleet_used;
  const holdout = aiLog?.holdout;
  const [comparison, setComparison] = useState<AlgorithmComparison | null>(null);
  useEffect(() => {
    fetch('/data/comparacion_algoritmos.json')
      .then((r) => (r.ok ? r.json() : null))
      .then(setComparison)
      .catch(() => setComparison(null));
  }, []);
  const comparisonMaxDelta = comparison
    ? Math.max(1e-6, ...Object.values(comparison.resumen).map((r) => r.delta_u_validacion_max))
    : 1;
  const fleetSaved = baseFleet !== undefined && optFleet !== undefined ? baseFleet - optFleet : undefined;
  const baseWait = summary?.avg_waiting_time_min;
  const optWait = summaryOpt?.avg_waiting_time_min;
  const waitDeltaPct = percentChange(baseWait, optWait);
  const optDispatches = summaryOpt?.total_dispatched_buses;

  // SVG Chart bounds
  // Scale fitted to the observed utilities (a fixed [-2.4, -1.85] range flattened the curve).
  const chartMetrics = useMemo(() => {
    const utils = history.flatMap((h: AIOptimizationIteration) => [h.utility, h.best_utility]);
    if (!utils.length) return { minU: -1, maxU: 0, range: 1, ticks: [] as number[] };
    const lo = Math.min(...utils);
    const hi = Math.max(...utils);
    const pad = Math.max(0.002, (hi - lo) * 0.12);
    const minU = lo - pad;
    const maxU = hi + pad;
    const range = maxU - minU;
    return { minU, maxU, range, ticks: [0.15, 0.5, 0.85].map((f) => minU + f * range) };
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

  // Best-so-far curve: the agent's convergence (never decreases).
  const bestPath = useMemo(() => {
    if (!history.length) return '';
    return history
      .map((h: AIOptimizationIteration, i: number) => `${i === 0 ? 'M' : 'L'} ${getSvgX(h.iteration).toFixed(1)} ${getSvgY(h.best_utility).toFixed(1)}`)
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
                interpretation="Las estaciones atendidas solo por servicios corrientes (pocas rutas paran en ellas) acumulan las colas más largas."
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
              <h4 className="section-card-title">FRECUENCIA DE LAS 6 RUTAS DE LA IA</h4>
              <MetricTooltip
                title="Intervalo de Despacho (Headway)"
                description="Tiempo en minutos entre buses sucesivos de la misma ruta (Vector H en [2.0, 15.0]^6)."
                interpretation="Menor intervalo = mayor frecuencia. El agente ajusta H para equilibrar la oferta con la demanda real."
                flowtmGoal={`Sostener la flota dentro de la cota: sum_r ceil(TiempoCiclo_r / h_r) <= ${MAX_FLEET}.`}
              />
            </div>
            <p className="section-card-subtitle">
              {isOptimized
                ? 'Vector H optimizado por FlowTM-Scheduler'
                : 'Programación estática oficial TransMilenio GTFS'}
            </p>

            <div className="route-balance-list">
              {routes
                .filter((r) => r.role === 'optimizable')
                .map((r: RouteConfig) => {
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
                          {r.stops_count} paradas &bull; {r.bus_type === 'biarticulado' ? 'Biarticulado' : 'Articulado'} ({r.capacity ?? 160}p)
                          {r.role !== 'optimizable' && ' • Fondo (GTFS fijo)'}
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
              <span className="breadcrumb-tag corridor-tag">CORREDOR PORTAL NORTE → MARLY · SENTIDO SUR (06:00 - 09:00 AM)</span>
              {isSplitView ? (
                <span className="breadcrumb-tag active-split-tag">MODO COMPARATIVO DUAL ACTIVO</span>
              ) : (
                <span className="breadcrumb-tag baseline-tag">AUDITORÍA LÍNEA BASE GTFS VIGENTE</span>
              )}
            </div>
            <h1 className="master-header-title">Diagnóstico Operativo, Demanda & Optimización de Frecuencias</h1>
            <p className="master-header-desc">
              Evaluación estocástica sobre el Gemelo Digital en SimPy con {stations.length} estaciones y{' '}
              {routes.length} servicios troncales del GTFS ({optimizableCount} optimizados por el agente, el resto
              con su frecuencia GTFS).
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

        {optimizedSource.kind === 'laboratorio' && (
          <div className="analytics-source-banner">
            <span>
              Está viendo una <b>prueba del Laboratorio IA</b> ({optimizedSource.algorithm}, {optimizedSource.finishedAt}),
              no el horario óptimo oficial del agente.
            </span>
            {onRestoreOptimum && (
              <button className="badge-restore-btn" onClick={onRestoreOptimum}>
                Volver al óptimo del agente
              </button>
            )}
          </div>
        )}

        {/* ==================================================================
            RESUMEN: veredicto validado fuera de muestra
            ================================================================== */}
        <section className="analytics-section-card exec-summary">
          <div className="section-card-header">
            <div>
              <div className="section-title-with-tooltip">
                <h3 className="section-card-title">RESUMEN: ¿LA IA MEJORA LA OPERACIÓN?</h3>
                <MetricTooltip
                  title="Cómo se obtuvo este resumen"
                  description="El horario de la IA y la operación actual se simularon en días que la IA nunca vio durante su búsqueda, con los mismos pasajeros en ambos casos. Se compara día por día."
                  interpretation="Verde = mejora confirmada estadísticamente (intervalo de confianza al 95% sin el cero). Rojo = empeora de forma confirmada. Gris = sin cambio demostrable."
                />
              </div>
              <p className="section-card-subtitle">
                {holdout
                  ? `Validado en ${holdout.utilidad.semillas} días simulados nuevos, frente a la operación actual de TransMilenio.`
                  : 'Sin validación fuera de muestra disponible.'}
              </p>
            </div>
          </div>
          {holdout && (
            <>
              <p className={`exec-verdict ${holdout.utilidad.significativo && holdout.utilidad.mejora ? 'good' : 'neutral'}`}>
                {holdout.utilidad.significativo && holdout.utilidad.mejora
                  ? `Sí: con ${optFleet ?? PLACEHOLDER} buses (hoy ${baseFleet ?? PLACEHOLDER}) la IA reduce el hacinamiento y mejora la utilidad de forma significativa; a cambio la espera media cambia ${formatSigned(holdout.espera_min.diferencia_pct, 2, '%')}.`
                  : 'La mejora de la utilidad no es estadísticamente significativa con días nuevos.'}
              </p>
              <div className="exec-cards">
                <ExecCard label="Utilidad U(S)" stat={holdout.utilidad} digits={4} absolute help="Nota global del horario: combina espera, hacinamiento, pasajeros varados y flota según los pesos del proyecto." />
                <ExecCard label="Buses con sobrecupo ≥ 95%" stat={holdout.sobrecupo_pct} digits={2} unit="%" help="Porcentaje de llegadas de bus a una estación con el bus casi lleno." />
                <ExecCard label="Espera media en andén" stat={holdout.espera_min} digits={3} unit=" min" help="Minutos promedio que espera un pasajero." />
                <ExecCard label="Pasajeros transportados" stat={holdout.transportados} digits={0} help="Personas que abordaron un bus entre 06:00 y 09:00." />
                <div className="exec-card">
                  <span className="exec-card-label">Flota física</span>
                  <span className="exec-card-value font-mono tabular-nums">
                    {baseFleet ?? PLACEHOLDER} → {optFleet ?? PLACEHOLDER}
                  </span>
                  <span className="exec-card-sub">buses · cota {MAX_FLEET} (sin compras)</span>
                </div>
              </div>
            </>
          )}
        </section>

        {/* ==================================================================
            FASE 1: DIAGNÓSTICO DE DEMANDA - MATRIZ ORIGEN - DESTINO (TULLAVE)
            ================================================================== */}
        <section className="analytics-section-card">
          <div className="section-card-header">
            <div>
              <div className="section-title-with-tooltip">
                <h3 className="section-card-title">1. ¿A DÓNDE VIAJA LA GENTE? (MATRIZ ORIGEN – DESTINO)</h3>
                <MetricTooltip
                  title="Matriz Origen-Destino (Demanda TuLlave)"
                  description="Viajes simulados por par origen–destino. El origen viene de las validaciones de entrada; el destino, de un modelo gravitacional sobre las salidas observadas (el recaudo troncal no registra el destino de cada viaje)."
                  interpretation="Identifica los pares de mayor demanda para decidir qué servicios (expresos o corrientes) deben reforzarse."
                  flowtmGoal="Dimensionar la oferta en las rutas expresas prioritarias para maximizar la velocidad comercial."
                />
              </div>
              <p className="section-card-subtitle">
                Pares origen–destino más frecuentes en la simulación base: llegadas Poisson calibradas con validaciones
                tullave y destinos según las salidas AM observadas (modelo gravitacional).
              </p>
            </div>
            <span className="badge-tullave font-mono">DEMANDA: VALIDACIONES TULLAVE</span>
          </div>

          <div className="od-flow-grid">
            {odPairs.length === 0 && (
              <div className="od-flow-card">
                <span className="od-pair-sub">Sin datos OD exportados para el escenario base.</span>
              </div>
            )}
            {odPairs.map((pair) => (
              <div className="od-flow-card" key={`${pair.origin}-${pair.destination}`}>
                <div className="od-card-header">
                  <span className="od-pair-name">
                    {pair.origin_name} &rarr; {pair.destination_name}
                  </span>
                  <span className="od-pair-val font-mono tabular-nums">
                    {pair.passengers.toLocaleString()} pax ({pair.share_pct.toFixed(1)}%)
                  </span>
                </div>
                <div className="od-progress-track">
                  <div
                    className="od-progress-fill"
                    style={{ width: `${Math.min(100, pair.share_pct)}%`, backgroundColor: 'var(--accent-blue)' }}
                  />
                </div>
                <span className="od-pair-sub">
                  {pair.destination === 'SUR'
                    ? 'Viajes que continúan al sur de Marly (Centro, Calle 26, Caracas Sur)'
                    : 'Viaje interno del corredor'}
                </span>
              </div>
            ))}
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
                  ? '2. OPERACIÓN COMPARADA: ACTUAL (GTFS) vs. HORARIO DEL AGENTE'
                  : '2. OPERACIÓN ACTUAL (GTFS DE TRANSMILENIO)'}
              </h3>
              <p className="section-card-subtitle">
                Una simulación de 06:00 a 09:00 (semilla 42), la misma que reproduce el mapa. Las colas por estación
                cambian con el reloj. La conclusión estadística (30 semillas) está en el resumen y en las metas.
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
              <h2 className="hero-title">3. ¿Cómo decide la IA?</h2>
              <p className="hero-subtitle">
                El agente prueba horarios H &isin; [2, 15]⁶ (minutos entre buses de cada ruta), simula cada uno en el
                gemelo digital y lo califica con la utilidad U(S). Nunca usa más de {MAX_FLEET} buses. La tabla muestra
                qué término de U(S) mejoró y el gráfico cómo convergió la búsqueda.
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
                  Verde: mejor utilidad encontrada (nunca baja). Azul: utilidad del horario en el que está el agente; baja
                  cuando acepta empeorar para explorar. {totalIterations} iteraciones; pase el cursor por un punto para ver ese
                  horario.
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
                {chartMetrics.ticks.map((u) => {
                  const y = getSvgY(u);
                  return (
                    <g key={u}>
                      <line x1={padX} y1={y} x2={svgWidth - padX} y2={y} stroke="var(--border-subtle)" strokeDasharray="3 3" />
                      <text x={padX - 8} y={y + 4} fill="var(--text-tertiary)" fontSize="10" textAnchor="end" className="font-mono">
                        {u.toFixed(3)}
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
                  Operación actual U₀ = {formatFixed(baseU, 4)}
                </text>

                {/* Area under curve */}
                <path d={areaPath} fill="url(#chartGradient)" />

                {/* Current-state utility (exploration) and best-so-far (convergence) */}
                <path d={pointsPath} fill="none" stroke="var(--accent-blue)" strokeWidth="1.5" strokeOpacity="0.7" strokeLinecap="round" strokeLinejoin="round" />
                <path d={bestPath} fill="none" stroke="var(--accent-green)" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />

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
                  <span className="strip-temp font-mono">T = {activeInspectorIteration.temperature?.toFixed(4) ?? '—'}</span>
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

            {/* U(S) term by term: current operation vs agent (explains where the gain comes from) */}
            <div className="utility-breakdown-table">
              <div className="ubt-row ubt-head">
                <span>Término de U(S)</span>
                <span>Peso</span>
                <span>Actual</span>
                <span>Agente</span>
                <span>Costo actual → agente</span>
              </div>
              {UTILITY_TERMS.map((term) => {
                const baseCost = aiLog?.baseline?.breakdown?.[term.key];
                const optCost = aiLog?.optimized?.breakdown?.[term.key];
                const delta = baseCost !== undefined && optCost !== undefined ? optCost - baseCost : undefined;
                return (
                  <div className="ubt-row" key={term.key}>
                    <span className="ubt-name">
                      {term.label}
                      <MetricTooltip title={term.label} description={term.help} />
                    </span>
                    <span className="font-mono tabular-nums">{term.weight}</span>
                    <span className="font-mono tabular-nums">{term.value(aiLog?.baseline)}</span>
                    <span className="font-mono tabular-nums">{term.value(aiLog?.optimized)}</span>
                    <span className={`font-mono tabular-nums ${delta === undefined ? '' : delta < 0 ? 'text-success' : delta > 0 ? 'text-alert' : ''}`}>
                      {formatFixed(baseCost, 4)} → {formatFixed(optCost, 4)}
                      {delta !== undefined && ` (${formatSigned(delta, 4)})`}
                    </span>
                  </div>
                );
              })}
              <p className="ubt-note">
                U(S) = −(suma de costos): un costo menor sube la utilidad. Valores esperados sobre las semillas de
                entrenamiento. Aquí se ve de dónde sale la mejora del agente.
              </p>
            </div>
          </div>

          {/* Quantitative goals, judged on out-of-sample seeds (Section 8) */}
          <div className="analytics-section-card">
            <div className="section-card-header">
              <div>
                <div className="section-title-with-tooltip">
                  <h4 className="section-card-title">4. METAS DEL PROYECTO (AVANCE II, SECCIÓN 8)</h4>
                  <MetricTooltip
                    title="Metas evaluadas fuera de muestra"
                    description="Cada meta se evalúa con semillas que el agente nunca vio durante la búsqueda: diferencia pareada entre el horario del agente y la operación actual, con intervalo de confianza al 95%."
                    interpretation="Una meta solo se marca como cumplida si la mejora es estadísticamente significativa; así se evita reportar mejoras que solo existen en la semilla de entrenamiento."
                    flowtmGoal="Reducción de espera, contención de sobrecupo y ganancia neta positiva de utilidad sin flota adicional."
                  />
                </div>
                <p className="section-card-subtitle">
                  {holdout
                    ? `Validación con ${holdout.espera_min.semillas} semillas nuevas (diferencia pareada vs. operación actual, IC 95%).`
                    : 'Sin validación fuera de muestra en el log del agente.'}
                </p>
              </div>
              {holdout && (
                <span className="verified-badge">
                  <CheckCircle size={14} weight="fill" /> VALIDADO FUERA DE MUESTRA
                </span>
              )}
            </div>

            <div className="goals-matrix-grid">
              {holdout && (
                <>
                  <GoalCard
                    title="Tiempo Medio Espera (W_prom)"
                    target={`Meta: ≥ ${WAIT_REDUCTION_GOAL_PCT}% red.`}
                    stat={holdout.espera_min}
                    digits={3}
                    unit=" min"
                    meetsGoal={(st) => st.mejora && st.significativo && st.diferencia_pct <= -WAIT_REDUCTION_GOAL_PCT}
                    description={(st) =>
                      st.significativo && !st.mejora
                        ? 'La espera media empeora levemente: el agente prioriza reducir el sobrecupo según los pesos de U(S).'
                        : `La meta del ${WAIT_REDUCTION_GOAL_PCT}% de reducción de espera no se alcanza con la oferta actual.`
                    }
                  />
                  <GoalCard
                    title="Ganancia de Utilidad (ΔU)"
                    target="Meta: ΔU > 0 significativo"
                    stat={holdout.utilidad}
                    digits={4}
                    absolute
                    meetsGoal={(st) => st.mejora && st.significativo}
                    description={(st) =>
                      st.mejora && st.significativo
                        ? 'La mejora de la utilidad multicriterio se sostiene con semillas nuevas.'
                        : 'La diferencia de utilidad no es significativa fuera de muestra.'
                    }
                  />
                  <GoalCard
                    title="Sobrecupo Crítico (≥ 95%)"
                    target="Meta: reducir el hacinamiento"
                    stat={holdout.sobrecupo_pct}
                    digits={2}
                    unit="%"
                    meetsGoal={(st) => st.mejora && st.significativo}
                    description={() => 'Fracción de llegadas de bus a estación con ocupación ≥ 95%.'}
                  />
                </>
              )}

              <div className="goal-item-card">
                <div className="goal-top">
                  <span className="goal-title">Uso Total de Flota (B_usados)</span>
                  <span className={`goal-status-pill ${optFleet !== undefined && maxFleet !== undefined && optFleet <= maxFleet ? 'ok' : 'partial'}`}>
                    {optFleet !== undefined && maxFleet !== undefined && optFleet <= maxFleet ? 'CUMPLE' : 'EXCEDIDO'}
                  </span>
                </div>
                <div className="goal-vals">
                  <span className="goal-target font-mono">Meta: &le; {MAX_FLEET} buses</span>
                  <span className="goal-achieved font-mono">
                    {optFleet ?? PLACEHOLDER} / {MAX_FLEET} buses
                    {fleetSaved !== undefined && ` (-${fleetSaved} fl.)`}
                  </span>
                </div>
                <p className="goal-desc">
                  Cota por construcción: el agente nunca evalúa ni acepta un horario que exceda la flota actual.
                </p>
              </div>
            </div>
          </div>

          {/* Controlled experiment: SA vs simpler agents with the same budget */}
          {comparison && (
            <div className="analytics-section-card">
              <div className="section-card-header">
                <div>
                  <div className="section-title-with-tooltip">
                    <h4 className="section-card-title">5. ¿POR QUÉ RECOCIDO SIMULADO? (EXPERIMENTO)</h4>
                    <MetricTooltip
                      title="Comparación controlada de algoritmos"
                      description={`Búsqueda aleatoria, hill climbing y recocido simulado con el mismo presupuesto (${comparison.presupuesto_evaluaciones} horarios × ${comparison.semillas_entrenamiento.length} semillas), ${comparison.corridas_por_algoritmo} corridas cada uno, validados con ${comparison.semillas_validacion} semillas nuevas.`}
                      interpretation="La búsqueda aleatoria no encuentra horarios mejores que el diseñado por TransMilenio; hill climbing se estanca en óptimos locales; el recocido simulado escapa de ellos aceptando empeoramientos controlados por la temperatura."
                      flowtmGoal="Justificar empíricamente la elección de la metaheurística."
                    />
                  </div>
                  <p className="section-card-subtitle">
                    ΔU en validación fuera de muestra (media y rango de {comparison.corridas_por_algoritmo} corridas por algoritmo).
                  </p>
                </div>
              </div>
              <div className="algo-compare-table">
                {Object.entries(comparison.resumen).map(([name, row]) => {
                  const widthPct = Math.max(0, (row.delta_u_validacion_media / comparisonMaxDelta) * 100);
                  return (
                    <div className="algo-compare-row" key={name}>
                      <span className="algo-name">{ALGORITHM_NAMES[name] ?? name}</span>
                      <div className="algo-bar-track">
                        <div className="algo-bar-fill" style={{ width: `${widthPct}%` }} />
                      </div>
                      <span className="algo-delta font-mono tabular-nums">
                        {formatSigned(row.delta_u_validacion_media, 4)}{' '}
                        <span className="text-muted">
                          [{formatSigned(row.delta_u_validacion_min, 4)}, {formatSigned(row.delta_u_validacion_max, 4)}]
                        </span>
                      </span>
                      <span className="algo-sig font-mono tabular-nums">
                        {row.corridas_significativas}/{comparison.corridas_por_algoritmo} significativas
                      </span>
                      <span className="algo-extra font-mono tabular-nums">
                        espera {formatSigned(row.espera_pct_media, 2, '%')} · sobrecupo {formatSigned(row.sobrecupo_pct_media, 2, '%')}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </section>

        {/* ==================================================================
            FASE 4: ENTREGABLE OFICIAL Y ACTUADOR DEL AGENTE GTFS
            ================================================================== */}
        <section className="gtfs-actuator-delivery-card">
          <div className="gtfs-delivery-content">
            <div className="gtfs-delivery-text">
              <div className="section-title-with-tooltip">
                <h3 className="gtfs-delivery-title">6. ENTREGABLE: HORARIO EN FORMATO GTFS (frequencies.txt)</h3>
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
                <span className="vector-label">Intervalos (actual → agente):</span>
                <span className="vector-values">
                  {Object.entries(gtfsHeadways)
                    .map(([r, h]) => `${r}: ${formatFixed(baseHeadways[r], 2)} → ${Number(h).toFixed(2)} min`)
                    .join('  |  ')}
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
