import React, { useEffect, useRef, useState } from 'react';
import { Brain, Bus, CaretDown, Check } from '@phosphor-icons/react';
import type { RouteConfig } from '../types';

interface RouteSelectDropdownProps {
  routes: RouteConfig[];
  selectedRoute: string | null;
  onSelectRoute: (routeId: string | null) => void;
}

const RouteItem: React.FC<{
  route: RouteConfig;
  selected: boolean;
  onPick: () => void;
}> = ({ route, selected, onPick }) => {
  const optimizable = route.role === 'optimizable';
  return (
    <button
      type="button"
      role="option"
      aria-selected={selected}
      className={`route-dropdown-item ${selected ? 'selected' : ''}`}
      onClick={onPick}
    >
      <div className="item-left">
        <span className="route-item-dot" style={{ backgroundColor: route.color }} />
        <div className="item-text-group">
          <div className="item-header-row">
            <span className="item-code font-mono">{route.id}</span>
            {optimizable && route.counterpart && (
              <span className="item-counterpart-badge" title={`Equivale a la ${route.counterpart} en sentido contrario`}>
                ≙ {route.counterpart}
              </span>
            )}
            <span className="item-typology-badge">cada {route.headway_min.toFixed(1)} min</span>
          </div>
          <span className="item-sub">
            Hacia {route.service} · {route.stops_count} paradas en el corredor
          </span>
        </div>
      </div>
      {selected && <Check size={14} weight="bold" className="item-check" />}
    </button>
  );
};

export const RouteSelectDropdown: React.FC<RouteSelectDropdownProps> = ({
  routes,
  selectedRoute,
  onSelectRoute,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close when clicking outside or pressing Escape
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const activeRoute = routes.find((r) => r.id === selectedRoute);
  const optimizable = routes.filter((r) => r.role === 'optimizable');
  const background = routes.filter((r) => r.role !== 'optimizable');
  const pick = (id: string | null) => {
    onSelectRoute(id === selectedRoute ? null : id);
    setIsOpen(false);
  };

  return (
    <div className="custom-route-dropdown-container" ref={containerRef}>
      <button
        type="button"
        className={`route-dropdown-trigger ${isOpen ? 'open' : ''} ${selectedRoute ? 'has-filter' : ''}`}
        onClick={() => setIsOpen((prev) => !prev)}
        title="Mostrar solo los buses de una ruta"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="trigger-left">
          {activeRoute ? (
            <>
              <span className="route-trigger-dot" style={{ backgroundColor: activeRoute.color }} />
              <span className="route-trigger-text font-mono font-bold">{activeRoute.id}</span>
            </>
          ) : (
            <>
              <Bus size={13} weight="bold" />
              <span className="route-trigger-text">Todas las rutas</span>
            </>
          )}
        </span>
        <CaretDown size={11} weight="bold" className={`trigger-caret ${isOpen ? 'rotated' : ''}`} />
      </button>

      {isOpen && (
        <div className="route-dropdown-menu glass-panel" role="listbox">
          <button
            type="button"
            role="option"
            aria-selected={selectedRoute === null}
            className={`route-dropdown-item ${selectedRoute === null ? 'selected' : ''}`}
            onClick={() => pick(null)}
          >
            <div className="item-left">
              <span className="route-item-dot dot-all" />
              <div className="item-text-group">
                <span className="item-name">Todas las rutas</span>
                <span className="item-sub">{routes.length} servicios troncales hacia el sur</span>
              </div>
            </div>
            {selectedRoute === null && <Check size={14} weight="bold" className="item-check" />}
          </button>

          <div className="route-dropdown-scroll">
            <div className="dropdown-group-header">
              <Brain size={12} weight="fill" />
              <span>OPTIMIZADAS POR LA IA ({optimizable.length})</span>
            </div>
            <p className="dropdown-group-note">
              Las 6 rutas del Avance II en sentido sur: misma numeración que B13…B75 (≙), que van hacia el norte.
            </p>
            {optimizable.map((r) => (
              <RouteItem key={r.id} route={r} selected={selectedRoute === r.id} onPick={() => pick(r.id)} />
            ))}

            <div className="dropdown-group-header">
              <Bus size={12} weight="bold" />
              <span>RUTAS DE FONDO ({background.length})</span>
            </div>
            <p className="dropdown-group-note">Comparten el corredor con su frecuencia GTFS; la IA no las modifica.</p>
            {background.map((r) => (
              <RouteItem key={r.id} route={r} selected={selectedRoute === r.id} onPick={() => pick(r.id)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
