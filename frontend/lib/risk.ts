import type { StockRisk } from "@/lib/api";

/**
 * Risk vocabulary shared by the dashboard, inventory page and inventory table.
 * Levels must match the backend's `risk_level` values exactly.
 */
export type KnownRiskLevel =
  | "critical"
  | "low_stock"
  | "no_demand_data"
  | "normal"
  | "overstock";

export const RISK_LABELS: Record<KnownRiskLevel | "unavailable", string> = {
  critical: "Critical",
  low_stock: "Low stock",
  no_demand_data: "No demand data",
  normal: "Normal",
  overstock: "Overstock",
  unavailable: "Risk unavailable",
};

export type RiskTone = "critical" | "warning" | "ok" | "info" | "muted";

export function riskTone(level: string | null | undefined): RiskTone {
  switch (level) {
    case "critical":
      return "critical";
    case "low_stock":
      return "warning";
    case "normal":
      return "ok";
    case "overstock":
      return "info";
    default:
      return "muted";
  }
}

export const RISK_TONE_CLASSES: Record<RiskTone, string> = {
  critical: "border-red-200 bg-red-50 text-red-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-700",
  info: "border-sky-200 bg-sky-50 text-sky-700",
  muted: "border-slate-200 bg-slate-50 text-slate-500",
};

export function riskLabel(level: string | null | undefined): string {
  if (!level) return RISK_LABELS.unavailable;
  return RISK_LABELS[level as KnownRiskLevel] ?? level.replaceAll("_", " ");
}

/** An item needs attention when it is critical or low, or when it must be reordered now. */
export function needsAttention(risk: StockRisk | null | undefined): boolean {
  if (!risk) return false;
  return (
    risk.requires_replenishment ||
    risk.risk_level === "critical" ||
    risk.risk_level === "low_stock"
  );
}

export const RISK_FILTERS = [
  { value: "all", label: "All risk levels" },
  { value: "attention", label: "Requires attention" },
  { value: "critical", label: "Critical" },
  { value: "low_stock", label: "Low stock" },
  { value: "normal", label: "Normal" },
  { value: "overstock", label: "Overstock" },
  { value: "no_demand_data", label: "No demand data" },
  { value: "unavailable", label: "Risk unavailable" },
] as const;

export type RiskFilter = (typeof RISK_FILTERS)[number]["value"];

export function matchesRiskFilter(
  filter: RiskFilter,
  risk: StockRisk | null | undefined
): boolean {
  if (filter === "all") return true;
  if (filter === "unavailable") return !risk;
  if (filter === "attention") return needsAttention(risk);
  return risk?.risk_level === filter;
}
