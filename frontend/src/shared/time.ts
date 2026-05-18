import { format, formatDistanceStrict, isToday, isYesterday } from "date-fns";

/** Format an ISO-8601 timestamp into a short local time like "7:15 AM". */
export function formatLocalTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return format(d, "h:mm a");
}

/** Format a calendar date heading: "Today", "Yesterday", or "Mon, May 17". */
export function formatDateHeading(date: Date): string {
  if (isToday(date)) return "Today";
  if (isYesterday(date)) return "Yesterday";
  return format(date, "EEE, MMM d");
}

/** Format minutes into a "Xh Ym" / "Ym" / "Xh" string. */
export function formatDuration(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes < 0) return "";
  const total = Math.round(minutes);
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

/** Express a relative timestamp like "2 hours ago" for chat / metadata uses. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return formatDistanceStrict(d, now, { addSuffix: true });
}
