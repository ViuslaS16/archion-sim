export interface AgentPosition {
  id: string;
  x: number;
  y: number;
  type: string;
}

export interface Obstacle {
  points: number[][];
}

export interface SimulationFrame {
  frame_id: number;
  data: Record<string, Record<string, unknown>>;
}

// --- Compliance ---

export interface ViolationCoordinate {
  x: number;
  y: number;
  z: number;
}

export interface Violation {
  id: string;
  type:
    | "corridor_width"
    | "door_width"
    | "turning_space"
    | "ramp_gradient"
    | "bottleneck";
  severity: "critical" | "high" | "medium" | "low";
  coordinate: ViolationCoordinate;
  measured_value: number;
  required_value: number;
  description: string;
  regulation: string;
}

export interface ComplianceReport {
  standard: string;
  building_type: string;
  total_violations: number;
  violations: Violation[];
  compliance_score: number;
  status: "pass" | "fail";
  summary: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
}

export interface ComplianceResponse {
  status: "idle" | "running" | "done" | "error";
  report?: ComplianceReport;
  error?: string;
  message?: string;
}

// --- Geometry (Module 2) ---

export interface GeometryData {
  boundaries: number[][];              // buffered boundary (for navigation)
  rawBoundaries: number[][];           // exact unbuffered boundary (for rendering)
  obstacles: number[][];               // [[x1,y1,x2,y2], ...]
  centerOffset?: [number, number];     // [cx, cy] subtracted during extraction
  floorArea?: number;                  // m² of floor space
  modelUrl?: string;
  modelFormat?: "obj" | "glb" | "gltf";
}

// --- Trajectories (Module 3) ---

export interface AgentFrame {
  pos: [number, number];
  type: "standard" | "specialist";
}

/** { "frame_id": { "agent_id": AgentFrame } } */
export type Trajectories = Record<string, Record<string, AgentFrame>>;

// --- Analytics ---

export interface FlowRatePoint {
  time_sec: number;
  agents_per_minute: number;
}

export interface CongestionIndex {
  percentage: number;
  slow_threshold_ms: number;
}

export interface EfficiencyScore {
  average: number;
  per_agent: number[];
}

export interface HeatmapBounds {
  min_x: number;
  min_y: number;
  max_x: number;
  max_y: number;
}

export interface DensityHeatmap {
  grid: number[][];
  bounds: HeatmapBounds;
  resolution: number;
  shape: [number, number];
  max_density: number;
}

export interface CongestionTimelinePoint {
  time_sec: number;
  congestion_pct: number;
}

export interface VelocityTimelinePoint {
  time_sec: number;
  avg_velocity_ms: number;
}

export interface AnalyticsSummary {
  total_agents: number;
  simulation_duration_sec: number;
  avg_velocity_ms: number;
  peak_congestion_pct: number;
  total_distance_m: number;
  floor_area_sqm: number;
}

export interface AnalyticsData {
  flow_rate: FlowRatePoint[];
  congestion_index: CongestionIndex;
  efficiency_score: EfficiencyScore;
  density_heatmap: DensityHeatmap;
  congestion_timeline: CongestionTimelinePoint[];
  velocity_timeline: VelocityTimelinePoint[];
  summary: AnalyticsSummary;
}

export interface AnalyticsResponse {
  status: "done" | "error";
  data?: AnalyticsData;
  error?: string;
}

export interface ReportResponse {
  status: "done" | "error";
  download_url?: string;
  filename?: string;
}

// --- Playback ---

export type PlaybackSpeed = 1 | 2 | 4;
export type ViewMode = "3d" | "2d";

// --- Simulation lifecycle ---

export type SimPhase =
  | "idle"
  | "uploading"
  | "processing"
  | "simulating"
  | "completed";
