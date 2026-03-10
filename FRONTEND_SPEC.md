# Archion Sim — Frontend Full Specification

Complete specification to generate the Next.js frontend from scratch. Every file, every component, every interface is documented here in exact implementation detail.

---

## Tech Stack

| Layer | Package | Version |
|---|---|---|
| Framework | `next` | 16.1.6 |
| UI Library | `react` / `react-dom` | 19.2.3 |
| 3D Engine | `three` | ^0.182.0 |
| R3F Renderer | `@react-three/fiber` | ^9.5.0 |
| R3F Utilities | `@react-three/drei` | ^10.7.7 |
| Animation | `gsap` | ^3.14.2 |
| Motion | `framer-motion` | ^12.34.0 |
| Charts | `recharts` | ^3.7.0 |
| Icons | `lucide-react` | ^0.569.0 |
| Styling | `tailwindcss` | ^4 |
| Language | TypeScript | ^5 |

### Dev Dependencies
- `@tailwindcss/postcss` ^4
- `@types/node`, `@types/react`, `@types/react-dom`, `@types/three`
- `eslint`, `eslint-config-next` 16.1.6

---

## File Tree

```
frontend/
├── package.json
├── tsconfig.json
├── next.config.ts
├── postcss.config.mjs
├── eslint.config.mjs
└── src/
    ├── app/
    │   ├── favicon.ico
    │   ├── globals.css
    │   ├── layout.tsx
    │   └── page.tsx
    ├── components/
    │   ├── AnalyticsDashboard.tsx
    │   ├── Controls.tsx
    │   ├── ErrorBoundary.tsx
    │   ├── ModelRenderer.tsx
    │   ├── ModelUpload.tsx
    │   ├── Providers.tsx
    │   ├── SimViewer.tsx
    │   └── ViolationMonitor.tsx
    ├── hooks/
    │   └── usePlayback.ts
    ├── lib/
    │   └── theme.ts
    └── types/
        └── simulation.ts
```

---

## Environment Variable

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Used in every component via:
```ts
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
```

---

## `src/types/simulation.ts` — All Interfaces

```ts
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

// --- Geometry ---

export interface GeometryData {
  boundaries: number[][];         // buffered boundary (for navigation)
  rawBoundaries: number[][];      // exact unbuffered boundary (for rendering)
  obstacles: number[][];          // [[x1,y1,x2,y2], ...]
  centerOffset?: [number, number]; // [cx, cy] subtracted during extraction
  floorArea?: number;             // m² of floor space
  modelUrl?: string;
  modelFormat?: "obj" | "glb" | "gltf";
}

// --- Trajectories ---

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
```

---

## `src/lib/theme.ts` — Design Tokens

```ts
export const colors = {
  cyan: {
    50: "#ecfeff", 100: "#cffafe", 200: "#a5f3fc",
    300: "#67e8f9", 400: "#22d3ee", 500: "#06b6d4",
    600: "#0891b2", 700: "#0e7490",
  },
  zinc: {
    50: "#fafafa", 100: "#f4f4f5", 200: "#e4e4e7",
    300: "#d4d4d8", 400: "#a1a1aa", 500: "#71717a",
    600: "#52525b", 700: "#3f3f46", 800: "#27272a",
    900: "#18181b", 950: "#09090b",
  },
  success: "#16a34a",
  warning: "#F59E0B",
  error: "#DC2626",
  info: "#3B82F6",
  severity: {
    critical: "#DC2626",
    high: "#F59E0B",
    medium: "#EAB308",
    low: "#3B82F6",
  },
  agent: {
    standard: "#3b82f6",
    specialist: "#eab308",
    conflict: "#f97316",
  },
} as const;

export const brand = {
  name: "Archion Sim",
  tagline: "Building Compliance & Analytics",
  version: "1.0.0",
} as const;

export const thresholds = {
  compliance: { pass: 70, warning: 50 },
  congestion: { good: 15, warning: 30 },
  efficiency: { good: 0.8, warning: 0.6 },
} as const;

export function getMetricStatus(
  value: number,
  metric: "compliance" | "congestion" | "efficiency",
): "good" | "warning" | "critical" {
  if (metric === "congestion") {
    if (value <= thresholds.congestion.good) return "good";
    if (value <= thresholds.congestion.warning) return "warning";
    return "critical";
  }
  if (metric === "compliance") {
    if (value >= thresholds.compliance.pass) return "good";
    if (value >= thresholds.compliance.warning) return "warning";
    return "critical";
  }
  if (value >= thresholds.efficiency.good) return "good";
  if (value >= thresholds.efficiency.warning) return "warning";
  return "critical";
}
```

---

## `src/hooks/usePlayback.ts`

### Purpose
rAF-based playback loop with time accumulator. Drives the 3D agent animation by advancing `frameRef.current` (a mutable ref) every tick. The ref is read each frame by the R3F `useFrame` loop in `AgentSwarm` without triggering React re-renders.

### Constants
- `PLAYBACK_FPS = 10` — simulation Hz
- `BASE_INTERVAL = 100` — ms per frame at 1x speed

