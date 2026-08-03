/**
 * Атмосфера вкладки + биолюминесцентные «щупальца медузы» по краям.
 */
export default function TabAtmosphere({ variant = 'farm' }) {
  return (
    <div className={`tab-atmosphere tab-atmosphere--${variant}`} aria-hidden>
      <div className="tab-atmosphere-base" />
      <div className="tab-atmosphere-glow tab-atmosphere-glow-a" />
      <div className="tab-atmosphere-glow tab-atmosphere-glow-b" />
      <div className="tab-atmosphere-texture" />

      <svg className="tab-atmosphere-vines tab-jelly" viewBox="0 0 100 160" preserveAspectRatio="none">
        <defs>
          <linearGradient id="jellyCoreL" x1="0" y1="1" x2="0.2" y2="0">
            <stop offset="0%" stopColor="var(--jelly-core-a)" stopOpacity="0" />
            <stop offset="35%" stopColor="var(--jelly-core-a)" stopOpacity="0.85" />
            <stop offset="100%" stopColor="var(--jelly-core-b)" stopOpacity="0.95" />
          </linearGradient>
          <linearGradient id="jellyCoreR" x1="1" y1="1" x2="0.8" y2="0">
            <stop offset="0%" stopColor="var(--jelly-core-a)" stopOpacity="0" />
            <stop offset="35%" stopColor="var(--jelly-core-a)" stopOpacity="0.85" />
            <stop offset="100%" stopColor="var(--jelly-core-b)" stopOpacity="0.95" />
          </linearGradient>
          <linearGradient id="jellyGlowL" x1="0" y1="1" x2="0.15" y2="0">
            <stop offset="0%" stopColor="var(--jelly-glow)" stopOpacity="0" />
            <stop offset="50%" stopColor="var(--jelly-glow)" stopOpacity="0.45" />
            <stop offset="100%" stopColor="var(--jelly-glow)" stopOpacity="0.2" />
          </linearGradient>
          <linearGradient id="jellyGlowR" x1="1" y1="1" x2="0.85" y2="0">
            <stop offset="0%" stopColor="var(--jelly-glow)" stopOpacity="0" />
            <stop offset="50%" stopColor="var(--jelly-glow)" stopOpacity="0.45" />
            <stop offset="100%" stopColor="var(--jelly-glow)" stopOpacity="0.2" />
          </linearGradient>
          <filter id="jellyBlur" x="-40%" y="-20%" width="180%" height="140%">
            <feGaussianBlur stdDeviation="1.1" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Left tentacles */}
        <g className="tab-vine tab-vine--l tab-jelly-arm tab-jelly-arm--l">
          <path className="tab-jelly-halo" d="M2 152 C8 118, 1 86, 12 52 C18 28, 6 16, 14 0" fill="none" stroke="url(#jellyGlowL)" />
          <path className="tab-jelly-core" d="M2 152 C8 118, 1 86, 12 52 C18 28, 6 16, 14 0" fill="none" stroke="url(#jellyCoreL)" />
          <path className="tab-jelly-filament" d="M5 148 C14 116, 6 90, 18 64 C24 46, 12 30, 20 12" fill="none" />
          <path className="tab-jelly-filament tab-jelly-filament--soft" d="M1 140 C10 112, 4 84, 14 58" fill="none" />
          <path className="tab-jelly-curl" d="M11 72 C18 66, 24 74, 20 82 C17 88, 26 90, 28 82" fill="none" />
          <circle className="tab-jelly-orb" cx="13" cy="48" r="1.15" />
          <circle className="tab-jelly-orb tab-jelly-orb--dim" cx="18" cy="78" r="0.8" />
          <circle className="tab-jelly-orb" cx="10" cy="108" r="0.95" />
          <circle className="tab-jelly-orb tab-jelly-orb--dim" cx="16" cy="28" r="0.7" />
        </g>

        {/* Right tentacles */}
        <g className="tab-vine tab-vine--r tab-jelly-arm tab-jelly-arm--r">
          <path className="tab-jelly-halo" d="M98 152 C92 118, 99 86, 88 52 C82 28, 94 16, 86 0" fill="none" stroke="url(#jellyGlowR)" />
          <path className="tab-jelly-core" d="M98 152 C92 118, 99 86, 88 52 C82 28, 94 16, 86 0" fill="none" stroke="url(#jellyCoreR)" />
          <path className="tab-jelly-filament" d="M95 148 C86 116, 94 90, 82 64 C76 46, 88 30, 80 12" fill="none" />
          <path className="tab-jelly-filament tab-jelly-filament--soft" d="M99 140 C90 112, 96 84, 86 58" fill="none" />
          <path className="tab-jelly-curl" d="M89 72 C82 66, 76 74, 80 82 C83 88, 74 90, 72 82" fill="none" />
          <circle className="tab-jelly-orb" cx="87" cy="48" r="1.15" />
          <circle className="tab-jelly-orb tab-jelly-orb--dim" cx="82" cy="78" r="0.8" />
          <circle className="tab-jelly-orb" cx="90" cy="108" r="0.95" />
          <circle className="tab-jelly-orb tab-jelly-orb--dim" cx="84" cy="28" r="0.7" />
        </g>

        {/* Bottom flowing tendrils */}
        <g className="tab-vine tab-vine--floor tab-jelly-arm tab-jelly-arm--floor">
          <path className="tab-jelly-halo tab-jelly-halo--floor" d="M12 157 C34 148, 66 148, 88 157" fill="none" />
          <path className="tab-jelly-core tab-jelly-core--floor" d="M14 156 C36 149, 64 149, 86 156" fill="none" />
          <path className="tab-jelly-filament tab-jelly-filament--soft" d="M22 155 C40 150, 60 150, 78 155" fill="none" />
          <circle className="tab-jelly-orb tab-jelly-orb--dim" cx="30" cy="152" r="0.75" />
          <circle className="tab-jelly-orb" cx="50" cy="150.5" r="0.9" />
          <circle className="tab-jelly-orb tab-jelly-orb--dim" cx="70" cy="152" r="0.75" />
        </g>
      </svg>

      <div className="tab-atmosphere-vignette" />
      <div className="tab-atmosphere-dust" />
    </div>
  )
}
