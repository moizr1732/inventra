import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ForecastingPage from "@/app/forecasting/page";
import { ApiError, inventraApi } from "@/lib/api";
import { forecast, item } from "./fixtures";

vi.mock("next/navigation", () => ({ usePathname: () => "/forecasting" }));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    inventraApi: { getInventory: vi.fn(), getForecast: vi.fn() },
  };
});

const api = vi.mocked(inventraApi);

async function renderPage() {
  render(await ForecastingPage());
}

function metricValue(title: string) {
  const text = document.body.textContent ?? "";
  return text.match(new RegExp(`${title}\\s*([\\d,]+)`))?.[1];
}

beforeEach(() => {
  api.getInventory.mockResolvedValue([
    item({ id: 1, item_code: "FAB-001", item_name: "Cotton Fabric" }),
    item({ id: 2, item_code: "SLK-100", item_name: "Silk Blend", unit_of_measure: "kg" }),
  ]);
  api.getForecast.mockImplementation(async (id: number) => {
    if (id === 1) return forecast({ item_id: 1 });
    return forecast({
      item_id: 2,
      item_code: "SLK-100",
      item_name: "Silk Blend",
      unit_of_measure: "kg",
      status: "insufficient_data",
      status_message: "SLK-100: consumption has only been tracked since 2026-11-10.",
      average_monthly_demand: null,
      forecasts: [],
    });
  });
});

describe("Forecasting page", () => {
  it("counts items by forecast status rather than adding quantities across units", async () => {
    await renderPage();
    expect(metricValue("Forecasted Items")).toBe("1");
    expect(metricValue("Awaiting History")).toBe("1");
    expect(screen.queryByText("Average Monthly Demand")).toBeNull();
    expect(screen.queryByText("90-Day Predicted Demand")).toBeNull();
  });

  it("explains why an item has no forecast, in the backend's own words", async () => {
    await renderPage();
    expect(screen.getByText(/consumption has only been tracked since 2026-11-10/)).toBeInTheDocument();
  });

  it("labels chart values with the item's own unit", async () => {
    await renderPage();
    // Each chart carries the unit in its label.
    expect(screen.getAllByText(/Demand quantity \(m\)/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/meters/)).toBeNull();
  });

  it("shows an empty dash instead of a zero for an item with no average", async () => {
    api.getInventory.mockResolvedValue([item({ id: 2, item_code: "SLK-100", item_name: "Silk Blend", unit_of_measure: "kg" })]);
    api.getForecast.mockResolvedValue(
      forecast({ item_id: 2, status: "insufficient_data", average_monthly_demand: null, forecasts: [], status_message: "new item" })
    );
    await renderPage();
    expect(screen.getByText("new item")).toBeInTheDocument();
    expect(screen.queryByText("0 kg")).toBeNull();
  });

  it("reports a failed inventory load clearly instead of rendering an empty page silently", async () => {
    api.getInventory.mockRejectedValue(new ApiError("down", null));
    await renderPage();
    expect(screen.getByText("Unable to connect to the forecasting service.")).toBeInTheDocument();
  });

  it("keeps the other items when one forecast request fails", async () => {
    api.getForecast.mockImplementation(async (id: number) => {
      if (id === 2) throw new ApiError("Request failed with status 500.", 500);
      return forecast({ item_id: 1 });
    });
    await renderPage();
    expect(metricValue("Forecasted Items")).toBe("1");
  });
});
