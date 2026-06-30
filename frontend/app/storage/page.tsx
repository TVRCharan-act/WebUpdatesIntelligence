"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Database, ExternalLink, Rows3 } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { Link } from "@/components/router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listStoredUrls } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime, truncate } from "@/lib/utils";

export default function StoragePage() {
  const storageQuery = useQuery({
    queryKey: queryKeys.storedUrls,
    queryFn: listStoredUrls,
  });

  const data = storageQuery.data;
  const companies = data?.companies || [];
  const totalSources = companies.reduce(
    (count, company) => count + company.sources.length,
    0,
  );
  const totalUrls = companies.reduce(
    (count, company) =>
      count +
      company.sources.reduce(
        (sourceCount, source) => sourceCount + source.stored_urls.length,
        0,
      ),
    0,
  );

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Stored URLs</h2>
        <p className="text-sm text-muted-foreground">
          Review URLs saved from baselines, monitor runs, and local JSON storage.
        </p>
      </div>

      {data?.message ? (
        <Card className="border-amber-300 bg-amber-50">
          <CardContent className="flex gap-3 py-4 text-sm text-amber-900">
            <AlertTriangle className="size-5 shrink-0" />
            <span>{data.message}</span>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Companies</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">{companies.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">{totalSources}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Stored URLs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">{totalUrls}</div>
          </CardContent>
        </Card>
      </div>

      {!storageQuery.isLoading && companies.length === 0 ? (
        <EmptyState
          icon={Rows3}
          title="No storage data"
          description="Create a company and source, then run a baseline or monitor to populate stored URLs."
        />
      ) : null}

      <div className="grid gap-5">
        {companies.map((company) => (
          <Card key={company.id}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-3">
                <span>{company.name}</span>
                <Badge variant="secondary">{company.sources.length} sources</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
              {company.sources.length === 0 ? (
                <div className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">
                  No sources exist under this company yet.
                </div>
              ) : null}

              {company.sources.map((source) => (
                <div key={source.id} className="rounded-lg border">
                  <div className="flex flex-col gap-3 border-b bg-secondary/35 p-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          href={`/sources/${source.id}`}
                          className="font-medium text-primary"
                        >
                          Source #{source.id}
                        </Link>
                        <Badge variant="outline">{source.strategy}</Badge>
                        <Badge variant="secondary">
                          {source.stored_urls.length} URLs
                        </Badge>
                      </div>
                      <div className="mt-1 truncate text-sm text-muted-foreground">
                        {source.url}
                      </div>
                    </div>
                    <div className="flex gap-2 text-xs text-muted-foreground">
                      <span>JSON: {source.json_url_count}</span>
                      <span>DB: {source.database_url_count}</span>
                    </div>
                  </div>

                  {source.message ? (
                    <div className="flex gap-3 p-4 text-sm text-muted-foreground">
                      <Database className="size-5 shrink-0" />
                      <span>
                        {source.message} Open the source detail page and run
                        the discovery check to see whether crawling found raw
                        URLs before storage.
                      </span>
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>URL</TableHead>
                          <TableHead>Stored In</TableHead>
                          <TableHead>First Seen</TableHead>
                          <TableHead>Run</TableHead>
                          <TableHead className="w-16"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {source.stored_urls.map((item) => (
                          <TableRow key={`${source.id}-${item.source}-${item.url}`}>
                            <TableCell className="max-w-xl">
                              <div className="font-medium">
                                {truncate(item.url, 100)}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={
                                  item.source === "json" ? "success" : "secondary"
                                }
                              >
                                {item.source}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              {item.first_seen_at
                                ? formatDateTime(item.first_seen_at)
                                : formatDateTime(item.discovered_at)}
                            </TableCell>
                            <TableCell>
                              {item.monitor_run_id ? `#${item.monitor_run_id}` : "-"}
                            </TableCell>
                            <TableCell>
                              <Button asChild size="icon" variant="ghost">
                                <a
                                  href={item.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  aria-label="Open stored URL"
                                >
                                  <ExternalLink />
                                </a>
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
