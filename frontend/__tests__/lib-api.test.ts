import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, inventraApi, toNumber, type InventoryItem } from "@/lib/api";
import { item } from "./fixtures";

type FetchMock = ReturnType<typeof vi.fn>;

function jsonResponse(status: number, body: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock: FetchMock;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("error messages from the backend", () => {
  it("shows a string detail exactly as the backend wrote it", async () => {
    fetchMock.mockResolvedValue(jsonResponse(409, { detail: "An inventory item with this item code already exists." }));
    await expect(inventraApi.getStockRisk(1)).rejects.toMatchObject({
      message: "An inventory item with this item code already exists.",
      status: 409,
    });
  });

  it("joins validation messages and removes the 'Value error' prefix", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(422, {
        detail: [
          { msg: "Value error, Reserved quantity cannot exceed on-hand quantity." },
          { msg: "Value error, These fields cannot be cleared: reorder_level." },
        ],
      })
    );
    const error = await inventraApi.getStockRisk(1).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe(
      "Reserved quantity cannot exceed on-hand quantity. These fields cannot be cleared: reorder_level."
    );
  });

  it("falls back to the status code when the body is not JSON", async () => {
    fetchMock.mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 }));
    await expect(inventraApi.getHealth()).rejects.toMatchObject({
      message: "Request failed with status 502.",
      status: 502,
    });
  });

  it("explains an unreachable backend in plain language", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(inventraApi.getHealth()).rejects.toMatchObject({
      message: "Cannot reach the Inventra backend. Check that it is running.",
      status: null,
    });
  });

  it("times out a stalled request instead of waiting forever", async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError"))
          );
        })
    );
    const pending = inventraApi.getPurchaseOrders().catch((e) => e);
    await vi.advanceTimersByTimeAsync(15_000);
    const error = await pending;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("The request timed out. Please try again.");
  });

  it("gives the assistant a longer timeout than ordinary requests", async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        })
    );
    const pending = inventraApi.sendAssistantMessage("Hi").catch((e) => e);
    await vi.advanceTimersByTimeAsync(20_000);
    expect(fetchMock.mock.calls.length).toBe(1);
    await vi.advanceTimersByTimeAsync(10_000);
    expect((await pending).message).toBe("The request timed out. Please try again.");
  });
});

describe("request shape", () => {
  it("sends the assistant message and conversation id as JSON", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { answer: "ok", intent: "greeting", sources: [], conversation_id: 4 }));
    await inventraApi.sendAssistantMessage("Hi", 4);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/assistant\/chat$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ message: "Hi", conversation_id: 4 });
  });

  it("omits conversation_id when starting a new conversation", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { answer: "ok", intent: "greeting", sources: [], conversation_id: 1 }));
    await inventraApi.sendAssistantMessage("Hi", null);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ message: "Hi" });
  });

  it("treats a 204 response as success with no body", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(inventraApi.deleteConversation(3).catch((e) => e)).resolves.toBeUndefined();
  });

  it("never caches API responses", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, []));
    await inventraApi.getConversations();
    expect(fetchMock.mock.calls[0][1].cache).toBe("no-store");
  });
});

describe("inventory pagination", () => {
  it("follows pages until a short page signals the end", async () => {
    const firstPage: InventoryItem[] = Array.from({ length: 500 }, (_, i) =>
      item({ id: i + 1, item_code: `IT-${i + 1}` })
    );
    const secondPage = [item({ id: 501, item_code: "IT-501" }), item({ id: 502, item_code: "IT-502" })];
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, firstPage))
      .mockResolvedValueOnce(jsonResponse(200, secondPage));

    const items = await inventraApi.getInventory();

    expect(items).toHaveLength(502);
    expect(fetchMock.mock.calls[0][0]).toMatch(/skip=0&limit=500$/);
    expect(fetchMock.mock.calls[1][0]).toMatch(/skip=500&limit=500$/);
  });

  it("stops after one request when the first page is short", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, [item()]));
    expect(await inventraApi.getInventory()).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("toNumber", () => {
  it("reads decimal strings and numbers", () => {
    expect(toNumber("850.000")).toBe(850);
    expect(toNumber(12)).toBe(12);
  });

  it("returns 0 for missing or non-numeric values rather than NaN", () => {
    expect(toNumber(null)).toBe(0);
    expect(toNumber(undefined)).toBe(0);
    expect(toNumber("not a number")).toBe(0);
  });
});