### Interface

```ts
interface UsePlaybackOptions {
  trajectories: Trajectories | null;
}

interface UsePlaybackReturn {
  isPlaying: boolean;
  currentFrame: number;          // React state, drives scrubber UI
  totalFrames: number;
  speed: PlaybackSpeed;          // 1 | 2 | 4
  frameRef: MutableRefObject<number>; // read by R3F loop (no re-render)
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  reset: () => void;
  setSpeed: (speed: PlaybackSpeed) => void;
  cycleSpeed: () => void;        // cycles 1 → 2 → 4 → 1
  scrubTo: (frame: number) => void;
  setPlaying: (playing: boolean) => void;
}
```

### Loop Logic
- `useEffect` on `[isPlaying, trajectories, totalFrames, speed]`
- `requestAnimationFrame` tick with `lastTimestampRef` and `accumulatorRef`
- Elapsed clamped to `200ms` to handle tab backgrounding
- `frameInterval = BASE_INTERVAL / speed`
- Drain accumulator in a `while` loop, incrementing `frameRef.current`
- Loop back to 0 when frame exceeds `totalFrames`
- Call `setCurrentFrame(frameRef.current)` to trigger scrubber re-render
- Returns cleanup: `cancelAnimationFrame(rafIdRef.current)`

---

## `src/app/globals.css`

```css
@import "tailwindcss";

:root {
  --background: #ffffff;
  --foreground: #171717;
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
}

@media (prefers-color-scheme: dark) {
  :root {
    --background: #0a0a0a;
    --foreground: #ededed;
  }
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: Arial, Helvetica, sans-serif;
}
```

---

## `src/app/layout.tsx`

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Providers } from "@/components/Providers";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Archion Sim — Building Compliance & Analytics",
  description: "AI-powered building compliance simulation and analysis platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

---

## `src/components/ErrorBoundary.tsx`

Class component. State: `{ hasError: boolean; error: Error | null }`.

- `getDerivedStateFromError` sets `hasError: true`
- `componentDidCatch` logs to console
- Error UI: full-screen dark card (`bg-zinc-950`), red icon, error message in monospace box, two buttons: **Try Again** (resets state) and **Reload Page** (`window.location.reload()`)

## `src/components/Providers.tsx`

Wraps children in `<ErrorBoundary>`. Thin wrapper allowing future providers (React Query, theme, etc.) to be added here.

```tsx
export function Providers({ children }: { children: ReactNode }) {
  return <ErrorBoundary>{children}</ErrorBoundary>;
}
```

---

## `src/components/ModelUpload.tsx`

### Purpose
Landing page drop zone for 3D model upload before geometry is loaded. Uploads via `XMLHttpRequest` (for progress events) to `POST /api/process-model`.

### State
```ts
type UploadStatus = "idle" | "uploading" | "success" | "error";
const [status, setStatus] = useState<UploadStatus>("idle");
const [progress, setProgress] = useState(0);    // 0-100
const [error, setError] = useState<string | null>(null);
const [dragOver, setDragOver] = useState(false);
```

### Props
```ts
interface ModelUploadProps {
  onUploadComplete: (data: GeometryData) => void;
  apiUrl: string;
}
```

### Validation
Accepted extensions: `.obj`, `.glb`, `.gltf`. Returns error string if invalid.

### Upload Flow
1. Build `FormData` with `file` key
2. `XHR.upload.addEventListener("progress")` → updates `progress` state
3. On load success (2xx): `JSON.parse(xhr.responseText)` → call `onUploadComplete`
4. On error: set `status = "error"`, extract `body.detail` or fall back to generic message

### UI Structure
- **Drop zone** (`div`): drag events (`onDragOver`, `onDragLeave`, `onDrop`), click → `inputRef.current.click()`
- Border color changes: cyan when dragging, red on error, green on success, zinc default
- Icon: `<CloudUpload>` (idle/drag), `<CheckCircle>` (success), `<FileWarning>` (error)
- Text: "Drag & drop a 3D model here / or click to browse — .obj, .glb, .gltf"
- Hidden `<input type="file" accept=".obj,.glb,.gltf">`
- **Progress bar**: shown when `status === "uploading"`, cyan fill animated via `width: ${progress}%`
- **Error toast**: shown when `status === "error"`, red background, `<FileWarning>` icon + error text

---

## `src/components/ModelRenderer.tsx`

### Purpose
Renders a 3D architectural model inside the R3F canvas. Supports `.obj`, `.glb`, `.gltf`. Aligns the model with the backend's coordinate system using `centerOffset`.

### Coordinate Mapping
The geometry pipeline centers boundaries by subtracting `centerOffset [cx, cy]` in 2D space (X, Y after Z-up rotation). In Three.js (Y-up):
- pipeline X → Three.js X
- pipeline Y → Three.js -Z

Alignment: shift model by `(-cx, -box.min.y + MODEL_Y_LIFT, cy)`

`MODEL_Y_LIFT = -0.5` (floor sits slightly below y=0 for visual grounding)

