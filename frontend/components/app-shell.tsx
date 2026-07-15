"use client";

import {
  BarChart3,
  Building2,
  DatabaseZap,
  FlaskConical,
  Gauge,
  LogOut,
  Mail,
  Menu,
  PlayCircle,
  Rows3,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import * as React from "react";

import { useAuth } from "@/components/auth-provider";
import { Link, usePathname } from "@/components/router";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/admin/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/admin/accounts", label: "Accounts", icon: BarChart3 },
  { href: "/admin/companies", label: "Companies", icon: Building2 },
  { href: "/admin/sources", label: "Sources", icon: DatabaseZap },
  { href: "/admin/crawler-lab", label: "Crawler Lab", icon: FlaskConical },
  { href: "/admin/storage", label: "Storage", icon: Rows3 },
  { href: "/admin/email", label: "Email", icon: Mail },
  { href: "/admin/runs", label: "Runs", icon: PlayCircle },
  { href: "/admin/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const title =
    navItems
      .slice()
      .sort((a, b) => b.href.length - a.href.length)
      .find((item) =>
        item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
      )?.label || "Sentinel Actalyst Ops";

  const sidebar = (
    <aside className="flex h-full flex-col border-r bg-card">
      <div className="flex h-16 items-center gap-2 border-b px-5">
        <div className="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <ShieldCheck className="size-5" />
        </div>
        <div>
          <div className="font-semibold">Sentinel Actalyst Ops</div>
          <div className="text-xs text-muted-foreground">Command post</div>
        </div>
      </div>
      <nav className="grid gap-1 p-3">
        {navItems.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground",
                active && "bg-secondary text-foreground",
              )}
            >
              <Icon className="size-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto border-t p-3">
        <Button
          variant="ghost"
          className="w-full justify-start text-muted-foreground"
          onClick={async () => {
            await auth.logout();
            window.location.assign("/admin/login");
          }}
        >
          <LogOut className="size-4" />
          Sign out
        </Button>
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen bg-background">
      <div className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">
        {sidebar}
      </div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/30"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative h-full w-72">{sidebar}</div>
        </div>
      ) : null}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setMobileOpen((open) => !open)}
              aria-label="Toggle navigation"
            >
              {mobileOpen ? <X /> : <Menu />}
            </Button>
            <div>
              <h1 className="text-lg font-semibold">{title}</h1>
              <p className="hidden text-sm text-muted-foreground sm:block">
                Control accounts, monitor sources, baselines, and runs.
              </p>
            </div>
          </div>
        </header>
        <main className="w-full max-w-7xl px-4 py-6 sm:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
