import { Badge } from "@/components/ui/badge";
import type { Summary } from "@/lib/api";

// Thin wrapper over the existing Badge. The severity field is real but uniform
// today (nothing in the pipeline sets it, so every insight is "medium") — so
// "medium" renders as calm, neutral metadata rather than a loud amber alarm,
// and only "high" carries visual weight. When Tier 2 starts classifying
// severity, high/low begin to stand out without any layout change (Build Spec
// §12, §14.3).

const CONFIG: Record<Summary["severity"], { variant: "destructive" | "secondary" | "outline"; label: string }> = {
  high: { variant: "destructive", label: "High priority" },
  medium: { variant: "secondary", label: "Medium" },
  low: { variant: "outline", label: "Low" },
};

export function SeverityBadge({ severity }: { severity: Summary["severity"] }) {
  const { variant, label } = CONFIG[severity] ?? CONFIG.medium;
  return <Badge variant={variant}>{label}</Badge>;
}
