import { useState } from "react";
import { ApiError } from "@/shared/apiClient";
import type { Baby } from "@/shared/types";
import { useUpdateBabyMutation } from "../babies/useBabies";
import { RemoveBabyDialog } from "./RemoveBabyDialog";

const NAME_MAX = 80;

function todayIsoDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function ageFromDob(dobIso: string): string {
  const dob = new Date(dobIso + "T00:00:00");
  if (Number.isNaN(dob.getTime())) return "";
  const now = new Date();
  const months =
    (now.getFullYear() - dob.getFullYear()) * 12 +
    (now.getMonth() - dob.getMonth()) -
    (now.getDate() < dob.getDate() ? 1 : 0);
  if (months < 1) {
    const days = Math.max(0, Math.floor((now.getTime() - dob.getTime()) / 86_400_000));
    return `${days} day${days === 1 ? "" : "s"} old`;
  }
  if (months < 24) return `${months} month${months === 1 ? "" : "s"} old`;
  const years = Math.floor(months / 12);
  return `${years} year${years === 1 ? "" : "s"} old`;
}

/**
 * View + edit a baby profile from the Profile surface.
 *
 * Editable fields are display name and date of birth (FR-009..FR-012).
 * Editing does not change the active baby (FR-013). Removal opens an
 * explicit confirmation dialog (FR-014..FR-018).
 */
export function BabyCard(props: {
  baby: Baby;
  isActive: boolean;
  onOpen?: () => void;
}): JSX.Element {
  const { baby, isActive, onOpen } = props;
  const update = useUpdateBabyMutation();
  const [editing, setEditing] = useState(false);
  const [removeOpen, setRemoveOpen] = useState(false);
  const [name, setName] = useState(baby.display_name);
  const [dob, setDob] = useState(baby.date_of_birth);
  const [clientError, setClientError] = useState<string | null>(null);

  const startEdit = () => {
    setName(baby.display_name);
    setDob(baby.date_of_birth);
    setClientError(null);
    update.reset();
    setEditing(true);
  };
  const cancel = () => {
    setEditing(false);
    setClientError(null);
    update.reset();
  };

  const save = (e: React.FormEvent) => {
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
      setClientError("Pick a valid date of birth.");
      return;
    }
    if (dob > todayIsoDate()) {
      setClientError("Date of birth can't be in the future.");
      return;
    }
    setClientError(null);
    update.mutate(
      { id: baby.id, body: { display_name: trimmed, date_of_birth: dob } },
      { onSuccess: () => setEditing(false) },
    );
  };

  const serverError =
    update.error instanceof ApiError ? update.error.message : null;
  const error = clientError ?? serverError;

  return (
    <article
      aria-label={`Baby ${baby.display_name}`}
      className={`rounded-2xl bg-white p-4 shadow-sm ring-1 ${isActive ? "ring-amber-300" : "ring-slate-200"}`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        {onOpen ? (
          <button
            type="button"
            onClick={onOpen}
            aria-label={`Open ${baby.display_name}'s profile`}
            className="min-w-0 rounded text-left hover:opacity-80"
          >
            <div className="flex items-center gap-2">
              <h3 className="truncate text-base font-semibold text-slate-900">
                {baby.display_name}
              </h3>
              {isActive ? (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
                  Active
                </span>
              ) : null}
            </div>
            <p className="text-xs text-slate-500">
              DOB {baby.date_of_birth} · {ageFromDob(baby.date_of_birth)}
            </p>
          </button>
        ) : (
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="truncate text-base font-semibold text-slate-900">
                {baby.display_name}
              </h3>
              {isActive ? (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
                  Active
                </span>
              ) : null}
            </div>
            <p className="text-xs text-slate-500">
              DOB {baby.date_of_birth} · {ageFromDob(baby.date_of_birth)}
            </p>
          </div>
        )}
        {!editing ? (
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={startEdit}
              className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 hover:bg-amber-200"
            >
              Edit
            </button>
            <button
              type="button"
              onClick={() => setRemoveOpen(true)}
              className="rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100"
            >
              Remove
            </button>
          </div>
        ) : null}
      </div>

      {editing ? (
        <form onSubmit={save} noValidate className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs text-slate-500">Name</span>
            <input
              autoFocus
              maxLength={NAME_MAX + 1}
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `baby-${baby.id}-error` : undefined}
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
            <p
              id={`baby-${baby.id}-error`}
              role="alert"
              aria-live="polite"
              className="text-sm text-red-600"
            >
              {error}
            </p>
          ) : null}
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={update.isPending}
              className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-60"
            >
              {update.isPending ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={cancel}
              disabled={update.isPending}
              className="rounded bg-white px-3 py-1.5 text-sm text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      {removeOpen ? (
        <RemoveBabyDialog
          baby={baby}
          onClose={() => setRemoveOpen(false)}
        />
      ) : null}
    </article>
  );
}