### Placeholder Color Filtering
Filters out meshes with blue/teal colors that come from the backend geometry preview. Hides meshes whose material color matches:
- Exact hex set: `0x008b8b`, `0x0080ff`, `0x0891b2`, `0x06b6d4`, `0x22d3ee`, `0x2a2a4a`, `0x1a1a3a`
- Heuristic: `r < 30 && g > 100 && b > 150` (teal family)

Hidden meshes get `obj.visible = false`.

### React Strict Mode Fix
**Critical bug**: In Strict Mode, effects run twice. The second run computes `Box3` from an already-translated scene, doubling the offset. Fix: always call `scene.position.set(0, 0, 0)` **before** computing `setFromObject`.

### Sub-components

**`GltfModel`**: uses `useGLTF(url)` from drei. `useEffect` on `[scene, centerOffset]`:
1. `scene.position.set(0, 0, 0)` — reset before bounds
2. `filterPlaceholderMeshes(scene)`
3. `scene.position.copy(computeAlignedPosition(scene, centerOffset))`

**`ObjModel`**: uses `useLoader(OBJLoader, url)`. Same effect pattern, plus:
- Applies fallback `MeshStandardMaterial` (`color: "#8899aa"`) to meshes missing material
- Enables `castShadow` and `receiveShadow` on all child meshes

**`ModelRenderer`** (default export):
```tsx
<Suspense fallback={null}>
  {format === "obj" ? <ObjModel .../> : <GltfModel .../>}
</Suspense>
```

---

## `src/components/SimViewer.tsx`

The core 3D viewport. Lazy-loaded (SSR disabled) via `dynamic(() => import(...), { ssr: false })` in `page.tsx`.

### Props
```ts
interface SimViewerProps {
  boundaries: number[][];              // buffered (navigation)
  rawBoundaries: number[][];           // exact (rendering)
  obstacles: number[][];               // [[x1,y1,x2,y2], ...]
  trajectories: Trajectories | null;
  frameRef: MutableRefObject<number>;
  phase: SimPhase;
  modelUrl?: string;
  modelFormat?: "obj" | "glb" | "gltf";
  centerOffset?: [number, number];
  violations?: Violation[];
  highlightedViolationId?: string | null;
  focusTarget?: { x: number; y: number; z: number } | null;
  onFocusComplete?: () => void;
  heatmapData?: DensityHeatmap | null;
  showHeatmap?: boolean;
  onToggleHeatmap?: () => void;
  viewMode?: ViewMode;
}
```

### Canvas Setup
```tsx
<Canvas shadows camera={{ position: [10, 10, 10], fov: 50, near: 0.1, far: 500 }}>
  <color attach="background" args={["#0f0f1a"]} />
  <ambientLight intensity={0.6} />
  <directionalLight position={[5, 10, 5]} intensity={1.0} castShadow />
  <hemisphereLight args={["#334155", "#0f172a", 0.3]} />
  ...
</Canvas>
```

Uses `rawBoundaries` for all rendering (exact wall positions). Falls back to `boundaries` if `rawBoundaries` is empty.

### Render Decision
```
if (hasModel)  → <ModelRenderer url format centerOffset />
else           → <FloorPlane> + <Walls> + <ObstacleWalls>
```

Then always: `<AgentSwarm>`, `<ViolationMarkers>`, `<ViewModeController>`, `<HeatmapOverlay>`, `<CameraFocuser>`, `<BoundaryGrid>`, `<CameraController>`.

---

### Sub-component: `CameraController`

**Purpose**: Zoom-to-fit camera based on boundary extents. Runs once on mount (and when boundaries change).

**Algorithm**:
1. Compute boundary extents: `cx`, `cz`, `span`
2. `dist = (span/2) / tan(fov/2) * 1.2`
3. `camera.position.set(cx + dist*0.35, dist*0.7, cz + dist*0.45)` — angled 3D view
4. `camera.lookAt(cx, 0, cz)`
5. Set `OrbitControls.target` to `(cx, 0, cz)`

**OrbitControls settings**: `enableDamping`, `dampingFactor=0.1`, `maxPolarAngle=Math.PI/2.1`, `minDistance=1`, `maxDistance=200`

---

### Sub-component: `CameraFocuser`

**Purpose**: GSAP animation to fly camera to a violation when user clicks "Focus" in the panel.

**Trigger**: When `target` prop changes (non-null).

**Coordinate mapping**: Backend `[x, y]` → Three.js `[x, 0, -y]`

**Animation**:
1. Compute camera position: `distance=5m`, `elevation=45°` orbit around target
2. Disable `OrbitControls` during animation
3. `gsap.to(camera.position, { duration: 1.5, ease: "power2.inOut" })`
4. `gsap.to(controls.target, { onUpdate: controls.update, onComplete: re-enable + call onComplete })`

---

### Sub-component: `FloorPlane`

Shown only when no 3D model is loaded. Creates `THREE.Shape` from boundary polygon, renders as flat mesh at `y=0.01`.

