import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { addDays, format, isSameDay, parseISO, startOfDay } from "date-fns";
import { usePoops } from "@/features/poops/usePoops";
import { apiClient } from "@/shared/apiClient";
import { queryKeys } from "@/shared/queryKeys";
import { PoopFunIcon } from "@/shared/playfulIcons";
import type { PoopConsistency, PoopEntry, PoopUpdate } from "@/shared/types";

// -----------------------------------------------------------------------------
// PoopHistoryPage — mirrors FeedHistoryPage layout.
//
// Header → day strip (‹ today ›) → stats banner (count / most-common
// consistency / avg gap) → list of poop cards → floating "+" FAB that opens a
// modal which supports both create (POST /v1/poops) and edit (PATCH/DELETE).
// -----------------------------------------------------------------------------

interface PoopHistoryPageProps {
  onBack: () => void;
}

export function PoopHistoryPage({ onBack }: PoopHistoryPageProps): JSX.Element {
  const [date, setDate] = useState<Date>(() => startOfDay(new Date()));
  const [modal, setModal] = useState<"new" | PoopEntry | null>(null);
  const poops = usePoops(date);
  const items = poops.data?.items ?? [];

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-4 bg-amber-50 px-4 pt-6 pb-28 text-slate-900">
      <Header onBack={onBack} />
      <DayStrip date={date} onChange={setDate} />
      <StatsBanner items={items} />
      <DayCaption date={date} count={items.length} />

      {poops.isLoading ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          Loading…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          No diaper changes for this day yet — tap + to log one.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((p) => (
            <PoopRow key={p.id} poop={p} onEdit={() => setModal(p)} />
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setModal("new")}
        aria-label="Log a diaper change"
        className="fixed right-6 bottom-6 z-30 grid h-14 w-14 place-items-center rounded-full bg-amber-500 text-3xl text-white shadow-lg ring-4 ring-amber-200 hover:bg-amber-600"
      >
        +
      </button>

      {modal !== null ? (
        <PoopFormModal
          defaultDate={date}
          poop={modal === "new" ? null : modal}
          onClose={() => setModal(null)}
          onDone={() => setModal(null)}
        />
      ) : null}
    </main>
  );
}

// -----------------------------------------------------------------------------
// Header
// -----------------------------------------------------------------------------

function Header({ onBack }: { onBack: () => void }): JSX.Element {
  return (
    <header className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back"
          className="grid h-9 w-9 place-items-center rounded-full text-slate-700 hover:bg-amber-100"
        >
          <ArrowLeftIcon className="h-5 w-5" />
        </button>
        <span className="grid h-8 w-8 place-items-center rounded-full bg-amber-100 text-amber-700">
          <PoopFunIcon className="h-6 w-6" />
        </span>
        <h1 className="text-lg font-semibold text-slate-900">Poop history</h1>
      </div>
      <button
        type="button"
        aria-label="Search"
        className="grid h-9 w-9 place-items-center rounded-full text-slate-500 hover:bg-amber-100"
      >
        <SearchIcon className="h-5 w-5" />
      </button>
    </header>
  );
}

// -----------------------------------------------------------------------------
// Day strip
// -----------------------------------------------------------------------------

function DayStrip(props: { date: Date; onChange: (d: Date) => void }): JSX.Element {
  const isToday = isSameDay(props.date, new Date());
  return (
    <div className="flex items-center justify-between rounded-2xl bg-amber-100/60 px-2 py-2 ring-1 ring-amber-200">
      <button
        type="button"
        onClick={() => props.onChange(addDays(props.date, -1))}
        aria-label="Previous day"
        className="grid h-8 w-8 place-items-center rounded-full bg-white text-slate-600 shadow-sm hover:bg-amber-50"
      >
        <ChevronLeftIcon className="h-4 w-4" />
      </button>
      <div className="flex flex-col items-center">
        <span className="flex items-center gap-1 text-sm font-semibold text-slate-800">
          {format(props.date, "EEE, MMM d")}
          <CalendarIcon className="h-4 w-4 text-slate-500" />
        </span>
        {isToday ? <span className="text-xs text-slate-500">Today</span> : null}
      </div>
      <button
        type="button"
        onClick={() => props.onChange(addDays(props.date, 1))}
        aria-label="Next day"
        className="grid h-8 w-8 place-items-center rounded-full bg-white text-slate-600 shadow-sm hover:bg-amber-50"
      >
        <ChevronRightIcon className="h-4 w-4" />
      </button>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Stats banner — count / most common consistency / avg gap between events
// -----------------------------------------------------------------------------

function StatsBanner({ items }: { items: PoopEntry[] }): JSX.Element {
  const { topConsistency, avgGapHours } = useMemo(() => {
    // Mode of consistency values (first one wins on tie, in enum order).
    const counts = new Map<PoopConsistency, number>();
    for (const p of items) counts.set(p.consistency, (counts.get(p.consistency) ?? 0) + 1);
    let topConsistency: PoopConsistency | null = null;
    let topCount = 0;
    for (const [k, v] of counts) {
      if (v > topCount) {
        topCount = v;
        topConsistency = k;
      }
    }

    if (items.length < 2) return { topConsistency, avgGapHours: null as number | null };
    const sorted = [...items].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));
    let totalMs = 0;
    for (let i = 1; i < sorted.length; i++) {
      const cur = sorted[i]!;
      const prev = sorted[i - 1]!;
      totalMs += parseISO(cur.occurred_at).getTime() - parseISO(prev.occurred_at).getTime();
    }
    const avgHours = totalMs / (sorted.length - 1) / (1000 * 60 * 60);
    return { topConsistency, avgGapHours: avgHours };
  }, [items]);

  return (
    <section
      aria-label="Diaper summary"
      className="grid grid-cols-3 rounded-2xl bg-amber-100/70 p-3 ring-1 ring-amber-200"
    >
      <Stat label="Changes" value={String(items.length)} />
      <div className="border-x border-amber-200/80">
        <Stat label="Most common" value={topConsistency ? prettyConsistency(topConsistency) : "—"} />
      </div>
      <Stat
        label="Avg gap"
        value={avgGapHours != null ? `${avgGapHours.toFixed(1)}h` : "—"}
      />
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="flex flex-col items-center px-1 text-center">
      <span className="text-[11px] text-slate-500">{label}</span>
      <span className="mt-0.5 text-base font-semibold text-slate-900">{value}</span>
    </div>
  );
}

function DayCaption({ date, count }: { date: Date; count: number }): JSX.Element {
  return (
    <p className="text-xs text-slate-500">
      {format(date, "MMM d")} — {count} {count === 1 ? "change" : "changes"}
    </p>
  );
}

// -----------------------------------------------------------------------------
// Poop row
// -----------------------------------------------------------------------------

function PoopRow({
  poop,
  onEdit,
}: {
  poop: PoopEntry;
  onEdit: () => void;
}): JSX.Element {
  const tone = consistencyTone(poop.consistency);
  return (
    <li>
      <button
        type="button"
        onClick={onEdit}
        aria-label={`Edit ${prettyConsistency(poop.consistency)} diaper at ${format(parseISO(poop.occurred_at), "h:mm a")}`}
        className="flex w-full items-center gap-3 rounded-2xl bg-white px-3 py-3 text-left shadow-sm ring-1 ring-slate-200 hover:bg-slate-50"
      >
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-full ${tone.bg} ${tone.fg}`}>
          <PoopFunIcon className="h-7 w-7" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-semibold text-slate-900">
            {prettyConsistency(poop.consistency)}
          </span>
          <span className="truncate text-xs text-slate-500">Diaper change</span>
        </div>
        <span className="shrink-0 text-xs text-slate-500">
          {format(parseISO(poop.occurred_at), "h:mm a")}
        </span>
        <ChevronRightIcon className="h-4 w-4 shrink-0 text-slate-300" />
      </button>
    </li>
  );
}

function prettyConsistency(c: PoopConsistency): string {
  switch (c) {
    case "watery":
      return "Watery";
    case "soft":
      return "Soft";
    case "formed":
      return "Formed";
    case "hard":
      return "Hard";
  }
}

function consistencyTone(c: PoopConsistency): { bg: string; fg: string } {
  switch (c) {
    case "watery":
      return { bg: "bg-sky-100", fg: "text-sky-600" };
    case "soft":
      return { bg: "bg-amber-100", fg: "text-amber-700" };
    case "formed":
      return { bg: "bg-emerald-100", fg: "text-emerald-700" };
    case "hard":
      return { bg: "bg-rose-100", fg: "text-rose-700" };
  }
}

// -----------------------------------------------------------------------------
// Poop form modal — create (poop=null) or edit (poop=PoopEntry).
// -----------------------------------------------------------------------------

function PoopFormModal(props: {
  defaultDate: Date;
  poop: PoopEntry | null;
  onClose: () => void;
  onDone: () => void;
}): JSX.Element {
  const qc = useQueryClient();
  const isEdit = props.poop !== null;
  const [consistency, setConsistency] = useState<PoopConsistency>(
    props.poop?.consistency ?? "soft",
  );
  const [whenLocal, setWhenLocal] = useState<string>(() =>
    toLocalInputValue(props.poop ? parseISO(props.poop.occurred_at) : new Date()),
  );
  const [error, setError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const invalidate = async () => {
    await qc.invalidateQueries({ queryKey: ["poops"] });
    await qc.invalidateQueries({ queryKey: queryKeys.poops(props.defaultDate) });
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const occurred_at = new Date(whenLocal).toISOString();
      if (props.poop) {
        const patch: PoopUpdate = {};
        if (consistency !== props.poop.consistency) patch.consistency = consistency;
        if (occurred_at !== props.poop.occurred_at) patch.occurred_at = occurred_at;
        return apiClient.updatePoop(props.poop.id, patch);
      }
      return apiClient.createPoop({ consistency, occurred_at });
    },
    onSuccess: async () => {
      await invalidate();
      props.onDone();
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Could not save diaper change");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => {
      if (!props.poop) throw new Error("Nothing to delete");
      return apiClient.deletePoop(props.poop.id);
    },
    onSuccess: async () => {
      await invalidate();
      props.onDone();
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Could not delete entry");
    },
  });

  const busy = saveMutation.isPending || deleteMutation.isPending;
  const valid = whenLocal.length > 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? "Edit diaper change" : "Log a diaper change"}
      className="fixed inset-0 z-40 flex items-end justify-center bg-slate-900/40 sm:items-center"
      onClick={props.onClose}
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          if (!valid || busy) return;
          saveMutation.mutate();
        }}
        className="flex w-full max-w-md flex-col gap-3 rounded-t-3xl bg-white p-5 shadow-2xl sm:rounded-2xl"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">
            {isEdit ? "Edit diaper change" : "Log a diaper change"}
          </h2>
          <button
            type="button"
            onClick={props.onClose}
            aria-label="Close"
            className="grid h-8 w-8 place-items-center rounded-full text-slate-500 hover:bg-slate-100"
          >
            ✕
          </button>
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-600">Consistency</span>
          <div className="grid grid-cols-4 gap-1.5">
            {(["watery", "soft", "formed", "hard"] as PoopConsistency[]).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setConsistency(c)}
                className={`rounded-lg px-2 py-1.5 text-xs font-medium ring-1 transition ${
                  consistency === c
                    ? "bg-amber-100 text-amber-700 ring-amber-300"
                    : "bg-white text-slate-700 ring-slate-200 hover:bg-slate-50"
                }`}
              >
                {prettyConsistency(c)}
              </button>
            ))}
          </div>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-600">When</span>
          <input
            type="datetime-local"
            value={whenLocal}
            onChange={(e) => setWhenLocal(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-amber-400 focus:outline-none focus:ring-1 focus:ring-amber-400"
          />
        </label>

        {error ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 ring-1 ring-red-200">
            {error}
          </p>
        ) : null}

        <div className="mt-1 flex items-center justify-between gap-2">
          {isEdit ? (
            confirmingDelete ? (
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <span>Delete this entry?</span>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate()}
                  disabled={busy}
                  className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteMutation.isPending ? "Deleting…" : "Yes, delete"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmingDelete(false)}
                  disabled={busy}
                  className="rounded-lg px-2 py-1.5 text-xs text-slate-600 hover:bg-slate-100"
                >
                  No
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmingDelete(true)}
                disabled={busy}
                className="rounded-lg px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                Delete
              </button>
            )
          ) : (
            <span />
          )}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={props.onClose}
              className="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!valid || busy}
              className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white shadow hover:bg-amber-600 disabled:opacity-50"
            >
              {saveMutation.isPending ? "Saving…" : isEdit ? "Save changes" : "Save entry"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

/**
 * Format a JS Date for an `<input type="datetime-local">` value.
 */
function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

// -----------------------------------------------------------------------------
// Inline icons
// -----------------------------------------------------------------------------

type IconProps = { className?: string };

function ArrowLeftIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}

function ChevronLeftIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}

function ChevronRightIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

function CalendarIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M16 3v4M8 3v4M3 10h18" />
    </svg>
  );
}

function SearchIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}
