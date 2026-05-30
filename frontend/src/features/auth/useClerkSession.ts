import { useAuth } from "@clerk/clerk-react";

/**
 * Thin wrapper over Clerk's `useAuth()` exposing only the surface MomDiary
 * needs. We always mint backend JWTs from the `momdiary-default` template so
 * the `email` + `email_verified` claims are present (see plan.md §Decision 3
 * and quickstart.md §1).
 */
export function useClerkSession(): {
  isLoaded: boolean;
  isSignedIn: boolean;
  userId: string | null;
  /** Returns a freshly-minted JWT for the backend, or null when signed-out. */
  getToken: () => Promise<string | null>;
} {
  const { isLoaded, isSignedIn, userId, getToken } = useAuth();
  return {
    isLoaded,
    isSignedIn: Boolean(isSignedIn),
    userId: userId ?? null,
    getToken: () => getToken({ template: "momdiary-default" }),
  };
}
