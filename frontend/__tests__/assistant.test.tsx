import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AssistantPage from "@/app/assistant/page";
import { ApiError, inventraApi, type AssistantResponse } from "@/lib/api";
import { item } from "./fixtures";

vi.mock("next/navigation", () => ({ usePathname: () => "/assistant" }));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    inventraApi: {
      getHealth: vi.fn(),
      getInventory: vi.fn(),
      getConversations: vi.fn(),
      getConversationMessages: vi.fn(),
      sendAssistantMessage: vi.fn(),
      deleteConversation: vi.fn(),
    },
  };
});

const api = vi.mocked(inventraApi);

function input() {
  return screen.getByLabelText("Message the assistant") as HTMLTextAreaElement;
}

function send(text: string) {
  fireEvent.change(input(), { target: { value: text } });
  fireEvent.keyDown(input(), { key: "Enter" });
}

beforeEach(() => {
  api.getHealth.mockResolvedValue({ status: "healthy", application: "Inventra", database: "connected" });
  api.getInventory.mockResolvedValue([item({ item_name: "Cotton Fabric" })]);
  api.getConversations.mockResolvedValue([]);
  api.getConversationMessages.mockResolvedValue([]);
  api.deleteConversation.mockResolvedValue({ message: "ok", conversation_id: 1 });
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("Assistant empty state", () => {
  it("invites a question and offers starting prompts", async () => {
    render(<AssistantPage />);
    expect(await screen.findByText("Ask about your inventory")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Stock risk/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /About Cotton Fabric/ })).toBeInTheDocument();
  });

  it("says where saved conversations will appear when there are none", async () => {
    render(<AssistantPage />);
    // The conversation list renders once in the desktop sidebar and once in the mobile history panel.
    expect((await screen.findAllByText("Your saved conversations will appear here.")).length).toBeGreaterThan(0);
  });

  it("shows the real service status from the health endpoint", async () => {
    render(<AssistantPage />);
    expect(await screen.findByText("Assistant online")).toBeInTheDocument();
  });

  it("reports an unreachable backend instead of claiming the assistant is online", async () => {
    api.getHealth.mockRejectedValue(new ApiError("Cannot reach", null));
    render(<AssistantPage />);
    expect(await screen.findByText("Backend unreachable")).toBeInTheDocument();
    expect(screen.queryByText("Assistant online")).toBeNull();
  });

  it("reports a reachable backend with a failing database", async () => {
    api.getHealth.mockResolvedValue({ status: "unhealthy", application: "Inventra", database: "disconnected" });
    render(<AssistantPage />);
    expect(await screen.findByText("Database unavailable")).toBeInTheDocument();
  });
});

describe("Assistant conversation", () => {
  it("sends a suggested prompt and shows the answer with plain-language intent labels", async () => {
    api.sendAssistantMessage.mockResolvedValue({
      answer: "Stock risk for FAB-001 (Cotton Fabric): Normal.",
      intent: "risk+forecast",
      sources: ["Inventory database"],
      conversation_id: 7,
    });
    render(<AssistantPage />);
    fireEvent.click(await screen.findByRole("button", { name: /About Cotton Fabric/ }));

    expect(await screen.findByText(/Stock risk for FAB-001/)).toBeInTheDocument();
    expect(api.sendAssistantMessage).toHaveBeenCalledWith(
      "Tell me about Cotton Fabric, whether it is at risk, and its demand forecast.",
      null
    );
    expect(screen.getByText("Stock risk, Forecast")).toBeInTheDocument();
    expect(screen.getByText(/Sources: Inventory database/)).toBeInTheDocument();
    expect(screen.queryByText("Ask about your inventory")).toBeNull();
  });

  it("sends with Enter and keeps the conversation id for follow-ups", async () => {
    api.sendAssistantMessage
      .mockResolvedValueOnce({ answer: "First answer", intent: "greeting", sources: [], conversation_id: 9 })
      .mockResolvedValueOnce({ answer: "Second answer", intent: "risk", sources: [], conversation_id: 9 });
    render(<AssistantPage />);
    await screen.findByText("Ask about your inventory");

    send("Hi");
    expect(await screen.findByText("First answer")).toBeInTheDocument();
    send("Is it at risk?");
    expect(await screen.findByText("Second answer")).toBeInTheDocument();
    expect(api.sendAssistantMessage.mock.calls[1]).toEqual(["Is it at risk?", 9]);
  });

  it("does not send when Shift+Enter is pressed, so multi-line messages are possible", async () => {
    render(<AssistantPage />);
    await screen.findByText("Ask about your inventory");
    fireEvent.change(input(), { target: { value: "line one" } });
    fireEvent.keyDown(input(), { key: "Enter", shiftKey: true });
    expect(api.sendAssistantMessage).not.toHaveBeenCalled();
  });

  it("ignores blank messages", async () => {
    render(<AssistantPage />);
    await screen.findByText("Ask about your inventory");
    fireEvent.change(input(), { target: { value: "   " } });
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    fireEvent.keyDown(input(), { key: "Enter" });
    expect(api.sendAssistantMessage).not.toHaveBeenCalled();
  });

  it("shows a loading state while the answer is being prepared", async () => {
    let resolveAnswer: (value: AssistantResponse) => void = () => {};
    api.sendAssistantMessage.mockReturnValue(
      new Promise<AssistantResponse>((resolve) => {
        resolveAnswer = resolve;
      })
    );
    render(<AssistantPage />);
    await screen.findByText("Ask about your inventory");
    send("Show me the inventory overview.");
    expect(await screen.findByText("Checking the inventory data...")).toBeInTheDocument();
    expect(input()).toBeDisabled();
    resolveAnswer({ answer: "Done", intent: "inventory", sources: [], conversation_id: 2 });
    expect(await screen.findByText("Done")).toBeInTheDocument();
    expect(screen.queryByText("Checking the inventory data...")).toBeNull();
  });
});

