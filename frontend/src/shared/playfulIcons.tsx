// Playful, multi-colour SVG icons used by the home tiles and the matching
// history page headers / rows. Kept in one place so the look stays in sync
// across screens.
//
// All icons are 24×24 viewBox and accept an optional className for sizing
// (e.g. "h-5 w-5"). Colours are hard-coded inside the SVGs — the tile's
// surrounding pastel circle background still provides contrast.

type IconProps = { className?: string };

// -----------------------------------------------------------------------------
// Feed — smiling baby bottle with a sparkle.
// -----------------------------------------------------------------------------
export function FeedFunIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      {/* nipple */}
      <rect x="9.5" y="1.8" width="5" height="2.6" rx="1.2" fill="#fcd9b0" stroke="#f59e0b" strokeWidth="0.5" />
      {/* cap collar */}
      <rect x="8.3" y="4.4" width="7.4" height="2" rx="0.5" fill="#94a3b8" />
      {/* body */}
      <rect x="7.3" y="6.4" width="9.4" height="15.2" rx="2.6" fill="#ffffff" stroke="#3b82f6" strokeWidth="1.2" />
      {/* milk line */}
      <path d="M7.5 14h9" stroke="#bfdbfe" strokeWidth="1.4" strokeLinecap="round" />
      {/* eyes */}
      <circle cx="10.4" cy="12" r="0.75" fill="#0f172a" />
      <circle cx="13.6" cy="12" r="0.75" fill="#0f172a" />
      {/* smile */}
      <path d="M10.4 15 Q12 16.3 13.6 15" stroke="#0f172a" strokeWidth="1" fill="none" strokeLinecap="round" />
      {/* sparkle */}
      <path
        d="M19.2 3.5l0.4 1 1 0.4-1 0.4-0.4 1-0.4-1-1-0.4 1-0.4z"
        fill="#fde047"
        stroke="#f59e0b"
        strokeWidth="0.3"
      />
    </svg>
  );
}

// -----------------------------------------------------------------------------
// Sleep — fluffy sleeping cloud with closed eyes and "zZz".
// -----------------------------------------------------------------------------
export function SleepFunIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      {/* cloud body */}
      <path
        d="M6 17 q-3 0 -3 -3 q0 -2.6 2.6 -3 q0 -3 3 -3 q2 0 3 2 q1.5 -1 3 0 q3 0 3 3 q2 0 2 2 q0 2 -2 2 z"
        fill="#e0e7ff"
        stroke="#6366f1"
        strokeWidth="1"
        strokeLinejoin="round"
      />
      {/* closed eyes */}
      <path d="M9 14 q1 -1.2 2 0" stroke="#3730a3" strokeWidth="0.9" fill="none" strokeLinecap="round" />
      <path d="M13 14 q1 -1.2 2 0" stroke="#3730a3" strokeWidth="0.9" fill="none" strokeLinecap="round" />
      {/* blush */}
      <circle cx="8.2" cy="15" r="0.7" fill="#fda4af" opacity="0.7" />
      <circle cx="15.8" cy="15" r="0.7" fill="#fda4af" opacity="0.7" />
      {/* zZz */}
      <path
        d="M16 4 L19 4 L16 7 L19 7"
        stroke="#7c3aed"
        strokeWidth="1.1"
        fill="none"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

// -----------------------------------------------------------------------------
// Poop — three-tier brown swirl with a smile and sparkle.
// -----------------------------------------------------------------------------
export function PoopFunIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      {/* bottom bulge */}
      <path d="M3 21 Q3 13.5 12 13.5 Q21 13.5 21 21 Z" fill="#92400e" />
      {/* middle bulge */}
      <path d="M6 14.5 Q6 9 12 9 Q18 9 18 14.5 Z" fill="#b45309" />
      {/* top blob */}
      <path d="M9 9.5 Q9 4 12 4 Q15 4 15 9.5 Z" fill="#d97706" />
      {/* eyes */}
      <circle cx="9.8" cy="16.2" r="1.25" fill="#ffffff" />
      <circle cx="14.2" cy="16.2" r="1.25" fill="#ffffff" />
      <circle cx="9.8" cy="16.2" r="0.55" fill="#0f172a" />
      <circle cx="14.2" cy="16.2" r="0.55" fill="#0f172a" />
      {/* smile */}
      <path d="M10 18.6 Q12 20.2 14 18.6" stroke="#ffffff" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      {/* sparkle */}
      <path
        d="M20 6l0.3 0.8 0.8 0.3-0.8 0.3-0.3 0.8-0.3-0.8-0.8-0.3 0.8-0.3z"
        fill="#fde047"
      />
    </svg>
  );
}

// -----------------------------------------------------------------------------
// Appointment — calendar page with a red heart in the middle.
// -----------------------------------------------------------------------------
export function AppointmentFunIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      {/* page */}
      <rect x="3" y="5" width="18" height="16" rx="2" fill="#ffffff" stroke="#f472b6" strokeWidth="1.2" />
      {/* header band */}
      <path d="M3 7 q0 -2 2 -2 h14 q2 0 2 2 v2 H3 z" fill="#f472b6" />
      {/* binding rings */}
      <rect x="6" y="3" width="2" height="4" rx="0.5" fill="#be185d" />
      <rect x="16" y="3" width="2" height="4" rx="0.5" fill="#be185d" />
      {/* faint grid lines */}
      <path d="M3 12 H21 M3 16 H21" stroke="#fce7f3" strokeWidth="0.8" />
      {/* heart */}
      <path
        d="M12 19 Q7.5 15.8 7.5 13.2 Q7.5 11 9.8 11 Q11.2 11 12 12.6 Q12.8 11 14.2 11 Q16.5 11 16.5 13.2 Q16.5 15.8 12 19z"
        fill="#ef4444"
        stroke="#b91c1c"
        strokeWidth="0.5"
        strokeLinejoin="round"
      />
      {/* heart highlight */}
      <path d="M10.2 12.4 q-0.6 0.6 -0.4 1.4" stroke="#fecaca" strokeWidth="0.8" fill="none" strokeLinecap="round" />
    </svg>
  );
}
