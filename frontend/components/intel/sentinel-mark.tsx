import { ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";

// The product mark: a plain, solid monochrome tile with the shield glyph.
// Static and restrained — the same neutral treatment used in the app header
// and the sign-in card.

export function SentinelMark({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground",
        className,
      )}
      aria-hidden="true"
    >
      <ShieldCheck className="size-5" />
    </div>
  );
}
