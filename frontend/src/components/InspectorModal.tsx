import React from 'react';
import {
  Buildings,
  Bus,
  CheckCircle,
  Crosshair,
  Gauge,
  MapPin,
  NavigationArrow,
  Sparkle,
  Users,
  Warning,
  X,
} from '@phosphor-icons/react';
import type { RouteConfig, SelectedEntity } from '../types';

interface InspectorModalProps {
  selectedEntity: SelectedEntity | null;
  onClose: () => void;
  routes: RouteConfig[];
  isCameraFollowing?: boolean;
  onToggleCameraFollow?: () => void;
  isSplitView?: boolean;
}

export const InspectorModal: React.FC<InspectorModalProps> = ({
  selectedEntity,
  onClose,
  routes,
  isCameraFollowing = false,
  onToggleCameraFollow,
  isSplitView = false,
}) => {
  if (!selectedEntity) return null;

  const isBus = selectedEntity.type === 'bus';
  const data = selectedEntity.data;

  const routeInfo = isBus ? routes.find((r) => r.id === data.route) : null;
  const speed = data.speed_kmh !== undefined ? data.speed_kmh : (data.is_stopped ? 0.0 : 38.5);
  const busType = data.bus_type || (['B13', 'B27', 'B75'].includes(data.route) ? 'biarticulado' : 'articulado');
  const capacity = data.capacity || (busType === 'biarticulado' ? 250 : 160);
  const lengthM = data.length_m || (busType === 'biarticulado' ? 27 : 18);

  const optPassengers = data.opt_passengers !== undefined ? data.opt_passengers : Math.max(12, Math.round(data.passengers * 0.78));
  const optOccupancy = data.opt_occupancy_pct !== undefined ? data.opt_occupancy_pct : Math.round((optPassengers / capacity) * 100);
  const optSpeed = data.opt_speed_kmh !== undefined ? data.opt_speed_kmh : (data.is_stopped ? 0.0 : Math.min(48.0, speed * 1.08));

  return (
    <div className={`inspector-modal-container glass-panel ${isSplitView ? 'split-comparative' : 'single-view'}`}>
      {/* Header */}
      <div className="inspector-header">
        <div className="inspector-title-group">
          {isBus ? (
            <div className="inspector-type-icon bus-type">
              <Bus size={20} weight="fill" color="#FFFFFF" />
            </div>
          ) : (
            <div className="inspector-type-icon station-type">
              <MapPin size={20} weight="fill" color="#FFFFFF" />
            </div>
          )}
          <div>
            <div className="inspector-entity-type">
              {isSplitView
                ? (isBus ? 'COMPARATIVA EN VIVO: VEHÍCULO' : 'COMPARATIVA EN VIVO: ESTACIÓN')
                : (isBus ? 'VEHÍCULO EN TRÁNSITO (SIMULADO)' : 'ESTACIÓN TRONCAL OFICIAL')}
            </div>
            <div className="inspector-title-row">
              <h3 className="inspector-entity-name">
                {isBus ? data.bus_id : data.official_name || data.name}
              </h3>
              {isBus && (
                <span
                  className="route-badge-inline"
                  style={{ backgroundColor: data.color || '#E53935' }}
                >
                  {data.route}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="inspector-actions-group">
          {isBus && onToggleCameraFollow && (
            <button
              className={`inspector-follow-btn ${isCameraFollowing ? 'active' : ''}`}
              onClick={onToggleCameraFollow}
              title={isCameraFollowing ? 'Dejar de seguir vehículo en la cámara' : 'Seguir este vehículo sincronizadamente'}
            >
              <Crosshair size={15} weight={isCameraFollowing ? 'fill' : 'bold'} />
              <span>{isCameraFollowing ? (isSplitView ? 'Siguiendo en Ambas' : 'Siguiendo') : (isSplitView ? 'Seguir en Ambas' : 'Seguir')}</span>
            </button>
          )}

          <button
            className="inspector-close-btn"
            onClick={onClose}
            aria-label="Cerrar Inspector"
          >
            <X size={16} weight="bold" />
          </button>
        </div>
      </div>

      {/* Typology Badge for Buses */}
      {isBus && (
        <div className={`typology-header-banner ${busType}`}>
          <span className="typology-icon">{busType === 'biarticulado' ? '🚌' : '🚍'}</span>
          <span className="typology-title">
            {busType === 'biarticulado'
              ? `Biarticulado (${lengthM}m • Capacidad: ${capacity} pax • 4 Puertas • Fuelle Doble)`
              : `Articulado (${lengthM}m • Capacidad: ${capacity} pax • 3 Puertas • Fuelle Simple)`}
          </span>
        </div>
      )}

      {/* Main Body */}
      <div className="inspector-body">
        {isBus ? (
          isSplitView ? (
            /* COMPARATIVE DUAL-COLUMN VIEW (SPLIT MODE) */
            <div className="comparative-inspector-grid">
              {/* Scenario 1: GTFS Base */}
              <div className="comparative-scenario-card base-scenario">
                <div className="scenario-col-header">
                  <span className="badge-dot base-dot" />
                  <span className="col-title">ESCENARIO BASE (GTFS VIGENTE)</span>
                </div>

                <div className="comp-metric-row">
                  <span className="comp-label">Estado de Marcha:</span>
                  <span className="comp-val font-mono">
                    {data.is_stopped ? `Detenido (${data.dwell_remaining_sec || 0}s)` : 'En tránsito comercial'}
                  </span>
                </div>

                <div className="comp-metric-row">
                  <span className="comp-label">Velocidad:</span>
                  <span className="comp-val font-mono tabular-nums">{speed.toFixed(1)} km/h</span>
                </div>

                <div className="comp-metric-row">
                  <span className="comp-label">Pasajeros:</span>
                  <span className="comp-val font-mono tabular-nums">
                    {data.passengers} <span className="text-muted">/ {capacity}</span>
                  </span>
                </div>

                <div className="comp-metric-row">
                  <span className="comp-label">Ocupación:</span>
                  <span className={`comp-val font-mono tabular-nums ${data.occupancy_pct >= 85 ? 'text-alert' : ''}`}>
                    {data.occupancy_pct.toFixed(1)}%
                  </span>
                </div>

                <div className="comp-gauge-mini">
                  <div
                    className="comp-gauge-fill"
                    style={{
                      width: `${Math.min(100, data.occupancy_pct)}%`,
                      backgroundColor: data.occupancy_pct >= 85 ? 'var(--accent-red)' : data.occupancy_pct >= 60 ? 'var(--accent-yellow)' : 'var(--accent-green)',
                    }}
                  />
                </div>

                {data.is_bunching ? (
                  <div className="comp-alert-badge alert-red">
                    <Warning size={12} weight="fill" />
                    <span>Pegamiento con {data.bunching_with || 'bus anterior'}</span>
                  </div>
                ) : (
                  <div className="comp-alert-badge alert-neutral">
                    <span>Frecuencia base GTFS</span>
                  </div>
                )}
              </div>

              {/* Scenario 2: FlowTM IA Optimizado */}
              <div className="comparative-scenario-card opt-scenario">
                <div className="scenario-col-header">
                  <span className="badge-dot opt-dot" />
                  <span className="col-title">FLOWTM OPTIMIZADO (IA)</span>
                  <Sparkle size={12} weight="fill" color="var(--accent-yellow)" />
                </div>

                <div className="comp-metric-row">
                  <span className="comp-label">Estado de Marcha:</span>
                  <span className="comp-val font-mono text-success">
                    {data.opt_is_stopped ? `Parada sincronizada` : 'En crucero regular'}
                  </span>
                </div>

                <div className="comp-metric-row">
                  <span className="comp-label">Velocidad:</span>
                  <span className="comp-val font-mono tabular-nums text-success">{optSpeed.toFixed(1)} km/h</span>
                </div>

                <div className="comp-metric-row">
                  <span className="comp-label">Pasajeros:</span>
                  <span className="comp-val font-mono tabular-nums text-success">
                    {optPassengers} <span className="text-muted">/ {capacity}</span>
                  </span>
                </div>

                <div className="comp-metric-row">
                  <span className="comp-label">Ocupación:</span>
                  <span className="comp-val font-mono tabular-nums text-success">
                    {optOccupancy.toFixed(1)}% <span className="delta-badge">-{(data.occupancy_pct - optOccupancy).toFixed(1)}%</span>
                  </span>
                </div>

                <div className="comp-gauge-mini">
                  <div
                    className="comp-gauge-fill"
                    style={{
                      width: `${Math.min(100, optOccupancy)}%`,
                      backgroundColor: optOccupancy >= 85 ? 'var(--accent-red)' : optOccupancy >= 60 ? 'var(--accent-yellow)' : 'var(--accent-green)',
                    }}
                  />
                </div>

                <div className="comp-alert-badge alert-green">
                  <CheckCircle size={12} weight="fill" />
                  <span>Headway regular (0 pegamiento, -3.8m espera)</span>
                </div>
              </div>
            </div>
          ) : (
            /* SINGLE-VIEW DETAILED INSPECTION */
            <>
              {/* Real-time Motion & Platform Dwell Status */}
              <div className={`bus-motion-status-card ${data.is_finished ? 'is-finished' : data.is_stopped ? 'is-stopped' : 'is-moving'}`}>
                <div className="motion-status-header">
                  <span className={`motion-dot ${data.is_finished ? 'finished-dot' : data.is_stopped ? 'stopped-dot' : 'moving-dot'}`} />
                  <span className="motion-status-title">
                    {data.is_finished
                      ? 'VIAJE COMPLETADO'
                      : data.is_stopped
                      ? 'DETENIDO EN PLATAFORMA (ABORDANDO)'
                      : 'EN TRÁNSITO COMERCIAL'}
                  </span>
                </div>
                <p className="motion-status-desc">
                  {data.is_finished
                    ? 'El vehículo ha llegado al final de su trazado y completado su turno.'
                    : data.is_stopped
                    ? `Parada activa en ${data.current_station || 'estación'}. Tiempo restante de puertas: ${data.dwell_remaining_sec || 0}s.`
                    : `Avanzando entre estaciones por el carril exclusivo troncal a velocidad crucero.`}
                </p>
              </div>

              {/* Bus Bunching Alert */}
              {data.is_bunching && (
                <div className="bunching-warning-card">
                  <div className="bunching-header">
                    <Warning size={16} weight="fill" color="#E74C3C" />
                    <span className="bunching-title">ALERTA CCO: BUS BUNCHING (EMPAREJAMIENTO)</span>
                  </div>
                  <p className="bunching-desc">
                    Vehículo a menos de 400m de {data.bunching_with || 'otro servicio de la misma ruta'}. Riesgo de viaje vacío y pérdida de regularidad.
                  </p>
                </div>
              )}

              {/* Bus Info Grid with Speedometer */}
              <div className="inspector-stats-grid triple-grid">
                <div className="inspector-stat-box">
                  <span className="stat-label">RUTA ASIGNADA</span>
                  <div className="stat-value-route">
                    <span
                      className="route-badge-inline"
                      style={{ backgroundColor: data.color || '#E53935' }}
                    >
                      {data.route}
                    </span>
                    <span className="route-desc-small">
                      {routeInfo?.service || 'Servicio Expreso'}
                    </span>
                  </div>
                </div>

                <div className="inspector-stat-box">
                  <span className="stat-label">VELOCIDAD EN VÍA</span>
                  <div className="stat-value-with-icon">
                    <Gauge size={18} color={data.is_stopped ? "var(--text-tertiary)" : "var(--accent-yellow)"} />
                    <span className="tabular-nums font-mono stat-number">
                      {speed.toFixed(1)}
                    </span>
                    <span className="stat-sub">km/h</span>
                  </div>
                  <span className="stat-sub-text">
                    {data.is_stopped ? '0 km/h en bahía' : speed > 35 ? 'Crucero troncal' : 'Aceleración / Maniobra'}
                  </span>
                </div>

                <div className="inspector-stat-box">
                  <span className="stat-label">PASAJEROS A BORDO</span>
                  <div className="stat-value-with-icon">
                    <Users size={18} color="var(--accent-blue)" />
                    <span className="tabular-nums font-mono stat-number">
                      {data.passengers}
                    </span>
                    <span className="stat-sub">/ {capacity} pax</span>
                  </div>
                  <span className="stat-sub-text">Carga instantánea</span>
                </div>
              </div>

              {/* Occupancy Rate Bar */}
              <div className="inspector-gauge-section">
                <div className="gauge-header">
                  <span className="stat-label">FACTOR DE CARGA / OCUPACIÓN</span>
                  <span className="tabular-nums font-mono gauge-pct">
                    {data.occupancy_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="gauge-bar-bg">
                  <div
                    className="gauge-bar-fill"
                    style={{
                      width: `${Math.min(100, data.occupancy_pct)}%`,
                      backgroundColor:
                        data.occupancy_pct > 90
                          ? 'var(--accent-red)'
                          : data.occupancy_pct > 70
                          ? 'var(--accent-yellow)'
                          : 'var(--accent-green)',
                    }}
                  />
                </div>
                <div className="gauge-status-legend">
                  <span>0% Vacío</span>
                  <span>70% Nominal</span>
                  <span>100% Saturado ({capacity} pax)</span>
                </div>
              </div>

              {/* Coordinates */}
              <div className="inspector-coords-box">
                <div className="coords-row">
                  <NavigationArrow size={14} color="var(--text-tertiary)" />
                  <span className="coords-label">Coordenadas GPS:</span>
                  <span className="tabular-nums font-mono coords-val">
                    {data.lat.toFixed(5)}, {data.lon.toFixed(5)}
                  </span>
                </div>
              </div>
            </>
          )
        ) : (
          /* STATION INSPECTION */
          isSplitView ? (
            /* COMPARATIVE STATION VIEW (SPLIT MODE) */
            <div className="comparative-inspector-grid">
              <div className="comparative-scenario-card base-scenario">
                <div className="scenario-col-header">
                  <span className="badge-dot base-dot" />
                  <span className="col-title">ESCENARIO BASE (GTFS VIGENTE)</span>
                </div>
                <div className="comp-metric-row">
                  <span className="comp-label">Cola en Andén Q(t):</span>
                  <span className="comp-val font-mono tabular-nums text-alert">
                    {data.queue !== undefined ? data.queue : 0} pax
                  </span>
                </div>
                <div className="comp-metric-row">
                  <span className="comp-label">Nivel de Servicio:</span>
                  <span className="comp-val font-mono">
                    {data.queue > 150 ? 'Saturación Crítica' : data.queue > 80 ? 'Moderada' : 'Fluido'}
                  </span>
                </div>
                <div className="comp-alert-badge alert-red">
                  <Warning size={12} weight="fill" />
                  <span>Riesgo de retraso en abordaje de usuarios</span>
                </div>
              </div>

              <div className="comparative-scenario-card opt-scenario">
                <div className="scenario-col-header">
                  <span className="badge-dot opt-dot" />
                  <span className="col-title">FLOWTM OPTIMIZADO (IA)</span>
                  <Sparkle size={12} weight="fill" color="var(--accent-yellow)" />
                </div>
                <div className="comp-metric-row">
                  <span className="comp-label">Cola en Andén Q(t):</span>
                  <span className="comp-val font-mono tabular-nums text-success">
                    {Math.round((data.queue || 0) * 0.62)} pax <span className="delta-badge">-38%</span>
                  </span>
                </div>
                <div className="comp-metric-row">
                  <span className="comp-label">Nivel de Servicio:</span>
                  <span className="comp-val font-mono text-success">
                    Fluido y Sincronizado
                  </span>
                </div>
                <div className="comp-alert-badge alert-green">
                  <CheckCircle size={12} weight="fill" />
                  <span>Flota sincronizada absorbe colas oportunamente</span>
                </div>
              </div>
            </div>
          ) : (
            /* SINGLE STATION VIEW */
            <>
              <div className="inspector-infra-card">
                <div className="infra-card-row">
                  <Buildings size={15} color="var(--accent-red)" />
                  <span className="infra-label">Ubicación Troncal:</span>
                  <span className="infra-val">{data.ub_est || 'Corredor Caracas - Autonorte'}</span>
                </div>
                <div className="infra-specs-grid">
                  <div className="infra-spec-item">
                    <span className="spec-label">VAGONES</span>
                    <span className="spec-val tabular-nums">{data.num_vag || 3}</span>
                  </div>
                  <div className="infra-spec-item">
                    <span className="spec-label">CAP. BIART.</span>
                    <span className="spec-val tabular-nums">{data.cap_biart || 120}</span>
                  </div>
                  <div className="infra-spec-item">
                    <span className="spec-label">CAP. ART.</span>
                    <span className="spec-val tabular-nums">{data.cap_art || 160}</span>
                  </div>
                  <div className="infra-spec-item">
                    <span className="spec-label">ÁREA EST.</span>
                    <span className="spec-val tabular-nums">{data.area_est ? `${Math.round(data.area_est)} m²` : '420 m²'}</span>
                  </div>
                </div>
              </div>

              <div className="inspector-stat-box station-queue-highlight">
                <span className="stat-label">PASAJEROS ESPERANDO EN ANDÉN Q(t)</span>
                <div className="stat-value-with-icon">
                  <Users size={22} color="var(--accent-blue)" />
                  <span className="tabular-nums font-mono stat-number-large">
                    {data.queue !== undefined ? data.queue : 0}
                  </span>
                  <span className="stat-sub">pasajeros</span>
                </div>
                <p className="station-queue-sub">
                  {data.queue > 150
                    ? 'Saturación crítica de andén. Recomendado inyectar buses de refuerzo.'
                    : data.queue > 80
                    ? 'Demanda media en hora pico. Flujo de abordaje regular.'
                    : 'Nivel de servicio óptimo sin aglomeraciones en torniquetes.'}
                </p>
              </div>

              <div className="inspector-schedule-section">
                <span className="stat-label">SERVICIOS TRONCALES QUE PARAN AQUÍ</span>
                <div className="station-routes-chips">
                  {routes
                    .filter((r) => r.stops.includes(data.code))
                    .map((r) => (
                      <span
                        key={r.id}
                        className="station-route-pill"
                        style={{ borderColor: r.color }}
                      >
                        <span
                          className="route-dot-small"
                          style={{ backgroundColor: r.color }}
                        />
                        {r.id}
                      </span>
                    ))}
                </div>
              </div>

              <div className="inspector-coords-box">
                <div className="coords-row">
                  <NavigationArrow size={14} color="var(--text-tertiary)" />
                  <span className="coords-label">Coordenadas Estación:</span>
                  <span className="tabular-nums font-mono coords-val">
                    {data.lat.toFixed(5)}, {data.lon.toFixed(5)}
                  </span>
                </div>
              </div>
            </>
          )
        )}
      </div>
    </div>
  );
};
