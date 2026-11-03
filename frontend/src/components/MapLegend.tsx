import React, { useState } from 'react';
import { CaretUp, Info, X } from '@phosphor-icons/react';
import { BUNCHING_DISTANCE_M } from '../hooks/useSimulation';
import type { RouteConfig } from '../types';

interface MapLegendProps {
  routes: RouteConfig[];
}

/**
 * Map symbology. Every entry mirrors a MapLibre layer in MapViewport: role-based
 * bus size, route-colored fill, occupancy ring (60/85%), bunching double ring and
 * station queue halos (80/150 pax).
 */
export const MapLegend: React.FC<MapLegendProps> = ({ routes }) => {
  const [isOpen, setIsOpen] = useState(false);
  const optimizable = routes.filter((r) => r.role === 'optimizable');
  const background = routes.filter((r) => r.role !== 'optimizable');

  return (
    <div className={`map-legend-wrapper ${isOpen ? 'expanded' : 'collapsed'}`}>
      {!isOpen ? (
        <button
          className="map-legend-toggle-btn glass-panel"
          onClick={() => setIsOpen(true)}
          title="Qué significa cada símbolo del mapa"
          id="btn-open-legend"
        >
          <Info size={16} weight="bold" />
          <span>Simbología del mapa</span>
          <CaretUp size={14} />
        </button>
      ) : (
        <div className="map-legend-card glass-panel" id="card-map-legend">
          <div className="legend-header">
            <div className="legend-title-group">
              <div className="legend-badge-icon">
                <Info size={15} weight="fill" />
              </div>
              <div>
                <h4 className="legend-title">SIMBOLOGÍA DEL MAPA</h4>
                <p className="legend-subtitle">Cómo leer buses y estaciones</p>
              </div>
            </div>
            <button className="legend-close-btn" onClick={() => setIsOpen(false)} title="Cerrar" id="btn-close-legend">
              <X size={15} />
            </button>
          </div>

          <div className="legend-content-scroll">
            {/* 1. Route role */}
            <div className="legend-section">
              <h5 className="legend-section-title">1. TAMAÑO DEL BUS = QUIÉN LO CONTROLA</h5>
              <div className="legend-items-list">
                <div className="legend-item-row">
                  <span className="legend-bus-symbol big" />
                  <div className="legend-item-desc">
                    <strong>Bus grande con etiqueta:</strong> una de las {optimizable.length} rutas cuyas frecuencias
                    reprograma la IA ({optimizable.map((r) => r.id).join(', ')}).
                  </div>
                </div>
                <div className="legend-item-row">
                  <span className="legend-bus-symbol small" />
                  <div className="legend-item-desc">
                    <strong>Bus pequeño y tenue:</strong> una de las {background.length} rutas de fondo; circula con su
                    frecuencia oficial (GTFS) en ambos escenarios.
                  </div>
                </div>
                <div className="legend-item-row">
                  <span className="legend-color-chips">
                    {optimizable.slice(0, 3).map((r) => (
                      <i key={r.id} style={{ backgroundColor: r.color }} />
                    ))}
                  </span>
                  <div className="legend-item-desc">
                    <strong>Color de relleno:</strong> color oficial de la ruta en el GTFS de TransMilenio.
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Occupancy ring and bunching */}
            <div className="legend-section">
              <h5 className="legend-section-title">2. ARO = QUÉ TAN LLENO VA EL BUS</h5>
              <div className="legend-items-list">
                <div className="legend-item-row">
                  <span className="legend-dot-indicator ring-green" />
                  <div className="legend-item-desc">
                    <strong>Verde (&lt; 60%):</strong> hay puestos disponibles.
                  </div>
                </div>
                <div className="legend-item-row">
                  <span className="legend-dot-indicator ring-yellow" />
                  <div className="legend-item-desc">
                    <strong>Amarillo (60% – 85%):</strong> lleno, típico de hora pico.
                  </div>
                </div>
                <div className="legend-item-row">
                  <span className="legend-dot-indicator ring-red" />
                  <div className="legend-item-desc">
                    <strong>Rojo (≥ 85%):</strong> hacinamiento; cuesta subir y bajar.
                  </div>
                </div>
                <div className="legend-item-row">
                  <span className="legend-dot-indicator ring-bunching" />
                  <div className="legend-item-desc">
                    <strong>Aro naranja exterior (bunching):</strong> dos buses de la misma ruta a menos de{' '}
                    {BUNCHING_DISTANCE_M} m; uno suele ir lleno y el otro vacío.
                  </div>
                </div>
              </div>
            </div>

            {/* 3. Station halos */}
            <div className="legend-section">
              <h5 className="legend-section-title">3. HALO DE LA ESTACIÓN = PERSONAS ESPERANDO</h5>
              <div className="legend-items-list">
                <div className="legend-item-row">
                  <span className="legend-dot-indicator station-low" />
                  <div className="legend-item-desc">
                    <strong>Verde (&lt; 80 pasajeros):</strong> se aborda sin congestión.
                  </div>
                </div>
                <div className="legend-item-row">
                  <span className="legend-dot-indicator station-med" />
                  <div className="legend-item-desc">
                    <strong>Amarillo (80 – 150):</strong> se forma fila en las puertas.
                  </div>
                </div>
                <div className="legend-item-row">
                  <span className="legend-dot-indicator station-high" />
                  <div className="legend-item-desc">
                    <strong>Rojo (&gt; 150):</strong> andén saturado. El halo crece con la cola.
                  </div>
                </div>
              </div>
            </div>

            {/* 4. Routes */}
            <div className="legend-section">
              <h5 className="legend-section-title">4. RUTAS DEL CORREDOR (SENTIDO SUR)</h5>
              <p className="legend-note">
                Optimizadas por la IA. «≙ B13» indica que comparten número con la ruta B13 del sentido contrario.
              </p>
              <div className="route-legend-chips">
                {optimizable.map((r) => (
                  <div key={r.id} className="route-legend-chip">
                    <span className="route-color-square" style={{ backgroundColor: r.color }} />
                    <span className="route-id font-mono">{r.id}</span>
                    {r.counterpart && <span className="route-type-tag">≙ {r.counterpart}</span>}
                  </div>
                ))}
              </div>
              <p className="legend-note">De fondo (frecuencia GTFS fija):</p>
              <div className="route-legend-chips">
                {background.map((r) => (
                  <div key={r.id} className="route-legend-chip muted">
                    <span className="route-color-square" style={{ backgroundColor: r.color }} />
                    <span className="route-id font-mono">{r.id}</span>
                  </div>
                ))}
              </div>
              <p className="legend-note">
                El GTFS no publica el tipo de vehículo: todos los buses se modelan como articulados de 160 pasajeros.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
