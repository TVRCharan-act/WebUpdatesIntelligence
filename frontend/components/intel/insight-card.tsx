"use client";

import { CheckCircle2, ExternalLink } from "lucide-react";

import { CompanyFavicon } from "@/components/intel/company-favicon";
import { ConfidenceSignal } from "@/components/intel/confidence-signal";
import { PriorityBadge } from "@/components/intel/priority-badge";
import { SeverityBadge } from "@/components/intel/severity-badge";
import { Button } from "@/components/ui/button";
import type { Priority, Summary } from "@/lib/api";
import { parseInsight } from "@/lib/parse-insight";
import { cn, formatRelativeTime } from "@/lib/utils";

// The insight rendered as an analyst's note: a sharp headline and one flowing
// paragraph that carries the significance in its prose — no labeled
// sub-sections. Severity and AI confidence are shown as glanceable signals
// (Build Spec §14.4). parseInsight keeps older labeled rows readable by pulling
// out the headline and body; new rows are already a clean paragraph.

interface InsightCardProps {
  insight: Summary;
  companyName: string;
  sourceLabel?: string;
  density?: "feed" | "compact";
  onReview?: (id: number) => void;
  isReviewing?: boolean;
  index?: number;
  highlight?: boolean;
  /** Owning company's priority, shown as a badge (customer-set). */
  priority?: Priority;
}

export function InsightCard({
  insight,
  companyName,
  sourceLabel,
  density = "feed",
  onReview,
  isReviewing,
  index = 0,
  highlight = false,
  priority,
}: InsightCardProps) {
  const parsed = parseInsight(insight.summary);
  const headline = parsed.headline || insight.title || "Website update";
  const body = parsed.whatHappened || insight.summary;
  const reviewed = Boolean(insight.reviewed_at);

  const motionClass = highlight ? "animate-highlight" : "animate-enter";
  const motionStyle = highlight ? undefined : { animationDelay: `${Math.min(index, 7) * 40}ms` };

  // Reviewed insights collapse to a single scannable line, history preserved.
  if (reviewed) {
    return (
      <article
        className={cn("flex items-center gap-3 rounded-xl border bg-card/60 px-4 py-3", motionClass)}
        style={motionStyle}
      >
        <CompanyFavicon url={insight.discovered_url} name={companyName} size={24} />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-muted-foreground">
          {headline}
        </span>
        <CheckCircle2 className="size-4 shrink-0 text-emerald-600" aria-label="Reviewed" />
        <span className="shrink-0 text-xs text-muted-foreground">
          {formatRelativeTime(insight.created_at)}
        </span>
        <a
          href={insight.discovered_url}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 text-muted-foreground hover:text-primary"
          aria-label="View original page"
        >
          <ExternalLink className="size-3.5" />
        </a>
      </article>
    );
  }

  return (
    <article
      className={cn("rounded-xl border bg-card p-4 shadow-sm transition hover:shadow-md", motionClass)}
      style={motionStyle}
    >
      <div className="flex items-center gap-3">
        <CompanyFavicon url={insight.discovered_url} name={companyName} size={32} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="truncate font-medium text-foreground">{companyName}</span>
            {sourceLabel ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="truncate">{sourceLabel}</span>
              </>
            ) : null}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
          <ConfidenceSignal level={insight.confidence} />
          <span>{formatRelativeTime(insight.created_at)}</span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-start gap-2">
        <h3 className={cn("font-semibold", density === "feed" ? "text-base" : "text-sm")}>
          {headline}
        </h3>
        <SeverityBadge severity={insight.severity} />
        {priority ? <PriorityBadge priority={priority} /> : null}
      </div>

      {body ? (
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
      ) : null}

      <div className="mt-4 flex items-center justify-between gap-3">
        {onReview ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onReview(insight.id)}
            disabled={isReviewing}
          >
            <CheckCircle2 />
            Mark reviewed
          </Button>
        ) : (
          <span />
        )}
        <Button asChild size="sm" variant="ghost">
          <a href={insight.discovered_url} target="_blank" rel="noreferrer">
            View original
            <ExternalLink />
          </a>
        </Button>
      </div>
    </article>
  );
}
