"use client";

import { LogOut, Radar, ShieldCheck, Sparkles } from "lucide-react";
import * as React from "react";

import { useAuth } from "@/components/auth-provider";
import { Link, usePathname } from "@/components/router";
import { Button } from "@/components/ui/button";
import { cn, getInitials } from "@/lib/utils";

// The customer app is exactly two pages, so the old sidebar gave way to a
// light top bar: brand, a two-tab pill switch, and the account. Legacy routes
// still resolve (see src/main.tsx) and simply light up the tab they belong to.

const HOME_PATHS = ["/dashboard", "/insights", "/trends"];

const navItems = [
  { href: "/dashboard", label: "Home", icon: Sparkles, isActive: (path: string) => HOME_PATHS.some((p) => path.startsWith(p)) },
  {
    href: "/monitors",
    label: "Watchtower",
    icon: Radar,
    isActive: (path: string) =>
      path.startsWith("/monitors") ||
      path.startsWith("/notifications") ||
      path.startsWith("/settings") ||
      path.startsWith("/onboarding"),
  },
];

export function CustomerShell({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link href="/dashboard" className="flex min-w-0 items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <ShieldCheck className="size-5" />
            </div>
            <div className="hidden min-w-0 sm:block">
              <div className="truncate font-semibold leading-tight">Sentinel Actalyst</div>
              <div className="text-xs text-muted-foreground">Always on watch</div>
            </div>
          </Link>

          <nav className="flex items-center gap-1 rounded-full bg-secondary p-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = item.isActive(pathname);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground sm:px-4",
                    active && "bg-card text-foreground shadow-sm",
                  )}
                >
                  <Icon className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-2 sm:flex">
              <div className="flex size-8 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
                {getInitials(auth.session?.name || "")}
              </div>
              <span className="max-w-32 truncate text-sm font-medium">{auth.session?.name}</span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Sign out"
              title="Sign out"
              onClick={async () => {
                await auth.logout();
                window.location.assign("/login");
              }}
            >
              <LogOut className="size-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
