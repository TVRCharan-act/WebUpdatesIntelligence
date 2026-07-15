"use client";

import { ArrowRight, Eye, EyeOff, LockKeyhole, UserRound } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { SentinelMark } from "@/components/intel/sentinel-mark";
import { useRouter } from "@/components/router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApiErrorMessage } from "@/lib/api";

// A plain, professional sign-in: a single centered card on a neutral
// background, matching the app's light workspace theme. No decorative scene.

export default function LoginPage({ admin = false }: { admin?: boolean }) {
  const auth = useAuth();
  const router = useRouter();
  const [name, setName] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
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
    <div className="login-scene flex min-h-screen items-center justify-center bg-secondary px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <SentinelMark className="size-11" />
          <div>
            <div className="text-xl font-semibold tracking-tight">
              <span className="gradient-text">Sentinel</span> Actalyst
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {admin ? "Command post — staff access only." : "Always watching. Always ahead."}
            </p>
          </div>
        </div>

        <div className="rounded-2xl border bg-card p-6 shadow-sm sm:p-8">
          <div className="mb-5 flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <LockKeyhole className="size-4" />
            {admin ? "Admin login" : "Customer login"}
          </div>

          <form className="grid gap-4" onSubmit={handleSubmit}>
            <div className="grid gap-2">
              <Label htmlFor="name">{admin ? "Admin name" : "Name"}</Label>
              <div className="relative">
                <UserRound className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoComplete="username"
                  required
                  className="pl-9"
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                  className="pl-9 pr-9"
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            <Button disabled={saving} className="mt-1 w-full">
              {saving ? "Signing in" : "Sign in"}
              <ArrowRight />
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          {admin
            ? "Use the admin credentials configured in the backend environment."
            : "Use the account name and password your Sentinel Actalyst admin provisioned for you."}
        </p>
      </div>
    </div>
  );
}
