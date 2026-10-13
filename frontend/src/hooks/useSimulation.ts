import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  AIOptimizationLog,
  BusTrajectory,
  BusTypology,
  InterpolatedBus,
  QueueTimestamp,
  RouteConfig,
  Station,
  SummaryKPIs,
} from '../types';

export const ROUTE_TYPOLOGIES: Record<string, { bus_type: BusTypology; capacity: number; length_m: number }> = {
  B13: { bus_type: 'biarticulado', capacity: 250, length_m: 27 },
  B27: { bus_type: 'biarticulado', capacity: 250, length_m: 27 },
  B75: { bus_type: 'biarticulado', capacity: 250, length_m: 27 },
  B18: { bus_type: 'articulado', capacity: 160, length_m: 18 },
  B23: { bus_type: 'articulado', capacity: 160, length_m: 18 },
  B74: { bus_type: 'articulado', capacity: 160, length_m: 18 },
};

function interpolateBusTrajectories(
  trajectories: BusTrajectory[],
  simTimeSec: number,
  selectedRoute: string | null,
  routeColorMap: Map<string, string>,
  stations: Station[],
  isOptimizedScenario = false
): InterpolatedBus[] {
  if (!trajectories.length) return [];

  const result: InterpolatedBus[] = [];
  const t = simTimeSec;

  for (let i = 0; i < trajectories.length; i++) {
    const b = trajectories[i];
    if (selectedRoute && b.route !== selectedRoute) continue;
    if (t < b.start_time || t > b.end_time) continue;

    const kf = b.keyframes;
    if (!kf || kf.length === 0) continue;

    const typo = ROUTE_TYPOLOGIES[b.route] || { bus_type: 'articulado' as BusTypology, capacity: 160, length_m: 18 };

    let lat = kf[0].lat;
    let lon = kf[0].lon;
    let occ = kf[0].occ;
    let pax = kf[0].pax;
    let isStopped = false;
    let currentStation: string | undefined;
    let dwellRemaining: number | undefined;
    let speedKmh = 0.0;

    if (t <= kf[0].t) {
      lat = kf[0].lat;
      lon = kf[0].lon;
      occ = kf[0].occ;
      pax = kf[0].pax;
    } else if (t >= kf[kf.length - 1].t) {
      const last = kf[kf.length - 1];
      lat = last.lat;
      lon = last.lon;
      occ = last.occ;
      pax = last.pax;
    } else {
      for (let j = 0; j < kf.length - 1; j++) {
        const k1 = kf[j];
        const k2 = kf[j + 1];
        if (t >= k1.t && t <= k2.t) {
          const span = k2.t - k1.t;
          const alpha = span > 0 ? (t - k1.t) / span : 0;
          lat = k1.lat + (k2.lat - k1.lat) * alpha;
          lon = k1.lon + (k2.lon - k1.lon) * alpha;

          // Dwell detection
          const dist = Math.hypot(k2.lat - k1.lat, k2.lon - k1.lon);
          if (dist < 0.00008 && span > 1.0) {
            isStopped = true;
            dwellRemaining = Math.max(0, Math.round(k2.t - t));
            if (stations.length > 0) {
              const matched = stations.find(
                (st) => Math.hypot(st.lat - lat, st.lon - lon) < 0.001
              );
              if (matched) currentStation = matched.name;
            }
            occ = k1.occ + (k2.occ - k1.occ) * alpha;
            pax = Math.round(k1.pax + (k2.pax - k1.pax) * alpha);
            speedKmh = 0.0;
          } else {
            isStopped = false;
            occ = k1.occ;
            pax = k1.pax;

            const dLat = (k2.lat - k1.lat) * 110574;
            const dLon = (k2.lon - k1.lon) * 110950;
            const distM = Math.hypot(dLat, dLon);
            const vBase = span > 0 ? (distM / span) * 3.6 : 38.0;

            let accel = 1.0;
            if (alpha < 0.22) {
              accel = Math.max(0.25, alpha / 0.22);
            } else if (alpha > 0.78) {
              accel = Math.max(0.25, (1.0 - alpha) / 0.22);
            }
            speedKmh = Math.round(vBase * accel * 10) / 10;
          }
          break;
        }
      }
    }

    // Dynamic color based on occupancy
    let displayColor = routeColorMap.get(b.route) || '#E53935';
    if (occ >= 90) {
      displayColor = '#E74C3C';
    } else if (occ >= 75) {
      displayColor = '#F39C12';
    }

    result.push({
      bus_id: b.bus_id,
      route: b.route,
      lat,
      lon,
      occupancy_pct: occ,
      passengers: pax,
      color: displayColor,
      bus_type: typo.bus_type,
      capacity: typo.capacity,
      length_m: typo.length_m,
      is_stopped: isStopped,
      current_station: currentStation,
      dwell_remaining_sec: dwellRemaining,
      speed_kmh: speedKmh,
      is_bunching: false,
    });
  }

  // Bus bunching detection only in baseline scenario
  if (!isOptimizedScenario) {
    for (let a = 0; a < result.length; a++) {
      for (let b = a + 1; b < result.length; b++) {
        if (result[a].route === result[b].route) {
          const dLat = (result[a].lat - result[b].lat) * 110574;
          const dLon = (result[a].lon - result[b].lon) * 110950;
          const dist = Math.hypot(dLat, dLon);
          if (dist < 420) {
            result[a].is_bunching = true;
            result[a].bunching_with = result[b].bus_id;
            result[b].is_bunching = true;
            result[b].bunching_with = result[a].bus_id;
          }
        }
      }
    }
  }

  return result;
}

