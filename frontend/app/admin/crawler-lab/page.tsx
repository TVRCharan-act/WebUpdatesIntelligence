"use client";

import { useMutation } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock3,
  FlaskConical,
  Link2,
  Scale,
  XCircle,
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ThinkingState } from "@/components/intel/thinking-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  compareCrawlers,
  getApiErrorMessage,
  type CrawlerLabCompareResult,
  type CrawlerLabProvider,
  type CrawlerLabProviderResult,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const PROVIDER_LABELS: Record<CrawlerLabProvider, string> = {
  zenrows: "ZenRows",
  crawl4ai: "Crawl4AI",
};

function StatRow({
  label,
  icon: Icon,
  children,
}: {
  label: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </span>
      <span className="font-mono tabular-nums">{children}</span>
    </div>
  );
}

function ProviderResultCard({
  result,
  isWinner,
}: {
  result: CrawlerLabProviderResult;
  isWinner: boolean;
}) {
  return (
    <Card className={cn(isWinner && "border-primary")}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2">
          {PROVIDER_LABELS[result.provider]}
          {isWinner ? <Badge>Judge&apos;s pick</Badge> : null}
        </CardTitle>
        {result.success ? (
          <Badge variant="success" className="flex items-center gap-1">
            <CheckCircle2 className="size-3" />
            Success
          </Badge>
        ) : (
          <Badge variant="destructive" className="flex items-center gap-1">
            <XCircle className="size-3" />
            Failed
          </Badge>
        )}
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-2 rounded-lg border p-3">
          <div className="text-xs font-semibold uppercase text-muted-foreground">Discovery (link extraction)</div>
          <StatRow label="Latency" icon={Clock3}>
            {result.discovery_latency_seconds}s
          </StatRow>
          <StatRow label="Links found" icon={Link2}>
            {result.discovery_link_count}
          </StatRow>
          {result.discovery_error ? (
            <p className="text-xs text-destructive">{result.discovery_error}</p>
          ) : result.discovery_sample_links.length ? (
            <ul className="mt-1 grid gap-0.5 text-xs text-muted-foreground">
              {result.discovery_sample_links.slice(0, 5).map((link) => (
                <li key={link} className="truncate">
                  {link}
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="grid gap-2 rounded-lg border p-3">
          <div className="text-xs font-semibold uppercase text-muted-foreground">Content acquisition</div>
          <StatRow label="Latency" icon={Clock3}>
            {result.content_latency_seconds}s
          </StatRow>
          <StatRow label="Content length" icon={FlaskConical}>
            {result.content_length.toLocaleString()} chars
          </StatRow>
          {result.content_error ? (
            <p className="text-xs text-destructive">{result.content_error}</p>
          ) : (
            <>
              {result.content_title ? (
                <p className="text-xs font-medium">{result.content_title}</p>
              ) : null}
              {result.content_snippet ? (
                <p className="line-clamp-4 text-xs text-muted-foreground">{result.content_snippet}</p>
              ) : null}
            </>
          )}
        </div>

        <StatRow label="Total latency" icon={Clock3}>
          {result.total_latency_seconds}s
        </StatRow>
      </CardContent>
    </Card>
  );
}

export default function CrawlerLabPage() {
  const [url, setUrl] = React.useState("");
  const [result, setResult] = React.useState<CrawlerLabCompareResult | null>(null);

  const compareMutation = useMutation({
    mutationFn: (targetUrl: string) => compareCrawlers(targetUrl),
    onSuccess: (data) => {
      setResult(data);
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    setResult(null);
    compareMutation.mutate(trimmed);
  }

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Crawler Lab</h2>
        <p className="text-sm text-muted-foreground">
          Run any page through both crawler pipelines side by side — ZenRows and Crawl4AI — and see
          which one performs better for that specific site, with an AI judge to help decide.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="size-4" />
            Run a comparison
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={handleSubmit}>
            <div className="grid flex-1 gap-2">
              <Label htmlFor="lab-url">Page URL</Label>
              <Input
                id="lab-url"
                type="url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://example.com/news"
                required
              />
            </div>
            <Button disabled={compareMutation.isPending}>
              {compareMutation.isPending ? "Running" : "Run comparison"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {compareMutation.isPending ? (
        <Card>
          <CardContent className="py-8">
            <ThinkingState
              lines={[
                "Crawling with ZenRows…",
                "Crawling with Crawl4AI…",
                "Asking the judge which one did better…",
              ]}
              ariaLabel="Running crawler comparison"
            />
          </CardContent>
        </Card>
      ) : null}

      {result ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            {result.results.map((providerResult) => (
              <ProviderResultCard
                key={providerResult.provider}
                result={providerResult}
                isWinner={result.judge.winner === providerResult.provider}
              />
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Scale className="size-4" />
                Judge&apos;s verdict
                {result.judge.model ? (
                  <span className="text-xs font-normal text-muted-foreground">via {result.judge.model}</span>
                ) : null}
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              {result.judge.available ? (
                <>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Winner:</span>
                    <Badge variant={result.judge.winner === "tie" ? "secondary" : "default"}>
                      {result.judge.winner === "tie"
                        ? "Tie"
                        : PROVIDER_LABELS[result.judge.winner as CrawlerLabProvider]}
                    </Badge>
                  </div>
                  <p className="text-sm">{result.judge.reasoning}</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div className="rounded-lg border p-3 text-xs">
                      <div className="mb-1 font-semibold">ZenRows</div>
                      {result.judge.zenrows_notes}
                    </div>
                    <div className="rounded-lg border p-3 text-xs">
                      <div className="mb-1 font-semibold">Crawl4AI</div>
                      {result.judge.crawl4ai_notes}
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No verdict available: {result.judge.error || "judging is not configured."}
                </p>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
