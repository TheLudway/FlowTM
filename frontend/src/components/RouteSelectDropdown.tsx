import React, { useEffect, useRef, useState } from 'react';
import { Bus, CaretDown, Check } from '@phosphor-icons/react';
import type { RouteConfig } from '../types';

interface RouteSelectDropdownProps {
  routes: RouteConfig[];
  selectedRoute: string | null;
  onSelectRoute: (routeId: string | null) => void;
}

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

  const activeRouteObj = routes.find((r) => r.id === selectedRoute);

  return (
    <div className="custom-route-dropdown-container" ref={containerRef}>
      <button
        type="button"
        className={`route-dropdown-trigger ${isOpen ? 'open' : ''} ${selectedRoute ? 'has-filter' : ''}`}
        onClick={() => setIsOpen((prev) => !prev)}
        title="Filtrar simulación por ruta troncal específica"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="trigger-left">
          {activeRouteObj ? (
            <>
              <span
                className="route-trigger-dot"
                style={{ backgroundColor: activeRouteObj.color }}
              />
              <span className="route-trigger-text font-mono font-bold">{activeRouteObj.id}</span>
            </>
          ) : (
            <>
              <Bus size={13} weight="bold" />
              <span className="route-trigger-text">Todas las Rutas</span>
            </>
          )}
        </span>
        <CaretDown size={11} weight="bold" className={`trigger-caret ${isOpen ? 'rotated' : ''}`} />
      </button>

      {isOpen && (
        <div className="route-dropdown-menu glass-panel" role="listbox">
          <div className="dropdown-menu-header">RUTAS TRONCALES (PILOTO)</div>

          {/* Option: All Routes */}
          <button
            type="button"
            className={`route-dropdown-item ${selectedRoute === null ? 'selected' : ''}`}
            onClick={() => {
              onSelectRoute(null);
              setIsOpen(false);
            }}
          >
            <div className="item-left">
              <span className="route-item-dot dot-all" />
              <div className="item-text-group">
                <span className="item-name">Todas las Rutas</span>
                <span className="item-sub">6 servicios en circulación</span>
              </div>
            </div>
            {selectedRoute === null && <Check size={14} weight="bold" className="item-check" />}
          </button>

          <div className="dropdown-divider" />

          {/* Individual Routes */}
          {routes.map((r) => {
            const isSelected = selectedRoute === r.id;
            return (
              <button
                key={r.id}
                type="button"
                className={`route-dropdown-item ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  onSelectRoute(isSelected ? null : r.id);
                  setIsOpen(false);
                }}
              >
                <div className="item-left">
                  <span
                    className="route-item-dot"
                    style={{ backgroundColor: r.color }}
                  />
                  <div className="item-text-group">
                    <div className="item-header-row">
                      <span className="item-code font-mono">{r.id}</span>
                      <span className="item-typology-badge">
                        {r.bus_type === 'biarticulado' ? 'Biartic. (250p)' : 'Artic. (160p)'}
                      </span>
                    </div>
                    <span className="item-sub">{r.name}</span>
                  </div>
                </div>
                {isSelected && <Check size={14} weight="bold" className="item-check" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
