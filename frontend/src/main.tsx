import * as React from "react";
import { createRoot } from "react-dom/client";

import "@/app/globals.css";
import DashboardPage from "@/app/page";
import AdminAccountsPage from "@/app/admin/accounts/page";
import CompaniesPage from "@/app/companies/page";
import CustomerDashboardPage from "@/app/dashboard/page";
import EmailPage from "@/app/email/page";
import InsightsPage from "@/app/insights/page";
import LoginPage from "@/app/login/page";
import MonitorDetailPage from "@/app/monitors/[id]/page";
import MonitorsPage from "@/app/monitors/page";
import NotificationsPage from "@/app/notifications/page";
import OnboardingPage from "@/app/onboarding/page";
import RunsPage from "@/app/runs/page";
import SettingsPage from "@/app/settings/page";
import WorkspaceSettingsPage from "@/app/settings/workspace/page";
import SourcesPage from "@/app/sources/page";
import SourceDetailsPage from "@/app/sources/[id]/page";
import StoragePage from "@/app/storage/page";
import TrendsPage from "@/app/trends/page";
import { useAuth } from "@/components/auth-provider";
import { AppShell } from "@/components/app-shell";
import { CustomerShell } from "@/components/customer-shell";
import { Providers } from "@/components/providers";
import { RouterProvider, usePathname } from "@/components/router";

function Routes() {
  const pathname = usePathname();
  const auth = useAuth();

  if (pathname === "/login") return <LoginPage />;
  if (pathname === "/admin/login") return <LoginPage admin />;

  if (auth.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Loading Sentinel Actalyst.
      </div>
    );
  }

  if (!auth.session) {
    window.location.replace(pathname.startsWith("/admin") ? "/admin/login" : "/login");
    return null;
  }

  if (pathname.startsWith("/admin") && auth.session.role !== "admin") {
    window.location.replace("/dashboard");
    return null;
  }

  if (pathname === "/") {
    window.location.replace(auth.session.role === "admin" ? "/admin/dashboard" : "/dashboard");
    return null;
  }

  if (pathname.startsWith("/admin")) {
    return (
      <AppShell>
        {pathname === "/admin/dashboard" ? <DashboardPage /> : null}
        {pathname === "/admin/accounts" ? <AdminAccountsPage /> : null}
        {pathname === "/admin/companies" ? <CompaniesPage /> : null}
        {pathname === "/admin/sources" ? <SourcesPage /> : null}
        {/^\/admin\/sources\/[^/]+$/.test(pathname) ? <SourceDetailsPage /> : null}
        {pathname === "/admin/storage" ? <StoragePage /> : null}
        {pathname === "/admin/email" ? <EmailPage /> : null}
        {pathname === "/admin/runs" ? <RunsPage /> : null}
        {pathname === "/admin/settings" ? <SettingsPage /> : null}
      </AppShell>
    );
  }

  return (
    <CustomerShell>
      {pathname === "/dashboard" ? <CustomerDashboardPage /> : null}
      {pathname === "/onboarding" ? <OnboardingPage /> : null}
      {pathname === "/monitors" ? <MonitorsPage /> : null}
      {/^\/monitors\/[^/]+$/.test(pathname) ? <MonitorDetailPage /> : null}
      {pathname === "/insights" ? <InsightsPage /> : null}
      {pathname === "/trends" ? <TrendsPage /> : null}
      {pathname === "/notifications" ? <NotificationsPage /> : null}
      {pathname.startsWith("/settings") ? <WorkspaceSettingsPage /> : null}
    </CustomerShell>
  );
}

function App() {
  return (
    <React.StrictMode>
      <RouterProvider>
        <Providers>
          <Routes />
        </Providers>
      </RouterProvider>
    </React.StrictMode>
  );
}

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element #root was not found.");
}

createRoot(root).render(<App />);
