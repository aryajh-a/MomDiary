import { useState } from "react";
import { ApiError } from "@/shared/apiClient";
import type { Baby, Gender } from "@/shared/types";
import { genderSchema } from "@/shared/types";
import { useUpdateBabyMutation } from "../babies/useBabies";
import { RemoveBabyDialog } from "./RemoveBabyDialog";
import {
  deltaDisplay,
  formatAge,
  formatBornDate,
  formatGender,
  formatHeight,
  formatLastMeasured,
  formatWeight,
  initials,
  NOT_SET,
} from "./babyProfileFormat";

const NAME_MAX = 80;
const WEIGHT_MAX = 70;
const HEIGHT_MAX = 200;

const GENDER_OPTIONS = genderSchema.options;

function todayIsoDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Dedicated per-baby profile screen (Feature 010). Read-only by default
 * (FR-004); the caregiver taps "Edit profile" to reveal the form. Renders
 * strictly the baby passed in by `ProfilePage` (selected from the `["babies"]`
 * list cache by id) so there is no cross-baby bleed-through (FR-007).
 *
 * Photo upload is deferred (FR-017): the avatar shows initials and the camera
 * affordance is a visible but inert "coming soon" control.
 */
export function BabyProfilePage(props: {
  baby: Baby;
  onBack: () => void;
}): JSX.Element {
  const { baby, onBack } = props;
  const [editing, setEditing] = useState(false);
  const [removeOpen, setRemoveOpen] = useState(false);

  return (
    <section
      aria-label="Baby profile"
      className="mx-auto flex h-[34rem] max-h-[85vh] w-full max-w-md flex-col gap-5 overflow-y-auto rounded-t-3xl bg-amber-50 px-4 pt-6 pb-6 text-slate-900 shadow-2xl ring-1 ring-slate-200 sm:rounded-2xl"
    >
      <header className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="rounded-full bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm ring-1 ring-slate-200 hover:bg-amber-50"
          aria-label="Back to profile"
        >
          ← Back
        </button>
        <h1 className="text-2xl font-bold text-slate-900">Baby profile</h1>
        <span aria-hidden="true" className="w-[68px]" />
      </header>

      <IdentityHeader baby={baby} />

      {editing ? (
        <EditForm baby={baby} onDone={() => setEditing(false)} />
      ) : (
        <>
          <ViewDetails baby={baby} />
          <GrowthCard baby={baby} />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="rounded-lg bg-amber-600 px-3 py-2 text-sm font-medium text-white hover:bg-amber-700"
            >
              Edit profile
            </button>
            <button
              type="button"
              onClick={() => setRemoveOpen(true)}
              className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700 hover:bg-rose-100"
            >
              Remove
            </button>
          </div>
        </>
      )}

      {/* Removal opens an explicit confirmation. On success the babies list
          invalidates, this baby drops out of the cache, and the profile sheet
          unmounts on its own (see ProfilePage). */}
      {removeOpen ? (
        <RemoveBabyDialog baby={baby} onClose={() => setRemoveOpen(false)} />
      ) : null}
    </section>
  );
}

// -----------------------------------------------------------------------------
// Identity header — avatar placeholder + inert photo button, name, age, born.
// -----------------------------------------------------------------------------

function IdentityHeader(props: { baby: Baby }): JSX.Element {
  const { baby } = props;
  return (
    <section className="flex flex-col items-center gap-3">
      <div className="relative">
        <div
          aria-hidden="true"
          className="flex h-24 w-24 items-center justify-center rounded-full bg-amber-200 text-3xl font-semibold text-amber-800"
        >
          {initials(baby.display_name)}
        </div>
        <button
          type="button"
          disabled
          aria-disabled="true"
          aria-label="Add photo (coming soon)"
          title="Coming soon"
          className="absolute -bottom-1 -right-1 cursor-not-allowed rounded-full bg-white px-2 py-1 text-sm shadow ring-1 ring-slate-200 opacity-70"
        >
          📷
        </button>
      </div>
      <div className="text-center">
        <h2 className="text-xl font-semibold text-slate-900">
          {baby.display_name}
        </h2>
        <p className="text-sm text-slate-500">
          {formatAge(baby.date_of_birth)} · Born{" "}
          {formatBornDate(baby.date_of_birth)}
        </p>
      </div>
    </section>
  );
}

// -----------------------------------------------------------------------------
// View mode — read-only details list with explicit "Not set" placeholders.
// -----------------------------------------------------------------------------

function DetailRow(props: { label: string; value: string }): JSX.Element {
  const isUnset = props.value === NOT_SET;
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-2.5 last:border-b-0">
      <dt className="text-sm text-slate-500">{props.label}</dt>
      <dd
        className={`text-sm font-medium ${isUnset ? "text-slate-400" : "text-slate-900"}`}
      >
        {props.value}
      </dd>
    </div>
  );
}

function ViewDetails(props: { baby: Baby }): JSX.Element {
  const { baby } = props;
  return (
    <section
      aria-label="Baby details"
      className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
    >
      <dl>
        <DetailRow label="Gender" value={formatGender(baby.gender)} />
        <DetailRow
          label="Date of birth"
          value={formatBornDate(baby.date_of_birth)}
        />
      </dl>
    </section>
  );
}

