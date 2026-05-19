import { useState } from "react";

import type { AppointmentEntry } from "@/shared/types";
import { formatLocalTime } from "@/shared/time";

export function AppointmentItem({ entry }: { entry: AppointmentEntry }): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const latestNote = entry.notes[entry.notes.length - 1];
  const extra = entry.notes.length - 1;
  const hasMore = extra > 0;
  return (
    <li className="flex flex-col gap-1 rounded border border-appointment-50 bg-white p-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-semibold text-2xl text-appointment-700">
          {formatLocalTime(entry.scheduled_at)}
        </span>
        {hasMore ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={expanded ? "Collapse notes" : `Show ${extra} more notes`}
            className="rounded px-1 text-slate-500 text-xs hover:bg-slate-100 hover:text-slate-700"
          >
            {expanded ? `− hide` : `+${extra} more`}
          </button>
        ) : null}
      </div>
      {expanded ? (
        <ul className="flex flex-col gap-2">
          {entry.notes.map((n, i) => (
            <li
              key={n.id ?? i}
              className="whitespace-pre-wrap rounded border border-slate-100 bg-slate-50 p-2 text-slate-700 text-sm"
            >
              {n.body}
            </li>
          ))}
        </ul>
      ) : latestNote ? (
        <p className="line-clamp-2 text-slate-600 text-sm">{latestNote.body}</p>
      ) : null}
    </li>
  );
}
