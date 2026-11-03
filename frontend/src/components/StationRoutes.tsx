import React from 'react';
import { Brain, Bus } from '@phosphor-icons/react';
import { MetricTooltip } from './MetricTooltip';
import type { AIOptimizationLog, RouteConfig } from '../types';

interface StationRoutesProps {
  stationCode: string;
  routes: RouteConfig[];
  aiLog?: AIOptimizationLog | null;
}

/** Trunk services stopping at a station, split by who controls their frequency. */
export const StationRoutes: React.FC<StationRoutesProps> = ({ stationCode, routes, aiLog }) => {
  const serving = routes.filter((r) => r.stops.includes(stationCode));
  const optimized = serving.filter((r) => r.role === 'optimizable');
  const background = serving.filter((r) => r.role !== 'optimizable');

  const pill = (route: RouteConfig, isOptimized: boolean) => {
    const base = route.headway_min;
    const ai = aiLog?.optimized?.headways?.[route.id];
    const changed = isOptimized && ai !== undefined && Math.abs(ai - base) > 1e-6;
    return (
      <div
        key={route.id}
        className={`station-route-pill ${isOptimized ? 'optimized' : 'background'}`}
        style={{ '--route-color': route.color } as React.CSSProperties}
        title={`Hacia ${route.service}`}
      >
        <span className="station-route-code font-mono">{route.id}</span>
        {isOptimized && route.counterpart && <span className="station-route-counterpart">≙ {route.counterpart}</span>}
        <span className="station-route-freq font-mono tabular-nums">
          {base.toFixed(1)}′
          {changed && (
            <>
              {' → '}
              <b className={ai < base ? 'freq-more' : 'freq-less'}>{ai.toFixed(1)}′</b>
            </>
          )}
        </span>
      </div>
    );
  };

  return (
    <div className="station-routes-section">
      <div className="station-routes-header">
        <span className="stat-label">RUTAS QUE PARAN AQUÍ ({serving.length})</span>
        <MetricTooltip
          title="Rutas que paran en la estación"
          description="Servicios troncales que, según el GTFS, se detienen en esta estación en sentido sur. El número es cada cuántos minutos pasa un bus (′ = minutos)."
          interpretation="En las rutas de la IA se muestra «actual → IA»: verde si la IA las hace pasar más seguido, amarillo si menos. Una estación con pocas rutas suele acumular más espera."
        />
      </div>
      {serving.length === 0 && <p className="station-routes-empty">Ninguna ruta troncal para aquí en el GTFS.</p>}
      {optimized.length > 0 && (
        <>
          <div className="station-routes-group">
            <Brain size={11} weight="fill" /> Optimizadas por la IA
          </div>
          <div className="station-routes-chips">{optimized.map((r) => pill(r, true))}</div>
        </>
      )}
      {background.length > 0 && (
        <>
          <div className="station-routes-group">
            <Bus size={11} weight="bold" /> De fondo (frecuencia GTFS fija)
          </div>
          <div className="station-routes-chips">{background.map((r) => pill(r, false))}</div>
        </>
      )}
    </div>
  );
};