// -----------------------------------------------------------------------------
// Growth measurements — current value + ↑/↓ delta vs the previous measurement,
// plus the last-measured date (Feature 010 growth history). Head circumference
// is intentionally omitted.
// -----------------------------------------------------------------------------

function GrowthRow(props: {
  label: string;
  value: string;
  delta: { text: string; up: boolean } | null;
}): JSX.Element {
  const { label, value, delta } = props;
  const isUnset = value === NOT_SET;
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-2.5 last:border-b-0">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="flex items-center gap-2">
        <span
          className={`text-sm font-medium ${isUnset ? "text-slate-400" : "text-slate-900"}`}
        >
          {value}
        </span>
        {delta ? (
          <span
            className={`text-xs font-semibold ${delta.up ? "text-emerald-600" : "text-rose-600"}`}
          >
            {delta.text}
          </span>
        ) : null}
      </dd>
    </div>
  );
}

function GrowthCard(props: { baby: Baby }): JSX.Element {
  const { baby } = props;
  return (
    <section
      aria-label="Growth measurements"
      className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
    >
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Growth measurements
      </h3>
      <dl>
        <GrowthRow
          label="Weight"
          value={formatWeight(baby.weight_kg)}
          delta={deltaDisplay(baby.weight_kg_delta, "kg")}
        />
        <GrowthRow
          label="Height"
          value={formatHeight(baby.height_cm)}
          delta={deltaDisplay(baby.height_cm_delta, "cm")}
        />
        <DetailRow
          label="Last measured"
          value={formatLastMeasured(baby.last_measured_at)}
        />
      </dl>
    </section>
  );
}

// -----------------------------------------------------------------------------
// Edit mode — pre-filled form, client validation mirroring the server schema.
// -----------------------------------------------------------------------------

function EditForm(props: { baby: Baby; onDone: () => void }): JSX.Element {
  const { baby, onDone } = props;
  const update = useUpdateBabyMutation();

  const [name, setName] = useState(baby.display_name);
  const [dob, setDob] = useState(baby.date_of_birth);
  const [gender, setGender] = useState<string>(baby.gender ?? "");
  const [weight, setWeight] = useState<string>(
    baby.weight_kg == null ? "" : String(baby.weight_kg),
  );
  const [height, setHeight] = useState<string>(
    baby.height_cm == null ? "" : String(baby.height_cm),
  );
  const [clientError, setClientError] = useState<string | null>(null);

  const parseOptionalNumber = (
    raw: string,
    label: string,
    max: number,
  ): { ok: true; value: number | null } | { ok: false; message: string } => {
    const trimmed = raw.trim();
    if (trimmed === "") return { ok: true, value: null };
    const n = Number(trimmed);
    if (!Number.isFinite(n) || n <= 0) {
      return { ok: false, message: `${label} must be a positive number.` };
    }
    if (n > max) {
      return { ok: false, message: `${label} must be ${max} or less.` };
    }
    return { ok: true, value: n };
  };

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (trimmedName.length === 0) {
      setClientError("Name can't be empty.");
      return;
    }
    if (trimmedName.length > NAME_MAX) {
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
    const w = parseOptionalNumber(weight, "Weight", WEIGHT_MAX);
    if (!w.ok) {
      setClientError(w.message);
      return;
    }
    const h = parseOptionalNumber(height, "Height", HEIGHT_MAX);
    if (!h.ok) {
      setClientError(h.message);
      return;
    }
    setClientError(null);

    update.mutate(
      {
        id: baby.id,
        body: {
          display_name: trimmedName,
          date_of_birth: dob,
          // Empty select value clears the field back to unset (FR-014).
          gender: gender === "" ? null : (gender as Gender),
          weight_kg: w.value,
          height_cm: h.value,
        },
      },
      { onSuccess: () => onDone() },
    );
  };

  const serverError =
    update.error instanceof ApiError ? update.error.message : null;
  const error = clientError ?? serverError;

  return (
    <form
      onSubmit={save}
      noValidate
      aria-label="Edit baby profile"
      className="flex flex-col gap-3 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-xs text-slate-500">Name</span>
        <input
          autoFocus
          maxLength={NAME_MAX + 1}
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-invalid={error ? true : undefined}
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

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-xs text-slate-500">Gender</span>
        <select
          value={gender}
          onChange={(e) => setGender(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1.5"
        >
          <option value="">Not set</option>
          {GENDER_OPTIONS.map((g) => (
            <option key={g} value={g}>
              {g.charAt(0).toUpperCase() + g.slice(1)}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-xs text-slate-500">Weight (kg)</span>
        <input
          type="number"
          inputMode="decimal"
          step="0.01"
          min="0"
          max={WEIGHT_MAX}
          value={weight}
          onChange={(e) => setWeight(e.target.value)}
          placeholder="Not set"
          className="rounded border border-slate-300 px-2 py-1.5"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-xs text-slate-500">Height (cm)</span>
        <input
          type="number"
          inputMode="decimal"
          step="0.1"
          min="0"
          max={HEIGHT_MAX}
          value={height}
          onChange={(e) => setHeight(e.target.value)}
          placeholder="Not set"
          className="rounded border border-slate-300 px-2 py-1.5"
        />
      </label>

      {error ? (
        <p role="alert" aria-live="polite" className="text-sm text-red-600">
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
          onClick={onDone}
          disabled={update.isPending}
          className="rounded bg-white px-3 py-1.5 text-sm text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50 disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
