"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  AlertCircle,
  Boxes,
  HelpCircle,
  Menu,
  Package,
  ShieldCheck,
  ShoppingCart,
  TrendingUp,
  X,
  type LucideIcon,
} from "lucide-react";

type NavItem = { label: string; href: string; icon: LucideIcon };

export const NAVIGATION: NavItem[] = [
  { label: "Dashboard", href: "/", icon: Boxes },
  { label: "Inventory", href: "/inventory", icon: Package },
  { label: "Forecasting", href: "/forecasting", icon: TrendingUp },
  { label: "Purchase Orders", href: "/purchase-orders", icon: ShoppingCart },
  { label: "AI Assistant", href: "/assistant", icon: ShieldCheck },
];

const SUPPORT: NavItem[] = [{ label: "Help & Support", href: "/help", icon: HelpCircle }];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  const renderItem = (item: NavItem) => {
    const Icon = item.icon;
    const active = isActive(pathname, item.href);
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
          active
            ? "bg-[#0F9488] text-white shadow-lg shadow-teal-950/20"
            : "text-slate-300 hover:bg-white/10 hover:text-white"
        }`}
      >
        <Icon size={18} aria-hidden="true" />
        {item.label}
      </Link>
    );
  };

  return (
    <nav aria-label="Main navigation" className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          Workspace
        </p>
        {NAVIGATION.map(renderItem)}
      </div>
      <div className="flex flex-col gap-1">
        <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          Support
        </p>
        {SUPPORT.map(renderItem)}
      </div>
    </nav>
  );
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0F9488]">
        <Boxes size={23} aria-hidden="true" />
      </div>
      <div>
        <p className="text-xl font-bold tracking-wide text-white">Inventra</p>
        <p className="text-xs text-slate-400">Inventory Intelligence</p>
      </div>
    </Link>
  );
}

/**
 * Application frame shared by every page: a fixed sidebar on wide screens and
 * a collapsible drawer on small screens. Page content is passed as children.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Escape closes the drawer. The listener only changes state in response to a key press.
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  return (
    <div className="flex min-h-screen bg-[#F5F7FA] text-[#172B3D]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:shadow"
      >
        Skip to content
      </a>

      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col overflow-y-auto border-r border-white/10 bg-[#0F2740] px-5 py-6 text-white lg:flex">
        <div className="mb-10">
          <Brand />
        </div>
        <Navigation />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between bg-[#0F2740] px-4 text-white lg:hidden">
          <Brand />
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
            aria-controls="mobile-navigation"
            className="rounded-lg p-2 text-slate-200 hover:bg-white/10"
          >
            <Menu size={22} aria-hidden="true" />
          </button>
        </header>

        {drawerOpen && (
          <div
            className="fixed inset-0 z-40 bg-slate-900/50 lg:hidden"
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
          />
        )}

        <aside
          id="mobile-navigation"
          aria-hidden={!drawerOpen}
          className={`fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col overflow-y-auto bg-[#0F2740] px-5 py-6 text-white shadow-2xl transition-transform duration-200 lg:hidden ${
            drawerOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="mb-8 flex items-center justify-between">
            <Brand />
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              aria-label="Close navigation"
              className="rounded-lg p-2 text-slate-300 hover:bg-white/10"
            >
              <X size={20} aria-hidden="true" />
            </button>
          </div>
          <Navigation onNavigate={() => setDrawerOpen(false)} />
        </aside>

        {children}
      </div>
    </div>
  );
}

/** Small reusable notice for page-level problems. */
export function InlineNotice({ tone = "error", children }: { tone?: "error" | "warning"; children: ReactNode }) {
  const styles =
    tone === "error"
      ? "border-red-200 bg-red-50 text-red-700"
      : "border-amber-200 bg-amber-50 text-amber-800";
  return (
    <div role="alert" className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${styles}`}>
      <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
