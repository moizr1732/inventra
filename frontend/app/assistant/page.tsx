
"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  Boxes,
  Package,
  TrendingUp,
  SlidersHorizontal,
  ShieldCheck,
  Send,
  Sparkles,
  Bot,
  User,
  Loader2,
  RotateCcw,
  MessageSquare,
  ArrowRight,
  AlertCircle,
  History,
  Plus,
  Trash2,
  Clock3,
} from "lucide-react";
import {
  inventraApi,
  type AssistantResponse,
  type AssistantConversation,
} from "@/lib/api";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  intent?: string;
  sources?: string[];
};

const suggestions = [
  {
    title: "Check stock risks",
    description: "Identify materials that need replenishment",
    prompt: "Identify inventory risks and tell me which items need replenishment.",
  },
  {
    title: "Inventory overview",
    description: "Get a summary of available stock",
    prompt: "Show me all inventory and available stock.",
  },
  {
    title: "Purchase orders",
    description: "Review purchase order statuses",
    prompt: "Show me all purchase orders and their current statuses.",
  },
  {
    title: "Demand forecast",
    description: "Explore upcoming material demand",
    prompt: "Can you forecast demand for FAB-001?",
  },
];

const navigation = [
  { label: "Dashboard", href: "/", icon: Boxes },
  { label: "Inventory", href: "/inventory", icon: Package },
  { label: "Forecasting", href: "/forecasting", icon: TrendingUp },
  {
    label: "Purchase Orders",
    href: "/purchase-orders",
    icon: SlidersHorizontal,
  },
  { label: "AI Assistant", href: "/assistant", icon: ShieldCheck },
];

function formatConversationDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [conversationId, setConversationId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<AssistantConversation[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [deletingConversationId, setDeletingConversationId] = useState<number | null>(null);
  const [lastFailedMessage, setLastFailedMessage] = useState("");

  const messageEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Restore the most recently updated conversation when the page opens.
  useEffect(() => {
    let cancelled = false;

    async function restoreLatestConversation() {
      setHistoryLoading(true);

      try {
        const history = await inventraApi.getConversations();

        if (cancelled) return;

        setConversations(history);

        if (history.length > 0) {
          const latest = history[0];
          const savedMessages =
            await inventraApi.getConversationMessages(latest.id);

          if (cancelled) return;

          setConversationId(latest.id);
          setMessages(
            savedMessages.map((message) => ({
              id: message.id,
              role: message.role,
              content: message.content,
              intent: message.intent ?? undefined,
            }))
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? `Unable to restore conversation history: ${err.message}`
              : "Unable to restore conversation history."
          );
        }
      } finally {
        if (!cancelled) {
          setHistoryLoading(false);
        }
      }
    }

    restoreLatestConversation();

    return () => {
      cancelled = true;
    };
  }, []);

  async function refreshConversationHistory() {
    try {
      const history = await inventraApi.getConversations();
      setConversations(history);
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
      const savedMessages =
        await inventraApi.getConversationMessages(id);

      setConversationId(id);

      setMessages(
        savedMessages.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          intent: message.intent ?? undefined,
        }))
      );

      setInput("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to open this conversation."
      );
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

    const confirmed = window.confirm(
      "Delete this conversation permanently? This cannot be undone."
    );

    if (!confirmed) return;

    setDeletingConversationId(id);
    setError("");

    try {
      await inventraApi.deleteConversation(id);

      if (conversationId === id) {
        setConversationId(null);
        setMessages([]);
        setInput("");
        setLastFailedMessage("");
      }

      await refreshConversationHistory();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to delete this conversation."
      );
    } finally {
      setDeletingConversationId(null);
    }
  }

  async function sendMessage(
    messageText: string,
    event?: FormEvent,
    isRetry = false
  ) {
    event?.preventDefault();

    const trimmedMessage = messageText.trim();

    if (!trimmedMessage || loading || historyLoading) return;

    if (!isRetry) {
      const userMessage: Message = {
        id: Date.now(),
        role: "user",
        content: trimmedMessage,
      };

      setMessages((previous) => [...previous, userMessage]);
    }

    setInput("");
    setError("");
    setLastFailedMessage("");
    setLoading(true);

    try {
      const response: AssistantResponse =
        await inventraApi.sendAssistantMessage(
          trimmedMessage,
          conversationId
        );

      setConversationId(response.conversation_id);

      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: response.answer,
        intent: response.intent,
        sources: response.sources,
      };

      setMessages((previous) => [...previous, assistantMessage]);

      await refreshConversationHistory();
    } catch (err) {
      setLastFailedMessage(trimmedMessage);

      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to Inventra AI. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-[#F5F7FA] text-[#172B43]">
      <aside className="sidebar sticky top-0 flex h-screen w-64 shrink-0 self-start flex-col border-r border-white/10 bg-[#0F2740] px-5 py-6 text-white">
        <Link href="/" className="mb-10 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0F9488]">
            <Boxes size={23} />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wide">Inventra</h1>
            <p className="text-xs text-slate-400">
              Inventory Intelligence
            </p>
          </div>
        </Link>

        <p className="mb-4 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          Workspace
        </p>

        <nav className="flex flex-col gap-2">
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = item.href === "/assistant";

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition ${
                  active
                    ? "bg-[#0F9488] text-white shadow-lg shadow-teal-950/20"
                    : "text-slate-300 hover:bg-white/10 hover:text-white"
                }`}
              >
                <Icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="mb-5 mt-8 flex items-center justify-between px-3">
          <div className="flex items-center gap-2">
            <History size={14} className="text-slate-400" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Recent conversations
            </p>
          </div>

          <button
            onClick={startNewConversation}
            disabled={loading || historyLoading}
            title="Start a new conversation"
            aria-label="Start a new conversation"
            className="rounded-lg p-1.5 text-slate-300 transition hover:bg-white/10 hover:text-white disabled:opacity-40"
          >
            <Plus size={17} />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
          {historyLoading ? (
            <div className="flex items-center gap-2 px-3 py-3 text-xs text-slate-400">
              <Loader2 size={14} className="animate-spin" />
              Loading history...
            </div>
          ) : conversations.length === 0 ? (
            <p className="px-3 py-3 text-xs leading-5 text-slate-500">
              Your saved conversations will appear here.
            </p>
          ) : (
            conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`group flex items-center gap-1 rounded-xl px-2 py-2 transition ${
                  conversationId === conversation.id
                    ? "bg-white/10"
                    : "hover:bg-white/5"
                }`}
              >
                <button
                  onClick={() => openConversation(conversation.id)}
                  disabled={loading || historyLoading}
                  className="min-w-0 flex-1 text-left disabled:opacity-50"
                >
                  <span
                    className={`block truncate px-1 text-xs font-medium ${
                      conversationId === conversation.id
                        ? "text-white"
                        : "text-slate-300"
                    }`}
                  >
                    {conversation.title}
                  </span>

                  <span className="mt-1 flex items-center gap-1 px-1 text-[10px] text-slate-500">
                    <Clock3 size={10} />
                    {formatConversationDate(conversation.updated_at)}
                    <span>·</span>
                    {conversation.message_count} messages
                  </span>
                </button>

                <button
                  onClick={() => deleteConversation(conversation.id)}
                  disabled={
                    deletingConversationId !== null || loading
                  }
                  title="Delete conversation"
                  aria-label={`Delete ${conversation.title}`}
                  className="rounded-md p-1.5 text-slate-500 opacity-0 transition hover:bg-red-500/20 hover:text-red-300 group-hover:opacity-100 focus:opacity-100 disabled:opacity-30"
                >
                  {deletingConversationId === conversation.id ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Trash2 size={13} />
                  )}
                </button>
              </div>
            ))
          )}
        </div>

        <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="mb-3 flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-emerald-400" />
            <span className="text-xs font-medium text-emerald-300">
              AI Service
            </span>
          </div>
          <p className="text-xs leading-5 text-slate-300">
            Ask questions about inventory, stock risks, forecasts and
            purchase orders.
          </p>
          <p className="mt-3 text-[10px] text-slate-500">
            Inventra Demo Environment
          </p>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[76px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-8">
          <div>
            <h2 className="text-lg font-bold text-[#172B43]">
              AI Assistant
            </h2>
            <p className="text-xs text-slate-500">
              Inventory intelligence at your fingertips
            </p>
          </div>

          <button
            onClick={startNewConversation}
            disabled={
              loading ||
              historyLoading ||
              (messages.length === 0 && conversationId === null)
            }
            className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus size={15} />
            New conversation
          </button>
        </header>

        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col overflow-y-auto px-5 py-8 md:px-10">
            {historyLoading ? (
              <div className="flex flex-1 items-center justify-center gap-3 text-sm text-slate-500">
                <Loader2 size={20} className="animate-spin text-[#0F9488]" />
                Restoring your conversation...
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-1 flex-col justify-center">
                <div className="mx-auto mb-8 max-w-2xl text-center">
                  <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-teal-50 text-[#0F9488]">
                    <Sparkles size={30} />
                  </div>

                  <h3 className="text-3xl font-bold tracking-tight text-[#172B43]">
                    Your inventory intelligence assistant
                  </h3>

                  <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-500">
                    Ask Inventra about material availability, stock
                    shortages, replenishment recommendations, demand
                    forecasts and purchase orders.
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  {suggestions.map((suggestion) => (
                    <button
                      key={suggestion.title}
                      onClick={() => sendMessage(suggestion.prompt)}
                      disabled={loading}
                      className="group rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-md disabled:opacity-50"
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <span className="text-sm font-semibold text-[#172B43]">
                          {suggestion.title}
                        </span>
                        <ArrowRight
                          size={16}
                          className="text-slate-400 transition group-hover:translate-x-1 group-hover:text-[#0F9488]"
                        />
                      </div>
                      <p className="text-xs leading-5 text-slate-500">
                        {suggestion.description}
                      </p>
                    </button>
                  ))}
                </div>

                <p className="mt-7 text-center text-[11px] text-slate-400">
                  Inventra uses application data to generate grounded
                  responses. Always review recommendations before
                  making procurement decisions.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-6 pb-6">
                {messages.map((message) => {
                  const isUser = message.role === "user";

                  return (
                    <div
                      key={message.id}
                      className={`flex gap-3 ${
                        isUser ? "justify-end" : "justify-start"
                      }`}
                    >
                      {!isUser && (
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-[#0F9488]">
                          <Bot size={19} />
                        </div>
                      )}

                      <div
                        className={`max-w-[85%] rounded-2xl px-5 py-4 ${
                          isUser
                            ? "rounded-tr-sm bg-[#173A59] text-white"
                            : "rounded-tl-sm border border-slate-200 bg-white text-[#26384D] shadow-sm"
                        }`}
                      >
                        <div
                          className={`mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider ${
                            isUser ? "text-slate-300" : "text-[#0F9488]"
                          }`}
                        >
                          {isUser ? (
                            <>
                              <User size={12} />
                              You
                            </>
                          ) : (
                            <>
                              <Sparkles size={12} />
                              Inventra AI
                            </>
                          )}
                        </div>

                        <p className="whitespace-pre-wrap text-sm leading-7">
                          {message.content}
                        </p>

                        {!isUser && message.intent && (
                          <div className="mt-4 border-t border-slate-100 pt-3">
                            <span className="rounded-md bg-teal-50 px-2 py-1 text-[10px] font-medium text-teal-700">
                              Intent: {message.intent.replaceAll("_", " ")}
                            </span>

                            {message.sources &&
                              message.sources.length > 0 && (
                                <div className="mt-2 text-[10px] text-slate-400">
                                  Sources: {message.sources.join(", ")}
                                </div>
                              )}
                          </div>
                        )}
                      </div>

                      {isUser && (
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#173A59] text-white">
                          <User size={18} />
                        </div>
                      )}
                    </div>
                  );
                })}

                {loading && (
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-50 text-[#0F9488]">
                      <Bot size={19} />
                    </div>
                    <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-5 py-4 shadow-sm">
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        <Loader2
                          size={16}
                          className="animate-spin text-[#0F9488]"
                        />
                        Analyzing your inventory data...
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messageEndRef} />
              </div>
            )}

            {error && (
              <div className="mt-4 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <AlertCircle size={18} className="mt-0.5 shrink-0" />
                <div>
                  <p className="font-semibold">Something went wrong</p>
                  <p className="mt-1 text-xs leading-5">{error}</p>

                  {lastFailedMessage && (
                    <button
                      onClick={() =>
                        sendMessage(lastFailedMessage, undefined, true)
                      }
                      disabled={loading}
                      className="mt-2 text-xs font-semibold underline disabled:opacity-50"
                    >
                      Try again
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="shrink-0 border-t border-slate-200 bg-white px-5 py-5 md:px-10">
            <div className="mx-auto max-w-5xl">
              <form
                onSubmit={(event) => sendMessage(input, event)}
                className="flex items-end gap-3 rounded-2xl border border-slate-200 bg-[#F8FAFC] p-2 transition focus-within:border-teal-400 focus-within:ring-2 focus-within:ring-teal-100"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center text-slate-400">
                  <MessageSquare size={19} />
                </div>

                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      sendMessage(input);
                    }
                  }}
                  placeholder="Ask about stock levels, risks, forecasts or purchase orders..."
                  rows={1}
                  disabled={loading || historyLoading}
                  className="max-h-32 min-h-10 flex-1 resize-y bg-transparent py-2 text-sm text-[#172B43] outline-none placeholder:text-slate-400 disabled:opacity-50"
                />

                <button
                  type="submit"
                  disabled={!input.trim() || loading || historyLoading}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#0F9488] text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label="Send message"
                >
                  {loading ? (
                    <Loader2 size={17} className="animate-spin" />
                  ) : (
                    <Send size={17} />
                  )}
                </button>
              </form>

              <p className="mt-3 text-center text-[10px] text-slate-400">
                Read-only AI assistant · Recommendations require human review
                and approval · Demo data only
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
