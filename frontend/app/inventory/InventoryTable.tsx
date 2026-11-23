
"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Package,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import type { InventoryItem, StockRisk } from "@/lib/api";

type Props = {
  items: InventoryItem[];
  risks: Record<number, StockRisk | null>;
};

function formatNumber(value: number | string | undefined | null) {
  return Number(value ?? 0).toLocaleString("en-US", {
    maximumFractionDigits: 2,
  });
}

function riskStyle(level: string) {
  switch (level.toLowerCase()) {
    case "critical":
      return "border-red-200 bg-red-50 text-red-700";
    case "high":
      return "border-orange-200 bg-orange-50 text-orange-700";
    case "medium":
      return "border-amber-200 bg-amber-50 text-amber-700";
    case "normal":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    default:
      return "border-slate-200 bg-slate-50 text-slate-500";
  }
}

export default function InventoryTable({ items, risks }: Props) {
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");

  const categories = useMemo(
    () =>
      Array.from(
        new Set(
          items
            .map((item) => item.category?.trim())
            .filter((category): category is string => Boolean(category))
        )
      ).sort(),
    [items]
  );

  const filteredItems = useMemo(() => {
    const term = search.trim().toLowerCase();

    return items.filter((item) => {
      const matchesSearch =
        !term ||
        item.item_name?.toLowerCase().includes(term) ||
        item.item_code?.toLowerCase().includes(term);

      const risk = risks[item.id];
      const level = risk?.risk_level?.toLowerCase() ?? "unavailable";

      const matchesRisk =
        riskFilter === "all" ||
        (riskFilter === "attention" &&
          (risk?.requires_replenishment === true ||
            ["critical", "high"].includes(level))) ||
        (riskFilter === "normal" && level === "normal") ||
        (riskFilter === "medium" && level === "medium") ||
        (riskFilter === "high" && level === "high") ||
        (riskFilter === "critical" && level === "critical") ||
        (riskFilter === "unavailable" && !risk);

      const matchesCategory =
        categoryFilter === "all" || item.category === categoryFilter;

      return matchesSearch && matchesRisk && matchesCategory;
    });
  }, [items, risks, search, riskFilter, categoryFilter]);

  const hasFilters =
    search.trim() !== "" ||
    riskFilter !== "all" ||
    categoryFilter !== "all";

  function clearFilters() {
    setSearch("");
    setRiskFilter("all");
    setCategoryFilter("all");
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 px-6 py-5">
        <div>
          <h3 className="text-base font-semibold text-slate-900">
            Inventory Items
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            Search and review stock positions and replenishment indicators
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
          <Package size={15} />
          {filteredItems.length} of {items.length} items
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 border-b border-slate-100 bg-white px-6 py-4 md:grid-cols-3">
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search item name or code..."
            aria-label="Search inventory"
            className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
          />
        </div>

        <div className="relative">
          <SlidersHorizontal
            size={15}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <select
            value={riskFilter}
            onChange={(event) => setRiskFilter(event.target.value)}
            aria-label="Filter by risk level"
            className="w-full appearance-none rounded-lg border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-700 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
          >
            <option value="all">All risk levels</option>
            <option value="attention">Requires attention</option>
            <option value="normal">Normal</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
            <option value="unavailable">Risk unavailable</option>
          </select>
        </div>

        <select
          value={categoryFilter}
          onChange={(event) => setCategoryFilter(event.target.value)}
          aria-label="Filter by category"
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
        >
          <option value="all">All categories</option>
          {categories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>
      </div>

      {hasFilters && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50/70 px-6 py-3">
          <p className="text-xs text-slate-500">
            Showing {filteredItems.length} matching{" "}
            {filteredItems.length === 1 ? "item" : "items"}
          </p>
          <button
            type="button"
            onClick={clearFilters}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-teal-700 hover:text-teal-900"
          >
            <X size={14} />
            Clear filters
          </button>
        </div>
      )}

      {filteredItems.length === 0 ? (
        <div className="px-6 py-16 text-center">
          <Search className="mx-auto text-slate-300" size={34} />
          <h4 className="mt-4 font-semibold text-slate-800">
            No matching inventory items
          </h4>
          <p className="mt-2 text-sm text-slate-500">
            Try another search term or adjust your filters.
          </p>
          {hasFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="mt-4 rounded-lg bg-teal-700 px-4 py-2 text-xs font-semibold text-white transition hover:bg-teal-800"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-6 py-4 font-semibold">Item</th>
                <th className="px-5 py-4 font-semibold">On Hand</th>
                <th className="px-5 py-4 font-semibold">Reserved</th>
                <th className="px-5 py-4 font-semibold">Available</th>
                <th className="px-5 py-4 font-semibold">Reorder Level</th>
                <th className="px-5 py-4 font-semibold">Lead Time</th>
                <th className="px-6 py-4 font-semibold">Risk Status</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {filteredItems.map((item) => {
                const risk = risks[item.id];
                const level = risk?.risk_level ?? "Unavailable";

                return (
                  <tr
                    key={item.id}
                    className="transition hover:bg-slate-50/80"
                  >
                    <td className="px-6 py-5">
                      <div className="font-semibold text-slate-800">
                        {item.item_name}
                      </div>
                      <div className="mt-1 text-xs text-slate-400">
                        {item.item_code} · {item.category || "Uncategorized"}
                      </div>
                    </td>
                    <td className="px-5 py-5 font-medium text-slate-700">
                      {formatNumber(item.on_hand_quantity)}
                    </td>
                    <td className="px-5 py-5 text-slate-600">
                      {formatNumber(item.reserved_quantity)}
                    </td>
                    <td className="px-5 py-5">
                      <span className="font-semibold text-slate-900">
                        {formatNumber(item.available_quantity)}
                      </span>
                      <span className="ml-1 text-xs text-slate-400">
                        {item.unit_of_measure ?? ""}
                      </span>
                    </td>
                    <td className="px-5 py-5 text-slate-600">
                      {formatNumber(item.reorder_level)}
                    </td>
                    <td className="px-5 py-5 text-slate-600">
                      {formatNumber(item.lead_time_days)} days
                    </td>
                    <td className="px-6 py-5">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${riskStyle(
                          level
                        )}`}
                      >
                        {risk ? (
                          level.toLowerCase() === "normal" ? (
                            <CheckCircle2 size={13} />
                          ) : (
                            <AlertTriangle size={13} />
                          )
                        ) : (
                          <AlertTriangle size={13} />
                        )}
                        {level}
                      </span>
                      {risk?.requires_replenishment && (
                        <p className="mt-1 text-[10px] font-medium text-amber-700">
                          Replenishment required
                        </p>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-6 py-4 text-xs text-slate-400">
        <span>
          Displaying {filteredItems.length} of {items.length} active inventory items
        </span>
        <span>Data retrieved from Inventra backend</span>
      </div>
    </section>
  );
}
