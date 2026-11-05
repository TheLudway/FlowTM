import React, { useState } from 'react';
import {
  CaretUp,
  Info,
  X,
} from '@phosphor-icons/react';
import type { RouteConfig } from '../types';

interface MapLegendProps {
  routes: RouteConfig[];
}

export const MapLegend: React.FC<MapLegendProps> = ({ routes }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className={`map-legend-wrapper ${isOpen ? 'expanded' : 'collapsed'}`}>
      {!isOpen ? (
        <button
          className="map-legend-toggle-btn glass-panel"
          onClick={() => setIsOpen(true)}
          title="Ver simbología, tipología de buses y convenciones del mapa"
          id="btn-open-legend"
        >
          <Info size={16} weight="bold" />
          <span>Simbología & Apéndice</span>
          <CaretUp size={14} />
        </button>
      ) : (
        <div className="map-legend-card glass-panel" id="card-map-legend">
          {/* Header */}
          <div className="legend-header">
            <div className="legend-title-group">
              <div className="legend-badge-icon">
                <Info size={15} weight="fill" />
              </div>
              <div>
                <h4 className="legend-title">APÉNDICE & SIMBOLOGÍA TRONCAL</h4>
                <p className="legend-subtitle">Convenciones operativas en tiempo real</p>
              </div>
            </div>
            <button
              className="legend-close-btn"
              onClick={() => setIsOpen(false)}
              title="Cerrar apéndice"
              id="btn-close-legend"
            >
              <X size={15} />
            </button>
          </div>

          <div className="legend-content-scroll">
            {/* 1. Vehicle Fleet Typology */}
            <div className="legend-section">
              <h5 className="legend-section-title">1. TIPOLOGÍA DE FLOTA (LONGITUD & CAPACIDAD)</h5>
              <div className="typology-legend-grid">
                <div className="typology-legend-item">
                  <div className="typology-symbol-box">
                    <div className="symbol-articulado" />
                  </div>
                  <div className="typology-info">
                    <span className="typology-name">🚍 Articulado (18 metros)</span>
                    <span className="typology-specs">Capacidad: 160 pasajeros • 3 puertas • Fuelle simple</span>
                    <span className="typology-routes">Servicios B18, B23, B74</span>
                  </div>
                </div>

                <div className="typology-legend-item">
                  <div className="typology-symbol-box">
                    <div className="symbol-biarticulado" />
                  </div>
                  <div className="typology-info">
                    <span className="typology-name">🚌 Biarticulado (27 metros)</span>
                    <span className="typology-specs">Capacidad: 250 pasajeros • 4 puertas • Doble fuelle articulado</span>
                    <span className="typology-routes">Servicios B13, B27, B75 (Alta Demanda Troncal)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Bus Occupancy Rings */}
            <div className="legend-section">
              <h5 className="legend-section-title">2. AROS DE OCUPACIÓN Y ESTADO DEL BUS</h5>
              <div className="legend-items-list">
                <div className="legend-item-row">
                  <span className="legend-dot-indicator ring-green" />
                  <div className="legend-item-desc">
                    <strong>🟢 Baja Ocupación (&lt; 60%):</strong> Capacidad holgada, confort alto para el usuario.
                  </div>
                </div>

                <div className="legend-item-row">
                  <span className="legend-dot-indicator ring-yellow" />
                  <div className="legend-item-desc">
                    <strong>🟡 Ocupación Media (60% - 85%):</strong> Llenado nominal en operación de hora pico.
                  </div>
                </div>

                <div className="legend-item-row">
                  <span className="legend-dot-indicator ring-red" />
                  <div className="legend-item-desc">
                    <strong>🔴 Sobrecupo Crítico (&ge; 85%):</strong> Hacinamiento severo en plataforma y cabina.
                  </div>
                </div>

                <div className="legend-item-row">
                  <span className="legend-dot-indicator ring-bunching" />
                  <div className="legend-item-desc">
                    <strong style={{ color: '#F39C12' }}>⚠️ Pegamiento de Buses (Bunching):</strong> Doble aro naranja titilante. Dos buses de la misma ruta separados por menos de 420m que viajan en racimo.
                  </div>
                </div>
              </div>
            </div>

            {/* 3. Station Platform Demand Halos */}
            <div className="legend-section">
              <h5 className="legend-section-title">3. HALOS DE CONGESTIÓN EN PLATAFORMA Q(t)</h5>
              <div className="legend-items-list">
                <div className="legend-item-row">
                  <span className="legend-dot-indicator station-low" />
                  <div className="legend-item-desc">
                    <strong>🔵 Flujo Ágil (&lt; 80 pax):</strong> Pasajeros abordan rápidamente sin congestión.
                  </div>
                </div>

                <div className="legend-item-row">
                  <span className="legend-dot-indicator station-med" />
                  <div className="legend-item-desc">
                    <strong>🟡 Espera Moderada (80 - 150 pax):</strong> Acumulación temporal en puertas de parada.
                  </div>
                </div>

                <div className="legend-item-row">
                  <span className="legend-dot-indicator station-high" />
                  <div className="legend-item-desc">
                    <strong>🔴 Sobrecupo en Plataforma (&gt; 150 pax):</strong> Estaciones críticas (ej. Calle 72, Flores) que demandan buses de refuerzo.
                  </div>
                </div>
              </div>
            </div>

            {/* 4. Active Trunk Routes */}
            <div className="legend-section">
              <h5 className="legend-section-title">4. RUTAS TRONCALES (PILOTO AUTONORTE - CARACAS)</h5>
              <div className="route-legend-chips">
                {routes.map((r) => (
                  <div key={r.id} className="route-legend-chip">
                    <span
                      className="route-color-square"
                      style={{ backgroundColor: r.color }}
                    />
                    <span className="route-id font-mono">{r.id}</span>
                    <span className="route-type-tag">
                      {r.bus_type === 'biarticulado' ? 'Biartic. (250)' : 'Artic. (160)'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
