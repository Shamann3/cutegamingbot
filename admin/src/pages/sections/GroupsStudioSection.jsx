import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchGroupsStudioOverview,
  fetchGroupsStudioDetail,
  searchGroupsStudio,
  setGroupsStudioBalance,
  setGroupsStudioLevel,
  groupsStudioModerate,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'

function fmt(n, digits = 0) {
  const v = Number(n) || 0
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: digits }).format(v)
}

function stars(n) {
  const v = Math.max(0, Math.min(5, Number(n) || 0))
  return `${'★'.repeat(v)}${'☆'.repeat(5 - v)}`
}

function shortWhen(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
  } catch {
    return String(iso).slice(0, 16)
  }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(String(text))
    notifyAdmin('Скопировано')
  } catch {
    notifyAdmin('Не удалось скопировать', { error: true })
  }
}

function Stat({ label, value, hint, delay = 0 }) {
  return (
    <div className="grp-stat" style={{ animationDelay: `${delay}ms` }}>
      <span className="grp-stat-label">{label}</span>
      <strong className="grp-stat-value">{value}</strong>
      {hint ? <span className="grp-stat-hint">{hint}</span> : null}
    </div>
  )
}

function Meter({ label, display, hint, fill = 0, tone = 'mint' }) {
  const v = Math.max(0, Math.min(100, Number(fill) || 0))
  return (
    <div className="grp-meter">
      <div className="grp-meter-head">
        <span>{label}</span>
        <strong>{display}</strong>
      </div>
      {hint ? <div className="grp-meter-hint">{hint}</div> : null}
      <div className="grp-meter-track">
        <div className={`grp-meter-fill grp-meter-${tone}`} style={{ width: `${v}%` }} />
      </div>
    </div>
  )
}

function RangeField({ label, value, min, max, step = 1, onChange, display, marks }) {
  return (
    <label className="grp-range">
      <div className="grp-range-head">
        <span>{label}</span>
        <strong>{display ?? value}</strong>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {marks ? <div className="grp-range-marks">{marks}</div> : null}
    </label>
  )
}

function Chip({ children, onClick, tone }) {
  return (
    <button type="button" className={`grp-chip${tone ? ` grp-chip-${tone}` : ''}`} onClick={onClick}>
      {children}
    </button>
  )
}

function PersonLine({ title, person }) {
  if (!person) return <p className="grp-help">{title}: —</p>
  const uname = person.username ? `@${String(person.username).replace(/^@/, '')}` : null
  return (
    <div className="grp-person">
      <span className="grp-person-role">{title}</span>
      <strong>{person.name}</strong>
      <span>{uname || person.user_id}</span>
      <Chip onClick={() => copyText(person.user_id)}>id</Chip>
    </div>
  )
}

function RankRow({ item, metric, onOpen, index = 0 }) {
  return (
    <button
      type="button"
      className="grp-rank-row"
      style={{ animationDelay: `${index * 40}ms` }}
      onClick={() => onOpen(item.chat_id)}
    >
      <span className="grp-rank-idx">{index + 1}</span>
      <span className="grp-rank-name">{item.name}</span>
      <span className="grp-rank-meta">
        {item.username ? `@${String(item.username).replace(/^@/, '')}` : item.chat_id}
      </span>
      <span className="grp-rank-metric">{metric}</span>
    </button>
  )
}

