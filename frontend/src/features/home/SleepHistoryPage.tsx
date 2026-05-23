import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  addDays,
  differenceInMinutes,
  format,
  isSameDay,
  parseISO,
  startOfDay,
} from "date-fns";
import { useSleeps } from "@/features/sleeps/useSleeps";
import { apiClient } from "@/shared/apiClient";
import { queryKeys } from "@/shared/queryKeys";
import type { SleepEntry, SleepUpdate } from "@/shared/types";

// -----------------------------------------------------------------------------
// SleepHistoryPage — mirrors FeedHistoryPage / PoopHistoryPage layout.
// Stats: count / total sleep / avg duration.
// Form fields: start_at, end_at (both required).
// -----------------------------------------------------------------------------

interface SleepHistoryPageProps {
  onBack: () => void;
}

export function SleepHistoryPage({ onBack }: SleepHistoryPageProps): JSX.Element {
  const [date, setDate] = useState<Date>(() => startOfDay(new Date()));
  const [modal, setModal] = useState<"new" | SleepEntry | null>(null);
  const sleeps = useSleeps(date);
  const items = sleeps.data?.items ?? [];

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-4 bg-amber-50 px-4 pt-6 pb-28 text-slate-900">
      <Header onBack={onBack} />
      <DayStrip date={date} onChange={setDate} />
      <StatsBanner items={items} />
      <DayCaption date={date} count={items.length} />

      {sleeps.isLoading ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          Loading…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          No sleeps for this day yet — tap + to log one.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((s) => (
            <SleepRow key={s.id} sleep={s} onEdit={() => setModal(s)} />
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setModal("new")}
        aria-label="Log a sleep"
        className="fixed right-6 bottom-6 z-30 grid h-14 w-14 place-items-center rounded-full bg-amber-500 text-3xl text-white shadow-lg ring-4 ring-amber-200 hover:bg-amber-600"
      >
        +
      </button>

      {modal !== null ? (
        <SleepFormModal
          defaultDate={date}
          sleep={modal === "new" ? null : modal}
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
        <span className="grid h-8 w-8 place-items-center rounded-full bg-violet-100 text-violet-600">
          <MoonIcon className="h-4 w-4" />
        </span>
        <h1 className="text-lg font-semibold text-slate-900">Sleep history</h1>
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
// Stats banner — sleeps / total sleep / avg duration
// -----------------------------------------------------------------------------

function StatsBanner({ items }: { items: SleepEntry[] }): JSX.Element {
  const { totalMin, avgMin } = useMemo(() => {
    const totalMin = items.reduce((s, x) => s + x.duration_minutes, 0);
    const avgMin = items.length > 0 ? totalMin / items.length : null;
    return { totalMin, avgMin };
  }, [items]);

  return (
    <section
      aria-label="Sleep summary"
      className="grid grid-cols-3 rounded-2xl bg-amber-100/70 p-3 ring-1 ring-amber-200"
    >
      <Stat label="Sleeps" value={String(items.length)} />
      <div className="border-x border-amber-200/80">
        <Stat label="Total" value={totalMin > 0 ? formatDuration(totalMin) : "—"} />
      </div>
      <Stat label="Avg" value={avgMin != null ? formatDuration(Math.round(avgMin)) : "—"} />
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
      {format(date, "MMM d")} — {count} {count === 1 ? "sleep" : "sleeps"}
    </p>
  );
}

// -----------------------------------------------------------------------------
// Sleep row
// -----------------------------------------------------------------------------

function SleepRow({
  sleep,
  onEdit,
}: {
  sleep: SleepEntry;
  onEdit: () => void;
}): JSX.Element {
  const start = parseISO(sleep.start_at);
  const end = parseISO(sleep.end_at);
  return (
    <li>
      <button
        type="button"
        onClick={onEdit}
        aria-label={`Edit sleep starting ${format(start, "h:mm a")}`}
        className="flex w-full items-center gap-3 rounded-2xl bg-white px-3 py-3 text-left shadow-sm ring-1 ring-slate-200 hover:bg-slate-50"
      >
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-violet-100 text-violet-600">
          <MoonIcon className="h-5 w-5" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-semibold text-slate-900">
            {formatDuration(sleep.duration_minutes)}
          </span>
          <span className="truncate text-xs text-slate-500">
            {format(start, "h:mm a")} – {format(end, "h:mm a")}
          </span>
        </div>
        <ChevronRightIcon className="h-4 w-4 shrink-0 text-slate-300" />
      </button>
    </li>
  );
}

function formatDuration(totalMin: number): string {
  if (totalMin <= 0) return "0m";
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

// -----------------------------------------------------------------------------
// Sleep form modal
// -----------------------------------------------------------------------------

function SleepFormModal(props: {
  defaultDate: Date;
  sleep: SleepEntry | null;
  onClose: () => void;
  onDone: () => void;
}): JSX.Element {
  const qc = useQueryClient();
  const isEdit = props.sleep !== null;
  // Default new entries to "1h ending now".
  const defaultEnd = props.sleep ? parseISO(props.sleep.end_at) : new Date();
  const defaultStart = props.sleep
    ? parseISO(props.sleep.start_at)
    : new Date(defaultEnd.getTime() - 60 * 60 * 1000);

  const [startLocal, setStartLocal] = useState<string>(() => toLocalInputValue(defaultStart));
  const [endLocal, setEndLocal] = useState<string>(() => toLocalInputValue(defaultEnd));
  const [error, setError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const invalidate = async () => {
    await qc.invalidateQueries({ queryKey: ["sleeps"] });
    await qc.invalidateQueries({ queryKey: queryKeys.sleeps(props.defaultDate) });
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const start_at = new Date(startLocal).toISOString();
      const end_at = new Date(endLocal).toISOString();
      if (props.sleep) {
        const patch: SleepUpdate = {};
        if (start_at !== props.sleep.start_at) patch.start_at = start_at;
        if (end_at !== props.sleep.end_at) patch.end_at = end_at;
        return apiClient.updateSleep(props.sleep.id, patch);
      }
      return apiClient.createSleep({ start_at, end_at });
    },
    onSuccess: async () => {
      await invalidate();
      props.onDone();
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Could not save sleep");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => {
      if (!props.sleep) throw new Error("Nothing to delete");
      return apiClient.deleteSleep(props.sleep.id);
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
  const startDate = startLocal ? new Date(startLocal) : null;
  const endDate = endLocal ? new Date(endLocal) : null;
  const valid =
    startDate != null &&
    endDate != null &&
    !Number.isNaN(startDate.getTime()) &&
    !Number.isNaN(endDate.getTime()) &&
    endDate.getTime() > startDate.getTime();
  const previewMin =
    valid && startDate && endDate ? differenceInMinutes(endDate, startDate) : 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? "Edit sleep" : "Log a sleep"}
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
            {isEdit ? "Edit sleep" : "Log a sleep"}
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
          <span className="text-slate-600">Started</span>
          <input
            type="datetime-local"
            value={startLocal}
            onChange={(e) => setStartLocal(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-violet-400 focus:outline-none focus:ring-1 focus:ring-violet-400"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-600">Ended</span>
          <input
            type="datetime-local"
            value={endLocal}
            onChange={(e) => setEndLocal(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-violet-400 focus:outline-none focus:ring-1 focus:ring-violet-400"
          />
        </label>

        {valid ? (
          <p className="text-xs text-slate-500">Duration: {formatDuration(previewMin)}</p>
        ) : (
          <p className="text-xs text-amber-700">End time must be after start time.</p>
        )}

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
              {saveMutation.isPending ? "Saving…" : isEdit ? "Save changes" : "Save sleep"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

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

function MoonIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M20 14.5A8 8 0 1110 4a7 7 0 0010 10.5z" />
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
