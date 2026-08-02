/**
 * Полезная аналитика профиля — только то, что помогает игроку действовать.
 * Палитра: black / gold / green.
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
      title: 'Начни с урожая',
      body: 'Посади саженец на пустой грядке и доведи до сбора — это основа прогресса.',
      tone: 'green',
    }
  }
  if (sold === 0 && harvest > 0) {
    return {
      title: 'Продай урожай',
      body: 'Собранные предметы можно продать на бирже и усилить баланс.',
      tone: 'gold',
    }
  }
  if (best && best.value > 20) {
    return {
      title: `Поднимись в топе «${best.label}»`,
      body: `Сейчас #${fmt(best.value)}. Несколько удачных циклов заметно сдвинут место.`,
      tone: 'gold',
    }
  }
  if (balance < 50 && harvest > 0) {
    return {
      title: 'Усиль экономику',
      body: 'Низкий баланс — продай лишнее на бирже или собери готовые грядки.',
      tone: 'green',
    }
  }
  if (deals > 0) {
    return {
      title: 'Держи ритм',
      body: 'Ферма + биржа работают лучше всего в цикле: посадил → собрал → продал.',
      tone: 'green',
    }
  }
  return {
    title: 'Твой следующий шаг',
    body: 'Проверь грядки: полей сухие, собери готовые, посади новые саженцы.',
    tone: 'green',
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
    <section className="pa-root" aria-label="Полезная сводка">
      <header className="pa-header">
        <p className="pa-eyebrow">Сводка</p>
        <h2 className="pa-title">Что важно сейчас</h2>
        <p className="pa-sub">
          {days > 0 ? `${days} дн. в игре` : 'Первый день'}
          {totalPlayers > 0 ? ` · ${fmt(totalPlayers)} игроков` : ''}
        </p>
      </header>

      <div className="pa-kpi-row">
        <div className="pa-kpi">
          <span className="pa-kpi-label">КУТ</span>
          <strong className="pa-kpi-value">{fmt(balance)}</strong>
        </div>
        <div className="pa-kpi">
          <span className="pa-kpi-label">Урожаи</span>
          <strong className="pa-kpi-value" style={{ color: GREEN }}>{fmt(harvest)}</strong>
        </div>
        <div className="pa-kpi">
          <span className="pa-kpi-label">Продано</span>
          <strong className="pa-kpi-value" style={{ color: GOLD }}>{fmt(sold)}</strong>
        </div>
      </div>

      <div className={`pa-tip pa-tip--${tip.tone}`}>
        <p className="pa-tip-title">{tip.title}</p>
        <p className="pa-tip-body">{tip.body}</p>
      </div>

      {top ? (
        <div className="pa-rank-card">
          <div className="pa-rank-main">
            <span className="pa-rank-label">Твой лучший ранг</span>
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
          <p className="pa-tip-body">Собери урожай или сделай сделку на бирже — и место в топе обновится.</p>
        </div>
      )}
    </section>
  )
}
