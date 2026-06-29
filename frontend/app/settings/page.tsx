"use client";

import { ServerCog } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { API_BASE_URL } from "@/lib/api";

export default function SettingsPage() {
  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Settings</h2>
        <p className="text-sm text-muted-foreground">
          Local frontend configuration.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ServerCog className="size-5" />
            API
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2">
          <label className="text-sm font-medium" htmlFor="api-base-url">
            API base URL
          </label>
          <Input id="api-base-url" value={API_BASE_URL} readOnly />
        </CardContent>
      </Card>
    </div>
  );
}
