// Check-frequency handling. Customers enter an interval as a number + unit
// (minutes / hours / days / weeks / months); everything is stored on the backend
// as `schedule_minutes`. These helpers convert to/from minutes and format a
// minute value into a human-readable label.

export type CadenceUnit = "minute" | "hour" | "day" | "week" | "month";

const UNIT_MINUTES: Record<CadenceUnit, number> = {
  minute: 1,
  hour: 60,
  day: 1440,
  week: 10080,
  month: 43200, // 30-day month
};

export const CADENCE_UNITS: { value: CadenceUnit; label: string }[] = [
  { value: "minute", label: "Minutes" },
  { value: "hour", label: "Hours" },
  { value: "day", label: "Days" },
  { value: "week", label: "Weeks" },
  { value: "month", label: "Months" },
];

/** Convert a number + unit into a positive integer of minutes. */
export function toMinutes(value: number | string, unit: CadenceUnit): number {
  const n = typeof value === "string" ? Number(value) : value;
  const per = UNIT_MINUTES[unit] ?? 1;
  const total = (Number.isFinite(n) && n > 0 ? n : 1) * per;
  return Math.max(1, Math.floor(total));
}

/** Decompose minutes into the largest unit that divides it evenly (for editing). */
export function minutesToParts(minutes: number | null | undefined): {
  value: number;
  unit: CadenceUnit;
} {
  const m = minutes && minutes >= 1 ? Math.floor(minutes) : 60;
  const order: CadenceUnit[] = ["month", "week", "day", "hour", "minute"];
  for (const unit of order) {
    const per = UNIT_MINUTES[unit];
    if (m % per === 0) return { value: m / per, unit };
  }
  return { value: m, unit: "minute" };
}

/** Backward-compatible: clamp a raw minute value to a positive integer. */
export function clampMinutes(value: number | string, fallback = 60): number {
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n) || n < 1) return fallback;
  return Math.floor(n);
}

/** Human-readable label for a minute interval (largest exact unit). */
export function formatCadence(minutes: number | null | undefined): string {
  if (minutes == null || minutes < 1) return "—";
  const tiers: [number, string, string][] = [
    [UNIT_MINUTES.month, "month", "Monthly"],
    [UNIT_MINUTES.week, "week", "Weekly"],
    [UNIT_MINUTES.day, "day", "Daily"],
    [UNIT_MINUTES.hour, "hour", "Hourly"],
  ];
  for (const [per, unit, singular] of tiers) {
    if (minutes === per) return singular;
    if (minutes % per === 0) return `Every ${minutes / per} ${unit}s`;
  }
  return `Every ${minutes} min`;
}
