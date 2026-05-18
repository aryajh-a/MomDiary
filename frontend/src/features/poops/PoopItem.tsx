import type { PoopConsistency, PoopEntry } from "@/shared/types";
import { formatLocalTime } from "@/shared/time";

const CONSISTENCY_LABEL: Record<PoopConsistency, string> = {
  watery: "Watery",
  soft: "Soft",
  formed: "Formed",
  hard: "Hard",
};

export function PoopItem({ entry }: { entry: PoopEntry }): JSX.Element {
  return (
    <li className="flex items-baseline justify-between gap-3 rounded border border-poop-50 bg-white p-3">
      <div className="flex flex-col">
        <span className="font-semibold text-2xl text-poop-700">
          {CONSISTENCY_LABEL[entry.consistency]}
        </span>
      </div>
      <span className="text-slate-500 text-xs">{formatLocalTime(entry.occurred_at)}</span>
    </li>
  );
}
