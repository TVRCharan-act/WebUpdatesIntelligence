"use client";

import { Bell, LogOut, Radar, Sparkles } from "lucide-react";
import * as React from "react";

import { useAuth } from "@/components/auth-provider";
import { SentinelMark } from "@/components/intel/sentinel-mark";
import { Button } from "@/components/ui/button";
import { cn, getInitials } from "@/lib/utils";

// The whole customer app is one scrolling page (app/dashboard/page.tsx),
// composed of anchored sections: #overview, #monitors, #alerts. On desktop the
// nav is a slim icon rail on the left that expands on hover / keyboard focus to
// reveal the labels (floating over the content, so nothing reflows); on mobile
// it's a top bar. Nothing routes — clicking scrolls the section into view and
// the active one is tracked via IntersectionObserver.

const SECTIONS = [
  { id: "overview", label: "Overview", icon: Sparkles },
  { id: "monitors", label: "Monitors", icon: Radar },
  { id: "alerts", label: "Alerts", icon: Bell },
];

/** Offset the observer reserves at the top so the active section flips sensibly. */
const SCROLL_OFFSET_PX = 80;

/** Labels/details that fade in only while the rail is expanded. */
const REVEAL =
  "opacity-0 transition-opacity duration-150 group-hover/side:opacity-100 group-focus-within/side:opacity-100";

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

  async function signOut() {
    await auth.logout();
    window.location.assign("/login");
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop: a slim icon rail that expands on hover / focus. The rail
          it's a slim w-16 column that widens to w-64, pushing the content
          over rather than covering it. */}
      <aside className="group/side sticky top-0 z-30 hidden h-svh w-16 shrink-0 flex-col overflow-hidden border-r bg-card transition-[width] duration-200 ease-out hover:w-64 focus-within:w-64 md:flex">
          <div className="px-2 py-4">
            <div className="flex items-center gap-3 px-1.5">
              <SentinelMark />
              <div className={cn("min-w-0 whitespace-nowrap", REVEAL)}>
                <div className="truncate font-semibold leading-tight">Sentinel Actalyst</div>
                <div className="truncate text-xs text-muted-foreground">Website monitoring</div>
              </div>
            </div>
          </div>

          <nav className="flex-1 space-y-1 px-2 py-2">
            {SECTIONS.map((section) => {
              const Icon = section.icon;
              const active = activeId === section.id;
              return (
                <a
                  key={section.id}
                  href={`/dashboard#${section.id}`}
                  title={section.label}
                  onClick={(event) => {
                    event.preventDefault();
                    jumpTo(section.id);
                    // Drop focus so the rail collapses back once the pointer
                    // leaves (a focused link would otherwise hold it open).
                    event.currentTarget.blur();
                  }}
                  aria-current={active ? "true" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-1.5 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                  )}
                >
                  <span className="flex w-9 shrink-0 items-center justify-center">
                    <Icon className="size-5" />
                  </span>
                  <span className={cn("whitespace-nowrap", REVEAL)}>{section.label}</span>
                </a>
              );
            })}
          </nav>

          <div className="border-t px-2 py-3">
            <div className="flex items-center gap-3 px-1.5">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
                {getInitials(auth.session?.name || "")}
              </div>
              <div className={cn("min-w-0 flex-1 whitespace-nowrap", REVEAL)}>
                <div className="truncate text-sm font-medium">{auth.session?.name}</div>
                <div className="truncate text-xs capitalize text-muted-foreground">
                  {auth.session?.role} account
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Sign out"
                title="Sign out"
                onClick={signOut}
                className={cn("shrink-0", REVEAL)}
              >
                <LogOut className="size-4" />
              </Button>
            </div>
          </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile: top bar + horizontal section nav. */}
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b bg-background/85 px-4 py-3 backdrop-blur md:hidden">
          <SentinelMark />
          <div className="min-w-0 flex-1 truncate font-semibold">Sentinel Actalyst</div>
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
            {getInitials(auth.session?.name || "")}
          </div>
          <Button variant="ghost" size="icon" aria-label="Sign out" title="Sign out" onClick={signOut}>
            <LogOut className="size-4" />
          </Button>
        </header>
        <nav className="sticky top-[57px] z-20 flex gap-1 overflow-x-auto border-b bg-background/85 px-3 py-2 backdrop-blur md:hidden">
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
                  "flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="size-4" />
                {section.label}
              </a>
            );
          })}
        </nav>

        <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
