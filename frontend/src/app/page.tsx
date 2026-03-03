"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ModelUpload from "@/components/ModelUpload";
import Controls from "@/components/Controls";
import { ViolationPanel } from "@/components/ViolationMonitor";
import { AnalyticsDashboard } from "@/components/AnalyticsDashboard";
import { usePlayback } from "@/hooks/usePlayback";
import type {
  GeometryData,
  Trajectories,
  SimPhase,
  Violation,
  ComplianceReport,
  AnalyticsData,
  ViewMode,
} from "@/types/simulation";

// Lazy-load SimViewer to avoid SSR issues with Three.js
const SimViewer = dynamic(() => import("@/components/SimViewer"), {
  ssr: false,
});

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  // --- Connection ---
  const [backendOk, setBackendOk] = useState(false);

  // --- Lifecycle ---
  const [phase, setPhase] = useState<SimPhase>("idle");
  const [error, setError] = useState<string | null>(null);

  // --- Data ---
  const [geometry, setGeometry] = useState<GeometryData | null>(null);
  const [trajectories, setTrajectories] = useState<Trajectories | null>(null);

  // --- Playback (rAF-based hook with speed control) ---
  const {
    isPlaying,
    currentFrame,
    totalFrames,
    speed,
    frameRef,
    togglePlay,
    reset: resetPlayback,
    cycleSpeed,
    scrubTo,
    setPlaying,
  } = usePlayback({ trajectories });

  const uploadInputRef = useRef<HTMLInputElement>(null);

  // --- View mode ---
  const [viewMode, setViewMode] = useState<ViewMode>("3d");
  const toggleViewMode = useCallback(() => {
    setViewMode((prev) => (prev === "3d" ? "2d" : "3d"));
  }, []);

  // --- Compliance ---
  const [buildingType, setBuildingType] = useState("residential");
  const [complianceReport, setComplianceReport] =
    useState<ComplianceReport | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [highlightedViolationId, setHighlightedViolationId] = useState<
    string | null
  >(null);
  const [focusTarget, setFocusTarget] = useState<{
    x: number;
    y: number;
    z: number;
  } | null>(null);

  // --- Analytics ---
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(
    null,
  );
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);

  // ----------------------------------------------------------------
  // Health check
  // ----------------------------------------------------------------
  useEffect(() => {
    fetch(`${API_URL}/api/health`)
      .then((r) => r.json())
      .then((d) => {
        if (d.status === "ok") setBackendOk(true);
      })
      .catch(() => setBackendOk(false));
  }, []);

  // ----------------------------------------------------------------
  // Upload handler
  // ----------------------------------------------------------------
  const handleUploadComplete = useCallback((data: GeometryData) => {
    // Prepend API_URL to relative model path so the browser can fetch it
    const fullData: GeometryData = {
      ...data,
      modelUrl: data.modelUrl ? `${API_URL}${data.modelUrl}` : undefined,
    };
    setGeometry(fullData);
    setTrajectories(null);
    resetPlayback();
    setPhase("processing");
    setComplianceReport(null);
    setComplianceLoading(false);
    setViewMode("3d");
    console.log("=== Geometry Data Received ===");
    console.log("Boundary points:", data.boundaries.length);
    console.log("Raw boundary points:", data.rawBoundaries?.length ?? 0);
    console.log("Obstacles detected:", data.obstacles.length);
    if (data.floorArea) console.log("Floor area:", data.floorArea, "m²");
    if (fullData.modelUrl) console.log("Model URL:", fullData.modelUrl);
  }, [resetPlayback]);

  // ----------------------------------------------------------------
  // Analytics
  // ----------------------------------------------------------------
  const handleRequestAnalytics = useCallback(async () => {
    setAnalyticsLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/analytics`);
      const data = await res.json();
      if (data.status === "done" && data.data) {
        setAnalyticsData(data.data as AnalyticsData);
      }
    } catch {
      // Non-critical
    } finally {
      setAnalyticsLoading(false);
    }
  }, []);

  // ----------------------------------------------------------------
  // Start simulation
  // ----------------------------------------------------------------
  const handleRunSim = useCallback(async () => {
    if (!geometry) return;
    setPhase("simulating");
    setError(null);
    setComplianceReport(null);
    setComplianceLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/start-simulation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          boundaries: geometry.boundaries,
          obstacles: geometry.obstacles,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }

      // Poll until done
      const poll = async (): Promise<Trajectories> => {
        await new Promise((r) => setTimeout(r, 1000));
        const r = await fetch(`${API_URL}/api/get-trajectories`);
        const data = await r.json();
        if (data.status === "running") return poll();
        if (!r.ok) throw new Error(data.detail || "Simulation failed");
        return data as Trajectories;
      };

      const traj = await poll();
      setTrajectories(traj);
      scrubTo(0);
      setPhase("completed");
      setPlaying(true); // auto-start playback
      console.log("=== Trajectories Received ===");
      console.log("Frames:", Object.keys(traj).length);
      console.log(
        "Agents:",
        Object.keys(traj["0"] || {}).length,
      );

      // Poll compliance report
      const pollCompliance = async (): Promise<ComplianceReport | null> => {
        await new Promise((r) => setTimeout(r, 500));
        const r = await fetch(`${API_URL}/api/compliance/report`);
        const data = await r.json();
        if (data.status === "running") return pollCompliance();
        if (data.status === "done" && data.report)
          return data.report as ComplianceReport;
        return null;
      };

      const report = await pollCompliance();
      setComplianceReport(report);
      setComplianceLoading(false);
      if (report) {
        console.log("=== Compliance Report ===");
        console.log(
          `Score: ${report.compliance_score}% (${report.status.toUpperCase()})`,
        );
        console.log(`Violations: ${report.total_violations}`);
      }

      // Auto-fetch analytics
      handleRequestAnalytics();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setPhase("processing"); // allow retry
      setComplianceLoading(false);
    }
  }, [geometry, handleRequestAnalytics, scrubTo, setPlaying]);

  // ----------------------------------------------------------------
  // Compliance handlers
  // ----------------------------------------------------------------
  const handleBuildingTypeChange = useCallback(
    async (type: string) => {
      setBuildingType(type);
      try {
        await fetch(`${API_URL}/api/compliance/init`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ building_type: type }),
        });
      } catch {
        // Non-critical — defaults will be used
      }
    },
    [],
  );

  const handleFocusViolation = useCallback((violation: Violation) => {
    setHighlightedViolationId(violation.id);
    setFocusTarget(violation.coordinate);
  }, []);

  const handleFocusComplete = useCallback(() => {
    setFocusTarget(null);
    setTimeout(() => setHighlightedViolationId(null), 3000);
  }, []);

  // ----------------------------------------------------------------
  // Control callbacks
  // ----------------------------------------------------------------
  const handleReset = useCallback(() => {
    setGeometry(null);
    setTrajectories(null);
    resetPlayback();
    setPhase("idle");
    setError(null);
    setComplianceReport(null);
    setComplianceLoading(false);
    setHighlightedViolationId(null);
    setFocusTarget(null);
    setAnalyticsData(null);
    setAnalyticsLoading(false);
    setShowHeatmap(false);
    setViewMode("3d");
  }, [resetPlayback]);

  const handleUploadClick = useCallback(() => {
    uploadInputRef.current?.click();
  }, []);

  // ----------------------------------------------------------------
  // Derived data
  // ----------------------------------------------------------------
  const agentCount = useMemo(() => {
    if (!trajectories) return 0;
    const firstFrame = trajectories["0"];
    return firstFrame ? Object.keys(firstFrame).length : 0;
  }, [trajectories]);

  // ----------------------------------------------------------------
  // Render
  // ----------------------------------------------------------------
  const hasViewport = geometry !== null;

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-zinc-950">
      {/* 3D Viewport (fills screen when geometry loaded) */}
      {hasViewport ? (
        <SimViewer
          boundaries={geometry.boundaries}
          rawBoundaries={geometry.rawBoundaries}
          obstacles={geometry.obstacles}
          trajectories={trajectories}
          frameRef={frameRef}
          phase={phase}
          modelUrl={geometry.modelUrl}
          modelFormat={geometry.modelFormat}
          centerOffset={geometry.centerOffset}
          violations={complianceReport?.violations ?? []}
          highlightedViolationId={highlightedViolationId}
          focusTarget={focusTarget}
          onFocusComplete={handleFocusComplete}
          heatmapData={analyticsData?.density_heatmap ?? null}
          showHeatmap={showHeatmap}
          onToggleHeatmap={() => setShowHeatmap((h) => !h)}
          viewMode={viewMode}
        />
      ) : (
        <div className="flex h-full flex-col items-center justify-center gap-8 p-8">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-white mb-2">Archion Sim</h1>
            <p
              className={`text-sm ${backendOk ? "text-green-400" : "text-zinc-500"}`}
            >
              {backendOk ? "Backend Connected" : "Checking backend…"}
            </p>
          </div>
          <ModelUpload
            apiUrl={API_URL}
            onUploadComplete={handleUploadComplete}
          />
        </div>
      )}

      {/* HUD overlay — always visible once geometry is loaded */}
      {hasViewport && (
        <>
          {/* Top-left info bar */}
          <div className="absolute top-4 left-4 z-10 flex items-center gap-3">
            <h1 className="text-sm font-bold text-white tracking-wide">
              ARCHION SIM
            </h1>
            <span className="text-[10px] font-mono text-zinc-500">
              {geometry.boundaries.length} boundary pts
              {geometry.obstacles.length > 0 &&
                ` · ${geometry.obstacles.length} obstacles`}
            </span>
            {trajectories && (
              <span className="text-[10px] font-mono text-cyan-500">
                · {Object.keys(trajectories["0"] || {}).length} agents
              </span>
            )}
          </div>

          {/* Building type selector — shown when ready to simulate */}
          {phase === "processing" && (
            <div className="absolute top-4 right-4 z-10 flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/90 backdrop-blur-md px-3 py-2">
              <label className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">
                Building Type
              </label>
              <select
                value={buildingType}
                onChange={(e) => handleBuildingTypeChange(e.target.value)}
                className="rounded bg-zinc-800 border border-zinc-600 text-xs text-zinc-300 px-2 py-1 focus:outline-none focus:border-cyan-500"
              >
                <option value="residential">Residential</option>
                <option value="public_buildings">Public Buildings</option>
                <option value="hospital">Hospital</option>
                <option value="educational">Educational</option>
                <option value="commercial">Commercial</option>
                <option value="industrial">Industrial</option>
              </select>
            </div>
          )}

          {/* Hidden file input triggered by Controls "Upload Model" button */}
          <input
            ref={uploadInputRef}
            type="file"
            accept=".obj,.glb,.gltf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              e.target.value = "";
              setPhase("uploading");
              const formData = new FormData();
              formData.append("file", file);
              fetch(`${API_URL}/api/process-model`, { method: "POST", body: formData })
                .then((r) => {
                  if (!r.ok) return r.json().then((b) => { throw new Error(b.detail || `HTTP ${r.status}`); });
                  return r.json();
                })
                .then((data) => handleUploadComplete(data))
                .catch((err) => {
                  setError(err instanceof Error ? err.message : "Upload failed");
                  setPhase("processing");
                });
            }}
          />

          {/* Error toast */}
          {error && (
            <div className="absolute top-4 right-4 z-10 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2">
              <p className="text-xs text-red-300">{error}</p>
            </div>
          )}

          {/* Violation Monitor + Analytics — shown after simulation completes */}
          {phase === "completed" && (
            <>
              <ViolationPanel
                report={complianceReport}
                loading={complianceLoading}
                onFocusViolation={handleFocusViolation}
              />
              <AnalyticsDashboard
                analyticsData={analyticsData}
                complianceReport={complianceReport}
                loading={analyticsLoading}
                onRequestAnalytics={handleRequestAnalytics}
              />
            </>
          )}

          {/* Bottom controls */}
          <Controls
            phase={phase}
            playing={isPlaying}
            frame={currentFrame}
            totalFrames={totalFrames}
            speed={speed}
            agentCount={agentCount}
            violationCount={complianceReport?.total_violations ?? 0}
            viewMode={viewMode}
            onUploadClick={handleUploadClick}
            onRunSim={handleRunSim}
            onTogglePlay={togglePlay}
            onSeek={scrubTo}
            onReset={handleReset}
            onCycleSpeed={cycleSpeed}
            onToggleViewMode={toggleViewMode}
          />
        </>
      )}
    </div>
  );
}
