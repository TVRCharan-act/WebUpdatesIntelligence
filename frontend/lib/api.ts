import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { recordHealthEvent } from "@/lib/health-events";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

type TimedRequestConfig = InternalAxiosRequestConfig & {
  metadata?: {
    started_at: number;
  };
};

function nowMs() {
  if (typeof performance !== "undefined") {
    return performance.now();
  }

  return Date.now();
}

function logFrontendApiTiming(
  config: TimedRequestConfig | undefined,
  status: string,
  statusCode?: number,
  error?: string,
) {
  if (!config?.url) {
    return;
  }

  const startedAt = config.metadata?.started_at;
  const durationMs = startedAt ? nowMs() - startedAt : undefined;

  recordHealthEvent({
    event_type: "frontend_api",
    action: `${(config.method || "GET").toUpperCase()} ${config.url}`,
    status,
    duration_ms: durationMs,
    metadata: {
      method: (config.method || "GET").toUpperCase(),
      url: config.url,
      status_code: statusCode,
      error,
    },
  });
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const timedConfig = config as TimedRequestConfig;
  timedConfig.metadata = {
    started_at: nowMs(),
  };
  return timedConfig;
});

api.interceptors.response.use(
  (response) => {
    logFrontendApiTiming(
      response.config as TimedRequestConfig,
      response.status >= 500 ? "error" : "ok",
      response.status,
    );
    return response;
  },
  (error: AxiosError) => {
    logFrontendApiTiming(
      error.config as TimedRequestConfig | undefined,
      "error",
      error.response?.status,
      error.message,
    );
    return Promise.reject(error);
  },
);

export type Strategy = "parent" | "feed" | "api";


export interface DiscoveryHealth {
  status: string;
  openai_configured: boolean;
  openai_model: string;
  browser_tracing_available: boolean;
  adapter_cache_path: string;
  adapter_cache_exists: boolean;
  cached_adapter_count: number;
  recent_discovery_event_count: number;
  recent_discovery_error_count: number;
  heavy_discovery_lock: Record<string, string | number | boolean | null>;
  limits: Record<string, string | number | boolean | null>;
}
export interface MonitorStatus {
  enabled_sources: number;
  queued: number;
  running: number;
  completed_today: number;
  failed_today: number;
}

export interface QueuedTaskResponse {
  task_id: string;
  status: "queued";
}

export interface TaskStatus {
  task_id: string;
  state: string;
  result: unknown;
}

export function taskHasFailedResult(task: TaskStatus) {
  if (task.state === "FAILURE" || task.state === "REVOKED") {
    return true;
  }

  if (task.result && typeof task.result === "object" && !Array.isArray(task.result)) {
    const status = "status" in task.result ? task.result.status : undefined;
    return status === "failed" || status === "error";
  }

  if (Array.isArray(task.result)) {
    return task.result.some((item) => {
      if (!item || typeof item !== "object") {
        return false;
      }

      const status = "status" in item ? item.status : undefined;
      return status === "failed" || status === "error";
    });
  }

  return false;
}

export type Priority = "high" | "medium" | "low";

export interface Company {
  id: number;
  name: string;
  owner_name: string | null;
  priority: Priority;
  created_at: string;
  updated_at: string;
}

export interface CompanyInput {
  name: string;
  priority?: Priority;
}

