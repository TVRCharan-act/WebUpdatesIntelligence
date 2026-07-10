import type { Source } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

// Derived monitoring health — turns the binary Active/Paused badge into an actual
// signal about whether a monitor is doing its job (Build Spec §15.4). Entirely
// frontend-only: computed from enabled + last_checked_at + schedule_minutes +
// whether the monitor has produced anything recently.

export type HealthTone = "ok" | "warn" | "paused";

export interface MonitorHealth {
  label: string;
  tone: HealthTone;
}

/** A monitor is "overdue" once it's this many times past its own cadence. */
const OVERDUE_FACTOR = 2.5;

export function monitoringHealth(source: Source, hasRecentActivity: boolean): MonitorHealth {
  if (!source.enabled) {
    return { label: "Off watch", tone: "paused" };
  }
  if (!source.last_checked_at) {
    return { label: "Taking up watch", tone: "warn" };
  }

  const last = new Date(source.last_checked_at).getTime();
  const overdueMs = source.schedule_minutes * 60_000 * OVERDUE_FACTOR;
  const checked = formatRelativeTime(source.last_checked_at);

  if (Date.now() - last > overdueMs) {
    return { label: `Watch overdue — last checked ${checked}`, tone: "warn" };
  }
  if (!hasRecentActivity) {
    return { label: `On watch · nothing new lately · checked ${checked}`, tone: "ok" };
  }
  return { label: `On watch · checked ${checked}`, tone: "ok" };
}
