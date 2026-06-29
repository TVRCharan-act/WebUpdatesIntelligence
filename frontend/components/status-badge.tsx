import { Badge } from "@/components/ui/badge";

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();

  if (["success", "completed", "finished"].includes(normalized)) {
    return <Badge variant="success">{status}</Badge>;
  }

  if (["failure", "failed", "error"].includes(normalized)) {
    return <Badge variant="destructive">{status}</Badge>;
  }

  if (["running", "pending", "queued", "started"].includes(normalized)) {
    return <Badge variant="warning">{status}</Badge>;
  }

  return <Badge variant="secondary">{status}</Badge>;
}
