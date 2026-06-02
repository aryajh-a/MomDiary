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

/** Convert an ISO-8601 timestamp into the value expected by
 *  `<input type="datetime-local">`: "YYYY-MM-DDTHH:mm" in local browser time. */
export function toDatetimeLocalInputValue(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

/** Convert a `<input type="datetime-local">` value back to an ISO-8601
 *  string with an explicit offset (uses local browser time + UTC `Z`). */
export function fromDatetimeLocalInputValue(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

/** The browser's current IANA timezone (e.g. "Asia/Kolkata"), or undefined if
 *  the environment can't report one. Sent on register/login so the backend can
 *  scope each caregiver's day boundaries to where they actually are (feature
 *  007). */
export function detectBrowserTimezone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}
