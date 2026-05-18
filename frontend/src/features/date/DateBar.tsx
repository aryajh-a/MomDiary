import { useQueryClient } from "@tanstack/react-query";
import { addDays, format } from "date-fns";
import { useSelectedDate } from "./useSelectedDate";
import { formatDateHeading } from "@/shared/time";
import { queryKeys } from "@/shared/queryKeys";

export function DateBar(): JSX.Element {
  const { date, setDate } = useSelectedDate();
  const qc = useQueryClient();

  function shift(days: number) {
    const next = addDays(date, days);
    setDate(next);
    invalidate(next);
  }

  function invalidate(next: Date) {
    for (const key of queryKeys.allForDate(next)) {
      qc.invalidateQueries({ queryKey: key });
    }
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const [y, m, d] = e.target.value.split("-").map(Number);
    if (!y || !m || !d) return;
    const next = new Date(y, m - 1, d);
    setDate(next);
    invalidate(next);
  }

  return (
    <div className="flex items-center gap-2" data-testid="datebar">
      <button
        type="button"
        aria-label="Previous day"
        onClick={() => shift(-1)}
        className="rounded bg-slate-200 px-2 py-1 text-sm hover:bg-slate-300"
      >
        ‹
      </button>
      <div className="flex flex-col">
        <span className="font-medium text-base">{formatDateHeading(date)}</span>
        <input
          type="date"
          aria-label="Pick a date"
          value={format(date, "yyyy-MM-dd")}
          onChange={onPick}
          className="text-slate-500 text-xs"
        />
      </div>
      <button
        type="button"
        aria-label="Next day"
        onClick={() => shift(1)}
        className="rounded bg-slate-200 px-2 py-1 text-sm hover:bg-slate-300"
      >
        ›
      </button>
    </div>
  );
}
