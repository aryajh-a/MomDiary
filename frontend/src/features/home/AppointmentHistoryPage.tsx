import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { addDays, format, isSameDay, parseISO, startOfDay } from "date-fns";
import { useAppointments } from "@/features/appointments/useAppointments";
import { apiClient } from "@/shared/apiClient";
import { queryKeys } from "@/shared/queryKeys";
import type { AppointmentEntry, AppointmentUpdate } from "@/shared/types";

// -----------------------------------------------------------------------------
// AppointmentHistoryPage — mirrors the other history pages.
// Stats: count / next upcoming time (relative to "now") / notes total.
// Form fields: scheduled_at + optional first note (note is only sent on
// create — editing notes lives behind a separate notes endpoint and is out of
// scope here).
// -----------------------------------------------------------------------------

interface AppointmentHistoryPageProps {
  onBack: () => void;
}

export function AppointmentHistoryPage({
  onBack,
}: AppointmentHistoryPageProps): JSX.Element {
  const [date, setDate] = useState<Date>(() => startOfDay(new Date()));
  const [modal, setModal] = useState<"new" | AppointmentEntry | null>(null);
  const appts = useAppointments(date);
  const items = appts.data?.items ?? [];

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-4 bg-amber-50 px-4 pt-6 pb-28 text-slate-900">
      <Header onBack={onBack} />
      <DayStrip date={date} onChange={setDate} />
      <StatsBanner items={items} />
      <DayCaption date={date} count={items.length} />

      {appts.isLoading ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          Loading…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          No appointments for this day — tap + to add one.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((a) => (
            <AppointmentRow key={a.id} appt={a} onEdit={() => setModal(a)} />
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setModal("new")}
        aria-label="Add an appointment"
        className="fixed right-6 bottom-6 z-30 grid h-14 w-14 place-items-center rounded-full bg-amber-500 text-3xl text-white shadow-lg ring-4 ring-amber-200 hover:bg-amber-600"
      >
        +
      </button>

      {modal !== null ? (
        <AppointmentFormModal
          defaultDate={date}
          appt={modal === "new" ? null : modal}
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
        <span className="grid h-8 w-8 place-items-center rounded-full bg-pink-100 text-pink-600">
          <StethoscopeIcon className="h-4 w-4" />
        </span>
        <h1 className="text-lg font-semibold text-slate-900">Appointments</h1>
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
// Stats banner — count / earliest time / total notes
// -----------------------------------------------------------------------------

function StatsBanner({ items }: { items: AppointmentEntry[] }): JSX.Element {
  const { firstTime, totalNotes } = useMemo(() => {
    const sorted = [...items].sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
    const firstTime = sorted[0] ? format(parseISO(sorted[0].scheduled_at), "h:mm a") : null;
    const totalNotes = items.reduce((s, a) => s + a.notes.length, 0);
    return { firstTime, totalNotes };
  }, [items]);

  return (
    <section
      aria-label="Appointment summary"
      className="grid grid-cols-3 rounded-2xl bg-amber-100/70 p-3 ring-1 ring-amber-200"
    >
      <Stat label="Appts" value={String(items.length)} />
      <div className="border-x border-amber-200/80">
        <Stat label="First" value={firstTime ?? "—"} />
      </div>
      <Stat label="Notes" value={String(totalNotes)} />
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
      {format(date, "MMM d")} — {count} {count === 1 ? "appointment" : "appointments"}
    </p>
  );
}

// -----------------------------------------------------------------------------
// Appointment row
// -----------------------------------------------------------------------------

function AppointmentRow({
  appt,
  onEdit,
}: {
  appt: AppointmentEntry;
  onEdit: () => void;
}): JSX.Element {
  const when = parseISO(appt.scheduled_at);
  const firstNote = appt.notes[0]?.body;
  const detail =
    firstNote != null
      ? firstNote
      : appt.notes.length === 0
        ? "No notes yet"
        : `${appt.notes.length} note${appt.notes.length === 1 ? "" : "s"}`;
  return (
    <li>
      <button
        type="button"
        onClick={onEdit}
        aria-label={`Edit appointment at ${format(when, "h:mm a")}`}
        className="flex w-full items-center gap-3 rounded-2xl bg-white px-3 py-3 text-left shadow-sm ring-1 ring-slate-200 hover:bg-slate-50"
      >
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-pink-100 text-pink-600">
          <StethoscopeIcon className="h-5 w-5" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-semibold text-slate-900">
            {format(when, "h:mm a")}
          </span>
          <span className="truncate text-xs text-slate-500">{detail}</span>
        </div>
        <ChevronRightIcon className="h-4 w-4 shrink-0 text-slate-300" />
      </button>
    </li>
  );
}

// -----------------------------------------------------------------------------
// Appointment form modal
// -----------------------------------------------------------------------------

function AppointmentFormModal(props: {
  defaultDate: Date;
  appt: AppointmentEntry | null;
  onClose: () => void;
  onDone: () => void;
}): JSX.Element {
  const qc = useQueryClient();
  const isEdit = props.appt !== null;
  const [whenLocal, setWhenLocal] = useState<string>(() =>
    toLocalInputValue(props.appt ? parseISO(props.appt.scheduled_at) : nextHour(new Date())),
  );
  // `note` is only used during create — editing notes is via a different
  // endpoint and is intentionally not exposed in this modal.
  const [note, setNote] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const invalidate = async () => {
    await qc.invalidateQueries({ queryKey: ["appointments"] });
    await qc.invalidateQueries({ queryKey: queryKeys.appointments(props.defaultDate) });
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const scheduled_at = new Date(whenLocal).toISOString();
      if (props.appt) {
        const patch: AppointmentUpdate = {};
        if (scheduled_at !== props.appt.scheduled_at) patch.scheduled_at = scheduled_at;
        return apiClient.updateAppointment(props.appt.id, patch);
      }
      const trimmed = note.trim();
      return apiClient.createAppointment({
        scheduled_at,
        ...(trimmed.length > 0 ? { note: trimmed } : {}),
      });
    },
    onSuccess: async () => {
      await invalidate();
      props.onDone();
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Could not save appointment");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => {
      if (!props.appt) throw new Error("Nothing to delete");
      return apiClient.deleteAppointment(props.appt.id);
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
      aria-label={isEdit ? "Edit appointment" : "Add appointment"}
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
            {isEdit ? "Edit appointment" : "Add appointment"}
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
          <span className="text-slate-600">When</span>
          <input
            type="datetime-local"
            value={whenLocal}
            onChange={(e) => setWhenLocal(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-pink-400 focus:outline-none focus:ring-1 focus:ring-pink-400"
          />
        </label>

        {!isEdit ? (
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-600">Note (optional)</span>
            <textarea
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={2000}
              placeholder="e.g. 2-month checkup with Dr. Lee"
              className="resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-pink-400 focus:outline-none focus:ring-1 focus:ring-pink-400"
            />
          </label>
        ) : appt_notes_preview(props.appt!)}

        {error ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 ring-1 ring-red-200">
            {error}
          </p>
        ) : null}

        <div className="mt-1 flex items-center justify-between gap-2">
          {isEdit ? (
            confirmingDelete ? (
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <span>Delete this appointment?</span>
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
              {saveMutation.isPending
                ? "Saving…"
                : isEdit
                  ? "Save changes"
                  : "Save appointment"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

// Read-only preview of existing notes when editing (notes are managed via a
// separate endpoint, so they're shown but not editable from this modal).
function appt_notes_preview(appt: AppointmentEntry): JSX.Element {
  if (appt.notes.length === 0) {
    return (
      <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500 ring-1 ring-slate-200">
        No notes on this appointment.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-1.5 rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200">
      <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
        Notes
      </span>
      {appt.notes.map((n) => (
        <p key={n.id} className="text-xs text-slate-700">
          {n.body}
        </p>
      ))}
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

function nextHour(d: Date): Date {
  const r = new Date(d);
  r.setMinutes(0, 0, 0);
  r.setHours(r.getHours() + 1);
  return r;
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

function StethoscopeIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M6 3v6a5 5 0 0010 0V3" />
      <circle cx="18" cy="15" r="2.5" />
      <path d="M11 14v2a4 4 0 004 4 4 4 0 004-4v-1.5" />
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
