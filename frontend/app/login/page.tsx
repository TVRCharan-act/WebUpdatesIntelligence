"use client";

import {
  Activity,
  ArrowRight,
  BrainCircuit,
  Clock3,
  Eye,
  EyeOff,
  Flame,
  LockKeyhole,
  Radar,
  ShieldCheck,
  TrendingUp,
  UserRound,
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { useRouter } from "@/components/router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApiErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

// The login screen is the one place Sentinel Actalyst gets to be a little
// theatrical — a fixed dark "command deck" scene (independent of the app's
// light workspace theme) built from the brand concept art: a glowing sigil,
// drifting stars, and floating glass telemetry chips around a glass card.
// All decorative motion is inert under prefers-reduced-motion (globals.css).

interface StatChipConfig {
  icon: React.ElementType;
  label: string;
  value: string;
  sublabel: string;
  className: string;
  enterDelay: number;
  floatDuration: number;
}

const STAT_CHIPS: StatChipConfig[] = [
  {
    icon: Radar,
    label: "Monitoring",
    value: "1,287",
    sublabel: "Websites · 24/7 active",
    className: "left-[2%] top-[12%]",
    enterDelay: 200,
    floatDuration: 5200,
  },
  {
    icon: Activity,
    label: "Changes detected",
    value: "12,458",
    sublabel: "Today",
    className: "left-[4%] top-[42%]",
    enterDelay: 420,
    floatDuration: 4600,
  },
  {
    icon: BrainCircuit,
    label: "AI confidence",
    value: "97.6%",
    sublabel: "Average",
    className: "left-[6%] top-[70%]",
    enterDelay: 640,
    floatDuration: 5800,
  },
  {
    icon: Flame,
    label: "High priority",
    value: "23",
    sublabel: "New insights",
    className: "right-[2%] top-[16%]",
    enterDelay: 300,
    floatDuration: 4900,
  },
  {
    icon: Clock3,
    label: "Time saved",
    value: "248 hrs",
    sublabel: "This month",
    className: "right-[4%] top-[46%]",
    enterDelay: 520,
    floatDuration: 5500,
  },
  {
    icon: TrendingUp,
    label: "Trending topic",
    value: "AI Pricing",
    sublabel: "+320%",
    className: "right-[6%] top-[74%]",
    enterDelay: 740,
    floatDuration: 5000,
  },
];

const STARS = Array.from({ length: 28 }, (_, i) => ({
  left: `${(i * 37) % 100}%`,
  top: `${(i * 53) % 100}%`,
  size: 1 + ((i * 7) % 3),
  delay: (i * 0.31) % 3.6,
}));

function SentinelSigil() {
  return (
    <div className="relative mx-auto flex size-32 items-center justify-center sm:size-40" aria-hidden="true">
      <div
        className="aurora-breathe absolute inset-[-60%] rounded-full blur-2xl"
        style={{
          background:
            "radial-gradient(circle, rgba(103,190,255,0.35), rgba(147,112,246,0.2) 45%, transparent 72%)",
        }}
      />
      <div
        className="sigil-spin absolute inset-0 rounded-full opacity-80"
        style={{
          background:
            "conic-gradient(from 0deg, transparent 0deg, rgba(94,213,255,0.95) 35deg, transparent 95deg, transparent 265deg, rgba(167,139,250,0.95) 320deg, transparent 360deg)",
          WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2px))",
          mask: "radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2px))",
        }}
      />
      <div
        className="sigil-spin-reverse absolute inset-5 rounded-full opacity-60"
        style={{
          background: "conic-gradient(from 120deg, transparent 0deg, rgba(94,213,255,0.7) 40deg, transparent 90deg)",
          WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 2px), #000 calc(100% - 1px))",
          mask: "radial-gradient(farthest-side, transparent calc(100% - 2px), #000 calc(100% - 1px))",
        }}
      />
      <div className="relative flex size-16 items-center justify-center rounded-full border border-white/20 bg-white/[0.06] shadow-[0_0_45px_rgba(94,213,255,0.45)] backdrop-blur-xl sm:size-20">
        <ShieldCheck className="sigil-pulse size-8 text-cyan-300 sm:size-9" />
      </div>
    </div>
  );
}

