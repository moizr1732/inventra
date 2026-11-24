import type { InventoryItem, PurchaseOrder, StockRisk, ForecastResponse } from "@/lib/api";

/** Synthetic demo data only. */
export function item(overrides: Partial<InventoryItem> = {}): InventoryItem {
  return {
    id: 1,
    item_code: "FAB-001",
    item_name: "Cotton Fabric",
    category: "Textiles",
    unit_of_measure: "m",
    on_hand_quantity: "900",
    reserved_quantity: "50",
    available_quantity: "850",
    reorder_level: "300",
    safety_stock: "150",
    lead_time_days: 7,
    unit_cost: "4.50",
    is_active: true,
    ...overrides,
  };
}

export function risk(overrides: Partial<StockRisk> = {}): StockRisk {
  return {
    item_id: 1,
    item_code: "FAB-001",
    item_name: "Cotton Fabric",
    unit_of_measure: "m",
    risk_level: "normal",
    average_daily_consumption: 20,
    observed_days: 90,
    available_quantity: 850,
    outstanding_open_po_quantity: 0,
    inventory_position: 850,
    lead_time_days: 7,
    safety_stock: 150,
    reorder_level: 300,
    calculated_reorder_point: 290,
    days_of_cover: 42,
    overstock_threshold_days: 60,
    suggested_order_quantity: 0,
    requires_replenishment: false,
    ...overrides,
  };
}

export function order(overrides: Partial<PurchaseOrder> = {}): PurchaseOrder {
  return {
    id: 1,
    po_number: "PO-2026-001",
    inventory_item_id: 1,
    supplier_name: "Northwind Mills",
    ordered_quantity: "400",
    received_quantity: "0",
    remaining_quantity: "400",
    unit_cost: "5.10",
    order_date: "2026-11-01",
    expected_delivery_date: null,
    status: "approved",
    notes: null,
    ...overrides,
  };
}

export function forecast(overrides: Partial<ForecastResponse> = {}): ForecastResponse {
  return {
    item_id: 1,
    item_code: "FAB-001",
    item_name: "Cotton Fabric",
    unit_of_measure: "m",
    status: "ok",
    status_message: "Forecast based on the last three complete periods of consumption.",
    historical_demand: [300, 600, 600],
    historical_periods: [],
    average_monthly_demand: 500,
    forecast_horizon: "Next three 30-day periods",
    method: "Three-period moving average",
    forecasts: [
      { forecast_period: 1, start_date: "2026-10-28", end_date: "2026-11-26", predicted_demand: 500 },
    ],
    ...overrides,
  };
}
