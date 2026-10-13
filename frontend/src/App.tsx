import React, { useEffect, useState } from 'react';
import { AnalyticsView } from './components/AnalyticsView';
import { Header } from './components/Header';
import { InspectorModal } from './components/InspectorModal';
import { KpiPanel } from './components/KpiPanel';
import { MapLegend } from './components/MapLegend';
import { MapViewport } from './components/MapViewport';
import { PlaybackBar } from './components/PlaybackBar';
import { useSimulation } from './hooks/useSimulation';
import type { ActiveView, InterpolatedBus, SelectedEntity, Station, ThemeMode } from './types';
import './App.css';

export const App: React.FC = () => {
  // Theme state
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('flowtm_theme');
    return (saved as ThemeMode) || 'dark';
  });

  // Calculate resolved theme (dark or light)
  const [resolvedTheme, setResolvedTheme] = useState<'dark' | 'light'>('dark');

  useEffect(() => {
    localStorage.setItem('flowtm_theme', theme);
    if (theme === 'system') {
      const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      setResolvedTheme(isDark ? 'dark' : 'light');
    } else {
      setResolvedTheme(theme);
    }
  }, [theme]);

  // Apply theme class to document body
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', resolvedTheme);
  }, [resolvedTheme]);

  // Simulation state hook with baseline & optimized dual feeds
  const {
    stations,
    routes,
    summary,
    summaryOpt,
    aiLog,
    simTimeSec,
    durationSec,
    isPlaying,
    playbackSpeed,
    selectedRoute,
    setSelectedRoute,
    activeBuses,
    activeBusesOptimized,
    currentQueues,
    currentQueuesOptimized,
    togglePlay,
    seek,
    setSpeed,
    reset,
  } = useSimulation();

  const [activeView, setActiveView] = useState<ActiveView>('map');
  const [isSplitView, setIsSplitView] = useState<boolean>(false);
  const [isKpiPanelOpen, setIsKpiPanelOpen] = useState(true);
  const [selectedEntity, setSelectedEntity] = useState<SelectedEntity | null>(null);
  const [isCameraFollowing, setIsCameraFollowing] = useState<boolean>(false);

  // Live entity synchronization: continuously updates entity metrics (passengers, dwell, status, queue) at 60 FPS
  const liveSelectedEntity = React.useMemo<SelectedEntity | null>(() => {
    if (!selectedEntity) return null;

    if (selectedEntity.type === 'bus') {
      const liveBus = activeBuses.find((b) => b.bus_id === selectedEntity.id);
      if (liveBus) {
        return {
          type: 'bus',
          id: liveBus.bus_id,
          data: liveBus,
        };
      }
      return {
        ...selectedEntity,
        data: {
          ...selectedEntity.data,
          is_finished: true,
        },
      };
    }

    if (selectedEntity.type === 'station') {
      const liveStation = stations.find((s) => s.code === selectedEntity.id);
      if (liveStation) {
        return {
          type: 'station',
          id: liveStation.code,
          data: {
            ...liveStation,
            queue: currentQueues[liveStation.code] || 0,
          },
        };
      }
    }

    return selectedEntity;
  }, [selectedEntity, activeBuses, stations, currentQueues]);

  // Allow deep-linking or automated inspection via ?inspect=bus or ?inspect=station
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const inspectType = params.get('inspect');
    if (inspectType === 'bus' && activeBuses.length > 0 && !selectedEntity) {
      const bus = activeBuses.find((b) => b.passengers > 50) || activeBuses[0];
      if (bus) {
        setSelectedEntity({ type: 'bus', id: bus.bus_id, data: bus });
      }
    }
  }, [activeBuses, selectedEntity]);

  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is in an input
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) return;

      if (e.code === 'Space') {
        e.preventDefault();
        togglePlay();
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        seek(Math.min(durationSec, simTimeSec + (e.shiftKey ? 60 : 10)));
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        seek(Math.max(0, simTimeSec - (e.shiftKey ? 60 : 10)));
      } else if (e.code === 'Escape') {
        setSelectedEntity(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePlay, seek, durationSec, simTimeSec]);

  return (
    <div className="flowtm-app-container">
      {/* 1. Header Bar with View Switcher and Split View Toggle */}
      <Header
        simTimeSec={simTimeSec}
        activeBusesCount={activeBuses.length}
        totalPassengers={summary?.total_passengers_served || 48899}
        routes={routes}
        selectedRoute={selectedRoute}
        onSelectRoute={setSelectedRoute}
        theme={theme}
        onThemeChange={setTheme}
        onToggleKpiPanel={() => setIsKpiPanelOpen((prev) => !prev)}
        isKpiPanelOpen={isKpiPanelOpen}
        activeView={activeView}
        onChangeView={setActiveView}
        isSplitView={isSplitView}
        onToggleSplitView={() => setIsSplitView((prev) => !prev)}
      />

      {/* 2. Main Central Viewport: Tab 1 (Mapa OCC) vs Tab 2 (Analítica & KPIs) */}
      <main className="flowtm-main-viewport">
        {activeView === 'map' ? (
          <div className={`map-viewport-wrapper ${isSplitView ? 'split-active' : 'single-active'}`}>
            {/* Viewport 1: Baseline Scenario (Current GTFS) */}
            <div className="map-panel-container base-panel">
              {isSplitView && (
                <div className="split-view-badge base-badge">
                  <span className="badge-dot" />
                  <span className="badge-text">ESCENARIO BASE (GTFS VIGENTE)</span>
                </div>
              )}
              <MapViewport
                theme={theme}
                resolvedTheme={resolvedTheme}
                stations={stations}
                routes={routes}
                activeBuses={activeBuses}
                currentQueues={currentQueues}
                selectedEntity={selectedEntity}
                onSelectEntity={setSelectedEntity}
                isCameraFollowing={isCameraFollowing}
                onStopCameraFollowing={() => setIsCameraFollowing(false)}
              />
            </div>

            {/* Viewport 2: Optimized Scenario (Split View) */}
            {isSplitView && (
              <div className="map-panel-container optimized-panel">
                <div className="split-view-badge opt-badge">
                  <span className="badge-dot opt-dot" />
                  <span className="badge-text">ESCENARIO OPTIMIZADO FLOWTM</span>
                  <span className="badge-tag">[FLOWTM-SCHEDULER ACTIVO]</span>
                </div>
                <MapViewport
                  theme={theme}
                  resolvedTheme={resolvedTheme}
                  stations={stations}
                  routes={routes}
                  activeBuses={activeBusesOptimized}
                  currentQueues={currentQueuesOptimized}
                  selectedEntity={selectedEntity}
                  onSelectEntity={setSelectedEntity}
                  isCameraFollowing={isCameraFollowing}
                  onStopCameraFollowing={() => setIsCameraFollowing(false)}
                />
              </div>
            )}

            {/* Floating Map Legend (Symbology & Fleet Appendix) */}
            <MapLegend routes={routes} />

            {/* Floating KPI Side Panel */}
            <KpiPanel
              isOpen={isKpiPanelOpen}
              onClose={() => setIsKpiPanelOpen(false)}
              summary={summary}
              routes={routes}
              stations={stations}
              activeBuses={activeBuses}
              currentQueues={currentQueues}
              isSplitView={isSplitView}
              onSelectStation={(st: Station) =>
                setSelectedEntity({
                  type: 'station',
                  id: st.code,
                  data: { ...st, queue: currentQueues[st.code] || 0 },
                })
              }
              onSelectBus={(bus: InterpolatedBus) =>
                setSelectedEntity({
                  type: 'bus',
                  id: bus.bus_id,
                  data: bus,
                })
              }
            />

            {/* Spring Inspector Modal with Live Reactive Telemetry */}
            <InspectorModal
              selectedEntity={liveSelectedEntity}
              onClose={() => {
                setSelectedEntity(null);
                setIsCameraFollowing(false);
              }}
              routes={routes}
              isCameraFollowing={isCameraFollowing}
              onToggleCameraFollow={() => setIsCameraFollowing((prev) => !prev)}
              isSplitView={isSplitView}
            />
          </div>
        ) : (
          /* Tab 2: Dedicated Analytics Dashboard */
          <AnalyticsView
            isSplitView={isSplitView}
            onToggleSplitView={() => setIsSplitView((prev) => !prev)}
            summary={summary}
            summaryOpt={summaryOpt}
            aiLog={aiLog}
            routes={routes}
            stations={stations}
            activeBuses={activeBuses}
            activeBusesOptimized={activeBusesOptimized}
            currentQueues={currentQueues}
            currentQueuesOptimized={currentQueuesOptimized}
            simTimeSec={simTimeSec}
          />
        )}
      </main>

      {/* 3. Master Playback & Timeline Controls (Always shared across tabs) */}
      <PlaybackBar
        simTimeSec={simTimeSec}
        durationSec={durationSec}
        isPlaying={isPlaying}
        playbackSpeed={playbackSpeed}
        onTogglePlay={togglePlay}
        onReset={reset}
        onSeek={seek}
        onSpeedChange={setSpeed}
      />
    </div>
  );
};

export default App;
