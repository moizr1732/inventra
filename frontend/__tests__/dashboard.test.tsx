import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, inventraApi } from "@/lib/api";
import DashboardPage from "@/app/page";
import { item, order, risk } from "./fixtures";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    inventraApi: {
      getInventory: vi.fn(),
      getStockRisk: vi.fn(),
      getPurchaseOrders: vi.fn(),
    },
  };
});

const api = vi.mocked(inventraApi);

async function renderDashboard() {
  render(await DashboardPage());
}

function metricValue(title: string) {
  // Text nodes of the card are concatenated: "<title><value><description>".
  const text = document.body.textContent ?? "";
  const match = text.match(new RegExp(`${title}\\s*([\\d,]+)`));
  return match?.[1];
}

beforeEach(() => {
  api.getInventory.mockResolvedValue([
    item({ id: 1, item_code: "FAB-001", item_name: "Cotton Fabric" }),
    item({ id: 2, item_code: "FAB-002", item_name: "Linen Fabric" }),
    item({ id: 3, item_code: "THR-010", item_name: "Polyester Thread", unit_of_measure: "pcs" }),
  ]);
  api.getStockRisk.mockImplementation(async (id: number) => {
    if (id === 1) return risk({ item_id: 1, risk_level: "critical", requires_replenishment: true });
    if (id === 2) return risk({ item_id: 2, item_code: "FAB-002", item_name: "Linen Fabric", risk_level: "low_stock" });
    return risk({ item_id: 3, item_code: "THR-010", risk_level: "normal" });
  });
  api.getPurchaseOrders.mockResolvedValue([order({ id: 1, status: "approved" }), order({ id: 2, po_number: "PO-2026-002", status: "received", remaining_quantity: "0" })]);
});

describe("Dashboard rendering", () => {
  it("counts critical items and items to reorder from the backend risk levels", async () => {
    await renderDashboard();
    expect(metricValue("Critical items")).toBe("1");
    expect(metricValue("Items to reorder")).toBe("1");
  });

  it("shows a live status when every request succeeds", async () => {
    await renderDashboard();
    expect(screen.getByText("Live data")).toBeInTheDocument();
    expect(screen.queryByText("Some dashboard data is unavailable")).toBeNull();
  });

  it("does not show a combined quantity across different units of measure", async () => {
    await renderDashboard();
    expect(screen.queryByText("Combined quantity across units")).toBeNull();
  });

  it("lists items that need attention, including low-stock items", async () => {
    await renderDashboard();
    // Item names can appear in more than one dashboard section, so presence is checked, not uniqueness.
    expect(screen.getAllByText("Linen Fabric").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Cotton Fabric").length).toBeGreaterThan(0);
    expect(screen.queryByText("Polyester Thread")).toBeNull();
  });
});

describe("Dashboard error states", () => {
  it("keeps rendering and marks the data as partial when purchase orders fail", async () => {
    api.getPurchaseOrders.mockRejectedValue(new ApiError("Cannot reach the Inventra backend. Check that it is running.", null));
    await renderDashboard();
    expect(screen.getByText("Partial data")).toBeInTheDocument();
    expect(screen.getByText("Some dashboard data is unavailable")).toBeInTheDocument();
    expect(screen.getByText("Purchase order data is unavailable.")).toBeInTheDocument();
    expect(metricValue("Critical items")).toBe("1");
  });

  it("shows unavailable metrics rather than zero when stock risk cannot be loaded", async () => {
    api.getStockRisk.mockRejectedValue(new ApiError("down", null));
    await renderDashboard();
    expect(metricValue("Critical items")).toBeUndefined();
    expect(screen.getByText("Stock risk data is unavailable.")).toBeInTheDocument();
  });

  it("shows a clear message when the inventory list cannot be loaded", async () => {
    api.getInventory.mockRejectedValue(new ApiError("down", null));
    await renderDashboard();
    expect(screen.getByText("Some dashboard data is unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Live data")).toBeNull();
  });

  it("says when there are no purchase orders rather than showing an empty table", async () => {
    api.getPurchaseOrders.mockResolvedValue([]);
    await renderDashboard();
    expect(screen.getByText("No purchase orders found.")).toBeInTheDocument();
  });
});
