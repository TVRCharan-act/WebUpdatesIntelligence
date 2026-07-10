"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

// "AI is working" state — a Signal pulse with a bright segment sweeping along it,
// plus narration that describes what the product is doing *for the customer*
// (Build Spec §14.6, §16). Used for onboarding's first look and check-now waits.
// The sweep is disabled under prefers-reduced-motion (see globals.css); the
// narration still cycles (text, not motion).

const WAVE = "M0 12 Q6 3 12 12 T24 12 T36 12 T48 12 T60 12 T72 12 T84 12 T96 12 L100 12";

const DEFAULT_LINES = [
  "Reading the page…",
  "Learning what's on it…",
  "Setting up your monitor…",
];

export function ThinkingState({
  lines = DEFAULT_LINES,
  ariaLabel = "Working",
  className,
}: {
  lines?: string[];
  ariaLabel?: string;
  className?: string;
}) {
  const [index, setIndex] = React.useState(0);

  React.useEffect(() => {
    if (lines.length <= 1) return;
    const timer = setInterval(() => {
      setIndex((current) => (current + 1) % lines.length);
    }, 2500);
    return () => clearInterval(timer);
  }, [lines.length]);

  return (
    <div
      className={cn("flex flex-col items-center gap-3 py-4", className)}
      role="status"
      aria-label={ariaLabel}
    >
      <svg
        viewBox="0 0 100 24"
        preserveAspectRatio="none"
        className="h-8 w-44 text-signal"
        aria-hidden="true"
      >
        <path
          d={WAVE}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
          className="opacity-20"
        />
        <path
          d={WAVE}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          pathLength={1}
          className="signal-sweep"
        />
      </svg>
      <p key={index} className="text-sm text-muted-foreground">
        {lines[index]}
      </p>
    </div>
  );
}
