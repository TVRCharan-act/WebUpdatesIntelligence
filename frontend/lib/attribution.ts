import type { Company, Source } from "@/lib/api";

// Honest company/source attribution for an insight.
//
// A Summary only carries `discovered_url` (the real page the insight is about)
// and `discovered_url_id` — there is no source_id on the customer /insights
// payload, so we attribute by matching the discovered URL's domain to a
// monitored source's domain. This is approximate but real; when no source
// matches, we fall back to the discovered URL's own domain rather than a generic
// "Tracked company" label. (Fixing this precisely would need a backend join —
// out of Tier-1 scope.)

export function hostOf(url: string): string | null {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

/** Registrable-ish domain: the last two labels of the host (best-effort). */
export function domainOf(url: string): string | null {
  const host = hostOf(url);
  if (!host) return null;
  const parts = host.split(".");
  return parts.length <= 2 ? host : parts.slice(-2).join(".");
}

export interface Attribution {
  companyName: string | null;
  domain: string | null;
  company: Company | null;
}

/**
 * Build a resolver mapping a discovered URL to its company, using the domains of
 * the monitored sources. Returns `{ companyName, domain, company }` — the full
 * company (for priority / added-date sorting) when a source domain matches.
 */
export function makeAttributor(
  sources: Source[],
  companies: Company[],
): (discoveredUrl: string) => Attribution {
  const companyById = new Map(companies.map((c) => [c.id, c]));
  const companyByDomain = new Map<string, Company>();

  for (const source of sources) {
    const domain = domainOf(source.url);
    const company = companyById.get(source.company_id);
    if (domain && company && !companyByDomain.has(domain)) {
      companyByDomain.set(domain, company);
    }
  }

  return (discoveredUrl: string): Attribution => {
    const domain = domainOf(discoveredUrl);
    const company = domain ? companyByDomain.get(domain) ?? null : null;
    return {
      companyName: company?.name ?? null,
      domain,
      company,
    };
  };
}
