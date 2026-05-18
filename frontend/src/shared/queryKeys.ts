import { format } from "date-fns";

/** Convert a JS `Date` to the canonical `YYYY-MM-DD` key used by query keys. */
export function isoDate(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export const queryKeys = {
  feeds: (date: Date) => ["feeds", isoDate(date)] as const,
  sleeps: (date: Date) => ["sleeps", isoDate(date)] as const,
  poops: (date: Date) => ["poops", isoDate(date)] as const,
  appointments: (date: Date) => ["appointments", isoDate(date)] as const,
  allForDate: (date: Date) =>
    [
      ["feeds", isoDate(date)],
      ["sleeps", isoDate(date)],
      ["poops", isoDate(date)],
      ["appointments", isoDate(date)],
    ] as const,
};

export type SectionKey = "feeds" | "sleeps" | "poops" | "appointments";

export const entryTypeToSection: Record<string, SectionKey> = {
  feed: "feeds",
  sleep: "sleeps",
  poop: "poops",
  appointment: "appointments",
};
