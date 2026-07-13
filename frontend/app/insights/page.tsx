"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpDown, Search } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { AnalystEmptyState } from "@/components/intel/analyst-empty-state";
import { InsightCard } from "@/components/intel/insight-card";
import { PRIORITY_RANK } from "@/components/intel/priority-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getApiErrorMessage,
  listCompanies,
  listInsights,
  listSources,
  updateInsightReview,
  type Summary,
} from "@/lib/api";
import { type Attribution, hostOf, makeAttributor } from "@/lib/attribution";
import { queryKeys } from "@/lib/query-keys";

type SortKey =
  | "recent"
  | "oldest"
  | "priority"
  | "severity"
  | "confidence"
  | "company_new"
  | "company_old"
  | "company_az";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "recent", label: "Newest update first" },
  { value: "oldest", label: "Oldest update first" },
  { value: "priority", label: "Company priority (high → low)" },
  { value: "severity", label: "Severity (high → low)" },
  { value: "confidence", label: "AI confidence (high → low)" },
  { value: "company_new", label: "Company added (newest)" },
  { value: "company_old", label: "Company added (earliest)" },
  { value: "company_az", label: "Company name (A → Z)" },
];

const LEVEL_RANK: Record<"low" | "medium" | "high", number> = { high: 3, medium: 2, low: 1 };

interface Enriched {
  insight: Summary;
  attr: Attribution;
}

function timeOf(iso: string | null | undefined): number {
  return iso ? new Date(iso).getTime() : 0;
}

function dayLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOf(now) - startOf(d)) / 86400000);
  if (diffDays <= 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(d);
}

function comparator(sort: SortKey): (a: Enriched, b: Enriched) => number {
  const recent = (a: Enriched, b: Enriched) =>
    timeOf(b.insight.created_at) - timeOf(a.insight.created_at);
  switch (sort) {
    case "oldest":
      return (a, b) => timeOf(a.insight.created_at) - timeOf(b.insight.created_at);
    case "priority":
      return (a, b) =>
        PRIORITY_RANK[b.attr.company?.priority ?? "medium"] -
          PRIORITY_RANK[a.attr.company?.priority ?? "medium"] || recent(a, b);
    case "severity":
      return (a, b) =>
        LEVEL_RANK[b.insight.severity] - LEVEL_RANK[a.insight.severity] || recent(a, b);
    case "confidence":
      return (a, b) =>
        LEVEL_RANK[b.insight.confidence] - LEVEL_RANK[a.insight.confidence] || recent(a, b);
    case "company_new":
      return (a, b) =>
        timeOf(b.attr.company?.created_at) - timeOf(a.attr.company?.created_at) || recent(a, b);
    case "company_old":
      return (a, b) =>
        (timeOf(a.attr.company?.created_at) || Infinity) -
          (timeOf(b.attr.company?.created_at) || Infinity) || recent(a, b);
    case "company_az":
      return (a, b) =>
        (a.attr.companyName || a.attr.domain || "~").localeCompare(
          b.attr.companyName || b.attr.domain || "~",
        ) || recent(a, b);
    default:
      return recent;
  }
}

export default function InsightsPage() {
  const [search, setSearch] = React.useState("");
  const [toReviewOnly, setToReviewOnly] = React.useState(false);
  const [sortBy, setSortBy] = React.useState<SortKey>("recent");
  const queryClient = useQueryClient();

  const insightsQuery = useQuery({ queryKey: queryKeys.insights, queryFn: () => listInsights(200) });
  const sourcesQuery = useQuery({ queryKey: queryKeys.sources, queryFn: listSources });
  const companiesQuery = useQuery({ queryKey: queryKeys.companies, queryFn: listCompanies });

  const reviewMutation = useMutation({
    mutationFn: (id: number) => updateInsightReview(id, true),
    onSuccess: () => {
      toast.success("Insight marked reviewed.");
      queryClient.invalidateQueries({ queryKey: queryKeys.insights });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const attribute = React.useMemo(
    () => makeAttributor(sourcesQuery.data || [], companiesQuery.data || []),
    [sourcesQuery.data, companiesQuery.data],
  );

  const term = search.trim().toLowerCase();
  const enriched: Enriched[] = React.useMemo(() => {
    return (insightsQuery.data || [])
      .filter((insight) => {
        const text = `${insight.title || ""} ${insight.summary} ${insight.discovered_url}`.toLowerCase();
        const matchesSearch = text.includes(term);
        const matchesReview = !toReviewOnly || !insight.reviewed_at;
        return matchesSearch && matchesReview;
      })
      .map((insight) => ({ insight, attr: attribute(insight.discovered_url) }))
      .sort(comparator(sortBy));
  }, [insightsQuery.data, term, toReviewOnly, sortBy, attribute]);

  // Highlight insights genuinely new since the last fetch (tracked on full set).
  const allIds = React.useMemo(
    () => (insightsQuery.data || []).map((i) => i.id),
    [insightsQuery.data],
  );
  const prevIdsRef = React.useRef<Set<number> | null>(null);
  const highlightIds = React.useMemo(() => {
    const prev = prevIdsRef.current;
    if (!prev) return new Set<number>();
    return new Set(allIds.filter((id) => !prev.has(id)));
  }, [allIds]);
  React.useEffect(() => {
    prevIdsRef.current = new Set(allIds);
  }, [allIds]);

  // Group by day only for the time-based sorts; otherwise a single flat list.
  const grouped = sortBy === "recent" || sortBy === "oldest";
  const sections = React.useMemo(() => {
    if (!grouped) return [["", enriched]] as [string, Enriched[]][];
    const map = new Map<string, Enriched[]>();
    for (const item of enriched) {
      const label = dayLabel(item.insight.created_at);
      const bucket = map.get(label);
      if (bucket) bucket.push(item);
      else map.set(label, [item]);
    }
    return Array.from(map.entries());
  }, [enriched, grouped]);

  const isLoading = insightsQuery.isLoading;
  const hasAny = (insightsQuery.data || []).length > 0;

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Insights</h2>
          <p className="text-sm text-muted-foreground">
            What changed across everything you watch — sort it however helps you act.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <Input
              className="pl-9 sm:w-64"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search insights"
            />
          </div>
          <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortKey)}>
            <SelectTrigger className="sm:w-56" aria-label="Sort insights">
              <ArrowUpDown className="size-4 text-muted-foreground" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant={toReviewOnly ? "default" : "outline"}
            onClick={() => setToReviewOnly((value) => !value)}
          >
            To review
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
          Loading insights…
        </div>
      ) : !hasAny ? (
        <AnalystEmptyState
          title="Your feed is quiet"
          body="Your sentinel is on watch. The instant a page it guards changes, the update lands here first."
          action={{ label: "Add a monitor", href: "/monitors" }}
        />
      ) : !enriched.length ? (
        <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
          Nothing matches — try clearing your filters.
        </div>
      ) : (
        <div className="grid gap-6">
          {sections.map(([label, items]) => (
            <section key={label || "all"} className="grid gap-3">
              {label ? (
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {label}
                </h3>
              ) : null}
              {items.map(({ insight, attr }, i) => (
                <InsightCard
                  key={insight.id}
                  insight={insight}
                  companyName={attr.companyName || attr.domain || "Website update"}
                  sourceLabel={hostOf(insight.discovered_url) || undefined}
                  priority={attr.company?.priority}
                  onReview={(id) => reviewMutation.mutate(id)}
                  isReviewing={reviewMutation.isPending}
                  index={i}
                  highlight={highlightIds.has(insight.id)}
                />
              ))}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
