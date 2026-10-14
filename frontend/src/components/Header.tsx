import React from 'react';
import {
  Bus,
  ChartLineUp,
  Columns,
  MapTrifold,
  Monitor,
  Moon,
  Pulse,
  SlidersHorizontal,
  Sun,
} from '@phosphor-icons/react';
import { RouteSelectDropdown } from './RouteSelectDropdown';
import type { ActiveView, RouteConfig, ThemeMode } from '../types';

interface HeaderProps {
  simTimeSec: number;
  activeBusesCount: number;
  totalPassengers: number;
  routes: RouteConfig[];
  selectedRoute: string | null;
  onSelectRoute: (routeId: string | null) => void;
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
  onToggleKpiPanel: () => void;
  isKpiPanelOpen: boolean;
  activeView: ActiveView;
  onChangeView: (view: ActiveView) => void;
  isSplitView: boolean;
  onToggleSplitView: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  simTimeSec,
  activeBusesCount,
  routes,
  selectedRoute,
  onSelectRoute,
  theme,
  onThemeChange,
  onToggleKpiPanel,
  isKpiPanelOpen,
  activeView,
  onChangeView,
  isSplitView,
  onToggleSplitView,
}) => {
  // Format simulation time (06:00:00 start)
  const totalSeconds = 6 * 3600 + Math.floor(simTimeSec);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours > 12 ? hours - 12 : hours;
  const timeFormatted = `${String(displayHours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')} ${period}`;

  // Cycle theme: dark -> light -> system -> dark
  const handleCycleTheme = () => {
    if (theme === 'dark') onThemeChange('light');
    else if (theme === 'light') onThemeChange('system');
    else onThemeChange('dark');
  };

  return (
    <header className="header-bar glass-panel">
      {/* 1. Left: Brand & Main Navigation Tabs */}
      <div className="header-brand">
        <div className="brand-logo-container" title="FlowTM • Centro de Control Operacional">
          <div className="brand-icon">
            <Bus size={18} weight="bold" color="#FFFFFF" />
          </div>
          <div className="brand-title">
            <span className="brand-flow">Flow</span>
            <span className="brand-tm">TM</span>
            <span className="brand-occ-badge">OCC</span>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="header-view-tabs">
          <button
            className={`view-tab-btn ${activeView === 'map' ? 'active' : ''}`}
            onClick={() => onChangeView('map')}
            title="Visor Troncal y Flota en Vivo (Mapa 3D WebGL)"
          >
            <MapTrifold size={15} weight={activeView === 'map' ? 'fill' : 'bold'} />
            <span className="tab-label">Mapa Troncal</span>
          </button>
          <button
            className={`view-tab-btn ${activeView === 'analytics' ? 'active' : ''}`}
            onClick={() => onChangeView('analytics')}
            title="Analítica Avanzada, Diagramas de Marey y Rendimiento"
          >
            <ChartLineUp size={15} weight={activeView === 'analytics' ? 'fill' : 'bold'} />
            <span className="tab-label">Analítica & KPIs</span>
          </button>
        </div>
      </div>

      {/* 2. Center: Sleek Compact Master Clock Pill */}
      <div className="header-clock-section">
        <div className="master-clock-pill" title="Reloj Maestro de Operaciones (Tiempo Real Simulado)">
          <span className="clock-live-indicator" />
          <span className="clock-tag">OCC</span>
          <span className="master-clock-time tabular-nums font-mono">{timeFormatted}</span>
        </div>
      </div>

      {/* 3. Right: Route Filter, Active Fleet, Split View & Controls */}
      <div className="header-actions">
        {/* Route Filter Selector (Map View Only) */}
        {activeView === 'map' && (
          <RouteSelectDropdown
            routes={routes}
            selectedRoute={selectedRoute}
            onSelectRoute={onSelectRoute}
          />
        )}

        {/* Active Fleet Indicator Badge */}
        <div className="fleet-stat-badge" title="Flota activa de buses en tránsito comercial">
          <Pulse size={14} weight="bold" color="var(--accent-blue)" />
          <span className="tabular-nums font-semibold font-mono">{activeBusesCount}</span>
          <span className="fleet-stat-label">Buses</span>
        </div>

        {/* Split Screen Toggle Button */}
        <button
          className={`split-view-toggle-btn ${isSplitView ? 'active' : ''}`}
          onClick={onToggleSplitView}
          title={isSplitView ? 'Cerrar Pantalla Dividida (Volver a Vista Simple)' : 'Comparar Escenario Base vs. Optimizado'}
        >
          <Columns size={15} weight={isSplitView ? 'fill' : 'bold'} />
          <span className="split-btn-label">{isSplitView ? 'Dividida' : 'Comparar'}</span>
          {isSplitView && <span className="split-active-indicator" />}
        </button>

        {/* Single Cycle Theme Toggle Button */}
        <button
          className="theme-cycle-btn"
          onClick={handleCycleTheme}
          title={`Tema: ${theme === 'dark' ? 'Oscuro' : theme === 'light' ? 'Claro' : 'Automático'}. Clic para cambiar.`}
          aria-label="Cambiar tema de color"
        >
          {theme === 'dark' && <Moon size={15} weight="fill" />}
          {theme === 'light' && <Sun size={15} weight="bold" />}
          {theme === 'system' && <Monitor size={15} weight="regular" />}
        </button>

        {/* Toggle KPI Panel (available in map view) */}
        {activeView === 'map' && (
          <button
            className={`kpi-toggle-btn ${isKpiPanelOpen ? 'active' : ''}`}
            onClick={onToggleKpiPanel}
            title={isKpiPanelOpen ? 'Ocultar Telemetría' : 'Abrir Telemetría'}
            aria-label="Alternar Panel de Telemetría"
          >
            <SlidersHorizontal size={16} weight="bold" />
          </button>
        )}
      </div>
    </header>
  );
};
