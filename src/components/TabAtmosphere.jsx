/**
 * Атмосфера вкладки + лёгкие «щупальца медузы» (без SVG-blur — дёшево по GPU).
 */
export default function TabAtmosphere({ variant = 'farm' }) {
  return (
    <div className={`tab-atmosphere tab-atmosphere--${variant}`} aria-hidden>
      <div className="tab-atmosphere-base" />
      <div className="tab-atmosphere-glow tab-atmosphere-glow-a" />
      <div className="tab-atmosphere-texture" />

      <svg className="tab-atmosphere-vines tab-jelly" viewBox="0 0 100 160" preserveAspectRatio="none">
        <defs>
          <linearGradient id="jellyCoreL" x1="0" y1="1" x2="0.2" y2="0">
            <stop offset="0%" stopColor="var(--jelly-core-a)" stopOpacity="0" />
            <stop offset="40%" stopColor="var(--jelly-core-a)" stopOpacity="0.75" />
            <stop offset="100%" stopColor="var(--jelly-core-b)" stopOpacity="0.9" />
          </linearGradient>
          <linearGradient id="jellyCoreR" x1="1" y1="1" x2="0.8" y2="0">
            <stop offset="0%" stopColor="var(--jelly-core-a)" stopOpacity="0" />
            <stop offset="40%" stopColor="var(--jelly-core-a)" stopOpacity="0.75" />
            <stop offset="100%" stopColor="var(--jelly-core-b)" stopOpacity="0.9" />
          </linearGradient>
        </defs>

        <g className="tab-vine tab-vine--l tab-jelly-arm tab-jelly-arm--l">
          <path className="tab-jelly-core" d="M2 152 C8 118, 1 86, 12 52 C18 28, 6 16, 14 0" fill="none" stroke="url(#jellyCoreL)" />
          <path className="tab-jelly-filament" d="M5 148 C14 116, 6 90, 18 64 C24 46, 12 30, 20 12" fill="none" />
          <circle className="tab-jelly-orb" cx="13" cy="48" r="1.05" />
          <circle className="tab-jelly-orb tab-jelly-orb--dim" cx="10" cy="108" r="0.8" />
        </g>

        <g className="tab-vine tab-vine--r tab-jelly-arm tab-jelly-arm--r">
          <path className="tab-jelly-core" d="M98 152 C92 118, 99 86, 88 52 C82 28, 94 16, 86 0" fill="none" stroke="url(#jellyCoreR)" />
          <path className="tab-jelly-filament" d="M95 148 C86 116, 94 90, 82 64 C76 46, 88 30, 80 12" fill="none" />
          <circle className="tab-jelly-orb" cx="87" cy="48" r="1.05" />
          <circle className="tab-jelly-orb tab-jelly-orb--dim" cx="90" cy="108" r="0.8" />
        </g>

        <g className="tab-vine tab-vine--floor tab-jelly-arm tab-jelly-arm--floor">
          <path className="tab-jelly-core tab-jelly-core--floor" d="M18 156 C40 150, 60 150, 82 156" fill="none" />
          <circle className="tab-jelly-orb tab-jelly-orb--dim" cx="50" cy="151" r="0.75" />
        </g>
      </svg>

      <div className="tab-atmosphere-vignette" />
    </div>
  )
}
