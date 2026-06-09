import { useState } from "react";
import { ApiError } from "@/shared/apiClient";
import { useCreateBabyMutation } from "./useBabies";

function todayIsoDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Shown after sign-in when the user has no active baby (FR-009 / US2). */
export function FirstBabyPrompt(): JSX.Element {
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [colorTag, setColorTag] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const create = useCreateBabyMutation();

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (create.isPending) return;
    const trimmed = name.trim();
    if (trimmed.length === 0) {
      setClientError("Please enter your baby's name.");
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dob)) {
      setClientError("Please enter a valid date of birth.");
      return;
    }
    if (dob > todayIsoDate()) {
      setClientError("Date of birth can't be in the future.");
      return;
    }
    setClientError(null);
    create.mutate({
      display_name: trimmed,
      date_of_birth: dob,
      ...(colorTag.trim() ? { color_tag: colorTag.trim() } : {}),
    });
  };

  const serverError =
    create.error instanceof ApiError ? create.error.message : null;
  const errMsg = clientError ?? serverError;

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold">Add your baby</h1>
      <p className="text-sm text-slate-600">
        We&apos;ll scope everything you log — feeds, sleeps, diapers — to this baby.
      </p>
      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        <label className="flex flex-col gap-1 text-sm">
          <span>Baby&apos;s name</span>
          <input
            required
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Date of birth</span>
          <input
            type="date"
            required
            max={todayIsoDate()}
            value={dob}
            onChange={(e) => setDob(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Color tag (optional)</span>
          <input
            maxLength={16}
            value={colorTag}
            onChange={(e) => setColorTag(e.target.value)}
            placeholder="e.g. blue"
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
          disabled={create.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-60"
        >
          {create.isPending ? "Saving…" : "Continue"}
        </button>
      </form>
    </main>
  );
}
