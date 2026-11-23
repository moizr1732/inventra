
import {
  AlertTriangle,
  Boxes,
  CalendarDays,
  Package,
  ShieldCheck,
  SlidersHorizontal,
  TrendingUp,
  Activity,
} from "lucide-react";
import Link from "next/link";
import type { ElementType } from "react";

import {
  inventraApi,
  type InventoryItem,
  type ForecastResponse,
} from "@/lib/api";

export const dynamic = "force-dynamic";

function formatNumber(value: number | string | undefined | null) {
  return Number(value ?? 0).toLocaleString("en-US", {
    maximumFractionDigits: 2,
  });
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-US", {
    day: "numeric",
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

function Sidebar() {
  const sections = [
    {
      title: "WORKSPACE",
      links: [
        { label: "Dashboard", href: "/", icon: Boxes },
        { label: "Inventory", href: "/inventory", icon: Package },
        { label: "Forecasting", href: "/forecasting", icon: TrendingUp },
        {
          label: "Purchase Orders",
          href: "/purchase-orders",
          icon: SlidersHorizontal,
        },
        { label: "AI Assistant", href: "/assistant", icon: ShieldCheck },
      ],
    },
    {
      title: "MANAGEMENT",
      links: [
        { label: "Activity", href: "/activity", icon: Activity },
        { label: "Settings", href: "/settings", icon: SlidersHorizontal },
        { label: "Help & Support", href: "/help", icon: AlertTriangle },
      ],
    },
  ];

  return (
    <aside className="sidebar sticky top-0 flex h-screen w-64 shrink-0 self-start flex-col">
      <div className="border-b border-white/10 px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-500 text-white">
            <Boxes size={22} />
          </div>

          <div>
            <h1 className="text-xl font-bold tracking-wide text-white">
              INVENTRA
            </h1>
            <p className="text-xs text-slate-400">
              Inventory Intelligence
            </p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-8 overflow-y-auto px-4 py-7">
        {sections.map((section) => (
          <div key={section.title}>
            <p className="mb-3 px-3 text-[10px] font-semibold tracking-[0.16em] text-slate-400">
              {section.title}
            </p>

            <div className="space-y-1">
              {section.links.map((item) => {
                const Icon = item.icon;
                const active = item.href === "/forecasting";

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`sidebar-link flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                      active
                        ? "bg-white/10 font-semibold text-white"
                        : "text-slate-300 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <Icon size={17} />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-white/10 px-6 py-5">
        <p className="text-xs font-medium text-slate-300">
          Inventra Platform
        </p>
        <p className="mt-1 text-[11px] text-slate-500">
          Demo environment
        </p>
      </div>
    </aside>
  );
}

async function getForecastData(): Promise<{
  forecasts: ForecastResponse[];
  errors: string[];
}> {
  try {
    const response = await inventraApi.getInventory();

    const items: InventoryItem[] = (
      Array.isArray(response) ? response : []
    ).filter(
      (item) =>
        item.is_active !== false &&
        item.item_code?.trim() &&
        item.item_code.toLowerCase() !== "string" &&
        item.item_name?.trim() &&
        item.item_name.toLowerCase() !== "string"
    );

    const results = await Promise.all(
      items.map(async (item) => {
        try {
          return await inventraApi.getForecast(item.id);
        } catch (error) {
          console.error(
            `Forecast failed for inventory item ${item.id}:`,
            error
          );
          return null;
        }
      })
    );

    const forecasts = results.filter(
      (item): item is ForecastResponse => item !== null
    );

    const errors =
      forecasts.length < items.length
        ? [`${items.length - forecasts.length} item forecast(s) could not be loaded.`]
        : [];

    return { forecasts, errors };
  } catch (error) {
    console.error("Failed to load forecast data:", error);

    return {
      forecasts: [],
      errors: ["Unable to connect to the forecasting service."],
    };
  }
}

function DemandChart({
  title,
  subtitle,
  values,
  labels,
  color,
}: {
  title: string;
  subtitle: string;
  values: number[];
  labels: string[];
  color: "teal" | "blue";
}) {
  const maxValue = Math.max(...values, 1);

  const barColor =
    color === "teal" ? "bg-teal-600" : "bg-blue-600";

  return (
    <div className="panel p-6">
      <div>
        <h3 className="font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
      </div>

      {values.length > 0 ? (
        <>
          <div className="mt-8 flex h-52 items-end gap-4 border-b border-slate-100 px-2">
            {values.map((value, index) => {
              const height = Math.max(
                8,
                (value / maxValue) * 100
              );

              return (
                <div
                  key={`${labels[index]}-${index}`}
                  className="flex h-full min-w-0 flex-1 flex-col items-center justify-end"
                >
                  <span className="mb-2 text-[10px] font-semibold text-slate-600">
                    {formatNumber(value)}
                  </span>

                  <div className="flex h-[75%] w-full items-end justify-center">
                    <div
                      className={`w-full max-w-16 rounded-t-lg ${barColor} transition-all`}
                      style={{ height: `${height}%` }}
                    />
                  </div>

                  <span className="mt-3 min-h-8 text-center text-[10px] text-slate-500">
                    {labels[index]}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-sm ${barColor}`}
            />
            <span className="text-xs text-slate-500">
              Demand quantity (meters)
            </span>
          </div>
        </>
      ) : (
        <div className="py-16 text-center text-sm text-slate-400">
          No demand data available.
        </div>
      )}
    </div>
  );
}

function ForecastCard({
  forecast,
}: {
  forecast: ForecastResponse;
}) {
  const totalForecast = forecast.forecasts.reduce(
    (sum, period) => sum + period.predicted_demand,
    0
  );

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 p-6">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-slate-900">
              {forecast.item_name}
            </h3>

            <span className="rounded-full bg-teal-50 px-2.5 py-1 text-[10px] font-semibold text-teal-700">
              {forecast.item_code}
            </span>
          </div>

          <p className="mt-1 text-xs text-slate-500">
            {forecast.forecast_horizon}
          </p>
        </div>

        <div className="text-right">
          <p className="text-xs text-slate-500">
            Total predicted demand
          </p>
          <p className="mt-1 text-xl font-semibold text-slate-900">
            {formatNumber(totalForecast)} m
          </p>
        </div>
      </div>

      <div className="p-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {forecast.forecasts.map((period) => (
            <div
              key={period.forecast_period}
              className="rounded-xl border border-slate-200 bg-slate-50 p-5"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">
                  PERIOD {period.forecast_period}
                </span>

                <CalendarDays
                  size={17}
                  className="text-teal-600"
                />
              </div>

              <p className="mt-4 text-2xl font-semibold text-slate-900">
                {formatNumber(period.predicted_demand)}
                <span className="ml-1 text-sm font-normal text-slate-500">
                  m
                </span>
              </p>

              <p className="mt-2 text-xs text-slate-500">
                {formatDate(period.start_date)}
              </p>

              <p className="text-xs text-slate-500">
                to {formatDate(period.end_date)}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-lg border border-blue-100 bg-blue-50/60 p-4">
          <div className="flex items-start gap-3">
            <Activity
              size={18}
              className="mt-0.5 shrink-0 text-blue-600"
            />

            <div>
              <p className="text-sm font-medium text-slate-800">
                Forecasting insight
              </p>

              <p className="mt-1 text-xs leading-5 text-slate-600">
                Average monthly historical demand is{" "}
                <strong>
                  {formatNumber(forecast.average_monthly_demand)} m
                </strong>
                . The backend currently predicts the demand shown above
                for each upcoming 30-day period.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default async function ForecastingPage() {
  const { forecasts, errors } = await getForecastData();

  const totalItems = forecasts.length;

  const averageMonthlyDemand =
    totalItems > 0
      ? forecasts.reduce(
          (sum, item) => sum + item.average_monthly_demand,
          0
        ) / totalItems
      : 0;

  const totalPredictedDemand = forecasts.reduce(
    (sum, item) =>
      sum +
      item.forecasts.reduce(
        (periodSum, period) => periodSum + period.predicted_demand,
        0
      ),
    0
  );

  const firstForecast = forecasts[0];

  const historicalValues =
    firstForecast?.historical_demand ?? [];

  const forecastValues =
    firstForecast?.forecasts.map(
      (period) => period.predicted_demand
    ) ?? [];

  const historicalLabels = historicalValues.map(
    (_, index) => `History ${index + 1}`
  );

  const forecastLabels =
    firstForecast?.forecasts.map(
      (period) => `Period ${period.forecast_period}`
    ) ?? [];

  return (
    <div className="flex min-h-screen bg-[#F5F7FA]">
      <Sidebar />

      <main className="min-w-0 flex-1 overflow-x-hidden">
        <header className="flex h-[76px] items-center justify-between border-b border-slate-200 bg-white px-8">
          <div>
            <p className="text-xs text-slate-400">
              Workspace /{" "}
              <span className="text-slate-700">Forecasting</span>
            </p>

            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Demand Forecasting
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
                Demand Intelligence
              </h1>

              <p className="mt-2 text-sm text-slate-500">
                Review historical consumption and upcoming demand predictions.
              </p>
            </div>

            <div className="text-xs text-slate-400">
              Backend-generated forecasts
            </div>
          </section>

          <section className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              title="Forecasted Items"
              value={formatNumber(totalItems)}
              description="Active items with forecast data"
              icon={Package}
            />

            <StatCard
              title="Average Monthly Demand"
              value={`${formatNumber(averageMonthlyDemand)} m`}
              description="Average across forecasted items"
              icon={Activity}
            />

            <StatCard
              title="90-Day Predicted Demand"
              value={`${formatNumber(totalPredictedDemand)} m`}
              description="Combined three-period forecast"
              icon={TrendingUp}
            />

            <StatCard
              title="Forecast Horizon"
              value={firstForecast ? "90 Days" : "N/A"}
              description="Three upcoming 30-day periods"
              icon={CalendarDays}
            />
          </section>

          {errors.map((error) => (
            <div
              key={error}
              className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
            >
              {error}
            </div>
          ))}

          {firstForecast && (
            <section className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <DemandChart
                title="Historical Demand"
                subtitle="Previously recorded demand observations"
                values={historicalValues}
                labels={historicalLabels}
                color="blue"
              />

              <DemandChart
                title="Predicted Demand"
                subtitle="Backend forecast for upcoming 30-day periods"
                values={forecastValues}
                labels={forecastLabels}
                color="teal"
              />
            </section>
          )}

          <section className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Item Forecast Details
              </h2>

              <p className="mt-1 text-xs text-slate-500">
                Individual demand projections for active inventory items.
              </p>
            </div>

            {forecasts.length > 0 ? (
              forecasts.map((forecast) => (
                <ForecastCard
                  key={forecast.item_id}
                  forecast={forecast}
                />
              ))
            ) : (
              <div className="panel p-12 text-center">
                <AlertTriangle
                  size={30}
                  className="mx-auto text-slate-400"
                />

                <h3 className="mt-4 font-semibold text-slate-800">
                  Forecast data unavailable
                </h3>

                <p className="mt-2 text-sm text-slate-500">
                  Check that the backend is running and inventory items
                  have valid forecast records.
                </p>
              </div>
            )}
          </section>

          <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
            <div className="flex items-start gap-3">
              <AlertTriangle
                size={19}
                className="mt-0.5 shrink-0 text-amber-600"
              />

              <div>
                <h3 className="text-sm font-semibold text-amber-900">
                  Forecast interpretation
                </h3>

                <p className="mt-1 text-xs leading-5 text-amber-800">
                  These are backend-generated demonstration predictions,
                  not verified actual demand or guaranteed procurement
                  requirements. Review inventory levels, open purchase
                  orders and human approval requirements before making
                  purchasing decisions.
                </p>
              </div>
            </div>
          </section>

          <p className="text-center text-[11px] text-slate-400">
            Inventra · Demand Intelligence · Synthetic demonstration data
          </p>
        </div>
      </main>
    </div>
  );
}