- Fill: `#2a2a4a` (dark blue-purple), `DoubleSide`
- Outline: `<line>` with `lineBasicMaterial color="#22d3ee"` (cyan)
- Group rotation: `[-Math.PI/2, 0, 0]` (XY plane → XZ floor)

---

### Sub-component: `Walls`

Shown only when no 3D model. `WALL_HEIGHT = 2.5m`, `WALL_THICKNESS = 0.08m`.

For each boundary segment:
1. Compute wall normal
2. Build `THREE.Shape` (thin rectangle offset by ±normal)
3. `ExtrudeGeometry` with `depth = WALL_HEIGHT`

Material: `color="#1e293b"`, `emissive="#0891b2"`, `emissiveIntensity=0.15`, `transparent`, `opacity=0.7`, `DoubleSide`

---

### Sub-component: `ObstacleWalls`

Same as `Walls` but for obstacles `[x1,y1,x2,y2]`. Height = `WALL_HEIGHT * 0.6 = 1.5m`.

Material: `color="#334155"`, `emissive="#06b6d4"`, `emissiveIntensity=0.1`, `transparent`, `opacity=0.55`

---

### Sub-component: `AgentSwarm`

**Purpose**: Renders up to 100 agents as `THREE.InstancedMesh` with lerp interpolation and conflict zone coloring.

**Constants**:
- `LERP_SPEED = 10`
- `MAX_AGENTS = 100`
- `CONFLICT_ZONE_RADIUS_SQ = 4.0` (2m radius, squared)

**Colors**:
- Standard agents: `#3b82f6` (blue)
- Specialist agents: `#eab308` (yellow), emissive glow
- Conflict zone (near violation): `#f97316` (orange)

**Geometries (pre-built, shared)**:
- Standard: `CapsuleGeometry(0.1, 0.8)` — human-sized, translated up by `0.5`
- Specialist: `CapsuleGeometry(0.035, 0.12)` — smaller marker dot

**useFrame loop**:
1. Read `frameRef.current` to get current frame index
2. If frame index changed, update `agentsRef.current` from trajectories
3. Detect jump (>2 frames) → clear `displayPosRef` for instant snap
4. Partition agents by type into `stdIds` and `specIds`
5. For each agent: lerp `displayPosRef[id]` toward target position with `t = 1 - exp(-LERP_SPEED * delta)`
6. Set matrix via `tempMatrix.makeTranslation(nx, 0.05, nz)`
7. Determine color: `inConflict(nx, nz)` checks squared distance to all violation XZ coords
8. `instanceMatrix.needsUpdate = true`, `instanceColor.needsUpdate = true`

**Conflict detection**: squared distance check against pre-computed `violationXZ` array (no `sqrt`).

---

### Sub-component: `ViewModeController`

**Purpose**: Animate camera between 3D perspective and 2D top-down when `viewMode` prop changes.

**2D mode**: Camera goes directly above center at height `span * 1.2`. Clamps `maxPolarAngle = 0.01` (locks to top-down) after animation.

**3D mode**: Camera returns to angled position. Restores `maxPolarAngle = Math.PI/2.1`.

Both use GSAP with `duration: 1.0, ease: "power2.inOut"`. Kills in-progress tweens before starting a new animation. Disables OrbitControls during animation, re-enables on complete.

---

### Sub-component: `BoundaryGrid`

Draws 1m-spaced grid lines clipped to the building polygon using scanline intersection.

**Adaptive spacing**: `span < 5 → 0.5m`, `span < 20 → 1m`, else `2m`

**Scanline algorithm**:
- Horizontal lines (constant Y): `scanlineIntersections(poly, y)` finds all X crossings, pairs them entry/exit
- Vertical lines (constant X): `scanlineIntersectionsV(poly, x)` finds all Y crossings
- Maps boundary `[x,y]` → Three.js `[x, 0, -y]`

Result: `Float32Array` of line segment vertex pairs fed into `<lineSegments>`.

Color: `#333333` (dark gray), position `y=0.005` (just above floor).

---

### Sub-component: `HeatmapOverlay`

**Purpose**: Real-time density heatmap as a `THREE.DataTexture` placed on the floor.

**Color scale**:
- `val < 0.5`: blue → yellow (lerp)
- `val >= 0.5`: yellow → red (lerp)
- `alpha = 0` when `val <= 0.01` (transparent for empty cells)

**Texture**: `Uint8Array` of RGBA data, `rows × cols × 4`. Row index flipped (`rows-1-r`) for OpenGL origin.

**Filters**: `LinearFilter` for smooth interpolation. `depthWrite=false`, `transparent`, `opacity=0.6`, `DoubleSide`.

**Placement**: Positioned at center of heatmap bounds, rotated `[-Math.PI/2, 0, 0]` (flat on floor).

---

### HTML Overlay (outside Canvas)

**Heatmap toggle button** (top-right): Shown when `heatmapData` available. Cyan border when active, zinc when inactive. Icon: `<Flame>`.

**Heatmap legend** (bottom-right above controls): Color gradient bar (`blue → yellow → red`), labels "Low / High".

