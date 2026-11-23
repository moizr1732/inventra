
import Link from "next/link";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  Boxes,
  CheckCircle2,
  Package,
  ShieldCheck,
  TrendingUp,
  Truck,
} from "lucide-react";

import {
  inventraApi,
  type InventoryItem,
  type PurchaseOrder,
  type StockRisk,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";

export const dynamic = "force-dynamic";

function number(value: number | string | null | undefined) {
  return Number(value ?? 0).toLocaleString("en-US", {
    maximumFractionDigits: 2,
  });
}

/** An item needs attention when its risk is critical or low, or when it must be reordered. */
function needsAttention(risk: StockRisk) {
  return (
    risk.requires_replenishment ||
    risk.risk_level === "critical" ||
    risk.risk_level === "low_stock"
  );
}

function MetricCard({
  title,
  value,
  description,
  icon: Icon,
  accent,
}: {
  title: string;
  value: string;
  description: string;
  icon: React.ElementType;
  accent: string;
}) {
  return (
    <div className="metric-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <h2 className="mt-3 text-2xl font-bold tracking-tight text-slate-900">
            {value}
          </h2>
          <p className="mt-2 text-xs text-slate-500">{description}</p>
        </div>
        <div className="metric-icon shrink-0" style={{ color: accent, background: `${accent}12` }}>
          <Icon size={20} />
        </div>
      </div>
    </div>
  );
}

async function getDashboardData() {
  const [inventoryResult, ordersResult] = await Promise.allSettled([
    inventraApi.getInventory(),
    inventraApi.getPurchaseOrders(),
  ]);

  const inventory: InventoryItem[] =
    inventoryResult.status === "fulfilled" ? inventoryResult.value : [];

  const orders: PurchaseOrder[] =
    ordersResult.status === "fulfilled" ? ordersResult.value : [];

  const riskResults = await Promise.allSettled(
    inventory.map((item) => inventraApi.getStockRisk(item.id))
  );

  const risks: StockRisk[] = riskResults
    .filter((result): result is PromiseFulfilledResult<StockRisk> =>
      result.status === "fulfilled"
    )
    .map((result) => result.value);

  const activeStatuses = [
    "draft",
    "pending",
    "approved",
    "ordered",
    "partially_received",
  ];

  return {
    inventory,
    orders,
    risks,
    inventoryAvailable: inventoryResult.status === "fulfilled",
    ordersAvailable: ordersResult.status === "fulfilled",
    risksAvailable: riskResults.every((result) => result.status === "fulfilled"),
    criticalCount: risks.filter((risk) => risk.risk_level === "critical").length,
    attentionRisks: risks.filter(needsAttention),
    replenishmentCount: risks.filter((risk) => risk.requires_replenishment).length,
    activeOrders: orders.filter((order) =>
      activeStatuses.includes(order.status.toLowerCase())
    ),
    receivedOrders: orders.filter(
      (order) => order.status.toLowerCase() === "received"
    ),
    cancelledOrders: orders.filter(
      (order) => order.status.toLowerCase() === "cancelled"
    ),
  };
}

function statusClass(status: string) {
  const value = status.toLowerCase();

  if (value === "received" || value === "approved") {
    return "bg-emerald-50 text-emerald-700";
  }
  if (value === "cancelled") return "bg-slate-100 text-slate-600";
  if (value === "pending" || value === "draft") {
    return "bg-amber-50 text-amber-700";
  }
  return "bg-blue-50 text-blue-700";
}

export default async function DashboardPage() {
  const data = await getDashboardData();

  const recentOrders = [...data.orders]
    .sort((a, b) => b.id - a.id)
    .slice(0, 5);

  const hasErrors =
    !data.inventoryAvailable || !data.ordersAvailable || !data.risksAvailable;

  return (
    <AppShell>

      <main className="min-w-0 flex-1">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-5 sm:px-8">
          <div>
            <p className="text-xs font-medium text-slate-400">INVENTORY INTELLIGENCE / OVERVIEW</p>
            <h1 className="mt-1 text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
              Dashboard
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Monitor inventory health and procurement performance.
            </p>
          </div>
          <div
            className={`flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold ${
              hasErrors
                ? "border-amber-200 bg-amber-50 text-amber-700"
                : "border-emerald-100 bg-emerald-50 text-emerald-700"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${hasErrors ? "bg-amber-500" : "bg-emerald-500"}`} />
            {hasErrors ? "Partial data" : "Live data"}
          </div>
        </header>

        <div className="space-y-7 p-5 sm:p-8">
          {hasErrors && (
            <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              <AlertTriangle size={19} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold">Some dashboard data is unavailable</p>
                <p className="mt-1 text-xs">
                  One or more API requests failed. Check that the backend is running and refresh this page.
                </p>
              </div>
            </div>
          )}

          <section>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="section-title">Operational overview</h2>
                <p className="mt-1 text-xs text-slate-500">Current inventory and procurement indicators</p>
              </div>
              <span className="text-xs text-slate-400">Updated on page load</span>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                title="Inventory items"
                value={data.inventoryAvailable ? number(data.inventory.length) : "—"}
                description="Active, valid inventory records"
                icon={Package}
                accent="#0D9488"
              />
              <MetricCard
                title="Critical items"
                value={data.risksAvailable ? number(data.criticalCount) : "—"}
                description="Stock covers less than the lead time"
                icon={Boxes}
                accent="#DC2626"
              />
              <MetricCard
                title="Items to reorder"
                value={data.risksAvailable ? number(data.replenishmentCount) : "—"}
                description="Suggested purchase needed now"
                icon={AlertTriangle}
                accent="#D97706"
              />
              <MetricCard
                title="Active purchase orders"
                value={data.ordersAvailable ? number(data.activeOrders.length) : "—"}
                description="Draft, pending and in progress"
                icon={Truck}
                accent="#7C3AED"
              />
            </div>
          </section>

          <section className="grid grid-cols-1 gap-5 xl:grid-cols-3">
            <div className="panel xl:col-span-2">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
                <div>
                  <h2 className="section-title">Stock health monitoring</h2>
                  <p className="mt-1 text-xs text-slate-500">Live risk assessment for your inventory</p>
                </div>
                <Link href="/inventory" className="flex items-center gap-1 text-xs font-semibold text-teal-700 hover:text-teal-900">
                  View inventory <ArrowRight size={14} />
                </Link>
              </div>

              <div className="divide-y divide-slate-100">
                {data.risks.length === 0 ? (
                  <div className="p-8 text-center text-sm text-slate-500">
                    {data.risksAvailable ? "No valid inventory risk records found." : "Stock risk data is unavailable."}
                  </div>
                ) : (
                  data.risks.map((risk) => {
                    const isRisk = needsAttention(risk);

                    return (
                      <div key={risk.item_id} className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
                        <div className="flex min-w-0 items-center gap-3">
                          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                            <Package size={19} />
                          </div>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-slate-800">{risk.item_name}</p>
                            <p className="text-xs text-slate-500">{risk.item_code}</p>
                          </div>
                        </div>
                        <div className="flex flex-wrap items-center gap-5">
                          <div className="text-right">
                            <p className="text-sm font-semibold text-slate-800">{number(risk.available_quantity)}</p>
                            <p className="text-[11px] text-slate-400">Available stock</p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-semibold text-slate-800">{number(risk.days_of_cover)} days</p>
                            <p className="text-[11px] text-slate-400">Stock cover</p>
                          </div>
                          <span className={`status-chip ${isRisk ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>
                            {risk.risk_level}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            <div className="panel">
              <div className="border-b border-slate-100 px-5 py-4">
                <h2 className="section-title">Procurement summary</h2>
                <p className="mt-1 text-xs text-slate-500">Purchase order lifecycle</p>
              </div>
              <div className="space-y-5 p-5">
                {[
                  { label: "Active orders", value: data.activeOrders.length, color: "bg-blue-500", icon: Truck },
                  { label: "Received orders", value: data.receivedOrders.length, color: "bg-emerald-500", icon: CheckCircle2 },
                  { label: "Cancelled orders", value: data.cancelledOrders.length, color: "bg-slate-400", icon: ArrowDownRight },
                ].map(({ label, value, color, icon: Icon }) => (
                  <div key={label} className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${color} bg-opacity-10`}>
                        <Icon size={18} className="text-slate-600" />
                      </span>
                      <span className="text-sm text-slate-600">{label}</span>
                    </div>
                    <span className="text-lg font-bold text-slate-900">{data.ordersAvailable ? number(value) : "—"}</span>
                  </div>
                ))}
                <Link href="/purchase-orders" className="flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-700">
                  Manage purchase orders <ArrowRight size={16} />
                </Link>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
              <div>
                <h2 className="section-title">Recent purchase orders</h2>
                <p className="mt-1 text-xs text-slate-500">Latest valid procurement records</p>
              </div>
              <Link href="/purchase-orders" className="text-xs font-semibold text-teal-700 hover:text-teal-900">
                View all orders →
              </Link>
            </div>

            {recentOrders.length === 0 ? (
              <p className="p-8 text-center text-sm text-slate-500">
                {data.ordersAvailable ? "No valid purchase orders found." : "Purchase order data is unavailable."}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[600px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500">
                    <tr>
                      <th className="px-5 py-3 font-semibold">PO number</th>
                      <th className="px-5 py-3 font-semibold">Supplier</th>
                      <th className="px-5 py-3 font-semibold">Quantity</th>
                      <th className="px-5 py-3 font-semibold">Expected delivery</th>
                      <th className="px-5 py-3 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {recentOrders.map((order) => (
                      <tr key={order.id} className="hover:bg-slate-50/70">
                        <td className="px-5 py-4 font-semibold text-slate-800">{order.po_number}</td>
                        <td className="px-5 py-4 text-slate-600">{order.supplier_name}</td>
                        <td className="px-5 py-4 text-slate-600">{number(order.ordered_quantity)}</td>
                        <td className="px-5 py-4 text-slate-600">{order.expected_delivery_date || "—"}</td>
                        <td className="px-5 py-4">
                          <span className={`status-chip ${statusClass(order.status)}`}>
                            {order.status.replaceAll("_", " ")}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Link href="/assistant" className="group rounded-xl bg-gradient-to-r from-slate-900 to-slate-800 p-5 text-white transition hover:shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold">Ask Inventra AI</p>
                  <p className="mt-1 text-xs text-slate-300">Explore stock risks, inventory and forecasts.</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10">
                  <ShieldCheck size={22} />
                </div>
              </div>
              <div className="mt-5 flex items-center gap-2 text-xs font-semibold text-teal-300">
                Open AI assistant <ArrowRight size={14} className="transition group-hover:translate-x-1" />
              </div>
            </Link>

            <Link href="/forecasting" className="group rounded-xl border border-slate-200 bg-white p-5 transition hover:border-teal-200 hover:shadow-md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-800">Demand forecasting</p>
                  <p className="mt-1 text-xs text-slate-500">Review predicted material demand and trends.</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
                  <TrendingUp size={22} />
                </div>
              </div>
              <div className="mt-5 flex items-center gap-2 text-xs font-semibold text-teal-700">
                Explore forecasts <ArrowRight size={14} className="transition group-hover:translate-x-1" />
              </div>
            </Link>
          </section>

          <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-5 text-[11px] text-slate-400">
            <span>Inventra · Inventory Intelligence</span>
            <span>Read-only dashboard · Business data from backend APIs</span>
          </footer>
        </div>
      </main>
    </AppShell>
  );
}
