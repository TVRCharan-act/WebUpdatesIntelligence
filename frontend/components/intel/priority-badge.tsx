import { Flag } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Priority } from "@/lib/api";
import { cn } from "@/lib/utils";

// Customer-set priority for a tracked company. Deliberately distinct from the
// AI-set SeverityBadge (a flag icon + priority-specific color), so "how much I
// care" is never confused with "how significant the AI thinks this change is".

const CONFIG: Record<Priority, { label: string; className: string }> = {
  high: { label: "High priority", className: "text-rose-600 dark:text-rose-400" },
  medium: { label: "Medium priority", className: "text-muted-foreground" },
  low: { label: "Low priority", className: "text-muted-foreground/70" },
};

export const PRIORITY_OPTIONS: { value: Priority; label: string }[] = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

/** For sorting: higher number = higher priority. */
export const PRIORITY_RANK: Record<Priority, number> = { high: 3, medium: 2, low: 1 };

export function PriorityBadge({ priority }: { priority: Priority }) {
  const { label, className } = CONFIG[priority] ?? CONFIG.medium;
  return (
    <Badge variant="outline" className={cn("gap-1 font-normal", className)}>
      <Flag className="size-3" />
      {label}
    </Badge>
  );
}
