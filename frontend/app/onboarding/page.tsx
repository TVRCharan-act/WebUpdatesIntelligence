"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Globe2, Newspaper, Trophy } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ThinkingState } from "@/components/intel/thinking-state";
import { useRouter } from "@/components/router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  baselineSource,
  createCompany,
  createSource,
  getApiErrorMessage,
  type WatchType,
} from "@/lib/api";
import { hostOf } from "@/lib/attribution";
import { clampMinutes } from "@/lib/cadence";
import { queryKeys } from "@/lib/query-keys";

const templates: { label: string; type: WatchType; icon: typeof Trophy }[] = [
  { label: "Track a competitor", type: "competitor", icon: Trophy },
  { label: "Watch an industry source", type: "industry", icon: Newspaper },
  { label: "Monitor your own site", type: "own", icon: Globe2 },
];

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selected, setSelected] = React.useState<WatchType>(templates[0].type);
  const [company, setCompany] = React.useState("");
  const [url, setUrl] = React.useState("");
  const [scheduleMinutes, setScheduleMinutes] = React.useState("60");

  const createMutation = useMutation({
    mutationFn: async () => {
      const createdCompany = await createCompany({ name: company.trim(), watch_type: selected });
      const source = await createSource({
        company_id: createdCompany.id,
        url: url.trim(),
        strategy: "parent",
        trace_js: false,
        js_bundle_sources: [],
        enabled: true,
        schedule_minutes: clampMinutes(scheduleMinutes),
      });
      await baselineSource(source.id);
      return source;
    },
    onSuccess: () => {
      toast.success("Your sentinel is on watch.");
      queryClient.invalidateQueries({ queryKey: queryKeys.companies });
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      router.replace("/dashboard");
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const domain = hostOf(url) || "the page";
  const scanLines = [
    `Taking up watch over ${domain}…`,
    "Learning what to look out for…",
    "Your sentinel is reporting for duty…",
  ];

  return (
    <div className="mx-auto grid max-w-4xl gap-6">
      <div>
        <h2 className="text-3xl font-semibold">What should your sentinel watch?</h2>
        <p className="mt-2 text-muted-foreground">
          Pick a starting point and add one URL. Your sentinel takes up watch and alerts you the
          moment anything changes.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {templates.map((template) => {
          const Icon = template.icon;
          return (
            <button
              key={template.type}
              type="button"
              disabled={createMutation.isPending}
              className={`rounded-xl border p-5 text-left transition hover:-translate-y-px hover:shadow-sm ${
                selected === template.type ? "border-primary bg-accent" : "bg-card"
              }`}
              onClick={() => setSelected(template.type)}
            >
              <Icon className="mb-4 size-5 text-primary" />
              <div className="font-semibold">{template.label}</div>
            </button>
          );
        })}
      </div>

      <Card>
        <CardContent className="p-6">
          {createMutation.isPending ? (
            <ThinkingState lines={scanLines} ariaLabel="Setting up your monitor" />
          ) : (
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                createMutation.mutate();
              }}
            >
              <div className="grid gap-2">
                <Label htmlFor="company">What should we call this?</Label>
                <Input
                  id="company"
                  value={company}
                  onChange={(event) => setCompany(event.target.value)}
                  placeholder="Acme"
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="url">Website URL</Label>
                <Input
                  id="url"
                  type="url"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://example.com/pricing"
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="cadence">Check every (minutes)</Label>
                <Input
                  id="cadence"
                  type="number"
                  min={1}
                  step={1}
                  value={scheduleMinutes}
                  onChange={(event) => setScheduleMinutes(event.target.value)}
                  placeholder="60"
                  required
                />
                <p className="text-xs text-muted-foreground">
                  How often your sentinel re-checks this site. e.g. 60 = hourly, 1440 = daily.
                </p>
              </div>
              <Button>
                Start monitoring
                <ArrowRight />
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
