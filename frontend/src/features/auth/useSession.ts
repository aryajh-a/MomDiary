import { useAuth, useClerk } from "@clerk/clerk-react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useEffect } from "react";
import { apiClient, ApiError, onUnauthorized, setActiveBabyId } from "@/shared/apiClient";
import type { CurrentUser, UserPublic, UserUpdate } from "@/shared/types";

/**
 * `useSession()` returns the backend's `CurrentUserOut` projection wrapped in
 * `{ user }` for backward compatibility with the rest of the app, which still
 * reads `session.data?.user`. The query is gated on Clerk's `isSignedIn`:
 * when signed-out it resolves to `null` so the `<SignedOut>` branch can take
 * over (App.tsx).
 */
export const SESSION_QUERY_KEY = ["session"] as const;

type SessionPayload = { user: CurrentUser } | null;

export function useSession(): UseQueryResult<SessionPayload, ApiError> {
  const qc = useQueryClient();
  const { isLoaded, isSignedIn } = useAuth();

  useEffect(() => {
    return onUnauthorized(() => {
      qc.setQueryData<SessionPayload>(SESSION_QUERY_KEY, null);
      setActiveBabyId(null);
    });
  }, [qc]);

  return useQuery<SessionPayload, ApiError>({
    queryKey: SESSION_QUERY_KEY,
    enabled: isLoaded && isSignedIn === true,
    queryFn: async () => {
      try {
        const user = await apiClient.me();
        setActiveBabyId(user.active_baby_id);
        return { user };
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: Infinity,
    retry: false,
  });
}

/**
 * Profile mutation. Backend `PUT /v1/users/me` is exempt from the
 * email-verification gate (T046a), so unverified users can still set their
 * display name on first sign-in.
 *
 * The backend returns the legacy `{ user: UserPublic }` envelope, which
 * lacks `clerk_user_id`. We patch only the mutable fields back into the
 * cached `CurrentUser` so subscribers stay consistent.
 */
export function useUpdateProfileMutation() {
  const qc = useQueryClient();
  return useMutation<{ user: UserPublic }, ApiError, UserUpdate>({
    mutationFn: (body) => apiClient.updateMe(body),
    onSuccess: (data) => {
      qc.setQueryData<SessionPayload>(SESSION_QUERY_KEY, (prev) => {
        if (!prev) return prev;
        return {
          user: {
            ...prev.user,
            display_name: data.user.display_name,
            email: data.user.email,
            active_baby_id: data.user.active_baby_id,
          },
        };
      });
    },
  });
}

/**
 * `useLogoutMutation()` — Clerk signOut + local cache wipe. The
 * `<SignedOut>` gate in App.tsx then renders the sign-in page.
 */
export function useLogoutMutation() {
  const qc = useQueryClient();
  const clerk = useClerk();
  return useMutation<void, ApiError, void>({
    mutationFn: async () => {
      await clerk.signOut();
    },
    onSuccess: () => {
      setActiveBabyId(null);
      qc.setQueryData<SessionPayload>(SESSION_QUERY_KEY, null);
      qc.clear();
    },
  });
}
