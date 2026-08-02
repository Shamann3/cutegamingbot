/**
 * Аналитика профиля в духе admin AnalyticsSection:
 * SVG-чарты + ранги, палитра black / gold / green.
 */

const GOLD = '#e8c56a'
const GREEN = '#3dd68c'

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('ru-RU')
}

function rankPercentile(rank, total) {
  if (!rank || !total || total < 1) return 0
  return Math.max(0, Math.min(100, Math.round((1 - (rank - 1) / total) * 100)))
}

function BarChart({ items }) {
  const max = Math.max(...items.map((i) => i.value), 1)
  return (
    <div className="pa-bars" role="img" aria-label="Активность">
      {items.map((item) => {
        const h = Math.max(8, Math.round((item.value / max) * 100))
        return (
          <div key={item.id} className="pa-bar-col">
            <div className="pa-bar-track">
              <div
                className="pa-bar-fill"
                style={{
                  height: `${h}%`,
                  background: item.color,
                  boxShadow: `0 0 12px ${item.color}55`,
                }}
              />
            </div>
            <span className="pa-bar-value">{fmt(item.value)}</span>
            <span className="pa-bar-label">{item.label}</span>
          </div>
        )
      })}
    </div>
  )
}

function RingStat({ label, value, max = 100, color = GOLD, sub }) {
  const pct = Math.max(0, Math.min(100, max > 0 ? (value / max) * 100 : 0))
  const r = 34
  const c = 2 * Math.PI * r
  const offset = c - (pct / 100) * c
  return (
    <div className="pa-ring">
      <svg viewBox="0 0 84 84" className="pa-ring-svg" aria-hidden>
        <circle cx="42" cy="42" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
        <circle
          cx="42"
          cy="42"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          transform="rotate(-90 42 42)"
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
        <text x="42" y="46" textAnchor="middle" className="pa-ring-text">
          {Math.round(pct)}%
        </text>
      </svg>
      <p className="pa-ring-label">{label}</p>
      {sub ? <p className="pa-ring-sub">{sub}</p> : null}
    </div>
  )
}

function MixChart({ harvest, craft, sales }) {
  const total = Math.max(harvest + craft + sales, 1)
  const parts = [
    { id: 'h', label: 'Урожай', value: harvest, color: GREEN },
    { id: 'c', label: 'Крафт', value: craft, color: GOLD },
    { id: 's', label: 'Биржа', value: sales, color: '#8fd9b0' },
  ]
  let cursor = 0
  const segments = parts.map((p) => {
    const start = cursor
    const share = (p.value / total) * 100
    cursor += share
    return { ...p, start, share }
  })

  return (
    <div className="pa-mix">
      <div className="pa-mix-track" aria-hidden>
        {segments.map((s) => (
          <span
            key={s.id}
            className="pa-mix-seg"
            style={{
              width: `${Math.max(s.share, s.value > 0 ? 4 : 0)}%`,
              background: s.color,
              boxShadow: s.value > 0 ? `0 0 10px ${s.color}44` : 'none',
            }}
          />
        ))}
      </div>
      <div className="pa-mix-legend">
        {parts.map((p) => (
          <span key={p.id} className="pa-mix-item">
            <i style={{ background: p.color }} aria-hidden />
            {p.label}
            <strong>{fmt(p.value)}</strong>
          </span>
        ))}
      </div>
    </div>
  )
}

export default function ProfileAnalytics({ profile, leaderboard }) {
  const harvest = Number(profile?.harvestCount || 0)
  const craft = Number(profile?.craftCount || 0)
  const sold = Number(profile?.marketItemsSold || 0)
  const deals = Number(profile?.marketSalesCount || 0)
  const days = Number(profile?.daysInGame || 0)
  const totalPlayers = Number(leaderboard?.total || 0)

  const harvestRank = Number(leaderboard?.myRank?.harvests || 0)
  const salesRank = Number(leaderboard?.myRank?.sales || 0)
  const balanceRank = Number(leaderboard?.myRank?.balance || 0)

  const bars = [
    { id: 'harvest', label: 'Урожай', value: harvest, color: GREEN },
    { id: 'craft', label: 'Крафт', value: craft, color: GOLD },
    { id: 'sold', label: 'Продано', value: sold, color: '#6ee7b7' },
    { id: 'deals', label: 'Сделки', value: deals, color: '#c4a35a' },
  ]

  return (
    <section className="pa-root" aria-label="Аналитика игрока">
      <header className="pa-header">
        <p className="pa-eyebrow">Аналитика</p>
        <h2 className="pa-title">Твой прогресс</h2>
        <p className="pa-sub">
          {days > 0 ? `${days} дн. в игре` : 'Первый день'}
          {totalPlayers > 0 ? ` · среди ${fmt(totalPlayers)} игроков` : ''}
        </p>
      </header>

      <div className="pa-card pa-card--bars">
        <div className="pa-card-head">
          <span>Активность</span>
          <span className="pa-card-hint">урожай · крафт · биржа</span>
        </div>
        <BarChart items={bars} />
      </div>

      <div className="pa-card">
        <div className="pa-card-head">
          <span>Состав прогресса</span>
        </div>
        <MixChart harvest={harvest} craft={craft} sales={sold} />
      </div>

      <div className="pa-rings">
        <RingStat
          label="Урожай"
          value={rankPercentile(harvestRank, totalPlayers)}
          color={GREEN}
          sub={harvestRank > 0 ? `топ #${fmt(harvestRank)}` : 'нет ранга'}
        />
        <RingStat
          label="Биржа"
          value={rankPercentile(salesRank, totalPlayers)}
          color={GOLD}
          sub={salesRank > 0 ? `топ #${fmt(salesRank)}` : 'нет ранга'}
        />
        <RingStat
          label="Баланс"
          value={rankPercentile(balanceRank, totalPlayers)}
          color="#9fd9b4"
          sub={balanceRank > 0 ? `топ #${fmt(balanceRank)}` : 'нет ранга'}
        />
      </div>

      <div className="pa-kpi-row">
        <div className="pa-kpi">
          <span className="pa-kpi-label">КУТ</span>
          <strong className="pa-kpi-value">{fmt(profile?.balance)}</strong>
        </div>
        <div className="pa-kpi">
          <span className="pa-kpi-label">Сборы</span>
          <strong className="pa-kpi-value" style={{ color: GREEN }}>{fmt(harvest)}</strong>
        </div>
        <div className="pa-kpi">
          <span className="pa-kpi-label">Сделки</span>
          <strong className="pa-kpi-value" style={{ color: GOLD }}>{fmt(deals)}</strong>
        </div>
      </div>
    </section>
  )
}
