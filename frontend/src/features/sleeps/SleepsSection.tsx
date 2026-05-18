import { useSelectedDate } from "@/features/date/useSelectedDate";
import { SectionShell } from "@/shared/SectionShell";
import { SleepIcon } from "./icon";
import { SleepItem } from "./SleepItem";
import { EMPTY_SLEEPS } from "./empty";
import { useSleeps } from "./useSleeps";

export function SleepsSection(): JSX.Element {
  const { date } = useSelectedDate();
  const q = useSleeps(date);
  const items = q.data?.items ?? [];
  return (
    <SectionShell
      title="Sleeps"
      ariaLabel="Sleeps"
      icon={<SleepIcon />}
      accentClass="border-sleep-50"
      isLoading={q.isLoading}
      isError={q.isError}
      count={items.length}
      emptyText={EMPTY_SLEEPS}
      onRetry={() => q.refetch()}
    >
      {items.map((entry) => (
        <SleepItem key={entry.id} entry={entry} />
      ))}
    </SectionShell>
  );
}
