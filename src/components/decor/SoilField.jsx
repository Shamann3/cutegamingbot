/**
 * Завораживающее поле грядки: почва, мох, лианы, споры света.
 * status: empty | growing | ready | dry
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
      <div className="soil-field-moss" />
      <div className="soil-field-mist" />

      {/* Угловая растительность */}
      <svg className="soil-field-vines" viewBox="0 0 160 112" preserveAspectRatio="none">
        <g className="soil-vine soil-vine--tl" fill="none" strokeLinecap="round">
          <path className="soil-vine-stem" d="M4 28 C18 22, 22 10, 36 6" />
          <path className="soil-vine-leaf" d="M14 22 C18 16, 24 16, 26 20 C22 22, 18 24, 14 22Z" />
          <path className="soil-vine-leaf" d="M24 12 C28 7, 34 8, 35 12 C31 14, 27 15, 24 12Z" />
        </g>
        <g className="soil-vine soil-vine--tr" fill="none" strokeLinecap="round">
          <path className="soil-vine-stem" d="M156 30 C142 22, 138 10, 124 6" />
          <path className="soil-vine-leaf" d="M146 22 C142 16, 136 16, 134 20 C138 22, 142 24, 146 22Z" />
          <path className="soil-vine-leaf" d="M136 12 C132 7, 126 8, 125 12 C129 14, 133 15, 136 12Z" />
        </g>
        <g className="soil-vine soil-vine--bl" fill="none" strokeLinecap="round">
          <path className="soil-vine-stem" d="M6 96 C20 100, 28 104, 42 102" />
          <path className="soil-vine-leaf" d="M18 98 C22 104, 28 104, 30 100 C26 98, 22 97, 18 98Z" />
        </g>
        <g className="soil-vine soil-vine--br" fill="none" strokeLinecap="round">
          <path className="soil-vine-stem" d="M154 96 C140 100, 132 104, 118 102" />
          <path className="soil-vine-leaf" d="M142 98 C138 104, 132 104, 130 100 C134 98, 138 97, 142 98Z" />
        </g>
      </svg>

      {/* Травинки у низа */}
      <div className="soil-field-grass">
        {Array.from({ length: 9 }, (_, i) => (
          <span key={i} className={`soil-blade soil-blade--${i + 1}`} />
        ))}
      </div>

      {/* Золотые споры / пыльца */}
      <div className="soil-field-spores">
        <span className="soil-spore soil-spore--1" />
        <span className="soil-spore soil-spore--2" />
        <span className="soil-spore soil-spore--3" />
        <span className="soil-spore soil-spore--4" />
        <span className="soil-spore soil-spore--5" />
      </div>

      {/* Тонкая золотая руна — едва заметный орнамент */}
      <svg className="soil-field-runes" viewBox="0 0 120 80" preserveAspectRatio="xMidYMid slice">
        <g fill="none" stroke="currentColor" strokeWidth="1">
          <circle cx="28" cy="26" r="6" />
          <path d="M28 20 L28 32 M22 26 L34 26" />
          <path d="M62 38 L68 32 L74 38 L68 44 Z" />
          <path d="M22 56 Q36 50 50 56 T78 56" />
        </g>
      </svg>

      {ready && <div className="soil-field-ready-glow" />}
    </div>
  )
}
