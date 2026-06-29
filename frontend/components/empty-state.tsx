import { type LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center gap-2 py-12 text-center">
        <div className="flex size-10 items-center justify-center rounded-md bg-secondary">
          <Icon className="size-5 text-muted-foreground" />
        </div>
        <div className="font-medium">{title}</div>
        <div className="max-w-sm text-sm text-muted-foreground">
          {description}
        </div>
      </CardContent>
    </Card>
  );
}
