import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/AppShell";

let currentPath = "/inventory";
vi.mock("next/navigation", () => ({ usePathname: () => currentPath }));

beforeEach(() => {
  currentPath = "/inventory";
});

describe("AppShell navigation", () => {
  it("lists every page that exists, including Help, and no dead routes", () => {
    render(<AppShell><main>content</main></AppShell>);
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    for (const label of ["Dashboard", "Inventory", "Forecasting", "Purchase Orders", "AI Assistant", "Help & Support"]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(within(nav).queryByText("Activity")).toBeNull();
    expect(within(nav).queryByText("Settings")).toBeNull();
  });

  it("marks the current page as the active link", () => {
    render(<AppShell><main>content</main></AppShell>);
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(nav).getByRole("link", { name: "Inventory" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
  });

  it("treats the dashboard as active only on the exact root path", () => {
    currentPath = "/";
    render(<AppShell><main>content</main></AppShell>);
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(nav).getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
  });

  it("renders page content and a skip link for keyboard users", () => {
    render(<AppShell><main>Page body</main></AppShell>);
    expect(screen.getByText("Page body")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main-content");
  });
});

describe("AppShell mobile drawer", () => {
  it("opens from the menu button and reports its state", () => {
    render(<AppShell><main>content</main></AppShell>);
    const open = screen.getByRole("button", { name: "Open navigation" });
    expect(open).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(open);
    expect(open).toHaveAttribute("aria-expanded", "true");
  });

  it("closes from the close button", () => {
    render(<AppShell><main>content</main></AppShell>);
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    fireEvent.click(screen.getByRole("button", { name: "Close navigation" }));
    expect(screen.getByRole("button", { name: "Open navigation" })).toHaveAttribute("aria-expanded", "false");
  });

  it("closes when Escape is pressed", () => {
    render(<AppShell><main>content</main></AppShell>);
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByRole("button", { name: "Open navigation" })).toHaveAttribute("aria-expanded", "false");
  });

  it("closes after a navigation link is chosen in the drawer", () => {
    render(<AppShell><main>content</main></AppShell>);
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    const drawer = document.getElementById("mobile-navigation") as HTMLElement;
    fireEvent.click(within(drawer).getByRole("link", { name: "Forecasting" }));
    expect(screen.getByRole("button", { name: "Open navigation" })).toHaveAttribute("aria-expanded", "false");
  });
});
