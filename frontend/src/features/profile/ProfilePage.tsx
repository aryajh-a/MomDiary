import { useState } from "react";
import { ApiError } from "@/shared/apiClient";
import type { UserPublic } from "@/shared/types";
import { useBabies, useCreateBabyMutation } from "../babies/useBabies";
import { BabyCard } from "./BabyCard";
import { BabyProfilePage } from "./BabyProfilePage";
import { CaregiverCard } from "./CaregiverCard";

const NAME_MAX = 80;

/**
 * The Profile surface — one screen showing the caregiver's own details and
 * every non-deleted baby they own, with edit + remove affordances per row
 * and an "Add a baby" entry point. (Feature 007.)
 */
export function ProfilePage(props: {
  user: UserPublic;
  onBack?: () => void;
}): JSX.Element {
  const { user, onBack } = props;
  const babies = useBabies();
  const items = babies.data?.items ?? [];
  const [adding, setAdding] = useState(false);
  const [selectedBabyId, setSelectedBabyId] = useState<number | null>(null);

  // Open the dedicated per-baby profile. Read the baby straight from the
  // already-loaded list cache by id so each screen shows only that baby's
  // own data with no cross-baby bleed-through (FR-007).
  const selectedBaby =
    selectedBabyId == null
      ? null
      : (items.find((b) => b.id === selectedBabyId) ?? null);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-5 bg-amber-50 px-4 pt-6 pb-28 text-slate-900">
      <header className="flex items-center justify-between">
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            className="rounded-full bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm ring-1 ring-slate-200 hover:bg-amber-50"
            aria-label="Back to home"
          >
            ← Back
          </button>
        ) : (
          <span aria-hidden="true" className="w-[68px]" />
        )}
        <h1 className="text-2xl font-bold text-slate-900">Profile</h1>
        <span aria-hidden="true" className="w-[68px]" />
      </header>

      <CaregiverCard user={user} />

      <section aria-labelledby="profile-babies-heading" className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2
            id="profile-babies-heading"
            className="text-sm font-semibold uppercase tracking-wide text-slate-500"
          >
            Your babies
          </h2>
          {items.length > 0 ? (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 hover:bg-amber-200"
            >
              Add a baby
            </button>
          ) : null}
        </div>

        {babies.isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : babies.isError ? (
          <p role="alert" className="text-sm text-red-600">
            Couldn&apos;t load your babies.{" "}
            <button
              type="button"
              onClick={() => babies.refetch()}
              className="underline"
            >
              Retry
            </button>
          </p>
        ) : items.length === 0 ? (
          <div className="rounded-2xl bg-white p-4 text-center shadow-sm ring-1 ring-slate-200">
            <p className="text-sm text-slate-600">No baby added yet</p>
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="mt-3 rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700"
            >
              Add a baby
            </button>
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {items.map((b) => (
              <li key={b.id}>
                <BabyCard
                  baby={b}
                  isActive={b.id === user.active_baby_id}
                  onOpen={() => setSelectedBabyId(b.id)}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      {adding ? <AddBabyDialog onClose={() => setAdding(false)} /> : null}

      {/* Per-baby profile opens as a bottom sheet (mirrors the chat panel),
          overlaying the list rather than replacing the whole screen. */}
      {selectedBaby ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Baby profile"
          className="fixed inset-0 z-40 flex items-end justify-center bg-slate-900/40 sm:items-center"
          onClick={() => setSelectedBabyId(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md origin-bottom animate-[chatPop_180ms_ease-out]"
          >
            <BabyProfilePage
              baby={selectedBaby}
              onBack={() => setSelectedBabyId(null)}
            />
          </div>
        </div>
      ) : null}
    </main>
  );
}

// -----------------------------------------------------------------------------
// Add-baby modal (re-uses the existing create-baby mutation; minimal form so
// the Profile screen has a self-contained add entry point — FR-020/021).
// -----------------------------------------------------------------------------

function todayIsoDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function AddBabyDialog(props: { onClose: () => void }): JSX.Element {
  const { onClose } = props;
  const create = useCreateBabyMutation();
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (trimmed.length === 0) {
      setClientError("Name can't be empty.");
      return;
    }
    if (trimmed.length > NAME_MAX) {
      setClientError(`Name must be ${NAME_MAX} characters or fewer.`);
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dob)) {
      setClientError("Pick a date of birth.");
      return;
    }
    if (dob > todayIsoDate()) {
      setClientError("Date of birth can't be in the future.");
      return;
    }
    setClientError(null);
    create.mutate(
      { display_name: trimmed, date_of_birth: dob },
      { onSuccess: () => onClose() },
    );
  };

  const serverError =
    create.error instanceof ApiError ? create.error.message : null;
  const error = clientError ?? serverError;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-baby-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4"
      onClick={() => {
        if (!create.isPending) onClose();
      }}
    >
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        noValidate
        className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl"
      >
        <h2 id="add-baby-title" className="text-lg font-semibold text-slate-900">
          Add a baby
        </h2>
        <div className="mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs text-slate-500">Name</span>
            <input
              autoFocus
              maxLength={NAME_MAX + 1}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="rounded border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs text-slate-500">Date of birth</span>
            <input
              type="date"
              max={todayIsoDate()}
              value={dob}
              onChange={(e) => setDob(e.target.value)}
              className="rounded border border-slate-300 px-2 py-1.5"
            />
          </label>
          {error ? (
            <p role="alert" aria-live="polite" className="text-sm text-red-600">
              {error}
            </p>
          ) : null}
        </div>
        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={create.isPending}
            className="rounded bg-white px-3 py-1.5 text-sm text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50 disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-60"
          >
            {create.isPending ? "Adding…" : "Add"}
          </button>
        </div>
      </form>
    </div>
  );
}
