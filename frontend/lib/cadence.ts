// Check-frequency handling. Customers enter the interval directly in minutes;
// this formats a minute value into a human-readable label for display.

/** Clamp a user-entered minute value to a sane positive integer. */
export function clampMinutes(value: number | string, fallback = 60): number {
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n) || n < 1) return fallback;
  return Math.floor(n);
}

/** Human-readable label for a minute interval (accurate, not bucketed). */
export function formatCadence(minutes: number | null | undefined): string {
  if (minutes == null || minutes < 1) return "—";
  if (minutes < 60) return `Every ${minutes} min`;
  if (minutes === 60) return "Hourly";
  if (minutes === 1440) return "Daily";
  if (minutes % 1440 === 0) return `Every ${minutes / 1440} days`;
  if (minutes % 60 === 0) return `Every ${minutes / 60} hours`;
  return `Every ${minutes} min`;
}
