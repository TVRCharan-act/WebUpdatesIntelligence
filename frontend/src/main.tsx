import * as React from "react";
import { createRoot } from "react-dom/client";

import "@/app/globals.css";
import DashboardPage from "@/app/page";
import CompaniesPage from "@/app/companies/page";
import EmailPage from "@/app/email/page";
import RunsPage from "@/app/runs/page";
import SettingsPage from "@/app/settings/page";
import SourcesPage from "@/app/sources/page";
import SourceDetailsPage from "@/app/sources/[id]/page";
import StoragePage from "@/app/storage/page";
import { AppShell } from "@/components/app-shell";
import { Providers } from "@/components/providers";
import { RouterProvider, usePathname } from "@/components/router";

function Routes() {
  const pathname = usePathname();

  if (pathname === "/") return <DashboardPage />;
  if (pathname === "/companies") return <CompaniesPage />;
  if (pathname === "/sources") return <SourcesPage />;
  if (/^\/sources\/[^/]+$/.test(pathname)) return <SourceDetailsPage />;
  if (pathname === "/storage") return <StoragePage />;
  if (pathname === "/email") return <EmailPage />;
  if (pathname === "/runs") return <RunsPage />;
  if (pathname === "/settings") return <SettingsPage />;

  return <DashboardPage />;
}

function App() {
  return (
    <React.StrictMode>
      <RouterProvider>
        <Providers>
          <AppShell>
            <Routes />
          </AppShell>
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
