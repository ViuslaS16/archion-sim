# Archion Sim — Complete Technical Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [How It Works — End-to-End Pipeline](#4-how-it-works--end-to-end-pipeline)
5. [Module 1: 3D Model Processing & Geometry Extraction](#5-module-1-3d-model-processing--geometry-extraction)
6. [Module 2: Pedestrian Simulation Engine](#6-module-2-pedestrian-simulation-engine)
7. [Module 3: Compliance Violation Detection](#7-module-3-compliance-violation-detection)
8. [Module 4: Analytics Engine](#8-module-4-analytics-engine)
9. [Module 5: AI Recommendation System](#9-module-5-ai-recommendation-system)
10. [Module 6: 3D Visualization & Playback](#10-module-6-3d-visualization--playback)
11. [Module 7: PDF Report Generation](#11-module-7-pdf-report-generation)
12. [API Reference](#12-api-reference)
13. [Data Flow Diagrams](#13-data-flow-diagrams)
14. [File Structure](#14-file-structure)

---

## 1. Overview

Archion Sim is an AI-powered building compliance simulation and analysis platform. It takes a 3D architectural model (OBJ/GLB/glTF), extracts its floor plan geometry, simulates pedestrian movement inside the building, detects regulatory compliance violations against Sri Lankan Planning & Development Regulations, generates AI-powered remediation recommendations using Google Gemini, and produces professional PDF audit reports.

### Core Capabilities

- **3D Model Processing**: Load OBJ/GLB/glTF models, extract floor boundaries using concave hull, detect interior walls via cross-section slicing
- **Pedestrian Simulation**: Agent-based simulation with heading-persistent random walks, wall collision avoidance, and exit-biased navigation
- **Compliance Checking**: Automated detection of corridor width, door width, turning space, ramp gradient, and bottleneck violations
- **AI Recommendations**: Google Gemini 2.0 Flash with chain-of-thought prompting, domain knowledge base, and severity-aware analysis depth
- **Real-time 3D Visualization**: InstancedMesh rendering of 50+ agents, violation markers with pulsing rings, density heatmap overlay, 2D/3D camera transitions
- **Professional Reporting**: 11-page PDF audit report with embedded charts, radar diagrams, AI recommendations, and appendix

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 16)                     │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ ModelUp  │  │ SimView  │  │ Controls │  │ ViolationPanel │  │
│  │  load    │  │  er (R3F)│  │ (HUD)    │  │ (Compliance)   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬───────┘  │
│       │              │              │                  │          │
│  ┌────┴──────────────┴──────────────┴──────────────────┴───────┐ │
│  │                     page.tsx (State Hub)                      │ │
│  │  geometry | trajectories | compliance | analytics | playback │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                              │ HTTP / fetch                       │
└──────────────────────────────┼───────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│                        BACKEND (FastAPI)                          │
│                              │                                    │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │                      main.py (API Router)                   │  │
│  └───┬──────────┬──────────┬──────────┬──────────┬───────────┘  │
│      │          │          │          │          │               │
│  ┌───┴───┐  ┌──┴───┐  ┌──┴───┐  ┌──┴───┐  ┌──┴────────┐     │
│  │Geometry│  │ Sim  │  │Comply│  │Analy │  │AI Consult │     │
│  │Extract │  │Engine│  │Checker│  │tics  │  │(Gemini)   │     │
│  └────────┘  └──────┘  └──────┘  └──────┘  └───────────┘     │
│                                                                   │
│  External: trimesh, shapely, scipy, numpy, matplotlib, reportlab │
│  External: Google Gemini 2.0 Flash API                           │
└───────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

### Frontend

| Technology | Version | Purpose |
|---|---|---|
| Next.js | 16.1.6 | React framework with SSR, dynamic imports |
| React | 19.2.3 | UI component library |
| TypeScript | 5.x | Type safety |
| Three.js | 0.182 | 3D rendering engine |
| @react-three/fiber | 9.5 | React renderer for Three.js |
| @react-three/drei | 10.7 | Three.js utility components (OrbitControls) |
| GSAP | 3.14 | Camera animation (focus, 2D/3D transitions) |
| Framer Motion | 12.34 | UI panel animations (slide-in panels) |
| Recharts | 3.7 | Data visualization charts (line, bar, area, radar) |
| Lucide React | 0.569 | Icon library |
| Tailwind CSS | 4.x | Utility-first CSS styling |

### Backend

| Technology | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| FastAPI | Async web framework with automatic OpenAPI docs |
| Trimesh | 3D mesh loading and cross-section slicing |
| Shapely | 2D computational geometry (polygons, buffers, containment) |
| NumPy | Numerical computation (trajectories, heatmaps) |
| SciPy | Gaussian filtering (heatmaps), KDTree (ramp gradient detection) |
| Matplotlib | Chart generation for PDF reports |
| ReportLab | PDF document generation (Platypus layout engine) |
| Google Generative AI | Gemini 2.0 Flash for AI compliance recommendations |
| python-dotenv | Environment variable management |

---

## 4. How It Works — End-to-End Pipeline

### Step-by-Step Flow

```
User uploads .glb file
       │
       ▼
┌──────────────────────┐
│ 1. GEOMETRY EXTRACTION│  backend/core/geometry.py
│                        │
│  Load mesh (trimesh)   │
│  Normalize Y→Z up axis │
│  Floor normalize (Z=0) │
│  Extract floor vertices│
│  Concave hull boundary │
│  Center coordinates    │
│  Slice walls at 1.5m   │
│  Buffer for navigation │
└──────────┬─────────────┘
           │ GeometryData: boundaries, obstacles, modelUrl
           ▼
┌──────────────────────┐
│ 2. USER SELECTS       │  Building type (residential, hospital, etc.)
│    BUILDING TYPE      │  Sets compliance regulation thresholds
└──────────┬─────────────┘
           │
           ▼
┌──────────────────────┐
│ 3. SIMULATION         │  backend/sim/engine.py
│                        │
│  Build walkable polygon│
│  Subtract wall buffers │
│  Spawn agents inside   │
│  600 frames @ 10Hz     │
│  Heading-persistent    │
│  random walk physics   │
│  Wall bounce detection │
│  Exit-biased steering  │
└──────────┬─────────────┘
           │ Trajectories: {frame: {agent: {pos, type}}}
           ▼
┌──────────────────────┐
│ 4. COMPLIANCE AUDIT   │  backend/core/compliance.py
│                        │
│  Check corridor widths │
│  Check door widths     │
│  Check turning spaces  │
│  Check ramp gradients  │
│  Check bottlenecks     │
│  Score computation     │
│  Spatial deduplication │
└──────────┬─────────────┘
           │ ComplianceReport: violations, score, status
           ▼
┌──────────────────────┐
│ 5. ANALYTICS           │  backend/core/analytics.py
│                        │
│  Velocity timeline     │
│  Congestion index      │
│  Flow rate calculation │
│  Path efficiency       │
│  Density heatmap       │
└──────────┬─────────────┘
           │ AnalyticsData: metrics, charts, heatmap
           ▼
┌──────────────────────┐
│ 6. 3D VISUALIZATION   │  frontend/src/components/SimViewer.tsx
│                        │
│  InstancedMesh agents  │
│  Violation markers     │
│  Heatmap overlay       │
│  Playback controls     │
│  2D/3D camera toggle   │
└──────────┬─────────────┘
           │
           ▼
┌──────────────────────┐
│ 7. AI RECOMMENDATIONS │  backend/core/ai_consultant.py
│    (On-demand)         │
│                        │
│  Chain-of-thought      │
│  Gemini 2.0 Flash      │
│  Domain knowledge base │
│  Cost estimation (LKR) │
│  Implementation steps  │
└──────────┬─────────────┘
           │
           ▼
┌──────────────────────┐
│ 8. PDF REPORT          │  backend/core/report_gen.py
│    (On-demand)         │
│                        │
│  11-page professional  │
│  audit report          │
│  Embedded charts       │
│  Radar/pie/bar charts  │
│  AI recommendations    │
└────────────────────────┘
```

---

## 5. Module 1: 3D Model Processing & Geometry Extraction

**File**: `backend/core/geometry.py`

### How the 3D Model is Processed

#### 1. Mesh Loading
```python
mesh = trimesh.load(file_path)
```
- Supports OBJ, GLB, and glTF formats
- If the file is a Scene (multiple meshes), all meshes are concatenated into one
- Validated to ensure it's a proper `Trimesh` object

#### 2. Axis Normalization
- GLB/glTF files use Y-up convention; the system uses Z-up
- The mesh is rotated 90 degrees around the X-axis: `rotation_matrix(π/2, [1,0,0])`
- For OBJ files, a heuristic checks if the Y-extent is unusually small compared to X and Z (indicating Y-up)

#### 3. Floor Normalization
- The mesh is translated vertically so the lowest Z-coordinate sits at Z=0
- This ensures the floor plane is at ground level for all subsequent calculations

#### 4. Floor Boundary Extraction
```python
floor_vertices = mesh.vertices[mesh.vertices[:, 2] < 1.0]  # vertices within 1m of floor
points_2d = floor_vertices[:, [0, 1]]                       # project to XY plane
exterior = concave_hull(MultiPoint(points_2d), ratio=0.3)   # tight concave hull
```
- Collects all vertices within 1 meter of floor level
- Projects them to 2D (X, Y plane)
- Computes a **concave hull** (ratio=0.3) to accurately capture L-shaped, U-shaped, or irregular floor plans
- Falls back to convex hull for degenerate cases

#### 5. Coordinate Centering
- The centroid of the bounding box is computed: `cx = (minx + maxx) / 2`
- All coordinates are shifted so the building center is at origin (0, 0)
- This `centerOffset` is sent to the frontend so the 3D model can be repositioned to match

#### 6. Navigation Boundary (Buffered)
```python
buffered_exterior = exterior.buffer(-0.3)  # 0.3m inward buffer
```
- The raw boundary is shrunk by 0.3m using Shapely's `buffer(-0.3)`
- This creates the "walkable area" — agents stay 0.3m away from walls
- If the buffer makes the polygon empty (very narrow building), it falls back to the raw boundary

#### 7. Interior Wall Extraction
```python
section = mesh.section(plane_origin=[0, 0, 1.5], plane_normal=[0, 0, 1])
```
- The mesh is cross-sectioned at Z=1.5m (typical door height)
- This reveals interior wall segments that wouldn't appear at floor level
- Each wall segment is stored as `[x1, y1, x2, y2]`
- Segments shorter than 0.3m are filtered out (noise)

### Output: `ExtractionResult`
```python
{
    "boundaries": [[x, y], ...],        # buffered (for simulation navigation)
    "rawBoundaries": [[x, y], ...],     # exact (for 3D rendering alignment)
    "obstacles": [[x1,y1,x2,y2], ...],  # interior wall segments
    "centerOffset": [cx, cy],           # translation applied to center building
    "floorArea": 125.5,                 # m² computed from polygon area
    "meshVertices": [...]               # centered vertices for ramp detection
}
```

---

## 6. Module 2: Pedestrian Simulation Engine

**File**: `backend/sim/engine.py`

### How Agents Move

The simulation generates **600 frames** (60 seconds at 10 Hz) of pre-computed trajectories. Each agent has a persistent heading that changes smoothly over time, creating natural-looking walking paths.

#### Simulation Parameters

| Parameter | Value | Description |
|---|---|---|
| `SIM_HZ` | 10 | Steps per second |
| `SIM_DURATION` | 60s | Total simulation time |
| `TOTAL_STEPS` | 600 | Total frames generated |
| `STEP_SIZE` | 0.09m | Distance per tick (~0.9 m/s walking speed) |
| `TURN_RATE` | 0.15 rad | Maximum heading change per tick |
| `BIG_TURN_CHANCE` | 2% | Chance of random heading change per tick |
| `EXIT_BIAS` | 0.45 | Fraction of step biased toward exit |
| `WALL_MARGIN` | 0.3m | Minimum distance from walls |
| `WALL_THICKNESS` | 0.2m | Buffer around wall segments |

#### Agent Types

| Type | Count | Description |
|---|---|---|
| Standard | 20-50 | Regular pedestrians (blue capsules in 3D) |
| Specialist | 3 | Facility staff/inspectors (yellow capsules with glow) |

#### Movement Physics — Frame-by-Frame

For each frame (every 100ms), every agent:

**1. Heading Update (Smooth Turning)**
```python
# 2% chance: completely random new heading (simulates decision to go somewhere else)
if random() < 0.02:
    heading = uniform(0, 2π)
else:
    # Small smooth turn: ±0.15 radians max
    heading += uniform(-0.15, 0.15)
```

**2. Exit Bias (Optional)**
If an exit position is set, the heading is steered toward it:
```python
to_exit = atan2(exit_y - y, exit_x - x)
angular_diff = (to_exit - heading + π) % (2π) - π
heading += angular_diff * 0.45  # 45% bias toward exit
```

**3. Speed Variation**
```python
speed = 0.09 * uniform(0.85, 1.15)  # ±15% variation per tick
```
This produces natural speed variation — people don't walk at constant speed.

**4. Position Update**
```python
dx = cos(heading) * speed
dy = sin(heading) * speed
new_x, new_y = x + dx, y + dy
```

**5. Wall Collision & Bounce**
```python
if walkable_area.contains(Point(new_x, new_y)):
    # Move to new position
    position = [new_x, new_y]
else:
    # Hit a wall — reverse heading with random jitter
    heading = heading + π + uniform(-0.5, 0.5)
    # Try one step in new direction
    new_x2 = x + cos(heading) * speed
    new_y2 = y + sin(heading) * speed
    if walkable_area.contains(Point(new_x2, new_y2)):
        position = [new_x2, new_y2]
    # else: stay in current position this tick
```

#### Walkable Area Construction

```python
# Start with building boundary, shrink by 0.3m
walk_area = boundary_polygon.buffer(-0.3)

# Subtract interior walls (each buffered to 0.2m thickness)
for wall_segment in obstacles:
    line = LineString([(x1,y1), (x2,y2)])
    wall_buffer = line.buffer(0.2)
    walk_area = walk_area.difference(wall_buffer)

# If result is MultiPolygon (walls split the space), keep largest piece
if isinstance(walk_area, MultiPolygon):
    walk_area = max(walk_area.geoms, key=lambda p: p.area)
```

#### Agent Spawning
```python
# Rejection sampling: random point inside walkable polygon
def sample_inside(polygon):
    minx, miny, maxx, maxy = polygon.bounds
    for _ in range(10000):
        x = uniform(minx, maxx)
        y = uniform(miny, maxy)
        if polygon.contains(Point(x, y)):
            return x, y
    return polygon.centroid.x, polygon.centroid.y
```

### Output: Trajectories Dict
```json
{
  "0": {
    "0": {"pos": [2.3456, -1.2345], "type": "standard"},
    "1": {"pos": [0.1234, 3.4567], "type": "specialist"},
    ...
  },
  "1": { ... },
  ...
  "599": { ... }
}
```

---

## 7. Module 3: Compliance Violation Detection

**File**: `backend/core/compliance.py`

### How Violations Are Detected

The compliance checker runs 5 independent checks against regulations loaded from `regulations.json`. Each check produces zero or more `Violation` objects.

#### Regulations Database

Loaded from `backend/core/regulations.json`, which defines per-building-type thresholds:

| Building Type | Min Corridor | Min Door | Turning Space | Max Ramp Gradient | Max Density |
|---|---|---|---|---|---|
| Residential | 1.2m | 0.75m | 1.5m | 8.3% (1:12) | 1.5 p/m² |
| Public | 1.5m | 0.9m | 1.5m | 8.3% (1:12) | 2.0 p/m² |
| Hospital | 2.4m | 1.2m | 2.1m | 5.0% (1:20) | 1.0 p/m² |
| Educational | 1.8m | 0.9m | 1.5m | 8.3% (1:12) | 1.5 p/m² |
| Commercial | 1.5m | 0.9m | 1.5m | 8.3% (1:12) | 2.0 p/m² |
| Industrial | 1.5m | 0.9m | 1.5m | 8.3% (1:12) | 1.5 p/m² |

### Check 1: Corridor Width

**Detects**: Parallel wall pairs that form corridors narrower than regulation minimum.

**Algorithm**:
1. Compute direction vector, midpoint, and length for each wall segment
2. For every pair of wall segments (i, j):
   - Check **parallelism**: cross product of direction vectors must be < 0.3 (nearly parallel)
   - Compute **perpendicular distance** between the two lines
   - Check **overlap**: project segment j onto segment i's axis; overlap must be > 0.5m
   - If perpendicular distance < minimum corridor width → **violation**
3. Also checks if the entire polygon is too narrow using `polygon.buffer(-min_width/2)`

**Severity Assignment**:
- `critical`: corridor < 50% of required width
- `high`: corridor < 75% of required width
- `medium`: corridor < 100% of required width

### Check 2: Door Width

**Detects**: Wall gaps (doors) narrower than regulation minimum.

**Algorithm**:
1. Collect all wall segment endpoints
2. For every pair of endpoints from **different** wall segments:
   - Compute gap distance (0.3m–2.5m range = potential door)
   - Verify midpoint is inside the building boundary
   - Check the gap direction is **not collinear** with the wall (dot product < 0.85)
   - If gap < minimum door width → **violation**
3. Spatially deduplicates: doors within 0.5m of each other are merged

### Check 3: Turning Space

**Detects**: Locations where a wheelchair turning circle cannot fit.

**Algorithm**:
1. Build walkable area (polygon minus wall buffers)
2. Collect check points: all wall endpoints (deduplicated to 0.3m radius)
3. For each point inside the boundary:
   - Create a circle of `min_turning_space / 2` radius
   - Test if `walkable.contains(turning_circle)`
   - If the circle doesn't fit → **violation** with `measured = 2 * distance_to_nearest_wall`

### Check 4: Ramp Gradient

**Detects**: Ramps steeper than the maximum allowed gradient.

**Algorithm**:
1. Filter mesh vertices between 0.05m and 2.0m height (ramp candidates)
2. Build KDTree on XY coordinates for fast neighbor queries
3. Sample up to 200 points; for each:
   - Find all neighbors within 1.0m horizontal radius
   - Compute gradient: `|Δz| / √(Δx² + Δy²)` for each neighbor pair
   - If max gradient > `max_ramp_gradient` → mark as steep
4. Cluster steep points within 2.0m of each other
5. Each cluster → one **violation** with the worst gradient

**Severity**:
- `critical`: gradient > 2x the limit
- `high`: gradient > 1.5x the limit
- `medium`: gradient > 1.0x the limit

### Check 5: Bottleneck Detection

**Detects**: Areas where pedestrian density exceeds safe limits during simulation.

**Algorithm**:
1. Divide the building into a 1m x 1m grid
2. For each simulation frame:
   - Count agents in each grid cell
   - Convert to density: `agents / cell_area` (persons/m²)
   - Track cells where density exceeds the maximum (`max_safe_density_persons_per_sqm`)
3. If a cell exceeds density for longer than `bottleneck_duration_threshold_sec` (typically 5s = 50 frames):
   - **Violation** with peak density and duration
4. Only cells whose center is inside the building polygon are considered

### Spatial Deduplication

All violations go through a spatial deduplication pass:
```python
def deduplicate_violations(violations, radius=1.5):
    # For each violation, find all others within 'radius' meters
    # From each cluster, keep only the one with the worst measured_value
```
This prevents 88 corridor violations from being reported when they're all on the same narrow corridor.

### Score Computation

```python
weights = {"critical": 10, "high": 5, "medium": 2, "low": 1}
total_deduction = sum(weight[v.severity] for v in violations)
score = max(0, 100 - total_deduction)
status = "pass" if score >= 70 else "fail"
```

---

## 8. Module 4: Analytics Engine

**File**: `backend/core/analytics.py`

### How Metrics Are Calculated

The analytics engine processes the raw trajectory data into 7 performance metrics.

#### Data Preparation

```python
# Build position array: shape (600, num_agents, 2)
positions = np.zeros((n_frames, n_agents, 2))

# Compute velocities: shape (599, num_agents)
# velocity = distance_between_frames / time_step
deltas = np.diff(positions, axis=0)          # frame-to-frame displacement
velocities = np.linalg.norm(deltas, axis=2) / (1/10)  # divide by 0.1s
```

#### Metric 1: Velocity Timeline

Average velocity of all agents per 1-second bucket (10 frames):
```python
for each 1-second bucket:
    avg_velocity = mean(velocities[start:end])
    # Output: [{time_sec: 0, avg_velocity_ms: 0.82}, ...]
```

#### Metric 2: Congestion Index

Percentage of agent-frames where velocity drops below 0.2 m/s (indicating congestion):
```python
slow_count = np.sum(velocities < 0.2)
congestion_percentage = slow_count / total_measurements * 100
```

#### Metric 3: Flow Rate

Counts agents reaching within 1.0m of the boundary edge per 10-second window:
```python
for each agent:
    distance_to_boundary = polygon.exterior.distance(Point(pos))
    if distance_to_boundary < 1.0:
        mark agent as "exited" at this frame

# Bin exits into 10-second windows → agents per minute
```

#### Metric 4: Path Efficiency

Compares straight-line distance (start→end) vs actual path taken:
```python
ideal = distance(start_position, end_position)
actual = sum(distances between consecutive positions)
efficiency = min(ideal / actual, 1.0)  # 1.0 = perfectly direct path
```

#### Metric 5: Density Heatmap

2D histogram of all agent positions across all frames, smoothed with Gaussian filter:
```python
# Flatten all 600*33 positions into one array
hist, _, _ = np.histogram2d(all_y, all_x, bins=[n_bins_y, n_bins_x])
hist = gaussian_filter(hist, sigma=1.0)    # smooth
grid_normalized = hist / hist.max()        # normalize 0-1
```
Resolution: 0.5m per cell. Output is a 2D grid used for both the 3D heatmap overlay and the PDF report.

#### Metric 6: Congestion Timeline

Congestion percentage per 5-second window (50 frames):
```python
for each 5-second window:
    slow_pct = count(velocities < 0.2) / total * 100
```

#### Metric 7: Summary

Aggregate statistics:
- Total agents, simulation duration
- Average velocity across all frames
- Peak congestion (worst single frame)
- Total distance traveled by all agents combined
- Floor area

---

## 9. Module 5: AI Recommendation System

**File**: `backend/core/ai_consultant.py`

### How AI Suggestions Work

The AI consultant uses **Google Gemini 2.0 Flash** with a sophisticated prompt engineering pipeline to generate architectural compliance recommendations.

#### Architecture

```
Violation Data ──┐
                  │
Knowledge Base ───┼──► Prompt Builder ──► Gemini 2.0 Flash ──► Validator ──► Post-Processor
                  │                            │
Few-shot Examples┘                       JSON Response
Severity Depth ──┘
```

#### 1. System Prompt Construction

The base system prompt establishes Gemini as a "senior Sri Lankan architect with 20+ years experience" and defines a **6-step reasoning framework**:

1. **ANALYZE**: Root cause category, percentage gap computation
2. **ASSESS SAFETY**: Who is affected, failure consequences
3. **DIAGNOSE**: Physical cause, UDA regulation citation
4. **SOLVE**: Primary solution with specific dimensions and materials
5. **ESTIMATE**: Cost in LKR with labor rates (skilled: LKR 5,500/day)
6. **ALTERNATIVES**: 2+ ranked alternatives with cost indications

The system prompt is enriched with building-type-specific regulations from the knowledge base.

#### 2. Domain Knowledge Base

**File**: `backend/core/knowledge_base.py`

Contains structured architectural knowledge:
- **Sri Lankan regulations**: Per building type, per violation type — specific regulation references, context notes
- **Common violations**: Typical causes, cost ranges (LKR), standard solutions for minor/moderate/major deficiencies
- **Safety impact data**: Per violation type — affected populations, failure consequences, impact level
- **Few-shot examples**: Complete input→output examples matched by violation type and severity
- **Time estimates**: Expected remediation timelines by deficiency level

#### 3. Severity-Aware Prompt Depth

Different severities get different analysis depth requirements:

| Severity | Requirements |
|---|---|
| Critical | Detailed safety impact, emergency scenario analysis, interim measures, 6+ implementation steps, 3+ alternatives |
| High | Detailed analysis with specific measurements, 5+ implementation steps |
| Medium | Practical analysis, 4+ implementation steps |
| Low | Concise analysis, 4+ implementation steps |

#### 4. Comparative Analysis

The prompt includes quantified gap analysis:
```
For corridor_width: "Measured 0.8m vs required 1.2m. Deficiency: 0.40m (33.3% below minimum)."
For ramp_gradient: "Measured 0.12 is 1.4x the maximum allowed 0.083."
For bottleneck: "Measured density 3.5 persons/m² is 1.75x the safe limit of 2.0 persons/m²."
```

#### 5. Response Processing Pipeline

```
Raw JSON from Gemini
        │
        ▼
┌─────────────────┐
│ JSON Validation  │  Ensure all 7 required fields exist with correct types
│                  │  Normalize complexity to lowercase
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Post-Processing  │  Cross-reference cost against KB ranges
│                  │  Ensure minimum 4 implementation steps
│                  │  Ensure 2+ alternative solutions
│                  │  Add confidence indicator (0.0-1.0)
└────────┬────────┘
         │
         ▼
    Final Recommendation
```

#### 6. Retry Logic

- Up to 2 retries with exponential backoff (1s, 2s)
- JSON parse failures trigger retry
- All retries exhausted → knowledge-base-grounded fallback recommendation

#### 7. Batch Processing

For PDF report generation, up to 5 violations are processed:
- Sorted by severity (critical first)
- Single model instance reused across all violations
- 60-second hard timeout for entire batch
- Results cached to avoid duplicate API calls

#### 8. Caching

- In-memory cache keyed by violation ID
- Cache persists across requests within the same server session
- Cache cleared when a new simulation starts

---

## 10. Module 6: 3D Visualization & Playback

**File**: `frontend/src/components/SimViewer.tsx`

### Rendering Architecture

The 3D scene is rendered using React Three Fiber (R3F), which wraps Three.js in React components.

#### Canvas Setup
```tsx
<Canvas shadows camera={{ position: [10, 10, 10], fov: 50, near: 0.1, far: 500 }}>
  <color attach="background" args={["#0f0f1a"]} />
  <ambientLight intensity={0.6} />
  <directionalLight position={[5, 10, 5]} intensity={1.0} castShadow />
  <hemisphereLight args={["#334155", "#0f172a", 0.3]} />
```

#### Scene Components

1. **ModelRenderer**: Loads and renders the original 3D model (OBJ/GLB/glTF) using `useGLTF` or `useLoader(OBJLoader)`
2. **FloorPlane**: Fallback flat polygon when no 3D model is loaded (ShapeGeometry from boundary points)
3. **Walls**: Fallback ExtrudeGeometry walls (2.5m height, 0.08m thickness)
4. **BoundaryGrid**: Scanline-clipped grid lines that only appear inside the building polygon
5. **AgentSwarm**: InstancedMesh-based agent rendering (the main performance feature)
6. **ViolationMarkers**: Bobbing spheres + pulsing rings at violation coordinates
7. **HeatmapOverlay**: DataTexture-based density visualization on the floor
8. **ViewModeController**: GSAP-animated camera transitions between 3D and 2D views

### AgentSwarm — InstancedMesh Rendering

Instead of creating individual mesh objects for each agent (which would be 33+ draw calls), the system uses **two InstancedMesh objects** — one for standard agents, one for specialists. This reduces draw calls to just 2.

```tsx
// Pre-built shared geometries (created once, reused for all agents)
const _standardGeo = new THREE.CapsuleGeometry(0.03, 0.1, 4, 8);  // human-shaped
_standardGeo.translate(0, 0.08, 0);  // pivot at feet

const _specialistGeo = new THREE.CapsuleGeometry(0.035, 0.12, 4, 8);
_specialistGeo.translate(0, 0.095, 0);
```

#### Per-Frame Update (inside `useFrame` callback):

```tsx
useFrame((_, delta) => {
  // 1. Read current frame data from trajectory
  const agents = trajectories[frameRef.current];

  // 2. Lerp interpolation (exponential smoothing)
  const t = 1 - Math.exp(-10 * delta);  // ~10fps lerp speed
  for each agent:
    displayPos = prevPos + (targetPos - prevPos) * t;

  // 3. Large seek detection (snap instead of lerp)
  if (Math.abs(currentFrame - lastFrame) > 2):
    displayPos = targetPos;  // instant snap

  // 4. Set instance matrix (position transform)
  tempMatrix.makeTranslation(x, 0.05, z);
  instancedMesh.setMatrixAt(index, tempMatrix);

  // 5. Conflict zone coloring
  for each violation coordinate:
    dx = agentX - violationX;
    dz = agentZ - violationZ;
    if (dx*dx + dz*dz <= 4.0):  // within 2m radius (squared, no sqrt)
      setColorAt(index, orange);
    else:
      setColorAt(index, blue);  // or yellow for specialist

  // 6. Flag buffers for GPU upload
  instancedMesh.instanceMatrix.needsUpdate = true;
  instancedMesh.instanceColor.needsUpdate = true;
});
```

### Playback System

**File**: `frontend/src/hooks/usePlayback.ts`

The playback hook uses `requestAnimationFrame` with a time accumulator pattern for smooth, frame-rate-independent playback:

```tsx
// Time accumulator pattern
const tick = (timestamp) => {
  elapsed = Math.min(timestamp - lastTimestamp, 200);  // clamp for tab backgrounding
  accumulator += elapsed;
  frameInterval = 100 / speed;  // 100ms at 1x, 50ms at 2x, 25ms at 4x

  while (accumulator >= frameInterval) {
    accumulator -= frameInterval;
    frameRef.current += 1;
    if (frameRef.current >= totalFrames) frameRef.current = 0;  // loop
  }

  setCurrentFrame(frameRef.current);
  requestAnimationFrame(tick);
};
```

Speed options: 1x (real-time), 2x (double speed), 4x (fast forward).

### 2D/3D Camera Transitions

**ViewModeController** uses GSAP to animate the camera:

- **3D mode**: Perspective orbit view, `maxPolarAngle = π/2.1` (can't go below floor)
- **2D mode**: Camera directly above center, `maxPolarAngle = 0.01` (locked to top-down)
- Transition: 1.0s GSAP animation on `camera.position` and `controls.target`
- Orbit controls disabled during animation, re-enabled on complete

### Violation Markers

Each violation is rendered as two overlapping objects:

1. **ViolationCone** (actually a sphere): `SphereGeometry(0.08)` at y=0.12
   - Gentle bob animation: `y = 0.12 + sin(t * 2) * 0.03`
   - Color mapped to severity (red/orange/yellow/blue)
   - Scale pulse when highlighted: `1.0 + sin(t * 4) * 0.3`

2. **PulsingRing**: `RingGeometry(0.12, 0.18, 32)` at y=0.03 (floor level)
   - Scale oscillates: `1.0 + |sin(t * 1.5)|`
   - Opacity fades inversely to scale
   - Flat on ground: `rotation=[-π/2, 0, 0]`

---

## 11. Module 7: PDF Report Generation

**File**: `backend/core/report_gen.py`

### Report Structure (11 Pages)

| Page | Title | Content |
|---|---|---|
| 1 | Cover | Project name, compliance score badge, building type, date, floor area |
| 2 | Executive Summary | Score, violation counts by severity, congestion/efficiency metrics, key findings |
| 3 | Building Information | Project details table (type, area, agents, duration, frame rate) |
| 4 | Compliance Analysis | Violation table (type, severity, measured/required, regulation) + bar chart |
| 5 | Compliance Breakdown | Radar chart (5 categories), severity pie chart, category status table |
| 6 | AI Recommendations | Per-violation: severity badge, analysis, solution, steps, complexity, cost, alternatives |
| 7 | Recommendations Summary | Condensed table, priority action items, remediation effort estimates |
| 8 | Performance Metrics | Velocity timeline chart, flow rate chart, metrics table |
| 9 | Density Heatmap | Full-page heatmap image, grid statistics, interpretation guide |
| 10 | Conclusion | Verdict, recommended next steps (6 items), generation timestamp |
| 11 | Appendix | Simulation methodology, standards reference table, severity definitions, disclaimer |

### Chart Generation

Charts are generated using Matplotlib and embedded as PNG images in the PDF:

```python
def _fig_to_image(fig, width=160*mm, height=80*mm):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width, height=height)
```

Charts include:
- **Violations bar chart**: Horizontal bars by type, colored by severity
- **Velocity line chart**: Average velocity over time with congestion threshold line
- **Flow rate line chart**: Agents per minute over time with average reference line
- **Density heatmap**: imshow with jet colormap, bilinear interpolation
- **Compliance radar chart**: 5-axis spider chart (corridor, door, turning, ramp, flow)
- **Severity pie chart**: Distribution of violations by severity level

---

## 12. API Reference

### Base URL: `http://localhost:8000`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check → `{status: "ok"}` |
| POST | `/api/process-model` | Upload 3D model, returns geometry data |
| POST | `/api/compliance/init` | Set building type for compliance checking |
| GET | `/api/compliance/report` | Poll compliance report status |
| POST | `/api/start-simulation` | Start simulation (background thread) |
| GET | `/api/get-trajectories` | Poll trajectory data (or "running" status) |
| GET | `/api/analytics` | Compute/return analytics data |
| POST | `/api/ai-consultant` | Get AI recommendation for a violation |
| POST | `/api/generate-report` | Generate PDF audit report |
| GET | `/api/download-report/{filename}` | Download generated PDF |
| GET | `/api/heatmap-image` | Get heatmap as standalone PNG |

### POST `/api/process-model`

**Request**: `multipart/form-data` with `file` field (.obj, .glb, .gltf)

**Response**:
```json
{
  "boundaries": [[x, y], ...],
  "rawBoundaries": [[x, y], ...],
  "obstacles": [[x1, y1, x2, y2], ...],
  "centerOffset": [cx, cy],
  "floorArea": 125.5,
  "modelUrl": "/static/models/abc123.glb",
  "modelFormat": "glb"
}
```

### POST `/api/start-simulation`

**Request**:
```json
{
  "boundaries": [[x, y], ...],
  "obstacles": [[x1, y1, x2, y2], ...],
  "exit_pos": [x, y],
  "n_standard": 30,
  "n_specialist": 3
}
```

**Response**: `{status: "started"}` — poll `/api/get-trajectories` until done.

### POST `/api/ai-consultant`

**Request**:
```json
{
  "violation_id": "corridor_width_1",
  "building_context": {"building_type": "hospital"}
}
```

**Response**:
```json
{
  "status": "success",
  "violation_id": "corridor_width_1",
  "ai_recommendation": {
    "analysis": "Root cause analysis...",
    "solution": "Widen corridor to 2.4m by...",
    "implementation_steps": ["Step 1: ...", ...],
    "complexity": "medium",
    "estimated_cost_lkr": "150000-300000",
    "regulation_reference": "UDA Section 4.2.1",
    "alternative_solutions": ["Option A...", "Option B..."]
  },
  "timestamp": "2026-02-23T10:30:00Z"
}
```

---

## 13. Data Flow Diagrams

### Simulation Lifecycle

```
idle → uploading → processing → simulating → completed
 │                      │            │            │
 │ Upload Model         │ Model      │ Start      │ Playback
 │ (drag & drop)        │ visible    │ simulation │ + analysis
 │                      │ in 3D     │            │
 └──────────────────────┘            │            │
                                     │            │
                         Select building type     │
                         (residential, hospital)   │
                                                   │
                                         ┌─────────┤
                                         │         │
                                  Compliance    Analytics
                                   Report      Dashboard
                                         │         │
                                         └────┬────┘
                                              │
                                         PDF Report
                                        (on demand)
```

### State Management (page.tsx)

```
                          page.tsx State Hub
                     ┌───────────────────────────────┐
                     │                               │
  geometry ──────────┤  GeometryData | null           │
  trajectories ──────┤  Trajectories | null           │
  phase ─────────────┤  SimPhase (idle→completed)     │
  complianceReport ──┤  ComplianceReport | null       │
  analyticsData ─────┤  AnalyticsData | null          │
  viewMode ──────────┤  "3d" | "2d"                  │
  showHeatmap ───────┤  boolean                       │
  buildingType ──────┤  string                        │
                     │                               │
  usePlayback() ─────┤  isPlaying, currentFrame,      │
                     │  speed, frameRef, controls     │
                     └───────────────────────────────┘
```

---

## 14. File Structure

```
archion-sim/
├── .gitignore
├── AI_RECOMMENDATION_ENGINE.md
├── DOCUMENTATION.md               # This file
├── FRONTEND_COMMIT_PLAN.md
├── SETUP.md
├── backend/
│   ├── .env                       # (Ignored in Git, local environment variables)
│   ├── main.py                    # FastAPI app, all API endpoints
│   ├── schemas.py                 # Pydantic models (ComplianceReport, Violation)
│   ├── core/
│   │   ├── ai_consultant.py       # Gemini AI recommendation engine
│   │   ├── analytics.py           # Performance metrics computation
│   │   ├── chart_generator.py     # Utilities for visual charts
│   │   ├── compliance.py          # Regulatory compliance checking (5 checks)
│   │   ├── geometry.py            # 3D model → 2D floor plan extraction
│   │   ├── knowledge_base.py      # Domain knowledge for AI prompts
│   │   ├── navigation.py          # Pathfinding and navigation graphs
│   │   ├── parameter_extractor.py # Extract building metrics
│   │   ├── regulations.json       # Building regulation thresholds
│   │   ├── report_gen.py          # PDF report generation (11 pages)
│   │   ├── spatial_analyzer.py    # Spatial layout analysis
│   │   └── validator.py           # Data validation models
│   ├── reports/                   # Generated PDF reports
│   ├── sim/
│   │   ├── data/                  # Simulation data storage
│   │   └── engine.py              # Pedestrian simulation engine
│   ├── tests/                     # Backend test configurations
│   └── uploads/                   # Uploaded 3D models (temporary)
├── frontend/
│   ├── package.json               # Node.js dependencies
│   ├── tsconfig.json              # TypeScript configuration
│   ├── public/                    # Static assets
│   └── src/
│       ├── app/
│       │   ├── layout.tsx         # Root layout with ErrorBoundary
│       │   ├── page.tsx           # Main app page (state hub)
│       │   └── globals.css        # Global styles
│       ├── components/
│       │   ├── AnalyticsDashboard.tsx # Charts, metrics, radar, PDF export
│       │   ├── Controls.tsx       # Bottom HUD (play, speed, timeline)
│       │   ├── ErrorBoundary.tsx  # Global error catcher with fallback UI
│       │   ├── ModelRenderer.tsx  # OBJ/GLB/glTF model loader
│       │   ├── ModelUpload.tsx    # Drag-and-drop file upload
│       │   ├── Providers.tsx      # Client-side provider wrapper
│       │   ├── SimViewer.tsx      # 3D Canvas with all R3F components
│       │   └── ViolationMonitor.tsx # Violation markers + panel + AI cards
│       ├── hooks/
│       │   └── usePlayback.ts     # rAF-based playback with speed control
│       ├── lib/
│       │   └── theme.ts           # Brand colors, thresholds, utilities
│       └── types/
│           └── simulation.ts      # All TypeScript interfaces
└── images/                        # General images and assets
```

---

## Appendix: Key Algorithms Summary

| Algorithm | Used In | Purpose |
|---|---|---|
| Concave Hull (ratio=0.3) | Geometry | Accurate floor plan extraction from vertices |
| Cross-section slicing (Z=1.5m) | Geometry | Interior wall detection |
| Shapely buffer/difference | Geometry, Simulation | Walkable area computation |
| Rejection sampling | Simulation | Random agent spawn inside polygon |
| Heading-persistent random walk | Simulation | Natural pedestrian movement |
| Exponential smoothing lerp | SimViewer | Smooth agent animation between frames |
| InstancedMesh | SimViewer | Single draw call for 50+ agents |
| Scanline intersection | SimViewer | Grid lines clipped to building polygon |
| Squared distance (no sqrt) | SimViewer | Fast conflict zone detection |
| Parallel wall detection (cross product) | Compliance | Corridor width measurement |
| KDTree neighborhood query | Compliance | Ramp gradient detection |
| Spatial deduplication (clustering) | Compliance | Merge nearby duplicate violations |
| histogram2d + gaussian_filter | Analytics | Density heatmap generation |
| Chain-of-thought prompting | AI Consultant | Structured reasoning for recommendations |
| Severity-aware depth control | AI Consultant | More detail for critical violations |
| Few-shot examples | AI Consultant | Format and quality guidance for Gemini |
| Response post-processing | AI Consultant | Cross-reference AI output against knowledge base |
| Time accumulator (rAF) | usePlayback | Frame-rate-independent playback at variable speed |
| GSAP tweening | SimViewer | Smooth camera transitions (focus, 2D/3D) |
