# 4-Day Frontend Commit Plan

This plan breaks down the Next.js `frontend` implementation into a logical sequence over 4 days. It ensures that foundational elements are built first, followed by the 3D scene, and finishing with the data overlays and UI integration.

## Day 1: Project Skeleton & Foundation
**Goal:** Set up the Next.js application, styling, and core utilities.

### Commits:
1. **Initialize Next.js & Dependencies:** Create `package.json`, `tsconfig.json`, `next.config.ts`, `eslint.config.mjs`, and `.gitignore`.
2. **Setup Tailwind CSS:** Configure `postcss.config.mjs` and initialize the root styles in `src/app/globals.css`.
3. **Core App Layout:** Build `src/app/layout.tsx` to include fundamental app wrapping and font imports.
4. **Types & Hooks:** 
   - Add `src/types/simulation.ts` to define the interfaces for trajectories, violations, and analytics.
   - Add `src/hooks/usePlayback.ts` to manage the requestAnimationFrame playback state, play/pause logic, and scrubbing.
5. **Basic Components (Non-3D):**
   - Add `src/components/Providers.tsx` and `src/components/ErrorBoundary.tsx`.
   - Add `src/components/ModelUpload.tsx` for handling `.obj`/`.glb` file uploads.

---

## Day 2: 3D Visualization Core
**Goal:** Build the React Three Fiber (R3F) Canvas and model loading capabilities.

### Commits:
1. **Model Loader Integration:** Build `src/components/ModelRenderer.tsx` using `@react-three/drei` and `three/examples/jsm/loaders/OBJLoader`. Implement logic to filter out placeholder materials and align the model's bounding box.
2. **Setup R3F Canvas:** Initialize `src/components/SimViewer.tsx` with `<Canvas>` and basic lighting.
3. **Camera & Scene Navigation:** Add `OrbitControls` and the `CameraController` to automatically scale and center the camera based on the provided boundary coordinates.
4. **Fallback Boundary Rendering:** Add logic to draw the `FloorPlane`, `Walls`, and `ObstacleWalls` within `SimViewer.tsx` when a 3D model isn't uploaded.

---

## Day 3: Simulation Overlay & HUD
**Goal:** Integrate the agent movement rendering and the heads-up display controls.

### Commits:
1. **Agent Swarm Logic (`SimViewer.tsx`):**
   - Implement the `AgentSwarm` component using `THREE.InstancedMesh`.
   - Add lerp-based interpolation between frame timestamps.
   - Implement partitioning for "standard" vs "specialist" agents with distinct colors.
2. **Heatmap & Scenery Grids (`SimViewer.tsx`):**
   - Implement `BoundaryGrid` to draw the 1m spaced pathfinding grid inside the floor polygon.
   - Implement `HeatmapOverlay` generating a real-time `THREE.DataTexture` based on the density grid.
3. **Simulation Controls UI:** Implement `src/components/Controls.tsx` with play/pause, scrub bar, speed multiplier toggles, and view mode toggles.
4. **Main Page Integration (Part 1):** Update `src/app/page.tsx` to tie together the `ModelUpload`, `Controls`, `SimViewer`, and the `usePlayback` hook state.

---

## Day 4: Analytics & Compliance Integration
**Goal:** Implement the graphical data dashboards, 3D violation markers, and the AI consultant UI.

### Commits:
1. **Analytics Dashboard Charts:** 
   - Implement `src/components/AnalyticsDashboard.tsx` utilizing `recharts`.
   - Build the Velocity Timeline, Flow Rate, Congestion Area charts, and the Compliance Radar.
   - Add the SVG circular Efficiency Gauge.
2. **Compliance UI:**
   - Implement `src/components/ViolationMonitor.tsx` to handle the sliding side-panel UI displaying building score and violations.
   - Build the `AIRecommendationCard` with expandable Framer Motion views and "Get AI Recommendation" functionality.
3. **3D Violation Markers (`SimViewer.tsx`):**
   - Implement `ViolationCone` and `PulsingRing` to render at the exact XZ engine coordinates with synchronized R3F useFrame animations.
   - Implement `CameraFocuser` GSAP animations to fly the camera directly to a marker when clicked in the UI.
4. **Final Page Integration:** Finalize `src/app/page.tsx` by polling the `/api/compliance/report` and `/api/analytics` endpoints, passing the fetched payloads into the dashboard and 3D viewers.
