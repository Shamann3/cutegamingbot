/**
 * Живое поле грядки: почва, плющ, мох, папоротник, споры.
 */
export default function SoilField({
  status = 'growing',
  moist = false,
  dry = false,
  ready = false,
  className = '',
}) {
  return (
    <div
      className={[
        'soil-field',
        moist ? 'soil-field--moist' : '',
        dry ? 'soil-field--dry' : '',
        ready ? 'soil-field--ready' : '',
        status === 'empty' ? 'soil-field--empty' : '',
        className,
      ].filter(Boolean).join(' ')}
      aria-hidden
    >
      <div className="soil-field-earth" />
      <div className="soil-field-furrows" />
      <div className="soil-field-moss" />
      <div className="soil-field-mist" />
      <div className="soil-field-canopy" />

      <svg className="soil-field-vines" viewBox="0 0 160 112" preserveAspectRatio="none">
        <defs>
          <linearGradient id="sfLeaf" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#9af5c8" />
            <stop offset="55%" stopColor="#2f9e64" />
            <stop offset="100%" stopColor="#14532d" />
          </linearGradient>
          <linearGradient id="sfStem" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#0f3d28" />
            <stop offset="100%" stopColor="#3dd68c" />
          </linearGradient>
        </defs>

        <g className="soil-vine soil-vine--tl">
          <path className="soil-vine-stem" d="M1 38 C14 26, 22 10, 46 3" fill="none" stroke="url(#sfStem)" />
          <path className="soil-vine-stem soil-vine-stem--thin" d="M6 44 C18 34, 28 16, 42 10" fill="none" />
          <path className="soil-vine-tendril" d="M20 28 C28 24, 34 30, 30 36 C28 40, 36 42, 40 36" fill="none" />
          <path className="soil-vine-leaf" d="M10 30 C16 20, 28 18, 32 26 C26 28, 18 32, 10 30Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M22 16 C28 6, 42 6, 44 16 C36 18, 28 20, 22 16Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M34 8 C38 1, 48 2, 49 9 C44 11, 38 12, 34 8Z" fill="url(#sfLeaf)" />
          <circle className="soil-vine-bud" cx="26" cy="24" r="1.4" />
        </g>

        <g className="soil-vine soil-vine--tr">
          <path className="soil-vine-stem" d="M159 38 C146 26, 138 10, 114 3" fill="none" stroke="url(#sfStem)" />
          <path className="soil-vine-stem soil-vine-stem--thin" d="M154 44 C142 34, 132 16, 118 10" fill="none" />
          <path className="soil-vine-tendril" d="M140 28 C132 24, 126 30, 130 36 C132 40, 124 42, 120 36" fill="none" />
          <path className="soil-vine-leaf" d="M150 30 C144 20, 132 18, 128 26 C134 28, 142 32, 150 30Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M138 16 C132 6, 118 6, 116 16 C124 18, 132 20, 138 16Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M126 8 C122 1, 112 2, 111 9 C116 11, 122 12, 126 8Z" fill="url(#sfLeaf)" />
          <circle className="soil-vine-bud" cx="134" cy="24" r="1.4" />
        </g>

        <g className="soil-vine soil-vine--bl">
          <path className="soil-vine-stem" d="M2 104 C20 108, 40 110, 58 104" fill="none" stroke="url(#sfStem)" />
          <path className="soil-vine-leaf" d="M14 102 C20 112, 34 112, 36 104 C28 102, 20 100, 14 102Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M32 104 C38 114, 52 112, 54 104 C46 102, 38 100, 32 104Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M48 102 C52 110, 62 108, 64 102 C58 100, 52 99, 48 102Z" fill="url(#sfLeaf)" />
        </g>

        <g className="soil-vine soil-vine--br">
          <path className="soil-vine-stem" d="M158 104 C140 108, 120 110, 102 104" fill="none" stroke="url(#sfStem)" />
          <path className="soil-vine-leaf" d="M146 102 C140 112, 126 112, 124 104 C132 102, 140 100, 146 102Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M128 104 C122 114, 108 112, 106 104 C114 102, 122 100, 128 104Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M112 102 C108 110, 98 108, 96 102 C102 100, 108 99, 112 102Z" fill="url(#sfLeaf)" />
        </g>

        {/* Боковые «заросли» */}
        <g className="soil-vine soil-vine--side-l" opacity="0.75">
          <path className="soil-vine-stem soil-vine-stem--thin" d="M0 70 C10 62, 14 48, 22 42" fill="none" />
          <path className="soil-vine-leaf" d="M8 58 C12 50, 22 50, 22 58 C16 60, 12 60, 8 58Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M14 48 C18 40, 28 42, 26 50 C22 50, 16 50, 14 48Z" fill="url(#sfLeaf)" />
        </g>
        <g className="soil-vine soil-vine--side-r" opacity="0.75">
          <path className="soil-vine-stem soil-vine-stem--thin" d="M160 70 C150 62, 146 48, 138 42" fill="none" />
          <path className="soil-vine-leaf" d="M152 58 C148 50, 138 50, 138 58 C144 60, 148 60, 152 58Z" fill="url(#sfLeaf)" />
          <path className="soil-vine-leaf" d="M146 48 C142 40, 132 42, 134 50 C138 50, 144 50, 146 48Z" fill="url(#sfLeaf)" />
        </g>
      </svg>

      <div className="soil-field-grass">
        {Array.from({ length: 14 }, (_, i) => (
          <span key={i} className={`soil-blade soil-blade--${i + 1}`} />
        ))}
      </div>

      <div className="soil-field-spores">
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={`soil-spore soil-spore--${i + 1}`} />
        ))}
      </div>

      <div className="soil-field-rim" />
      <div className="soil-field-corner-glow soil-field-corner-glow--tl" />
      <div className="soil-field-corner-glow soil-field-corner-glow--tr" />

      {ready && <div className="soil-field-ready-glow" />}
      {moist && !dry && <div className="soil-field-dew" />}
    </div>
  )
}
