
"use client";

import {
  AlertTriangle,
  Package,
  ShieldCheck,
  SlidersHorizontal,
  Search,
  Truck,
  ClipboardList,
  CalendarDays,
  RefreshCw,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ElementType } from "react";
import {
  inventraApi,
  type PurchaseOrder,
  type InventoryItem,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";

function formatNumber(value: number | string | undefined | null) {
  return Number(value ?? 0).toLocaleString("en-US", {
    maximumFractionDigits: 2,
  });
}

function formatDate(value: string) {
  if (!value) return "—";

  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function StatCard({
  title,
  value,
  description,
  icon: Icon,
}: {
  title: string;
  value: string;
  description: string;
  icon: ElementType;
}) {
  return (
    <div className="metric-card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">
            {value}
          </h2>
          <p className="mt-2 text-xs text-slate-500">{description}</p>
        </div>
        <div className="metric-icon">
          <Icon size={20} />
        </div>
      </div>
    </div>
  );
}

function statusStyle(status: string) {
  switch (status.toLowerCase()) {
    case "received":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "approved":
    case "ordered":
    case "partially_received":
      return "bg-blue-50 text-blue-700 border-blue-200";
    case "pending":
      return "bg-amber-50 text-amber-700 border-amber-200";
    case "cancelled":
      return "bg-rose-50 text-rose-700 border-rose-200";
    case "draft":
      return "bg-slate-100 text-slate-600 border-slate-200";
    default:
      return "bg-slate-100 text-slate-600 border-slate-200";
  }
}

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function fetchPurchaseData() {
    const [orderData, inventoryData] = await Promise.all([
      inventraApi.getPurchaseOrders(),
      inventraApi.getInventory(),
    ]);
    return {
      orders: Array.isArray(orderData) ? orderData : [],
      inventory: Array.isArray(inventoryData) ? inventoryData : [],
    };
  }

  // Initial load. The cancelled flag stops a stale response updating an unmounted view.
  useEffect(() => {
    let cancelled = false;

    fetchPurchaseData()
      .then((data) => {
        if (cancelled) return;
        setOrders(data.orders);
        setInventory(data.inventory);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("Failed to load purchase orders:", err);
        setError(err instanceof Error ? err.message : "Unable to load purchase orders.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchPurchaseData();
      setOrders(data.orders);
      setInventory(data.inventory);
    } catch (err) {
      console.error("Failed to refresh purchase orders:", err);
      setError(err instanceof Error ? err.message : "Unable to load purchase orders.");
    } finally {
      setLoading(false);
    }
  }

  const itemNames = useMemo(() => {
    return Object.fromEntries(inventory.map((item) => [item.id, item.item_name]));
  }, [inventory]);

  const filteredOrders = useMemo(() => {
    return orders.filter((order) => {
      const query = search.trim().toLowerCase();
      const matchesSearch =
        !query ||
        order.po_number.toLowerCase().includes(query) ||
        order.supplier_name.toLowerCase().includes(query) ||
        (itemNames[order.inventory_item_id] ?? "")
          .toLowerCase()
          .includes(query);

      const matchesStatus =
        statusFilter === "all" ||
        order.status.toLowerCase() === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [orders, search, statusFilter, itemNames]);

  const activeOrders = orders.filter((order) =>
    ["draft", "pending", "approved", "ordered", "partially_received"].includes(
      order.status.toLowerCase()
    )
  ).length;

  const receivedOrders = orders.filter(
    (order) => order.status.toLowerCase() === "received"
  ).length;

  const cancelledOrders = orders.filter(
    (order) => order.status.toLowerCase() === "cancelled"
  ).length;

  const totalOrdered = orders.reduce(
    (sum, order) => sum + Number(order.ordered_quantity ?? 0),
    0
  );

  return (
    <AppShell>

      <main className="min-w-0 flex-1 overflow-x-hidden">
        <header className="flex min-h-[76px] items-center justify-between border-b border-slate-200 bg-white px-8 py-3">
          <div>
            <p className="text-xs text-slate-400">
              Workspace /{" "}
              <span className="text-slate-700">Purchase Orders</span>
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Procurement Management
            </h2>
          </div>

          <div className="flex items-center gap-3">
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700">
              Synthetic demo data
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#173A59] text-sm font-semibold text-white">
              A
            </div>
          </div>
        </header>

        <div className="mx-auto max-w-[1500px] space-y-7 p-8">
          <section className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
                Purchase Orders
              </h1>
              <p className="mt-2 text-sm text-slate-500">
                Track procurement activity, supplier orders and delivery progress.
              </p>
            </div>

            <button
              onClick={refresh}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
              Refresh data
            </button>
          </section>

          <section className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              title="Total Purchase Orders"
              value={formatNumber(orders.length)}
              description="All recorded purchase orders"
              icon={ClipboardList}
            />
            <StatCard
              title="Active Orders"
              value={formatNumber(activeOrders)}
              description="Draft, pending or in progress"
              icon={Truck}
            />
            <StatCard
              title="Received Orders"
              value={formatNumber(receivedOrders)}
              description="Orders marked as received"
              icon={ShieldCheck}
            />
            <StatCard
              title="Cancelled Orders"
              value={formatNumber(cancelledOrders)}
              description="Cancelled procurement records"
              icon={AlertTriangle}
            />
          </section>

          <section className="panel p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-slate-900">
                  Purchase Order Register
                </h3>
                <p className="mt-1 text-xs text-slate-500">
                  {filteredOrders.length} of {orders.length} records displayed
                </p>
              </div>
              <div className="text-xs text-slate-400">
                Total ordered quantity:{" "}
                <span className="font-semibold text-slate-700">
                  {formatNumber(totalOrdered)}
                </span>
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-3 md:flex-row">
              <div className="relative flex-1">
                <Search
                  size={17}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search PO number, supplier or item..."
                  className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                />
              </div>

              <div className="relative md:w-56">
                <SlidersHorizontal
                  size={16}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                  className="w-full appearance-none rounded-lg border border-slate-200 bg-white py-2.5 pl-9 pr-4 text-sm text-slate-700 outline-none focus:border-teal-500"
                >
                  <option value="all">All statuses</option>
                  <option value="draft">Draft</option>
                  <option value="pending">Pending</option>
                  <option value="approved">Approved</option>
                  <option value="ordered">Ordered</option>
                  <option value="partially_received">Partially received</option>
                  <option value="received">Received</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
            </div>

            {error && (
              <div className="mt-5 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                <AlertTriangle size={17} />
                {error}
              </div>
            )}

            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[950px] text-left">
                <thead>
                  <tr className="border-b border-slate-200 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    <th className="px-4 py-3">Purchase Order</th>
                    <th className="px-4 py-3">Supplier</th>
                    <th className="px-4 py-3">Inventory Item</th>
                    <th className="px-4 py-3">Order Date</th>
                    <th className="px-4 py-3">Delivery Date</th>
                    <th className="px-4 py-3">Ordered</th>
                    <th className="px-4 py-3">Received</th>
                    <th className="px-4 py-3">Remaining</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-12 text-center text-sm text-slate-400">
                        Loading purchase orders...
                      </td>
                    </tr>
                  ) : filteredOrders.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-12 text-center">
                        <Package size={28} className="mx-auto text-slate-300" />
                        <p className="mt-3 text-sm font-medium text-slate-600">
                          No purchase orders found
                        </p>
                        <p className="mt-1 text-xs text-slate-400">
                          Try changing your search or status filter.
                        </p>
                      </td>
                    </tr>
                  ) : (
                    filteredOrders.map((order) => {
                      return (
                        <tr
                          key={order.id}
                          className="transition hover:bg-slate-50/80"
                        >
                          <td className="px-4 py-4">
                            <p className="text-sm font-semibold text-slate-800">
                              {order.po_number}
                            </p>
                            <p className="mt-1 text-[11px] text-slate-400">
                              PO ID: {order.id}
                            </p>
                          </td>
                          <td className="px-4 py-4 text-sm text-slate-600">
                            {order.supplier_name}
                          </td>
                          <td className="px-4 py-4">
                            <p className="text-sm text-slate-700">
                              {itemNames[order.inventory_item_id] ??
                                (order.inventory_item_id === 1
                                  ? "Placeholder inventory item"
                                  : `Inventory item #${order.inventory_item_id}`)}
                            </p>
                            <p className="mt-1 text-[11px] text-slate-400">
                              Item ID: {order.inventory_item_id}
                            </p>
                          </td>
                          <td className="px-4 py-4 text-sm text-slate-600">
                            {formatDate(order.order_date)}
                          </td>
                          <td className="px-4 py-4 text-sm text-slate-600">
                            {formatDate(order.expected_delivery_date ?? "")}
                          </td>
                          <td className="px-4 py-4 text-sm font-medium text-slate-700">
                            {formatNumber(order.ordered_quantity)}
                          </td>
                          <td className="px-4 py-4 text-sm text-emerald-700">
                            {formatNumber(order.received_quantity)}
                          </td>
                          <td className="px-4 py-4 text-sm text-slate-700">
                            {formatNumber(order.remaining_quantity)}
                          </td>
                          <td className="px-4 py-4">
                            <span
                              className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize ${statusStyle(order.status)}`}
                            >
                              {order.status.replaceAll("_", " ")}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="panel p-6">
              <div className="flex items-center gap-3">
                <div className="metric-icon">
                  <Truck size={19} />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900">
                    Procurement Status
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Current distribution of order records
                  </p>
                </div>
              </div>

              <div className="mt-6 space-y-4">
                {[
                  { label: "Received", count: receivedOrders, color: "bg-emerald-500" },
                  { label: "Active", count: activeOrders, color: "bg-blue-500" },
                  { label: "Cancelled", count: cancelledOrders, color: "bg-rose-500" },
                ].map((item) => {
                  const percentage =
                    orders.length > 0
                      ? (item.count / orders.length) * 100
                      : 0;

                  return (
                    <div key={item.label}>
                      <div className="mb-2 flex justify-between text-xs">
                        <span className="font-medium text-slate-600">
                          {item.label}
                        </span>
                        <span className="text-slate-500">
                          {item.count} orders
                        </span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full ${item.color}`}
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="panel p-6">
              <div className="flex items-center gap-3">
                <div className="metric-icon">
                  <CalendarDays size={19} />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900">
                    Procurement Guidance
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Controls for responsible purchasing
                  </p>
                </div>
              </div>

              <div className="mt-6 rounded-xl border border-amber-100 bg-amber-50 p-4">
                <p className="text-sm font-semibold text-amber-800">
                  Human approval required
                </p>
                <p className="mt-2 text-xs leading-5 text-amber-700">
                  Review supplier, quantity, cost and delivery details before
                  approving procurement. This dashboard does not automatically
                  submit orders to suppliers.
                </p>
              </div>

              <p className="mt-4 text-xs leading-5 text-slate-500">
                Purchase order records shown here come from the Inventra
                demonstration database. They should not be interpreted as
                verified live AGI procurement transactions.
              </p>
            </div>
          </section>

          <p className="text-center text-[11px] text-slate-400">
            Inventra · Procurement Intelligence · Synthetic demonstration data
          </p>
        </div>
      </main>
    </AppShell>
  );
}
