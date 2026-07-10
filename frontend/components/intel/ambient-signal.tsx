import { cn } from "@/lib/utils";

// The ambient Signal waveform behind the Dashboard briefing header (and the login
// screen). Two layers drifting at different speeds give a livelier "alive" feel;
// brightened for more presence. Amplitude reflects real account activity level
// (Build Spec §2.2, §17.1). Purely decorative → aria-hidden; drift is disabled
// under prefers-reduced-motion (see globals.css).

const PERIOD = 50; // one full wave; drift distance matches for a seamless loop
const MID = 20;

function wavePath(width: number, amp: number): string {
  const half = PERIOD / 2;
  let d = `M 0 ${MID}`;
  let x = 0;
  let up = true;
  while (x < width) {
    const cx = x + half / 2;
    const cy = up ? MID - amp : MID + amp;
    const ex = x + half;
    d += ` Q ${cx} ${cy} ${ex} ${MID}`;
    x = ex;
    up = !up;
  }
  return d;
}

export function AmbientSignal({
  amplitude = 1,
  className,
}: {
  /** Scales wave height; e.g. Quiet 0.6 · Normal 1 · Busy 1.4. */
  amplitude?: number;
  className?: string;
}) {
  const front = wavePath(400, Math.max(3, 9 * amplitude));
  const back = wavePath(400, Math.max(4, 13 * amplitude));

  return (
    <svg
      className={cn(
        "pointer-events-none absolute inset-0 size-full text-signal opacity-[0.16] dark:opacity-[0.26]",
        className,
      )}
      viewBox="0 0 200 40"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {/* Back layer — larger, fainter, slower drift for parallax depth. */}
      <g className="signal-drift" style={{ animationDuration: "12s" }}>
        <path
          d={back}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.25}
          vectorEffect="non-scaling-stroke"
          className="opacity-50"
        />
      </g>
      {/* Front layer — brighter, primary wave. */}
      <g className="signal-drift">
        <path
          d={front}
          fill="none"
          stroke="currentColor"
          strokeWidth={2.25}
          vectorEffect="non-scaling-stroke"
        />
      </g>
    </svg>
  );
}
