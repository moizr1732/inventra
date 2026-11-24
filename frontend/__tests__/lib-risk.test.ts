import { describe, expect, it } from "vitest";
import { RISK_FILTERS, matchesRiskFilter, needsAttention, riskLabel, riskTone } from "@/lib/risk";
import { risk } from "./fixtures";

describe("needsAttention", () => {
  it("flags critical and low-stock items", () => {
    expect(needsAttention(risk({ risk_level: "critical" }))).toBe(true);
    expect(needsAttention(risk({ risk_level: "low_stock" }))).toBe(true);
  });

  it("flags any item that must be reordered now, whatever its level", () => {
    expect(needsAttention(risk({ risk_level: "normal", requires_replenishment: true }))).toBe(true);
  });

  it("does not flag normal, overstock or unknown-demand items", () => {
    expect(needsAttention(risk({ risk_level: "normal" }))).toBe(false);
    expect(needsAttention(risk({ risk_level: "overstock" }))).toBe(false);
    expect(needsAttention(risk({ risk_level: "no_demand_data" }))).toBe(false);
  });

  it("treats a missing risk record as not requiring attention", () => {
    expect(needsAttention(null)).toBe(false);
    expect(needsAttention(undefined)).toBe(false);
  });
});

describe("riskLabel and riskTone", () => {
  it("labels every backend risk level in plain language", () => {
    expect(riskLabel("critical")).toBe("Critical");
    expect(riskLabel("low_stock")).toBe("Low stock");
    expect(riskLabel("no_demand_data")).toBe("No demand data");
  });

  it("never shows a raw identifier for an unknown level", () => {
    expect(riskLabel("future_level")).toBe("future level");
  });

  it("describes a missing level as unavailable", () => {
    expect(riskLabel(null)).toBe("Risk unavailable");
  });

  it("maps low stock to the warning tone, not the retired 'high' or 'medium' levels", () => {
    expect(riskTone("low_stock")).toBe("warning");
    expect(riskTone("high")).toBe("muted");
    expect(riskTone("medium")).toBe("muted");
  });
});

describe("risk filters", () => {
  it("offers only levels the backend actually produces", () => {
    const backendLevels = ["critical", "low_stock", "no_demand_data", "normal", "overstock"];
    const values = RISK_FILTERS.map((f) => f.value) as string[];
    expect(values).not.toContain("high");
    expect(values).not.toContain("medium");
    for (const value of values) {
      expect(["all", "attention", "unavailable", ...backendLevels]).toContain(value);
    }
  });

  it("'requires attention' includes low-stock items", () => {
    expect(matchesRiskFilter("attention", risk({ risk_level: "low_stock" }))).toBe(true);
    expect(matchesRiskFilter("attention", risk({ risk_level: "normal" }))).toBe(false);
  });

  it("exact-level filters match only that level", () => {
    expect(matchesRiskFilter("low_stock", risk({ risk_level: "low_stock" }))).toBe(true);
    expect(matchesRiskFilter("critical", risk({ risk_level: "low_stock" }))).toBe(false);
  });

  it("'unavailable' matches items with no risk record, and 'all' matches everything", () => {
    expect(matchesRiskFilter("unavailable", undefined)).toBe(true);
    expect(matchesRiskFilter("unavailable", risk())).toBe(false);
    expect(matchesRiskFilter("all", undefined)).toBe(true);
  });
});
