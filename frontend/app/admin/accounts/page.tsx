"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, UsersRound } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { createAccount, getApiErrorMessage, listAccounts } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime } from "@/lib/utils";

export default function AdminAccountsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = React.useState("");
  const [password, setPassword] = React.useState("");

  const accountsQuery = useQuery({
    queryKey: queryKeys.accounts,
    queryFn: listAccounts,
  });
  const accounts = accountsQuery.data || [];

  const addMutation = useMutation({
    mutationFn: () => createAccount({ name: name.trim(), password }),
    onSuccess: (account) => {
      toast.success(`Account "${account.name}" created. They can sign in now.`);
      setName("");
      setPassword("");
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  function handleAdd(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || !password) return;
    addMutation.mutate();
  }

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Accounts</h2>
        <p className="text-sm text-muted-foreground">
          Provision customer accounts. New accounts can sign in immediately and are saved across restarts.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="size-4" />
            Register a customer account
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end" onSubmit={handleAdd}>
            <div className="grid gap-2">
              <Label htmlFor="account-name">Account name</Label>
              <Input
                id="account-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="acme-team"
                autoComplete="off"
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="account-password">Password</Label>
              <Input
                id="account-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Set a password"
                autoComplete="new-password"
                required
              />
            </div>
            <Button disabled={addMutation.isPending}>
              <Plus />
              {addMutation.isPending ? "Creating" : "Create account"}
            </Button>
          </form>
          <p className="mt-3 text-xs text-muted-foreground">
            Share these credentials with the customer directly. Passwords are stored in the backend
            accounts file — treat them like environment secrets.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configured customers</CardTitle>
        </CardHeader>
        <CardContent>
          {!accountsQuery.isLoading && accounts.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
              <div className="flex size-10 items-center justify-center rounded-md bg-secondary">
                <UsersRound className="size-5 text-muted-foreground" />
              </div>
              <div className="font-medium">No customer accounts yet</div>
              <div className="max-w-sm text-sm text-muted-foreground">
                Use the form above to register your first customer, or add USER_n_ entries to the backend
                environment.
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Companies</TableHead>
                  <TableHead>Monitors</TableHead>
                  <TableHead>Last login</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((account) => (
                  <TableRow key={account.name}>
                    <TableCell className="font-medium">{account.name}</TableCell>
                    <TableCell>{account.company_count}</TableCell>
                    <TableCell>{account.monitor_count}</TableCell>
                    <TableCell>{formatDateTime(account.last_login_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
