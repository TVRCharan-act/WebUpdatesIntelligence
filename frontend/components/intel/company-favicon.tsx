"use client";

import * as React from "react";

import { cn, getInitials } from "@/lib/utils";

// Real favicon of the real monitored domain, with an initials fallback that
// reuses the existing avatar treatment. Never shows a broken-image glyph
// (Build Spec §14.1).

interface CompanyFaviconProps {
  /** Source.url — the domain is extracted internally. */
  url: string;
  /** Company name, for initials fallback + alt text. */
  name: string;
  /** Pixel size; matches the existing avatar sizes. */
  size?: 24 | 32 | 40 | 44;
  className?: string;
}

function hostFrom(url: string): string | null {
  try {
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

const SIZE_CLASS: Record<number, string> = {
  24: "size-6 text-[10px]",
  32: "size-8 text-xs",
  40: "size-10 text-sm",
  44: "size-11 text-sm",
};

export function CompanyFavicon({ url, name, size = 40, className }: CompanyFaviconProps) {
  const host = hostFrom(url);
  const [failed, setFailed] = React.useState(false);

  const shell = cn(
    "flex shrink-0 items-center justify-center overflow-hidden rounded-xl border bg-card font-semibold text-accent-foreground",
    SIZE_CLASS[size],
    className,
  );

  if (!host || failed) {
    return (
      <div className={cn(shell, "bg-accent")} aria-hidden="true">
        {getInitials(name)}
      </div>
    );
  }

  return (
    <div className={shell} aria-hidden="true">
      <img
        src={`https://www.google.com/s2/favicons?sz=64&domain=${host}`}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        className="size-full object-contain p-1"
        onError={() => setFailed(true)}
      />
    </div>
  );
}
