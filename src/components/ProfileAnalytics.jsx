/**
 * Полная сводка профиля: ферма Mini App + поля из bot/funcs/profile.py
 */

const GOLD = '#e8c56a'
const GREEN = '#3dd68c'
const ICE = '#9ec9e8'

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('ru-RU')
}

function bestRank(ranks) {
  const valid = ranks.filter((r) => r.value > 0)
  if (!valid.length) return null
  return valid.reduce((a, b) => (a.value < b.value ? a : b))
}

function formatRegDate(iso) {
  if (!iso) return null
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return String(iso)
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
  } catch {
    return String(iso)
  }
}

function nextTip({ harvest, sold, deals, balance, best, referrals }) {
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
  if (referrals === 0) {
    return {
      title: 'Пригласи друга',
      body: 'Рефералы усиливают статистику профиля — ссылка есть в боте.',
      tone: 'gold',
      icon: '🤝',
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

function StatCell({ label, value, tone }) {
  return (
    <div className={`pa-stat${tone ? ` pa-stat--${tone}` : ''}`}>
      <span className="pa-stat-label">{label}</span>
      <strong className="pa-stat-value">{value}</strong>
    </div>
  )
}

function FarmLive({ farm }) {
  if (!farm) return null
  const { plots = [], trees = [], ready = 0, dry = 0, planted = 0, empty = 0 } = farm
  const plotCount = plots.length
  const treeCount = trees.length
  if (!plotCount && !treeCount) return null

  return (
    <div className="pa-farm-live" aria-label="Состояние фермы">
      <div className="pa-farm-live-head">
        <span aria-hidden>🏡</span>
        <div>
          <p className="pa-tip-title">Ферма сейчас</p>
          <p className="pa-tip-body">
            {plotCount} грядок · {treeCount} деревьев
          </p>
        </div>
      </div>
      <div className="pa-farm-chips">
        {ready > 0 && <span className="pa-chip pa-chip--gold">Готово {ready}</span>}
        {dry > 0 && <span className="pa-chip pa-chip--ice">Сухие {dry}</span>}
        {planted > 0 && <span className="pa-chip pa-chip--green">Растут {planted}</span>}
        {empty > 0 && <span className="pa-chip">Пустые {empty}</span>}
      </div>
    </div>
  )
}

export default function ProfileAnalytics({ profile, leaderboard, farmLive }) {
  const harvest = Number(profile?.harvestCount || 0)
  const craft = Number(profile?.craftCount || 0)
  const sold = Number(profile?.marketItemsSold || 0)
  const deals = Number(profile?.marketSalesCount || 0)
  const balance = Number(profile?.balance || 0)
  const days = Number(profile?.daysInGame || 0)
  const totalPlayers = Number(leaderboard?.total || 0)

  const wins = Number(profile?.wins || 0)
  const losses = Number(profile?.losses || 0)
  const winAmount = Number(profile?.winAmount || 0)
  const donated = Number(profile?.donated || 0)
  const transferLimit = Number(profile?.transferLimit || 0)
  const withdrawLimit = Number(profile?.withdrawLimit || 0)
  const referrals = Number(profile?.referrals || 0)
  const experience = Number(profile?.experience || 0)
  const repPlus = Number(profile?.repPlus || 0)
  const repMinus = Number(profile?.repMinus || 0)
  const country = profile?.countryEmoji || ''
  const referer = profile?.refererName || ''
  const banned = Boolean(profile?.isBanned)
  const regLabel = formatRegDate(profile?.registeredAt)

  const ranks = [
    { id: 'harvests', label: 'Урожай', value: Number(leaderboard?.myRank?.harvests || 0), color: GREEN },
    { id: 'sales', label: 'Биржа', value: Number(leaderboard?.myRank?.sales || 0), color: GOLD },
    { id: 'balance', label: 'Баланс', value: Number(leaderboard?.myRank?.balance || 0), color: '#9fd9b4' },
  ]
  const top = bestRank(ranks)
  const tip = nextTip({ harvest, sold, deals, balance, best: top, referrals })

  const showGames = wins > 0 || losses > 0 || winAmount > 0
  const showRep = repPlus > 0 || repMinus > 0
  const showEconomy = donated > 0 || transferLimit > 0 || withdrawLimit > 0 || referrals > 0 || experience > 0

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
            {profile?.userId ? ` · ID ${profile.userId}` : ''}
          </p>
        </div>
      </header>

      {banned && (
        <div className="pa-ban" role="status">
          🚫 Аккаунт заблокирован
        </div>
      )}

      {(country || referer) && (
        <div className="pa-identity">
          {country && (
            <p className="pa-identity-line">
              <span aria-hidden>{country}</span>
              <span>Страна отмечена в профиле</span>
            </p>
          )}
          {referer && (
            <p className="pa-identity-line">
              <span aria-hidden>🪴</span>
              <span>Приглашён: {referer}</span>
            </p>
          )}
        </div>
      )}

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

      <div className="pa-kpi-row pa-kpi-row--secondary">
        <div className="pa-kpi">
          <span className="pa-kpi-label">Крафт</span>
          <strong className="pa-kpi-value">{fmt(craft)}</strong>
        </div>
        <div className="pa-kpi">
          <span className="pa-kpi-label">Сделки</span>
          <strong className="pa-kpi-value">{fmt(deals)}</strong>
        </div>
        <div className="pa-kpi">
          <span className="pa-kpi-label">Опыт</span>
          <strong className="pa-kpi-value" style={{ color: ICE }}>{fmt(experience)}</strong>
        </div>
      </div>

      <FarmLive farm={farmLive} />

      <div className={`pa-tip pa-tip--${tip.tone}`}>
        <span className="pa-tip-icon" aria-hidden>{tip.icon}</span>
        <div>
          <p className="pa-tip-title">{tip.title}</p>
          <p className="pa-tip-body">{tip.body}</p>
        </div>
      </div>

      {showEconomy && (
        <div className="pa-block">
          <p className="pa-block-title">Лимиты и экономика</p>
          <div className="pa-stat-grid">
            {donated > 0 && <StatCell label="Задоначено" value={`${fmt(donated)} кут`} tone="gold" />}
            {transferLimit > 0 && <StatCell label="Переводы до" value={`${fmt(transferLimit)} кут`} />}
            {withdrawLimit > 0 && <StatCell label="Лимит выводов" value={`${fmt(withdrawLimit)} кут`} tone="ice" />}
            {referrals > 0 && <StatCell label="Рефералы" value={fmt(referrals)} tone="green" />}
          </div>
        </div>
      )}

      {showGames && (
        <div className="pa-block">
          <p className="pa-block-title">Игровая статистика</p>
          <div className="pa-stat-grid">
            {(wins > 0 || losses > 0) && (
              <StatCell label="Wins / Losses" value={`${fmt(wins)} / ${fmt(losses)}`} tone="gold" />
            )}
            {winAmount > 0 && <StatCell label="Выиграно" value={`${fmt(winAmount)} кут`} tone="gold" />}
          </div>
        </div>
      )}

      {showRep && (
        <div className="pa-block">
          <p className="pa-block-title">Репутация</p>
          <div className="pa-stat-grid pa-stat-grid--2">
            <StatCell label="Плюсы" value={fmt(repPlus)} tone="green" />
            <StatCell label="Минусы" value={fmt(repMinus)} />
          </div>
        </div>
      )}

      {(regLabel || days > 0) && (
        <div className="pa-reg">
          <span aria-hidden>⛵️</span>
          <div>
            {regLabel && <p className="pa-tip-title">{regLabel}</p>}
            <p className="pa-tip-body">
              {days === 0 ? 'Менее дня с регистрации' : `${days} ${pluralDays(days)} в игре`}
            </p>
          </div>
        </div>
      )}

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

function pluralDays(n) {
  if (n % 10 === 1 && n % 100 !== 11) return 'день'
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return 'дня'
  return 'дней'
}