**Loading overlay** (full-screen): Shown when `phase === "simulating" || "uploading"`. Semi-transparent black backdrop + `<Loader2 className="animate-spin text-cyan-400">`. Text: "Calculating Physics…" or "Processing Model…".

---

## `src/components/Controls.tsx`

Bottom-center HUD bar. Fixed at `bottom-6 left-1/2 -translate-x-1/2`.

### Props
```ts
interface ControlsProps {
  phase: SimPhase;
  playing: boolean;
  frame: number;
  totalFrames: number;
  speed: PlaybackSpeed;
  agentCount: number;
  violationCount: number;
  viewMode: ViewMode;
  onUploadClick: () => void;
  onRunSim: () => void;
  onTogglePlay: () => void;
  onSeek: (frame: number) => void;
  onReset: () => void;
  onCycleSpeed: () => void;
  onToggleViewMode: () => void;
}
```

### Derived Booleans
- `canRun = phase === "processing"`
- `canPlay = phase === "completed" && totalFrames > 0`
- `isWorking = phase === "uploading" || phase === "simulating"`

### Time Format
```ts
const formatTime = (f: number) => {
  const secs = f / 10;  // 10fps
  const m = Math.floor(secs / 60);
  const s = (secs % 60).toFixed(1);
  return `${m}:${s.padStart(4, "0")}`;
};
```

### Elements (left to right)
1. **Upload Model** button — `<Upload>` icon, disabled when `isWorking`, shows `<Loader2>` when uploading
2. `div.h-6.w-px.bg-zinc-700` divider
3. **Run Simulation** button — `<Zap>` icon, cyan when `canRun`, shows `<Loader2>` when simulating
4. Divider
5. **Play/Pause** button — `<Play>` / `<Pause>` icon, disabled when `!canPlay`
6. **Speed** button — cycles `1x → 2x → 4x → 1x`, cyan monospace text
7. **Timeline scrubber**: `<input type="range">` `min=0 max=totalFrames-1`, `accent-cyan-500`, width `w-40`. Left label: `formatTime(frame)`, right: `formatTime(totalFrames-1)`
8. Stats (only when `canPlay`): frame counter, agent count (cyan), violation count (red)
9. Divider
10. **2D/3D toggle** — `<Eye>` for 3D, `<Box>` for 2D, disabled when not `canPlay && phase !== "processing"`
11. **Reset** button — `<RotateCcw>` icon

**Phase indicator**: Below the bar, small monospace text showing current phase. Amber when working, green when completed, zinc otherwise.

---

## `src/components/ViolationMonitor.tsx`

Exports two components: `ViolationPanel` (HTML overlay) and `ViolationMarkers` (R3F, inside Canvas).

### Severity Config
```ts
const SEVERITY_COLORS = { critical: "#DC2626", high: "#F59E0B", medium: "#EAB308", low: "#3B82F6" };
const SEVERITY_BG = {
  critical: "border-red-500 bg-red-500/10",
  high: "border-orange-500 bg-orange-500/10",
  medium: "border-yellow-500 bg-yellow-500/10",
  low: "border-blue-500 bg-blue-500/10",
};
const SEVERITY_TEXT = { critical: "text-red-400", high: "text-orange-400", medium: "text-yellow-400", low: "text-blue-400" };
```

### AIRecommendation Interface
```ts
interface AIRecommendation {
  analysis: string;
  solution: string;
  implementation_steps: string[];
  complexity: string;          // "low" | "medium" | "high"
  estimated_cost_lkr: string;  // Sri Lankan Rupees
  regulation_reference: string;
  alternative_solutions: string[];
  _confidence?: number;        // 0-1 score from validator
  _is_fallback?: boolean;      // true if Gemini unavailable
  _cost_overridden?: boolean;  // true if cost came from knowledge base
}
```

### `ConfidenceBadge`
Shows confidence percentage if `_confidence` is set. Color: green ≥80%, yellow ≥60%, orange <60%. Shows "Fallback · No AI" badge if `_is_fallback`.

### `AIRecommendationCard`
Framer Motion expand: `initial={{ height: 0, opacity: 0 }}`. Sections:
1. Header: `<Sparkles>` + "AI Recommendation" label + `<ConfidenceBadge>`
2. Analysis paragraph
3. Solution paragraph
4. Implementation steps: bulleted list with `<CheckCircle2>` icons. **Always uses `rec.implementation_steps ?? []`** to guard crash.
5. Bottom row: complexity chip (`COMPLEXITY_COLORS`), cost in LKR (with "(kb estimate)" suffix if `_cost_overridden`), regulation reference (truncated `max-w-[160px]`)
6. Alternative solutions list

### `ViolationCard`
State: `aiRec`, `aiLoading`, `aiError`, `expanded`.

**AI button behavior**:
- First click → fetch `POST /api/ai-consultant` with `{ violation_id, building_context: {} }`
- Response: `data.status === "success" && data.ai_recommendation` → set `aiRec`; or `data.fallback_recommendation` → use fallback
- Subsequent clicks → toggle `expanded`
- Loading: spinner with "Generating…" text
- Loaded: chevron up/down + "Show/Hide AI Recommendation"
- Unloaded: `<Sparkles>` + "Get AI Recommendation"

