import React from 'react';
import {
  CheckCircle,
  Clock,
  Gauge,
  Sparkle,
  TrendDown,
  TrendUp,
  Users,
  Warning,
  X,
} from '@phosphor-icons/react';
import { MetricTooltip } from './MetricTooltip';
import type { InterpolatedBus, RouteConfig, Station, SummaryKPIs } from '../types';

/** One base-vs-optimized KPI row; lower values are better for every metric shown. */
const CompareCard: React.FC<{
  title: string;
  icon: React.ReactNode;
  tooltip: { title: string; description: string; interpretation?: string };
  base: number | undefined;
  optimized: number | undefined;
  digits: number;
  unit: string;
}> = ({ title, icon, tooltip, base, optimized, digits, unit }) => {
  const fmt = (v: number | undefined) => (v === undefined ? '—' : `${v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })}${unit}`);
  const delta = base !== undefined && optimized !== undefined ? optimized - base : undefined;
  const pct = delta !== undefined && base ? (delta / base) * 100 : undefined;
  const better = delta !== undefined && delta < 0;
  const worse = delta !== undefined && delta > 0;
  return (
    <div className="comp-kpi-card">
      <div className="comp-kpi-header">
        <div className="comp-title-group">
          <span className="comp-kpi-title">{title}</span>
          <MetricTooltip {...tooltip} />
        </div>
        {icon}
      </div>
      <div className="comp-kpi-values">
        <div className="comp-val-col">
          <span className="col-tag base-tag">ACTUAL (GTFS)</span>
          <span className="col-num font-mono tabular-nums">{fmt(base)}</span>
        </div>
        <div className="comp-delta-col">
          {better && <TrendDown size={18} color="var(--accent-green)" />}
          {worse && <TrendUp size={18} color="var(--accent-red)" />}
          <span className="delta-num">
            {pct === undefined ? (delta === 0 ? '0%' : '—') : `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`}
          </span>
        </div>
        <div className="comp-val-col">
          <span className="col-tag opt-tag">AGENTE IA</span>
          <span className={`col-num font-mono tabular-nums ${better ? 'text-success' : worse ? 'text-alert' : ''}`}>
            {fmt(optimized)}
          </span>
        </div>
      </div>
    </div>
  );
};

interface KpiPanelProps {
  isOpen: boolean;
  onClose: () => void;
  summary: SummaryKPIs | null;
  summaryOpt?: SummaryKPIs | null;
  activeBusesOptimized?: InterpolatedBus[];
  currentQueuesOptimized?: Record<string, number>;
  routes: RouteConfig[];
  stations: Station[];
  activeBuses: InterpolatedBus[];
  currentQueues: Record<string, number>;
  onSelectStation: (station: Station) => void;
  onSelectBus: (bus: InterpolatedBus) => void;
  isSplitView?: boolean;
}

