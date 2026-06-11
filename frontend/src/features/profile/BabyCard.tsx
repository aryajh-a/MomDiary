import type { Baby } from "@/shared/types";

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
 * A baby row on the Profile surface. Tapping the card opens that baby's
 * dedicated profile screen, where editing and removal now live (Feature 010).
 * Editing/removing a baby is no longer offered inline on this list.
 */
export function BabyCard(props: {
  baby: Baby;
  isActive: boolean;
  onOpen?: () => void;
}): JSX.Element {
  const { baby, isActive, onOpen } = props;

  const summary = (
    <>
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
    </>
  );

  return (
    <article
      aria-label={`Baby ${baby.display_name}`}
      className={`rounded-2xl bg-white p-4 shadow-sm ring-1 ${isActive ? "ring-amber-300" : "ring-slate-200"}`}
    >
      {onOpen ? (
        <button
          type="button"
          onClick={onOpen}
          aria-label={`Open ${baby.display_name}'s profile`}
          className="block w-full rounded text-left hover:opacity-80"
        >
          {summary}
        </button>
      ) : (
        <div className="min-w-0">{summary}</div>
      )}
    </article>
  );
}
