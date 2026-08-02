/**
 * Цветовой слой поверх лесного фона — у каждой вкладки свой характер
 * + тонкая отсылка на растительность (лианы по краям).
 */
export default function TabAtmosphere({ variant = 'farm' }) {
  return (
    <div className={`tab-atmosphere tab-atmosphere--${variant}`} aria-hidden>
      <div className="tab-atmosphere-base" />
      <div className="tab-atmosphere-glow tab-atmosphere-glow-a" />
      <div className="tab-atmosphere-glow tab-atmosphere-glow-b" />
      <div className="tab-atmosphere-texture" />
      <svg className="tab-atmosphere-vines" viewBox="0 0 100 160" preserveAspectRatio="none">
        <g className="tab-vine tab-vine--l" fill="none" strokeLinecap="round">
          <path className="tab-vine-stem" d="M2 140 C8 110, 4 80, 12 52 C18 30, 10 16, 16 4" />
          <path className="tab-vine-leaf" d="M10 70 C14 62, 22 63, 22 70 C17 72, 13 73, 10 70Z" />
          <path className="tab-vine-leaf" d="M12 42 C16 34, 24 36, 23 43 C18 45, 14 45, 12 42Z" />
          <path className="tab-vine-leaf" d="M14 18 C18 11, 25 13, 24 20 C20 21, 16 21, 14 18Z" />
        </g>
        <g className="tab-vine tab-vine--r" fill="none" strokeLinecap="round">
          <path className="tab-vine-stem" d="M98 140 C92 110, 96 80, 88 52 C82 30, 90 16, 84 4" />
          <path className="tab-vine-leaf" d="M90 70 C86 62, 78 63, 78 70 C83 72, 87 73, 90 70Z" />
          <path className="tab-vine-leaf" d="M88 42 C84 34, 76 36, 77 43 C82 45, 86 45, 88 42Z" />
          <path className="tab-vine-leaf" d="M86 18 C82 11, 75 13, 76 20 C80 21, 84 21, 86 18Z" />
        </g>
        <g className="tab-vine tab-vine--floor" fill="none">
          <path className="tab-vine-stem tab-vine-stem--floor" d="M18 156 C40 150, 60 150, 82 156" />
        </g>
      </svg>
      <div className="tab-atmosphere-vignette" />
    </div>
  )
}
