"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { CadenceField } from "@/components/intel/cadence-field";
import { PRIORITY_OPTIONS } from "@/components/intel/priority-badge";
import { ThinkingState } from "@/components/intel/thinking-state";
import { useRouter } from "@/components/router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  baselineSource,
  createCompany,
  createSource,
  getApiErrorMessage,
  type Priority,
} from "@/lib/api";
import { hostOf } from "@/lib/attribution";
import { toMinutes, type CadenceUnit } from "@/lib/cadence";
import { queryKeys } from "@/lib/query-keys";

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [company, setCompany] = React.useState("");
  const [url, setUrl] = React.useState("");
  const [priority, setPriority] = React.useState<Priority>("medium");
  const [cadenceValue, setCadenceValue] = React.useState("1");
  const [cadenceUnit, setCadenceUnit] = React.useState<CadenceUnit>("hour");

  const createMutation = useMutation({
    mutationFn: async () => {
      const createdCompany = await createCompany({ name: company.trim(), priority });
      const source = await createSource({
        company_id: createdCompany.id,
        url: url.trim(),
        strategy: "parent",
        trace_js: false,
        js_bundle_sources: [],
        enabled: true,
        schedule_minutes: toMinutes(cadenceValue, cadenceUnit),
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
    <div className="mx-auto grid max-w-2xl gap-6">
      <div>
        <h2 className="text-3xl font-semibold">Post your first sentinel</h2>
        <p className="mt-2 text-muted-foreground">
          Name what you're tracking, add one URL, and set how important it is. Your sentinel takes up
          watch and alerts you the moment anything changes.
        </p>
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
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="priority">Priority</Label>
                  <Select value={priority} onValueChange={(v) => setPriority(v as Priority)}>
                    <SelectTrigger id="priority">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PRIORITY_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="cadence">Check every</Label>
                  <CadenceField
                    id="cadence"
                    value={cadenceValue}
                    unit={cadenceUnit}
                    onValueChange={setCadenceValue}
                    onUnitChange={setCadenceUnit}
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Priority helps you sort what matters most in your feed. You can change both later.
              </p>
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
