import { useSelectedDate } from "@/features/date/useSelectedDate";
import { SectionShell } from "@/shared/SectionShell";
import { PoopIcon } from "./icon";
import { PoopItem } from "./PoopItem";
import { EMPTY_POOPS } from "./empty";
import { usePoops } from "./usePoops";

export function PoopsSection(): JSX.Element {
  const { date } = useSelectedDate();
  const q = usePoops(date);
  const items = q.data?.items ?? [];
  return (
    <SectionShell
      title="Diapers"
      ariaLabel="Poops"
      icon={<PoopIcon />}
      accentClass="border-poop-50"
      isLoading={q.isLoading}
      isError={q.isError}
      count={items.length}
      emptyText={EMPTY_POOPS}
      onRetry={() => q.refetch()}
    >
      {items.map((entry) => (
        <PoopItem key={entry.id} entry={entry} />
      ))}
    </SectionShell>
  );
}
