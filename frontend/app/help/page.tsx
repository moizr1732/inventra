import { AppShell } from "@/components/AppShell";

const sections = [
  {
    title: "Stock risk levels",
    items: [
      "Critical: days of cover are within the item's lead time, or no stock is available. Replenish now.",
      "Low stock: available stock is at or below the reorder point.",
      "Normal: stock covers demand beyond the lead time and is above the reorder point.",
      "Overstock: stock covers more than the overstock threshold (60 days by default).",
      "No demand data: nothing has been consumed in the analysis window, so cover cannot be calculated.",
    ],
  },
  {
    title: "How the numbers are calculated",
    items: [
      "Average daily consumption is measured over the days an item has been tracked, not over a fixed window. A new item is not made to look like it has low demand.",
      "Reorder point = average daily consumption x lead time + safety stock, never lower than the configured reorder level.",
      "Suggested order = reorder point minus inventory position. Inventory position is available stock plus open purchase orders that have not yet been received.",
      "Draft and pending purchase orders are shown as outstanding but are not counted as incoming stock until approved.",
    ],
  },
  {
    title: "Demand forecasts and planning",
    items: [
      "Forecasts use a three-period moving average over the last three complete 30-day periods.",
      "Forecast periods are fixed 30-day windows, so a manual override stays attached to its period for the whole period.",
      "A planning override replaces the AI forecast for planning only. The original AI forecast is always kept and shown alongside it.",
      "New items with less than 90 days of history, and items with no recorded consumption, show a status explaining why no forecast is available.",
    ],
  },
  {
    title: "Using the AI assistant",
    items: [
      "Ask about a specific item by name or item code, or use follow-ups such as \"Is it at risk?\" after naming an item.",
      "The assistant reads live figures from the database on every question. Earlier replies are never used as a source of current stock.",
      "Scenario questions such as \"What if demand increases by 20%?\" are simulations. They do not change any inventory record.",
      "The assistant is read-only. It cannot create, approve, change or cancel purchase orders or inventory records.",
    ],
  },
];

export default function HelpPage() {
  return (
    <AppShell>
      <main id="main-content" className="min-w-0 flex-1 px-5 py-8 sm:px-8">
        <header className="mb-8">
          <p className="text-xs font-medium text-slate-400">SUPPORT</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Help & Support</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-500">
            How to read Inventra&apos;s risk levels, forecasts and assistant answers.
          </p>
        </header>

        <div className="grid gap-5 xl:grid-cols-2">
          {sections.map((section) => (
            <section key={section.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-base font-semibold text-slate-900">{section.title}</h2>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
                {section.items.map((item) => (
                  <li key={item} className="flex gap-3">
                    <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500" aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <p className="mt-8 text-xs text-slate-400">
          Inventra demonstrates synthetic data. Recommendations require human review before any procurement decision.
        </p>
      </main>
    </AppShell>
  );
}
