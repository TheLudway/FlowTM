import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Brain, Lightning, MapTrifold, Play, Stop, Warning } from '@phosphor-icons/react';
import type {
  AgentRunPayload,
  AIOptimizationIteration,
  AIOptimizationLog,
  HoldoutReport,
  PairedStat,
  ReplayPayload,
  RouteConfig,
} from '../types';
import { MetricTooltip } from './MetricTooltip';
import './AgentLab.css';

type Algorithm = 'recocido_simulado' | 'hill_climbing' | 'busqueda_aleatoria';
type Status = 'idle' | 'running' | 'done' | 'error';

interface ScenarioInfo {
  rutas_optimizables: string[];
  rutas_fondo: string[];
  intervalos_base: Record<string, number>;
  flota_base: number;
  flota_maxima: number;
  pesos_por_defecto: Weights;
  limites: { presupuesto: number; semillas: number };
}

interface Weights {
  espera: number;
  sobrecupo: number;
  varados: number;
  flota: number;
}

interface EvaluationSummary {
  headways: Record<string, number>;
  utility: number;
  utility_se?: number;
  fleet_used: number;
  metrics: Record<string, number>;
  breakdown?: Record<string, number>;
}

interface AgentResult {
  algoritmo: string;
  evaluaciones: number;
  parametros: Record<string, number>;
  inicial: EvaluationSummary;
  mejor: EvaluationSummary;
  delta_utilidad: number;
  validacion: HoldoutReport;
  replay: ReplayPayload;
}

const ALGORITHM_LABELS: Record<Algorithm, string> = {
  recocido_simulado: 'Recocido simulado',
  hill_climbing: 'Hill climbing',
  busqueda_aleatoria: 'Búsqueda aleatoria',
};

const WEIGHT_LABELS: Record<keyof Weights, string> = {
  espera: 'Tiempo de espera',
  sobrecupo: 'Sobrecupo (≥95%)',
  varados: 'Pasajeros varados',
  flota: 'Uso de flota',
};

const fmtSigned = (value: number, digits: number, suffix = '') =>
  `${value >= 0 ? '+' : ''}${value.toFixed(digits)}${suffix}`;

function toLog(
  scenario: ScenarioInfo,
  result: AgentResult,
  history: AIOptimizationIteration[],
  maxFleet: number,
): AIOptimizationLog {
  const summarize = (e: EvaluationSummary) => ({
    headways: e.headways,
    fleet_used: e.fleet_used,
    utility: e.utility,
    breakdown: e.breakdown ?? {},
    wait_time_min: e.metrics.avg_waiting_time_min,
    stranded_pax: e.metrics.stranded_passengers_in_queue,
    overcrowded_pct: e.metrics.overcrowded_bus_pct,
    transported_pax: e.metrics.total_transported_passengers,
  });
  return {
    baseline: summarize(result.inicial),
    optimized: summarize(result.mejor),
    delta_utility: result.delta_utilidad,
    max_fleet: maxFleet,
    holdout: result.validacion,
    optimizable_routes: scenario.rutas_optimizables,
    background_routes: scenario.rutas_fondo,
    history,
  };
}

const StatRow: React.FC<{ label: string; stat: PairedStat; digits: number; unit?: string; absolute?: boolean }> = ({
  label,
  stat,
  digits,
  unit = '',
  absolute = false,
}) => {
  const tone = !stat.significativo ? 'neutral' : stat.mejora ? 'good' : 'bad';
  return (
    <div className="lab-stat-row">
      <span className="lab-stat-label">{label}</span>
      <span className="lab-stat-values font-mono tabular-nums">
        {stat.base.toFixed(digits)} → {stat.candidato.toFixed(digits)}
        {unit}
      </span>
      <span className={`lab-stat-delta tone-${tone} font-mono tabular-nums`}>
        {absolute ? fmtSigned(stat.diferencia, digits) : fmtSigned(stat.diferencia_pct, 2, '%')}
      </span>
      <span className="lab-stat-ci font-mono tabular-nums">
        IC95 [{stat.ic95[0].toFixed(digits)}, {stat.ic95[1].toFixed(digits)}] · {stat.semillas_mejor}/{stat.semillas}
      </span>
    </div>
  );
};

