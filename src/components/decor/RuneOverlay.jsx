/** Светящиеся руны на грядке (как на мокапе). */
export default function RuneOverlay({ className = '' }) {
  return (
    <svg
      viewBox="0 0 120 80"
      className={`absolute inset-0 w-full h-full opacity-[0.22] pointer-events-none ${className}`}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
    >
      <g fill="none" stroke="#c9a84c" strokeWidth="1.2" opacity="0.8">
        <circle cx="30" cy="28" r="8" />
        <path d="M30 20 L30 36 M22 28 L38 28" />
        <path d="M60 40 L68 32 L76 40 L68 48 Z" />
        <circle cx="90" cy="24" r="6" />
        <path d="M90 18 L90 30 M84 24 L96 24" />
        <path d="M24 58 Q36 50 48 58 T72 58" />
        <path d="M82 52 L88 58 L82 64" />
      </g>
      <g fill="#d4af37" opacity="0.15">
        <circle cx="48" cy="22" r="2" />
        <circle cx="72" cy="44" r="1.5" />
        <circle cx="36" cy="48" r="1.5" />
      </g>
    </svg>
  )
}