export interface Source {
  id: number;
  company_id: number;
  url: string;
  strategy: Strategy;
  trace_js: boolean;
  js_bundle_sources: string[];
  enabled: boolean;
  schedule_minutes: number;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceCreateInput {
  company_id: number;
  url: string;
  strategy: Strategy;
  trace_js: boolean;
  js_bundle_sources: string[];
  enabled: boolean;
  schedule_minutes: number;
}

export type SourceUpdateInput = Partial<Omit<SourceCreateInput, "company_id">>;

export interface MonitorRun {
  id: number;
  source_id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface MonitorResult {
  status: string;
  source_id: number;
  strategy: Strategy;
  run_id: number | null;
  new_urls: string[];
  processed_urls: string[];
  failed_urls: string[];
  duration_seconds: number;
  errors: string[];
  log_messages?: string[];
}

export interface DiscoveredUrl {
  id: number;
  source_id: number;
  monitor_run_id: number | null;
  url: string;
  payload: Record<string, unknown> | null;
  discovered_at: string;
}

export interface Summary {
  id: number;
  discovered_url_id: number;
  discovered_url: string;
  title: string | null;
  summary: string;
  model: string | null;
  severity: "low" | "medium" | "high";
  confidence: "low" | "medium" | "high";
  reviewed_at: string | null;
  created_at: string;
}

export interface AuthSession {
  name: string;
  role: "admin" | "customer";
}

export interface AccountOverview {
  name: string;
  role: "customer";
  company_count: number;
  monitor_count: number;
  last_login_at: string | null;
}

export interface DailyInsightCount {
  date: string;
  count: number;
}

export interface CompanyInsightCount {
  company_id: number;
  company_name: string;
  count: number;
}

export interface SourceInsightCount {
  source_id: number;
  url: string;
  count: number;
}

export interface InsightStats {
  days: number;
  daily: DailyInsightCount[];
  by_company: CompanyInsightCount[];
  busiest_sources: SourceInsightCount[];
  by_source_daily: Record<number, number[]>;
  avg_seconds_to_insight: number | null;
}

export interface NotificationRecipient {
  id: number;
  company_id: number;
  email: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationRecipientInput {
  email: string;
  enabled: boolean;
}

export type NotificationRecipientUpdateInput =
  Partial<NotificationRecipientInput>;

export interface CompanyNotificationRecipients {
  id: number;
  name: string;
  recipients: NotificationRecipient[];
}

export interface SmtpStatus {
  configured: boolean;
  host: string | null;
  port: number | null;
  sender: string | null;
  username: string | null;
  use_tls: boolean;
  use_ssl: boolean;
  global_recipient_count: number;
  missing: string[];
}

export interface EmailSummary {
  id: number;
  company_id: number;
  company_name: string;
  source_id: number;
  source_url: string;
  discovered_url_id: number;
  discovered_url: string;
  title: string | null;
  summary: string;
  model: string | null;
  created_at: string;
  recipients: string[];
  recipient_count: number;
  smtp_configured: boolean;
  would_send: boolean;
  notification_mode: "manual" | "automatic";
  email_status: string;
  email_sent_at: string | null;
  email_error: string | null;
}

export interface EmailNotificationSettings {
  mode: "manual" | "automatic";
}

export interface EmailSendResult {
  summary_id: number;
  status: "sent" | "failed" | "skipped";
  message: string;
}

export interface MonitorRunDetails extends MonitorRun {
  discovered_urls: DiscoveredUrl[];
}

export interface DiscoveryPreviewUrl {
  url: string;
  already_seen: boolean;
  source: string | null;
  region: string | null;
  label: string | null;
}

export interface SourceDiscoveryPreview {
  source_id: number;
  source_url: string;
  strategy: Strategy;
  status: "ok" | "error";
  message: string | null;
  raw_url_count: number;
  content_url_count: number;
  already_seen_count: number;
  new_candidate_count: number;
  urls: DiscoveryPreviewUrl[];
}

export interface StoredUrl {
  url: string;
  source: "json" | "database";
  first_seen_at: string | null;
  discovered_at: string | null;
  monitor_run_id: number | null;
  payload: Record<string, unknown> | null;
}

export interface SourceStoredUrls {
  id: number;
  company_id: number;
  url: string;
  strategy: Strategy;
  stored_urls: StoredUrl[];
  json_url_count: number;
  database_url_count: number;
  message: string | null;
}

export interface CompanyStoredUrls {
  id: number;
  name: string;
  sources: SourceStoredUrls[];
}

export interface StoredUrlsResponse {
  status: "ok" | "warning" | "error";
  message: string | null;
  companies: CompanyStoredUrls[];
}

export function getApiErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string }>;
    return axiosError.response?.data?.detail || axiosError.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong.";
}


export async function getDiscoveryHealth() {
  const response = await api.get<DiscoveryHealth>("/health/discovery");
  return response.data;
}

export async function login(input: { name: string; password: string }) {
  const response = await api.post<AuthSession>("/auth/login", input);
  return response.data;
}

export async function getCurrentSession() {
  const response = await api.get<AuthSession>("/auth/me");
  return response.data;
}

export async function logout() {
  await api.post("/auth/logout");
}

export async function listAccounts() {
  const response = await api.get<AccountOverview[]>("/admin/accounts");
  return response.data;
}

export async function createAccount(input: { name: string; password: string }) {
  const response = await api.post<AccountOverview>("/admin/accounts", input);
  return response.data;
}
export async function getMonitorStatus() {
  const response = await api.get<MonitorStatus>("/monitor/status");
  return response.data;
}

export async function runAllSources() {
  const response = await api.post<QueuedTaskResponse>("/monitor/run-all");
  return response.data;
}

export async function listCompanies() {
  const response = await api.get<Company[]>("/companies");
  return response.data;
}

export async function createCompany(input: CompanyInput) {
  const response = await api.post<Company>("/companies", input);
  return response.data;
}

export async function updateCompany(id: number, input: CompanyInput) {
  const response = await api.patch<Company>(`/companies/${id}`, input);
  return response.data;
}

export async function deleteCompany(id: number) {
  await api.delete(`/companies/${id}`);
}

export async function listSources() {
  const response = await api.get<Source[]>("/sources");
  return response.data;
}

export async function getSource(id: number) {
  const response = await api.get<Source>(`/sources/${id}`);
  return response.data;
}

export async function createSource(input: SourceCreateInput) {
  const response = await api.post<Source>("/sources", input);
  return response.data;
}

export async function updateSource(id: number, input: SourceUpdateInput) {
  const response = await api.patch<Source>(`/sources/${id}`, input);
  return response.data;
}

export async function deleteSource(id: number) {
  await api.delete(`/sources/${id}`);
}

export async function baselineSource(id: number) {
  const response = await api.post<QueuedTaskResponse>(`/sources/${id}/baseline`);
  return response.data;
}

export async function runSource(id: number) {
  const response = await api.post<QueuedTaskResponse>(`/sources/${id}/run`);
  return response.data;
}

export async function listSourceRuns(id: number) {
  const response = await api.get<MonitorRun[]>(`/sources/${id}/runs`);
  return response.data;
}

export async function listSourceDiscoveredUrls(id: number) {
  const response = await api.get<DiscoveredUrl[]>(
    `/sources/${id}/discovered-urls`,
  );
  return response.data;
}

export async function listSourceSummaries(id: number) {
  const response = await api.get<Summary[]>(`/sources/${id}/summaries`);
  return response.data;
}

export async function listInsights(limit = 100) {
  const response = await api.get<Summary[]>("/insights", {
    params: { limit },
  });
  return response.data;
}

export async function updateInsightReview(id: number, reviewed: boolean) {
  const response = await api.patch<Summary>(`/insights/${id}/review`, {
    reviewed,
  });
  return response.data;
}

export async function getInsightStats(days = 30) {
  const response = await api.get<InsightStats>("/insights/stats", {
    params: { days },
  });
  return response.data;
}

export async function getSmtpStatus() {
  const response = await api.get<SmtpStatus>("/email/smtp-status");
  return response.data;
}

export async function getEmailNotificationSettings() {
  const response =
    await api.get<EmailNotificationSettings>("/email/settings");
  return response.data;
}

export async function updateEmailNotificationSettings(
  input: EmailNotificationSettings,
) {
  const response = await api.patch<EmailNotificationSettings>(
    "/email/settings",
    input,
  );
  return response.data;
}

export async function listCompanyRecipients() {
  const response =
    await api.get<CompanyNotificationRecipients[]>("/email/recipients");
  return response.data;
}

export async function createCompanyRecipient(
  companyId: number,
  input: NotificationRecipientInput,
) {
  const response = await api.post<NotificationRecipient>(
    `/email/companies/${companyId}/recipients`,
    input,
  );
  return response.data;
}

export async function updateNotificationRecipient(
  recipientId: number,
  input: NotificationRecipientUpdateInput,
) {
  const response = await api.patch<NotificationRecipient>(
    `/email/recipients/${recipientId}`,
    input,
  );
  return response.data;
}

export async function deleteNotificationRecipient(recipientId: number) {
  await api.delete(`/email/recipients/${recipientId}`);
}

export async function listEmailSummaries(companyId?: number) {
  const response = await api.get<EmailSummary[]>("/email/summaries", {
    params: companyId ? { company_id: companyId } : undefined,
  });
  return response.data;
}

export async function sendEmailSummary(summaryId: number) {
  const response = await api.post<EmailSendResult>(
    `/email/summaries/${summaryId}/send`,
  );
  return response.data;
}

export async function getSourceDiscoveryPreview(id: number) {
  const response = await api.get<SourceDiscoveryPreview>(
    `/sources/${id}/discovery-preview`,
  );
  return response.data;
}

export async function listRuns() {
  const response = await api.get<MonitorRun[]>("/runs");
  return response.data;
}

export async function getRun(id: number) {
  const response = await api.get<MonitorRunDetails>(`/runs/${id}`);
  return response.data;
}

export async function getTaskStatus(taskId: string) {
  const response = await api.get<TaskStatus>(`/tasks/${taskId}`);
  return response.data;
}

export async function listStoredUrls() {
  const response = await api.get<StoredUrlsResponse>("/storage/urls");
  return response.data;
}
