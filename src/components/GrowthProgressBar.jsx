export default function GrowthProgressBar({ progress, label, labelTitle }) {
  const pct = Math.round(progress * 100)

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] font-bold text-emerald-200/90">
        <span>Рост</span>
        <span className="tabular-nums">{pct}%</span>
      </div>
      <div className="h-2.5 rounded-full bg-black/40 border border-emerald-500/30 overflow-hidden">
        <div
          className="growth-progress-fill h-full rounded-full bg-gradient-to-r from-emerald-700 via-emerald-400 to-lime-300 transition-all duration-300 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      {label && (
        <p
          className="text-center text-[10px] font-semibold text-emerald-100/75"
          title={labelTitle || undefined}
        >
          {label}
        </p>
      )}
    </div>
  )
}
