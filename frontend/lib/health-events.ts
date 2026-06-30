const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface HealthEvent {
  event_type: string;
  action: string;
  status?: string;
  duration_ms?: number;
  metadata?: Record<string, unknown>;
}

export function recordHealthEvent(event: HealthEvent) {
  if (typeof window === "undefined") {
    return;
  }

  const body = JSON.stringify({
    status: "ok",
    ...event,
    metadata: {
      path: window.location.pathname,
      ...event.metadata,
    },
  });
  const url = `${API_BASE_URL}/health/events`;

  try {
    if ("sendBeacon" in navigator) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon(url, blob);
      return;
    }

    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    return;
  }
}