**Card content**:
- Header: violation type icon + type label (formatted) + severity badge + **Focus** button (`<Focus>` icon → `onFocusViolation(violation)`)
- Description text
- Measured vs Required values (formatted by type: `ramp_gradient` → `%`, `bottleneck` → `p/m²`, else `m`)
- Regulation citation in italic zinc-600
- AI button (full width, purple border/bg)
- Error text if `aiError`
- `<AnimatePresence>` wrapping `<AIRecommendationCard>` for mount/unmount animation

### `ViolationPanel`
State: `panelOpen: boolean`.

**Floating trigger button** (`absolute bottom-24 right-4 z-20`):
- Loading: spinner
- Pass: `<ShieldCheck className="text-green-400">`
- Fail: `<ShieldAlert className="text-red-400">`
- Shows violation count badge (red circle) when `totalViolations > 0`

**Sliding panel** (Framer Motion spring, slides from right):
- `initial={{ x: 400 }}` → `animate={{ x: 0 }}`
- Width: `w-[380px]`, full height, `z-30`, dark glass bg
- **Header**: "Compliance Report" + close `<X>` button
- **Score section**: standard name, building type, score badge (green or red) with pass/fail status + percentage. Severity summary chips below.
- **Violation list**: scrollable `overflow-y-auto`, each rendered as `<ViolationCard>`
- Empty state: "Run a simulation to generate compliance report"
- Loading state: spinner + "Running audit…"

### `ViolationMarkers` (R3F)

**`ViolationCone`**: `<sphereGeometry args={[0.08, 12, 12]}>` at position `[x, 1.8, -y]`.
- `useFrame`: bobs `y = 1.8 + sin(t*2)*0.06`
- When highlighted: scale pulse `1.0 + sin(t*4)*0.3`
- Material: `emissive={color}`, intensity 0.6 (normal) or 1.0 (highlighted)

**`PulsingRing`**: `<ringGeometry args={[0.12, 0.18, 32]}>` at `[x, 1.8, -y]`, rotation `[-Math.PI/2, 0, 0]` (flat).
- `useFrame`: `pulse = 1.0 + |sin(t*1.5)|`
- Scale: `(pulse, pulse, 1)` — expands outward
- Opacity: `0.6 * (1 - (pulse - 1.0))` — fades as it expands

Each violation renders one `ViolationCone` + one `PulsingRing` in a `<group key={v.id}>`.

---

## `src/components/AnalyticsDashboard.tsx`

### Props
```ts
{
  analyticsData: AnalyticsData | null;
  complianceReport: ComplianceReport | null;
  loading: boolean;
  onRequestAnalytics: () => void;
}
```

### Layout
Floating button bottom-left (`absolute bottom-24 left-4`). Sliding panel from left (Framer Motion, same spring config as ViolationPanel but `initial={{ x: -400 }}`).

### `MetricCard`
Small card `rounded-lg border border-zinc-800 bg-zinc-900/50 p-3`. Icon + label row, large value with unit. Optional status dot (green/yellow/red).

### `EfficiencyGauge`
SVG semi-circle arc gauge. 180° sweep from left to right.
- Background arc: `stroke="#27272a"`, strokeWidth 8
- Fill arc: color by score (`<60% red`, `60-80% yellow`, `≥80% green`)
- `describeArc(cx, cy, r, startAngle, endAngle)` builds SVG arc path via `A` command
- Center text: score percentage + "Efficiency" label

### Chart Tooltip Style
All charts use consistent tooltip: `background: "#18181b"`, `border: "1px solid #3f3f46"`, `borderRadius: "6px"`, `fontSize: 11`.

### `buildViolationBarData`
Aggregates `report.violations` by type, returns `{ name, count, type }[]`.

### `buildRadarData`
5 categories: Corridor Width, Door Width, Turning Space, Ramp Gradient, Flow Capacity.
- Each category score: `100 - sum(penalty for each violation of that type)`
- Penalties: critical=25, high=15, medium=8, low=3
- Flow Capacity = `efficiency * 100`

### Sections in panel (scrollable)

1. **2×2 Metric Cards**: Avg Velocity (cyan), Congestion % (red/yellow/green based on thresholds), Efficiency % (green/yellow/red), Avg Flow Rate (blue)

2. **Compliance Radar** (only if `complianceReport`): `<RadarChart>` 200px height, `stroke="#06b6d4"`, `fill="#06b6d4"` at 30% opacity

3. **Velocity Timeline**: `<LineChart>` 120px, line `stroke="#06b6d4"`, reference line at `y=0.2` (danger threshold, red dashed)

4. **Violation Distribution**: Horizontal `<BarChart>` 120px, each bar colored by violation type, category labels on Y axis

5. **Congestion Timeline**: `<AreaChart>` 120px, amber area fill with gradient (40% → 5% opacity)

6. **Efficiency Gauge**: SVG arc gauge

7. **Flow Rate**: `<LineChart>` 120px, emerald line `stroke="#10B981"`, dots enabled (`r=3`), yellow dashed reference at avg flow rate

