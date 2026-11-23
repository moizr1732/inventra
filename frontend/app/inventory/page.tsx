
import {
  AlertTriangle,
  Boxes,
  Package,
  ShieldCheck,
} from "lucide-react";
import type { ElementType } from "react";
import InventoryTable from "./InventoryTable";

import {
  inventraApi,
  type InventoryItem,
  type StockRisk,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";

export const dynamic = "force-dynamic";

function formatNumber(value: number | string | undefined | null) {
  return Number(value ?? 0).toLocaleString("en-US", {
    maximumFractionDigits: 2,
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

async function getInventoryData(): Promise<{
  items: InventoryItem[];
  risks: Record<number, StockRisk | null>;
}> {
  try {
    const response = await inventraApi.getInventory();

    const items = (Array.isArray(response) ? response : []).filter(
      (item) =>
        item.is_active !== false &&
        item.item_code?.trim() &&
        item.item_code.toLowerCase() !== "string" &&
        item.item_name?.trim() &&
        item.item_name.toLowerCase() !== "string"
    );

    const riskResults = await Promise.all(
      items.map(async (item) => {
        try {
          const risk = await inventraApi.getStockRisk(item.id);
          return [item.id, risk] as const;
        } catch {
          return [item.id, null] as const;
        }
      })
    );

    return {
      items,
      risks: Object.fromEntries(riskResults),
    };
  } catch (error) {
    console.error("Failed to load inventory data:", error);

    return {
      items: [],
      risks: {},
    };
  }
}

export default async function InventoryPage() {
  const { items, risks } = await getInventoryData();

  const totalItems = items.length;

  const totalAvailable = items.reduce(
    (sum, item) => sum + Number(item.available_quantity ?? 0),
    0
  );

  const lowStock = items.filter((item) => {
    const risk = risks[item.id];

    return (
      risk?.requires_replenishment === true ||
      ["critical", "high"].includes(
        risk?.risk_level?.toLowerCase() ?? ""
      )
    );
  }).length;

  const normalStock = items.filter(
    (item) => risks[item.id]?.risk_level?.toLowerCase() === "normal"
  ).length;

  const normalPercentage =
    totalItems > 0 ? Math.round((normalStock / totalItems) * 100) : 0;

  return (
    <AppShell>

      <main className="min-w-0 flex-1 overflow-x-hidden">
        <header className="flex h-[76px] items-center justify-between border-b border-slate-200 bg-white px-8">
          <div>
            <p className="text-xs text-slate-400">
              Workspace /{" "}
              <span className="text-slate-700">Inventory</span>
            </p>

            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Inventory Management
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
                Inventory Overview
              </h1>

              <p className="mt-2 text-sm text-slate-500">
                Monitor stock levels, availability and replenishment risk.
              </p>
            </div>

            <div className="text-xs text-slate-400">
              Live application data
            </div>
          </section>

          <section className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              title="Total Inventory Items"
              value={formatNumber(totalItems)}
              description="Active items in the inventory"
              icon={Package}
            />

            <StatCard
              title="Available Stock"
              value={formatNumber(totalAvailable)}
              description="Combined available quantity"
              icon={Boxes}
            />

            <StatCard
              title="Items Requiring Attention"
              value={formatNumber(lowStock)}
              description="High or critical stock risk"
              icon={AlertTriangle}
            />

            <StatCard
              title="Normal Stock Items"
              value={formatNumber(normalStock)}
              description="Items currently within normal levels"
              icon={ShieldCheck}
            />
          </section>

          <InventoryTable items={items} risks={risks} />

          <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="panel p-6">
              <div className="flex items-center gap-3">
                <div className="metric-icon">
                  <ShieldCheck size={19} />
                </div>

                <div>
                  <h3 className="font-semibold text-slate-900">
                    Inventory Health
                  </h3>

                  <p className="mt-1 text-xs text-slate-500">
                    Current stock-risk assessment
                  </p>
                </div>
              </div>

              <div className="mt-6 flex items-center justify-between">
                <div>
                  <p className="text-3xl font-semibold text-slate-900">
                    {normalPercentage}%
                  </p>

                  <p className="mt-1 text-xs text-slate-500">
                    Items with normal risk
                  </p>
                </div>

                <div className="rounded-xl bg-emerald-50 p-3 text-emerald-600">
                  <ShieldCheck size={25} />
                </div>
              </div>

              <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-teal-600"
                  style={{ width: `${normalPercentage}%` }}
                />
              </div>

              <p className="mt-3 text-xs text-slate-500">
                {normalStock} of {totalItems} items currently have normal risk.
              </p>
            </div>

            <div className="panel p-6">
              <div className="flex items-center gap-3">
                <div className="metric-icon">
                  <AlertTriangle size={19} />
                </div>

                <div>
                  <h3 className="font-semibold text-slate-900">
                    Replenishment Monitoring
                  </h3>

                  <p className="mt-1 text-xs text-slate-500">
                    Items that may require procurement attention
                  </p>
                </div>
              </div>

              <div className="mt-6 flex items-center justify-between">
                <div>
                  <p className="text-3xl font-semibold text-slate-900">
                    {lowStock}
                  </p>

                  <p className="mt-1 text-xs text-slate-500">
                    Items requiring attention
                  </p>
                </div>

                <div className="rounded-xl bg-amber-50 p-3 text-amber-600">
                  <AlertTriangle size={25} />
                </div>
              </div>

              <p className="mt-5 text-xs leading-5 text-slate-500">
                Review risk assessments before making replenishment decisions.
                Procurement actions should follow the required human approval
                process.
              </p>
            </div>
          </section>

          <p className="text-center text-[11px] text-slate-400">
            Inventra · Inventory Intelligence · Synthetic demonstration data
          </p>
        </div>
      </main>
    </AppShell>
  );
}
