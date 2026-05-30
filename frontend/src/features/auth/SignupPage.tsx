import { SignUp } from "@clerk/clerk-react";

/**
 * Clerk-hosted sign-up widget (FR-001, FR-002).
 *
 * Clerk handles email/password creation, the Google OAuth flow, and the
 * email-verification token exchange. On completion the user is redirected
 * to `/` where the `SignedIn` gate mounts the shell — but writes are still
 * blocked by `<VerifyEmailBanner>` until the verification claim flips true.
 */
export function SignUpPage(): JSX.Element {
  return (
    <main className="flex min-h-screen items-center justify-center bg-amber-50 p-4">
      <SignUp
        routing="path"
        path="/sign-up"
        signInUrl="/sign-in"
        afterSignUpUrl="/"
      />
    </main>
  );
}