export function useSimulation() {
  const [stations, setStations] = useState<Station[]>([]);
  const [routes, setRoutes] = useState<RouteConfig[]>([]);
  const [trajectories, setTrajectories] = useState<BusTrajectory[]>([]);
  const [trajectoriesOpt, setTrajectoriesOpt] = useState<BusTrajectory[]>([]);
  const [queueTimeline, setQueueTimeline] = useState<QueueTimestamp[]>([]);
  const [queueTimelineOpt, setQueueTimelineOpt] = useState<QueueTimestamp[]>([]);
  const [summary, setSummary] = useState<SummaryKPIs | null>(null);
  const [summaryOpt, setSummaryOpt] = useState<SummaryKPIs | null>(null);
  const [aiLog, setAiLog] = useState<AIOptimizationLog | null>(null);

  // Simulation Clock state
  const [simTimeSec, setSimTimeSec] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(5);
  const [selectedRoute, setSelectedRoute] = useState<string | null>(null);

  const simTimeRef = useRef<number>(0);
  const isPlayingRef = useRef<boolean>(true);
  const speedRef = useRef<number>(5);
  const lastRafTimeRef = useRef<number | null>(null);

  const DURATION_SEC = 10800; // 3 hours (06:00:00 - 09:00:00 AM)

  // Keep refs in sync for requestAnimationFrame
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  useEffect(() => {
    speedRef.current = playbackSpeed;
  }, [playbackSpeed]);

  // Load all simulation assets (Baseline + AI Optimized)
  useEffect(() => {
    Promise.all([
      fetch('/data/stations.json').then((r) => r.json()),
      fetch('/data/routes.json').then((r) => r.json()),
      fetch('/data/bus_trajectories.json').then((r) => r.json()),
      fetch('/data/station_queues.json').then((r) => r.json()),
      fetch('/data/summary.json').then((r) => r.json()),
      fetch('/data/bus_trajectories_opt.json').then((r) => r.json()).catch(() => []),
      fetch('/data/station_queues_opt.json').then((r) => r.json()).catch(() => []),
      fetch('/data/summary_opt.json').then((r) => r.json()).catch(() => null),
      fetch('/data/ai_optimization_log.json').then((r) => r.json()).catch(() => null),
    ])
      .then(([sts, rts, trjs, qtl, smm, trjsOpt, qtlOpt, smmOpt, log]) => {
        // Enrich routes with typology
        const enrichedRoutes = rts.map((r: RouteConfig) => {
          const typo = ROUTE_TYPOLOGIES[r.id] || { bus_type: 'articulado', capacity: 160, length_m: 18 };
          return {
            ...r,
            bus_type: typo.bus_type,
            capacity: typo.capacity,
            length_m: typo.length_m,
          };
        });
        setStations(sts);
        setRoutes(enrichedRoutes);
        setTrajectories(trjs);
        setQueueTimeline(qtl);
        setSummary(smm);
        if (trjsOpt && trjsOpt.length > 0) setTrajectoriesOpt(trjsOpt);
        if (qtlOpt && qtlOpt.length > 0) setQueueTimelineOpt(qtlOpt);
        if (smmOpt) setSummaryOpt(smmOpt);
        if (log) setAiLog(log);
      })
      .catch((err) => console.error('Error loading simulation assets:', err));
  }, []);

  // Main 60 FPS animation loop
  useEffect(() => {
    let animId: number;

    const tick = (now: number) => {
      if (lastRafTimeRef.current !== null && isPlayingRef.current) {
        const deltaSec = (now - lastRafTimeRef.current) / 1000;
        const newTime = simTimeRef.current + deltaSec * speedRef.current;

        if (newTime >= DURATION_SEC) {
          simTimeRef.current = DURATION_SEC;
          setIsPlaying(false);
          setSimTimeSec(DURATION_SEC);
        } else {
          simTimeRef.current = newTime;
          setSimTimeSec(newTime);
        }
      }
      lastRafTimeRef.current = now;
      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, []);

  // Controls
  const togglePlay = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  const seek = useCallback((timeSec: number) => {
    const clamped = Math.max(0, Math.min(DURATION_SEC, timeSec));
    simTimeRef.current = clamped;
    setSimTimeSec(clamped);
  }, []);

  const setSpeed = useCallback((speed: number) => {
    setPlaybackSpeed(speed);
  }, []);

  const reset = useCallback(() => {
    simTimeRef.current = 0;
    setSimTimeSec(0);
    setIsPlaying(true);
  }, []);

  // Route colors lookup map
  const routeColorMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const r of routes) {
      map.set(r.id, r.color);
    }
    return map;
  }, [routes]);

  // Compute interpolated active buses for Baseline scenario
  const activeBuses = useMemo<InterpolatedBus[]>(() => {
    return interpolateBusTrajectories(
      trajectories,
      simTimeSec,
      selectedRoute,
      routeColorMap,
      stations,
      false
    );
  }, [trajectories, simTimeSec, selectedRoute, routeColorMap, stations]);

  // Compute interpolated active buses for AI Optimized scenario
  const activeBusesOptimized = useMemo<InterpolatedBus[]>(() => {
    if (trajectoriesOpt.length > 0) {
      return interpolateBusTrajectories(
        trajectoriesOpt,
        simTimeSec,
        selectedRoute,
        routeColorMap,
        stations,
        true
      );
    }
    // Fallback if opt trajectories file not loaded yet
    return activeBuses.map((bus) => ({
      ...bus,
      occupancy_pct: Math.round(bus.occupancy_pct * 0.85),
      passengers: Math.round(bus.passengers * 0.85),
      is_bunching: false,
      bunching_with: undefined,
    }));
  }, [trajectoriesOpt, activeBuses, simTimeSec, selectedRoute, routeColorMap, stations]);

  // Compute station queues for Baseline
  const currentQueues = useMemo<Record<string, number>>(() => {
    if (!queueTimeline.length) return {};
    const t = simTimeSec;

    let closest = queueTimeline[0];
    let minDiff = Math.abs(queueTimeline[0].t - t);

    for (let i = 1; i < queueTimeline.length; i++) {
      const diff = Math.abs(queueTimeline[i].t - t);
      if (diff < minDiff) {
        minDiff = diff;
        closest = queueTimeline[i];
      }
    }

    return closest ? closest.queues : {};
  }, [queueTimeline, simTimeSec]);

  // Compute station queues for Optimized scenario
  const currentQueuesOptimized = useMemo<Record<string, number>>(() => {
    if (queueTimelineOpt.length > 0) {
      const t = simTimeSec;
      let closest = queueTimelineOpt[0];
      let minDiff = Math.abs(queueTimelineOpt[0].t - t);

      for (let i = 1; i < queueTimelineOpt.length; i++) {
        const diff = Math.abs(queueTimelineOpt[i].t - t);
        if (diff < minDiff) {
          minDiff = diff;
          closest = queueTimelineOpt[i];
        }
      }
      return closest ? closest.queues : {};
    }

    // Fallback: coordinate headway queue reduction
    const res: Record<string, number> = {};
    for (const [code, q] of Object.entries(currentQueues)) {
      res[code] = Math.max(0, Math.round(q * 0.65));
    }
    return res;
  }, [queueTimelineOpt, currentQueues, simTimeSec]);

  return {
    stations,
    routes,
    summary,
    summaryOpt,
    aiLog,
    simTimeSec,
    durationSec: DURATION_SEC,
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
  };
}
