"use client";

import { useState, useRef, useCallback } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldAlert,
  ShieldCheck,
  MoveHorizontal,
  DoorOpen,
  RotateCw,
  TrendingUp,
  Users,
  Focus,
  X,
  Sparkles,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { Violation, ComplianceReport } from "@/types/simulation";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Severity config
// ---------------------------------------------------------------------------

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#DC2626",
  high: "#F59E0B",
  medium: "#EAB308",
  low: "#3B82F6",
};

const SEVERITY_BG: Record<string, string> = {
  critical: "border-red-500 bg-red-500/10",
  high: "border-orange-500 bg-orange-500/10",
  medium: "border-yellow-500 bg-yellow-500/10",
  low: "border-blue-500 bg-blue-500/10",
};

const SEVERITY_TEXT: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-blue-400",
};

const COMPLEXITY_COLORS: Record<string, string> = {
  low: "bg-green-500/20 text-green-400 border-green-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  high: "bg-red-500/20 text-red-400 border-red-500/30",
  unknown: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
};

// ---------------------------------------------------------------------------
// Type icons
// ---------------------------------------------------------------------------

function ViolationIcon({ type }: { type: string }) {
  const cls = "h-4 w-4";
  switch (type) {
    case "corridor_width":
      return <MoveHorizontal className={cls} />;
    case "door_width":
      return <DoorOpen className={cls} />;
    case "turning_space":
      return <RotateCw className={cls} />;
    case "ramp_gradient":
      return <TrendingUp className={cls} />;
    case "bottleneck":
      return <Users className={cls} />;
    default:
      return <ShieldAlert className={cls} />;
  }
}

function formatType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatValue(type: string, value: number): string {
  if (type === "ramp_gradient") return `${(value * 100).toFixed(1)}%`;
  if (type === "bottleneck") return `${value.toFixed(1)} p/m²`;
  return `${value.toFixed(2)}m`;
}

// ---------------------------------------------------------------------------
// AI Recommendation types
// ---------------------------------------------------------------------------

interface AIRecommendation {
  analysis: string;
  solution: string;
  implementation_steps: string[];
  complexity: string;
  estimated_cost_lkr: string;
  regulation_reference: string;
  alternative_solutions: string[];
  _confidence?: number;
  _is_fallback?: boolean;
  _cost_overridden?: boolean;
}

// ---------------------------------------------------------------------------
// Confidence badge
// ---------------------------------------------------------------------------

