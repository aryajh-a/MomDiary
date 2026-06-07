/** Unit tests for the Baby Profile display helpers (Feature 010). */
import { describe, expect, it } from "vitest";
import {
  deltaDisplay,
  formatGender,
  formatHeight,
  formatLastMeasured,
  formatWeight,
  initials,
  NOT_SET,
} from "@/features/profile/babyProfileFormat";

describe("babyProfileFormat", () => {
  it("labels gender or falls back to Not set", () => {
    expect(formatGender("girl")).toBe("Girl");
    expect(formatGender("boy")).toBe("Boy");
    expect(formatGender("other")).toBe("Other");
    expect(formatGender(null)).toBe(NOT_SET);
  });

  it("formats weight/height in metric with Not set for null", () => {
    expect(formatWeight(7.2)).toBe("7.2 kg");
    expect(formatWeight(8)).toBe("8 kg");
    expect(formatWeight(null)).toBe(NOT_SET);
    expect(formatHeight(62)).toBe("62 cm");
    expect(formatHeight(null)).toBe(NOT_SET);
  });

  it("formats growth deltas with arrow + direction, and nothing when flat/absent", () => {
    expect(deltaDisplay(0.3, "kg")).toEqual({ text: "↑0.3 kg", up: true });
    expect(deltaDisplay(-0.5, "cm")).toEqual({ text: "↓0.5 cm", up: false });
    expect(deltaDisplay(0, "kg")).toBeNull();
    expect(deltaDisplay(null, "kg")).toBeNull();
  });

  it("formats last-measured date or Not set", () => {
    expect(formatLastMeasured(null)).toBe(NOT_SET);
    expect(formatLastMeasured("2025-05-10")).toMatch(/may/i);
  });

  it("derives avatar initials", () => {
    expect(initials("Mia Johnson")).toBe("MJ");
    expect(initials("Liam")).toBe("L");
    expect(initials("  ")).toBe("?");
  });
});
