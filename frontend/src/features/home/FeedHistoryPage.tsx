import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { addDays, format, isSameDay, parseISO, startOfDay } from "date-fns";
import { useFeeds } from "@/features/feeds/useFeeds";
import { apiClient } from "@/shared/apiClient";
import { queryKeys } from "@/shared/queryKeys";
import type { FeedEntry, FeedType, FeedUnit, FeedUpdate } from "@/shared/types";

// -----------------------------------------------------------------------------
// FeedHistoryPage — matches UX/Feedhistory.jpeg.
//
// Header (back arrow + title) → day strip (‹ today ›) → stats banner (count /
// total ml / avg gap) → list of feed cards → floating "+" FAB that opens a
// small new-feed form that POSTs to /v1/feeds. On success the feeds query is
// invalidated so the list and the home page refresh.
// -----------------------------------------------------------------------------

interface FeedHistoryPageProps {
  onBack: () => void;
}

export function FeedHistoryPage({ onBack }: FeedHistoryPageProps): JSX.Element {
  const [date, setDate] = useState<Date>(() => startOfDay(new Date()));
  // `null` = no modal; `"new"` = create form; `FeedEntry` = edit that entry.
  const [modal, setModal] = useState<"new" | FeedEntry | null>(null);
  const feeds = useFeeds(date);
  const items = feeds.data?.items ?? [];

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-4 bg-amber-50 px-4 pt-6 pb-28 text-slate-900">
      <Header onBack={onBack} />
      <DayStrip date={date} onChange={setDate} />
      <StatsBanner items={items} />
      <DayCaption date={date} count={items.length} />

      {feeds.isLoading ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          Loading…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          No feeds for this day yet — tap + to log one.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((f) => (
            <FeedRow key={f.id} feed={f} onEdit={() => setModal(f)} />
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setModal("new")}
        aria-label="Log a feed"
        className="fixed right-6 bottom-6 z-30 grid h-14 w-14 place-items-center rounded-full bg-amber-500 text-3xl text-white shadow-lg ring-4 ring-amber-200 hover:bg-amber-600"
      >
        +
      </button>

      {modal !== null ? (
        <FeedFormModal
          defaultDate={date}
          feed={modal === "new" ? null : modal}
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
        <span className="grid h-8 w-8 place-items-center rounded-full bg-sky-100 text-sky-600">
          <DropIcon className="h-4 w-4" />
        </span>
        <h1 className="text-lg font-semibold text-slate-900">Feed history</h1>
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
// Stats banner
// -----------------------------------------------------------------------------

function StatsBanner({ items }: { items: FeedEntry[] }): JSX.Element {
  const { totalMl, avgGapHours } = useMemo(() => {
    // Sum quantities reported in ml. (Solids may be in `g` — we exclude them
    // from the "total ml" stat rather than mixing units.)
    const totalMl = items
      .filter((f) => f.unit === "ml")
      .reduce((s, f) => s + f.quantity, 0);

    // Avg gap = mean of deltas between consecutive feed timestamps.
    if (items.length < 2) return { totalMl, avgGapHours: null as number | null };
    const sorted = [...items].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));
    let totalMs = 0;
    for (let i = 1; i < sorted.length; i++) {
      const cur = sorted[i]!;
      const prev = sorted[i - 1]!;
      totalMs += parseISO(cur.occurred_at).getTime() - parseISO(prev.occurred_at).getTime();
    }
    const avgHours = totalMs / (sorted.length - 1) / (1000 * 60 * 60);
    return { totalMl, avgGapHours: avgHours };
  }, [items]);

  return (
    <section
      aria-label="Feed summary"
      className="grid grid-cols-3 rounded-2xl bg-amber-100/70 p-3 ring-1 ring-amber-200"
    >
      <Stat label="Feeds" value={String(items.length)} />
      <div className="border-x border-amber-200/80">
        <Stat label="Total ml" value={totalMl > 0 ? `${Math.round(totalMl)}ml` : "—"} />
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
      {format(date, "MMM d")} — {count} entr{count === 1 ? "y" : "ies"}
    </p>
  );
}

// -----------------------------------------------------------------------------
// Feed row
// -----------------------------------------------------------------------------

function FeedRow({
  feed,
  onEdit,
}: {
  feed: FeedEntry;
  onEdit: () => void;
}): JSX.Element {
  return (
    <li>
      <button
        type="button"
        onClick={onEdit}
        aria-label={`Edit ${prettyFeedType(feed.feed_type)} feed at ${format(parseISO(feed.occurred_at), "h:mm a")}`}
        className="flex w-full items-center gap-3 rounded-2xl bg-white px-3 py-3 text-left shadow-sm ring-1 ring-slate-200 hover:bg-slate-50"
      >
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-sky-100 text-sky-600">
          <DropIcon className="h-5 w-5" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-semibold text-slate-900">
            {feed.quantity}
            {feed.unit} · {prettyFeedType(feed.feed_type)}
          </span>
          <span className="truncate text-xs text-slate-500">
            {prettyFeedType(feed.feed_type)} feed
          </span>
        </div>
        <span className="shrink-0 text-xs text-slate-500">
          {format(parseISO(feed.occurred_at), "h:mm a")}
        </span>
        <ChevronRightIcon className="h-4 w-4 shrink-0 text-slate-300" />
      </button>
    </li>
  );
}

function prettyFeedType(t: FeedType): string {
  switch (t) {
    case "breast_milk":
      return "Breast";
    case "formula":
      return "Formula";
    case "solids":
      return "Solids";
    case "water":
      return "Water";
  }
}

// -----------------------------------------------------------------------------
// Feed form modal — handles both create (feed=null) and edit (feed=FeedEntry).
// In edit mode a Delete button is shown that DELETEs the entry.
// -----------------------------------------------------------------------------

function FeedFormModal(props: {
  defaultDate: Date;
  feed: FeedEntry | null;
  onClose: () => void;
  onDone: () => void;
}): JSX.Element {
  const qc = useQueryClient();
  const isEdit = props.feed !== null;
  const [feedType, setFeedType] = useState<FeedType>(props.feed?.feed_type ?? "formula");
  const [quantity, setQuantity] = useState<string>(
    props.feed ? String(props.feed.quantity) : "120",
  );
  const [unit, setUnit] = useState<FeedUnit>(props.feed?.unit ?? "ml");
  const [whenLocal, setWhenLocal] = useState<string>(() =>
    toLocalInputValue(props.feed ? parseISO(props.feed.occurred_at) : new Date()),
  );
  const [error, setError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const invalidate = async () => {
    // Invalidate every cached date for feeds — the entry might affect any day.
    await qc.invalidateQueries({ queryKey: ["feeds"] });
    await qc.invalidateQueries({ queryKey: queryKeys.feeds(props.defaultDate) });
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const occurred_at = new Date(whenLocal).toISOString();
      if (props.feed) {
        // Send only fields that changed, to keep PATCH minimal.
        const patch: FeedUpdate = {};
        if (feedType !== props.feed.feed_type) patch.feed_type = feedType;
        if (Number(quantity) !== props.feed.quantity) patch.quantity = Number(quantity);
        if (unit !== props.feed.unit) patch.unit = unit;
        if (occurred_at !== props.feed.occurred_at) patch.occurred_at = occurred_at;
        return apiClient.updateFeed(props.feed.id, patch);
      }
      return apiClient.createFeed({
        feed_type: feedType,
        quantity: Number(quantity),
        unit,
        occurred_at,
      });
    },
    onSuccess: async () => {
      await invalidate();
      props.onDone();
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Could not save feed");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => {
      if (!props.feed) throw new Error("Nothing to delete");
      return apiClient.deleteFeed(props.feed.id);
    },
    onSuccess: async () => {
      await invalidate();
      props.onDone();
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Could not delete feed");
    },
  });

  const busy = saveMutation.isPending || deleteMutation.isPending;
  const qtyNum = Number(quantity);
  const valid = Number.isFinite(qtyNum) && qtyNum > 0 && whenLocal.length > 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? "Edit feed" : "Log a feed"}
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
            {isEdit ? "Edit feed" : "Log a feed"}
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
          <span className="text-slate-600">Type</span>
          <div className="grid grid-cols-4 gap-1.5">
            {(["breast_milk", "formula", "solids", "water"] as FeedType[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setFeedType(t)}
                className={`rounded-lg px-2 py-1.5 text-xs font-medium ring-1 transition ${
                  feedType === t
                    ? "bg-sky-100 text-sky-700 ring-sky-300"
                    : "bg-white text-slate-700 ring-slate-200 hover:bg-slate-50"
                }`}
              >
                {prettyFeedType(t)}
              </button>
            ))}
          </div>
        </label>

        <div className="grid grid-cols-3 gap-2">
          <label className="col-span-2 flex flex-col gap-1 text-sm">
            <span className="text-slate-600">Quantity</span>
            <input
              type="number"
              inputMode="decimal"
              step="any"
              min="0"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-600">Unit</span>
            <select
              value={unit}
              onChange={(e) => setUnit(e.target.value as FeedUnit)}
              className="rounded-lg border border-slate-300 px-2 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
            >
              <option value="ml">ml</option>
              <option value="g">g</option>
            </select>
          </label>
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-600">When</span>
          <input
            type="datetime-local"
            value={whenLocal}
            onChange={(e) => setWhenLocal(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
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
                <span>Delete this feed?</span>
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
              {saveMutation.isPending ? "Saving…" : isEdit ? "Save changes" : "Save feed"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

/**
 * Format a JS Date for an `<input type="datetime-local">` value (the input
 * expects a naïve local-time string `YYYY-MM-DDTHH:mm`, no timezone).
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

function DropIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 2.5c2.5 3.5 7 8.2 7 12.3a7 7 0 11-14 0c0-4.1 4.5-8.8 7-12.3z" />
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
