import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/api/client";
import type { User } from "@/api/types";

const ME_KEY = ["auth", "me"] as const;

/**
 * Resolves the current session. Returns null when unauthenticated — that's a
 * normal state the app routes around, not an error to propagate up the
 * boundary. Anything else (network error, 5xx) bubbles as a real error.
 */
export function useCurrentUser() {
  return useQuery<User | null>({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        return await api.get<User>("/api/auth/me");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          return null;
        }
        throw err;
      }
    },
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (creds: { username: string; password: string }) =>
      api.post<{ user: User }>("/api/auth/login", creds),
    onSuccess: ({ user }) => {
      qc.setQueryData(ME_KEY, user);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/api/auth/logout"),
    onSuccess: () => {
      qc.setQueryData(ME_KEY, null);
      // Drop everything else — it's all scoped to the logged-out user.
      qc.clear();
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (payload: { current_password: string; new_password: string }) =>
      api.post<void>("/api/auth/change-password", payload),
  });
}
