import { useState } from "react";
import { ApiError } from "@/shared/apiClient";
import { useRegisterMutation } from "./useSession";

export function SignupPage(props: { onSwitchToLogin: () => void }): JSX.Element {
  const { onSwitchToLogin } = props;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const register = useRegisterMutation();

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (register.isPending) return;
    register.mutate({
      email: email.trim(),
      password,
      display_name: displayName.trim(),
    });
  };

  const errMsg =
    register.error instanceof ApiError
      ? register.error.status === 409
        ? "An account with that email already exists."
        : register.error.message
      : null;

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold">Create your MomDiary account</h1>
      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        <label className="flex flex-col gap-1 text-sm">
          <span>Your name</span>
          <input
            required
            maxLength={80}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5"
          />
        </label>
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
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5"
          />
          <span className="text-xs text-slate-500">At least 12 characters.</span>
        </label>
        {errMsg && (
          <p role="alert" className="text-sm text-red-600">
            {errMsg}
          </p>
        )}
        <button
          type="submit"
          disabled={register.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-60"
        >
          {register.isPending ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="text-sm text-slate-600">
        Already have an account?{" "}
        <button
          type="button"
          onClick={onSwitchToLogin}
          className="text-slate-900 underline"
        >
          Sign in
        </button>
      </p>
    </main>
  );
}
