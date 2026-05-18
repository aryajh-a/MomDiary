import type { FeedEntry, FeedType, FeedUnit } from "@/shared/types";
import { formatLocalTime } from "@/shared/time";

const FEED_LABEL: Record<FeedType, string> = {
  breast_milk: "breast milk",
  formula: "formula",
  solids: "solids",
  water: "water",
};

const UNIT_LABEL: Record<FeedUnit, string> = { ml: "ml", g: "g" };

export function FeedItem({ entry }: { entry: FeedEntry }): JSX.Element {
  return (
    <li className="flex items-baseline justify-between gap-3 rounded border border-feed-50 bg-white p-3">
      <div className="flex flex-col">
        <span className="font-semibold text-2xl text-feed-700">
          {entry.quantity} {UNIT_LABEL[entry.unit]}
        </span>
        <span className="text-slate-600 text-sm">{FEED_LABEL[entry.feed_type]}</span>
      </div>
      <span className="text-slate-500 text-xs">{formatLocalTime(entry.occurred_at)}</span>
    </li>
  );
}
