import { useState } from "react";
import { ApiError } from "@/shared/apiClient";
import type { UserPublic } from "@/shared/types";
import { useUpdateProfileMutation } from "../auth/useSession";

const NAME_MAX = 80;

/**
 * View + edit the caregiver's own profile fields.
 *
 * Display name is editable (FR-005 / FR-007). Email is shown read-only —
 * sign-in identifier changes are out of scope for v1 (FR-008).
 */
export function CaregiverCard(props: { user: UserPublic }): JSX.Element {
  const { user } = props;
  const update = useUpdateProfileMutation();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user.display_name);
  const [clientError, setClientError] = useState<string | null>(null);

  const startEdit = () => {
    setName(user.display_name);
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
      setClientError("Display name can't be empty.");
      return;
    }
    if (trimmed.length > NAME_MAX) {
      setClientError(`Display name must be ${NAME_MAX} characters or fewer.`);
      return;
    }
    setClientError(null);
    update.mutate(
      { display_name: trimmed },
      { onSuccess: () => setEditing(false) },
    );
  };

  const serverError =
    update.error instanceof ApiError ? update.error.message : null;
  const error = clientError ?? serverError;

  return (
    <section
      aria-labelledby="profile-caregiver-heading"
      className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2
          id="profile-caregiver-heading"
          className="text-sm font-semibold uppercase tracking-wide text-slate-500"
        >
          Your details
        </h2>
        {!editing ? (
          <button
            type="button"
            onClick={startEdit}
            className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 hover:bg-amber-200"
          >
            Edit
          </button>
        ) : null}
      </div>

      {!editing ? (
        <dl className="space-y-2">
          <div>
            <dt className="text-xs text-slate-500">Name</dt>
            <dd className="text-base font-medium text-slate-900">
              {user.display_name}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Email</dt>
            <dd className="text-sm text-slate-700">{user.email}</dd>
          </div>
        </dl>
      ) : (
        <form onSubmit={save} noValidate className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs text-slate-500">Name</span>
            <input
              autoFocus
              maxLength={NAME_MAX + 1}
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "caregiver-name-error" : undefined}
              className="rounded border border-slate-300 px-2 py-1.5"
            />
          </label>
          <div className="text-xs text-slate-500">
            Email: <span className="text-slate-700">{user.email}</span>{" "}
            <span className="text-slate-400">(can't be changed here)</span>
          </div>
          {error ? (
            <p
              id="caregiver-name-error"
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
      )}
    </section>
  );
}
