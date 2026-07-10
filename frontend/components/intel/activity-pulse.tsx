"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

// The Signal motif rendered as a chart. One component, three sizes — replaces the
// three duplicated bar-chart implementations in dashboard / monitors / trends
// (Build Spec §14.2). Pure SVG + CSS, no charting dependency.

interface ActivityPulseProps {
  /** Per-day counts, oldest → newest. */
  data: number[];
  /** Pixel height. */
  height?: number;
  variant?: "line" | "area";
  /** Shown when the series is empty or all-zero (never a flat line reading as "down"). */
  emptyLabel?: string;
  /** Required — describes the trend for screen readers. */
  ariaLabel: string;
  className?: string;
}

const VIEW_W = 100;
const VIEW_H = 32;
const PAD_Y = 3;

/** Build a smooth (Catmull-Rom → cubic bezier) path through the points. */
function smoothPath(points: Array<[number, number]>): string {
  if (points.length === 0) return "";
  if (points.length === 1) {
    const [x, y] = points[0];
    return `M ${x} ${y} L ${VIEW_W} ${y}`;
  }

  let d = `M ${points[0][0]} ${points[0][1]}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] || points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] || p2;

    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;

    d += ` C ${cp1x} ${cp1y} ${cp2x} ${cp2y} ${p2[0]} ${p2[1]}`;
  }
  return d;
}

export function ActivityPulse({
  data,
  height = 48,
  variant = "area",
  emptyLabel = "No activity yet",
  ariaLabel,
  className,
}: ActivityPulseProps) {
  const hasActivity = data.length > 0 && data.some((n) => n > 0);

  if (!hasActivity) {
    return (
      <div
        className={cn(
          "flex items-center justify-center text-xs text-muted-foreground",
          className,
        )}
        style={{ height }}
        role="img"
        aria-label={emptyLabel}
      >
        {emptyLabel}
      </div>
    );
  }

  const max = Math.max(1, ...data);
  const step = data.length > 1 ? VIEW_W / (data.length - 1) : VIEW_W;
  const usableH = VIEW_H - PAD_Y * 2;

  const points: Array<[number, number]> = data.map((count, i) => {
    const x = data.length > 1 ? i * step : 0;
    const y = PAD_Y + (usableH - (count / max) * usableH);
    return [x, y];
  });

  const linePath = smoothPath(points);
  const areaPath = `${linePath} L ${VIEW_W} ${VIEW_H} L 0 ${VIEW_H} Z`;

  return (
    <svg
      className={cn("w-full", className)}
      style={{ height }}
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={ariaLabel}
    >
      {variant === "area" ? (
        <path d={areaPath} fill="hsl(var(--signal-fill) / 0.12)" stroke="none" />
      ) : null}
      <path
        d={linePath}
        fill="none"
        stroke="hsl(var(--signal))"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
        pathLength={1}
        className="signal-draw"
      />
    </svg>
  );
}
