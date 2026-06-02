import { useState } from "react";
import { ApiError } from "@/shared/apiClient";
import { detectBrowserTimezone } from "@/shared/time";
import { useLoginMutation } from "./useSession";

export function LoginPage(props: { onSwitchToSignup: () => void }): JSX.Element {
  const { onSwitchToSignup } = props;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLoginMutation();

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (login.isPending) return;
    login.mutate({ email: email.trim(), password, timezone: detectBrowserTimezone() });
  };

  const errMsg =
    login.error instanceof ApiError
      ? login.error.status === 401
        ? "Invalid email or password."
        : login.error.message
      : null;

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold">Sign in to MomDiary</h1>
      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        <label className="flex flex-col gap-1 text-sm">
          <span>Email</span>
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Password</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            minLength={12}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5"
          />
        </label>
        {errMsg && (
          <p role="alert" className="text-sm text-red-600">
            {errMsg}
          </p>
        )}
        <button
          type="submit"
          disabled={login.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-60"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="text-sm text-slate-600">
        No account?{" "}
        <button
          type="button"
          onClick={onSwitchToSignup}
          className="text-slate-900 underline"
        >
          Create one
        </button>
      </p>
    </main>
  );
}
