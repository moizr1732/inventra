/**
 * Typed client for the Inventra API.
 *
 * Errors carry the backend's own message where it has one, so users see
 * "Reserved quantity cannot exceed on-hand quantity" rather than a generic
 * failure. Every request has a timeout so a stalled backend cannot leave
 * the interface loading forever.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const DEFAULT_TIMEOUT_MS = 15_000;
const ASSISTANT_TIMEOUT_MS = 30_000;
const PAGE_SIZE = 500;

/** Quantities arrive as decimal strings from inventory endpoints and as numbers from analytics endpoints. */
export type Quantity = number | string;

export interface InventoryItem {
  id: number;
  item_code: string;
  item_name: string;
  category: string | null;
  unit_of_measure: string;
  on_hand_quantity: Quantity;
  reserved_quantity: Quantity;
  available_quantity: Quantity;
  reorder_level: Quantity;
  safety_stock: Quantity;
  lead_time_days: number;
  unit_cost: Quantity;
  is_active: boolean;
}

export type RiskLevel =
  | "critical"
  | "low_stock"
  | "no_demand_data"
  | "normal"
  | "overstock";

export interface StockRisk {
  item_id: number;
  item_code: string;
  item_name: string;
  unit_of_measure: string;
  risk_level: RiskLevel;
  average_daily_consumption: number;
  observed_days: number;
  available_quantity: number;
  outstanding_open_po_quantity: number;
  inventory_position: number;
  lead_time_days: number;
  safety_stock: number;
  reorder_level: number;
  calculated_reorder_point: number;
  days_of_cover: number | null;
  overstock_threshold_days: number;
  suggested_order_quantity: number;
  requires_replenishment: boolean;
}

export type PurchaseOrderStatus =
  | "draft"
  | "pending"
  | "approved"
  | "ordered"
  | "partially_received"
  | "received"
  | "cancelled";

export interface PurchaseOrder {
  id: number;
  po_number: string;
  inventory_item_id: number;
  supplier_name: string;
  ordered_quantity: Quantity;
  received_quantity: Quantity;
  remaining_quantity: Quantity;
  unit_cost: Quantity;
  order_date: string;
  expected_delivery_date: string | null;
  status: PurchaseOrderStatus;
  notes: string | null;
}

export type ForecastStatus = "ok" | "no_demand" | "insufficient_data";

export interface ForecastPeriod {
  forecast_period: number;
  start_date: string;
  end_date: string;
  predicted_demand: number;
}

export interface HistoricalPeriod {
  period: number;
  start_date: string;
  end_date: string;
  total_consumption: number;
}

export interface ForecastResponse {
  item_id: number;
  item_code: string;
  item_name: string;
  unit_of_measure: string;
  status: ForecastStatus;
  status_message: string;
  historical_demand: number[];
  historical_periods: HistoricalPeriod[];
  average_monthly_demand: number | null;
  forecast_horizon: string;
  method: string;
  forecasts: ForecastPeriod[];
}

export interface PlanningPeriod {
  forecast_period: number;
  start_date: string;
  end_date: string;
  original_ai_demand: number | null;
  adjusted_demand: number | null;
  final_planning_demand: number | null;
  adjustment_status: "ai_forecast" | "manually_adjusted" | "no_forecast";
  adjusted_by: string | null;
  adjustment_reason: string | null;
}

export interface PlanningResponse {
  item_id: number;
  item_code: string;
  item_name: string;
  unit_of_measure: string;
  forecast_status: ForecastStatus;
  status_message: string;
  planning_horizon: string;
  planning_periods: PlanningPeriod[];
}

export interface AssistantResponse {
  answer: string;
  intent: string;
  sources: string[];
  conversation_id: number;
}

export interface AssistantConversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface AssistantConversationMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  intent: string | null;
  created_at: string;
}

export interface HealthResponse {
  status: string;
  application: string;
  database: string;
}

export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Pull a readable message out of FastAPI's error body. */
function messageFromBody(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const parts = detail
      .map((entry) =>
        entry && typeof entry === "object" && "msg" in entry
          ? String((entry as { msg: unknown }).msg).replace(/^Value error, /, "")
          : null
      )
      .filter((part): part is string => Boolean(part));
    if (parts.length > 0) return parts.join(" ");
  }

  if (detail && typeof detail === "object" && "detail" in detail) {
    return String((detail as { detail: unknown }).detail);
  }

  return fallback;
}

async function request<T>(
  method: "GET" | "POST" | "DELETE" | "PATCH",
  endpoint: string,
  options: { body?: unknown; timeoutMs?: number } = {}
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  );

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method,
      cache: "no-store",
      signal: controller.signal,
      headers: options.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request timed out. Please try again.", null);
    }
    throw new ApiError(
      "Cannot reach the Inventra backend. Check that it is running.",
      null
    );
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 204) return undefined as T;

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    throw new ApiError(
      messageFromBody(body, `Request failed with status ${response.status}.`),
      response.status
    );
  }

  return body as T;
}

/** Fetch every active inventory item, following pagination. */
async function getAllInventory(): Promise<InventoryItem[]> {
  const items: InventoryItem[] = [];
  for (let skip = 0; ; skip += PAGE_SIZE) {
    const page = await request<InventoryItem[]>(
      "GET",
      `/inventory?skip=${skip}&limit=${PAGE_SIZE}`
    );
    items.push(...page);
    if (page.length < PAGE_SIZE) break;
  }
  return items;
}

export const inventraApi = {
  getHealth: () => request<HealthResponse>("GET", "/health"),

  getInventory: () => getAllInventory(),

  getStockRisk: (itemId: number) =>
    request<StockRisk>("GET", `/inventory/${itemId}/risk`),

  getPurchaseOrders: () =>
    request<PurchaseOrder[]>("GET", "/purchase-orders?limit=500"),

  getForecast: (itemId: number) =>
    request<ForecastResponse>("GET", `/forecasting/${itemId}`),

  getPlanning: (itemId: number) =>
    request<PlanningResponse>("GET", `/forecasting/${itemId}/planning`),

  sendAssistantMessage: (message: string, conversationId?: number | null) =>
    request<AssistantResponse>("POST", "/assistant/chat", {
      body: {
        message,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      },
      timeoutMs: ASSISTANT_TIMEOUT_MS,
    }),

  getConversations: () =>
    request<AssistantConversation[]>("GET", "/assistant/conversations"),

  getConversationMessages: (conversationId: number) =>
    request<AssistantConversationMessage[]>(
      "GET",
      `/assistant/conversations/${conversationId}/messages`
    ),

  deleteConversation: (conversationId: number) =>
    request<{ message: string; conversation_id: number }>(
      "DELETE",
      `/assistant/conversations/${conversationId}`
    ),
};

/** Quantities may be strings or numbers depending on the endpoint. */
export function toNumber(value: Quantity | null | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}
