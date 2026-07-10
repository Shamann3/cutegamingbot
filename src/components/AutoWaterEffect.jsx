const BURST_DROPS = [
  { left: '18%', delay: '0ms', size: '0.72rem' },
  { left: '32%', delay: '140ms', size: '0.65rem' },
  { left: '48%', delay: '70ms', size: '0.8rem' },
  { left: '62%', delay: '210ms', size: '0.68rem' },
  { left: '76%', delay: '120ms', size: '0.74rem' },
  { left: '40%', delay: '280ms', size: '0.66rem' },
  { left: '55%', delay: '350ms', size: '0.7rem' },
]

const IDLE_DROPS = [
  { left: '22%', delay: '0s', size: '0.62rem' },
  { left: '38%', delay: '0.8s', size: '0.58rem' },
  { left: '54%', delay: '1.6s', size: '0.64rem' },
  { left: '68%', delay: '2.2s', size: '0.6rem' },
]

export default function AutoWaterEffect({ mode = 'burst' }) {
  if (mode === 'idle') {
    return (
      <div className="farm-autowater-idle absolute inset-0 pointer-events-none overflow-hidden z-[15]" aria-hidden>
        {IDLE_DROPS.map((drop, index) => (
          <span
            key={index}
            className="farm-autowater-drop-idle"
            style={{
              left: drop.left,
              fontSize: drop.size,
              animationDelay: drop.delay,
            }}
          >
            💧
          </span>
        ))}
        <div className="farm-autowater-idle-glow" />
      </div>
    )
  }

  return (
    <div className="farm-autowater-effect absolute inset-0 pointer-events-none overflow-hidden z-20" aria-hidden>
      {BURST_DROPS.map((drop, index) => (
        <span
          key={index}
          className="farm-autowater-drop"
          style={{
            left: drop.left,
            fontSize: drop.size,
            animationDelay: drop.delay,
          }}
        >
          💧
        </span>
      ))}
      <div className="farm-autowater-mist" />
    </div>
  )
}
