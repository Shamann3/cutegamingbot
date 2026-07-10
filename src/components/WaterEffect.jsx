export default function WaterEffect({ active }) {
  if (!active) return null

  const drops = [
    { left: '28%', delay: '0ms' },
    { left: '42%', delay: '120ms' },
    { left: '56%', delay: '60ms' },
    { left: '70%', delay: '180ms' },
  ]

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden z-20" aria-hidden>
      {drops.map((d, i) => (
        <span
          key={i}
          className="absolute top-2 w-2 h-3 rounded-full bg-sky-300/90 animate-water-drop shadow-sm"
          style={{ left: d.left, animationDelay: d.delay }}
        />
      ))}
      <div className="absolute inset-0 bg-sky-400/25 animate-water-splash" />
    </div>
  )
}
