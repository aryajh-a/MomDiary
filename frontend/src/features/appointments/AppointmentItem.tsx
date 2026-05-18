import type { AppointmentEntry } from "@/shared/types";
import { formatLocalTime } from "@/shared/time";

export function AppointmentItem({ entry }: { entry: AppointmentEntry }): JSX.Element {
  const latestNote = entry.notes[entry.notes.length - 1];
  const extra = entry.notes.length - 1;
  return (
    <li className="flex flex-col gap-1 rounded border border-appointment-50 bg-white p-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-semibold text-2xl text-appointment-700">
          {formatLocalTime(entry.scheduled_at)}
        </span>
        {extra > 0 ? (
          <span className="text-slate-500 text-xs">+{extra} more</span>
        ) : null}
      </div>
      {latestNote ? (
        <p className="line-clamp-2 text-slate-600 text-sm">{latestNote.body}</p>
      ) : null}
    </li>
  );
}
