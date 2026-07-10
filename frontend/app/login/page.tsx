"use client";

import { ArrowRight, LockKeyhole, ShieldCheck } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { AmbientSignal } from "@/components/intel/ambient-signal";
import { useAuth } from "@/components/auth-provider";
import { useRouter } from "@/components/router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApiErrorMessage } from "@/lib/api";

export default function LoginPage({ admin = false }: { admin?: boolean }) {
  const auth = useAuth();
  const router = useRouter();
  const [name, setName] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      const session = await auth.login({ name, password });
      if (admin && session.role !== "admin") {
        toast.error("This login is for staff accounts.");
        await auth.logout();
        return;
      }
      router.replace(session.role === "admin" ? "/admin/dashboard" : "/dashboard");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-[radial-gradient(circle_at_10%_10%,hsl(var(--accent)),transparent_34%),hsl(var(--background))] px-4 py-10">
      <div className="mx-auto grid w-full max-w-5xl items-center gap-8 lg:grid-cols-[1fr_420px]">
        <div className="relative max-w-xl overflow-hidden">
          <AmbientSignal amplitude={1.2} />
          <div className="relative">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <ShieldCheck className="size-6" />
            </div>
            <div>
              <div className="text-lg font-semibold">
                {admin ? "Sentinel Actalyst Ops" : "Sentinel Actalyst"}
              </div>
              <div className="text-sm text-muted-foreground">
                {admin ? "Command post" : "Always on watch over the web"}
              </div>
            </div>
          </div>
          <h1 className="text-4xl font-semibold tracking-normal sm:text-5xl">
            {admin ? "Sign in to run the watch." : "Welcome back. Your sentinel's been watching."}
          </h1>
          <p className="mt-4 text-lg text-muted-foreground">
            {admin
              ? "Use the admin credentials configured in the backend environment."
              : "Use the account name and password your Sentinel Actalyst admin provisioned for you."}
          </p>
          </div>
        </div>

        <Card className="border-border/80 shadow-xl">
          <CardContent className="p-6">
            <form className="grid gap-5" onSubmit={handleSubmit}>
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <LockKeyhole className="size-4" />
                {admin ? "Admin login" : "Customer login"}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoComplete="username"
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>
              <Button className="w-full" disabled={saving}>
                {saving ? "Signing in" : "Continue"}
                <ArrowRight />
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
