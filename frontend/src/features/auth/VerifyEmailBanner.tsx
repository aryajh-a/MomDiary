import { useUser } from "@clerk/clerk-react";
import { useState } from "react";

/**
 * Persistent banner shown at the top of the app shell while the signed-in
 * caregiver's primary email is unverified. Fulfils FR-003 (block diary
 * writes until verified) on the client side; the backend `require_verified_email`
 * dependency is the authoritative gate.
 *
 * Renders nothing once Clerk reports the email is verified.
 */
export function VerifyEmailBanner(): JSX.Element | null {
  const { isLoaded, user } = useUser();
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isLoaded || !user) return null;

  const primary = user.primaryEmailAddress;
  if (!primary) return null;
  if (primary.verification?.status === "verified") return null;

  const resend = async () => {
    setError(null);
    setSending(true);
    try {
      await primary.prepareVerification({ strategy: "email_code" });
      setSent(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not send email");
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className="border-b border-amber-200 bg-amber-100 px-4 py-2 text-xs text-amber-900"
    >
      <div className="mx-auto flex w-full max-w-md flex-wrap items-center justify-between gap-2">
        <span>
          Verify <strong>{primary.emailAddress}</strong> to start logging
          entries.
        </span>
        <button
          type="button"
          onClick={resend}
          disabled={sending || sent}
          className="rounded bg-white px-2 py-1 text-amber-900 ring-1 ring-amber-300 hover:bg-amber-50 disabled:opacity-60"
        >
          {sending ? "Sending…" : sent ? "Sent ✓" : "Resend email"}
        </button>
        {error ? <span className="basis-full text-red-700">{error}</span> : null}
      </div>
    </div>
  );
}
