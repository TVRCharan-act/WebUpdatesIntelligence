import type { DailyInsightCount } from "@/lib/api";

// Emerging-trend / activity-level derivation — computed entirely on the frontend
// from the daily[] series that getInsightStats() already returns. No backend
// change required (Build Spec §12, §14.7).

export interface TrendResult {
  /** Qualitative activity level relative to the trailing average. */
  level: "Quiet" | "Normal" | "Busy";
  /** This-week vs prior-weeks-average % change; null when history is too short. */
  deltaPct: number | null;
  direction: "up" | "down" | "flat";
}

const WEEK = 7;

export function deriveTrend(daily: DailyInsightCount[] | undefined): TrendResult {
  const series = daily ?? [];
  const counts = series.map((day) => day.count);

  const thisWeek = counts.slice(-WEEK).reduce((sum, n) => sum + n, 0);
  const prior = counts.slice(0, Math.max(0, counts.length - WEEK));

  // Need at least a full prior week to make an honest comparison.
  if (prior.length < WEEK) {
    return { level: thisWeek > 0 ? "Normal" : "Quiet", deltaPct: null, direction: "flat" };
  }

  const priorWeekAvg = (prior.reduce((sum, n) => sum + n, 0) / prior.length) * WEEK;

  const deltaPct =
    priorWeekAvg > 0 ? Math.round(((thisWeek - priorWeekAvg) / priorWeekAvg) * 100) : null;

  const direction: TrendResult["direction"] =
    deltaPct == null ? "flat" : deltaPct > 10 ? "up" : deltaPct < -10 ? "down" : "flat";

  const ratio = thisWeek / Math.max(priorWeekAvg, 1);
  const level: TrendResult["level"] =
    thisWeek === 0 && priorWeekAvg === 0
      ? "Quiet"
      : ratio >= 1.25
        ? "Busy"
        : ratio <= 0.5
          ? "Quiet"
          : "Normal";

  return { level, deltaPct, direction };
}
