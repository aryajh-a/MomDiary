import { useSelectedDate } from "@/features/date/useSelectedDate";
import { SectionShell } from "@/shared/SectionShell";
import { FeedIcon } from "./icon";
import { FeedItem } from "./FeedItem";
import { EMPTY_FEEDS } from "./empty";
import { useFeeds } from "./useFeeds";

export function FeedsSection(): JSX.Element {
  const { date } = useSelectedDate();
  const q = useFeeds(date);
  const items = q.data?.items ?? [];
  return (
    <SectionShell
      title="Feeds"
      ariaLabel="Feeds"
      icon={<FeedIcon />}
      accentClass="border-feed-50"
      isLoading={q.isLoading}
      isError={q.isError}
      count={items.length}
      emptyText={EMPTY_FEEDS}
      onRetry={() => q.refetch()}
    >
      {items.map((entry) => (
        <FeedItem key={entry.id} entry={entry} date={date} />
      ))}
    </SectionShell>
  );
}
