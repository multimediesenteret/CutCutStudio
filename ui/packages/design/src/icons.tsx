// Icons from the GUI concept (concept/assets/views.js). Inline SVG: works offline in Edge.
import type { ReactElement } from "react";

const S = { fill: "none", stroke: "currentColor", strokeWidth: 2 } as const;
const R = { ...S, strokeLinecap: "round" } as const;

export const icons = {
  sun: (
    <>
      <circle cx="12" cy="12" r="4.5" {...S} />
      <g {...R}>
        <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" />
      </g>
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" {...S} strokeLinejoin="round" />,
  cam: (
    <>
      <rect x="2.5" y="6" width="13" height="12" rx="2.5" {...S} />
      <path d="M15.5 10.5l6-3.5v10l-6-3.5z" {...S} strokeLinejoin="round" />
    </>
  ),
  mic: (
    <>
      <rect x="8.5" y="2.5" width="7" height="12" rx="3.5" {...S} />
      <path d="M5 11.5a7 7 0 0 0 14 0M12 18.5V22" {...R} />
    </>
  ),
  card: (
    <>
      <rect x="2.5" y="5" width="19" height="14" rx="2.5" {...S} />
      <path d="M2.5 9.5h19" {...S} />
    </>
  ),
  check: <path d="M5 12.5l4.5 4.5L19 7.5" {...R} strokeWidth={2.6} strokeLinejoin="round" />,
  help: (
    <>
      <circle cx="12" cy="12" r="9.5" {...S} />
      <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.6v.6M12 17.2v.1" {...R} />
    </>
  ),
  grid: (
    <>
      <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" {...S} />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" {...S} />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" {...S} />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" {...S} />
    </>
  ),
  sliders: (
    <>
      <g {...R}>
        <path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" />
      </g>
      <g {...S}>
        <circle cx="16" cy="6" r="2" />
        <circle cx="10" cy="12" r="2" />
        <circle cx="18" cy="18" r="2" />
      </g>
    </>
  ),
  rec: (
    <>
      <circle cx="12" cy="12" r="9" {...S} />
      <circle cx="12" cy="12" r="4.5" fill="currentColor" />
    </>
  ),
  pulse: <path d="M2.5 12h4l2.5-6 4.5 12 2.5-6h5.5" {...R} strokeLinejoin="round" />,
  wand: (
    <>
      <path d="M4 20L15 9M13 7l4 4" {...R} />
      <path
        d="M18 2.5v3M16.5 4h3M20.5 9v2M19.5 10h2M9 3v2M8 4h2"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
      />
    </>
  ),
  list: (
    <g {...R}>
      <path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" />
    </g>
  ),
  gear: (
    <>
      <circle cx="12" cy="12" r="3.2" {...S} />
      <path
        d="M12 2.5v2.6M12 18.9v2.6M21.5 12h-2.6M5.1 12H2.5M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8M18.7 18.7l-1.8-1.8M7.1 7.1L5.3 5.3"
        {...R}
      />
    </>
  ),
} as const;

export type IconName = keyof typeof icons;

export function Icon({ name }: { name: IconName }): ReactElement {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {icons[name]}
    </svg>
  );
}

export function Logo({ className = "logo" }: { className?: string }): ReactElement {
  return (
    <svg className={className} viewBox="20 50 190 90" role="img" aria-label="CutCut Studio">
      <g fill="var(--eye)">
        <rect x="32" y="90" width="7" height="20" rx="3.5" />
        <rect x="44" y="78" width="7" height="44" rx="3.5" />
        <rect x="56" y="68" width="7" height="64" rx="3.5" />
        <rect x="68" y="82" width="7" height="36" rx="3.5" />
        <rect x="80" y="92" width="7" height="16" rx="3.5" />
      </g>
      <g stroke="var(--pgm)" strokeWidth="6" strokeLinecap="round">
        <line x1="100" y1="128" x2="114" y2="72" />
        <line x1="116" y1="128" x2="130" y2="72" />
      </g>
      <rect
        x="158"
        y="56"
        width="44"
        height="30"
        rx="5"
        fill="none"
        stroke="var(--bleed)"
        strokeWidth="1.5"
      />
      <rect
        x="151"
        y="72"
        width="44"
        height="30"
        rx="5"
        fill="none"
        stroke="var(--bleed)"
        strokeWidth="1.5"
      />
      <rect
        x="144"
        y="88"
        width="48"
        height="34"
        rx="5"
        fill="var(--eye-soft)"
        stroke="var(--eye)"
        strokeWidth="2.5"
      />
      <circle cx="182" cy="97" r="4" fill="var(--pgm)" />
    </svg>
  );
}
