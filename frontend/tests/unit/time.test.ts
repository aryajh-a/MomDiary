import { describe, expect, it } from "vitest";
import { formatDateHeading, formatDuration, formatLocalTime } from "@/shared/time";

describe("formatLocalTime", () => {
  it("renders an ISO timestamp as local h:mm a", () => {
    const out = formatLocalTime("2026-05-17T07:15:00-07:00");
    expect(out).toMatch(/^\d{1,2}:\d{2}\s?(AM|PM)$/);
  });
  it("returns empty string on bad input", () => {
    expect(formatLocalTime("not-a-date")).toBe("");
  });
});

describe("formatDateHeading", () => {
  it("returns 'Today' for today", () => {
    expect(formatDateHeading(new Date())).toBe("Today");
  });
  it("returns 'Yesterday' for yesterday", () => {
    const y = new Date();
    y.setDate(y.getDate() - 1);
    expect(formatDateHeading(y)).toBe("Yesterday");
  });
  it("returns weekday + month + day for other dates", () => {
    // Use a date that is reliably neither today nor yesterday (1 year out).
    const d = new Date();
    d.setFullYear(d.getFullYear() + 1);
    d.setDate(15);
    expect(formatDateHeading(d)).toMatch(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/);
  });
});

describe("formatDuration", () => {
  it.each([
    [0, "0m"],
    [5, "5m"],
    [60, "1h"],
    [90, "1h 30m"],
    [125, "2h 5m"],
  ])("formats %i minutes as %s", (m, expected) => {
    expect(formatDuration(m)).toBe(expected);
  });
  it("returns empty string for negatives or NaN", () => {
    expect(formatDuration(-1)).toBe("");
    expect(formatDuration(Number.NaN)).toBe("");
  });
});
