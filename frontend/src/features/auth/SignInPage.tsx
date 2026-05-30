import { SignIn } from "@clerk/clerk-react";

/**
 * Clerk-hosted sign-in widget (FR-001, FR-006).
 *
 * `routing="path"` lets Clerk own subpaths under `/sign-in/*` (email
 * verification, factor selection, social callbacks). After sign-in we land
 * back on `/` where `<SignedIn>` reveals the app shell.
 */
export function SignInPage(): JSX.Element {
  return (
    <main className="flex min-h-screen items-center justify-center bg-amber-50 p-4">
      <SignIn
        routing="path"
        path="/sign-in"
        signUpUrl="/sign-up"
        afterSignInUrl="/"
      />
    </main>
  );
}