function StatChip({ icon: Icon, label, value, sublabel, className, enterDelay, floatDuration }: StatChipConfig) {
  return (
    <div
      className={cn(
        "stat-chip absolute hidden w-40 rounded-xl border border-white/10 bg-white/[0.05] p-3 text-left shadow-[0_10px_30px_-14px_rgba(0,0,0,0.7)] backdrop-blur-xl xl:block",
        className,
      )}
      style={
        {
          "--stat-enter-delay": `${enterDelay}ms`,
          "--stat-float-delay": `${enterDelay + 500}ms`,
          "--stat-float-duration": `${floatDuration}ms`,
        } as React.CSSProperties
      }
    >
      <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-white/45">
        <Icon className="size-3" />
        {label}
      </div>
      <div className="mt-1 font-mono text-lg font-semibold text-white">{value}</div>
      <div className="text-[11px] text-white/40">{sublabel}</div>
    </div>
  );
}

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

  const accent = admin ? "from-amber-300 via-orange-400 to-rose-400" : "from-cyan-300 via-sky-400 to-violet-400";

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#050914] px-4 py-10">
      {/* Deep-space gradient base + horizon glow, independent of the app's light theme. */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,#0f2244_0%,#0a1329_45%,#050914_80%)]" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-[radial-gradient(ellipse_at_50%_100%,rgba(255,175,110,0.12),transparent_70%)]" />

      {/* Distant stars. */}
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        {STARS.map((star, i) => (
          <span
            key={i}
            className="twinkle absolute rounded-full bg-white"
            style={{
              left: star.left,
              top: star.top,
              width: star.size,
              height: star.size,
              animationDelay: `${star.delay}s`,
            }}
          />
        ))}
      </div>

      {/* Floating telemetry chips. */}
      {STAT_CHIPS.map((chip) => (
        <StatChip key={chip.label} {...chip} />
      ))}

      <div className="relative z-10 grid w-full max-w-md gap-6">
        <div className="grid gap-3 text-center">
          <SentinelSigil />
          <div>
            <div className="text-2xl font-semibold tracking-wide text-white">
              SENTINEL <span className="font-normal text-white/60">ACTALYST</span>
            </div>
            <p className="mt-1 text-sm text-white/50">
              {admin ? "Command post — staff access only." : "Always watching. Always ahead."}
            </p>
            <p className="text-sm text-white/35">
              {admin ? "" : "AI-powered intelligence for a changing web."}
            </p>
          </div>
        </div>

        <div className="animate-enter rounded-2xl border border-white/10 bg-white/[0.05] p-6 shadow-[0_20px_70px_-20px_rgba(56,189,248,0.25)] backdrop-blur-2xl sm:p-8">
          <div className="mb-5 flex items-center gap-2 text-sm font-medium text-white/60">
            <LockKeyhole className="size-4" />
            {admin ? "Admin login" : "Customer login"}
          </div>

          <form className="grid gap-4" onSubmit={handleSubmit}>
            <div className="grid gap-2">
              <Label htmlFor="name" className="text-white/70">
                {admin ? "Admin name" : "Name"}
              </Label>
              <div className="group relative">
                <UserRound className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-white/35 transition-colors group-focus-within:text-cyan-300" />
                <Input
                  id="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoComplete="username"
                  required
                  className="border-white/15 bg-white/5 pl-9 text-white placeholder:text-white/30 focus-visible:border-cyan-300/50 focus-visible:bg-white/[0.08] focus-visible:ring-cyan-300/40"
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="password" className="text-white/70">
                Password
              </Label>
              <div className="group relative">
                <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-white/35 transition-colors group-focus-within:text-cyan-300" />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                  className="border-white/15 bg-white/5 pl-9 pr-9 text-white placeholder:text-white/30 focus-visible:border-cyan-300/50 focus-visible:bg-white/[0.08] focus-visible:ring-cyan-300/40"
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/35 transition-colors hover:text-white/70"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            <Button
              disabled={saving}
              className={cn(
                "mt-1 w-full bg-gradient-to-r text-white shadow-[0_8px_24px_-8px_rgba(56,189,248,0.55)] transition-all hover:-translate-y-px hover:shadow-[0_12px_32px_-8px_rgba(56,189,248,0.7)] active:translate-y-0",
                accent,
              )}
            >
              {saving ? "Signing in" : "Sign in"}
              <ArrowRight />
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-white/30">
          {admin
            ? "Use the admin credentials configured in the backend environment."
            : "Use the account name and password your Sentinel Actalyst admin provisioned for you."}
        </p>
      </div>
    </div>
  );
}
