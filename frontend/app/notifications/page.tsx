"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Mail, Plus, Trash2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  createCompanyRecipient,
  deleteNotificationRecipient,
  getApiErrorMessage,
  getEmailNotificationSettings,
  listCompanyRecipients,
  updateEmailNotificationSettings,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const [emailByCompany, setEmailByCompany] = React.useState<Record<number, string>>({});
  const recipientsQuery = useQuery({
    queryKey: queryKeys.companyRecipients,
    queryFn: listCompanyRecipients,
  });
  const settingsQuery = useQuery({
    queryKey: queryKeys.emailSettings,
    queryFn: getEmailNotificationSettings,
  });

  const settingsMutation = useMutation({
    mutationFn: updateEmailNotificationSettings,
    onSuccess: () => {
      toast.success("Notification cadence updated.");
      queryClient.invalidateQueries({ queryKey: queryKeys.emailSettings });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const addMutation = useMutation({
    mutationFn: ({ companyId, email }: { companyId: number; email: string }) =>
      createCompanyRecipient(companyId, { email, enabled: true }),
    onSuccess: () => {
      toast.success("Recipient added.");
      setEmailByCompany({});
      queryClient.invalidateQueries({ queryKey: queryKeys.companyRecipients });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteNotificationRecipient,
    onSuccess: () => {
      toast.success("Recipient removed.");
      queryClient.invalidateQueries({ queryKey: queryKeys.companyRecipients });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const mode = settingsQuery.data?.mode || "manual";

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Notifications</h2>
        <p className="text-sm text-muted-foreground">
          Decide when your sentinel reaches out, and who it reaches.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="size-4" />
            When to send alerts
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {[
            { label: "Automatic", value: "automatic", detail: "Send each update the moment your sentinel spots it." },
            { label: "Manual review", value: "manual", detail: "Send only the updates your team approves first." },
          ].map((option) => (
            <button
              key={option.label}
              className={`rounded-xl border p-4 text-left transition hover:-translate-y-px hover:shadow-sm ${
                mode === option.value ? "border-primary bg-accent" : "bg-card"
              }`}
              onClick={() => settingsMutation.mutate({ mode: option.value as "manual" | "automatic" })}
            >
              <div className="font-semibold">{option.label}</div>
              <p className="mt-1 text-sm text-muted-foreground">{option.detail}</p>
            </button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="size-4" />
            Alert recipients
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-5">
          {(recipientsQuery.data || []).map((company) => (
            <section key={company.id} className="rounded-xl border p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <h3 className="font-semibold">{company.name}</h3>
                <Badge variant="secondary">{company.recipients.length} recipients</Badge>
              </div>
              <div className="flex flex-wrap gap-2">
                {company.recipients.map((recipient) => (
                  <span key={recipient.id} className="inline-flex items-center gap-2 rounded-full border bg-secondary px-3 py-1 text-sm">
                    {recipient.email}
                    <button aria-label={`Remove ${recipient.email}`} onClick={() => deleteMutation.mutate(recipient.id)}>
                      <Trash2 className="size-3.5" />
                    </button>
                  </span>
                ))}
              </div>
              <form
                className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end"
                onSubmit={(event) => {
                  event.preventDefault();
                  addMutation.mutate({
                    companyId: company.id,
                    email: emailByCompany[company.id] || "",
                  });
                }}
              >
                <div className="grid flex-1 gap-2">
                  <Label htmlFor={`recipient-${company.id}`}>Add recipient</Label>
                  <Input
                    id={`recipient-${company.id}`}
                    type="email"
                    value={emailByCompany[company.id] || ""}
                    onChange={(event) =>
                      setEmailByCompany((current) => ({
                        ...current,
                        [company.id]: event.target.value,
                      }))
                    }
                    placeholder="person@example.com"
                    required
                  />
                </div>
                <Button>
                  <Plus />
                  Add
                </Button>
              </form>
            </section>
          ))}
          {!recipientsQuery.isLoading && !(recipientsQuery.data || []).length ? (
            <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
              Add a monitor before configuring recipients.
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
