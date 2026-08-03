/**
 * Атмосфера вкладки + реалистичные плющевые края.
 */
export default function TabAtmosphere({ variant = 'farm' }) {
  return (
    <div className={`tab-atmosphere tab-atmosphere--${variant}`} aria-hidden>
      <div className="tab-atmosphere-base" />
      <div className="tab-atmosphere-glow tab-atmosphere-glow-a" />
      <div className="tab-atmosphere-glow tab-atmosphere-glow-b" />
      <div className="tab-atmosphere-texture" />
      <svg className="tab-atmosphere-vines" viewBox="0 0 100 160" preserveAspectRatio="none">
        <defs>
          <linearGradient id="tabLeafGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#7ef0b4" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#1f7a4d" stopOpacity="0.75" />
          </linearGradient>
          <linearGradient id="tabStemGrad" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#14532d" />
            <stop offset="100%" stopColor="#3dd68c" />
          </linearGradient>
        </defs>

        <g className="tab-vine tab-vine--l">
          <path
            className="tab-vine-stem"
            d="M1.5 150 C6 118, 3 88, 11 58 C17 34, 8 18, 14 2"
            fill="none"
            stroke="url(#tabStemGrad)"
          />
          <path
            className="tab-vine-stem tab-vine-stem--soft"
            d="M4 148 C10 120, 8 92, 16 66"
            fill="none"
          />
          <path className="tab-vine-tendril" d="M10 78 C16 74, 20 80, 17 86 C15 90, 21 92, 24 86" fill="none" />
          <path className="tab-vine-leaf" d="M8 96 C12 86, 22 86, 22 96 C16 98, 12 98, 8 96Z" fill="url(#tabLeafGrad)" />
          <path className="tab-vine-leaf" d="M10 68 C14 58, 24 60, 23 70 C18 70, 12 70, 10 68Z" fill="url(#tabLeafGrad)" />
          <path className="tab-vine-leaf" d="M12 42 C16 32, 26 34, 24 44 C20 44, 14 44, 12 42Z" fill="url(#tabLeafGrad)" />
          <path className="tab-vine-leaf" d="M13 18 C17 10, 25 12, 24 20 C20 20, 15 20, 13 18Z" fill="url(#tabLeafGrad)" />
          <circle className="tab-vine-bud" cx="14" cy="54" r="0.9" />
        </g>

        <g className="tab-vine tab-vine--r">
          <path
            className="tab-vine-stem"
            d="M98.5 150 C94 118, 97 88, 89 58 C83 34, 92 18, 86 2"
            fill="none"
            stroke="url(#tabStemGrad)"
          />
          <path
            className="tab-vine-stem tab-vine-stem--soft"
            d="M96 148 C90 120, 92 92, 84 66"
            fill="none"
          />
          <path className="tab-vine-tendril" d="M90 78 C84 74, 80 80, 83 86 C85 90, 79 92, 76 86" fill="none" />
          <path className="tab-vine-leaf" d="M92 96 C88 86, 78 86, 78 96 C84 98, 88 98, 92 96Z" fill="url(#tabLeafGrad)" />
          <path className="tab-vine-leaf" d="M90 68 C86 58, 76 60, 77 70 C82 70, 88 70, 90 68Z" fill="url(#tabLeafGrad)" />
          <path className="tab-vine-leaf" d="M88 42 C84 32, 74 34, 76 44 C80 44, 86 44, 88 42Z" fill="url(#tabLeafGrad)" />
          <path className="tab-vine-leaf" d="M87 18 C83 10, 75 12, 76 20 C80 20, 85 20, 87 18Z" fill="url(#tabLeafGrad)" />
          <circle className="tab-vine-bud" cx="86" cy="54" r="0.9" />
        </g>

        <g className="tab-vine tab-vine--floor">
          <path
            className="tab-vine-stem tab-vine-stem--floor"
            d="M16 156 C38 149, 62 149, 84 156"
            fill="none"
          />
          <path className="tab-vine-leaf" d="M28 154 C30 148, 36 148, 36 154 C33 155, 30 155, 28 154Z" fill="url(#tabLeafGrad)" />
          <path className="tab-vine-leaf" d="M50 153 C52 147, 58 147, 58 153 C55 154, 52 154, 50 153Z" fill="url(#tabLeafGrad)" />
          <path className="tab-vine-leaf" d="M70 154 C72 148, 78 148, 78 154 C75 155, 72 155, 70 154Z" fill="url(#tabLeafGrad)" />
        </g>
      </svg>
      <div className="tab-atmosphere-vignette" />
      <div className="tab-atmosphere-dust" />
    </div>
  )
}
