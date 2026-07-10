export default function GrowthProgressBar({ progress, label }) {
  const pct = Math.round(progress * 100)

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] font-bold text-amber-300/90">
        <span>Рост</span>
        <span className="tabular-nums">{pct}%</span>
      </div>
      <div className="h-2.5 rounded-full bg-black/40 border border-amber-600/30 overflow-hidden">
        <div
          className="growth-progress-fill h-full rounded-full bg-gradient-to-r from-amber-500 via-amber-400 to-yellow-300 transition-all duration-300 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      {label && (
        <p className="text-center text-[10px] font-semibold text-amber-200/80 tabular-nums">
          {label}
        </p>
      )}
    </div>
  )
}
