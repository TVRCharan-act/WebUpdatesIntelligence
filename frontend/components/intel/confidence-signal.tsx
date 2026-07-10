import type { Summary } from "@/lib/api";
import { cn } from "@/lib/utils";

// AI confidence as a phone-signal-style bar indicator (Build Spec §14.8). A
// distinct visual language from severity — its own cool indigo token and a bar
// shape, never a colored pill — so "how sure the AI is" is never confused with
// "how bad this is". Now backed by a real `confidence` field.

const LEVELS: Record<Summary["confidence"], { bars: number; label: string }> = {
  low: { bars: 1, label: "Low" },
  medium: { bars: 2, label: "Medium" },
  high: { bars: 3, label: "High" },
};

const HEIGHTS = ["h-1.5", "h-2.5", "h-3.5"];

export function ConfidenceSignal({ level }: { level: Summary["confidence"] }) {
  const { bars, label } = LEVELS[level] ?? LEVELS.medium;
  return (
    <span
      className="inline-flex items-end gap-0.5"
      role="img"
      aria-label={`AI confidence: ${label}`}
      title={`AI confidence: ${label}`}
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={cn(
            "w-1 rounded-sm",
            HEIGHTS[i],
            i < bars ? "bg-[hsl(var(--confidence))]" : "bg-muted-foreground/25",
          )}
        />
      ))}
    </span>
  );
}
