"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Pencil, Plus, Save, Trash2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  createCompany,
  deleteCompany,
  getApiErrorMessage,
  listCompanies,
  updateCompany,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime } from "@/lib/utils";

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const [name, setName] = React.useState("");
  const [editing, setEditing] = React.useState<Record<number, string>>({});

  const companiesQuery = useQuery({
    queryKey: queryKeys.companies,
    queryFn: listCompanies,
  });

  const createMutation = useMutation({
    mutationFn: createCompany,
    onSuccess: () => {
      setName("");
      toast.success("Company created.");
      queryClient.invalidateQueries({ queryKey: queryKeys.companies });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, value }: { id: number; value: string }) =>
      updateCompany(id, { name: value }),
    onSuccess: () => {
      toast.success("Company renamed.");
      queryClient.invalidateQueries({ queryKey: queryKeys.companies });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCompany,
    onSuccess: () => {
      toast.success("Company deleted.");
      queryClient.invalidateQueries({ queryKey: queryKeys.companies });
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createMutation.mutate({ name });
  }

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Companies</h2>
        <p className="text-sm text-muted-foreground">
          Organize sources by the company they belong to.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create company</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-3 sm:flex-row" onSubmit={handleCreate}>
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Company name"
              required
            />
            <Button disabled={createMutation.isPending}>
              <Plus />
              Create
            </Button>
          </form>
        </CardContent>
      </Card>

      {(companiesQuery.data || []).length === 0 && !companiesQuery.isLoading ? (
        <EmptyState
          icon={Building2}
          title="No companies"
          description="Create a company before adding monitor sources."
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Company list</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-40">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(companiesQuery.data || []).map((company) => {
                  const value = editing[company.id] ?? company.name;
                  const changed = value.trim() && value !== company.name;

                  return (
                    <TableRow key={company.id}>
                      <TableCell>
                        <Input
                          value={value}
                          onChange={(event) =>
                            setEditing((current) => ({
                              ...current,
                              [company.id]: event.target.value,
                            }))
                          }
                        />
                      </TableCell>
                      <TableCell>{formatDateTime(company.created_at)}</TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button
                            size="icon"
                            variant="outline"
                            disabled={!changed || updateMutation.isPending}
                            aria-label="Save company"
                            onClick={() =>
                              updateMutation.mutate({
                                id: company.id,
                                value: value.trim(),
                              })
                            }
                          >
                            {changed ? <Save /> : <Pencil />}
                          </Button>
                          <Button
                            size="icon"
                            variant="destructive"
                            aria-label="Delete company"
                            onClick={() => {
                              if (confirm(`Delete ${company.name}?`)) {
                                deleteMutation.mutate(company.id);
                              }
                            }}
                          >
                            <Trash2 />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
