"use client";

import {
  BarChart3,
  Bell,
  Gauge,
  Lightbulb,
  LogOut,
  Menu,
  Radar,
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
  { href: "/dashboard", label: "Command Center", icon: Gauge },
  { href: "/monitors", label: "Monitors", icon: Radar },
  { href: "/insights", label: "Insights", icon: Lightbulb },
  { href: "/trends", label: "Trends", icon: BarChart3 },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/settings/workspace", label: "Settings", icon: Settings },
];

export function CustomerShell({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const activeItem = navItems
    .slice()
    .sort((a, b) => b.href.length - a.href.length)
    .find((item) => pathname.startsWith(item.href));

  const sidebar = (
    <aside className="flex h-full flex-col bg-[hsl(222_47%_9%)] text-white">
      <div className="flex h-16 items-center gap-3 border-b border-white/10 px-5">
        <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <ShieldCheck className="size-5" />
        </div>
        <div>
          <div className="font-semibold">Sentinel Actalyst</div>
          <div className="text-xs text-white/55">Always on watch</div>
        </div>
      </div>
      <nav className="grid gap-1 p-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-white/65 transition-colors hover:bg-white/10 hover:text-white",
                active && "bg-white/10 text-white",
              )}
            >
              <Icon className="size-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto border-t border-white/10 p-3">
        <div className="mb-3 rounded-lg bg-white/10 px-3 py-2">
          <div className="text-sm font-medium">{auth.session?.name}</div>
          <div className="text-xs text-white/55">Customer workspace</div>
        </div>
        <Button
          variant="ghost"
          className="w-full justify-start text-white/65 hover:bg-white/10 hover:text-white"
          onClick={async () => {
            await auth.logout();
            window.location.assign("/login");
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
            className="absolute inset-0 bg-black/40"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative h-full w-72">{sidebar}</div>
        </div>
      ) : null}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background/90 px-4 backdrop-blur sm:px-6">
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
              <h1 className="text-lg font-semibold">
                {activeItem?.label || "Sentinel Actalyst"}
              </h1>
              <p className="hidden text-sm text-muted-foreground sm:block">
                On watch — what changed, why it matters, and what needs you.
              </p>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
