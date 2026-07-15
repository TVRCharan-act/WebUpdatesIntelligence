"use client";

import { Bell, Building2, LogOut, Radar, ShieldCheck, Sparkles } from "lucide-react";
import * as React from "react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { cn, getInitials } from "@/lib/utils";

// The whole customer app is one scrolling page (app/dashboard/page.tsx),
// composed of anchored sections: #overview, #monitors, #alerts, #workspace.
// This header is a jump nav — it never routes, it just scrolls the section
// into view and tracks which one is on screen via IntersectionObserver.

const SECTIONS = [
  { id: "overview", label: "Overview", icon: Sparkles },
  { id: "monitors", label: "Monitors", icon: Radar },
  { id: "alerts", label: "Alerts", icon: Bell },
  { id: "workspace", label: "Workspace", icon: Building2 },
];

/** Header height (h-16) the sticky bar reserves — sections use scroll-mt-24 to match. */
const SCROLL_OFFSET_PX = 80;

function useActiveSection(ids: string[]) {
  const [activeId, setActiveId] = React.useState(ids[0]);

  React.useEffect(() => {
    const elements = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => Boolean(el));

    if (!elements.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveId(visible[0].target.id);
      },
      { rootMargin: `-${SCROLL_OFFSET_PX}px 0px -70% 0px`, threshold: 0 },
    );

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [ids]);

  return activeId;
}

export function CustomerShell({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const sectionIds = React.useMemo(() => SECTIONS.map((s) => s.id), []);
  const activeId = useActiveSection(sectionIds);

  function jumpTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.history.replaceState(null, "", `/dashboard#${id}`);
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <a
            href="/dashboard#overview"
            onClick={(event) => {
              event.preventDefault();
              jumpTo("overview");
            }}
            className="flex min-w-0 items-center gap-3"
          >
            <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <ShieldCheck className="size-5" />
            </div>
            <div className="hidden min-w-0 sm:block">
              <div className="truncate font-semibold leading-tight">Sentinel Actalyst</div>
              <div className="text-xs text-muted-foreground">Always on watch</div>
            </div>
          </a>

          <nav className="flex items-center gap-1 rounded-full bg-secondary p-1">
            {SECTIONS.map((section) => {
              const Icon = section.icon;
              const active = activeId === section.id;
              return (
                <a
                  key={section.id}
                  href={`/dashboard#${section.id}`}
                  onClick={(event) => {
                    event.preventDefault();
                    jumpTo(section.id);
                  }}
                  aria-current={active ? "true" : undefined}
                  className={cn(
                    "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground sm:px-4",
                    active && "bg-card text-foreground shadow-sm",
                  )}
                >
                  <Icon className="size-4" />
                  <span className="hidden sm:inline">{section.label}</span>
                </a>
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
