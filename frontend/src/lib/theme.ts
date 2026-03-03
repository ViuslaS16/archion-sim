/**
 * Archion Sim — Brand Theme Constants
 *
 * Centralized color palette and design tokens used across the application.
 * Import these instead of hardcoding hex values in components.
 */

export const colors = {
  // Primary brand
  cyan: {
    50: "#ecfeff",
    100: "#cffafe",
    200: "#a5f3fc",
    300: "#67e8f9",
    400: "#22d3ee",
    500: "#06b6d4",
    600: "#0891b2",
    700: "#0e7490",
  },

  // Neutrals (zinc)
  zinc: {
    50: "#fafafa",
    100: "#f4f4f5",
    200: "#e4e4e7",
    300: "#d4d4d8",
    400: "#a1a1aa",
    500: "#71717a",
    600: "#52525b",
    700: "#3f3f46",
    800: "#27272a",
    900: "#18181b",
    950: "#09090b",
  },

  // Semantic
  success: "#16a34a",
  warning: "#F59E0B",
  error: "#DC2626",
  info: "#3B82F6",

  // Severity mapping
  severity: {
    critical: "#DC2626",
    high: "#F59E0B",
    medium: "#EAB308",
    low: "#3B82F6",
  },

  // Agent colors
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

/** Compliance score thresholds */
export const thresholds = {
  compliance: {
    pass: 70,
    warning: 50,
  },
  congestion: {
    good: 15,
    warning: 30,
  },
  efficiency: {
    good: 0.8,
    warning: 0.6,
  },
} as const;

/** Evaluate a metric and return a status level */
export function getMetricStatus(
  value: number,
  metric: "compliance" | "congestion" | "efficiency",
): "good" | "warning" | "critical" {
  if (metric === "congestion") {
    // Higher is worse
    if (value <= thresholds.congestion.good) return "good";
    if (value <= thresholds.congestion.warning) return "warning";
    return "critical";
  }
  if (metric === "compliance") {
    if (value >= thresholds.compliance.pass) return "good";
    if (value >= thresholds.compliance.warning) return "warning";
    return "critical";
  }
  // efficiency — higher is better
  if (value >= thresholds.efficiency.good) return "good";
  if (value >= thresholds.efficiency.warning) return "warning";
  return "critical";
}
