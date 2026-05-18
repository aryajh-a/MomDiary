import { describe, expect, it } from "vitest";
import { queryKeys, isoDate } from "@/shared/queryKeys";

describe("queryKeys", () => {
  const d = new Date(2026, 4, 17);

  it("produces stable, deterministic keys", () => {
    expect(queryKeys.feeds(d)).toEqual(["feeds", isoDate(d)]);
    expect(queryKeys.sleeps(d)).toEqual(["sleeps", isoDate(d)]);
    expect(queryKeys.poops(d)).toEqual(["poops", isoDate(d)]);
    expect(queryKeys.appointments(d)).toEqual(["appointments", isoDate(d)]);
  });

  it("returns the same key for the same date instance", () => {
    expect(queryKeys.feeds(d)).toEqual(queryKeys.feeds(new Date(2026, 4, 17)));
  });

  it("allForDate returns the four keys", () => {
    const all = queryKeys.allForDate(d);
    expect(all).toHaveLength(4);
    expect(all[0]?.[0]).toBe("feeds");
    expect(all[1]?.[0]).toBe("sleeps");
    expect(all[2]?.[0]).toBe("poops");
    expect(all[3]?.[0]).toBe("appointments");
  });

  it("isoDate uses YYYY-MM-DD", () => {
    expect(isoDate(d)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
