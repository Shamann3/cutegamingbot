function SkinSvg({ children }) {
  return (
    <svg className="gm-skin-mark" viewBox="0 0 160 160" aria-hidden="true">
      {children}
    </svg>
  )
}

const MARKS = {
  board: (
    <SkinSvg>
      <rect x="78" y="18" width="28" height="28" fill="currentColor" opacity="0.55" />
      <rect x="106" y="18" width="28" height="28" fill="currentColor" opacity="0.16" />
      <rect x="78" y="46" width="28" height="28" fill="currentColor" opacity="0.16" />
      <rect x="106" y="46" width="28" height="28" fill="currentColor" opacity="0.55" />
      <circle cx="92" cy="32" r="7" fill="#1a120c" opacity="0.7" />
      <circle cx="120" cy="60" r="7" fill="#f3efe6" opacity="0.55" />
    </SkinSvg>
  ),
  wood: (
    <SkinSvg>
      <ellipse cx="118" cy="42" rx="34" ry="22" fill="none" stroke="currentColor" strokeWidth="3" opacity="0.28" />
      <ellipse cx="118" cy="42" rx="22" ry="13" fill="none" stroke="currentColor" strokeWidth="2.4" opacity="0.38" />
      <ellipse cx="118" cy="42" rx="10" ry="6" fill="currentColor" opacity="0.42" />
    </SkinSvg>
  ),
  cookie: (
    <SkinSvg>
      <circle cx="118" cy="44" r="30" fill="currentColor" opacity="0.34" />
      <circle cx="108" cy="34" r="5" fill="#3a1608" opacity="0.55" />
      <circle cx="126" cy="40" r="4" fill="#3a1608" opacity="0.45" />
      <circle cx="116" cy="54" r="4.5" fill="#3a1608" opacity="0.5" />
    </SkinSvg>
  ),
  wheel: (
    <SkinSvg>
      <circle cx="118" cy="44" r="30" fill="none" stroke="currentColor" strokeWidth="4" opacity="0.4" />
      <circle cx="118" cy="44" r="8" fill="currentColor" opacity="0.55" />
      <path d="M118 14v20M118 54v20M88 44h20M128 44h20M97 23l14 14M125 51l14 14M97 65l14-14M125 37l14-14" stroke="currentColor" strokeWidth="3" opacity="0.35" />
    </SkinSvg>
  ),
  felt: (
    <SkinSvg>
      <rect x="92" y="20" width="48" height="48" rx="4" fill="currentColor" opacity="0.18" />
      <circle cx="106" cy="34" r="4" fill="#f3efe6" opacity="0.7" />
      <circle cx="126" cy="34" r="4" fill="#f3efe6" opacity="0.7" />
      <circle cx="116" cy="44" r="4" fill="#f3efe6" opacity="0.7" />
      <circle cx="106" cy="54" r="4" fill="#f3efe6" opacity="0.7" />
      <circle cx="126" cy="54" r="4" fill="#f3efe6" opacity="0.7" />
    </SkinSvg>
  ),
  duel: (
    <SkinSvg>
      <path d="M86 62l52-40" stroke="currentColor" strokeWidth="5" opacity="0.45" />
      <path d="M90 22l48 40" stroke="currentColor" strokeWidth="5" opacity="0.28" />
      <circle cx="86" cy="62" r="6" fill="currentColor" opacity="0.5" />
      <circle cx="138" cy="62" r="6" fill="currentColor" opacity="0.35" />
    </SkinSvg>
  ),
  coin: (
    <SkinSvg>
      <circle cx="118" cy="44" r="30" fill="currentColor" opacity="0.28" />
      <circle cx="118" cy="44" r="20" fill="none" stroke="currentColor" strokeWidth="3" opacity="0.5" />
      <path d="M118 30v28M110 38h16" stroke="currentColor" strokeWidth="3" opacity="0.55" />
    </SkinSvg>
  ),
  steel: (
    <SkinSvg>
      <path d="M100 22l28 28-10 10-28-28z" fill="currentColor" opacity="0.32" />
      <path d="M136 22l-28 28 10 10 28-28z" fill="currentColor" opacity="0.2" />
      <circle cx="118" cy="60" r="6" fill="currentColor" opacity="0.45" />
    </SkinSvg>
  ),
  hazard: (
    <SkinSvg>
      <path d="M118 16l32 56H86z" fill="currentColor" opacity="0.3" />
      <rect x="114" y="34" width="8" height="20" fill="#1a0808" opacity="0.7" />
      <circle cx="118" cy="62" r="4" fill="#1a0808" opacity="0.7" />
    </SkinSvg>
  ),
  grid: (
    <SkinSvg>
      <path d="M96 22v48M132 22v48M88 34h52M88 58h52" stroke="currentColor" strokeWidth="3" opacity="0.35" />
      <path d="M100 26l12 12M112 26l-12 12" stroke="currentColor" strokeWidth="3" opacity="0.5" />
      <circle cx="124" cy="46" r="8" fill="none" stroke="currentColor" strokeWidth="3" opacity="0.4" />
    </SkinSvg>
  ),
  clover: (
    <SkinSvg>
      <circle cx="108" cy="40" r="14" fill="currentColor" opacity="0.34" />
      <circle cx="128" cy="40" r="14" fill="currentColor" opacity="0.34" />
      <circle cx="118" cy="26" r="14" fill="currentColor" opacity="0.34" />
      <path d="M118 40v32" stroke="currentColor" strokeWidth="4" opacity="0.35" />
    </SkinSvg>
  ),
  jungle: (
    <SkinSvg>
      <path d="M136 18c-28 8-40 28-40 52 22-8 38-24 44-46z" fill="currentColor" opacity="0.32" />
      <path d="M108 28c-8 16-8 32 2 46" fill="none" stroke="currentColor" strokeWidth="3" opacity="0.28" />
    </SkinSvg>
  ),
  rose: (
    <SkinSvg>
      <circle cx="118" cy="40" r="12" fill="currentColor" opacity="0.5" />
      <circle cx="104" cy="48" r="12" fill="currentColor" opacity="0.28" />
      <circle cx="132" cy="48" r="12" fill="currentColor" opacity="0.28" />
      <circle cx="118" cy="56" r="12" fill="currentColor" opacity="0.22" />
    </SkinSvg>
  ),
  blast: (
    <SkinSvg>
      <circle cx="118" cy="44" r="10" fill="currentColor" opacity="0.7" />
      <path d="M118 12v18M118 58v18M86 44h18M132 44h18M96 22l12 12M128 54l12 12M96 66l12-12M128 34l12-12" stroke="currentColor" strokeWidth="4" opacity="0.4" />
    </SkinSvg>
  ),
  terminal: (
    <SkinSvg>
      <path d="M96 58l10-28 10 16 10-22 10 34" fill="none" stroke="currentColor" strokeWidth="4" opacity="0.45" />
      <path d="M96 64h40" stroke="currentColor" strokeWidth="3" opacity="0.25" />
    </SkinSvg>
  ),
  billiard: (
    <SkinSvg>
      <circle cx="118" cy="44" r="28" fill="#111" opacity="0.72" />
      <circle cx="118" cy="44" r="12" fill="#f2f2f2" opacity="0.85" />
      <text x="118" y="49" textAnchor="middle" fontSize="14" fill="#111" fontWeight="700">8</text>
    </SkinSvg>
  ),
  neon: (
    <SkinSvg>
      <path d="M98 18v52" stroke="currentColor" strokeWidth="5" opacity="0.55" />
      <path d="M118 22v48" stroke="#ff4d6d" strokeWidth="5" opacity="0.4" />
      <path d="M138 18v52" stroke="currentColor" strokeWidth="5" opacity="0.28" />
    </SkinSvg>
  ),
  court: (
    <SkinSvg>
      <circle cx="118" cy="44" r="26" fill="currentColor" opacity="0.32" />
      <path d="M92 44h52M118 18v52" stroke="#3a2214" strokeWidth="3" opacity="0.45" />
    </SkinSvg>
  ),
  grass: (
    <SkinSvg>
      <circle cx="118" cy="44" r="26" fill="#f4f4f4" opacity="0.8" />
      <path d="M104 30c10 6 18 6 28 0M104 58c10-6 18-6 28 0M92 44h52" stroke="currentColor" strokeWidth="2.4" opacity="0.45" />
    </SkinSvg>
  ),
  alley: (
    <SkinSvg>
      <path d="M118 16l12 40H106z" fill="currentColor" opacity="0.36" />
      <circle cx="118" cy="62" r="8" fill="currentColor" opacity="0.4" />
    </SkinSvg>
  ),
  target: (
    <SkinSvg>
      <circle cx="118" cy="44" r="30" fill="none" stroke="currentColor" strokeWidth="6" opacity="0.22" />
      <circle cx="118" cy="44" r="18" fill="none" stroke="currentColor" strokeWidth="6" opacity="0.38" />
      <circle cx="118" cy="44" r="6" fill="currentColor" opacity="0.7" />
    </SkinSvg>
  ),
  dice: (
    <SkinSvg>
      <rect x="90" y="18" width="52" height="52" rx="4" fill="#f4f0ec" opacity="0.82" />
      <circle cx="104" cy="32" r="5" fill="#c62828" />
      <circle cx="128" cy="32" r="5" fill="#c62828" />
      <circle cx="116" cy="44" r="5" fill="#c62828" />
      <circle cx="104" cy="56" r="5" fill="#c62828" />
      <circle cx="128" cy="56" r="5" fill="#c62828" />
    </SkinSvg>
  ),
  roulette: (
    <SkinSvg>
      <circle cx="118" cy="44" r="30" fill="none" stroke="currentColor" strokeWidth="10" opacity="0.22" />
      <circle cx="118" cy="44" r="30" fill="none" stroke="#d4af37" strokeWidth="3" opacity="0.45" strokeDasharray="8 7" />
      <circle cx="118" cy="44" r="7" fill="#d4af37" opacity="0.7" />
    </SkinSvg>
  ),
  paper: (
    <SkinSvg>
      <rect x="94" y="16" width="44" height="56" rx="2" fill="currentColor" opacity="0.18" />
      <path d="M102 30h28M102 42h28M102 54h18" stroke="currentColor" strokeWidth="3" opacity="0.4" />
    </SkinSvg>
  ),
  brass: (
    <SkinSvg>
      <rect x="108" y="16" width="20" height="40" rx="2" fill="currentColor" opacity="0.4" />
      <circle cx="118" cy="64" r="12" fill="currentColor" opacity="0.32" />
    </SkinSvg>
  ),
  plain: (
    <SkinSvg>
      <rect x="94" y="22" width="44" height="44" rx="2" fill="currentColor" opacity="0.2" />
    </SkinSvg>
  ),
}

export default function GameSkin({ motif = 'plain' }) {
  return (
    <i className="gm-skin-art" aria-hidden="true">
      {MARKS[motif] || MARKS.plain}
    </i>
  )
}

export function themeOf(game) {
  return game?.theme || {
    accent: '#8a827c',
    accent2: '#d8cfc6',
    ink: '#141416',
    wash: 'rgba(255,255,255,.06)',
    motif: 'plain',
  }
}

export function themeVars(theme) {
  const t = theme || themeOf()
  return {
    '--gm-accent': t.accent,
    '--gm-accent2': t.accent2,
    '--gm-ink': t.ink,
    '--gm-wash': t.wash,
  }
}
