"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ExternalLink,
  MailCheck,
  MailWarning,
  Pencil,
  Plus,
  Save,
  Send,
  Trash2,
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { Link } from "@/components/router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  createCompanyRecipient,
  deleteNotificationRecipient,
  getApiErrorMessage,
  getEmailNotificationSettings,
  getSesStatus,
  listCompanyRecipients,
  listEmailSummaries,
  sendEmailSummary,
  updateNotificationRecipient,
  updateEmailNotificationSettings,
  type CompanyNotificationRecipients,
  type EmailSummary,
  type NotificationRecipient,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime, truncate } from "@/lib/utils";

function summarySubject(summary: EmailSummary) {
  return summary.title || "Website update";
}

function recipientLabel(recipients: string[]) {
  if (recipients.length === 0) {
    return "No enabled recipients";
  }

  if (recipients.length === 1) {
    return recipients[0];
  }

  return `${recipients[0]} +${recipients.length - 1}`;
}

export default function EmailPage() {
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = React.useState<Record<number, string>>({});
  const [editing, setEditing] = React.useState<Record<number, string>>({});
  const [companyFilter, setCompanyFilter] = React.useState("all");

  const selectedCompanyId =
    companyFilter === "all" ? undefined : Number(companyFilter);

  const sesQuery = useQuery({
    queryKey: queryKeys.sesStatus,
    queryFn: getSesStatus,
  });
  const settingsQuery = useQuery({
    queryKey: queryKeys.emailSettings,
    queryFn: getEmailNotificationSettings,
  });
  const recipientsQuery = useQuery({
    queryKey: queryKeys.companyRecipients,
    queryFn: listCompanyRecipients,
  });
  const summariesQuery = useQuery({
    queryKey: queryKeys.emailSummaries(selectedCompanyId),
    queryFn: () => listEmailSummaries(selectedCompanyId),
  });

  const invalidateEmailData = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.companyRecipients });
    queryClient.invalidateQueries({ queryKey: ["email", "summaries"] });
  };

  const settingsMutation = useMutation({
    mutationFn: updateEmailNotificationSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.emailSettings });
      queryClient.invalidateQueries({ queryKey: ["email", "summaries"] });
      toast.success("Email mode updated.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const createRecipientMutation = useMutation({
    mutationFn: ({
      companyId,
      email,
    }: {
      companyId: number;
      email: string;
    }) =>
      createCompanyRecipient(companyId, {
        email,
        enabled: true,
      }),
    onSuccess: (_, variables) => {
      setDrafts((current) => ({ ...current, [variables.companyId]: "" }));
      invalidateEmailData();
      toast.success("Recipient added.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const updateRecipientMutation = useMutation({
    mutationFn: ({
      recipientId,
      input,
    }: {
      recipientId: number;
      input: Partial<Pick<NotificationRecipient, "email" | "enabled">>;
    }) => updateNotificationRecipient(recipientId, input),
    onSuccess: () => {
      invalidateEmailData();
      toast.success("Recipient updated.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const deleteRecipientMutation = useMutation({
    mutationFn: deleteNotificationRecipient,
    onSuccess: () => {
      invalidateEmailData();
      toast.success("Recipient deleted.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const sendSummaryMutation = useMutation({
    mutationFn: sendEmailSummary,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["email", "summaries"] });
      toast.success(result.message);
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const companies: CompanyNotificationRecipients[] = recipientsQuery.data || [];
  const summaries = summariesQuery.data || [];
  const notificationMode = settingsQuery.data?.mode || "manual";
  const recipientCount = companies.reduce(
    (count, company) => count + company.recipients.length,
    0,
  );
  const enabledRecipientCount = companies.reduce(
    (count, company) =>
      count + company.recipients.filter((recipient) => recipient.enabled).length,
    0,
  );
  const readySummaryCount = summaries.filter((summary) => summary.would_send).length;

  function addRecipient(companyId: number) {
    const email = drafts[companyId]?.trim();
    if (!email) {
      toast.error("Enter a recipient email.");
      return;
    }

    createRecipientMutation.mutate({ companyId, email });
  }

  function saveRecipient(recipient: NotificationRecipient) {
    const email = editing[recipient.id]?.trim();
    if (!email) {
      toast.error("Enter a recipient email.");
      return;
    }

    updateRecipientMutation.mutate(
      {
        recipientId: recipient.id,
        input: { email },
      },
      {
        onSuccess: () =>
          setEditing((current) => {
            const next = { ...current };
            delete next[recipient.id];
            return next;
          }),
      },
    );
  }

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Email</h2>
        <p className="text-sm text-muted-foreground">
          Manage company recipients and review LLM summaries before they are sent.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              SES Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={sesQuery.data?.configured ? "success" : "warning"}>
              {sesQuery.data?.configured ? "Configured" : "Needs setup"}
            </Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              Companies
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">{companies.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              Enabled Recipients
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">{enabledRecipientCount}</div>
            <div className="text-xs text-muted-foreground">
              {recipientCount} total
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              Ready Summaries
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">{readySummaryCount}</div>
            <div className="text-xs text-muted-foreground">
              {summaries.length} visible
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Email notification mode</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm font-medium">
              {notificationMode === "automatic"
                ? "Automatic sending"
                : "Manual approval"}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {notificationMode === "automatic"
                ? "New LLM summaries are emailed as soon as processing succeeds."
                : "New LLM summaries stay queued until you press Send."}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant={notificationMode === "manual" ? "default" : "outline"}
              onClick={() => settingsMutation.mutate({ mode: "manual" })}
              disabled={settingsMutation.isPending}
            >
              Manual
            </Button>
            <Button
              variant={notificationMode === "automatic" ? "default" : "outline"}
              onClick={() => settingsMutation.mutate({ mode: "automatic" })}
              disabled={settingsMutation.isPending}
            >
              Automatic
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {sesQuery.data?.configured ? (
              <MailCheck className="size-5" />
            ) : (
              <MailWarning className="size-5" />
            )}
            Amazon SES configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <div className="text-xs font-medium uppercase text-muted-foreground">Region</div>
              <div className="mt-1 text-sm">{sesQuery.data?.ses_region || "-"}</div>
            </div>
            <div>
              <div className="text-xs font-medium uppercase text-muted-foreground">
                Sender
              </div>
              <div className="mt-1 text-sm">{sesQuery.data?.sender || "-"}</div>
            </div>
            <div>
              <div className="text-xs font-medium uppercase text-muted-foreground">
                Configuration set
              </div>
              <div className="mt-1 text-sm">{sesQuery.data?.configuration_set || "Not configured"}</div>
            </div>
          </div>

          {!sesQuery.data?.configured ? (
            <div className="rounded-md border border-border bg-secondary p-3 text-sm text-foreground">
              Missing environment values:{" "}
              {(sesQuery.data?.missing || []).join(", ") || "SES settings"}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Company recipients</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-5">
          {!recipientsQuery.isLoading && companies.length === 0 ? (
            <EmptyState
              icon={MailWarning}
              title="No companies"
              description="Create companies first, then add recipients for each company."
            />
          ) : null}

          {companies.map((company) => (
            <div key={company.id} className="rounded-lg border">
              <div className="flex flex-col gap-3 border-b bg-secondary/35 p-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="font-medium">{company.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {company.recipients.length} recipients
                  </div>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Input
                    placeholder="recipient@example.com"
                    value={drafts[company.id] || ""}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [company.id]: event.target.value,
                      }))
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        addRecipient(company.id);
                      }
                    }}
                  />
                  <Button
                    onClick={() => addRecipient(company.id)}
                    disabled={createRecipientMutation.isPending}
                  >
                    <Plus className="size-4" />
                    Add
                  </Button>
                </div>
              </div>

              {company.recipients.length === 0 ? (
                <div className="p-4 text-sm text-muted-foreground">
                  No recipients for this company yet.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Email</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead className="w-28">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {company.recipients.map((recipient) => {
                      const isEditing = recipient.id in editing;
                      return (
                        <TableRow key={recipient.id}>
                          <TableCell>
                            {isEditing ? (
                              <Input
                                value={editing[recipient.id]}
                                onChange={(event) =>
                                  setEditing((current) => ({
                                    ...current,
                                    [recipient.id]: event.target.value,
                                  }))
                                }
                              />
                            ) : (
                              <span className="font-medium">
                                {recipient.email}
                              </span>
                            )}
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Switch
                                checked={recipient.enabled}
                                onCheckedChange={(enabled) =>
                                  updateRecipientMutation.mutate({
                                    recipientId: recipient.id,
                                    input: { enabled },
                                  })
                                }
                                aria-label="Toggle recipient"
                              />
                              <Badge
                                variant={
                                  recipient.enabled ? "success" : "secondary"
                                }
                              >
                                {recipient.enabled ? "Enabled" : "Paused"}
                              </Badge>
                            </div>
                          </TableCell>
                          <TableCell>{formatDateTime(recipient.updated_at)}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              {isEditing ? (
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  onClick={() => saveRecipient(recipient)}
                                  aria-label="Save recipient"
                                >
                                  <Save />
                                </Button>
                              ) : (
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  onClick={() =>
                                    setEditing((current) => ({
                                      ...current,
                                      [recipient.id]: recipient.email,
                                    }))
                                  }
                                  aria-label="Edit recipient"
                                >
                                  <Pencil />
                                </Button>
                              )}
                              <Button
                                size="icon"
                                variant="ghost"
                                onClick={() =>
                                  deleteRecipientMutation.mutate(recipient.id)
                                }
                                aria-label="Delete recipient"
                              >
                                <Trash2 />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <span>LLM email summaries</span>
            <div className="w-full lg:w-72">
              <Label htmlFor="company-filter" className="sr-only">
                Filter company
              </Label>
              <Select value={companyFilter} onValueChange={setCompanyFilter}>
                <SelectTrigger id="company-filter">
                  <SelectValue placeholder="All companies" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All companies</SelectItem>
                  {companies.map((company) => (
                    <SelectItem key={company.id} value={String(company.id)}>
                      {company.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          {!summariesQuery.isLoading && summaries.length === 0 ? (
            <EmptyState
              icon={MailWarning}
              title="No summaries yet"
              description="Run monitors and summary generation to populate email-ready outputs."
            />
          ) : null}

          {summaries.map((summary) => (
            <div key={summary.id} className="rounded-lg border p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={summary.would_send ? "success" : "warning"}
                    >
                      {summary.email_status === "sent"
                        ? "Sent"
                        : summary.would_send
                          ? "Ready to send"
                          : "Not ready"}
                    </Badge>
                    <Badge variant="outline">{summary.email_status}</Badge>
                    <Badge variant="secondary">{summary.company_name}</Badge>
                    {summary.model ? (
                      <Badge variant="outline">{summary.model}</Badge>
                    ) : null}
                  </div>
                  <h3 className="mt-3 text-base font-semibold">
                    {summarySubject(summary)}
                  </h3>
                  <div className="mt-1 text-sm text-muted-foreground">
                    To: {recipientLabel(summary.recipients)}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {notificationMode === "manual" &&
                  summary.email_status !== "sent" ? (
                    <Button
                      onClick={() => sendSummaryMutation.mutate(summary.id)}
                      disabled={
                        sendSummaryMutation.isPending || !summary.would_send
                      }
                    >
                      <Send className="size-4" />
                      Send
                    </Button>
                  ) : null}
                  <Button asChild size="icon" variant="ghost">
                    <a
                      href={summary.discovered_url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label="Open discovered URL"
                    >
                      <ExternalLink />
                    </a>
                  </Button>
                </div>
              </div>

              <div className="mt-4 rounded-md bg-secondary/35 p-3 text-sm leading-6 whitespace-pre-wrap">
                {summary.summary}
              </div>

              <div className="mt-4 grid gap-2 text-xs text-muted-foreground lg:grid-cols-3">
                <div>Created: {formatDateTime(summary.created_at)}</div>
                <div>
                  Source:{" "}
                  <Link
                    href={`/sources/${summary.source_id}`}
                    className="text-primary"
                  >
                    {truncate(summary.source_url, 52)}
                  </Link>
                </div>
                <div>
                  {summary.email_sent_at
                    ? `Sent: ${formatDateTime(summary.email_sent_at)}`
                    : `Recipients: ${summary.recipient_count}`}
                </div>
              </div>
              {summary.email_error ? (
                <div className="mt-3 rounded-md border border-border bg-secondary p-3 text-sm text-foreground">
                  {summary.email_error}
                </div>
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
