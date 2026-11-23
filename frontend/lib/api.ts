
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface InventoryItem {
  id: number;
  item_code: string;
  item_name: string;
  category: string;
  unit_of_measure: string;
  on_hand_quantity: string;
  reserved_quantity: string;
  available_quantity: string;
  reorder_level: string;
  safety_stock: string;
  lead_time_days: number;
  unit_cost: string;
  is_active: boolean;
}

export interface StockRisk {
  item_id: number;
  item_code: string;
  item_name: string;
  risk_level: string;
  average_daily_consumption: number;
  available_quantity: number;
  outstanding_open_po_quantity: number;
  inventory_position: number;
  lead_time_days: number;
  safety_stock: number;
  calculated_reorder_point: number;
  days_of_cover: number;
  overstock_threshold_days: number;
  suggested_order_quantity: number;
  requires_replenishment: boolean;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  inventory_item_id: number;
  supplier_name: string;
  ordered_quantity: string;
  received_quantity: string;
  remaining_quantity: string;
  unit_cost: string;
  order_date: string;
  expected_delivery_date: string;
  status: string;
}

export interface ForecastResponse {
  item_id: number;
  item_code: string;
  item_name: string;
  historical_demand: number[];
  average_monthly_demand: number;
  forecast_horizon: string;
  forecasts: {
    forecast_period: number;
    start_date: string;
    end_date: string;
    predicted_demand: number;
  }[];
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

async function apiRequest<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `API request failed (${response.status}): ${endpoint}`
    );
  }

  return response.json() as Promise<T>;
}

async function apiPost<T>(
  endpoint: string,
  body: unknown
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(
      `API request failed (${response.status}): ${endpoint}`
    );
  }

  return response.json() as Promise<T>;
}

async function apiDelete<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "DELETE",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `API request failed (${response.status}): ${endpoint}`
    );
  }

  return response.json() as Promise<T>;
}

export const inventraApi = {
  getInventory: () =>
    apiRequest<InventoryItem[]>("/inventory"),

  getStockRisk: (itemId: number) =>
    apiRequest<StockRisk>(`/inventory/${itemId}/risk`),

  getPurchaseOrders: () =>
    apiRequest<PurchaseOrder[]>("/purchase-orders"),

  getForecast: (itemId: number) =>
    apiRequest<ForecastResponse>(`/forecasting/${itemId}`),

  sendAssistantMessage: (
    message: string,
    conversationId?: number | null
  ) =>
    apiPost<AssistantResponse>("/assistant/chat", {
      message,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    }),

  getConversations: () =>
    apiRequest<AssistantConversation[]>("/assistant/conversations"),

  getConversationMessages: (conversationId: number) =>
    apiRequest<AssistantConversationMessage[]>(
      `/assistant/conversations/${conversationId}/messages`
    ),

  deleteConversation: (conversationId: number) =>
    apiDelete<{ message: string; conversation_id: number }>(
      `/assistant/conversations/${conversationId}`
    ),
};
