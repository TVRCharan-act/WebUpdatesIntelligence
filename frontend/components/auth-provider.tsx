"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import {
  getCurrentSession,
  login as loginRequest,
  logout as logoutRequest,
  type AuthSession,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

type AuthContextValue = {
  session: AuthSession | null;
  isLoading: boolean;
  login: (input: { name: string; password: string }) => Promise<AuthSession>;
  logout: () => Promise<void>;
};

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const sessionQuery = useQuery({
    queryKey: queryKeys.session,
    queryFn: getCurrentSession,
    retry: false,
  });

  const loginMutation = useMutation({
    mutationFn: loginRequest,
    onSuccess: (session) => {
      queryClient.setQueryData(queryKeys.session, session);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: logoutRequest,
    onSettled: () => {
      queryClient.clear();
    },
  });

  const value = React.useMemo<AuthContextValue>(
    () => ({
      session: sessionQuery.data ?? null,
      isLoading: sessionQuery.isLoading,
      login: (input) => loginMutation.mutateAsync(input),
      logout: () => logoutMutation.mutateAsync(),
    }),
    [loginMutation, logoutMutation, sessionQuery.data, sessionQuery.isLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
