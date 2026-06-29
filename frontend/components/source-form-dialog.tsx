"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  type Company,
  type Source,
  type SourceCreateInput,
  type SourceUpdateInput,
  type Strategy,
} from "@/lib/api";

interface FormState {
  company_id: string;
  url: string;
  strategy: Strategy;
  trace_js: boolean;
  js_bundle_sources: string;
  enabled: boolean;
  schedule_minutes: string;
}

function sourceToForm(source?: Source): FormState {
  return {
    company_id: source?.company_id ? String(source.company_id) : "",
    url: source?.url || "",
    strategy: source?.strategy || "parent",
    trace_js: source?.trace_js || false,
    js_bundle_sources: source?.js_bundle_sources?.join("\n") || "",
    enabled: source?.enabled ?? true,
    schedule_minutes: String(source?.schedule_minutes ?? 60),
  };
}

export function SourceFormDialog({
  open,
  companies,
  source,
  isSaving,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  companies: Company[];
  source?: Source;
  isSaving?: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (input: SourceCreateInput | SourceUpdateInput) => void;
}) {
  const [form, setForm] = React.useState<FormState>(() => sourceToForm(source));
  const isEdit = Boolean(source);

  React.useEffect(() => {
    if (open) {
      setForm(sourceToForm(source));
    }
  }, [open, source]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => {
      const next = {
        ...current,
        [key]: value,
      };

      if (key === "strategy" && value !== "parent") {
        next.trace_js = false;
      }

      return next;
    });
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const jsSources = form.js_bundle_sources
      .split("\n")
      .map((value) => value.trim())
      .filter(Boolean);

    const base = {
      url: form.url.trim(),
      strategy: form.strategy,
      trace_js: form.strategy === "parent" ? form.trace_js : false,
      js_bundle_sources: jsSources,
      enabled: form.enabled,
      schedule_minutes: Number(form.schedule_minutes || 0),
    };

    if (isEdit) {
      onSubmit(base);
      return;
    }

    onSubmit({
      ...base,
      company_id: Number(form.company_id),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit source" : "Add source"}</DialogTitle>
          <DialogDescription>
            Configure a monitor target and its discovery strategy.
          </DialogDescription>
        </DialogHeader>

        <form className="grid gap-4" onSubmit={handleSubmit}>
          <div className="grid gap-2">
            <Label htmlFor="company">Company</Label>
            <Select
              value={form.company_id}
              onValueChange={(value) => update("company_id", value)}
              disabled={isEdit}
              required
            >
              <SelectTrigger id="company">
                <SelectValue placeholder="Select company" />
              </SelectTrigger>
              <SelectContent>
                {companies.map((company) => (
                  <SelectItem key={company.id} value={String(company.id)}>
                    {company.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="url">URL</Label>
            <Input
              id="url"
              type="url"
              value={form.url}
              onChange={(event) => update("url", event.target.value)}
              placeholder="https://example.com"
              required
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="strategy">Strategy</Label>
              <Select
                value={form.strategy}
                onValueChange={(value) => update("strategy", value as Strategy)}
              >
                <SelectTrigger id="strategy">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="parent">Parent</SelectItem>
                  <SelectItem value="feed">Feed</SelectItem>
                  <SelectItem value="api">API</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="schedule">Schedule minutes</Label>
              <Input
                id="schedule"
                type="number"
                min={0}
                value={form.schedule_minutes}
                onChange={(event) =>
                  update("schedule_minutes", event.target.value)
                }
                required
              />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="js-bundles">JS bundle sources</Label>
            <Textarea
              id="js-bundles"
              value={form.js_bundle_sources}
              onChange={(event) =>
                update("js_bundle_sources", event.target.value)
              }
              placeholder="/_next/static/chunks/app.js"
            />
          </div>

          <div className="grid gap-3 rounded-lg border p-3 sm:grid-cols-2">
            <label className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium">Trace JS</span>
              <Switch
                checked={form.trace_js}
                disabled={form.strategy !== "parent"}
                onCheckedChange={(value) => update("trace_js", value)}
              />
            </label>
            <label className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium">Enabled</span>
              <Switch
                checked={form.enabled}
                onCheckedChange={(value) => update("enabled", value)}
              />
            </label>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving || companies.length === 0}>
              {isSaving ? "Saving" : "Save source"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
