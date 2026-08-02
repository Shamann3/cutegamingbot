/**
 * Поле грядки: слои почвы, борозды, лианы, крона, споры.
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
      <div className="soil-field-furrows" />
      <div className="soil-field-moss" />
      <div className="soil-field-mist" />
      <div className="soil-field-canopy" />

      <svg className="soil-field-vines" viewBox="0 0 160 112" preserveAspectRatio="none">
        <g className="soil-vine soil-vine--tl" fill="none" strokeLinecap="round">
          <path className="soil-vine-stem" d="M2 34 C16 24, 24 8, 44 4" />
          <path className="soil-vine-stem soil-vine-stem--thin" d="M8 40 C20 34, 28 18, 40 12" />
          <path className="soil-vine-leaf" d="M12 28 C18 20, 28 20, 30 26 C24 28, 18 30, 12 28Z" />
          <path className="soil-vine-leaf" d="M24 14 C30 6, 40 8, 41 14 C35 16, 29 17, 24 14Z" />
          <path className="soil-vine-leaf" d="M34 8 C38 2, 46 3, 47 8 C42 10, 38 11, 34 8Z" />
        </g>
        <g className="soil-vine soil-vine--tr" fill="none" strokeLinecap="round">
          <path className="soil-vine-stem" d="M158 34 C144 24, 136 8, 116 4" />
          <path className="soil-vine-stem soil-vine-stem--thin" d="M152 40 C140 34, 132 18, 120 12" />
          <path className="soil-vine-leaf" d="M148 28 C142 20, 132 20, 130 26 C136 28, 142 30, 148 28Z" />
          <path className="soil-vine-leaf" d="M136 14 C130 6, 120 8, 119 14 C125 16, 131 17, 136 14Z" />
          <path className="soil-vine-leaf" d="M126 8 C122 2, 114 3, 113 8 C118 10, 122 11, 126 8Z" />
        </g>
        <g className="soil-vine soil-vine--bl" fill="none" strokeLinecap="round">
          <path className="soil-vine-stem" d="M4 102 C22 106, 38 108, 54 104" />
          <path className="soil-vine-leaf" d="M16 102 C22 110, 32 110, 34 104 C28 102, 22 100, 16 102Z" />
          <path className="soil-vine-leaf" d="M34 104 C40 112, 50 110, 52 104 C46 102, 40 101, 34 104Z" />
        </g>
        <g className="soil-vine soil-vine--br" fill="none" strokeLinecap="round">
          <path className="soil-vine-stem" d="M156 102 C138 106, 122 108, 106 104" />
          <path className="soil-vine-leaf" d="M144 102 C138 110, 128 110, 126 104 C132 102, 138 100, 144 102Z" />
          <path className="soil-vine-leaf" d="M126 104 C120 112, 110 110, 108 104 C114 102, 120 101, 126 104Z" />
        </g>
      </svg>

      <div className="soil-field-grass">
        {Array.from({ length: 12 }, (_, i) => (
          <span key={i} className={`soil-blade soil-blade--${i + 1}`} />
        ))}
      </div>

      <div className="soil-field-spores">
        {Array.from({ length: 8 }, (_, i) => (
          <span key={i} className={`soil-spore soil-spore--${i + 1}`} />
        ))}
      </div>

      <div className="soil-field-rim" />

      {ready && <div className="soil-field-ready-glow" />}
      {moist && !dry && <div className="soil-field-dew" />}
    </div>
  )
}
