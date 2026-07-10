"use client";

import { Link } from "@/components/router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

// Confident, forward-looking empty state — never apologetic (Build Spec §14.5,
// §16). Replaces the ad-hoc border-dashed blocks scattered across the app.

interface AnalystEmptyStateProps {
  title: string;
  body: string;
  action?: { label: string; href: string };
  /** Renders the ambient Signal pulse; respects prefers-reduced-motion. */
  animated?: boolean;
}

export function AnalystEmptyState({
  title,
  body,
  action,
  animated = true,
}: AnalystEmptyStateProps) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center gap-3 py-14 text-center">
        {animated ? <AmbientPulse /> : null}
        <div className="text-lg font-semibold">{title}</div>
        <p className="max-w-md text-sm text-muted-foreground">{body}</p>
        {action ? (
          <Button asChild className="mt-2">
            <Link href={action.href}>{action.label}</Link>
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

function AmbientPulse() {
  return (
    <svg
      width={72}
      height={28}
      viewBox="0 0 72 28"
      fill="none"
      aria-hidden="true"
      className="text-signal"
    >
      <path
        d="M0 14 H16 L22 5 L30 23 L38 9 L44 14 H72"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        className="signal-draw"
      />
    </svg>
  );
}