describe("Assistant error recovery", () => {
  it("removes the unsent question, restores it to the input, and offers a retry", async () => {
    api.sendAssistantMessage.mockRejectedValue(new ApiError("Cannot reach the Inventra backend. Check that it is running.", null));
    render(<AssistantPage />);
    await screen.findByText("Ask about your inventory");
    send("Which products are at risk?");

    expect(await screen.findByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Cannot reach the Inventra backend. Check that it is running.")).toBeInTheDocument();
    // The question was not saved, so it must not look as though it was sent.
    const messageBubbles = screen.queryAllByText("Which products are at risk?").filter((el) => el.tagName !== "TEXTAREA");
    expect(messageBubbles).toHaveLength(0);
    expect(input()).toHaveValue("Which products are at risk?");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("retries the same question successfully", async () => {
    api.sendAssistantMessage
      .mockRejectedValueOnce(new ApiError("timed out", null))
      .mockResolvedValueOnce({ answer: "Recovered answer", intent: "risk", sources: [], conversation_id: 3 });
    render(<AssistantPage />);
    await screen.findByText("Ask about your inventory");
    send("Which products are at risk?");
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Recovered answer")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).toBeNull();
  });

  it("does not send a message while another is in progress", async () => {
    api.sendAssistantMessage.mockReturnValue(new Promise(() => {}));
    render(<AssistantPage />);
    await screen.findByText("Ask about your inventory");
    send("first");
    await waitFor(() => expect(input()).toBeDisabled());
    fireEvent.keyDown(input(), { key: "Enter" });
    expect(api.sendAssistantMessage).toHaveBeenCalledTimes(1);
  });
});

describe("Assistant history", () => {
  it("restores the most recent conversation on load", async () => {
    api.getConversations.mockResolvedValue([
      { id: 5, title: "Stock check", created_at: "2026-11-20T10:00:00Z", updated_at: "2026-11-20T10:05:00Z", message_count: 2 },
    ]);
    api.getConversationMessages.mockResolvedValue([
      { id: 1, role: "user", content: "Stock check question", intent: null, created_at: "2026-11-20T10:00:00Z" },
      { id: 2, role: "assistant", content: "Restored answer", intent: "inventory", created_at: "2026-11-20T10:00:01Z" },
    ]);
    render(<AssistantPage />);
    expect(await screen.findByText("Restored answer")).toBeInTheDocument();
    expect(api.getConversationMessages).toHaveBeenCalledWith(5);
    expect(screen.getAllByText("Stock check").length).toBeGreaterThan(0);
  });

  it("shows a loading message while history is restored", async () => {
    api.getConversations.mockReturnValue(new Promise(() => {}));
    render(<AssistantPage />);
    expect(await screen.findByText("Restoring your conversation...")).toBeInTheDocument();
  });

  it("reports a history failure without hiding the input", async () => {
    api.getConversations.mockRejectedValue(new ApiError("Cannot reach the Inventra backend.", null));
    render(<AssistantPage />);
    expect(await screen.findByText(/Unable to restore conversation history/)).toBeInTheDocument();
    expect(input()).not.toBeDisabled();
  });

  it("does not delete a conversation unless the user confirms", async () => {
    api.getConversations.mockResolvedValue([
      { id: 5, title: "Stock check", created_at: "2026-11-20T10:00:00Z", updated_at: "2026-11-20T10:05:00Z", message_count: 2 },
    ]);
    api.getConversationMessages.mockResolvedValue([]);
    vi.mocked(window.confirm).mockReturnValue(false);
    render(<AssistantPage />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Delete Stock check" }))[0]);
    expect(api.deleteConversation).not.toHaveBeenCalled();
  });

  it("deletes a confirmed conversation and refreshes the list", async () => {
    api.getConversations
      .mockResolvedValueOnce([{ id: 5, title: "Stock check", created_at: "2026-11-20T10:00:00Z", updated_at: "2026-11-20T10:05:00Z", message_count: 2 }])
      .mockResolvedValueOnce([]);
    api.getConversationMessages.mockResolvedValue([]);
    render(<AssistantPage />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Delete Stock check" }))[0]);
    await waitFor(() => expect(api.deleteConversation).toHaveBeenCalledWith(5));
    expect((await screen.findAllByText("Your saved conversations will appear here.")).length).toBeGreaterThan(0);
  });
});
