// Shared parser for the summarizer's plain-text output.
//
// The summarizer (mysignal/summarizers/openai_summarizer.py) emits four labeled
// sections: HEADLINE / UPDATE / KEY DETAILS / FOLLOW UP. FOLLOW UP is only ever a
// "Read the full update here: <url>" line, so we deliberately DROP it from the
// rendered sections — the source link is already surfaced as the "View original"
// chrome. Lifted out of app/monitors/[id]/page.tsx so the feed and dossier share
// one parser (Build Spec §14.4).

export interface ParsedInsight {
  /** News-style headline, if the model produced one. */
  headline?: string;
  /** What changed — the primary narrative body. */
  whatHappened?: string;
  /** Supporting facts, usually bullet lines. */
  keyDetails?: string;
}

const LABELS = ["HEADLINE:", "UPDATE:", "KEY DETAILS:", "FOLLOW UP:"] as const;

const FIELD_BY_LABEL: Record<string, keyof ParsedInsight> = {
  "HEADLINE:": "headline",
  "UPDATE:": "whatHappened",
  "KEY DETAILS:": "keyDetails",
  // FOLLOW UP: intentionally absent — it collapses into the source link.
};

/**
 * Split raw summarizer text into structured sections.
 *
 * If no known labels are found, the whole string is treated as the
 * "what happened" body so nothing is ever lost.
 */
export function parseInsight(summary: string): ParsedInsight {
  const result: ParsedInsight = {};
  let matchedAny = false;

  for (const label of LABELS) {
    const start = summary.indexOf(label);
    if (start === -1) continue;
    matchedAny = true;

    const contentStart = start + label.length;
    const nextStarts = LABELS.map((candidate) =>
      summary.indexOf(candidate, contentStart),
    ).filter((index) => index > start);
    const end = nextStarts.length ? Math.min(...nextStarts) : summary.length;

    const field = FIELD_BY_LABEL[label];
    if (field) {
      result[field] = summary.slice(contentStart, end).trim();
    }
  }

  if (!matchedAny) {
    result.whatHappened = summary.trim();
  }

  return result;
}

/** Split the parsed KEY DETAILS block into individual bullet lines. */
export function keyDetailLines(keyDetails: string | undefined): string[] {
  if (!keyDetails) return [];
  return keyDetails
    .split("\n")
    .map((line) => line.replace(/^[-*•]\s*/, "").trim())
    .filter(Boolean);
}
