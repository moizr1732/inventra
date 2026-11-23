"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  AlertCircle,
  ArrowRight,
  Bot,
  Clock3,
  History,
  Loader2,
  MessageSquare,
  Plus,
  Send,
  Sparkles,
  Trash2,
  User,
} from "lucide-react";
import { AppShell, InlineNotice } from "@/components/AppShell";
import {
  inventraApi,
  type AssistantConversation,
  type AssistantResponse,
  type InventoryItem,
} from "@/lib/api";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  intent?: string;
  sources?: string[];
};

type ServiceState = "checking" | "online" | "degraded" | "offline";

// Message ids only need to be unique within this page. They are assigned in
// event handlers, never during render.
let messageSequence = 0;
function nextMessageId() {
  messageSequence += 1;
  return messageSequence;
}

const INTENT_LABELS: Record<string, string> = {
  risk: "Stock risk",
  forecast: "Forecast",
  planning: "Planning demand",
  purchase_orders: "Purchase orders",
  inventory: "Inventory",
  valuation: "Valuation",
  scenario: "What-if",
  greeting: "Greeting",
  help: "Help",
  clarification: "Clarification",
  unsupported: "Not supported",
  unsupported_action: "Read-only",
  how_are_you: "Small talk",
  thanks: "Thanks",
  farewell: "Goodbye",
  acknowledgement: "Acknowledgement",
  identity: "About",
};

/** "risk+forecast" -> "Stock risk, Forecast" */
function formatIntent(intent: string) {
  return intent
    .split("+")
    .map((part) => INTENT_LABELS[part] ?? part.replaceAll("_", " "))
    .join(", ");
}

function formatConversationDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function toMessage(saved: { id: number; role: "user" | "assistant"; content: string; intent: string | null }): Message {
  return {
    id: saved.id,
    role: saved.role,
    content: saved.content,
    intent: saved.intent ?? undefined,
  };
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastFailedMessage, setLastFailedMessage] = useState("");

  const [conversationId, setConversationId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<AssistantConversation[]>([]);
  // Starts true because the page restores history on mount.
  const [historyLoading, setHistoryLoading] = useState(true);
  const [deletingConversationId, setDeletingConversationId] = useState<number | null>(null);

  const [service, setService] = useState<ServiceState>("checking");
  const [firstItem, setFirstItem] = useState<InventoryItem | null>(null);

  const messageEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Restore the most recently updated conversation.
  useEffect(() => {
    let cancelled = false;

    async function restoreLatestConversation() {
      try {
        const history = await inventraApi.getConversations();
        if (cancelled) return;
        setConversations(history);

        if (history.length > 0) {
          const latest = history[0];
          const saved = await inventraApi.getConversationMessages(latest.id);
          if (cancelled) return;
          setConversationId(latest.id);
          setMessages(saved.map(toMessage));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? `Unable to restore conversation history. ${err.message}` : "Unable to restore conversation history.");
        }
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    }

    restoreLatestConversation();
    return () => {
      cancelled = true;
    };
  }, []);

  // Service status is checked against the real health endpoint, not assumed.
  useEffect(() => {
    let cancelled = false;

    inventraApi
      .getHealth()
      .then((health) => {
        if (!cancelled) setService(health.database === "connected" ? "online" : "degraded");
      })
      .catch(() => {
        if (!cancelled) setService("offline");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Suggestions use a real item name when one exists, instead of a hardcoded code.
  useEffect(() => {
    let cancelled = false;

    inventraApi
      .getInventory()
      .then((items) => {
        if (!cancelled && items.length > 0) setFirstItem(items[0]);
      })
      .catch(() => {
        // Suggestions fall back to generic prompts; the page is still usable.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function refreshConversationHistory() {
    try {
      setConversations(await inventraApi.getConversations());
    } catch (err) {
      console.error("Unable to refresh conversation history:", err);
    }
  }

  async function openConversation(id: number) {
    if (loading || historyLoading || id === conversationId) return;

    setLoading(true);
    setError("");
    setLastFailedMessage("");

    try {
      const saved = await inventraApi.getConversationMessages(id);
      setConversationId(id);
      setMessages(saved.map(toMessage));
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open this conversation.");
    } finally {
      setLoading(false);
    }
  }

  function startNewConversation() {
    if (loading) return;
    setConversationId(null);
    setMessages([]);
    setInput("");
    setError("");
    setLastFailedMessage("");
  }

  async function deleteConversation(id: number) {
    if (loading || deletingConversationId !== null) return;
    if (!window.confirm("Delete this conversation permanently? This cannot be undone.")) return;

    setDeletingConversationId(id);
    setError("");

    try {
      await inventraApi.deleteConversation(id);
      if (conversationId === id) startNewConversation();
      await refreshConversationHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete this conversation.");
    } finally {
      setDeletingConversationId(null);
    }
  }

  async function sendMessage(messageText: string, event?: FormEvent) {
    event?.preventDefault();

    const trimmed = messageText.trim();
    if (!trimmed || loading || historyLoading) return;

    const userMessageId = nextMessageId();
    setMessages((previous) => [...previous, { id: userMessageId, role: "user", content: trimmed }]);
    setInput("");
    setError("");
    setLastFailedMessage("");
    setLoading(true);

    try {
      const response: AssistantResponse = await inventraApi.sendAssistantMessage(trimmed, conversationId);

      setConversationId(response.conversation_id);
      setMessages((previous) => [
        ...previous,
        {
          id: nextMessageId(),
          role: "assistant",
          content: response.answer,
          intent: response.intent,
          sources: response.sources,
        },
      ]);
      setService("online");
      await refreshConversationHistory();
    } catch (err) {
      // The backend saves nothing for a failed turn, so the question is removed
      // from the transcript and returned to the input rather than shown as sent.
      setMessages((previous) => previous.filter((message) => message.id !== userMessageId));
      setInput(trimmed);
      setLastFailedMessage(trimmed);
      setError(err instanceof Error ? err.message : "Unable to reach the assistant. Please try again.");
      if (err instanceof Error && /cannot reach|timed out/i.test(err.message)) setService("offline");
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter inserts a line; IME composition is left alone.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      sendMessage(input);
    }
  }

  const suggestions = [
    {
      title: "Stock risk",
      description: "Which products are at risk of running out?",
      prompt: "Which products are at risk of running out?",
    },
    {
      title: "Inventory overview",
      description: "See available and on-hand stock",
      prompt: "Show me the inventory overview.",
    },
    {
      title: "Purchase orders",
      description: "Outstanding orders and their status",
      prompt: "Show outstanding purchase orders.",
    },
    firstItem
      ? {
          title: `About ${firstItem.item_name}`,
          description: "Stock risk and demand forecast",
          prompt: `Tell me about ${firstItem.item_name}, whether it is at risk, and its demand forecast.`,
        }
      : {
          title: "Demand forecast",
          description: "Ask about a specific item",
          prompt: "What is the demand forecast for an item? I will name it next.",
        },
  ];

  const statusStyles: Record<ServiceState, { dot: string; label: string }> = {
    checking: { dot: "bg-slate-400", label: "Checking service" },
    online: { dot: "bg-emerald-500", label: "Assistant online" },
    degraded: { dot: "bg-amber-500", label: "Database unavailable" },
    offline: { dot: "bg-red-500", label: "Backend unreachable" },
  };
  const status = statusStyles[service];

  const conversationList = historyLoading ? (
    <div className="flex items-center gap-2 px-3 py-3 text-xs text-slate-400">
      <Loader2 size={14} className="animate-spin" aria-hidden="true" />
      Loading history...
    </div>
  ) : conversations.length === 0 ? (
    <p className="px-3 py-3 text-xs leading-5 text-slate-500">Your saved conversations will appear here.</p>
  ) : (
    conversations.map((conversation) => {
      const active = conversationId === conversation.id;
      return (
        <div
          key={conversation.id}
          className={`group flex items-center gap-1 rounded-xl px-2 py-2 transition ${
            active ? "bg-slate-100" : "hover:bg-slate-50"
          }`}
        >
          <button
            type="button"
            onClick={() => openConversation(conversation.id)}
            disabled={loading || historyLoading}
            aria-current={active ? "true" : undefined}
            className="min-w-0 flex-1 rounded-md text-left disabled:opacity-50"
          >
            <span className={`block truncate px-1 text-xs font-medium ${active ? "text-slate-900" : "text-slate-700"}`}>
              {conversation.title}
            </span>
            <span className="mt-1 flex items-center gap-1 px-1 text-[10px] text-slate-400">
              <Clock3 size={10} aria-hidden="true" />
              {formatConversationDate(conversation.updated_at)}
              <span aria-hidden="true">·</span>
              {conversation.message_count} messages
            </span>
          </button>

          <button
            type="button"
            onClick={() => deleteConversation(conversation.id)}
            disabled={deletingConversationId !== null || loading}
            title="Delete conversation"
            aria-label={`Delete ${conversation.title}`}
            // Always visible on touch screens, revealed on hover for pointers.
            className="rounded-md p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600 focus-visible:opacity-100 disabled:opacity-30 md:opacity-0 md:group-hover:opacity-100"
          >
            {deletingConversationId === conversation.id ? (
              <Loader2 size={13} className="animate-spin" aria-hidden="true" />
            ) : (
              <Trash2 size={13} aria-hidden="true" />
            )}
          </button>
        </div>
      );
    })
  );

  return (
    <AppShell>
      <div className="flex min-h-0 min-w-0 flex-1">
        <aside className="hidden w-72 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-4">
            <div className="flex items-center gap-2">
              <History size={15} className="text-slate-400" aria-hidden="true" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Conversations</h2>
            </div>
            <button
              type="button"
              onClick={startNewConversation}
              disabled={loading || historyLoading}
              title="Start a new conversation"
              aria-label="Start a new conversation"
              className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-100 disabled:opacity-40"
            >
              <Plus size={17} aria-hidden="true" />
            </button>
          </div>
          <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">{conversationList}</div>
          <div className="border-t border-slate-100 p-4">
            <div className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${status.dot}`} aria-hidden="true" />
              <span className="text-xs font-medium text-slate-600">{status.label}</span>
            </div>
          </div>
        </aside>

        <main id="main-content" className="flex min-w-0 flex-1 flex-col">
          <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-5 py-4 sm:px-8">
            <div>
              <h1 className="text-lg font-bold text-slate-900">AI Assistant</h1>
              <p className="text-xs text-slate-500">Read-only answers from live inventory data</p>
            </div>

            <div className="flex items-center gap-2">
              <details className="relative md:hidden">
                <summary className="flex cursor-pointer list-none items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600">
                  <History size={14} aria-hidden="true" />
                  History
                </summary>
                <div className="absolute right-0 z-20 mt-2 max-h-80 w-72 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
                  {conversationList}
                </div>
              </details>

              <button
                type="button"
                onClick={startNewConversation}
                disabled={loading || historyLoading || (messages.length === 0 && conversationId === null)}
                className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Plus size={15} aria-hidden="true" />
                <span className="hidden sm:inline">New conversation</span>
              </button>
            </div>
          </header>

          <div className="flex min-h-0 flex-1 flex-col">
            <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col overflow-y-auto px-4 py-6 sm:px-8">
              {historyLoading ? (
                <div className="flex flex-1 items-center justify-center gap-3 text-sm text-slate-500">
                  <Loader2 size={20} className="animate-spin text-[#0F9488]" aria-hidden="true" />
                  Restoring your conversation...
                </div>
              ) : messages.length === 0 ? (
                <div className="flex flex-1 flex-col justify-center">
                  <div className="mx-auto mb-8 max-w-xl text-center">
                    <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-50 text-[#0F9488]">
                      <Sparkles size={26} aria-hidden="true" />
                    </div>
                    <h2 className="text-2xl font-bold tracking-tight text-slate-900">Ask about your inventory</h2>
                    <p className="mt-3 text-sm leading-6 text-slate-500">
                      Stock levels, risks, reorder quantities, forecasts and purchase orders. Answers come from live data.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {suggestions.map((suggestion) => (
                      <button
                        key={suggestion.title}
                        type="button"
                        onClick={() => sendMessage(suggestion.prompt)}
                        disabled={loading}
                        className="group rounded-xl border border-slate-200 bg-white p-4 text-left transition hover:border-teal-300 hover:shadow-md disabled:opacity-50"
                      >
                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-sm font-semibold text-slate-900">{suggestion.title}</span>
                          <ArrowRight size={16} className="text-slate-400 transition group-hover:translate-x-1 group-hover:text-[#0F9488]" aria-hidden="true" />
                        </div>
                        <p className="text-xs leading-5 text-slate-500">{suggestion.description}</p>
                      </button>
                    ))}
                  </div>

                  <p className="mt-7 text-center text-[11px] text-slate-400">
                    Recommendations are for review. Inventra cannot place or approve orders.
                  </p>
                </div>
              ) : (
                <ol className="flex flex-col gap-5 pb-4" aria-live="polite">
                  {messages.map((message) => {
                    const isUser = message.role === "user";
                    return (
                      <li key={message.id} className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
                        {!isUser && (
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-[#0F9488]">
                            <Bot size={17} aria-hidden="true" />
                          </div>
                        )}

                        <div
                          className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                            isUser
                              ? "rounded-tr-sm bg-[#173A59] text-white"
                              : "rounded-tl-sm border border-slate-200 bg-white text-slate-800 shadow-sm"
                          }`}
                        >
                          <p className={`mb-1 text-[10px] font-semibold uppercase tracking-wider ${isUser ? "text-slate-300" : "text-[#0F9488]"}`}>
                            {isUser ? "You" : "Inventra AI"}
                          </p>
                          <p className="whitespace-pre-wrap break-words text-sm leading-6">{message.content}</p>

                          {!isUser && message.intent && (
                            <div className="mt-3 border-t border-slate-100 pt-2">
                              <span className="rounded-md bg-teal-50 px-2 py-0.5 text-[10px] font-medium text-teal-700">
                                {formatIntent(message.intent)}
                              </span>
                              {message.sources && message.sources.length > 0 && (
                                <p className="mt-1.5 text-[10px] text-slate-400">Sources: {message.sources.join(", ")}</p>
                              )}
                            </div>
                          )}
                        </div>

                        {isUser && (
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#173A59] text-white">
                            <User size={16} aria-hidden="true" />
                          </div>
                        )}
                      </li>
                    );
                  })}

                  {loading && (
                    <li className="flex items-start gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-50 text-[#0F9488]">
                        <Bot size={17} aria-hidden="true" />
                      </div>
                      <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
                        <div className="flex items-center gap-2 text-sm text-slate-500">
                          <Loader2 size={15} className="animate-spin text-[#0F9488]" aria-hidden="true" />
                          Checking the inventory data...
                        </div>
                      </div>
                    </li>
                  )}
                  <div ref={messageEndRef} />
                </ol>
              )}

              {error && (
                <div className="mt-4">
                  <InlineNotice>
                    <p className="font-semibold">Something went wrong</p>
                    <p className="mt-1 text-xs leading-5">{error}</p>
                    {lastFailedMessage && (
                      <button
                        type="button"
                        onClick={() => sendMessage(lastFailedMessage)}
                        disabled={loading}
                        className="mt-2 text-xs font-semibold underline disabled:opacity-50"
                      >
                        Try again
                      </button>
                    )}
                  </InlineNotice>
                </div>
              )}
            </div>

            <div className="shrink-0 border-t border-slate-200 bg-white px-4 py-4 sm:px-8">
              <form
                onSubmit={(event) => sendMessage(input, event)}
                className="mx-auto flex max-w-4xl items-end gap-3 rounded-2xl border border-slate-200 bg-[#F8FAFC] p-2 focus-within:border-teal-400 focus-within:ring-2 focus-within:ring-teal-100"
              >
                <div className="flex h-10 w-8 shrink-0 items-center justify-center text-slate-400">
                  <MessageSquare size={18} aria-hidden="true" />
                </div>

                <label htmlFor="assistant-input" className="sr-only">
                  Message the assistant
                </label>
                <textarea
                  id="assistant-input"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about stock levels, risks, forecasts or purchase orders..."
                  rows={1}
                  maxLength={1000}
                  disabled={loading || historyLoading}
                  className="max-h-32 min-h-10 flex-1 resize-none bg-transparent py-2 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-50"
                />

                <button
                  type="submit"
                  disabled={!input.trim() || loading || historyLoading}
                  aria-label="Send message"
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#0F9488] text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {loading ? <Loader2 size={17} className="animate-spin" aria-hidden="true" /> : <Send size={17} aria-hidden="true" />}
                </button>
              </form>

              <p className="mt-2 text-center text-[10px] text-slate-400">
                Read-only assistant. Demo data only. Recommendations require human review and approval.
              </p>
              {service === "offline" && (
                <p className="mt-1 text-center text-[10px] text-red-600">
                  <AlertCircle size={10} className="mr-1 inline" aria-hidden="true" />
                  The backend cannot be reached. Start the API and refresh the page.
                </p>
              )}
            </div>
          </div>
        </main>
      </div>
    </AppShell>
  );
}
