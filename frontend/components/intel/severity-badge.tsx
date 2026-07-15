import { Badge } from "@/components/ui/badge";
import type { Summary } from "@/lib/api";

// Thin wrapper over the existing Badge. In the monochrome system severity is
// conveyed by *weight*, not colour: "high" is a solid black fill, "medium" a
// calm gray fill, "low" a bare outline. Red is reserved for genuine errors, so
// a high-severity insight is emphatic without masquerading as a failure. When
// Tier 2 starts classifying severity, the hierarchy already reads (Build Spec
// §12, §14.3).

const CONFIG: Record<Summary["severity"], { variant: "default" | "secondary" | "outline"; label: string }> = {
  high: { variant: "default", label: "High priority" },
  medium: { variant: "secondary", label: "Medium" },
  low: { variant: "outline", label: "Low" },
};

export function SeverityBadge({ severity }: { severity: Summary["severity"] }) {
  const { variant, label } = CONFIG[severity] ?? CONFIG.medium;
  return <Badge variant={variant}>{label}</Badge>;
}