function ConfidenceBadge({ confidence, isFallback }: { confidence?: number; isFallback?: boolean }) {
  if (isFallback) {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-zinc-600/40 bg-zinc-700/20 px-2 py-0.5 text-[9px] font-medium text-zinc-500">
        Fallback · No AI
      </span>
    );
  }
  if (confidence == null) return null;
  const pct = Math.round(confidence * 100);
  const color =
    pct >= 80
      ? "border-green-500/30 bg-green-500/10 text-green-400"
      : pct >= 60
        ? "border-yellow-500/30 bg-yellow-500/10 text-yellow-400"
        : "border-orange-500/30 bg-orange-500/10 text-orange-400";
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[9px] font-medium ${color}`}>
      {pct}% confidence
    </span>
  );
}

// ---------------------------------------------------------------------------
// AI Recommendation Card
// ---------------------------------------------------------------------------

function AIRecommendationCard({ rec }: { rec: AIRecommendation }) {
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="mt-2 rounded-md border border-purple-500/20 bg-purple-500/5 p-3 space-y-2.5"
    >
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Sparkles className="h-3 w-3 text-purple-400" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-purple-400">
            AI Recommendation
          </span>
        </div>
        <ConfidenceBadge
          confidence={rec._confidence}
          isFallback={rec._is_fallback}
        />
      </div>

      {/* Analysis */}
      <div>
        <p className="text-[10px] font-semibold text-zinc-400 mb-0.5">Analysis</p>
        <p className="text-[11px] text-zinc-300 leading-relaxed">{rec.analysis}</p>
      </div>

      {/* Solution */}
      <div>
        <p className="text-[10px] font-semibold text-zinc-400 mb-0.5">Solution</p>
        <p className="text-[11px] text-zinc-300 leading-relaxed">{rec.solution}</p>
      </div>

      {/* Steps */}
      {(rec.implementation_steps ?? []).length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-zinc-400 mb-1">
            Implementation Steps
          </p>
          <ul className="space-y-1">
            {(rec.implementation_steps ?? []).map((step, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <CheckCircle2 className="h-3 w-3 text-zinc-600 mt-0.5 shrink-0" />
                <span className="text-[10px] text-zinc-400 leading-relaxed">
                  {step}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Bottom row: complexity + cost */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <span
          className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[9px] font-bold uppercase ${COMPLEXITY_COLORS[rec.complexity] ?? COMPLEXITY_COLORS.unknown}`}
        >
          {rec.complexity}
        </span>
        {rec.estimated_cost_lkr && rec.estimated_cost_lkr !== "N/A" && (
          <span className="text-[9px] font-mono text-zinc-500">
            LKR {rec.estimated_cost_lkr}
            {rec._cost_overridden && (
              <span className="ml-1 text-zinc-600 not-italic">(kb estimate)</span>
            )}
          </span>
        )}
        {rec.regulation_reference && rec.regulation_reference !== "N/A" && (
          <span className="text-[9px] text-zinc-600 italic truncate max-w-[160px]" title={rec.regulation_reference}>
            {rec.regulation_reference}
          </span>
        )}
      </div>

      {/* Alternatives */}
      {(rec.alternative_solutions ?? []).length > 0 && (
        <div>
          <p className="text-[9px] font-semibold text-zinc-500 mb-0.5">
            Alternatives
          </p>
          {(rec.alternative_solutions ?? []).map((alt, i) => (
            <p key={i} className="text-[9px] text-zinc-600 leading-relaxed">
              {i + 1}. {alt}
            </p>
          ))}
        </div>
      )}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// ViolationCard — single violation with AI recommendation
// ---------------------------------------------------------------------------