### Bottom Action Bar (pinned)
- **Generate Report**: `POST /api/generate-report` with `{ project_name: "Building Compliance Audit" }`. Response has `download_url`.
- **Download PDF**: Anchor link to `${API_URL}${downloadUrl}`, opens in new tab.

### Auto-fetch logic
When panel opens and `analyticsData` is null and `loading` is false → calls `onRequestAnalytics()`.

---

## `src/app/page.tsx` — Main Orchestrator

### State Summary
```ts
const [backendOk, setBackendOk] = useState(false);
const [phase, setPhase] = useState<SimPhase>("idle");
const [error, setError] = useState<string | null>(null);
const [geometry, setGeometry] = useState<GeometryData | null>(null);
const [trajectories, setTrajectories] = useState<Trajectories | null>(null);
const [viewMode, setViewMode] = useState<ViewMode>("3d");
const [buildingType, setBuildingType] = useState("residential");
const [complianceReport, setComplianceReport] = useState<ComplianceReport | null>(null);
const [complianceLoading, setComplianceLoading] = useState(false);
const [highlightedViolationId, setHighlightedViolationId] = useState<string | null>(null);
const [focusTarget, setFocusTarget] = useState<{ x: number; y: number; z: number } | null>(null);
const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
const [analyticsLoading, setAnalyticsLoading] = useState(false);
const [showHeatmap, setShowHeatmap] = useState(false);
```

Plus playback from `usePlayback({ trajectories })`.

### API Endpoints Used
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Backend liveness check on mount |
| POST | `/api/process-model` | Upload `.obj/.glb/.gltf` → GeometryData |
| POST | `/api/start-simulation` | Start simulation with boundaries + obstacles |
| GET | `/api/get-trajectories` | Poll for Trajectories (200ms interval) |
| GET | `/api/compliance/report` | Poll for ComplianceReport (500ms interval) |
| POST | `/api/compliance/init` | Set building type |
| GET | `/api/analytics` | Fetch AnalyticsData |
| POST | `/api/ai-consultant` | Get AI recommendation per violation |
| POST | `/api/generate-report` | Generate PDF report |

### Health Check
On mount: `fetch("/api/health")` → check `d.status === "ok"` → `setBackendOk(true)`.

### `handleUploadComplete`
- Prepends `API_URL` to `data.modelUrl` (relative path from backend)
- Sets geometry, resets trajectories and playback
- Sets `phase = "processing"`
- Resets compliance state

### `handleRunSim`
1. `setPhase("simulating")`, `setComplianceLoading(true)`
2. `POST /api/start-simulation` with `{ boundaries, obstacles }`
3. Poll `GET /api/get-trajectories` every 1000ms until `status !== "running"`
4. Set trajectories, `scrubTo(0)`, `setPlaying(true)` (auto-start), `setPhase("completed")`
5. Concurrently: poll `GET /api/compliance/report` every 500ms
6. Set compliance report when done
7. Auto-call `handleRequestAnalytics()`
8. On any error: `setError(message)`, `setPhase("processing")` (allow retry)

### `handleBuildingTypeChange`
Updates `buildingType` state + fires `POST /api/compliance/init` with `{ building_type }` (non-critical, errors swallowed).

### `handleFocusViolation`
Sets `highlightedViolationId = violation.id`, `focusTarget = violation.coordinate`.

### `handleFocusComplete`
Clears `focusTarget`. After 3 seconds, clears `highlightedViolationId` (keeps cone pulsing briefly).

### `handleReset`
Resets all state to defaults: geometry, trajectories, playback, phase, error, compliance, analytics, heatmap, viewMode.

### Layout
```
<div className="relative h-screen w-screen overflow-hidden bg-zinc-950">
```

**When `geometry === null`** (idle / initial upload):
- Centered landing: `<h1>Archion Sim</h1>` + backend status dot + `<ModelUpload>`

**When `geometry !== null`** (any phase after upload):
- Full-screen `<SimViewer>` as background
- HUD overlays:
  - Top-left: "ARCHION SIM" label + boundary count + agent count
  - Top-right (phase=processing only): building type `<select>` dropdown
  - Hidden `<input type="file">` (triggered by Controls "Upload Model" button)
  - Error toast (top-right, red, shown when `error !== null`, disappears when another upload starts)
  - When `phase === "completed"`: `<ViolationPanel>` + `<AnalyticsDashboard>`
  - Always: `<Controls>` bar

### `SimViewer` lazy load
```ts
const SimViewer = dynamic(() => import("@/components/SimViewer"), { ssr: false });
```
Prevents Three.js SSR crash.

### Building Type Options
`residential`, `public_buildings`, `hospital`, `educational`, `commercial`, `industrial`

### Agent Count Derived
```ts
const agentCount = useMemo(() => {
  if (!trajectories) return 0;
  const firstFrame = trajectories["0"];
  return firstFrame ? Object.keys(firstFrame).length : 0;
}, [trajectories]);
```

---

## Coordinate System

