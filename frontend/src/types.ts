export type ThemeMode = 'system' | 'dark' | 'light';
export type ActiveView = 'map' | 'analytics' | 'agent';

export type BusTypology = 'articulado' | 'biarticulado';

export interface Station {
  code: string;
  name: string;
  official_name?: string;
  sequence: number;
  lat: number;
  lon: number;
  distance_next_m: number;
  travel_time_sec: number;
  ub_est?: string;
  num_vag?: number;
  cap_biart?: number;
  cap_art?: number;
  area_est?: number;
}

export interface RouteConfig {
  id: string;
  name: string;
  service: string;
  color: string;
  role?: 'optimizable' | 'fondo';
  /** Opposite-direction route with the same number (e.g. B13 for H13). */
  counterpart?: string | null;
  headway_min: number;
  cycle_time_min?: number;
  stops: string[];
  stops_count: number;
  bus_type?: BusTypology;
  capacity?: number;
  length_m?: number;
}

export interface Keyframe {
  t: number;
  lat: number;
  lon: number;
  occ: number;
  pax: number;
}

export interface BusTrajectory {
  bus_id: string;
  route: string;
  start_time: number;
  end_time: number;
  keyframes: Keyframe[];
}

export interface QueueTimestamp {
  t: number;
  queues: Record<string, number>;
}

export interface SummaryKPIs {
  total_dispatched_buses: number;
  total_passengers_served: number;
  avg_waiting_time_min: number;
  avg_occupancy_pct: number;
  overcrowded_buses_pct: number;
  max_queue_station: number;
  active_routes: number;
  total_stations: number;
  sim_duration_sec: number;
  start_hour: number;
  stranded_passengers_in_queue?: number;
  avg_dispatch_delay_min?: number;
  optimizable_routes?: number;
  od_top?: ODPair[];
}

export interface ODPair {
  origin: string;
  destination: string;
  origin_name: string;
  destination_name: string;
  passengers: number;
  share_pct: number;
}

export interface InterpolatedBus {
  bus_id: string;
  route: string;
  lat: number;
  lon: number;
  occupancy_pct: number;
  passengers: number;
  color: string;
  /** Route is one of the 6 services the agent optimizes. */
  is_optimizable?: boolean;
  bus_type: BusTypology;
  capacity: number;
  length_m: number;
  prev_station?: string;
  next_station?: string;
  is_stopped?: boolean;
  current_station?: string;
  dwell_remaining_sec?: number;
  speed_kmh?: number;
  is_bunching?: boolean;
  bunching_with?: string;
  // Metrics for optimized comparative simulation
  opt_occupancy_pct?: number;
  opt_passengers?: number;
  opt_speed_kmh?: number;
  opt_is_stopped?: boolean;
  opt_current_station?: string;
  opt_dwell_remaining_sec?: number;
  opt_lat?: number;
  opt_lon?: number;
}

export interface SelectedEntity {
  type: 'bus' | 'station';
  id: string;
  data: any;
}

export interface AIOptimizationIteration {
  iteration: number;
  temperature: number | null;
  evaluations?: number;
  candidate_headways?: Record<string, number>;
  candidate_utility?: number;
  candidate_utility_se?: number;
  headways: Record<string, number>;
  utility: number;
  delta_u: number;
  accepted: boolean;
  is_new_best: boolean;
  best_utility: number;
  wait_time_min: number;
  stranded_pax: number;
  overcrowded_pct: number;
  fleet_used: number;
  breakdown?: {
    utility: number;
    cost: number;
    w_wait_term: number;
    w_overcrowd_term: number;
    w_stranded_term: number;
    w_fleet_term: number;
    hard_penalty: number;
    w_mean: number;
    overcrowded_pct: number;
    q_remanente: number;
    fleet_used: number;
  };
}

export interface AIOptimizationLog {
  baseline: {
    headways: Record<string, number>;
    fleet_used: number;
    utility: number;
    breakdown: any;
    wait_time_min: number;
    stranded_pax: number;
    overcrowded_pct: number;
    transported_pax: number;
  };
  optimized: {
    headways: Record<string, number>;
    fleet_used: number;
    utility: number;
    breakdown: any;
    wait_time_min: number;
    stranded_pax: number;
    overcrowded_pct: number;
    transported_pax: number;
  };
  delta_utility: number;
  max_fleet?: number;
  holdout?: HoldoutReport;
  config?: Record<string, unknown>;
  optimizable_routes?: string[];
  background_routes?: string[];
  history: AIOptimizationIteration[];
}

/** Replay telemetry of a schedule in the frontend contracts. */
export interface ReplayPayload {
  bus_trajectories: BusTrajectory[];
  station_queues: QueueTimestamp[];
  summary: SummaryKPIs;
}

/** Description of a Lab run shown on the split-screen badge. */
export interface LabRunInfo {
  runId?: number;
  algorithm: string;
  finishedAt: string;
  deltaU: number;
  validated: boolean;
}

/** An agent run from the Agent Lab, ready to be shown on the map. */
export interface AgentRunPayload {
  replay: ReplayPayload;
  log: AIOptimizationLog;
  source: LabRunInfo;
}

/** Which schedule the optimized (right) side of the split view is showing. */
export type OptimizedSource = { kind: 'agente' } | ({ kind: 'laboratorio' } & LabRunInfo);

export interface PairedStat {
  base: number;
  candidato: number;
  diferencia: number;
  diferencia_pct: number;
  ic95: [number, number];
  semillas_mejor: number;
  semillas: number;
  /** 95% CI excludes zero (either direction). */
  significativo: boolean;
  /** Difference goes in the desirable direction. */
  mejora: boolean;
}

export interface HoldoutReport {
  semillas: number[];
  utilidad: PairedStat;
  espera_min: PairedStat;
  sobrecupo_pct: PairedStat;
  varados: PairedStat;
  transportados: PairedStat;
  flota: { base: number; candidato: number };
}

export interface AlgorithmSummary {
  delta_u_validacion_media: number;
  delta_u_validacion_min: number;
  delta_u_validacion_max: number;
  corridas_significativas: number;
  espera_pct_media: number;
  sobrecupo_pct_media: number;
}

export interface AlgorithmComparison {
  presupuesto_evaluaciones: number;
  semillas_entrenamiento: number[];
  semillas_validacion: number;
  corridas_por_algoritmo: number;
  resumen: Record<string, AlgorithmSummary>;
}
