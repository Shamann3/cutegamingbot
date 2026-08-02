/**
 * Элитная полезная сводка профиля — black / gold / green + растительность.
 */

const GOLD = '#e8c56a'
const GREEN = '#3dd68c'

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('ru-RU')
}

function bestRank(ranks) {
  const valid = ranks.filter((r) => r.value > 0)
  if (!valid.length) return null
  return valid.reduce((a, b) => (a.value < b.value ? a : b))
}

function nextTip({ harvest, sold, deals, balance, best }) {
  if (harvest === 0) {
    return {
      title: 'Посади первый саженец',
      body: 'Пустая грядка → купить саженец → посадить. Это главный цикл фермы.',
      tone: 'green',
      icon: '🌱',
    }
  }
  if (sold === 0 && harvest > 0) {
    return {
      title: 'Продай урожай на бирже',
      body: 'Собранные предметы дают КУТ. Открой «Торговля» и выставь лот.',
      tone: 'gold',
      icon: '💱',
    }
  }
  if (best && best.value > 20) {
    return {
      title: `Поднимись в «${best.label}»`,
      body: `Сейчас #${fmt(best.value)}. Ещё несколько циклов — и место заметно вырастет.`,
      tone: 'gold',
      icon: '🏆',
    }
  }
  if (balance < 50 && harvest > 0) {
    return {
      title: 'Усиль баланс',
      body: 'Собери готовые грядки и продай лишнее — КУТ нужны для саженцев и воды.',
      tone: 'green',
      icon: '💧',
    }
  }
  if (deals > 0) {
    return {
      title: 'Держи ритм сезона',
      body: 'Посадил → полил → собрал → продал. Этот цикл и делает ферму прибыльной.',
      tone: 'green',
      icon: '🌿',
    }
  }
  return {
    title: 'Проверь грядки',
    body: 'Полей сухие, собери готовые, посади новые саженцы — прогресс уже в поле.',
    tone: 'green',
    icon: '🌾',
  }
}

export default function ProfileAnalytics({ profile, leaderboard }) {
  const harvest = Number(profile?.harvestCount || 0)
  const sold = Number(profile?.marketItemsSold || 0)
  const deals = Number(profile?.marketSalesCount || 0)
  const balance = Number(profile?.balance || 0)
  const days = Number(profile?.daysInGame || 0)
  const totalPlayers = Number(leaderboard?.total || 0)

  const ranks = [
    { id: 'harvests', label: 'Урожай', value: Number(leaderboard?.myRank?.harvests || 0), color: GREEN },
    { id: 'sales', label: 'Биржа', value: Number(leaderboard?.myRank?.sales || 0), color: GOLD },
    { id: 'balance', label: 'Баланс', value: Number(leaderboard?.myRank?.balance || 0), color: '#9fd9b4' },
  ]
  const top = bestRank(ranks)
  const tip = nextTip({ harvest, sold, deals, balance, best: top })

  return (
    <section className="pa-root" aria-label="Сводка фермера">
      <header className="pa-header">
        <div className="pa-header-mark" aria-hidden>
          <span className="pa-header-leaf">🌿</span>
        </div>
        <div>
          <p className="pa-eyebrow">Сводка фермера</p>
          <h2 className="pa-title">Что важно сейчас</h2>
          <p className="pa-sub">
            {days > 0 ? `${days} дн. в игре` : 'Первый день'}
            {totalPlayers > 0 ? ` · ${fmt(totalPlayers)} игроков` : ''}
          </p>
        </div>
      </header>

      <div className="pa-kpi-row">
        <div className="pa-kpi pa-kpi--gold">
          <span className="pa-kpi-label">КУТ</span>
          <strong className="pa-kpi-value">{fmt(balance)}</strong>
        </div>
        <div className="pa-kpi pa-kpi--green">
          <span className="pa-kpi-label">Урожаи</span>
          <strong className="pa-kpi-value">{fmt(harvest)}</strong>
        </div>
        <div className="pa-kpi">
          <span className="pa-kpi-label">Продано</span>
          <strong className="pa-kpi-value" style={{ color: GOLD }}>{fmt(sold)}</strong>
        </div>
      </div>

      <div className={`pa-tip pa-tip--${tip.tone}`}>
        <span className="pa-tip-icon" aria-hidden>{tip.icon}</span>
        <div>
          <p className="pa-tip-title">{tip.title}</p>
          <p className="pa-tip-body">{tip.body}</p>
        </div>
      </div>

      {top ? (
        <div className="pa-rank-card">
          <div className="pa-rank-main">
            <span className="pa-rank-label">Лучший ранг</span>
            <strong className="pa-rank-value" style={{ color: top.color }}>
              #{fmt(top.value)}
            </strong>
            <span className="pa-rank-meta">{top.label}</span>
          </div>
          <ul className="pa-rank-list">
            {ranks.map((r) => (
              <li key={r.id}>
                <span>{r.label}</span>
                <strong style={{ color: r.value > 0 ? r.color : undefined }}>
                  {r.value > 0 ? `#${fmt(r.value)}` : '—'}
                </strong>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="pa-rank-card pa-rank-card--empty">
          <p className="pa-tip-title">Ранг появится после активности</p>
          <p className="pa-tip-body">Собери урожай или сделай сделку — и место в топе обновится.</p>
        </div>
      )}
    </section>
  )
}
