import { Globe2, Newspaper, Radar, Swords, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { WatchType } from "@/lib/api";

// A monitor's "post" — what the sentinel is watching for. Drives the AI analyst's
// lens on the backend (openai_summarizer) and reads here as a small chip.

const CONFIG: Record<WatchType, { label: string; icon: LucideIcon }> = {
  competitor: { label: "Competitor", icon: Swords },
  industry: { label: "Industry", icon: Newspaper },
  own: { label: "Own site", icon: Globe2 },
  general: { label: "General watch", icon: Radar },
};

export const WATCH_TYPE_OPTIONS: { value: WatchType; label: string }[] = [
  { value: "competitor", label: "Competitor" },
  { value: "industry", label: "Industry source" },
  { value: "own", label: "Your own site" },
  { value: "general", label: "General watch" },
];

export function WatchTypeBadge({ type }: { type: WatchType }) {
  const { label, icon: Icon } = CONFIG[type] ?? CONFIG.general;
  return (
    <Badge variant="outline" className="gap-1 font-normal">
      <Icon className="size-3" />
      {label}
    </Badge>
  );
}
