import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import InventoryTable from "@/app/inventory/InventoryTable";
import { item, risk } from "./fixtures";

const cotton = item({ id: 1, item_code: "FAB-001", item_name: "Cotton Fabric", category: "Textiles" });
const thread = item({ id: 2, item_code: "THR-010", item_name: "Polyester Thread", category: "Notions", unit_of_measure: "pcs" });
const silk = item({ id: 3, item_code: "SLK-100", item_name: "Silk Blend", category: "Textiles" });

const risks = {
  1: risk({ item_id: 1, risk_level: "critical", requires_replenishment: true, suggested_order_quantity: 40 }),
  2: risk({ item_id: 2, item_code: "THR-010", item_name: "Polyester Thread", risk_level: "low_stock" }),
  3: null,
};

function renderTable(items = [cotton, thread, silk], riskMap: Record<number, unknown> = risks) {
  return render(<InventoryTable items={items} risks={riskMap as never} />);
}

function rowFor(name: string) {
  return screen.getByText(name).closest("tr") as HTMLElement;
}

describe("InventoryTable content", () => {
  it("shows each item with its code and category", () => {
    renderTable();
    expect(screen.getByText("Cotton Fabric")).toBeInTheDocument();
    expect(screen.getByText(/FAB-001 · Textiles/)).toBeInTheDocument();
  });

  it("labels risk in plain language, never with a raw identifier", () => {
    renderTable();
    expect(within(rowFor("Cotton Fabric")).getByText("Critical")).toBeInTheDocument();
    expect(within(rowFor("Polyester Thread")).getByText("Low stock")).toBeInTheDocument();
    expect(within(rowFor("Silk Blend")).getByText("Risk unavailable")).toBeInTheDocument();
    expect(screen.queryByText("low_stock")).toBeNull();
  });

  it("flags items that must be reordered now", () => {
    renderTable();
    expect(within(rowFor("Cotton Fabric")).getByText("Replenishment required")).toBeInTheDocument();
    expect(within(rowFor("Polyester Thread")).queryByText("Replenishment required")).toBeNull();
  });

  it("reports how many items are displayed", () => {
    renderTable();
    expect(screen.getByText("3 of 3 items")).toBeInTheDocument();
  });
});

describe("InventoryTable filtering", () => {
  it("offers the backend's risk levels and none of the retired ones", () => {
    renderTable();
    const select = screen.getByLabelText("Filter by risk level");
    const labels = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(labels).toContain("Low stock");
    expect(labels).toContain("Critical");
    expect(labels).not.toContain("High");
    expect(labels).not.toContain("Medium");
  });

  it("'Requires attention' includes low-stock items, not only critical ones", () => {
    renderTable();
    fireEvent.change(screen.getByLabelText("Filter by risk level"), { target: { value: "attention" } });
    expect(screen.getByText("Cotton Fabric")).toBeInTheDocument();
    expect(screen.getByText("Polyester Thread")).toBeInTheDocument();
    expect(screen.queryByText("Silk Blend")).toBeNull();
    expect(screen.getByText("2 of 3 items")).toBeInTheDocument();
  });

  it("searches by item name and by code", () => {
    renderTable();
    const search = screen.getByLabelText("Search inventory");
    fireEvent.change(search, { target: { value: "thread" } });
    expect(screen.getByText("1 of 3 items")).toBeInTheDocument();
    expect(screen.queryByText("Cotton Fabric")).toBeNull();
    fireEvent.change(search, { target: { value: "slk-100" } });
    expect(screen.getByText("Silk Blend")).toBeInTheDocument();
    expect(screen.queryByText("Polyester Thread")).toBeNull();
  });

  it("filters by category", () => {
    renderTable();
    fireEvent.change(screen.getByLabelText("Filter by category"), { target: { value: "Notions" } });
    expect(screen.getByText("Polyester Thread")).toBeInTheDocument();
    expect(screen.queryByText("Cotton Fabric")).toBeNull();
  });

  it("shows an empty state with a working reset when nothing matches", () => {
    renderTable();
    fireEvent.change(screen.getByLabelText("Search inventory"), { target: { value: "no such item" } });
    expect(screen.getByText("No matching inventory items")).toBeInTheDocument();
    // The filter bar and the empty state each offer a reset; either one works.
    fireEvent.click(screen.getAllByRole("button", { name: "Clear filters" })[0]);
    expect(screen.getByLabelText("Search inventory")).toHaveValue("");
    expect(screen.getByText("Cotton Fabric")).toBeInTheDocument();
  });

  it("shows the empty state when the inventory itself is empty", () => {
    renderTable([], {});
    expect(screen.getByText("No matching inventory items")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Clear filters" })).toBeNull();
  });
});
