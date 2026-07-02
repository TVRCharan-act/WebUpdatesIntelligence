export const queryKeys = {
  monitorStatus: ["monitor-status"] as const,
  discoveryHealth: ["discovery-health"] as const,
  companies: ["companies"] as const,
  sources: ["sources"] as const,
  source: (id: number) => ["sources", id] as const,
  sourceRuns: (id: number) => ["sources", id, "runs"] as const,
  sourceDiscoveredUrls: (id: number) =>
    ["sources", id, "discovered-urls"] as const,
  sourceDiscoveryPreview: (id: number) =>
    ["sources", id, "discovery-preview"] as const,
  sourceSummaries: (id: number) => ["sources", id, "summaries"] as const,
  smtpStatus: ["email", "smtp-status"] as const,
  emailSettings: ["email", "settings"] as const,
  companyRecipients: ["email", "recipients"] as const,
  emailSummaries: (companyId?: number) =>
    ["email", "summaries", companyId || "all"] as const,
  runs: ["runs"] as const,
  run: (id: number) => ["runs", id] as const,
  task: (id: string) => ["tasks", id] as const,
  storedUrls: ["storage", "urls"] as const,
};
