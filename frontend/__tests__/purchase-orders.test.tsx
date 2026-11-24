import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PurchaseOrdersPage from "@/app/purchase-orders/page";
import { ApiError, inventraApi } from "@/lib/api";
import { item, order } from "./fixtures";

vi.mock("next/navigation", () => ({ usePathname: () => "/purchase-orders" }));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    inventraApi: { getPurchaseOrders: vi.fn(), getInventory: vi.fn() },
  };
});

const api = vi.mocked(inventraApi);

beforeEach(() => {
  api.getInventory.mockResolvedValue([item({ id: 1, item_name: "Cotton Fabric" })]);
  api.getPurchaseOrders.mockResolvedValue([
    order({ id: 1, po_number: "PO-2026-001", supplier_name: "Northwind Mills", status: "approved" }),
    order({ id: 2, po_number: "PO-2026-002", supplier_name: "Harbor Textiles", status: "received", remaining_quantity: "0" }),
  ]);
});

describe("Purchase orders page", () => {
  it("disables refresh while the first load is in progress", () => {
    api.getPurchaseOrders.mockReturnValue(new Promise(() => {}));
    render(<PurchaseOrdersPage />);
    expect(screen.getByRole("button", { name: /Refresh data/ })).toBeDisabled();
  });

  it("lists orders with their supplier and status once loaded", async () => {
    render(<PurchaseOrdersPage />);
    expect(await screen.findByText("PO-2026-001")).toBeInTheDocument();
    expect(screen.getByText("Northwind Mills")).toBeInTheDocument();
    expect(screen.getByText("Harbor Textiles")).toBeInTheDocument();
  });

  it("searches by order number or supplier", async () => {
    render(<PurchaseOrdersPage />);
    await screen.findByText("PO-2026-001");
    const search = screen.getByPlaceholderText(/search/i);
    fireEvent.change(search, { target: { value: "harbor" } });
    expect(screen.queryByText("PO-2026-001")).toBeNull();
    expect(screen.getByText("PO-2026-002")).toBeInTheDocument();
  });

  it("explains when no order matches the current search", async () => {
    render(<PurchaseOrdersPage />);
    await screen.findByText("PO-2026-001");
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: "zzz-no-match" } });
    expect(screen.getByText("No purchase orders found")).toBeInTheDocument();
    expect(screen.getByText("Try changing your search or status filter.")).toBeInTheDocument();
  });

  it("shows the backend's message when the orders cannot be loaded", async () => {
    api.getPurchaseOrders.mockRejectedValue(new ApiError("Cannot reach the Inventra backend. Check that it is running.", null));
    render(<PurchaseOrdersPage />);
    expect(await screen.findByText("Cannot reach the Inventra backend. Check that it is running.")).toBeInTheDocument();
  });

  it("reloads from the server when refresh is pressed", async () => {
    render(<PurchaseOrdersPage />);
    await screen.findByText("PO-2026-001");
    fireEvent.click(screen.getByRole("button", { name: /Refresh data/ }));
    await waitFor(() => expect(api.getPurchaseOrders).toHaveBeenCalledTimes(2));
  });
});
