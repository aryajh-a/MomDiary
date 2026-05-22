import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { apiClient, ApiError, onUnauthorized, setActiveBabyId } from "@/shared/apiClient";
import type { LoginRequest, RegisterRequest, UserPublic, UserUpdate } from "@/shared/types";

export const SESSION_QUERY_KEY = ["session"] as const;

/** Subscribe to {@link UserPublic} for the signed-in caregiver.
 *
 * The query infinitely caches (`staleTime: Infinity`); `apiClient` evicts it on
 * 401 via `onUnauthorized`. On a successful fetch we mirror the user's persisted
 * `active_baby_id` into the module-level header state (`setActiveBabyId`).
 */
export function useSession() {
  const qc = useQueryClient();

  useEffect(() => {
    return onUnauthorized(() => {
      // Clear server-derived caches; the next render shows the LoginPage.
      qc.setQueryData<{ user: UserPublic } | null>(SESSION_QUERY_KEY, null);
      setActiveBabyId(null);
    });
  }, [qc]);

  const query = useQuery<{ user: UserPublic } | null, ApiError>({
    queryKey: SESSION_QUERY_KEY,
    queryFn: async () => {
      try {
        const res = await apiClient.me();
        setActiveBabyId(res.user.active_baby_id);
        return res;
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: Infinity,
    retry: false,
  });

  return query;
}

export function useLoginMutation() {
  const qc = useQueryClient();
  return useMutation<{ user: UserPublic }, ApiError, LoginRequest>({
    mutationFn: (body) => apiClient.login(body),
    onSuccess: (data) => {
      setActiveBabyId(data.user.active_baby_id);
      qc.setQueryData(SESSION_QUERY_KEY, data);
    },
  });
}

export function useRegisterMutation() {
  const qc = useQueryClient();
  return useMutation<{ user: UserPublic }, ApiError, RegisterRequest>({
    mutationFn: (body) => apiClient.register(body),
    onSuccess: (data) => {
      setActiveBabyId(data.user.active_baby_id);
      qc.setQueryData(SESSION_QUERY_KEY, data);
    },
  });
}

export function useLogoutMutation() {
  const qc = useQueryClient();
  return useMutation<{ ok: true }, ApiError, void>({
    mutationFn: () => apiClient.logout(),
    onSuccess: () => {
      setActiveBabyId(null);
      qc.setQueryData(SESSION_QUERY_KEY, null);
      qc.clear();
    },
  });
}

export function useUpdateProfileMutation() {
  const qc = useQueryClient();
  return useMutation<{ user: UserPublic }, ApiError, UserUpdate>({
    mutationFn: (body) => apiClient.updateMe(body),
    onSuccess: (data) => qc.setQueryData(SESSION_QUERY_KEY, data),
  });
}
