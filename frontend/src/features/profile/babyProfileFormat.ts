/**
 * Display helpers for the Baby Profile screen (Feature 010).
 *
 * Pure formatting only — no React, no I/O — so they're trivially unit-testable
 * and shared between view mode and any future surface. Unset optional fields
 * render an explicit placeholder rather than being hidden (FR-003).
 */
import type { Gender } from "@/shared/types";

export const NOT_SET = "Not set";

/** Human age derived from an ISO `YYYY-MM-DD` date of birth (FR-002). */
export function formatAge(dobIso: string): string {
  const dob = new Date(dobIso + "T00:00:00");
  if (Number.isNaN(dob.getTime())) return "";
  const now = new Date();
  const months =
    (now.getFullYear() - dob.getFullYear()) * 12 +
    (now.getMonth() - dob.getMonth()) -
    (now.getDate() < dob.getDate() ? 1 : 0);
  if (months < 1) {
    const days = Math.max(
      0,
      Math.floor((now.getTime() - dob.getTime()) / 86_400_000),
    );
    return `${days} day${days === 1 ? "" : "s"} old`;
  }
  if (months < 24) return `${months} month${months === 1 ? "" : "s"} old`;
  const years = Math.floor(months / 12);
  return `${years} year${years === 1 ? "" : "s"} old`;
}

/** "Born" line — a friendly long date, falling back to the raw ISO string. */
export function formatBornDate(dobIso: string): string {
  const d = new Date(dobIso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return dobIso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

const GENDER_LABELS: Record<Gender, string> = {
  girl: "Girl",
  boy: "Boy",
  other: "Other",
};

export function formatGender(gender: Gender | null): string {
  return gender ? GENDER_LABELS[gender] : NOT_SET;
}

export function formatWeight(weightKg: number | null): string {
  return weightKg == null ? NOT_SET : `${weightKg} kg`;
}

export function formatHeight(heightCm: number | null): string {
  return heightCm == null ? NOT_SET : `${heightCm} cm`;
}

/** "Last measured" line — friendly date, or the unset placeholder. */
export function formatLastMeasured(measuredAtIso: string | null): string {
  return measuredAtIso ? formatBornDate(measuredAtIso) : NOT_SET;
}

export interface DeltaDisplay {
  /** e.g. "↑0.3 kg" / "↓1.5 cm". */
  text: string;
  /** true when the value increased (drives the up/down arrow + colour). */
  up: boolean;
}

/**
 * Change vs the previous measurement, for the growth card. Returns null when
 * there is no prior measurement (`delta == null`) or no change (`0`), so the
 * UI shows just the current value with no badge.
 */
export function deltaDisplay(
  delta: number | null,
  unit: string,
): DeltaDisplay | null {
  if (delta == null || delta === 0) return null;
  const up = delta > 0;
  // Round display to 2 dp to avoid float noise (e.g. 0.30000000000000004).
  const magnitude = Math.round(Math.abs(delta) * 100) / 100;
  return { text: `${up ? "↑" : "↓"}${magnitude} ${unit}`, up };
}

/** Avatar initials from a display name (placeholder while photos are deferred). */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 1).toUpperCase();
  return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
}
