import type { SleepEntry } from "@/shared/types";
import { formatDuration, formatLocalTime } from "@/shared/time";

export function SleepItem({ entry }: { entry: SleepEntry }): JSX.Element {
  return (
    <li className="flex items-baseline justify-between gap-3 rounded border border-sleep-50 bg-white p-3">
      <div className="flex flex-col">
        <span className="font-semibold text-2xl text-sleep-700">
          {formatDuration(entry.duration_minutes)}
        </span>
        <span className="text-slate-600 text-sm">
          {formatLocalTime(entry.start_at)} – {formatLocalTime(entry.end_at)}
        </span>
      </div>
    </li>
  );
}