function MiniTable({ columns, rows, empty = 'Пусто' }) {
  if (!rows?.length) return <p className="grp-help">{empty}</p>
  return (
    <div className="grp-table-wrap">
      <table className="grp-table">
        <thead>
          <tr>
            {columns.map((c) => <th key={c.key}>{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row._key || i} style={{ animationDelay: `${i * 28}ms` }}>
              {columns.map((c) => (
                <td key={c.key}>{c.render ? c.render(row) : row[c.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const BALANCE_MAX = 500_000
const MUTE_PRESETS = [
  { label: '1ч', h: 1 },
  { label: '6ч', h: 6 },
  { label: '24ч', h: 24 },
  { label: '3д', h: 72 },
  { label: '7д', h: 168 },
  { label: 'навсегда', h: 0 },
]

export default function GroupsStudioSection() {
  const [tab, setTab] = useState('lookup')
  const [sub, setSub] = useState('overview')
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState([])
  const [searching, setSearching] = useState(false)
  const [detail, setDetail] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [balanceDraft, setBalanceDraft] = useState(0)
  const [levelDraft, setLevelDraft] = useState(0)
  const [saving, setSaving] = useState(false)
  const [modUser, setModUser] = useState('')
  const [modAction, setModAction] = useState('mute')
  const [modHours, setModHours] = useState(24)
  const [modReason, setModReason] = useState('')
  const [modding, setModding] = useState(false)
  const [rawOpen, setRawOpen] = useState(false)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchGroupsStudioOverview()
      setOverview(data)
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadOverview() }, [loadOverview])

  const openChat = useCallback(async (chatId) => {
    setLoadingDetail(true)
    setTab('detail')
    setSub('overview')
    try {
      const data = await fetchGroupsStudioDetail(chatId)
      setDetail(data)
      setBalanceDraft(Math.round(Number(data?.chat?.chatbalance ?? 0)))
      setLevelDraft(Number(data?.chat?.level || 0))
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  const onSearch = async (e) => {
    e?.preventDefault?.()
    if (!query.trim()) return
    setSearching(true)
    try {
      const data = await searchGroupsStudio(query.trim())
      const items = Array.isArray(data?.items) ? data.items : []
      setHits(items)
      if (items.length === 1) await openChat(items[0].chat_id)
      else if (!items.length) notifyAdmin('Ничего не найдено', { error: true })
    } catch (err) {
      notifyAdmin(String(err?.message || err), { error: true })
    } finally {
      setSearching(false)
    }
  }

  const onSaveBalance = async () => {
    if (!detail?.chat?.chat_id) return
    setSaving(true)
    try {
      await setGroupsStudioBalance(detail.chat.chat_id, Number(balanceDraft))
      notifyAdmin('Баланс группы обновлён')
      await openChat(detail.chat.chat_id)
      await loadOverview()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onSaveLevel = async () => {
    if (!detail?.chat?.chat_id) return
    setSaving(true)
    try {
      await setGroupsStudioLevel(detail.chat.chat_id, Number(levelDraft))
      notifyAdmin(Number(levelDraft) === 0 ? 'Уровень сброшен' : `Уровень → ★${levelDraft}`)
      await openChat(detail.chat.chat_id)
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onModerate = async () => {
    if (!detail?.chat?.chat_id || !modUser.trim()) return
    setModding(true)
    try {
      const hours = Number(modHours)
      const untilSec = ['mute', 'ban'].includes(modAction) && Number.isFinite(hours) && hours > 0
        ? Math.round(hours * 3600)
        : null
      await groupsStudioModerate({
        chat_id: detail.chat.chat_id,
        user_id: Number(modUser),
        action: modAction,
        until_sec: untilSec,
        reason: modReason || undefined,
      })
      notifyAdmin(`Готово: ${modAction}`)
      await openChat(detail.chat.chat_id)
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setModding(false)
    }
  }

  const g = overview?.global || {}
  const chat = detail?.chat
  const fund = detail?.fund
  const bars = detail?.bars || {}
  const balanceMax = Math.max(BALANCE_MAX, Math.ceil((Number(chat?.chatbalance) || 0) * 1.5), Number(balanceDraft) || 0)

  const tabs = useMemo(() => ([
    { id: 'lookup', label: 'Поиск' },
    { id: 'detail', label: 'Карточка' },
    { id: 'tops', label: 'Топы' },
  ]), [])

  const detailSubs = useMemo(() => ([
    { id: 'overview', label: 'Обзор' },
    { id: 'economy', label: 'Экономика' },
    { id: 'people', label: 'Люди' },
    { id: 'moderation', label: 'Модерация' },
    { id: 'control', label: 'Контроль' },
    { id: 'raw', label: 'Все поля' },
  ]), [])

  if (loading && !overview) {
    return <div className="grp-page"><p className="grp-loading">Загрузка студии групп…</p></div>
  }

  return (
    <div className="grp-page">
      <header className="grp-hero">
        <div className="grp-hero-glow" aria-hidden />
        <h1 className="grp-title">Группы</h1>
        <p className="grp-sub">
          Полные данные чата: баланс, участники, комиссии, дом проекта, активность и модерация.
        </p>
        <div className="grp-hero-stats">
          <Stat label="Чатов в базе" value={fmt(overview?.chats_total)} delay={0} />
          <Stat label="Комиссии всего" value={fmt(g.commission)} hint="кут" delay={60} />
          <Stat label="В дом проекта" value={fmt(g.to_project)} hint="из комиссий" delay={120} />
          <Stat label="Событий" value={fmt(g.events)} delay={180} />
        </div>
      </header>

      <nav className="grp-tabs">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`grp-tab${tab === t.id ? ' grp-tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="grp-scroll">
        {tab === 'lookup' && (
          <section className="grp-panel grp-enter">
            <h2 className="grp-panel-title">Найти группу</h2>
            <p className="grp-help">
              chat_id (−100…), @username, t.me/… или часть названия. Приватные без username — лучше по id.
            </p>
            <form className="grp-search" onSubmit={onSearch}>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="−1002135149822 · @club · t.me/… · Название"
              />
              <button type="submit" className="elite-btn elite-btn-primary" disabled={searching}>
                {searching ? 'Ищем…' : 'Открыть'}
              </button>
            </form>
            <div className="grp-hits">
              {hits.map((h, i) => (
                <button
                  key={h.chat_id}
                  type="button"
                  className="grp-hit"
                  style={{ animationDelay: `${i * 40}ms` }}
                  onClick={() => openChat(h.chat_id)}
                >
                  <strong>{h.name}</strong>
                  <span>{stars(h.level)} · бч {fmt(h.chatbalance)}</span>
                  <code>{h.chat_id}</code>
                </button>
              ))}
            </div>
          </section>
        )}

        {tab === 'detail' && (
          <section className="grp-panel grp-enter">
            {loadingDetail && <p className="grp-loading">Загрузка карточки…</p>}
            {!loadingDetail && !chat && (
              <p className="grp-help">Сначала найдите группу на вкладке «Поиск» или в топах.</p>
            )}
            {!loadingDetail && chat && (
              <>
                <div className="grp-detail-head">
                  <div>
                    <h2 className="grp-detail-title">{chat.name}</h2>
                    <p className="grp-help" style={{ marginBottom: '.45rem' }}>
                      {detail.stars}
                      {detail.gbl?.badge_title ? ` · ${detail.gbl.badge_title}` : ''}
                      {detail.scale_score != null ? ` · сила ${detail.scale_score}` : ''}
                    </p>
                    <div className="grp-id-row">
                      <code>{chat.chat_id}</code>
                      <Chip onClick={() => copyText(chat.chat_id)}>копировать id</Chip>
                      {chat.username ? (
                        <Chip onClick={() => copyText(`@${String(chat.username).replace(/^@/, '')}`)}>
                          @{String(chat.username).replace(/^@/, '')}
                        </Chip>
                      ) : null}
                      {chat.link ? (
                        <a className="grp-chip" href={chat.link} target="_blank" rel="noreferrer">ссылка</a>
                      ) : null}
                    </div>
                    <p className="grp-help" style={{ marginTop: '.55rem' }}>
                      {detail.members != null ? `${fmt(detail.members)} участников` : 'участники —'}
                      {detail.telegram?.type ? ` · ${detail.telegram.type}` : ''}
                      {detail.bot?.status ? ` · бот: ${detail.bot.status}` : ''}
                      {detail.activity?.messages_30d != null
                        ? ` · ${fmt(detail.activity.messages_30d)} сообщ. / 30д`
                        : ''}
                    </p>
                  </div>
                  <div className="grp-detail-actions">
                    <button type="button" className="elite-btn" onClick={() => openChat(chat.chat_id)}>
                      Обновить
                    </button>
                  </div>
                </div>

                <div className="grp-meters">
                  <Meter
                    label="Баланс группы"
                    display={`${fmt(chat.chatbalance)} кут`}
                    hint="бч"
                    fill={bars.balance}
                    tone="mint"
                  />
                  <Meter
                    label="Комиссии"
                    display={`${fmt(fund?.commission_sum)} кут`}
                    hint="за всё время"
                    fill={bars.commission}
                    tone="gold"
                  />
                  <Meter
                    label="Дом проекта"
                    display={`${fmt(fund?.to_project_sum)} кут`}
                    hint="с этой группы"
                    fill={bars.project}
                    tone="rose"
                  />
                  <Meter
                    label="Активность"
                    display={detail.activity?.messages_30d != null ? `${fmt(detail.activity.messages_30d)} сообщ.` : '—'}
                    hint="за 30 дней"
                    fill={bars.activity}
                    tone="sky"
                  />
                  <Meter
                    label="Участники"
                    display={detail.members != null ? fmt(detail.members) : '—'}
                    hint="в Telegram"
                    fill={bars.members}
                    tone="violet"
                  />
                  <Meter
                    label="Уровень"
                    display={stars(chat.level)}
                    hint={detail.gbl?.badge_title || `★${chat.level}`}
                    fill={bars.level}
                    tone="star"
                  />
                </div>

                <nav className="grp-subtabs">
                  {detailSubs.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      className={`grp-subtab${sub === s.id ? ' grp-subtab-active' : ''}`}
                      onClick={() => setSub(s.id)}
                    >
                      {s.label}
                    </button>
                  ))}
                </nav>

                <div key={sub} className="grp-subview grp-enter">
                  {sub === 'overview' && (
                    <>
                      <div className="grp-stat-grid">
                        <Stat label="Баланс группы" value={fmt(chat.chatbalance)} hint="кут" />
                        <Stat label="Уровень" value={stars(chat.level)} hint={detail.gbl?.stars_label || ''} />
                        <Stat label="Комиссии за всё время" value={fmt(fund?.commission_sum)} hint="кут" />
                        <Stat label="В дом проекта" value={fmt(fund?.to_project_sum)} hint="за всё время" />
                        <Stat label="Комиссии за 7 дней" value={fmt(fund?.last_7d?.commission)} />
                        <Stat label="В дом за 7 дней" value={fmt(fund?.last_7d?.to_project)} />
                        <Stat label="Комиссии за 30 дней" value={fmt(fund?.last_30d?.commission)} />
                        <Stat label="В дом за 30 дней" value={fmt(fund?.last_30d?.to_project)} />
                        <Stat label="Фонд роста" value={fmt(fund?.pool_balance)} hint={`всего накоплено ${fmt(fund?.pool_total_ever)}`} />
                        <Stat label="Вернулось в баланс группы" value={fmt(fund?.to_chat_sum)} />
                        <Stat label="Средняя комиссия" value={fmt(fund?.avg_commission, 2)} />
                        <Stat label="Игровых событий" value={fmt(fund?.events)} />
                      </div>
                      {detail.telegram?.description ? (
                        <div className="grp-card">
                          <h3 className="grp-card-title">Описание Telegram</h3>
                          <p className="grp-help" style={{ margin: 0 }}>{detail.telegram.description}</p>
                        </div>
                      ) : null}
                      <div className="grp-two">
                        <div className="grp-card">
                          <h3 className="grp-card-title">Уровень и ставки</h3>
                          <p className="grp-help">
                            Лимит ставки: {detail.gbl?.stake_cap_effective ?? detail.gbl?.stake_cap_base ?? 'без лимита'}
                            {detail.gbl?.next_price != null ? ` · следующий уровень = ${fmt(detail.gbl.next_price)} ⭐` : ''}
                            {detail.gbl?.enabled === false ? ' · система выключена' : ''}
                          </p>
                          <div className="grp-mini-stats">
                            <span>dex-баланс: {fmt(chat.dexbalance)}</span>
                            <span>создана: {shortWhen(chat.created_at)}</span>
                          </div>
                        </div>
                        <div className="grp-card">
                          <h3 className="grp-card-title">Царь чата и чёрный рынок</h3>
                          <p className="grp-help">
                            {detail.king?.configured
                              ? `${detail.king.enabled ? 'включён' : 'выключен'} · период ${detail.king.period_kind || '—'} · минимум ${detail.king.min_messages || 0} сообщ. · награды ${detail.king.reward_p1}/${detail.king.reward_p2}/${detail.king.reward_p3}`
                              : 'не настроено'}
                          </p>
                          <p className="grp-help" style={{ marginBottom: 0 }}>
                            Чёрный рынок: {fmt(detail.black_market?.deposits_sum)} кут · {fmt(detail.black_market?.deposits_count)} депозитов
                          </p>
                        </div>
                      </div>
                    </>
                  )}

                  {sub === 'economy' && (
                    <>
                      <div className="grp-stat-grid">
                        <Stat label="Вернулось в баланс группы" value={fmt(fund?.to_chat_sum)} hint="за всё время" />
                        <Stat label="Ушло в фонд роста" value={fmt(fund?.to_fund_sum)} hint="за всё время" />
                        <Stat label="Ушло в дом проекта" value={fmt(fund?.to_project_sum)} hint="за всё время" />
                        <Stat label="Фонд обновлялся" value={shortWhen(fund?.pool_updated_at)} />
                      </div>
                      <div className="grp-card">
                        <h3 className="grp-card-title">По играм</h3>
                        <MiniTable
                          columns={[
                            { key: 'game', label: 'Игра' },
                            { key: 'commission', label: 'Комиссия', render: (r) => fmt(r.commission) },
                            { key: 'to_project', label: 'Дом', render: (r) => fmt(r.to_project) },
                            { key: 'events', label: 'Событий', render: (r) => fmt(r.events) },
                          ]}
                          rows={fund?.by_game || []}
                          empty="Нет проводок"
                        />
                      </div>
                      <div className="grp-card">
                        <h3 className="grp-card-title">Топ плательщиков комиссий</h3>
                        <MiniTable
                          columns={[
                            { key: 'name', label: 'Игрок', render: (r) => `${r.name}${r.username ? ` @${r.username}` : ''}` },
                            { key: 'commission', label: 'Комиссия', render: (r) => fmt(r.commission) },
                            { key: 'events', label: 'Игр', render: (r) => fmt(r.events) },
                            { key: 'user_id', label: 'ID' },
                          ]}
                          rows={fund?.top_payers || []}
                        />
                      </div>
                      <div className="grp-card">
                        <h3 className="grp-card-title">Последние проводки</h3>
                        <MiniTable
                          columns={[
                            { key: 'at', label: 'Когда', render: (r) => shortWhen(r.at) },
                            { key: 'game', label: 'Игра' },
                            { key: 'commission', label: 'Комиссия', render: (r) => fmt(r.commission) },
                            { key: 'to_project', label: 'Дом', render: (r) => fmt(r.to_project) },
                            { key: 'user_id', label: 'User' },
                          ]}
                          rows={fund?.recent || []}
                        />
                      </div>
                    </>
                  )}

                  {sub === 'people' && (
                    <>
                      <div className="grp-card">
                        <h3 className="grp-card-title">Роли</h3>
                        <PersonLine title="Создатель группы" person={detail.creator} />
                        <PersonLine title="Спонсор уровня" person={detail.sponsor} />
                        <div className="grp-mini-stats">
                          <span>в memberchat: {fmt(detail.activity?.members_tracked)}</span>
                          <span>писатели 30д: {fmt(detail.activity?.writers_30d)}</span>
                          <span>сообщения 30д: {fmt(detail.activity?.messages_30d)}</span>
                          <span>источник: {detail.activity?.source || '—'}</span>
                        </div>
                      </div>
                      <div className="grp-card">
                        <h3 className="grp-card-title">Админы Telegram ({(detail.admins || []).length})</h3>
                        <MiniTable
                          columns={[
                            { key: 'name', label: 'Имя', render: (r) => `${r.name}${r.is_bot ? ' 🤖' : ''}` },
                            { key: 'status', label: 'Статус' },
                            { key: 'username', label: 'Username', render: (r) => r.username ? `@${r.username}` : '—' },
                            { key: 'user_id', label: 'ID' },
                          ]}
                          rows={detail.admins || []}
                          empty="Не удалось получить админов (бот не в чате?)"
                        />
                        {detail.bot?.status ? (
                          <p className="grp-help" style={{ marginTop: '.65rem', marginBottom: 0 }}>
                            Бот: {detail.bot.status}
                            {detail.bot.can_restrict ? ' · restrict' : ''}
                            {detail.bot.can_delete ? ' · delete' : ''}
                            {detail.bot.can_invite ? ' · invite' : ''}
                            {detail.bot.can_promote ? ' · promote' : ''}
                          </p>
                        ) : null}
                      </div>
                      <div className="grp-card">
                        <h3 className="grp-card-title">Топ писателей 30д</h3>
                        <MiniTable
                          columns={[
                            { key: 'name', label: 'Имя', render: (r) => `${r.name}${r.username ? ` @${r.username}` : ''}` },
                            { key: 'messages', label: 'Сообщ.', render: (r) => fmt(r.messages) },
                            { key: 'user_id', label: 'ID' },
                          ]}
                          rows={detail.activity?.top_writers || []}
                        />
                      </div>
                    </>
                  )}

                  {sub === 'moderation' && (
                    <>
                      <div className="grp-stat-grid">
                        <Stat label="Муты (лог)" value={fmt(detail.moderation?.mutes)} />
                        <Stat label="Баны (лог)" value={fmt(detail.moderation?.bans)} />
                        <Stat label="Варны (лог)" value={fmt(detail.moderation?.warns)} />
                        <Stat label="Кики" value={fmt(detail.moderation?.kicks)} />
                        <Stat label="Актив. муты" value={fmt(detail.moderation?.active_mutes)} />
                        <Stat label="Актив. баны" value={fmt(detail.moderation?.active_bans)} />
                        <Stat label="Актив. варны" value={fmt(detail.moderation?.active_warns)} />
                        <Stat label="Действий 30д" value={fmt(detail.moderation?.actions_30d)} />
                      </div>
                      <div className="grp-two">
                        <div className="grp-card">
                          <h3 className="grp-card-title">Активные муты</h3>
                          <MiniTable
                            columns={[
                              { key: 'name', label: 'Кто', render: (r) => r.name || r.user_id },
                              { key: 'until', label: 'До', render: (r) => shortWhen(r.until) },
                              { key: 'reason', label: 'Причина' },
                            ]}
                            rows={detail.moderation?.active?.mutes || []}
                          />
                        </div>
                        <div className="grp-card">
                          <h3 className="grp-card-title">Активные баны</h3>
                          <MiniTable
                            columns={[
                              { key: 'name', label: 'Кто', render: (r) => r.name || r.user_id },
                              { key: 'until', label: 'До', render: (r) => shortWhen(r.until) },
                              { key: 'reason', label: 'Причина' },
                            ]}
                            rows={detail.moderation?.active?.bans || []}
                          />
                        </div>
                      </div>
                      <div className="grp-card">
                        <h3 className="grp-card-title">Активные варны</h3>
                        <MiniTable
                          columns={[
                            { key: 'user_id', label: 'User' },
                            { key: 'expires_at', label: 'До', render: (r) => shortWhen(r.expires_at) },
                            { key: 'admin', label: 'Админ' },
                            { key: 'reason', label: 'Причина' },
                          ]}
                          rows={detail.moderation?.active?.warns || []}
                        />
                      </div>
                      <div className="grp-card">
                        <h3 className="grp-card-title">Последние действия модерации</h3>
                        <MiniTable
                          columns={[
                            { key: 'at', label: 'Когда', render: (r) => shortWhen(r.at) },
                            { key: 'action', label: 'Действие' },
                            { key: 'target_user_id', label: 'Цель' },
                            { key: 'admin', label: 'Админ' },
                            { key: 'reason', label: 'Причина' },
                          ]}
                          rows={detail.moderation?.recent || []}
                        />
                      </div>
                    </>
                  )}

                  {sub === 'control' && (
                    <div className="grp-two">
                      <div className="grp-card grp-card-control">
                        <h3 className="grp-card-title">Баланс и уровень</h3>
                        <RangeField
                          label="Баланс группы (кут)"
                          value={Math.min(balanceMax, Math.max(0, Number(balanceDraft) || 0))}
                          min={0}
                          max={balanceMax}
                          step={100}
                          onChange={setBalanceDraft}
                          display={fmt(balanceDraft)}
                          marks={<span>0 — {fmt(balanceMax)}</span>}
                        />
                        <label className="grp-field">
                          <span>Точное значение</span>
                          <input
                            value={balanceDraft}
                            onChange={(e) => setBalanceDraft(e.target.value === '' ? 0 : Number(e.target.value))}
                            inputMode="decimal"
                          />
                        </label>
                        <div className="grp-chip-row">
                          {[0, 1000, 5000, 10000, 50000, 100000].map((v) => (
                            <Chip key={v} onClick={() => setBalanceDraft(v)}>{fmt(v)}</Chip>
                          ))}
                        </div>
                        <button type="button" className="elite-btn elite-btn-primary" disabled={saving} onClick={onSaveBalance}>
                          Сохранить бч
                        </button>

                        <RangeField
                          label="Уровень ★0–★5"
                          value={levelDraft}
                          min={0}
                          max={5}
                          step={1}
                          onChange={setLevelDraft}
                          display={stars(levelDraft)}
                          marks={<span>0  1  2  3  4  5</span>}
                        />
                        <div className="grp-star-picks">
                          {[0, 1, 2, 3, 4, 5].map((n) => (
                            <button
                              key={n}
                              type="button"
                              className={`grp-star-pick${levelDraft === n ? ' is-on' : ''}`}
                              onClick={() => setLevelDraft(n)}
                            >
                              {n === 0 ? '☆0' : `★${n}`}
                            </button>
                          ))}
                        </div>
                        <div className="grp-actions">
                          <button type="button" className="elite-btn elite-btn-primary" disabled={saving} onClick={onSaveLevel}>
                            Применить уровень
                          </button>
                          <button type="button" className="elite-btn" disabled={saving} onClick={() => setLevelDraft(0)}>
                            Сбросить ★0
                          </button>
                        </div>
                      </div>

                      <div className="grp-card grp-card-control">
                        <h3 className="grp-card-title">Модерация</h3>
                        <p className="grp-help">Через игрового бота. Нужны права админа бота в чате.</p>
                        <label className="grp-field">
                          <span>ID игрока</span>
                          <input value={modUser} onChange={(e) => setModUser(e.target.value)} placeholder="123456789" inputMode="numeric" />
                        </label>
                        <label className="grp-field">
                          <span>Действие</span>
                          <select value={modAction} onChange={(e) => setModAction(e.target.value)}>
                            <option value="mute">Мут</option>
                            <option value="unmute">Размут</option>
                            <option value="kick">Кик</option>
                            <option value="ban">Бан</option>
                            <option value="unban">Разбан</option>
                          </select>
                        </label>
                        {['mute', 'ban'].includes(modAction) ? (
                          <>
                            <RangeField
                              label="Срок (часы)"
                              value={modHours}
                              min={0}
                              max={720}
                              step={1}
                              onChange={setModHours}
                              display={modHours === 0 ? 'навсегда' : `${modHours} ч`}
                            />
                            <div className="grp-chip-row">
                              {MUTE_PRESETS.map((p) => (
                                <Chip key={p.label} tone={modHours === p.h ? 'on' : undefined} onClick={() => setModHours(p.h)}>
                                  {p.label}
                                </Chip>
                              ))}
                            </div>
                          </>
                        ) : null}
                        <label className="grp-field">
                          <span>Причина</span>
                          <input value={modReason} onChange={(e) => setModReason(e.target.value)} placeholder="панель" />
                        </label>
                        <button type="button" className="elite-btn elite-btn-primary" disabled={modding} onClick={onModerate}>
                          {modding ? 'Выполняем…' : 'Выполнить'}
                        </button>
                      </div>
                    </div>
                  )}

                  {sub === 'raw' && (
                    <div className="grp-card">
                      <div className="grp-detail-head" style={{ marginBottom: '.5rem' }}>
                        <h3 className="grp-card-title">Все поля из базы и Telegram</h3>
                        <button type="button" className="elite-btn" onClick={() => setRawOpen((v) => !v)}>
                          {rawOpen ? 'Свернуть JSON' : 'Показать JSON'}
                        </button>
                      </div>
                      <div className="grp-kv-grid">
                        {Object.entries(detail.chat_raw || {}).map(([k, v]) => (
                          <div key={k} className="grp-kv">
                            <span>{k}</span>
                            <strong>{v == null || v === '' ? '—' : String(v)}</strong>
                          </div>
                        ))}
                      </div>
                      {detail.telegram && Object.keys(detail.telegram).length ? (
                        <>
                          <h4 className="grp-card-title" style={{ marginTop: '1rem' }}>Telegram</h4>
                          <div className="grp-kv-grid">
                            {Object.entries(detail.telegram).map(([k, v]) => (
                              <div key={k} className="grp-kv">
                                <span>{k}</span>
                                <strong>{typeof v === 'object' ? JSON.stringify(v) : (v == null || v === '' ? '—' : String(v))}</strong>
                              </div>
                            ))}
                          </div>
                        </>
                      ) : null}
                      {rawOpen ? (
                        <pre className="grp-raw-json">{JSON.stringify(detail, null, 2)}</pre>
                      ) : null}
                    </div>
                  )}
                </div>
              </>
            )}
          </section>
        )}

        {tab === 'tops' && (
          <section className="grp-tops grp-enter">
            <div className="grp-card">
              <h3 className="grp-card-title">Топ по комиссиям</h3>
              {(overview?.top_commission || []).map((it, i) => (
                <RankRow key={`c-${it.chat_id}`} item={it} metric={fmt(it.commission)} onOpen={openChat} index={i} />
              ))}
            </div>
            <div className="grp-card">
              <h3 className="grp-card-title">Топ в дом проекта</h3>
              {(overview?.top_project || []).map((it, i) => (
                <RankRow key={`p-${it.chat_id}`} item={it} metric={fmt(it.to_project)} onOpen={openChat} index={i} />
              ))}
            </div>
            <div className="grp-card">
              <h3 className="grp-card-title">Топ по бч</h3>
              {(overview?.top_balance || []).map((it, i) => (
                <RankRow key={`b-${it.chat_id}`} item={it} metric={fmt(it.chatbalance)} onOpen={openChat} index={i} />
              ))}
            </div>
            <p className="grp-help">{overview?.hint}</p>
          </section>
        )}
      </div>
    </div>
  )
}