export const AgentLab: React.FC<{
  routes: RouteConfig[];
  onShowOnMap: (run: AgentRunPayload) => void;
}> = ({ routes, onShowOnMap }) => {
  const [scenario, setScenario] = useState<ScenarioInfo | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [algorithm, setAlgorithm] = useState<Algorithm>('recocido_simulado');
  const [budget, setBudget] = useState(60);
  const [seeds, setSeeds] = useState(5);
  const [step, setStep] = useState(0.5);
  const [searchSeed, setSearchSeed] = useState(42);
  const [maxFleet, setMaxFleet] = useState<number | null>(null);
  const [weights, setWeights] = useState<Weights>({ espera: 0.4, sobrecupo: 0.3, varados: 0.15, flota: 0.15 });

  const [status, setStatus] = useState<Status>('idle');
  const [history, setHistory] = useState<AIOptimizationIteration[]>([]);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    fetch('/api/escenario')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: ScenarioInfo) => {
        setScenario(data);
        setMaxFleet(data.flota_maxima);
        setWeights(data.pesos_por_defecto);
      })
      .catch(() => setApiError('No se pudo contactar la API del agente.'));
    return () => sourceRef.current?.close();
  }, []);

  const routeColor = useMemo(() => new Map(routes.map((r) => [r.id, r.color])), [routes]);
  const weightTotal = weights.espera + weights.sobrecupo + weights.varados + weights.flota;

  const stop = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setStatus((current) => (current === 'running' ? 'idle' : current));
  }, []);

  const run = useCallback(async () => {
    setHistory([]);
    setResult(null);
    setRunError(null);
    setStatus('running');
    try {
      const response = await fetch('/api/agente', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          algoritmo: algorithm,
          presupuesto: budget,
          semillas: seeds,
          paso_min: step,
          semilla_busqueda: searchSeed,
          flota_maxima: maxFleet,
          pesos: weights,
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail ? JSON.stringify(detail.detail) : `HTTP ${response.status}`);
      }
      const { job_id: jobId } = await response.json();
      const source = new EventSource(`/api/agente/${jobId}/eventos`);
      sourceRef.current = source;
      source.addEventListener('iteracion', (event) => {
        const entry = JSON.parse((event as MessageEvent).data) as AIOptimizationIteration;
        setHistory((previous) => [...previous, entry]);
      });
      source.addEventListener('resultado', (event) => {
        setResult(JSON.parse((event as MessageEvent).data) as AgentResult);
        setStatus('done');
        source.close();
      });
      source.addEventListener('error', (event) => {
        const data = (event as MessageEvent).data;
        if (data) {
          setRunError(JSON.parse(data).mensaje);
          setStatus('error');
        }
        source.close();
      });
    } catch (error) {
      setRunError(error instanceof Error ? error.message : String(error));
      setStatus('error');
    }
  }, [algorithm, budget, seeds, step, searchSeed, maxFleet, weights]);

  // Convergence chart geometry
  const chart = useMemo(() => {
    if (history.length < 2) return null;
    const width = 760;
    const height = 220;
    const pad = 40;
    const values = history.flatMap((h) => [h.utility, h.best_utility]);
    const minU = Math.min(...values);
    const maxU = Math.max(...values);
    const span = Math.max(1e-6, maxU - minU);
    const lastIteration = history[history.length - 1].iteration || 1;
    const x = (i: number) => pad + (i / lastIteration) * (width - 2 * pad);
    const y = (u: number) => height - pad - ((u - minU) / span) * (height - 2 * pad);
    const path = (key: 'utility' | 'best_utility') =>
      history.map((h, i) => `${i === 0 ? 'M' : 'L'}${x(h.iteration).toFixed(1)},${y(h[key]).toFixed(1)}`).join(' ');
    return { width, height, pad, minU, maxU, x, y, current: path('utility'), best: path('best_utility') };
  }, [history]);

  const latest = history[history.length - 1];
  const evaluationsDone = latest?.evaluations ?? 0;

  if (apiError) {
    return (
      <div className="agent-lab-container">
        <section className="lab-card lab-offline">
          <Warning size={22} weight="fill" color="var(--accent-yellow)" />
          <div>
            <h3>{apiError}</h3>
            <p>
              El laboratorio ejecuta el agente en vivo sobre el gemelo digital. Inicie el backend en otra terminal:
            </p>
            <code>uv run uvicorn flowtm.api.app:app --port 8000</code>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="agent-lab-container">
      <header className="lab-header">
        <div>
          <span className="lab-eyebrow">AGENTE RACIONAL · BÚSQUEDA EN VIVO SOBRE EL GEMELO DIGITAL</span>
          <h1 className="lab-title">Laboratorio del Agente</h1>
          <p className="lab-subtitle">
            Configure la función de utilidad, la cota de flota y el algoritmo. Cada horario candidato se simula con{' '}
            {seeds} semilla{seeds > 1 ? 's' : ''} (utilidad esperada) y el mejor se valida con 10 semillas que el agente
            nunca vio.
          </p>
        </div>
      </header>

      <section className="lab-card lab-guide">
        <h4 className="lab-card-title">¿Qué hace este laboratorio?</h4>
        <ol className="lab-guide-steps">
          <li>
            <b>El problema.</b> TransMilenio tiene un número fijo de buses ({scenario?.flota_base ?? '—'} para estas 6
            rutas). La IA decide <em>cada cuántos minutos sale un bus</em> de cada ruta para que la gente espere menos y
            viaje menos apretada, sin comprar buses nuevos.
          </li>
          <li>
            <b>Cómo decide.</b> Prueba un horario, lo simula en el gemelo digital (pasajeros reales de TransMilenio) y le
            pone una nota, la <em>utilidad U(S)</em>: más alta es mejor. Luego cambia un poco el horario y repite, quedándose
            con los mejores.
          </li>
          <li>
            <b>Qué puede tocar usted.</b> Qué tan importante es cada objetivo (pesos), cuántos buses hay (cota de flota) y
            cuánto tiempo busca (presupuesto). Pulse <em>Ejecutar agente</em> y mire la curva verde subir.
          </li>
          <li>
            <b>Cómo saber si funcionó.</b> Al final, el mejor horario se prueba en días simulados que la IA nunca vio. Si
            la mejora se mantiene, aparece en verde.
          </li>
        </ol>
      </section>

      <div className="lab-grid">
        {/* Controls */}
        <section className="lab-card lab-controls">
          <h4 className="lab-card-title">
            <Brain size={15} weight="bold" /> Configuración
          </h4>

          <label className="lab-field">
            <span className="lab-label-help">
              Algoritmo
              <MetricTooltip
                title="Algoritmo de búsqueda"
                description="Estrategia que usa la IA para explorar horarios. Recocido simulado acepta a veces empeorar para no quedarse atascado; hill climbing solo acepta mejoras; búsqueda aleatoria prueba horarios al azar."
                interpretation="El recocido simulado es el agente del proyecto: en el experimento fue el único que mejoró de forma significativa (ver Analítica)."
              />
            </span>
            <select value={algorithm} onChange={(e) => setAlgorithm(e.target.value as Algorithm)} disabled={status === 'running'}>
              {Object.entries(ALGORITHM_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label className="lab-field">
            <span className="lab-label-help">
              Presupuesto <b className="font-mono">{budget}</b> horarios
              <MetricTooltip
                title="Presupuesto de búsqueda"
                description="Cuántos horarios distintos puede probar la IA. Cada uno se simula varias veces (las semillas)."
                interpretation="Más presupuesto = búsqueda más larga y normalmente mejores resultados. 60 tarda ~30 s; 150 ~80 s."
              />
            </span>
            <input type="range" min={10} max={scenario?.limites.presupuesto ?? 300} step={10} value={budget}
              onChange={(e) => setBudget(Number(e.target.value))} disabled={status === 'running'} />
          </label>

          <label className="lab-field">
            <span className="lab-label-help">
              Semillas por evaluación <b className="font-mono">{seeds}</b>
              <MetricTooltip
                title="Semillas (días simulados)"
                description="Cada semilla es un día distinto: los pasajeros llegan en momentos diferentes. La nota de un horario es el promedio sobre estas semillas."
                interpretation="Con 1 semilla la IA puede elegir un horario que solo tuvo suerte ese día; con 5 o más la decisión es más confiable."
              />
            </span>
            <input type="range" min={1} max={scenario?.limites.semillas ?? 10} value={seeds}
              onChange={(e) => setSeeds(Number(e.target.value))} disabled={status === 'running'} />
          </label>

          <div className="lab-field-row">
            <label className="lab-field">
              <span className="lab-label-help">
                Paso (min)
                <MetricTooltip
                  title="Tamaño del paso"
                  description="Cuántos minutos cambia el intervalo de una ruta en cada movimiento de la IA."
                  interpretation="Pasos pequeños afinan; pasos grandes exploran más rápido pero con menos precisión."
                />
              </span>
              <select value={step} onChange={(e) => setStep(Number(e.target.value))} disabled={status === 'running'}>
                {[0.25, 0.5, 1, 2].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label className="lab-field">
              <span className="lab-label-help">
                Semilla búsqueda
                <MetricTooltip
                  title="Semilla de la búsqueda"
                  description="Fija las decisiones aleatorias de la IA para que el resultado se pueda repetir exactamente."
                  interpretation="Cámbiela para ver otra corrida independiente del mismo algoritmo."
                />
              </span>
              <input type="number" value={searchSeed} onChange={(e) => setSearchSeed(Number(e.target.value))}
                disabled={status === 'running'} />
            </label>
          </div>

          <label className="lab-field">
            <span className="lab-label-help">
              Cota de flota B<sub>max</sub> <b className="font-mono">{maxFleet ?? '—'}</b>
              {scenario && <em> (operación actual: {scenario.flota_base})</em>}
              <MetricTooltip
                title="Cota de flota (sin comprar buses)"
                description="Número máximo de buses que la IA puede usar en las 6 rutas, contando ida y regreso. El valor por defecto es la flota que TransMilenio usa hoy según el GTFS."
                interpretation="Bájela para preguntar: ¿qué tan bien se puede operar con menos buses? La IA nunca propone un horario que la exceda."
              />
            </span>
            <input type="range" min={scenario ? Math.round(scenario.flota_base * 0.7) : 0}
              max={scenario?.flota_base ?? 0} value={maxFleet ?? 0}
              onChange={(e) => setMaxFleet(Number(e.target.value))} disabled={status === 'running' || !scenario} />
          </label>

          <h5 className="lab-subtitle-sm lab-label-help">
            Pesos de U(S)
            <MetricTooltip
              title="Pesos de la utilidad U(S)"
              description="Qué tan importante es cada objetivo para la nota del horario. Se normalizan para sumar 100%."
              interpretation="Ejemplo: si sube 'Tiempo de espera', la IA preferirá horarios con menos espera aunque los buses vayan más llenos. Los valores por defecto son los del Avance II."
            />
          </h5>
          {(Object.keys(WEIGHT_LABELS) as (keyof Weights)[]).map((key) => (
            <label className="lab-field lab-weight" key={key}>
              <span>
                {WEIGHT_LABELS[key]}{' '}
                <b className="font-mono">{weightTotal > 0 ? ((weights[key] / weightTotal) * 100).toFixed(0) : 0}%</b>
              </span>
              <input type="range" min={0} max={1} step={0.05} value={weights[key]}
                onChange={(e) => setWeights((w) => ({ ...w, [key]: Number(e.target.value) }))}
                disabled={status === 'running'} />
            </label>
          ))}

          {status === 'running' ? (
            <button className="lab-run-btn stop" onClick={stop}>
              <Stop size={15} weight="fill" /> Detener visualización
            </button>
          ) : (
            <button className="lab-run-btn" onClick={run} disabled={!scenario || weightTotal <= 0}>
              <Play size={15} weight="fill" /> Ejecutar agente
            </button>
          )}
        </section>

        {/* Live convergence */}
        <section className="lab-card lab-live">
          <div className="lab-live-header">
            <h4 className="lab-card-title">
              <Lightning size={15} weight="bold" /> Convergencia en vivo
              <MetricTooltip
                title="Cómo leer la curva"
                description="Cada punto es un horario probado. Azul: la nota del horario en el que está la IA. Verde: la mejor nota encontrada hasta ahora (nunca baja). Gris: horarios rechazados."
                interpretation="Al inicio la IA acepta empeorar para explorar (temperatura alta); al final solo acepta mejoras. Si la línea verde deja de subir, la búsqueda convergió."
              />
            </h4>
            {status !== 'idle' && (
              <span className="lab-progress-label font-mono tabular-nums">
                {evaluationsDone}/{budget} horarios · {evaluationsDone * seeds} simulaciones
              </span>
            )}
          </div>
          <div className="lab-progress-track">
            <div className="lab-progress-fill" style={{ width: `${Math.min(100, (evaluationsDone / budget) * 100)}%` }} />
          </div>

          {chart ? (
            <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="lab-chart" preserveAspectRatio="none">
              <text x={chart.pad - 6} y={chart.y(chart.maxU) + 4} textAnchor="end" className="lab-axis">
                {chart.maxU.toFixed(3)}
              </text>
              <text x={chart.pad - 6} y={chart.y(chart.minU) + 4} textAnchor="end" className="lab-axis">
                {chart.minU.toFixed(3)}
              </text>
              <path d={chart.current} className="lab-line-current" />
              <path d={chart.best} className="lab-line-best" />
              {history.map((h) => (
                <circle key={h.iteration} cx={chart.x(h.iteration)} cy={chart.y(h.utility)} r={h.is_new_best ? 4 : 2.2}
                  className={h.is_new_best ? 'lab-dot-best' : h.accepted ? 'lab-dot-accepted' : 'lab-dot-rejected'} />
              ))}
            </svg>
          ) : (
            <div className="lab-chart-empty">
              {status === 'running' ? 'Evaluando el horario inicial…' : 'Ejecute el agente para ver cómo explora el espacio de horarios.'}
            </div>
          )}
          <div className="lab-legend">
            <span><i className="sw sw-current" /> Utilidad del estado actual</span>
            <span><i className="sw sw-best" /> Mejor encontrada</span>
            <span><i className="sw sw-rejected" /> Rechazado</span>
          </div>

          {latest && (
            <div className="lab-live-metrics font-mono tabular-nums">
              <span>Iter {latest.iteration}</span>
              {latest.temperature !== null && latest.temperature !== undefined && <span>T = {latest.temperature.toFixed(4)}</span>}
              <span>U actual {latest.utility.toFixed(4)}</span>
              <span>Mejor {latest.best_utility.toFixed(4)}</span>
              <span>Flota {latest.fleet_used}/{maxFleet}</span>
            </div>
          )}

          {scenario && (
            <div className="lab-headways">
              {scenario.rutas_optimizables.map((route) => {
                const base = scenario.intervalos_base[route];
                const current = (result?.mejor.headways ?? latest?.headways ?? scenario.intervalos_base)[route];
                const delta = current - base;
                return (
                  <div className="lab-headway-item" key={route}>
                    <span className="route-tag" style={{ backgroundColor: routeColor.get(route) ?? '#9E9E9E' }}>{route}</span>
                    <span className="font-mono tabular-nums">
                      {base.toFixed(2)} → <b>{current.toFixed(2)}</b> min
                    </span>
                    {Math.abs(delta) > 1e-6 && (
                      <span className={`lab-headway-delta ${delta < 0 ? 'more' : 'less'}`}>
                        {delta < 0 ? '+ frecuencia' : '− frecuencia'}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {runError && (
            <div className="lab-error">
              <Warning size={14} weight="fill" /> {runError}
            </div>
          )}
        </section>
      </div>

      {/* Result */}
      {result && scenario && (
        <section className="lab-card lab-result">
          <div className="lab-result-header">
            <div>
              <h4 className="lab-card-title">
                Resultado · {ALGORITHM_LABELS[result.algoritmo as Algorithm] ?? result.algoritmo}
                <MetricTooltip
                  title="Resultado y validación"
                  description="El mejor horario encontrado se vuelve a simular en 10 días que la IA nunca vio y se compara, día por día, con la operación actual."
                  interpretation="Verde: mejora confirmada (el intervalo de confianza al 95% no incluye el cero). Rojo: empeora de forma confirmada. Gris: no se puede afirmar que cambie."
                />
              </h4>
              <p className="lab-subtitle">
                Entrenamiento ({seeds} semillas): ΔU = <b className="font-mono">{fmtSigned(result.delta_utilidad, 4)}</b> ·{' '}
                {result.evaluaciones} horarios evaluados · flota {result.inicial.fleet_used} → {result.mejor.fleet_used}
              </p>
            </div>
            <button className="lab-run-btn secondary"
              onClick={() =>
                onShowOnMap({
                  replay: result.replay,
                  log: toLog(scenario, result, history, maxFleet ?? scenario.flota_maxima),
                  source: {
                    algorithm: ALGORITHM_LABELS[result.algoritmo as Algorithm] ?? result.algoritmo,
                    finishedAt: new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }),
                    deltaU: result.validacion.utilidad.diferencia,
                    validated: result.validacion.utilidad.significativo && result.validacion.utilidad.mejora,
                  },
                })
              }>
              <MapTrifold size={15} weight="bold" /> Ver en el mapa comparativo
            </button>
          </div>

          <h5 className="lab-subtitle-sm">
            Validación fuera de muestra ({result.validacion.utilidad.semillas} semillas nuevas, diferencia pareada vs. operación actual)
          </h5>
          <div className={`lab-verdict ${result.validacion.utilidad.significativo ? (result.validacion.utilidad.mejora ? 'good' : 'bad') : 'neutral'}`}>
            {result.validacion.utilidad.significativo
              ? result.validacion.utilidad.mejora
                ? 'La mejora en utilidad se sostiene con semillas nuevas (IC 95% > 0).'
                : 'El horario es peor que la operación actual con semillas nuevas.'
              : 'La diferencia en utilidad no es estadísticamente significativa con semillas nuevas.'}
          </div>
          <StatRow label="Utilidad U(S)" stat={result.validacion.utilidad} digits={4} absolute />
          <StatRow label="Espera media" stat={result.validacion.espera_min} digits={3} unit=" min" />
          <StatRow label="Buses con sobrecupo" stat={result.validacion.sobrecupo_pct} digits={2} unit="%" />
          <StatRow label="Pasajeros varados" stat={result.validacion.varados} digits={0} />
          <StatRow label="Transportados" stat={result.validacion.transportados} digits={0} />
          <p className="lab-footnote">
            Verde/rojo: el intervalo de confianza al 95% de la diferencia pareada excluye el cero (mejora/empeora con
            significancia). Gris: diferencia no significativa. «a/b»: semillas en las que el horario del agente es mejor.
          </p>
        </section>
      )}
    </div>
  );
};