function ViolationCard({
  violation,
  onFocusViolation,
}: {
  violation: Violation;
  onFocusViolation: (v: Violation) => void;
}) {
  const [aiRec, setAiRec] = useState<AIRecommendation | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const handleGetAI = useCallback(async () => {
    if (aiRec) {
      setExpanded((e) => !e);
      return;
    }

    setAiLoading(true);
    setAiError(null);

    try {
      const res = await fetch(`${API_URL}/api/ai-consultant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          violation_id: violation.id,
          building_context: {},
        }),
      });

      const data = await res.json();

      if (data.status === "success" && data.ai_recommendation) {
        setAiRec(data.ai_recommendation);
        setExpanded(true);
      } else if (data.fallback_recommendation) {
        setAiRec(data.fallback_recommendation);
        setExpanded(true);
      } else {
        setAiError("Failed to get recommendation");
      }
    } catch {
      setAiError("AI service unavailable. Please try again.");
    } finally {
      setAiLoading(false);
    }
  }, [violation.id, aiRec]);

  return (
    <div className={`rounded-lg border ${SEVERITY_BG[violation.severity]} p-3`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={SEVERITY_TEXT[violation.severity]}>
            <ViolationIcon type={violation.type} />
          </span>
          <div>
            <p className="text-xs font-semibold text-zinc-200">
              {formatType(violation.type)}
            </p>
            <span
              className={`text-[10px] font-bold uppercase ${SEVERITY_TEXT[violation.severity]}`}
            >
              {violation.severity}
            </span>
          </div>
        </div>
        <button
          onClick={() => onFocusViolation(violation)}
          className="flex items-center gap-1 rounded-md bg-zinc-800 px-2 py-1 text-[10px] font-medium text-zinc-300 transition hover:bg-zinc-700"
        >
          <Focus className="h-3 w-3" />
          Focus
        </button>
      </div>

      <p className="mt-2 text-[11px] text-zinc-400 leading-relaxed">
        {violation.description}
      </p>

      <div className="mt-2 flex items-center gap-3 text-[10px] font-mono">
        <span className="text-zinc-400">
          Measured:{" "}
          <span className={SEVERITY_TEXT[violation.severity]}>
            {formatValue(violation.type, violation.measured_value)}
          </span>
        </span>
        <span className="text-zinc-500">|</span>
        <span className="text-zinc-400">
          Required:{" "}
          <span className="text-zinc-300">
            {formatValue(violation.type, violation.required_value)}
          </span>
        </span>
      </div>

      <p className="mt-1.5 text-[9px] text-zinc-600 italic">
        {violation.regulation}
      </p>

      {/* AI Recommendation button */}
      <button
        onClick={handleGetAI}
        disabled={aiLoading}
        className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md border border-purple-500/30 bg-purple-500/10 px-3 py-1.5 text-[10px] font-medium text-purple-400 transition hover:bg-purple-500/20 disabled:opacity-50"
      >
        {aiLoading ? (
          <>
            <div className="h-3 w-3 animate-spin rounded-full border-2 border-purple-500/30 border-t-purple-400" />
            Generating…
          </>
        ) : aiRec ? (
          <>
            {expanded ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            {expanded ? "Hide" : "Show"} AI Recommendation
          </>
        ) : (
          <>
            <Sparkles className="h-3 w-3" />
            Get AI Recommendation
          </>
        )}
      </button>

      {/* Error */}
      {aiError && (
        <p className="mt-1.5 text-[10px] text-red-400">{aiError}</p>
      )}

      {/* Recommendation */}
      <AnimatePresence>
        {aiRec && expanded && <AIRecommendationCard rec={aiRec} />}
      </AnimatePresence>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ViolationPanel — HTML overlay (outside Canvas)
// ---------------------------------------------------------------------------

interface ViolationPanelProps {
  report: ComplianceReport | null;
  loading: boolean;
  onFocusViolation: (violation: Violation) => void;
}

export function ViolationPanel({
  report,
  loading,
  onFocusViolation,
}: ViolationPanelProps) {
  const [panelOpen, setPanelOpen] = useState(false);

  const totalViolations = report?.total_violations ?? 0;
  const passed = report?.status === "pass";

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setPanelOpen((p) => !p)}
        className="absolute bottom-24 right-4 z-20 flex items-center gap-2 rounded-xl border border-zinc-700 bg-zinc-900/90 backdrop-blur-md px-4 py-3 shadow-2xl transition hover:bg-zinc-800"
      >
        {loading ? (
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-500 border-t-cyan-400" />
        ) : passed ? (
          <ShieldCheck className="h-5 w-5 text-green-400" />
        ) : (
          <ShieldAlert className="h-5 w-5 text-red-400" />
        )}
        <span className="text-xs font-medium text-zinc-300">
          {loading
            ? "Auditing…"
            : report
              ? `${totalViolations} Violation${totalViolations !== 1 ? "s" : ""}`
              : "Compliance"}
        </span>
        {totalViolations > 0 && !loading && (
          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
            {totalViolations}
          </span>
        )}
      </button>

      {/* Sliding panel */}
      <AnimatePresence>
        {panelOpen && (
          <motion.div
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="absolute right-0 top-0 bottom-0 w-[380px] z-30 border-l border-zinc-700 bg-zinc-950/95 backdrop-blur-xl overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-zinc-400" />
                <span className="text-sm font-semibold text-zinc-200">
                  Compliance Report
                </span>
              </div>
              <button
                onClick={() => setPanelOpen(false)}
                className="rounded-lg p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Score badge */}
            {report && (
              <div className="px-4 py-3 border-b border-zinc-800">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
                      {report.standard}
                    </p>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      {formatType(report.building_type)}
                    </p>
                  </div>
                  <div
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 ${
                      passed
                        ? "bg-green-500/15 border border-green-500/30"
                        : "bg-red-500/15 border border-red-500/30"
                    }`}
                  >
                    {passed ? (
                      <ShieldCheck className="h-4 w-4 text-green-400" />
                    ) : (
                      <ShieldAlert className="h-4 w-4 text-red-400" />
                    )}
                    <span
                      className={`text-sm font-bold ${
                        passed ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      {report.compliance_score}%
                    </span>
                    <span
                      className={`text-[10px] font-bold uppercase ${
                        passed ? "text-green-500" : "text-red-500"
                      }`}
                    >
                      {report.status}
                    </span>
                  </div>
                </div>

                {/* Summary chips */}
                <div className="flex gap-2 mt-3">
                  {(["critical", "high", "medium", "low"] as const).map(
                    (sev) => {
                      const count = report.summary[sev] ?? 0;
                      if (count === 0) return null;
                      return (
                        <span
                          key={sev}
                          className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-medium ${SEVERITY_BG[sev]} ${SEVERITY_TEXT[sev]}`}
                        >
                          {count} {sev}
                        </span>
                      );
                    },
                  )}
                </div>
              </div>
            )}

            {/* Violation cards */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
              {!report && !loading && (
                <p className="text-xs text-zinc-500 text-center py-8">
                  Run a simulation to generate compliance report
                </p>
              )}
              {loading && (
                <div className="flex flex-col items-center gap-2 py-8">
                  <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-600 border-t-cyan-400" />
                  <p className="text-xs text-zinc-500">Running audit…</p>
                </div>
              )}
              {report?.violations.map((v) => (
                <ViolationCard
                  key={v.id}
                  violation={v}
                  onFocusViolation={onFocusViolation}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ---------------------------------------------------------------------------
// ViolationMarkers — R3F component (inside Canvas)
// ---------------------------------------------------------------------------

function ViolationCone({
  violation,
  highlighted,
}: {
  violation: Violation;
  highlighted: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  const color = SEVERITY_COLORS[violation.severity] ?? "#ffffff";

  // Backend [x, y] → Three.js [x, height, -y]
  const targetX = violation.coordinate.x;
  const targetZ = -violation.coordinate.y;

  useFrame((state) => {
    if (!meshRef.current) return;
    const t = state.clock.elapsedTime;

    // Bob above floor for visibility
    meshRef.current.position.y = 1.8 + Math.sin(t * 2) * 0.06;

    // Scale pulse when highlighted
    if (highlighted) {
      const s = 1.0 + Math.sin(t * 4) * 0.3;
      meshRef.current.scale.setScalar(s);
    } else {
      meshRef.current.scale.setScalar(1);
    }
  });

  return (
    <mesh
      ref={meshRef}
      position={[targetX, 1.8, targetZ]}
    >
      <sphereGeometry args={[0.08, 12, 12]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={highlighted ? 1.0 : 0.6}
        transparent
        opacity={0.9}
      />
    </mesh>
  );
}

function PulsingRing({
  violation,
}: {
  violation: Violation;
}) {
  const ringRef = useRef<THREE.Mesh>(null);
  const color = SEVERITY_COLORS[violation.severity] ?? "#ffffff";
  const targetX = violation.coordinate.x;
  const targetZ = -violation.coordinate.y;

  useFrame((state) => {
    if (!ringRef.current) return;
    const t = state.clock.elapsedTime;
    const pulse = 1.0 + Math.abs(Math.sin(t * 1.5));
    ringRef.current.scale.set(pulse, pulse, 1);
    const mat = ringRef.current.material as THREE.MeshBasicMaterial;
    mat.opacity = 0.6 * (1 - (pulse - 1.0));
  });

  return (
    <mesh
      ref={ringRef}
      position={[targetX, 1.8, targetZ]}
      rotation={[-Math.PI / 2, 0, 0]}
    >
      <ringGeometry args={[0.12, 0.18, 32]} />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.6}
        depthWrite={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

interface ViolationMarkersProps {
  violations: Violation[];
  highlightedId: string | null;
}

export function ViolationMarkers({
  violations,
  highlightedId,
}: ViolationMarkersProps) {
  return (
    <group>
      {violations.map((v) => (
        <group key={v.id}>
          <ViolationCone
            violation={v}
            highlighted={v.id === highlightedId}
          />
          <PulsingRing violation={v} />
        </group>
      ))}
    </group>
  );
}
