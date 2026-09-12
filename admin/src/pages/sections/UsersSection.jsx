import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import {
  adjustAdminUserBalance,
  adjustAdminUserItem,
  adminFarmPlotAction,
  deletePlayerNote,
  exportPlayerProfile,
  fetchAdminUser,
  fetchAdminUserAudit,
  fetchAdminUserCuteHistory,
  fetchAdminUserIntel,
  fetchAdminUserTransfers,
  fetchContentDex,
  fetchFarmUser,
  fetchPlayerBans,
  fetchPlayerInventory,
  fetchPlayerNotes,
  fetchPlayerQuests,
  resetAdminUserOnboarding,
  resetFarmUserPlots,
  searchAdminUsers,
  setAdminUserBanned,
  uploadBanEvidence,
  upsertPlayerNote,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'
import UserLookupPreview from '../../components/UserLookupPreview'
import PlayerDossierPanel from '../../components/PlayerDossierPanel'

const EVENT_LABELS = {
  shop_buy: 'Покупка в магазине',
  plot_buy: 'Покупка грядки',
  plot_clear: 'Очистка грядки',
  craft_success: 'Крафт успех',
  craft_fail: 'Крафт провал',
  market_buy: 'Покупка на бирже',
  market_sell: 'Продажа на бирже',
  admin_balance: 'Admin: баланс',
  admin_item: 'Admin: предмет',
  admin_ban: 'Admin: бан',
  admin_unban: 'Admin: разбан',
  admin_market_cancel: 'Admin: снят лот',
  admin_farm_reset: 'Admin: сброс грядок',
  admin_farm_global_reset: 'Admin: глобальный сброс фермы',
  admin_onboarding_reset: 'Admin: сброс обучения',
}

const PLOT_SLOTS_FALLBACK = 8

const PROFILE_TABS = [
  { id: 'profile', label: 'Профиль' },
  { id: 'intel', label: 'Аналитика' },
  { id: 'transfers', label: 'Переводы' },
  { id: 'farm', label: 'Ферма' },
  { id: 'history', label: 'История' },
  { id: 'quests', label: 'Квесты' },
  { id: 'bans', label: 'Баны' },
  { id: 'inventory', label: 'Инвентарь' },
  { id: 'notes', label: 'Заметки' },
]

const LEVEL_LABELS = {
  huge: 'огромная',
  large: 'крупная',
  notable: 'заметная',
  small: 'обычная',
}

function formatKutAmount(n) {
  const v = Number(n) || 0
  return `${v.toLocaleString('ru-RU')} кут`
}

function EmptyHint({ children }) {
  return <p className="panel-users-empty-hint">{children}</p>
}

function PlayerIntelOverview({ intel, onOpenUser }) {
  if (!intel) {
    return (
      <article className="panel-shelf panel-users-card pu-intel-card pu-intel-loading">
        <p className="panel-shelf-muted">Собираю аналитику игрока…</p>
      </article>
    )
  }

  const act = intel.activity30d || {}
  const byChat = act.byChat || []
  const most = act.mostActive
  const maxMsg = Math.max(1, ...byChat.map((c) => c.messages || 0))
  const thr = intel.thresholds || {}
  const eco = intel.economy || {}
  const moves = intel.significantMoves || []
  const p2p = intel.p2p || {}
  const eng = intel.engagement || {}
  const msgs = eng.messages || {}
  const days = eng.activeDays || {}
  const sess = eng.sessions || {}
  const farm = eng.farm || {}
  const signals = eng.signals || {}
  const hourly = eng.hourlyHeat || []
  const maxHour = Math.max(1, ...hourly)
  const topLife = eng.topGroupsLifetime || []
  const score = Number(signals.engagementScore || 0)
  const churn = signals.churnRisk || 'unknown'
  const churnLabel = { low: 'низкий', medium: 'средний', high: 'высокий', unknown: 'н/д' }[churn] || churn

  const fmtMin = (m) => {
    const n = Number(m) || 0
    if (n < 60) return `${n} мин`
    const h = Math.floor(n / 60)
    const mm = n % 60
    return mm ? `${h} ч ${mm} мин` : `${h} ч`
  }

  return (
    <div className="pu-intel-stack">
      <article className="panel-shelf panel-users-card pu-intel-card">
        <div className="pu-bento-head">
          <div>
            <p className="panel-shelf-label">Индекс вовлечённости</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">Сводка поведения</h3>
          </div>
          <span className="pu-bento-chip">{score}/100</span>
        </div>
        <div className="pu-engage-score">
          <div className="pu-engage-score-bar"><span style={{ width: `${score}%` }} /></div>
          <div className="pu-engage-meta">
            <span>Риск оттока: <strong data-risk={churn}>{churnLabel}</strong></span>
            {signals.inactiveDays != null && (
              <span>Неактивен: <strong>{signals.inactiveDays} дн.</strong></span>
            )}
            {eng.platform && <span>Клиент: <strong>{eng.platform}</strong></span>}
            {eng.timezone && <span>TZ: <strong>{eng.timezone}</strong></span>}
          </div>
          {(signals.labels || []).length > 0 && (
            <div className="pu-engage-labels">
              {signals.labels.map((l) => <span key={l} className="pu-engage-pill">{l}</span>)}
            </div>
          )}
        </div>
      </article>

      <article className="panel-shelf panel-users-card pu-intel-card">
        <div className="pu-bento-head">
          <div>
            <p className="panel-shelf-label">Присутствие</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">Сообщения и активные дни</h3>
          </div>
        </div>
        <div className="pu-stat-grid">
          <div><span>Сегодня</span><strong>{(msgs.day || 0).toLocaleString('ru-RU')}</strong></div>
          <div><span>Неделя</span><strong>{(msgs.week || 0).toLocaleString('ru-RU')}</strong></div>
          <div><span>Месяц</span><strong>{(msgs.month || 0).toLocaleString('ru-RU')}</strong></div>
          <div><span>Год</span><strong>{(msgs.year || 0).toLocaleString('ru-RU')}</strong></div>
          <div><span>Всего сообщ.</span><strong>{(msgs.lifetime || 0).toLocaleString('ru-RU')}</strong></div>
          <div><span>Ср. / активный день</span><strong>{msgs.avgPerActiveDay ?? 0}</strong></div>
          <div><span>Ср. / день · месяц</span><strong>{msgs.avgPerDayMonth ?? 0}</strong></div>
          <div><span>Ср. / день · год</span><strong>{msgs.avgPerDayYear ?? 0}</strong></div>
          <div><span>Активных дней · нед</span><strong>{days.week ?? 0}</strong></div>
          <div><span>Активных дней · мес</span><strong>{days.month ?? 0}</strong></div>
          <div><span>Серия сейчас</span><strong>{eng.streak?.current ?? 0}</strong></div>
          <div><span>Лучшая серия</span><strong>{eng.streak?.best ?? 0}</strong></div>
        </div>
      </article>

      <article className="panel-shelf panel-users-card pu-intel-card">
        <div className="pu-bento-head">
          <div>
            <p className="panel-shelf-label">Оценка активного времени</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">По сессиям входа в Mini App</h3>
          </div>
        </div>
        <div className="pu-stat-grid">
          <div><span>За 30 дней</span><strong>{fmtMin(sess.estimatedMinutes30d)}</strong></div>
          <div><span>Всего (оценка)</span><strong>{fmtMin(sess.estimatedMinutesTotal)}</strong></div>
          <div><span>Ср. / активный день</span><strong>{fmtMin(sess.avgMinutesPerActiveDay)}</strong></div>
          <div><span>Ср. / день · месяц</span><strong>{fmtMin(sess.avgMinutesPerDayMonth)}</strong></div>
          <div><span>Сессий · 30д</span><strong>{sess.sessionCount30d ?? 0}</strong></div>
          <div><span>Входов · 30д</span><strong>{sess.loginEvents30d ?? 0}</strong></div>
        </div>
        <p className="pu-intel-note">
          Точного таймера нет — время считается по цепочкам входов (пауза &gt;30 мин = новая сессия, до 3 ч на сессию).
        </p>
      </article>

      <article className="panel-shelf panel-users-card pu-intel-card">
        <div className="pu-bento-head">
          <div>
            <p className="panel-shelf-label">Активность · 30 дней</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">Сообщения в группах</h3>
          </div>
          <span className="pu-bento-chip">{act.totalMessages?.toLocaleString('ru-RU') || 0}</span>
        </div>

        {most ? (
          <div className="pu-intel-highlight">
            <span className="pu-intel-highlight-kicker">Самая активная группа</span>
            <strong>{most.chatName}</strong>
            <em>{most.messages.toLocaleString('ru-RU')} сообщений</em>
          </div>
        ) : (
          <p className="panel-shelf-muted">За 30 дней сообщений в группах нет</p>
        )}

        {byChat.length > 0 && (
          <ul className="pu-intel-bars">
            {byChat.slice(0, 8).map((c) => (
              <li key={c.chatId}>
                <div className="pu-intel-bar-meta">
                  <span className="pu-intel-bar-name">{c.chatName}</span>
                  <span className="pu-intel-bar-val">{c.messages.toLocaleString('ru-RU')}</span>
                </div>
                <div className="pu-intel-bar-track">
                  <span style={{ width: `${Math.max(4, (c.messages / maxMsg) * 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </article>

      {topLife.length > 0 && (
        <article className="panel-shelf panel-users-card pu-intel-card">
          <div className="pu-bento-head">
            <div>
              <p className="panel-shelf-label">Домашние группы</p>
              <h3 className="panel-users-subtitle panel-users-subtitle-tight">Где играет чаще всего · всё время</h3>
            </div>
          </div>
          <ul className="pu-intel-bars">
            {topLife.slice(0, 8).map((c) => (
              <li key={c.chatId}>
                <div className="pu-intel-bar-meta">
                  <span className="pu-intel-bar-name">{c.chatName}</span>
                  <span className="pu-intel-bar-val">{c.messages.toLocaleString('ru-RU')} · {c.activeDays} дн.</span>
                </div>
                <div className="pu-intel-bar-track">
                  <span style={{ width: `${Math.max(4, (c.messages / Math.max(1, topLife[0].messages)) * 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </article>
      )}

      {hourly.some((v) => v > 0) && (
        <article className="panel-shelf panel-users-card pu-intel-card">
          <div className="pu-bento-head">
            <div>
              <p className="panel-shelf-label">Часы активности</p>
              <h3 className="panel-users-subtitle panel-users-subtitle-tight">Когда чаще заходит · 90 дней (UTC)</h3>
            </div>
          </div>
          <div className="pu-heat-hours" aria-hidden>
            {hourly.map((v, h) => (
              <div key={h} className="pu-heat-col" title={`${h}:00 — ${v}`}>
                <span style={{ height: `${Math.max(8, (v / maxHour) * 100)}%` }} />
                <em>{h}</em>
              </div>
            ))}
          </div>
        </article>
      )}

      <article className="panel-shelf panel-users-card pu-intel-card">
        <div className="pu-bento-head">
          <div>
            <p className="panel-shelf-label">Ферма · события</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">Посадки / поливы / сборы</h3>
          </div>
        </div>
        <div className="pu-stat-grid">
          <div><span>Посадил</span><strong>{farm.plants ?? 0}</strong></div>
          <div><span>Полил</span><strong>{farm.waters ?? 0}</strong></div>
          <div><span>Собрал</span><strong>{farm.harvests ?? 0}</strong></div>
          <div><span>Засохло</span><strong>{farm.withers ?? 0}</strong></div>
          <div><span>Эффективность</span><strong>{farm.efficiencyPct != null ? `${farm.efficiencyPct}%` : '—'}</strong></div>
          <div><span>Открытий игр</span><strong>{(eng.gameOpens?.total || 0).toLocaleString('ru-RU')}</strong></div>
        </div>
      </article>

      <article className="panel-shelf panel-users-card pu-intel-card">
        <div className="pu-bento-head">
          <div>
            <p className="panel-shelf-label">Экономика под игрока</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">Масштаб сумм</h3>
          </div>
        </div>
        <div className="pu-intel-thresholds">
          <div>
            <span>Заметная</span>
            <strong>≥ {formatKutAmount(thr.notable)}</strong>
          </div>
          <div>
            <span>Крупная</span>
            <strong>≥ {formatKutAmount(thr.large)}</strong>
          </div>
          <div>
            <span>Огромная</span>
            <strong>≥ {formatKutAmount(thr.huge)}</strong>
          </div>
        </div>
        <p className="pu-intel-note">
          Пороги считаются от богатства игрока (~{formatKutAmount(thr.wealth)}):
          мелкие суммы для богатых не подсвечиваются.
        </p>
        <div className="pu-intel-eco-grid">
          <div><span>Донаты</span><strong>{formatKutAmount(eco.donateLifetime || eco.donateJournal?.total || 0)}</strong></div>
          <div><span>Побед</span><strong>{eco.wins ?? 0}</strong></div>
          <div><span>Поражений</span><strong>{eco.losses ?? 0}</strong></div>
          <div><span>Выиграно</span><strong>{formatKutAmount(eco.winAmount || 0)}</strong></div>
        </div>
      </article>

      <article className="panel-shelf panel-users-card pu-intel-card">
        <div className="pu-bento-head">
          <div>
            <p className="panel-shelf-label">Крупные движения</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">Где много кут</h3>
          </div>
          <span className="pu-bento-chip">{moves.length}</span>
        </div>
        {moves.length === 0 ? (
          <p className="panel-shelf-muted">Крупных операций относительно баланса нет</p>
        ) : (
          <ul className="pu-intel-moves">
            {moves.slice(0, 12).map((m) => (
              <li key={m.id} className={`pu-intel-move pu-level-${m.level}`}>
                <div className="pu-intel-move-top">
                  <span className={`pu-dir ${m.direction}`}>{m.direction === 'in' ? '+' : '−'}{m.amount.toLocaleString('ru-RU')}</span>
                  <span className="pu-level-pill">{LEVEL_LABELS[m.level] || m.level}</span>
                </div>
                <p>{m.cause || 'без причины'}</p>
                {m.when && <time>{m.when}</time>}
              </li>
            ))}
          </ul>
        )}
      </article>

      <article className="panel-shelf panel-users-card pu-intel-card">
        <div className="pu-bento-head">
          <div>
            <p className="panel-shelf-label">P2P переводы</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">Кому и от кого</h3>
          </div>
        </div>
        <div className="pu-intel-p2p-summary">
          <div>
            <span>Отправлено</span>
            <strong>{formatKutAmount(p2p.sentSum)} · {p2p.sentCount || 0} шт</strong>
          </div>
          <div>
            <span>Получено</span>
            <strong>{formatKutAmount(p2p.recvSum)} · {p2p.recvCount || 0} шт</strong>
          </div>
        </div>
        {(p2p.recent || []).length === 0 ? (
          <p className="panel-shelf-muted">Переводов пока нет</p>
        ) : (
          <ul className="pu-intel-transfers">
            {p2p.recent.slice(0, 10).map((t) => (
              <li key={t.id} className={`pu-level-${t.level || 'small'}`}>
                <button
                  type="button"
                  className="pu-cp-link"
                  onClick={() => onOpenUser?.(t.counterparty?.userId)}
                >
                  {t.direction === 'out' ? '→' : '←'}{' '}
                  {t.counterparty?.username ? `@${t.counterparty.username}` : t.counterparty?.name}
                </button>
                <strong className={t.direction === 'out' ? 'pu-out' : 'pu-in'}>
                  {t.direction === 'out' ? '−' : '+'}{formatKutAmount(t.amount)}
                </strong>
                <span className="pu-cause">{t.cause || 'перевод'}</span>
                <time>{t.createdAt ? formatDate(t.createdAt) : ''}</time>
              </li>
            ))}
          </ul>
        )}
        {(intel.itemTrades?.count > 0) && (
          <p className="pu-intel-note">Сделок с предметами (по истории): {intel.itemTrades.count}</p>
        )}
      </article>
    </div>
  )
}

function PlayerTransfersPanel({ userId, intel, onOpenUser }) {
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [near, setNear] = useState('')
  const [items, setItems] = useState(intel?.p2p?.recent || [])
  const [total, setTotal] = useState(intel?.p2p?.recent?.length || 0)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setItems(intel?.p2p?.recent || [])
    setTotal(intel?.p2p?.recent?.length || 0)
  }, [intel])

  const load = async () => {
    if (!userId) return
    setLoading(true)
    try {
      const data = await fetchAdminUserTransfers(userId, {
        dateFrom,
        dateTo,
        near,
        limit: 80,
      })
      setItems(data.items || [])
      setTotal(data.total || 0)
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка загрузки переводов', { error: true })
    } finally {
      setLoading(false)
    }
  }

  const cute = (intel?.cuteRecent?.items || []).filter((it) => it.kind === 'transfer' || it.cause === 'передача предметов')

  return (
    <div className="pu-transfers-panel">
      <div className="pu-bento-head">
        <div>
          <p className="panel-shelf-label">История</p>
          <h3 className="panel-users-subtitle">Переводы кут и предметов</h3>
        </div>
      </div>

      <div className="pu-transfer-filters">
        <label className="pu-field">
          <span className="pu-field-label">С даты</span>
          <input className="panel-users-input pu-field-input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label className="pu-field">
          <span className="pu-field-label">По дату</span>
          <input className="panel-users-input pu-field-input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <label className="pu-field">
          <span className="pu-field-label">Около времени (±12ч)</span>
          <input className="panel-users-input pu-field-input" type="datetime-local" value={near} onChange={(e) => setNear(e.target.value)} />
        </label>
        <button type="button" className="panel-users-btn panel-users-btn-primary" disabled={loading} onClick={load}>
          {loading ? '…' : 'Показать'}
        </button>
      </div>

      <h4 className="pu-section-title">P2P переводы кут · {total}</h4>
      {items.length === 0 ? (
        <p className="panel-shelf-muted">Нет переводов за выбранный период</p>
      ) : (
        <ul className="pu-intel-transfers pu-intel-transfers-full">
          {items.map((t) => (
            <li key={t.id} className={`pu-level-${t.level || 'small'}`}>
              <button type="button" className="pu-cp-link" onClick={() => onOpenUser?.(t.counterparty?.userId)}>
                {t.direction === 'out' ? 'Отправил' : 'Получил от'}{' '}
                {t.counterparty?.username ? `@${t.counterparty.username}` : t.counterparty?.name}
                <em> · id {t.counterparty?.userId}</em>
              </button>
              <strong className={t.direction === 'out' ? 'pu-out' : 'pu-in'}>
                {t.direction === 'out' ? '−' : '+'}{formatKutAmount(t.amount)}
              </strong>
              <span className="pu-cause">{t.cause || 'без комментария'}</span>
              <time>{t.createdAt ? formatDate(t.createdAt) : ''}</time>
            </li>
          ))}
        </ul>
      )}

      <h4 className="pu-section-title">Из истории кут (в т.ч. предметы)</h4>
      {cute.length === 0 ? (
        <p className="panel-shelf-muted">Нет связанных записей</p>
      ) : (
        <ul className="pu-intel-moves">
          {cute.map((it, idx) => (
            <li key={`${it.ts}-${idx}`} className={`pu-intel-move pu-level-${it.level || 'small'}`}>
              <div className="pu-intel-move-top">
                <span className={`pu-dir ${it.direction}`}>
                  {it.direction === 'in' ? '+' : '−'}{Number(it.amount || 0).toLocaleString('ru-RU')} кут
                </span>
                <span className="pu-level-pill">{it.kind === 'transfer' ? 'перевод' : (LEVEL_LABELS[it.level] || 'запись')}</span>
              </div>
              <p>{it.cause || '—'}</p>
              {it.counterparty && (
                <button type="button" className="pu-cp-link" onClick={() => onOpenUser?.(it.counterparty.userId)}>
                  {it.counterparty.username ? `@${it.counterparty.username}` : it.counterparty.name}
                </button>
              )}
              {it.ts && <time>{formatDate(it.ts)}</time>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const PERIOD_LABELS = { hourly: 'Часовые', daily: 'Дневные', weekly: 'Недельные' }

function formatDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

function initialsFromName(name) {
  const parts = String(name || '?').trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return (parts[0]?.[0] || '?').toUpperCase()
}

// ---------------------------------------------------------------------------
// EvidencePhotoPicker — загрузка нескольких фото с превью
// ---------------------------------------------------------------------------
const EVIDENCE_BASE = `${import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'}/users/evidence/`

function EvidencePhotoPicker({ fileIds, onChange, disabled }) {
  const [items, setItems] = useState([])
  const inputRef = useRef(null)

  useEffect(() => {
    onChange(items.filter((i) => i.fileId).map((i) => i.fileId))
  }, [items]) // eslint-disable-line

  const addFiles = (files) => {
    const newItems = Array.from(files).map((file) => ({
      id: `${Date.now()}-${Math.random()}`,
      localUrl: URL.createObjectURL(file),
      fileId: '',
      uploading: true,
      error: false,
      file,
    }))
    setItems((prev) => [...prev, ...newItems])
    newItems.forEach((item) => {
      uploadBanEvidence(item.file)
        .then((r) => setItems((prev) => prev.map((i) =>
          i.id === item.id ? { ...i, fileId: r.fileId || '', uploading: false } : i
        )))
        .catch(() => setItems((prev) => prev.map((i) =>
          i.id === item.id ? { ...i, uploading: false, error: true } : i
        )))
    })
  }

  const remove = (id) => {
    setItems((prev) => {
      const item = prev.find((i) => i.id === id)
      if (item?.localUrl) URL.revokeObjectURL(item.localUrl)
      return prev.filter((i) => i.id !== id)
    })
  }

  const retry = (id) => {
    const item = items.find((i) => i.id === id)
    if (!item) return
    setItems((prev) => prev.map((i) => i.id === id ? { ...i, uploading: true, error: false } : i))
    uploadBanEvidence(item.file)
      .then((r) => setItems((prev) => prev.map((i) =>
        i.id === id ? { ...i, fileId: r.fileId || '', uploading: false } : i
      )))
      .catch(() => setItems((prev) => prev.map((i) =>
        i.id === id ? { ...i, uploading: false, error: true } : i
      )))
  }

  return (
    <>
      <div className="ev-photo-picker">
        <div className="ev-photo-grid">
          {items.map((item) => (
            <div key={item.id} className={`ev-photo-thumb${item.error ? ' ev-photo-thumb-error' : ''}`}>
              <img
                src={item.localUrl}
                alt=""
                className="ev-photo-img"
                style={{ cursor: 'default' }}
              />
              {item.uploading && (
                <div className="ev-photo-overlay">
                  <div className="ev-photo-spin" />
                </div>
              )}
              {item.error && (
                <div className="ev-photo-overlay ev-photo-overlay-error" onClick={() => retry(item.id)}>
                  <span>↺</span>
                </div>
              )}
              {!item.uploading && !item.error && item.fileId && (
                <div className="ev-photo-badge-ok">✓</div>
              )}
              <button className="ev-photo-remove" onClick={() => remove(item.id)} disabled={disabled}>✕</button>
            </div>
          ))}
          <button className="ev-photo-add" onClick={() => inputRef.current?.click()} disabled={disabled}>
            <span>+</span>
            <span className="ev-photo-add-hint">Фото</span>
          </button>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => { if (e.target.files?.length) addFiles(e.target.files); e.target.value = '' }}
        />
      </div>

    </>
  )
}

function formatSeconds(s) {
  if (s == null) return '-'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}ч ${m}м`
  if (m > 0) return `${m}м ${sec}с`
  return `${sec}с`
}

// ---- Quest progress tab ----
function QuestsTab({ userId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    fetchPlayerQuests(userId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [userId])

  if (loading) return <p className="panel-shelf-muted">Загрузка…</p>
  if (error) return <p className="panel-shelf-error">{error}</p>
  if (!data) return null

  return (
    <div className="pu-quests">
      <h4 className="pu-section-title">Текущий прогресс</h4>
      {(data.periods || []).map((p) => (
        <div key={p.period} className="pu-quest-period">
          <div className="pu-quest-period-head">
            <span className="pu-quest-period-label">{PERIOD_LABELS[p.period] || p.period}</span>
            <span className="pu-quest-claimed">Взято: {p.claimedCount}</span>
          </div>
          {p.acceptedQuestId ? (
            <div className="pu-quest-active">
              <div className="pu-quest-row">
                <span className="pu-quest-id">{p.acceptedQuestId}</span>
                <span className="pu-quest-title">{p.questTitle || '-'}</span>
              </div>
              <div className="pu-quest-progress-row">
                <div className="pu-quest-bar-wrap">
                  <div
                    className="pu-quest-bar"
                    style={{
                      width: `${p.questTarget ? Math.min(100, (p.currentProgress / p.questTarget) * 100) : 0}%`,
                    }}
                  />
                </div>
                <span className="pu-quest-progress-text">
                  {p.currentProgress} / {p.questTarget ?? '?'}
                </span>
              </div>
              <div className="pu-quest-meta">
                <span>Взято: {p.acceptedAt ? formatDate(p.acceptedAt) : '-'}</span>
                {p.timerRemainingSeconds != null && (
                  <span className="pu-quest-timer">⏱ {formatSeconds(p.timerRemainingSeconds)}</span>
                )}
              </div>
            </div>
          ) : (
            <p className="panel-shelf-muted">Задание не взято</p>
          )}
        </div>
      ))}

      {data.history.length > 0 && (
        <>
          <h4 className="pu-section-title" style={{ marginTop: '1rem' }}>История ({data.history.length})</h4>
          <div className="pu-quest-history">
            {data.history.map((h, i) => (
              <div key={i} className="pu-quest-history-row">
                <span className={`pu-quest-ev ${h.eventType === 'quest_complete' ? 'complete' : 'accept'}`}>
                  {h.eventType === 'quest_complete' ? '✅' : '▶'}
                </span>
                <span className="pu-quest-history-id">{h.questId || '-'}</span>
                <span className="pu-quest-history-period">{PERIOD_LABELS[h.period] || h.period || '-'}</span>
                <time className="pu-quest-history-time">{formatDate(h.createdAt)}</time>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ---- Ban history tab ----
function BansTab({ userId }) {
  const [bans, setBans] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    fetchPlayerBans(userId)
      .then((d) => setBans(d.bans || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [userId])

  if (loading) return <p className="panel-shelf-muted">Загрузка…</p>
  if (error) return <p className="panel-shelf-error">{error}</p>
  if (!bans || bans.length === 0) return <p className="panel-shelf-muted">История банов пуста</p>

  return (
    <div className="pu-bans">
      <h4 className="pu-section-title">История банов ({bans.length})</h4>
      <div className="pu-ban-list">
        {bans.map((b) => (
          <div key={b.id} className={`pu-ban-row ${b.action}`}>
            <span className={`pu-ban-badge ${b.action}`}>{b.action === 'ban' ? '🔴 БАН' : '🟢 РАЗБАН'}</span>
            <div className="pu-ban-meta">
              {b.reason && <span className="pu-ban-reason">Причина: {b.reason}</span>}
              <span className="pu-ban-admin">Admin ID: {b.adminUserId || '-'}</span>
              <time className="pu-ban-time">{formatDate(b.createdAt)}</time>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---- Inventory tab ----
function InventoryTab({ userId, canMutate = false, onChanged }) {
  const [items, setItems] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [qty, setQty] = useState('1')
  const [busy, setBusy] = useState(false)

  const reload = useCallback(() => {
    if (!userId) return
    setLoading(true)
    fetchPlayerInventory(userId)
      .then((d) => setItems(d.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [userId])

  useEffect(() => { reload() }, [reload])

  const runDelta = async (sign) => {
    if (!selected || !canMutate) return
    const n = Math.abs(Number.parseInt(qty, 10) || 0)
    if (!n) return
    setBusy(true)
    try {
      await adjustAdminUserItem(userId, String(selected.itemId), sign * n, '')
      notifyAdmin(sign > 0 ? `Выдано ×${n}` : `Забрано ×${n}`)
      setSelected(null)
      setQty('1')
      reload()
      onChanged?.()
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка', { error: true })
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="panel-shelf-muted">Загрузка…</p>
  if (error) return <p className="panel-shelf-error">{error}</p>
  if (!items || items.length === 0) return <p className="panel-shelf-muted">Инвентарь пуст</p>

  return (
    <div className="pu-inventory">
      <div className="pu-bento-head">
        <div>
          <h4 className="pu-section-title" style={{ margin: 0 }}>Инвентарь ({items.length} позиций)</h4>
          <p className="panel-shelf-muted" style={{ margin: '0.25rem 0 0' }}>
            {canMutate ? 'Нажми на предмет — выдать или забрать' : 'Только просмотр'}
          </p>
        </div>
      </div>
      <div className="pu-inventory-grid">
        {items.map((item) => (
          <button
            type="button"
            key={item.itemId}
            className={`pu-inv-item${selected?.itemId === item.itemId ? ' is-active' : ''}${canMutate ? ' is-clickable' : ''}`}
            disabled={!canMutate || busy}
            onClick={() => {
              if (!canMutate) return
              setSelected(item)
              setQty('1')
            }}
          >
            <span className="pu-inv-emoji">{item.emoji}</span>
            <span className="pu-inv-name">{item.name}</span>
            <span className="pu-inv-count">×{item.count}</span>
          </button>
        ))}
      </div>

      {selected && canMutate && (
        <div className="pu-inv-popover pu-inv-popover-inline" role="dialog">
          <div className="pu-inv-popover-head">
            <strong>{selected.emoji} {selected.name}</strong>
            <button type="button" className="pu-close-btn" onClick={() => setSelected(null)}>✕</button>
          </div>
          <p className="panel-shelf-muted">Сейчас ×{selected.count}</p>
          <label className="pu-field">
            <span className="pu-field-label">Количество</span>
            <input
              className="panel-users-input pu-field-input"
              value={qty}
              onChange={(e) => setQty(e.target.value.replace(/\D/g, ''))}
              inputMode="numeric"
              placeholder="1"
            />
          </label>
          <div className="pu-kut-actions">
            <button type="button" className="panel-users-btn panel-users-btn-success" disabled={busy || !Number(qty)} onClick={() => runDelta(1)}>
              Выдать
            </button>
            <button type="button" className="panel-users-btn panel-users-btn-danger" disabled={busy || !Number(qty)} onClick={() => runDelta(-1)}>
              Забрать
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---- Farm control tab ----
function FarmControlTab({ userId, profile, canControl, onChanged }) {
  const [farm, setFarm] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [selectedId, setSelectedId] = useState(null)
  const [plantCrop, setPlantCrop] = useState('')

  const reload = useCallback(() => {
    if (!userId) return
    setLoading(true)
    fetchFarmUser(userId)
      .then((d) => {
        setFarm(d)
        const crops = d.farmCrops || []
        if (!plantCrop && crops[0]) setPlantCrop(String(crops[0].key || crops[0].id || ''))
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [userId, plantCrop])

  useEffect(() => { reload() }, [userId]) // eslint-disable-line react-hooks/exhaustive-deps

  const plots = farm?.plots || profile?.plots || []
  const plotSlots = Math.max(1, farm?.maxPlots ?? profile?.maxPlots ?? PLOT_SLOTS_FALLBACK)
  const crops = farm?.farmCrops || []
  const selected = plots.find((p) => Number(p.id) === Number(selectedId))

  const run = async (action, cropId = null) => {
    if (!canControl || !selectedId) return
    setBusy(true)
    setError('')
    try {
      const res = await adminFarmPlotAction(userId, selectedId, action, cropId)
      notifyAdmin(res.message || 'Готово')
      if (res.farm) setFarm(res.farm)
      else reload()
      onChanged?.()
    } catch (e) {
      setError(e.message || 'Ошибка')
      notifyAdmin(e.message || 'Ошибка', { error: true })
    } finally {
      setBusy(false)
    }
  }

  const statusOf = (plot) => String(plot?.status || '').toUpperCase()

  if (loading && !farm) return <p className="panel-shelf-muted">Загрузка фермы…</p>

  return (
    <div className="pu-farm-tab">
      <div className="pu-bento-head">
        <div>
          <p className="panel-shelf-label">Ферма</p>
          <h3 className="panel-users-subtitle">Грядки игрока</h3>
        </div>
        <span className="pu-bento-chip">{farm?.ownedPlots ?? profile?.ownedPlots}/{farm?.maxPlots ?? profile?.maxPlots}</span>
      </div>
      {!canControl && (
        <p className="panel-shelf-muted">Просмотр. Управление грядками доступно только владельцу.</p>
      )}
      {error && <p className="panel-shelf-error">{error}</p>}

      <div className="panel-users-plot-grid pu-farm-grid">
        {Array.from({ length: plotSlots }, (_, i) => {
          const plotId = i + 1
          const plot = plots.find((p) => Number(p.id) === plotId)
          const status = plot ? statusOf(plot) : ''
          const statusClass = !plot
            ? ' is-locked'
            : status === 'READY'
              ? ' is-ready'
              : status === 'EMPTY'
                ? ' is-empty'
                : status === 'WITHERED'
                  ? ' is-withered'
                  : ' is-busy'
          return (
            <button
              type="button"
              key={plotId}
              className={`panel-users-plot${statusClass}${selectedId === plotId ? ' is-selected' : ''}`}
              onClick={() => setSelectedId(plotId)}
            >
              <span className="panel-users-plot-id">#{plotId}</span>
              <span className="panel-users-plot-status">{plot ? plot.status : '—'}</span>
              {plot?.cropLabel && <span className="pu-plot-crop">{plot.cropLabel}</span>}
              {plot?.needsWater && <span className="pu-plot-water">нужен полив</span>}
            </button>
          )
        })}
      </div>

      {selectedId && (
        <div className="pu-farm-controls">
          <div className="pu-farm-controls-head">
            <strong>Грядка #{selectedId}</strong>
            <span>{selected ? statusOf(selected) : '—'}</span>
            {selected?.cropLabel && <em>{selected.cropLabel}</em>}
          </div>
          {canControl ? (
            <>
              <div className="pu-farm-actions">
                <button type="button" className="panel-users-btn" disabled={busy || statusOf(selected) !== 'GROWING'} onClick={() => run('water')}>
                  Полить
                </button>
                <button type="button" className="panel-users-btn" disabled={busy || !['GROWING', 'READY'].includes(statusOf(selected))} onClick={() => run('force_ripe')}>
                  Дозреть
                </button>
                <button type="button" className="panel-users-btn panel-users-btn-success" disabled={busy || statusOf(selected) !== 'READY'} onClick={() => run('harvest')}>
                  Собрать → инвентарь
                </button>
                <button type="button" className="panel-users-btn panel-users-btn-danger" disabled={busy} onClick={() => run('clear')}>
                  Очистить
                </button>
              </div>
              <div className="pu-farm-plant-row">
                <select
                  className="panel-users-input pu-field-input"
                  value={plantCrop}
                  onChange={(e) => setPlantCrop(e.target.value)}
                  disabled={busy || !crops.length}
                >
                  {crops.length === 0 && <option value="">Нет культур</option>}
                  {crops.map((c) => (
                    <option key={c.key || c.id} value={c.key || c.id}>{c.displayName || c.name || c.key}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-primary"
                  disabled={busy || !plantCrop || !['EMPTY', 'WITHERED', ''].includes(statusOf(selected))}
                  onClick={() => run('plant', plantCrop)}
                >
                  Посадить
                </button>
              </div>
              <button
                type="button"
                className="panel-users-btn"
                disabled={busy}
                onClick={async () => {
                  setBusy(true)
                  try {
                    await resetFarmUserPlots(userId, null)
                    notifyAdmin('Все грядки сброшены')
                    reload()
                    onChanged?.()
                  } catch (e) {
                    notifyAdmin(e.message, { error: true })
                  } finally {
                    setBusy(false)
                  }
                }}
              >
                Сбросить все грядки
              </button>
            </>
          ) : (
            <p className="panel-shelf-muted">Выберите грядку, чтобы увидеть статус. Изменения недоступны.</p>
          )}
        </div>
      )}
    </div>
  )
}
function NotesTab({ userId, adminId }) {
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [text, setText] = useState('')
  const [editingId, setEditingId] = useState(null)

  const reload = useCallback(() => {
    if (!userId) return
    setLoading(true)
    fetchPlayerNotes(userId)
      .then((d) => setNotes(d.notes || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [userId])

  useEffect(() => { reload() }, [reload])

  const handleSave = async () => {
    if (!text.trim()) return
    setSaving(true)
    setError('')
    try {
      await upsertPlayerNote(userId, { text: text.trim(), noteId: editingId })
      setText('')
      setEditingId(null)
      reload()
      notifyAdmin('Заметка сохранена')
    } catch (e) {
      setError(e.message)
      notifyAdmin(e.message, { error: true })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (noteId) => {
    setSaving(true)
    try {
      await deletePlayerNote(userId, noteId)
      reload()
      notifyAdmin('Заметка удалена')
    } catch (e) {
      setError(e.message)
      notifyAdmin(e.message, { error: true })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="pu-notes">
      <h4 className="pu-section-title">Заметки администраторов</h4>
      {error && <p className="panel-shelf-error">{error}</p>}

      <div className="pu-notes-form">
        <textarea
          className="pu-notes-textarea"
          placeholder="Новая заметка…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          disabled={saving}
        />
        <div className="pu-notes-form-actions">
          {editingId && (
            <button
              className="panel-users-btn"
              onClick={() => { setEditingId(null); setText('') }}
              disabled={saving}
            >
              Отмена
            </button>
          )}
          <button
            className="panel-users-btn panel-users-btn-primary"
            onClick={handleSave}
            disabled={saving || !text.trim()}
          >
            {saving ? '…' : editingId ? 'Сохранить' : 'Добавить заметку'}
          </button>
        </div>
      </div>

      {loading && <p className="panel-shelf-muted">Загрузка…</p>}
      {!loading && notes.length === 0 && <p className="panel-shelf-muted">Заметок нет</p>}

      <div className="pu-notes-list">
        {notes.map((n) => (
          <div key={n.id} className="pu-note-card">
            <div className="pu-note-head">
              <span className="pu-note-admin">{n.adminName || `Admin ${n.adminUserId}`}</span>
              <time className="pu-note-time">{formatDate(n.createdAt)}</time>
              <div className="pu-note-actions">
                <button
                  className="pu-note-btn"
                  onClick={() => { setEditingId(n.id); setText(n.text) }}
                  disabled={saving}
                >
                  ✏️
                </button>
                <button
                  className="pu-note-btn pu-note-btn-del"
                  onClick={() => handleDelete(n.id)}
                  disabled={saving}
                >
                  🗑
                </button>
              </div>
            </div>
            <p className="pu-note-text">{n.text}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---- Dex item picker for quick item give ----
function DexItemQuickPicker({ dexItems, onSelect, disabled }) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = dexItems.filter((i) => {
    const q = search.toLowerCase()
    return !q || i.name.toLowerCase().includes(q) || String(i.id).includes(q) || (i.emoji || '').includes(q)
  }).slice(0, 30)

  return (
    <div className="pu-dex-picker" ref={ref}>
      <input
        className="panel-users-input"
        placeholder="Поиск предмета…"
        value={search}
        onChange={(e) => { setSearch(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        disabled={disabled}
      />
      {open && filtered.length > 0 && (
        <div className="pu-dex-picker-dropdown">
          {filtered.map((item) => (
            <button
              key={item.id}
              className="pu-dex-picker-item"
              onMouseDown={(e) => {
                e.preventDefault()
                onSelect(String(item.id), item)
                setSearch(`${item.emoji} ${item.name}`)
                setOpen(false)
              }}
            >
              <span className="pu-dex-picker-emoji">{item.emoji}</span>
              <span className="pu-dex-picker-name">{item.name}</span>
              <span className="pu-dex-picker-id">#{item.id}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ---- Полная история кут (cutehistory + donate + переводы) ----
const CUTE_PAGE = 50

function CounterpartyLine({ direction, cp }) {
  const name = cp.username ? `@${cp.username}` : (cp.name || 'игрок')
  const arrow = direction === 'out' ? '→' : '←'
  return (
    <p className="panel-shelf-muted">
      {arrow} {name} <span style={{ opacity: 0.6 }}>(id {cp.userId})</span>
    </p>
  )
}

function CuteHistoryFeed({ userId }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [donations, setDonations] = useState(null)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // filters
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [direction, setDirection] = useState('')      // '' | 'in' | 'out'
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [onlyTransfers, setOnlyTransfers] = useState(false)

  // debounce the free-text cause search so typing doesn't fire a request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 350)
    return () => clearTimeout(t)
  }, [q])

  // Monotonically-increasing counter: if a newer request lands before an older
  // one resolves, the older result is discarded (no stale overwrites).
  const loadReqRef = useRef(0)

  const load = useCallback(async (nextOffset) => {
    const reqId = ++loadReqRef.current
    setLoading(true)
    setError('')
    try {
      const data = await fetchAdminUserCuteHistory(userId, {
        dateFrom, dateTo, direction, q: debouncedQ, onlyTransfers,
        limit: CUTE_PAGE, offset: nextOffset,
      })
      if (reqId !== loadReqRef.current) return  // stale - newer request is in flight
      setTotal(data.total || 0)
      setDonations(data.donations || null)
      setItems((prev) => nextOffset === 0 ? (data.items || []) : [...prev, ...(data.items || [])])
      setOffset(nextOffset)
    } catch (e) {
      if (reqId !== loadReqRef.current) return
      setError(e.message || 'Ошибка загрузки')
    } finally {
      if (reqId === loadReqRef.current) setLoading(false)
    }
  }, [userId, dateFrom, dateTo, direction, debouncedQ, onlyTransfers])

  // первичная загрузка и перезагрузка при смене фильтров
  useEffect(() => { load(0) }, [load])

  return (
    <div className="pu-cute">
      <div className="pu-cute-filters">
        <input type="date" className="panel-users-input" value={dateFrom}
               onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" className="panel-users-input" value={dateTo}
               onChange={(e) => setDateTo(e.target.value)} />
        <select className="panel-users-input" value={direction}
                onChange={(e) => setDirection(e.target.value)}>
          <option value="">Все</option>
          <option value="in">Начисления</option>
          <option value="out">Списания</option>
        </select>
        <input className="panel-users-input" placeholder="Поиск по причине…" value={q}
               onChange={(e) => setQ(e.target.value)} />
        <label className="pu-cute-check">
          <input type="checkbox" checked={onlyTransfers}
                 onChange={(e) => setOnlyTransfers(e.target.checked)} />
          Только переводы
        </label>
      </div>

      {donations && (
        <div className="pu-cute-donations">
          💜 Донаты: {donations.count} шт · {donations.total.toLocaleString('ru-RU')} кут
          <span className="pu-cute-donations-hint"> (без дат — таблица их не хранит)</span>
        </div>
      )}

      {error && <p className="panel-shelf-error">{error}</p>}
      {!loading && items.length === 0 && <p className="panel-shelf-muted">Записей нет</p>}

      <ul className="panel-users-audit-list">
        {items.map((it, i) => (
          <li key={i} className="panel-users-audit-item">
            <div className="panel-users-audit-head">
              <span className="panel-users-audit-type">
                {it.cause || '—'}
                {it.kind === 'donate' && <span className="pu-cute-badge">донат</span>}
                {it.kind === 'transfer' && <span className="pu-cute-badge pu-cute-badge-tr">перевод</span>}
                {it.kind === 'chat_deposit' && <span className="pu-cute-badge pu-cute-badge-bch">бч</span>}
              </span>
              <time className="panel-users-audit-time">{formatDate(it.ts)}</time>
            </div>
            <p className={`panel-users-audit-amount ${it.direction === 'in' ? 'pu-cute-in' : 'pu-cute-out'}`}>
              {it.direction === 'in' ? '+' : '−'}{Math.abs(it.amount)} кут
            </p>
            {it.balance != null && (
              <p className="panel-shelf-muted">Баланс: {it.balance}</p>
            )}
            {it.counterparty && (
              <CounterpartyLine direction={it.direction} cp={it.counterparty} />
            )}
            {it.group && (
              <p className="panel-shelf-muted">
                → группа {it.group.name || '—'}
                {it.group.username ? ` @${it.group.username}` : ''}{' '}
                <span style={{ opacity: 0.6 }}>(id {it.group.chatId})</span>
              </p>
            )}
          </li>
        ))}
      </ul>

      {items.length < total && (
        <button className="panel-users-btn" disabled={loading}
                onClick={() => load(offset + CUTE_PAGE)}>
          {loading ? '…' : `Ещё (${items.length}/${total})`}
        </button>
      )}

      <style>{`
        .pu-cute-filters { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; align-items: center; }
        .pu-cute-filters .panel-users-input { flex: 1 1 120px; min-width: 100px; }
        .pu-cute-check { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #cccccc; white-space: nowrap; }
        .pu-cute-donations { font-size: 13px; color: #d29bff; background: #1a1420; border: 1px solid #2c2038; border-radius: 8px; padding: 8px 12px; margin-bottom: 10px; }
        .pu-cute-donations-hint { color: #7a7280; font-size: 11px; }
        .pu-cute-badge { margin-left: 6px; font-size: 10px; padding: 1px 6px; border-radius: 6px; background: #2a2a30; color: #d0a94a; vertical-align: middle; }
        .pu-cute-badge-tr { color: #6fb1ff; }
        .pu-cute-badge-bch { color: #57c785; }
        .pu-cute-in { color: #57c785; }
        .pu-cute-out { color: #e06666; }
      `}</style>
    </div>
  )
}

export default function UsersSection({ initialUserId = null, onInitialUserConsumed, permissions = [], role = null }) {
  const isOwner = role === 'owner'
  const perms = new Set(permissions)
  const canMutateEconomy = isOwner // обычные админы: всё видят, кут/предметы/ферму не меняют
  const canBan = perms.has('moderate_ban')
  const canUnban = perms.has('moderate_unban')
  const canBalance = canMutateEconomy
  const canItems = canMutateEconomy
  const canFarmControl = canMutateEconomy
  const canManageSettings = isOwner

  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [profile, setProfile] = useState(null)
  const [audit, setAudit] = useState(null)
  const [intel, setIntel] = useState(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [profileTab, setProfileTab] = useState('profile')
  const [historySource, setHistorySource] = useState('audit')  // 'audit' | 'cute'

  const [kutDelta, setKutDelta] = useState('')
  const [kutNote, setKutNote] = useState('')
  const [itemId, setItemId] = useState('')
  const [itemDelta, setItemDelta] = useState('')
  const [itemNote, setItemNote] = useState('')
  const [invAdjust, setInvAdjust] = useState(null)
  const [invQty, setInvQty] = useState('1')
  const [banReason, setBanReason] = useState('')
  const [banEvidence, setBanEvidence] = useState('')
  const [banPhotoIds, setBanPhotoIds] = useState([])
  const [unbanReason, setUnbanReason] = useState('')
  const [unbanEvidence, setUnbanEvidence] = useState('')
  const [unbanPhotoIds, setUnbanPhotoIds] = useState([])
  const [pendingAction, setPendingAction] = useState(null)

  // compare mode
  const [compareQuery, setCompareQuery] = useState('')
  const [compareResolvedId, setCompareResolvedId] = useState(null)
  const [compareProfile, setCompareProfile] = useState(null)
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareError, setCompareError] = useState('')
  const [showCompare, setShowCompare] = useState(false)

  // dex items for picker
  const [dexItems, setDexItems] = useState([])
  useEffect(() => {
    fetchContentDex({ limit: 100 }).then((d) => setDexItems(d.items || [])).catch(() => {})
  }, [])

  const hasProfile = Boolean(profile?.userId)
  const plots = profile?.plots || []
  const plotSlots = hasProfile
    ? Math.max(1, profile.maxPlots ?? PLOT_SLOTS_FALLBACK)
    : PLOT_SLOTS_FALLBACK

  // Monotonically-increasing counter: if a newer request lands before an older
  // one resolves, the older result is discarded (no stale overwrites).
  const loadReqRef = useRef(0)

  const loadUser = useCallback(async (userId) => {
    const reqId = ++loadReqRef.current
    setLoading(true)
    setResults([])
    setError('')
    setProfileTab('profile')
    setIntel(null)
    try {
      const [userData, auditData] = await Promise.all([
        fetchAdminUser(userId),
        fetchAdminUserAudit(userId, { limit: 30 }),
      ])
      if (reqId !== loadReqRef.current) return  // stale - newer request is in flight
      setProfile(userData)
      setAudit(auditData)
      setResults([])
      setBanPhotoIds([])
      setUnbanPhotoIds([])
      setLoading(false)

      fetchAdminUserIntel(userId)
        .then((intelData) => {
          if (reqId !== loadReqRef.current) return
          setIntel(intelData)
        })
        .catch(() => {
          if (reqId !== loadReqRef.current) return
          setIntel(null)
        })
    } catch (err) {
      if (reqId !== loadReqRef.current) return
      setError(err.message || 'Не удалось загрузить игрока')
      setProfile(null)
      setAudit(null)
      setIntel(null)
      setLoading(false)
    }
  }, [])

  const handleLoadCompare = useCallback(async () => {
    const uid = compareResolvedId || (/^\d+$/.test(compareQuery.trim()) ? Number(compareQuery.trim()) : null)
    setCompareLoading(true)
    setCompareError('')
    try {
      if (uid) {
        const userData = await fetchAdminUser(Number(uid))
        setCompareProfile(userData)
        return
      }
      const q = compareQuery.trim()
      if (!q) return
      const data = await searchAdminUsers(q)
      const list = data.results || []
      if (list.length === 0) { setCompareError('Никого не найдено'); return }
      if (list.length > 1) { setCompareError('Найдено несколько — выберите в превью'); return }
      const userData = await fetchAdminUser(list[0].userId)
      setCompareProfile(userData)
    } catch (e) {
      setCompareError(e.message || 'Ошибка')
    } finally {
      setCompareLoading(false)
    }
  }, [compareQuery, compareResolvedId])

  const handleExport = useCallback(async () => {
    if (!profile?.userId) return
    try {
      const data = await exportPlayerProfile(profile.userId)
      const json = JSON.stringify(data, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `player_${profile.userId}_export.json`
      a.click()
      URL.revokeObjectURL(url)
      notifyAdmin('Экспорт скачан')
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка экспорта', { error: true })
    }
  }, [profile?.userId])

  useEffect(() => {
    if (!initialUserId) return
    loadUser(initialUserId).finally(() => {
      onInitialUserConsumed?.()
    })
  }, [initialUserId, loadUser, onInitialUserConsumed])

  const handleSearch = useCallback(async () => {
    const q = query.trim()
    if (!q) return

    setLoading(true)
    setError('')
    setInfo('')

    try {
      const data = await searchAdminUsers(q)
      const list = data.results || []
      setResults(list)
      if (list.length === 1) {
        await loadUser(list[0].userId)
      } else if (list.length === 0) {
        setProfile(null)
        setAudit(null)
        setError('Никого не найдено')
      } else {
        setProfile(null)
        setAudit(null)
      }
    } catch (err) {
      setError(err.message || 'Ошибка поиска')
      setResults([])
      setProfile(null)
      setAudit(null)
    } finally {
      setLoading(false)
    }
  }, [query, loadUser])

  const reloadCurrent = useCallback(async () => {
    if (!profile?.userId) return
    await loadUser(profile.userId)
  }, [profile?.userId, loadUser])

  const runAction = useCallback(
    async (fn) => {
      if (!profile?.userId) return
      setActionLoading(true)
      setError('')
      setInfo('')
      try {
        await fn()
        setInfo('Готово')
        notifyAdmin('Готово')
        await reloadCurrent()
      } catch (err) {
        const message = err.message || 'Ошибка действия'
        setError(message)
        notifyAdmin(message, { error: true })
      } finally {
        setActionLoading(false)
      }
    },
    [profile?.userId, reloadCurrent],
  )

  return (
    <div className="panel-users">
      <AdminActionModal
        open={pendingAction === 'ban'}
        title="Забанить игрока?"
        description="Игрок потеряет доступ к игре и получит сообщение в боте."
        confirmText="Забанить"
        danger
        loading={actionLoading}
        onConfirm={() => {
          setPendingAction(null)
          runAction(() =>
            setAdminUserBanned(profile.userId, true, banReason, banEvidence, banPhotoIds[0] || ''),
          ).then(() => { setBanReason(''); setBanEvidence(''); setBanPhotoIds([]) })
        }}
        onCancel={() => {
          if (!actionLoading) setPendingAction(null)
        }}
      />
      <AdminActionModal
        open={pendingAction === 'unban'}
        title="Снять бан?"
        description="Игрок получит сообщение в игровом боте."
        confirmText="Снять бан"
        loading={actionLoading}
        onConfirm={() => {
          setPendingAction(null)
          runAction(() =>
            setAdminUserBanned(profile.userId, false, unbanReason, unbanEvidence, unbanPhotoIds[0] || ''),
          ).then(() => { setUnbanReason(''); setUnbanEvidence(''); setUnbanPhotoIds([]) })
        }}
        onCancel={() => {
          if (!actionLoading) setPendingAction(null)
        }}
      />
      <AdminActionModal
        open={pendingAction === 'onboarding'}
        title="Сбросить обучение?"
        description="Игрок получит сообщение в игровом боте."
        confirmText="Сбросить"
        danger
        loading={actionLoading}
        onConfirm={() => {
          setPendingAction(null)
          runAction(() => resetAdminUserOnboarding(profile.userId))
        }}
        onCancel={() => {
          if (!actionLoading) setPendingAction(null)
        }}
      />
      <article className="panel-shelf panel-shelf-page panel-users-search">
        <p className="panel-shelf-label">Игроки</p>
        <h2 className="panel-page-title">Поиск игрока</h2>
        <p className="panel-page-lead">Введите ID, @username или имя — минимум 2 символа</p>

        <form
          className="panel-users-search-form"
          onSubmit={(e) => {
            e.preventDefault()
            handleSearch()
          }}
        >
          <input
            className="panel-users-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="6801702632 или @username"
            disabled={loading}
          />
          <button type="submit" className="panel-users-btn panel-users-btn-primary" disabled={loading}>
            {loading ? '…' : 'Найти'}
          </button>
        </form>

        {results.length > 1 && !hasProfile && (
          <ul className="panel-users-results">
            {results.map((row) => (
              <li key={row.userId}>
                <button
                  type="button"
                  className="panel-users-result-btn"
                  onClick={() => loadUser(row.userId)}
                >
                  <span>
                    {row.displayName}
                    {row.username && ` @${row.username}`}
                  </span>
                  <span className="panel-users-result-meta">
                    ID {row.userId} · {row.balance} кут
                    {row.banned && ' · забанен'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
      </article>

      <div className={`panel-users-body${loading && !hasProfile ? ' panel-users-body-loading' : ''}`}>

        {/* ── Шапка с вкладками — вся ширина ── */}
        {hasProfile && (
          <div className="panel-shelf pu-tabs-bar">
            <div className="pu-profile-header">
              <p className="panel-shelf-label">Профиль · {profile?.displayName}</p>
              <div className="pu-profile-header-actions">
                <button className="pu-action-btn" onClick={() => setShowCompare((v) => !v)}>⚖️ Сравнить</button>
                <button className="pu-action-btn" onClick={handleExport}>📥 Экспорт</button>
              </div>
            </div>
            <div className="pu-tabs">
              {PROFILE_TABS.map((t) => (
                <button key={t.id} className={`pu-tab${profileTab === t.id ? ' active' : ''}`} onClick={() => setProfileTab(t.id)}>
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Контент вкладок (кроме профиля) — только своё, без наложений ── */}
        {hasProfile && profileTab === 'transfers' && (
          <div className="pu-tab-pane">
            <PlayerTransfersPanel userId={profile.userId} intel={intel} onOpenUser={(id) => id && loadUser(id)} />
          </div>
        )}
        {hasProfile && profileTab === 'intel' && (
          <div className="pu-tab-pane pu-tab-stack">
            <PlayerIntelOverview intel={intel} onOpenUser={(id) => id && loadUser(id)} />
            <PlayerDossierPanel
              intel={intel}
              isOwner={isOwner}
              canEdit={isOwner}
              onSaved={() => loadUser(profile.userId)}
            />
          </div>
        )}
        {hasProfile && profileTab === 'farm' && (
          <article className="panel-shelf panel-users-card pu-tab-pane">
            <FarmControlTab
              userId={profile.userId}
              profile={profile}
              canControl={canFarmControl}
              onChanged={() => loadUser(profile.userId)}
            />
          </article>
        )}
        {hasProfile && profileTab === 'history' && (
          <article className="panel-shelf panel-users-card pu-tab-pane pu-history-tab">
            <div className="pu-bento-head">
              <div>
                <p className="panel-shelf-label">История</p>
                <h3 className="panel-users-subtitle">
                  {historySource === 'audit'
                    ? `События (${audit?.total ?? 0})`
                    : 'кут — полная история'}
                </h3>
              </div>
            </div>

            {hasProfile && (
              <div className="pu-hist-switch">
                <button
                  type="button"
                  className={`pu-hist-tab${historySource === 'audit' ? ' active' : ''}`}
                  onClick={() => setHistorySource('audit')}
                >Действия</button>
                <button
                  type="button"
                  className={`pu-hist-tab${historySource === 'cute' ? ' active' : ''}`}
                  onClick={() => setHistorySource('cute')}
                >кут (полная)</button>
              </div>
            )}

            {historySource === 'cute' && (
              <CuteHistoryFeed userId={profile.userId} />
            )}

            {historySource === 'audit' && (
              <>
                {(audit?.events || []).length === 0 && (
                  <p className="panel-shelf-muted">Записей пока нет</p>
                )}
                {(audit?.events || []).length > 0 && (
                  <ul className="panel-users-audit-list">
                    {audit.events.map((ev) => (
                      <li key={ev.id} className="panel-users-audit-item">
                        <div className="panel-users-audit-head">
                          <span className="panel-users-audit-type">
                            {EVENT_LABELS[ev.eventType] || ev.eventType}
                          </span>
                          <time className="panel-users-audit-time">{formatDate(ev.createdAt)}</time>
                        </div>
                        {ev.amount != null && (
                          <p className="panel-users-audit-amount">
                            {ev.amount > 0 ? '+' : ''}
                            {ev.amount} кут
                          </p>
                        )}
                        {ev.balanceBefore != null && ev.balanceAfter != null && (
                          <p className="panel-shelf-muted">
                            Баланс: {ev.balanceBefore} → {ev.balanceAfter}
                          </p>
                        )}
                        {ev.details?.item_id && (
                          <p className="panel-shelf-muted">
                            Предмет: {ev.details.item_id}
                            {ev.details.count_after != null && ` (осталось ${ev.details.count_after})`}
                          </p>
                        )}
                        {ev.details?.admin_user_id && (
                          <p className="panel-shelf-muted">Admin ID: {ev.details.admin_user_id}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </article>
        )}
        {hasProfile && profileTab === 'quests' && (
          <div className="pu-tab-pane panel-shelf panel-users-card">
            <QuestsTab userId={profile.userId} />
          </div>
        )}
        {hasProfile && profileTab === 'bans' && (
          <div className="pu-tab-pane panel-shelf panel-users-card">
            <BansTab userId={profile.userId} />
          </div>
        )}
        {hasProfile && profileTab === 'inventory' && (
          <div className="pu-tab-pane panel-shelf panel-users-card">
            <InventoryTab
              userId={profile.userId}
              canMutate={canItems}
              onChanged={() => loadUser(profile.userId)}
            />
          </div>
        )}
        {hasProfile && profileTab === 'notes' && (
          <div className="pu-tab-pane panel-shelf panel-users-card">
            <NotesTab userId={profile.userId} />
          </div>
        )}

        {/* ── Вкладка «Профиль»: только карточка + инвентарь + действия ── */}
        {(profileTab === 'profile' || !hasProfile) && (
        <div className="pu-profile-layout">
        <article className="panel-shelf panel-users-card panel-users-profile-card pu-hero-card">
          <div className="pu-hero-banner">
            <div className="pu-hero-banner-glow" aria-hidden />
            <div className="pu-hero-main">
              <div className="panel-users-avatar-wrap">
                {profile?.photoUrl ? (
                  <img className="panel-users-avatar" src={profile.photoUrl} alt="" />
                ) : (
                  <div className="panel-users-avatar panel-users-avatar-fallback" aria-hidden="true">
                    {hasProfile ? initialsFromName(profile.displayName) : '?'}
                  </div>
                )}
                {hasProfile && (
                  <span className={`pu-hero-status-dot${profile.banned ? ' is-ban' : ' is-ok'}`} aria-hidden />
                )}
              </div>

              <div className="pu-hero-identity">
                <p className="pu-hero-kicker">Карточка пользователя</p>
                <h3 className={`panel-users-name${!hasProfile ? ' panel-users-placeholder' : ''}`}>
                  {hasProfile ? profile.displayName : 'Игрок не выбран'}
                </h3>
                <div className="pu-hero-meta-row">
                  {hasProfile && profile.username ? (
                    <span className="pu-hero-chip">@{profile.username}</span>
                  ) : null}
                  <span className="pu-hero-chip pu-hero-chip-id">
                    ID {hasProfile ? profile.userId : '—'}
                  </span>
                  {hasProfile && profile.banned && (
                    <span className="panel-users-badge panel-users-badge-ban">BAN</span>
                  )}
                  {hasProfile && !profile.banned && (
                    <span className="pu-hero-chip pu-hero-chip-ok">активен</span>
                  )}
                  {intel?.dossier?.country && (
                    <span className="pu-hero-chip">{intel.dossier.country}</span>
                  )}
                </div>
                {hasProfile && (
                  <p className="pu-hero-seen">
                    {profile.lastSeenAt ? `Был в сети: ${formatDate(profile.lastSeenAt)}` : 'Активность неизвестна'}
                    {intel?.dossier?.registeredAtLabel ? ` · с ${intel.dossier.registeredAtLabel}` : ''}
                    {intel?.dossier?.accountAge ? ` · ${intel.dossier.accountAge}` : ''}
                  </p>
                )}
              </div>

              <div className="pu-hero-balance">
                <span className="pu-hero-balance-label">Баланс кут</span>
                <strong className={`pu-hero-balance-value${!hasProfile ? ' panel-users-placeholder' : ''}`}>
                  {hasProfile ? profile.balance?.toLocaleString('ru-RU') : '—'}
                </strong>
                <span className="pu-hero-balance-sub">
                  {intel?.dossier?.donated
                    ? `донат ${Number(intel.dossier.donated).toLocaleString('ru-RU')}`
                    : 'игровой баланс'}
                </span>
              </div>
            </div>

            <div className="panel-users-stats pu-hero-keystats">
              <div>
                <span className="panel-users-stat-label">Грядки</span>
                <strong className={!hasProfile ? 'panel-users-placeholder' : ''}>
                  {hasProfile ? `${profile.ownedPlots}/${profile.maxPlots}` : '—'}
                </strong>
              </div>
              <div>
                <span className="panel-users-stat-label">Биржа</span>
                <strong className={!hasProfile ? 'panel-users-placeholder' : ''}>
                  {hasProfile ? profile.marketSalesCount ?? 0 : '—'}
                </strong>
              </div>
              <div>
                <span className="panel-users-stat-label">Wins / Losses</span>
                <strong>
                  {hasProfile
                    ? `${Number(intel?.dossier?.wins ?? 0).toLocaleString('ru-RU')} / ${Number(intel?.dossier?.losses ?? 0).toLocaleString('ru-RU')}`
                    : '—'}
                </strong>
              </div>
              <div>
                <span className="panel-users-stat-label">Сообщения · 30д</span>
                <strong>
                  {hasProfile
                    ? (intel?.activity30d?.totalMessages != null
                      ? Number(intel.activity30d.totalMessages).toLocaleString('ru-RU')
                      : '…')
                    : '—'}
                </strong>
              </div>
            </div>

            {hasProfile && intel?.activity30d?.mostActive && (
              <div className="pu-hero-active-group">
                <span>Самая активная группа</span>
                <strong>{intel.activity30d.mostActive.chatName}</strong>
                <em>{intel.activity30d.mostActive.messages.toLocaleString('ru-RU')} сообщ.</em>
              </div>
            )}

            {hasProfile && intel && (
              <div className="pu-hero-dossier-wrap">
                <p className="pu-hero-section-title">Основное о пользователе</p>
                <PlayerDossierPanel
                  intel={intel}
                  isOwner={isOwner}
                  canEdit={false}
                  compact
                />
              </div>
            )}

            {hasProfile && profile.banned && profile.bannedReason && (
              <p className="panel-users-ban-reason">Причина бана: {profile.bannedReason}</p>
            )}

            {!hasProfile && !loading && (
              <EmptyHint>Найди игрока — карточка заполнится здесь</EmptyHint>
            )}
          </div>
        </article>

        <div className="panel-users-right">
          <article className="panel-shelf panel-users-card panel-users-inventory-card pu-inv-card">
            <div className="pu-bento-head">
              <div>
                <p className="panel-shelf-label">Инвентарь</p>
                <h3 className="panel-users-subtitle panel-users-subtitle-tight">Предметы</h3>
              </div>
              {hasProfile && (
                <span className="pu-bento-chip">{(profile.inventory || []).length}</span>
              )}
            </div>

            {!hasProfile && (
              <ul className="panel-users-inv-list panel-users-inv-list-empty">
                {[1, 2, 3].map((n) => (
                  <li key={n} className="panel-users-inv-ghost">
                    <span className="panel-users-ghost-bar" />
                  </li>
                ))}
              </ul>
            )}

            {hasProfile && (profile.inventory || []).length === 0 && (
              <p className="panel-shelf-muted">Пусто</p>
            )}

            {hasProfile && (profile.inventory || []).length > 0 && (
              <ul className="panel-users-inv-list">
                {profile.inventory.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="pu-inv-row pu-inv-row-btn"
                      disabled={!canItems || actionLoading}
                      onClick={() => {
                        if (!canItems) return
                        setInvAdjust(item)
                        setInvQty('1')
                        setItemId(String(item.id))
                      }}
                    >
                      <span className="pu-inv-emoji">{item.emoji}</span>
                      <span className="pu-inv-name">{item.name}</span>
                      <span className="pu-inv-count">×{item.count}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {invAdjust && canItems && (
              <div className="pu-inv-popover" role="dialog" aria-label="Изменить предмет">
                <div className="pu-inv-popover-head">
                  <strong>{invAdjust.emoji} {invAdjust.name}</strong>
                  <button type="button" className="pu-close-btn" onClick={() => setInvAdjust(null)}>✕</button>
                </div>
                <p className="panel-shelf-muted">Сейчас ×{invAdjust.count}</p>
                <label className="pu-field">
                  <span className="pu-field-label">Количество</span>
                  <input
                    className="panel-users-input pu-field-input"
                    value={invQty}
                    onChange={(e) => setInvQty(e.target.value.replace(/\D/g, ''))}
                    inputMode="numeric"
                    placeholder="1"
                  />
                </label>
                <div className="pu-kut-actions">
                  <button
                    type="button"
                    className="panel-users-btn panel-users-btn-success"
                    disabled={actionLoading || !Number(invQty)}
                    onClick={() => {
                      const q = Number.parseInt(invQty, 10)
                      if (!q) return
                      runAction(() => adjustAdminUserItem(profile.userId, String(invAdjust.id), q, ''))
                        .then(() => setInvAdjust(null))
                    }}
                  >
                    Выдать
                  </button>
                  <button
                    type="button"
                    className="panel-users-btn panel-users-btn-danger"
                    disabled={actionLoading || !Number(invQty)}
                    onClick={() => {
                      const q = Number.parseInt(invQty, 10)
                      if (!q) return
                      runAction(() => adjustAdminUserItem(profile.userId, String(invAdjust.id), -q, ''))
                        .then(() => setInvAdjust(null))
                    }}
                  >
                    Забрать
                  </button>
                </div>
              </div>
            )}

            {!hasProfile && !loading && (
              <EmptyHint>Список предметов после поиска</EmptyHint>
            )}
          </article>

          <article className="panel-shelf panel-users-card panel-users-actions-card">
            <div className="pu-bento-head">
              <div>
                <p className="panel-shelf-label">Действия</p>
                <h3 className="panel-users-subtitle panel-users-subtitle-tight">
                  {isOwner || canBalance || canItems || canBan || canUnban || canManageSettings
                    ? 'Выдача и модерация'
                    : 'Только просмотр'}
                </h3>
              </div>
              <span className="pu-bento-chip">{isOwner ? 'owner' : 'ops'}</span>
            </div>

            {!(canBalance || canItems || canBan || canUnban || canManageSettings) && (
              <p className="panel-shelf-muted">У вашей роли нет прав на изменение игрока — доступно только чтение досье и истории.</p>
            )}

            <div className="panel-users-action-grid">
              {canBalance && (
              <div className="panel-users-action-block pu-action-tile pu-action-tile-kut">
                <div className="pu-action-tile-top">
                  <span className="pu-action-ico" aria-hidden>◈</span>
                  <div>
                    <p className="panel-users-action-title">Баланс кут</p>
                    <p className="pu-action-hint">Выдать или забрать</p>
                  </div>
                </div>
                <label className="pu-field">
                  <span className="pu-field-label">Сумма</span>
                  <div className="pu-stepper">
                    <button
                      type="button"
                      className="pu-stepper-btn"
                      disabled={!hasProfile || actionLoading}
                      onClick={() => {
                        const n = Math.abs(Number.parseInt(kutDelta, 10) || 0)
                        setKutDelta(String(Math.max(0, n - 50)))
                      }}
                      aria-label="Минус 50"
                    >−</button>
                    <input
                      className="panel-users-input pu-field-input"
                      value={kutDelta}
                      onChange={(e) => setKutDelta(e.target.value.replace(/\D/g, ''))}
                      placeholder="100"
                      inputMode="numeric"
                      disabled={!hasProfile || actionLoading}
                    />
                    <button
                      type="button"
                      className="pu-stepper-btn"
                      disabled={!hasProfile || actionLoading}
                      onClick={() => {
                        const n = Math.abs(Number.parseInt(kutDelta, 10) || 0)
                        setKutDelta(String(n + 50))
                      }}
                      aria-label="Плюс 50"
                    >+</button>
                  </div>
                </label>
                <label className="pu-field">
                  <span className="pu-field-label">Сообщение в боте</span>
                  <input
                    className="panel-users-input pu-field-input"
                    value={kutNote}
                    onChange={(e) => setKutNote(e.target.value)}
                    placeholder="Необязательно"
                    disabled={!hasProfile || actionLoading}
                  />
                </label>
                <div className="pu-kut-actions">
                  <button
                    type="button"
                    className="panel-users-btn panel-users-btn-success"
                    disabled={!hasProfile || actionLoading || !Number(kutDelta)}
                    onClick={() => {
                      const amount = Math.abs(Number.parseInt(kutDelta, 10))
                      if (!amount) return
                      runAction(() => adjustAdminUserBalance(profile.userId, amount, kutNote.trim()))
                      setKutDelta('')
                      setKutNote('')
                    }}
                  >
                    Выдать
                  </button>
                  <button
                    type="button"
                    className="panel-users-btn panel-users-btn-danger"
                    disabled={!hasProfile || actionLoading || !Number(kutDelta)}
                    onClick={() => {
                      const amount = Math.abs(Number.parseInt(kutDelta, 10))
                      if (!amount) return
                      runAction(() => adjustAdminUserBalance(profile.userId, -amount, kutNote.trim()))
                      setKutDelta('')
                      setKutNote('')
                    }}
                  >
                    Забрать
                  </button>
                </div>
              </div>
              )}

              {canItems && (
              <div className="panel-users-action-block pu-action-tile pu-action-tile-item">
                <div className="pu-action-tile-top">
                  <span className="pu-action-ico" aria-hidden>▣</span>
                  <div>
                    <p className="panel-users-action-title">Предмет</p>
                    <p className="pu-action-hint">Выдать или забрать</p>
                  </div>
                </div>
                <div className="pu-field">
                  <span className="pu-field-label">Поиск в дексе</span>
                  <DexItemQuickPicker
                    dexItems={dexItems}
                    onSelect={(id) => setItemId(id)}
                    disabled={!hasProfile || actionLoading}
                  />
                </div>
                <div className="pu-field-row">
                  <label className="pu-field">
                    <span className="pu-field-label">ID</span>
                    <input
                      className="panel-users-input pu-field-input"
                      value={itemId}
                      onChange={(e) => setItemId(e.target.value)}
                      placeholder="item_id"
                      disabled={!hasProfile || actionLoading}
                    />
                  </label>
                  <label className="pu-field">
                    <span className="pu-field-label">Кол-во</span>
                    <input
                      className="panel-users-input pu-field-input"
                      value={itemDelta}
                      onChange={(e) => setItemDelta(e.target.value.replace(/\D/g, ''))}
                      placeholder="1"
                      inputMode="numeric"
                      disabled={!hasProfile || actionLoading}
                    />
                  </label>
                </div>
                <label className="pu-field">
                  <span className="pu-field-label">Сообщение в боте</span>
                  <input
                    className="panel-users-input pu-field-input"
                    value={itemNote}
                    onChange={(e) => setItemNote(e.target.value)}
                    placeholder="Необязательно"
                    disabled={!hasProfile || actionLoading}
                  />
                </label>
                <div className="pu-kut-actions">
                  <button
                    type="button"
                    className="panel-users-btn panel-users-btn-success"
                    disabled={!hasProfile || actionLoading || !itemId.trim() || !Number(itemDelta)}
                    onClick={() => {
                      const amount = Math.abs(Number.parseInt(itemDelta, 10))
                      if (!itemId.trim() || !amount) return
                      runAction(() =>
                        adjustAdminUserItem(profile.userId, itemId.trim(), amount, itemNote.trim()),
                      )
                      setItemDelta('')
                      setItemNote('')
                    }}
                  >
                    Выдать
                  </button>
                  <button
                    type="button"
                    className="panel-users-btn panel-users-btn-danger"
                    disabled={!hasProfile || actionLoading || !itemId.trim() || !Number(itemDelta)}
                    onClick={() => {
                      const amount = Math.abs(Number.parseInt(itemDelta, 10))
                      if (!itemId.trim() || !amount) return
                      runAction(() =>
                        adjustAdminUserItem(profile.userId, itemId.trim(), -amount, itemNote.trim()),
                      )
                      setItemDelta('')
                      setItemNote('')
                    }}
                  >
                    Забрать
                  </button>
                </div>
              </div>
              )}

              {canBan && (
              <div className="panel-users-action-block pu-action-tile pu-action-tile-ban">
                <div className="pu-action-tile-top">
                  <span className="pu-action-ico pu-action-ico-danger" aria-hidden>✕</span>
                  <div>
                    <p className="panel-users-action-title">Бан</p>
                    <p className="pu-action-hint">Блокировка в боте</p>
                  </div>
                </div>
                <label className="pu-field">
                  <span className="pu-field-label">Причина</span>
                  <input
                    className="panel-users-input pu-field-input"
                    value={banReason}
                    onChange={(e) => setBanReason(e.target.value)}
                    placeholder="Уйдёт игроку в бот"
                    disabled={!hasProfile || actionLoading || (hasProfile && profile.banned)}
                  />
                </label>
                <label className="pu-field">
                  <span className="pu-field-label">Доказательства</span>
                  <textarea
                    className="panel-users-input pu-field-input pu-field-area"
                    rows={2}
                    value={banEvidence}
                    onChange={(e) => setBanEvidence(e.target.value)}
                    placeholder="Текст или ссылки"
                    disabled={!hasProfile || actionLoading || (hasProfile && profile.banned)}
                  />
                </label>
                <EvidencePhotoPicker
                  key={`ban-${profile?.userId ?? 'empty'}`}
                  fileIds={banPhotoIds}
                  onChange={setBanPhotoIds}
                  disabled={!hasProfile || actionLoading || (hasProfile && profile.banned)}
                />
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-danger pu-action-cta"
                  disabled={
                    !hasProfile || actionLoading || (hasProfile && profile.banned) ||
                    !banReason.trim() || (!banEvidence.trim() && banPhotoIds.length === 0)
                  }
                  onClick={() => setPendingAction('ban')}
                >
                  Забанить
                </button>
              </div>
              )}

              {canUnban && (
              <div className="panel-users-action-block pu-action-tile pu-action-tile-unban">
                <div className="pu-action-tile-top">
                  <span className="pu-action-ico pu-action-ico-ok" aria-hidden>✓</span>
                  <div>
                    <p className="panel-users-action-title">Разбан</p>
                    <p className="pu-action-hint">Вернуть доступ</p>
                  </div>
                </div>
                {hasProfile && profile.banned && profile.bannedReason && (
                  <p className="pu-ban-reason-pill">Был бан: {profile.bannedReason}</p>
                )}
                <label className="pu-field">
                  <span className="pu-field-label">Причина</span>
                  <input
                    className="panel-users-input pu-field-input"
                    value={unbanReason}
                    onChange={(e) => setUnbanReason(e.target.value)}
                    placeholder="Причина разбана"
                    disabled={!hasProfile || actionLoading || (hasProfile && !profile.banned)}
                  />
                </label>
                <label className="pu-field">
                  <span className="pu-field-label">Обоснование</span>
                  <textarea
                    className="panel-users-input pu-field-input pu-field-area"
                    rows={2}
                    value={unbanEvidence}
                    onChange={(e) => setUnbanEvidence(e.target.value)}
                    placeholder="Кратко по делу"
                    disabled={!hasProfile || actionLoading || (hasProfile && !profile.banned)}
                  />
                </label>
                <EvidencePhotoPicker
                  key={`unban-${profile?.userId ?? 'empty'}`}
                  fileIds={unbanPhotoIds}
                  onChange={setUnbanPhotoIds}
                  disabled={!hasProfile || actionLoading || (hasProfile && !profile.banned)}
                />
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-success pu-action-cta"
                  disabled={
                    !hasProfile || actionLoading || (hasProfile && !profile.banned) ||
                    !unbanReason.trim() || (!unbanEvidence.trim() && unbanPhotoIds.length === 0)
                  }
                  onClick={() => setPendingAction('unban')}
                >
                  Снять бан
                </button>
              </div>
              )}

              {canManageSettings && (
              <div className="panel-users-action-block pu-action-tile pu-action-tile-onboard">
                <div className="pu-action-tile-top">
                  <span className="pu-action-ico" aria-hidden>↻</span>
                  <div>
                    <p className="panel-users-action-title">Обучение</p>
                    <p className="pu-action-hint">Сброс + грядка №1</p>
                  </div>
                </div>
                <button
                  type="button"
                  className="panel-users-btn pu-action-cta"
                  disabled={!hasProfile || actionLoading}
                  onClick={() => setPendingAction('onboarding')}
                >
                  Сбросить обучение
                </button>
              </div>
              )}
            </div>
          </article>
        </div>
        </div>
        )}

        {/* Compare panel */}
        {showCompare && hasProfile && profileTab === 'profile' && (
          <article className="panel-shelf panel-users-card pu-compare-card">
            <div className="pu-compare-head">
              <p className="panel-shelf-label">⚖️ Сравнение</p>
              <button className="pu-close-btn" onClick={() => { setShowCompare(false); setCompareProfile(null) }}>✕</button>
            </div>
            <form
              className="panel-users-search-form"
              onSubmit={(e) => { e.preventDefault(); handleLoadCompare() }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <UserLookupPreview
                  label="Сравнить с"
                  value={compareQuery}
                  onChange={(v) => { setCompareQuery(v); setCompareResolvedId(null) }}
                  onResolved={(u) => setCompareResolvedId(u ? Number(u.userId || u.user_id) : null)}
                  onOpenUser={(id) => loadUser(id)}
                  placeholder="ID, @username или имя"
                />
              </div>
              <button type="submit" className="panel-users-btn panel-users-btn-primary" disabled={compareLoading}>
                {compareLoading ? '…' : 'Найти'}
              </button>
            </form>
            {compareError && <p className="panel-shelf-error">{compareError}</p>}
            {compareProfile && (
              <div className="pu-compare-body">
                <div className="pu-compare-col">
                  <p className="pu-compare-name">{profile.displayName}</p>
                  <p className="pu-compare-stat">💰 {profile.balance?.toLocaleString('ru-RU')}</p>
                  <p className="pu-compare-stat">🌱 {profile.ownedPlots}/{profile.maxPlots}</p>
                  <p className="pu-compare-stat">📦 {(profile.inventory || []).length} видов</p>
                  <p className="pu-compare-stat">{profile.banned ? '🔴 Забанен' : '🟢 Активен'}</p>
                </div>
                <div className="pu-compare-vs">VS</div>
                <div className="pu-compare-col">
                  <p className="pu-compare-name">{compareProfile.displayName}</p>
                  <p className="pu-compare-stat">💰 {compareProfile.balance?.toLocaleString('ru-RU')}</p>
                  <p className="pu-compare-stat">🌱 {compareProfile.ownedPlots}/{compareProfile.maxPlots}</p>
                  <p className="pu-compare-stat">📦 {(compareProfile.inventory || []).length} видов</p>
                  <p className="pu-compare-stat">{compareProfile.banned ? '🔴 Забанен' : '🟢 Активен'}</p>
                </div>
              </div>
            )}
          </article>
        )}
      </div>
    </div>
  )
}