The backend uses a 2D coordinate system `[x, y]` where `y` increases upward. Three.js uses Y-up with Z as depth. The mapping is:

```
Backend 2D [x, y]  →  Three.js [x, 0, -y]
```

This negation of Y to Z is applied consistently in:
- `CameraController`: `cz = -(min_y + max_y) / 2`
- `FloorPlane`: `group rotation={[-Math.PI/2, 0, 0]}`
- `AgentSwarm`: `targetZ = -agent.pos[1]`
- `ViolationCone` / `PulsingRing`: `targetZ = -violation.coordinate.y`
- `HeatmapOverlay`: `centerZ = -(min_y + max_y) / 2`
- `BoundaryGrid`: `verts.push(x, 0, -y, ...)`

---

## Key Design Decisions

### Why `frameRef` instead of state for playback
R3F's `useFrame` runs 60fps inside the WebGL render loop. Reading React state would cause re-renders every frame. `frameRef.current` is read directly in `useFrame` with zero React overhead. `currentFrame` state is updated separately to drive only the scrubber UI.

### Why `InstancedMesh` for agents
`InstancedMesh` renders all agents in a single WebGL draw call. With 100 agents, this is critical — separate meshes would cause 100 draw calls per frame.

### Why `rawBoundaries` vs `boundaries`
The backend buffers boundary points inward for pathfinding (agents can't walk through walls). `rawBoundaries` are the exact architectural coordinates extracted from the 3D model, used for rendering the floor plane and wall geometry. Using `rawBoundaries` for rendering means walls appear in the correct position matching the 3D model.

### Why `dynamic(() => ..., { ssr: false })`
Three.js accesses `window`, `document`, and WebGL APIs that don't exist in Node.js. Without `ssr: false`, Next.js would crash during server-side rendering.

### React Strict Mode double-effect fix
In development, React Strict Mode intentionally runs effects twice. `GltfModel.useEffect` calls `scene.position.set(0,0,0)` before `new THREE.Box3().setFromObject(root)` to ensure the bounding box is always computed from the origin, not from an already-translated position.

---

## API Data Shapes (for reference)

### `POST /api/process-model` → `GeometryData`
```json
{
  "boundaries": [[x,y], ...],
  "rawBoundaries": [[x,y], ...],
  "obstacles": [[x1,y1,x2,y2], ...],
  "centerOffset": [cx, cy],
  "floorArea": 250.5,
  "modelUrl": "/static/uploads/model.glb",
  "modelFormat": "glb"
}
```

### `GET /api/get-trajectories` → `Trajectories`
```json
{
  "status": "done",
  "0": { "agent_0": { "pos": [x,y], "type": "standard" }, ... },
  "1": { ... },
  ...
}
```

### `GET /api/compliance/report`
```json
{
  "status": "done",
  "report": {
    "standard": "SLS 1072:2015",
    "building_type": "residential",
    "total_violations": 3,
    "violations": [
      {
        "id": "v1",
        "type": "corridor_width",
        "severity": "critical",
        "coordinate": { "x": 5.2, "y": 3.1, "z": 0 },
        "measured_value": 0.85,
        "required_value": 1.2,
        "description": "Corridor width insufficient for wheelchair access",
        "regulation": "SLS 1072:2015 §4.3.1"
      }
    ],
    "compliance_score": 72,
    "status": "pass",
    "summary": { "critical": 1, "high": 1, "medium": 1, "low": 0 }
  }
}
```

### `POST /api/ai-consultant` → AI Recommendation
```json
{
  "status": "success",
  "ai_recommendation": {
    "analysis": "...",
    "solution": "...",
    "implementation_steps": ["Step 1...", "Step 2..."],
    "complexity": "medium",
    "estimated_cost_lkr": "50,000 - 150,000",
    "regulation_reference": "SLS 1072:2015 §4.3.1",
    "alternative_solutions": ["Option A...", "Option B..."],
    "_confidence": 0.87,
    "_is_fallback": false,
    "_cost_overridden": false
  }
}
```

### `GET /api/analytics`
```json
{
  "status": "done",
  "data": {
    "flow_rate": [{ "time_sec": 0, "agents_per_minute": 12.5 }, ...],
    "congestion_index": { "percentage": 18.3, "slow_threshold_ms": 500 },
    "efficiency_score": { "average": 0.76, "per_agent": [...] },
    "density_heatmap": {
      "grid": [[0.1, 0.4, ...], ...],
      "bounds": { "min_x": 0, "min_y": 0, "max_x": 20, "max_y": 15 },
      "resolution": 0.5,
      "shape": [30, 40],
      "max_density": 3.2
    },
    "congestion_timeline": [{ "time_sec": 0, "congestion_pct": 12.1 }, ...],
    "velocity_timeline": [{ "time_sec": 0, "avg_velocity_ms": 1.35 }, ...],
    "summary": {
      "total_agents": 50,
      "simulation_duration_sec": 120,
      "avg_velocity_ms": 1.28,
      "peak_congestion_pct": 34.5,
      "total_distance_m": 4820.3,
      "floor_area_sqm": 250.5
    }
  }
}
```
