/**
 * Цветовой слой поверх лесного фона - у каждой вкладки свой характер.
 */
export default function TabAtmosphere({ variant = 'farm' }) {
  return (
    <div className={`tab-atmosphere tab-atmosphere--${variant}`} aria-hidden>
      <div className="tab-atmosphere-base" />
      <div className="tab-atmosphere-glow tab-atmosphere-glow-a" />
      <div className="tab-atmosphere-glow tab-atmosphere-glow-b" />
      <div className="tab-atmosphere-texture" />
      <div className="tab-atmosphere-vignette" />
    </div>
  )
}