export const KpiPanel: React.FC<KpiPanelProps> = ({
  isOpen,
  onClose,
  summary,
  summaryOpt = null,
  activeBusesOptimized = [],
  currentQueuesOptimized = {},
  routes: _routes,
  stations,
  activeBuses,
  currentQueues,
  onSelectStation,
  onSelectBus: _onSelectBus,
  isSplitView = false,
}) => {
  if (!isOpen) return null;

  // Calculate live fleet statistics from active buses
  const currentTotalPax = activeBuses.reduce((acc, b) => acc + b.passengers, 0);
  const totalCapacity = activeBuses.reduce((acc, b) => acc + (b.capacity || 160), 0);
  const biartCount = activeBuses.filter((b) => b.bus_type === 'biarticulado').length;
  const artCount = activeBuses.filter((b) => b.bus_type !== 'biarticulado').length;

  const currentAvgOcc = activeBuses.length > 0
    ? activeBuses.reduce((acc, b) => acc + b.occupancy_pct, 0) / activeBuses.length
    : 0;
  const overcrowdedBuses = activeBuses.filter((b) => b.occupancy_pct >= 85).length;

  // Total waiting queue across all corridor stations right now
  const totalWaitingPax = Object.values(currentQueues).reduce((acc, q) => acc + q, 0);

  // Optimized scenario: real telemetry of the right-hand map at the same instant.
  const totalWaitingPaxOpt = Object.values(currentQueuesOptimized).reduce((acc, q) => acc + q, 0);
  const overcrowdedBusesOpt = activeBusesOptimized.filter((b) => b.occupancy_pct >= 85).length;
  const bunchingBuses = activeBuses.filter((b) => b.is_bunching).length;
  const bunchingBusesOpt = activeBusesOptimized.filter((b) => b.is_bunching).length;

  // Sort stations by current queue size descending
  const stationsWithQueues = stations.map((s) => ({
    ...s,
    queue: currentQueues[s.code] || 0,
  })).sort((a, b) => b.queue - a.queue);

  const topQueues = stationsWithQueues.slice(0, 5);

  return (
    <aside className={`kpi-panel-container glass-panel ${isSplitView ? 'kpi-split-mode' : ''}`}>
      {/* Header */}
      <div className="kpi-panel-header">
        <div>
          <h2 className="kpi-panel-title">
            {isSplitView ? 'COMPARATIVA DE TELEMETRÍA (CCO)' : 'TELEMETRÍA EN VIVO'}
          </h2>
          <p className="kpi-panel-desc">
            {isSplitView ? 'Contraste GTFS Base vs. FlowTM IA' : 'Métricas operacionales del corredor troncal'}
          </p>
        </div>
        <button
          className="kpi-close-btn"
          onClick={onClose}
          aria-label="Cerrar Panel"
          id="btn-close-kpi"
        >
          <X size={18} weight="bold" />
        </button>
      </div>

      <div className="kpi-panel-body">
        {isSplitView ? (
          /* COMPARATIVE TELEMETRY MODE (SPLIT SCREEN): real data of both scenarios */
          <div className="kpi-comparative-section">
            <div className="split-kpi-banner">
              <Sparkle size={15} weight="fill" color="var(--accent-yellow)" />
              <span>Operación actual vs. horario del agente (mismo instante)</span>
            </div>

            <CompareCard
              title="TIEMPO MEDIO DE ESPERA (3 H)"
              icon={<Clock size={16} color="var(--accent-blue)" />}
              tooltip={{
                title: 'Tiempo medio de espera',
                description: 'Minutos promedio que un pasajero espera en el andén antes de abordar, en toda la simulación de 06:00 a 09:00.',
                interpretation: 'Es un valor de toda la corrida (no cambia con el reloj). La validación con 30 semillas está en Analítica.',
              }}
              base={summary?.avg_waiting_time_min}
              optimized={summaryOpt?.avg_waiting_time_min}
              digits={2}
              unit=" min"
            />
            <CompareCard
              title="BUSES CON OCUPACIÓN ≥ 85% (AHORA)"
              icon={<Warning size={16} color="var(--accent-red)" />}
              tooltip={{
                title: 'Buses muy llenos en este instante',
                description: 'Buses en circulación con más del 85% de su capacidad (aro rojo en el mapa).',
                interpretation: 'Cambia con el reloj de la simulación. Menos es mejor.',
              }}
              base={overcrowdedBuses}
              optimized={overcrowdedBusesOpt}
              digits={0}
              unit=" buses"
            />
            <CompareCard
              title="PASAJEROS EN ANDÉN (AHORA)"
              icon={<Users size={16} color="var(--accent-green)" />}
              tooltip={{
                title: 'Pasajeros esperando',
                description: `Total de personas esperando bus en las ${stations.length} estaciones del corredor en este instante.`,
                interpretation: 'Cambia con el reloj de la simulación. Menos es mejor.',
              }}
              base={totalWaitingPax}
              optimized={totalWaitingPaxOpt}
              digits={0}
              unit=" pax"
            />
            <CompareCard
              title="BUSES PEGADOS / BUNCHING (AHORA)"
              icon={<CheckCircle size={16} color="var(--accent-yellow)" />}
              tooltip={{
                title: 'Buses pegados (bunching)',
                description: 'Buses de la misma ruta a menos de 420 m entre sí (doble aro naranja en el mapa).',
                interpretation: 'Indica intervalos irregulares: un bus llega lleno y el siguiente casi vacío. Menos es mejor.',
              }}
              base={bunchingBuses}
              optimized={bunchingBusesOpt}
              digits={0}
              unit=" buses"
            />
          </div>
        ) : (
          /* SINGLE-VIEW TELEMETRY (STANDARD DASHBOARD) */
          <>
            <div className="kpi-cards-grid">
              {/* Waiting Time */}
              <div className="kpi-metric-card">
                <div className="kpi-card-header">
                  <div className="kpi-label-with-tooltip">
                    <span className="kpi-label">TIEMPO MEDIO ESPERA</span>
                    <MetricTooltip
                      title="Tiempo Medio de Espera"
                      description="Minutos promedio que un usuario permanece en la plataforma antes de abordar su ruta troncal."
                      interpretation="Línea base GTFS registrada en la hora pico de la mañana (06:00 - 09:00 AM)."
                    />
                  </div>
                  <Clock size={16} color="var(--accent-blue)" />
                </div>
                <div className="kpi-value tabular-nums">
                  {summary ? summary.avg_waiting_time_min.toFixed(2) : '—'}
                  <span className="kpi-unit">min</span>
                </div>
                <div className="kpi-subtext">Línea base GTFS pico (Meta &lt; 5.0m)</div>
              </div>

              {/* Passengers on board */}
              <div className="kpi-metric-card">
                <div className="kpi-card-header">
                  <div className="kpi-label-with-tooltip">
                    <span className="kpi-label">PASAJEROS A BORDO</span>
                    <MetricTooltip
                      title="Carga Instantánea de Flota"
                      description="Cantidad de pasajeros viajando en este instante dentro de los buses activos."
                      interpretation="Compara la carga con la capacidad total de la flota en circulación."
                    />
                  </div>
                  <Users size={16} color="var(--accent-green)" />
                </div>
                <div className="kpi-value tabular-nums">
                  {currentTotalPax.toLocaleString()}
                </div>
                <div className="kpi-subtext">
                  Capacidad: {totalCapacity.toLocaleString()} pax ({biartCount} biart. + {artCount} art.)
                </div>
              </div>

              {/* Average Fleet Occupancy */}
              <div className="kpi-metric-card">
                <div className="kpi-card-header">
                  <div className="kpi-label-with-tooltip">
                    <span className="kpi-label">OCUPACIÓN PROMEDIO</span>
                    <MetricTooltip
                      title="Factor de Ocupación de Flota"
                      description="Porcentaje promedio de capacidad ocupada en los vehículos en circulación."
                      interpretation="Rango óptimo: 60% a 80%. Valores superiores a 85% representan hacinamiento severo."
                    />
                  </div>
                  <Gauge size={16} color={currentAvgOcc > 85 ? "var(--accent-red)" : currentAvgOcc > 70 ? "var(--accent-yellow)" : "var(--accent-green)"} />
                </div>
                <div className="kpi-value tabular-nums">
                  {currentAvgOcc.toFixed(1)}
                  <span className="kpi-unit">%</span>
                </div>
                <div className="kpi-progress-bg">
                  <div
                    className="kpi-progress-fill"
                    style={{
                      width: `${Math.min(100, currentAvgOcc)}%`,
                      backgroundColor: currentAvgOcc > 85 ? 'var(--accent-red)' : currentAvgOcc > 70 ? 'var(--accent-yellow)' : 'var(--accent-green)'
                    }}
                  />
                </div>
                <div className="kpi-subtext">
                  Corredor global: {summary ? summary.avg_occupancy_pct.toFixed(1) : '43.1'}%
                </div>
              </div>

              {/* Overcrowded Buses */}
              <div className="kpi-metric-card">
                <div className="kpi-card-header">
                  <div className="kpi-label-with-tooltip">
                    <span className="kpi-label">BUSES SATURADOS</span>
                    <MetricTooltip
                      title="Buses con Sobrecupo Crítico"
                      description="Número de vehículos con ocupación igual o mayor al 85% de su capacidad."
                      interpretation="Indica puntos donde los usuarios no logran subir y se alarga el tiempo de parada."
                    />
                  </div>
                  <Warning size={16} color={overcrowdedBuses > 0 ? "var(--accent-red)" : "var(--accent-green)"} />
                </div>
                <div className="kpi-value tabular-nums" style={{ color: overcrowdedBuses > 0 ? 'var(--accent-red)' : undefined }}>
                  {overcrowdedBuses}
                  <span className="kpi-unit">(&ge;85%)</span>
                </div>
                <div className="kpi-subtext">
                  {summary ? `${summary.overcrowded_buses_pct.toFixed(1)}% de viajes en sobrecupo` : 'Límite operativo superado'}
                </div>
              </div>
            </div>

            {/* Top Critical Platform Queues */}
            <div className="kpi-section">
              <div className="kpi-section-header">
                <span className="kpi-section-title">TOP 5 ANDENES CONGESTIONADOS Q(t)</span>
                <span className="badge badge-accent">
                  Total: {totalWaitingPax.toLocaleString()} pax
                </span>
              </div>

              <div className="stations-queue-list">
                {topQueues.map((st) => {
                  const pct = Math.min(100, (st.queue / 200) * 100);
                  const isHigh = st.queue > 150;
                  const isMed = st.queue > 80;

                  return (
                    <div
                      key={st.code}
                      className="station-queue-row"
                      onClick={() => onSelectStation(st)}
                      title="Clic para inspeccionar estación"
                    >
                      <div className="station-row-info">
                        <span className="station-name-text">{st.official_name || st.name}</span>
                        <span className="station-queue-val tabular-nums font-mono">
                          {st.queue} pax
                        </span>
                      </div>
                      <div className="station-progress-bg">
                        <div
                          className="station-progress-fill"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: isHigh
                              ? 'var(--accent-red)'
                              : isMed
                              ? 'var(--accent-yellow)'
                              : 'var(--accent-green)',
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Active Fleet Breakdown by Typology */}
            <div className="kpi-section">
              <div className="kpi-section-header">
                <span className="kpi-section-title">DISTRIBUCIÓN DE FLOTA ACTIVA</span>
                <span className="kpi-badge-count font-mono">{activeBuses.length} buses</span>
              </div>
              <div className="fleet-typology-summary">
                <div className="typology-stat-pill">
                  <span className="typology-dot biart-dot" />
                  <span>Biarticulados (250p): <strong>{biartCount}</strong></span>
                </div>
                <div className="typology-stat-pill">
                  <span className="typology-dot art-dot" />
                  <span>Articulados (160p): <strong>{artCount}</strong></span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  );
};
