"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, CreditCard, UserRound, UsersRound } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listCompanies, listSources } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export default function WorkspaceSettingsPage() {
  const auth = useAuth();
  const companiesQuery = useQuery({ queryKey: queryKeys.companies, queryFn: listCompanies });
  const sourcesQuery = useQuery({ queryKey: queryKeys.sources, queryFn: listSources });
  const companies = companiesQuery.data || [];
  const sources = sourcesQuery.data || [];

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Settings</h2>
        <p className="text-sm text-muted-foreground">
          Workspace, team, billing, and account details for your provisioned account.
        </p>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="size-4" />
              Workspace
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Display name</span>
              <span>{auth.session?.name}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Tracked companies</span>
              <span>{companies.length}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Active monitors</span>
              <span>{sources.filter((source) => source.enabled).length}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UsersRound className="size-4" />
              Team
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div className="flex items-center gap-3 rounded-xl border p-3">
              <div className="flex size-9 items-center justify-center rounded-full bg-accent font-semibold text-accent-foreground">
                {auth.session?.name?.[0]?.toUpperCase() || "P"}
              </div>
              <div>
                <div className="font-medium">{auth.session?.name}</div>
                <div className="text-muted-foreground">Provisioned account</div>
              </div>
            </div>
            <p className="text-muted-foreground">
              Need to add a teammate? Contact your Sentinel Actalyst admin.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CreditCard className="size-4" />
              Billing
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Plan</span>
              <Badge variant="secondary">Pilot</Badge>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Monitor usage</span>
              <span>{sources.length} active</span>
            </div>
            <p className="text-muted-foreground">Plan changes are handled directly by your Sentinel Actalyst admin.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserRound className="size-4" />
              Account
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Name</span>
              <span>{auth.session?.name}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Role</span>
              <span>{auth.session?.role}</span>
            </div>
            <p className="text-muted-foreground">Password changes are handled in the backend environment configuration.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
