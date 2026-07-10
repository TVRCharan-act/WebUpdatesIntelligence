"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { AnalystEmptyState } from "@/components/intel/analyst-empty-state";
import { InsightCard } from "@/components/intel/insight-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  getApiErrorMessage,
  listCompanies,
  listInsights,
  listSources,
  updateInsightReview,
  type Summary,
} from "@/lib/api";
import { hostOf, makeAttributor } from "@/lib/attribution";
import { queryKeys } from "@/lib/query-keys";

function dayLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOf(now) - startOf(d)) / 86400000);
  if (diffDays <= 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(d);
}

export default function InsightsPage() {
  const [search, setSearch] = React.useState("");
  const [toReviewOnly, setToReviewOnly] = React.useState(false);
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
  const insights = (insightsQuery.data || [])
    .filter((insight) => {
      const text = `${insight.title || ""} ${insight.summary} ${insight.discovered_url}`.toLowerCase();
      const matchesSearch = text.includes(term);
      const matchesReview = !toReviewOnly || !insight.reviewed_at;
      return matchesSearch && matchesReview;
    })
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  // Highlight insights that are genuinely new since the last fetch (§17.3).
  // Tracked against the full dataset so search/filter changes never flag items.
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

  const groups = React.useMemo(() => {
    const map = new Map<string, Summary[]>();
    for (const insight of insights) {
      const label = dayLabel(insight.created_at);
      const bucket = map.get(label);
      if (bucket) bucket.push(insight);
      else map.set(label, [insight]);
    }
    return Array.from(map.entries());
  }, [insights]);

  const isLoading = insightsQuery.isLoading;
  const hasAny = (insightsQuery.data || []).length > 0;

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Insights</h2>
          <p className="text-sm text-muted-foreground">
            What changed across everything you watch — newest first.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <Input
              className="pl-9 sm:w-80"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search insights"
            />
          </div>
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
      ) : !insights.length ? (
        <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
          Nothing matches — try clearing your filters.
        </div>
      ) : (
        <div className="grid gap-6">
          {groups.map(([label, items]) => (
            <section key={label} className="grid gap-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {label}
              </h3>
              {items.map((insight, i) => {
                const { companyName, domain } = attribute(insight.discovered_url);
                return (
                  <InsightCard
                    key={insight.id}
                    insight={insight}
                    companyName={companyName || domain || "Website update"}
                    sourceLabel={hostOf(insight.discovered_url) || undefined}
                    onReview={(id) => reviewMutation.mutate(id)}
                    isReviewing={reviewMutation.isPending}
                    index={i}
                    highlight={highlightIds.has(insight.id)}
                  />
                );
              })}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
