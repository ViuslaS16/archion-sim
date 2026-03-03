"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart3,
  X,
  Download,
  FileText,
  Activity,
  Gauge,
  Users,
  TrendingUp,
  Loader2,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import type { AnalyticsData, ComplianceReport } from "@/types/simulation";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Metric Card
// ---------------------------------------------------------------------------

function MetricCard({
  icon,
  label,
  value,
  unit,
  color = "text-cyan-400",
  status,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit: string;
  color?: string;
  status?: "good" | "warning" | "critical";
}) {
  const statusDot = status === "good" ? "bg-green-400" : status === "warning" ? "bg-yellow-400" : status === "critical" ? "bg-red-400" : null;
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
      <div className="mb-1 flex items-center gap-1.5">
        {icon}
        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
          {label}
        </span>
        {statusDot && (
          <span className={`ml-auto h-2 w-2 rounded-full ${statusDot}`} />
        )}
      </div>
      <p className={`text-lg font-bold ${color}`}>
        {value}
        <span className="ml-1 text-xs text-zinc-500">{unit}</span>
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Efficiency Gauge (SVG)
// ---------------------------------------------------------------------------

function EfficiencyGauge({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(1, score));
  // Arc params
  const r = 45;
  const cx = 60;
  const cy = 55;
  const startAngle = Math.PI;
  const endAngle = 0;
  const totalArc = Math.PI; // 180 degrees

  const bgPath = describeArc(cx, cy, r, startAngle, endAngle);
  const fillAngle = startAngle - totalArc * pct;
  const fillPath = describeArc(cx, cy, r, startAngle, fillAngle);

  let color = "#DC2626"; // red
  if (pct >= 0.8) color = "#16a34a"; // green
  else if (pct >= 0.6) color = "#EAB308"; // yellow

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 120 65" className="h-16 w-full">
        <path d={bgPath} fill="none" stroke="#27272a" strokeWidth="8" strokeLinecap="round" />
        <path d={fillPath} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round" />
        <text x={cx} y={50} textAnchor="middle" fill="#e4e4e7" fontSize="16" fontWeight="bold">
          {(pct * 100).toFixed(0)}%
        </text>
        <text x={cx} y={62} textAnchor="middle" fill="#71717a" fontSize="7">
          Efficiency
        </text>
      </svg>
    </div>
  );
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const x1 = cx + r * Math.cos(startAngle);
  const y1 = cy - r * Math.sin(startAngle);
  const x2 = cx + r * Math.cos(endAngle);
  const y2 = cy - r * Math.sin(endAngle);
  const largeArc = Math.abs(startAngle - endAngle) > Math.PI ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 0 ${x2} ${y2}`;
}

// ---------------------------------------------------------------------------
// Custom Tooltip
// ---------------------------------------------------------------------------

const chartTooltipStyle = {
  contentStyle: {
    background: "#18181b",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    fontSize: 11,
    color: "#e4e4e7",
  },
  itemStyle: { color: "#e4e4e7" },
};

// ---------------------------------------------------------------------------
// Violation bar data
// ---------------------------------------------------------------------------

const VIOLATION_COLORS: Record<string, string> = {
  corridor_width: "#DC2626",
  door_width: "#F59E0B",
  turning_space: "#EAB308",
  ramp_gradient: "#DC2626",
  bottleneck: "#3B82F6",
};

function buildViolationBarData(report: ComplianceReport | null) {
  if (!report) return [];
  const counts: Record<string, number> = {};
  for (const v of report.violations) {
    counts[v.type] = (counts[v.type] || 0) + 1;
  }
  return Object.entries(counts).map(([type, count]) => ({
    name: type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    count,
    type,
  }));
}

// ---------------------------------------------------------------------------
// Compliance Radar Data
// ---------------------------------------------------------------------------

function buildRadarData(report: ComplianceReport | null, efficiency: number) {
  const categories = [
    { key: "corridor_width", label: "Corridor Width" },
    { key: "door_width", label: "Door Width" },
    { key: "turning_space", label: "Turning Space" },
    { key: "ramp_gradient", label: "Ramp Gradient" },
    { key: "bottleneck", label: "Flow Capacity" },
  ];

  const sevPenalty: Record<string, number> = { critical: 25, high: 15, medium: 8, low: 3 };
  const penalties: Record<string, number> = {};

  if (report) {
    for (const v of report.violations) {
      penalties[v.type] = (penalties[v.type] || 0) + (sevPenalty[v.severity] || 5);
    }
  }

  return categories.map((c, i) => ({
    category: c.label,
    score: i === 4
      ? Math.max(0, Math.min(100, efficiency * 100))
      : Math.max(0, Math.min(100, 100 - (penalties[c.key] || 0))),
    fullMark: 100,
  }));
}

// ---------------------------------------------------------------------------
// Section Header
// ---------------------------------------------------------------------------

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="mb-1 text-[10px] font-mono uppercase tracking-wider text-zinc-500">
      {children}
    </h4>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function AnalyticsDashboard({
  analyticsData,
  complianceReport,
  loading,
  onRequestAnalytics,
}: {
  analyticsData: AnalyticsData | null;
  complianceReport: ComplianceReport | null;
  loading: boolean;
  onRequestAnalytics: () => void;
}) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  const handleGenerateReport = useCallback(async () => {
    setReportLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/generate-report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_name: "Building Compliance Audit" }),
      });
      const data = await res.json();
      if (data.download_url) {
        setDownloadUrl(data.download_url);
      }
    } catch {
      // Non-critical
    } finally {
      setReportLoading(false);
    }
  }, []);

  // Auto-request analytics if panel opened and no data
  const handleToggle = useCallback(() => {
    setPanelOpen((p) => {
      if (!p && !analyticsData && !loading) {
        onRequestAnalytics();
      }
      return !p;
    });
  }, [analyticsData, loading, onRequestAnalytics]);

  const violationBarData = buildViolationBarData(complianceReport);

  // Avg flow rate
  const avgFlowRate =
    analyticsData && analyticsData.flow_rate.length > 0
      ? analyticsData.flow_rate.reduce((s, p) => s + p.agents_per_minute, 0) /
        analyticsData.flow_rate.length
      : 0;

  return (
    <>
      {/* Floating button — bottom-left */}
      <button
        onClick={handleToggle}
        className="absolute bottom-24 left-4 z-20 flex items-center gap-2 rounded-xl border border-zinc-700 bg-zinc-900/90 px-4 py-3 shadow-2xl backdrop-blur-md transition hover:bg-zinc-800"
      >
        <BarChart3 className="h-5 w-5 text-cyan-400" />
        <span className="text-xs font-medium text-zinc-300">Analytics</span>
      </button>

      {/* Sliding panel from left */}
      <AnimatePresence>
        {panelOpen && (
          <motion.div
            initial={{ x: -400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -400, opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="absolute bottom-0 left-0 top-0 z-30 flex w-[380px] flex-col overflow-hidden border-r border-zinc-700 bg-zinc-950/95 backdrop-blur-xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-zinc-200">
                  Analytics Dashboard
                </h3>
              </div>
              <button
                onClick={() => setPanelOpen(false)}
                className="rounded-md p-1 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3 pb-24">
              {loading && !analyticsData ? (
                <div className="flex flex-col items-center gap-3 py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-cyan-400" />
                  <p className="text-xs text-zinc-400">Computing analytics...</p>
                </div>
              ) : !analyticsData ? (
                <div className="flex flex-col items-center gap-3 py-12">
                  <Activity className="h-8 w-8 text-zinc-600" />
                  <p className="text-xs text-zinc-500">No analytics data yet</p>
                  <button
                    onClick={onRequestAnalytics}
                    className="rounded-lg bg-cyan-600 px-3 py-1.5 text-xs text-white hover:bg-cyan-500"
                  >
                    Compute Analytics
                  </button>
                </div>
              ) : (
                <>
                  {/* ---- Metric cards (2x2) ---- */}
                  <div className="grid grid-cols-2 gap-2">
                    <MetricCard
                      icon={<Activity className="h-3.5 w-3.5 text-cyan-400" />}
                      label="Avg Velocity"
                      value={analyticsData.summary.avg_velocity_ms.toFixed(2)}
                      unit="m/s"
                    />
                    <MetricCard
                      icon={<Users className="h-3.5 w-3.5 text-orange-400" />}
                      label="Congestion"
                      value={analyticsData.congestion_index.percentage.toFixed(1)}
                      unit="%"
                      color={
                        analyticsData.congestion_index.percentage > 30
                          ? "text-red-400"
                          : analyticsData.congestion_index.percentage > 15
                            ? "text-yellow-400"
                            : "text-green-400"
                      }
                      status={
                        analyticsData.congestion_index.percentage > 30
                          ? "critical"
                          : analyticsData.congestion_index.percentage > 15
                            ? "warning"
                            : "good"
                      }
                    />
                    <MetricCard
                      icon={<Gauge className="h-3.5 w-3.5 text-emerald-400" />}
                      label="Efficiency"
                      value={(analyticsData.efficiency_score.average * 100).toFixed(1)}
                      unit="%"
                      color={
                        analyticsData.efficiency_score.average >= 0.8
                          ? "text-green-400"
                          : analyticsData.efficiency_score.average >= 0.6
                            ? "text-yellow-400"
                            : "text-red-400"
                      }
                      status={
                        analyticsData.efficiency_score.average >= 0.8
                          ? "good"
                          : analyticsData.efficiency_score.average >= 0.6
                            ? "warning"
                            : "critical"
                      }
                    />
                    <MetricCard
                      icon={<TrendingUp className="h-3.5 w-3.5 text-blue-400" />}
                      label="Flow Rate"
                      value={avgFlowRate.toFixed(1)}
                      unit="agents/min"
                    />
                  </div>

                  {/* ---- Compliance Radar ---- */}
                  {complianceReport && (
                    <div>
                      <SectionHeader>Compliance Categories</SectionHeader>
                      <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-2">
                        <ResponsiveContainer width="100%" height={200}>
                          <RadarChart
                            data={buildRadarData(
                              complianceReport,
                              analyticsData.efficiency_score.average,
                            )}
                          >
                            <PolarGrid stroke="#27272a" />
                            <PolarAngleAxis
                              dataKey="category"
                              tick={{ fontSize: 8, fill: "#a1a1aa" }}
                            />
                            <PolarRadiusAxis
                              angle={90}
                              domain={[0, 100]}
                              tick={{ fontSize: 7, fill: "#52525b" }}
                            />
                            <Radar
                              name="Score"
                              dataKey="score"
                              stroke="#06b6d4"
                              fill="#06b6d4"
                              fillOpacity={0.3}
                              strokeWidth={2}
                            />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}

                  {/* ---- Velocity Timeline ---- */}
                  <div>
                    <SectionHeader>Velocity Over Time</SectionHeader>
                    <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-2">
                      <ResponsiveContainer width="100%" height={120}>
                        <LineChart data={analyticsData.velocity_timeline}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                          <XAxis
                            dataKey="time_sec"
                            tick={{ fontSize: 8, fill: "#71717a" }}
                            stroke="#3f3f46"
                            label={{ value: "Time (s)", position: "insideBottom", offset: -2, fontSize: 8, fill: "#71717a" }}
                          />
                          <YAxis tick={{ fontSize: 8, fill: "#71717a" }} stroke="#3f3f46" />
                          <Tooltip {...chartTooltipStyle} />
                          <ReferenceLine y={0.2} stroke="#DC2626" strokeDasharray="4 4" strokeWidth={0.8} />
                          <Line
                            type="monotone"
                            dataKey="avg_velocity_ms"
                            stroke="#06b6d4"
                            strokeWidth={1.5}
                            dot={false}
                            name="Avg Velocity (m/s)"
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* ---- Violation Distribution ---- */}
                  {violationBarData.length > 0 && (
                    <div>
                      <SectionHeader>Violation Distribution</SectionHeader>
                      <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-2">
                        <ResponsiveContainer width="100%" height={120}>
                          <BarChart data={violationBarData} layout="vertical">
                            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
                            <XAxis type="number" tick={{ fontSize: 8, fill: "#71717a" }} stroke="#3f3f46" allowDecimals={false} />
                            <YAxis
                              type="category"
                              dataKey="name"
                              tick={{ fontSize: 8, fill: "#a1a1aa" }}
                              stroke="#3f3f46"
                              width={90}
                            />
                            <Tooltip {...chartTooltipStyle} />
                            <Bar dataKey="count" radius={[0, 4, 4, 0]} name="Violations">
                              {violationBarData.map((entry, i) => (
                                <Cell key={i} fill={VIOLATION_COLORS[entry.type] ?? "#6B7280"} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}

                  {/* ---- Congestion Timeline ---- */}
                  <div>
                    <SectionHeader>Congestion Over Time</SectionHeader>
                    <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-2">
                      <ResponsiveContainer width="100%" height={120}>
                        <AreaChart data={analyticsData.congestion_timeline}>
                          <defs>
                            <linearGradient id="congGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#F59E0B" stopOpacity={0.4} />
                              <stop offset="100%" stopColor="#F59E0B" stopOpacity={0.05} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                          <XAxis
                            dataKey="time_sec"
                            tick={{ fontSize: 8, fill: "#71717a" }}
                            stroke="#3f3f46"
                            label={{ value: "Time (s)", position: "insideBottom", offset: -2, fontSize: 8, fill: "#71717a" }}
                          />
                          <YAxis tick={{ fontSize: 8, fill: "#71717a" }} stroke="#3f3f46" />
                          <Tooltip {...chartTooltipStyle} />
                          <Area
                            type="monotone"
                            dataKey="congestion_pct"
                            stroke="#F59E0B"
                            fill="url(#congGrad)"
                            strokeWidth={1.5}
                            name="Congestion %"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* ---- Efficiency Gauge ---- */}
                  <div>
                    <SectionHeader>Path Efficiency</SectionHeader>
                    <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-3">
                      <EfficiencyGauge score={analyticsData.efficiency_score.average} />
                    </div>
                  </div>

                  {/* ---- Flow Rate ---- */}
                  <div>
                    <SectionHeader>Flow Rate Over Time</SectionHeader>
                    <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-2">
                      <ResponsiveContainer width="100%" height={120}>
                        <LineChart data={analyticsData.flow_rate}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                          <XAxis
                            dataKey="time_sec"
                            tick={{ fontSize: 8, fill: "#71717a" }}
                            stroke="#3f3f46"
                            label={{ value: "Time (s)", position: "insideBottom", offset: -2, fontSize: 8, fill: "#71717a" }}
                          />
                          <YAxis tick={{ fontSize: 8, fill: "#71717a" }} stroke="#3f3f46" />
                          <Tooltip {...chartTooltipStyle} />
                          <ReferenceLine
                            y={avgFlowRate}
                            stroke="#EAB308"
                            strokeDasharray="4 4"
                            strokeWidth={0.8}
                          />
                          <Line
                            type="monotone"
                            dataKey="agents_per_minute"
                            stroke="#10B981"
                            strokeWidth={1.5}
                            dot={{ r: 3, fill: "#10B981" }}
                            name="Agents/min"
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Action buttons — pinned at bottom */}
            {analyticsData && (
              <div className="space-y-2 border-t border-zinc-800 px-4 py-3">
                <button
                  onClick={handleGenerateReport}
                  disabled={reportLoading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-600 px-3 py-2 text-xs font-medium text-white transition hover:bg-cyan-500 disabled:opacity-50"
                >
                  {reportLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <FileText className="h-4 w-4" />
                  )}
                  {reportLoading ? "Generating..." : "Generate Report"}
                </button>
                {downloadUrl && (
                  <a
                    href={`${API_URL}${downloadUrl}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-xs font-medium text-zinc-300 transition hover:bg-zinc-700"
                  >
                    <Download className="h-4 w-4" />
                    Download PDF
                  </a>
                )}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
