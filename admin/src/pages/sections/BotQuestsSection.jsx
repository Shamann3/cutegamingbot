import { useCallback, useEffect, useMemo, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import { notifyAdmin } from '../../lib/notify'
import {
  fetchBotQuestsOverview,
  fetchBotSubTasks,
  createBotSubTask,
  bulkCreateBotSubTasks,
  patchBotSubTask,
  deleteBotSubTask,
  fetchBotChallenges,
  createBotChallenge,
  bulkCreateBotChallenges,
  patchBotChallenge,
  deleteBotChallenge,
  disableBotChallenge,
} from '../../lib/adminClient'

const START_PRESETS = [
  { label: 'Сейчас', minutes: 0 },
  { label: '+15м', minutes: 15 },
  { label: '+1ч', minutes: 60 },
  { label: '+3ч', minutes: 180 },
  { label: '+1д', minutes: 1440 },
  { label: '+3д', minutes: 4320 },
]

function pad(n) {
  return String(n).padStart(2, '0')
}

function toLocalInput(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function presetStart(minutes) {
  if (!minutes) return ''
  const d = new Date()
  d.setMinutes(d.getMinutes() + minutes)
  return toLocalInput(d)
}

function fmtDt(iso) {
  if (!iso) return 'сразу'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function emptySubRow(sharedStart = '') {
  return {
    key: Math.random().toString(36).slice(2),
    chatRef: '',
    reward: '2',
    limitMode: 'unlimited',
    totalCap: '30',
    ttlValue: '12',
    ttlUnit: 'h',
    startsAt: sharedStart,
  }
}

function emptyGcRow(sharedStart = '') {
  return {
    key: Math.random().toString(36).slice(2),
    startAmount: '100',
    targetAmount: '500',
    rewardAmount: '100',
    maxBet: '',
    chatRef: '',
    maxUsers: '',
    free: '-',
    startsAt: sharedStart,
  }
}

function statusMeta(item) {
  if (item.status === 'disabled') return { cls: 'off', text: 'Выключено', pulse: false }
  if (item.scheduled) return { cls: 'soon', text: 'Ждёт старта', pulse: true }
  if (item.effectiveActive) return { cls: 'live', text: 'В эфире', pulse: true }
  if (item.active === false) return { cls: 'off', text: 'На паузе', pulse: false }
  return { cls: 'mute', text: 'Неактивно', pulse: false }
}

function IconSpark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <ellipse cx="12" cy="13" rx="6.2" ry="5.4" fill="currentColor" opacity="0.95" />
      <path d="M7.2 8.2c-1.8-2.4-4.2-2.8-4.6-1.2-.5 2.1 1.6 4.4 4.1 5.2" fill="currentColor" opacity="0.85" />
      <path d="M16.8 8.2c1.8-2.4 4.2-2.8 4.6-1.2.5 2.1-1.6 4.4-4.1 5.2" fill="currentColor" opacity="0.85" />
      <circle cx="10.2" cy="12.4" r="1.05" fill="#050505" />
      <circle cx="13.8" cy="12.4" r="1.05" fill="#050505" />
      <path d="M10.6 15.1c.8.7 2 .7 2.8 0" stroke="#050505" strokeWidth="1.2" fill="none" strokeLinecap="round" />
    </svg>
  )
}

function IconSub() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path d="M8 7.5h8a3 3 0 0 1 3 3V17a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-6.5a3 3 0 0 1 3-3z" />
      <path d="M9 7.5V6.2A3.2 3.2 0 0 1 12.2 3h0A3.2 3.2 0 0 1 15.4 6.2V7.5" />
      <path d="M9.5 13h5" />
    </svg>
  )
}

function IconGc() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path d="M12 3l7 4v5c0 4.2-2.8 7.8-7 9-4.2-1.2-7-4.8-7-9V7l7-4z" />
      <path d="M9.2 12.2l1.8 1.8 3.8-3.8" />
    </svg>
  )
}

function IconRefresh() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M20 12a8 8 0 1 1-2.2-5.5" />
      <path d="M20 4.5V9h-4.5" />
    </svg>
  )
}

export default function BotQuestsSection() {
  const [mode, setMode] = useState('subs')
  const [overview, setOverview] = useState(null)
  const [subs, setSubs] = useState([])
  const [gcs, setGcs] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [bulkMode, setBulkMode] = useState(false)
  const [sharedStart, setSharedStart] = useState('')
  const [activePreset, setActivePreset] = useState(0)
  const [subRows, setSubRows] = useState([emptySubRow()])
  const [gcRows, setGcRows] = useState([emptyGcRow()])
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [composerOpen, setComposerOpen] = useState(true)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, s, c] = await Promise.all([
        fetchBotQuestsOverview(),
        fetchBotSubTasks(),
        fetchBotChallenges(),
      ])
      setOverview(ov)
      setSubs(s.items || [])
      setGcs(c.items || [])
    } catch (e) {
      notifyAdmin(e?.message || 'Не удалось загрузить задания', { error: true })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const applySharedStart = (value, presetMinutes = null) => {
    setSharedStart(value)
    setActivePreset(presetMinutes)
    setSubRows((rows) => rows.map((r) => ({ ...r, startsAt: value })))
    setGcRows((rows) => rows.map((r) => ({ ...r, startsAt: value })))
  }

  const list = mode === 'subs' ? subs : gcs
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return list.filter((item) => {
      if (filter === 'live' && !item.effectiveActive) return false
      if (filter === 'soon' && !item.scheduled) return false
      if (filter === 'off') {
        const off = item.status === 'disabled' || item.active === false || (!item.effectiveActive && !item.scheduled)
        if (!off) return false
      }
      if (!q) return true
      const hay = mode === 'subs'
        ? `${item.chatRef} ${item.id} ${item.reward}`
        : `${item.id} ${item.startAmount} ${item.targetAmount} ${item.rewardAmount} ${item.targetChatRef || ''} ${item.free}`
      return hay.toLowerCase().includes(q)
    })
  }, [list, filter, query, mode])

  const counts = useMemo(() => ({
    all: list.length,
    live: list.filter((i) => i.effectiveActive).length,
    soon: list.filter((i) => i.scheduled).length,
    off: list.filter((i) => i.status === 'disabled' || i.active === false || (!i.effectiveActive && !i.scheduled)).length,
  }), [list])

  const saveSubs = async () => {
    const payload = subRows
      .filter((r) => (r.chatRef || '').trim())
      .map((r) => ({
        chatRef: r.chatRef.trim(),
        reward: r.reward,
        limitMode: r.limitMode,
        totalCap: r.limitMode === 'cap' ? Number(r.totalCap) : null,
        ttlValue: r.limitMode === 'ttl' ? Number(r.ttlValue) : null,
        ttlUnit: r.ttlUnit || 'h',
        startsAt: r.startsAt ? new Date(r.startsAt).toISOString() : null,
        active: true,
      }))
    if (!payload.length) {
      notifyAdmin('Добавьте хотя бы один канал', { error: true })
      return
    }
    setSaving(true)
    try {
      if (payload.length === 1 && !bulkMode) {
        await createBotSubTask(payload[0])
        notifyAdmin('Задание на подписку сохранено')
      } else {
        const res = await bulkCreateBotSubTasks(payload)
        notifyAdmin(`Создано: ${res.ok}${res.failed ? `, ошибок: ${res.failed}` : ''}`)
        if (res.errors?.length) notifyAdmin(res.errors[0].error, { error: true })
      }
      setSubRows([emptySubRow(sharedStart)])
      await load()
    } catch (e) {
      notifyAdmin(e?.message || 'Ошибка сохранения', { error: true })
    } finally {
      setSaving(false)
    }
  }

  const saveGcs = async () => {
    const payload = gcRows.map((r) => ({
      startAmount: Number(r.startAmount),
      targetAmount: Number(r.targetAmount),
      rewardAmount: Number(r.rewardAmount),
      maxBet: r.maxBet === '' || r.maxBet == null ? null : Number(r.maxBet),
      chatRef: (r.chatRef || '').trim() || null,
      maxUsers: r.maxUsers === '' || r.maxUsers == null ? null : Number(r.maxUsers),
      free: r.free === '+' ? '+' : '-',
      startsAt: r.startsAt ? new Date(r.startsAt).toISOString() : null,
    }))
    if (!payload.length) return
    for (const p of payload) {
      if (!(p.startAmount > 0 && p.targetAmount > p.startAmount && p.rewardAmount > 0)) {
        notifyAdmin('Проверьте старт / цель / награду (цель > старт)', { error: true })
        return
      }
    }
    setSaving(true)
    try {
      if (payload.length === 1 && !bulkMode) {
        await createBotChallenge(payload[0])
        notifyAdmin('Челлендж создан')
      } else {
        const res = await bulkCreateBotChallenges(payload)
        notifyAdmin(`Создано: ${res.ok}${res.failed ? `, ошибок: ${res.failed}` : ''}`)
        if (res.errors?.length) notifyAdmin(res.errors[0].error, { error: true })
      }
      setGcRows([emptyGcRow(sharedStart)])
      await load()
    } catch (e) {
      notifyAdmin(e?.message || 'Ошибка создания', { error: true })
    } finally {
      setSaving(false)
    }
  }

  const duplicateGc = (item) => {
    setMode('gc')
    setComposerOpen(true)
    setBulkMode(true)
    setGcRows((rows) => [
      {
        ...emptyGcRow(sharedStart),
        startAmount: String(item.startAmount),
        targetAmount: String(item.targetAmount),
        rewardAmount: String(item.rewardAmount),
        maxBet: item.betLimit != null ? String(item.betLimit) : '',
        chatRef: item.targetChatRef || '',
        maxUsers: item.maxUsers != null ? String(item.maxUsers) : '',
        free: item.free || '-',
      },
      ...rows,
    ])
  }

  const runCardAction = async (id, fn, okMsg) => {
    setBusyId(id)
    try {
      await fn()
      if (okMsg) notifyAdmin(okMsg)
      await load()
    } catch (e) {
      notifyAdmin(e?.message || 'Ошибка', { error: true })
    } finally {
      setBusyId(null)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setSaving(true)
    try {
      if (deleteTarget.kind === 'sub') {
        await deleteBotSubTask(deleteTarget.id)
        notifyAdmin('Задание удалено')
      } else {
        await deleteBotChallenge(deleteTarget.id)
        notifyAdmin('Задание удалено')
      }
      setDeleteTarget(null)
      await load()
    } catch (e) {
      notifyAdmin(e?.message || 'Ошибка', { error: true })
    } finally {
      setSaving(false)
    }
  }

  const ov = overview || {
    subTasks: { total: 0, active: 0, scheduled: 0 },
    challenges: { total: 0, active: 0, scheduled: 0, disabled: 0 },
    subRewardPaidTotal: '0',
  }

  const cmdPreview = mode === 'subs'
    ? `+задание ${(subRows[0]?.chatRef || '@channel').trim() || '@channel'} ${subRows[0]?.reward || '2'}${subRows[0]?.limitMode === 'cap' ? ` ${subRows[0].totalCap}ч` : ''}${subRows[0]?.limitMode === 'ttl' ? ` ${subRows[0].ttlValue}${subRows[0].ttlUnit}` : ''}`
    : `+заданиеч ${gcRows[0]?.startAmount || 100} ${gcRows[0]?.targetAmount || 500} ${gcRows[0]?.rewardAmount || 100}${gcRows[0]?.maxBet ? ` ${gcRows[0].maxBet}` : ''}${gcRows[0]?.chatRef ? ` ${gcRows[0].chatRef}` : ''}${gcRows[0]?.maxUsers ? ` 0/${gcRows[0].maxUsers}` : ''} ${gcRows[0]?.free || '-'}`

  const readyCount = mode === 'subs'
    ? subRows.filter((r) => r.chatRef.trim()).length
    : gcRows.length

  return (
    <div className={`panel-content bq-root bq-theme-${mode}`}>
      <div className="bq-atmosphere" aria-hidden="true">
        <span className="bq-orb bq-orb-a" />
        <span className="bq-orb bq-orb-b" />
        <span className="bq-grid" />
      </div>

      <header className="bq-hero">
        <div className="bq-hero-main">
          <div className="bq-badge">
            <IconSpark />
            <span>Только создатель</span>
          </div>
          <h2 className="bq-title">Студия заданий</h2>
          <p className="bq-lead">
            Создавай задания на подписку и челленджи вместо команд
            <code>+задание</code> и <code>+заданиеч</code>.
            Можно сразу много штук и с временем старта.
          </p>
          <div className="bq-hero-actions">
            <button type="button" className="bq-btn bq-btn-ghost" onClick={load} disabled={loading}>
              <IconRefresh />
              {loading ? 'Обновляю…' : 'Обновить'}
            </button>
            <button
              type="button"
              className="bq-btn bq-btn-primary"
              onClick={() => setComposerOpen((v) => !v)}
            >
              {composerOpen ? 'Скрыть конструктор' : 'Открыть конструктор'}
            </button>
          </div>
        </div>

        <div className="bq-metrics">
          <div className="bq-metric" style={{ '--i': 0 }}>
            <div className="bq-metric-icon bq-metric-cyan"><IconSub /></div>
            <div>
              <span className="bq-metric-label">Подписки в эфире</span>
              <strong className="bq-metric-value">{ov.subTasks.active}</strong>
              <span className="bq-metric-sub">скоро {ov.subTasks.scheduled} · всего {ov.subTasks.total}</span>
            </div>
          </div>
          <div className="bq-metric" style={{ '--i': 1 }}>
            <div className="bq-metric-icon bq-metric-violet"><IconGc /></div>
            <div>
              <span className="bq-metric-label">Челленджи в эфире</span>
              <strong className="bq-metric-value">{ov.challenges.active}</strong>
              <span className="bq-metric-sub">скоро {ov.challenges.scheduled} · выкл {ov.challenges.disabled}</span>
            </div>
          </div>
          <div className="bq-metric" style={{ '--i': 2 }}>
            <div className="bq-metric-icon bq-metric-blue">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
                <ellipse cx="12" cy="7" rx="7" ry="2.6" />
                <path d="M5 7v10c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6V7" />
                <path d="M5 12c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6" />
              </svg>
            </div>
            <div>
              <span className="bq-metric-label">Всего выдано игрокам</span>
              <strong className="bq-metric-value">{ov.subRewardPaidTotal}</strong>
              <span className="bq-metric-sub">награда за подписки (quebalance)</span>
            </div>
          </div>
        </div>
      </header>

      <div className="bq-toolbar">
        <div className="bq-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'subs'}
            className={`bq-tab${mode === 'subs' ? ' is-active' : ''}`}
            onClick={() => setMode('subs')}
          >
            <IconSub />
            Подписки
            <span className="bq-tab-count">{subs.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'gc'}
            className={`bq-tab${mode === 'gc' ? ' is-active' : ''}`}
            onClick={() => setMode('gc')}
          >
            <IconGc />
            Челленджи
            <span className="bq-tab-count">{gcs.length}</span>
          </button>
          <span className="bq-tab-glider" data-mode={mode} aria-hidden="true" />
        </div>

        <div className="bq-filters">
          {[
            ['all', 'Все', counts.all],
            ['live', 'В эфире', counts.live],
            ['soon', 'Ждут старта', counts.soon],
            ['off', 'Выключены', counts.off],
          ].map(([id, label, n]) => (
            <button
              key={id}
              type="button"
              className={`bq-pill${filter === id ? ' is-active' : ''}`}
              onClick={() => setFilter(id)}
            >
              {label}
              <em>{n}</em>
            </button>
          ))}
        </div>

        <label className="bq-search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" />
            <path d="M16.2 16.2L21 21" />
          </svg>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={mode === 'subs' ? 'Поиск по каналу, id…' : 'Поиск по цели, чату, id…'}
          />
        </label>
      </div>

      <div className={`bq-layout${composerOpen ? '' : ' is-wide'}`}>
        {composerOpen && (
          <aside className="bq-composer">
            <div className="bq-composer-head">
              <div>
                <p className="bq-kicker">{mode === 'subs' ? 'Создание заданий' : 'Создание челленджей'}</p>
                <h3>{mode === 'subs' ? 'Новые задания на подписку' : 'Новые игровые челленджи'}</h3>
              </div>
              <button
                type="button"
                className={`bq-toggle${bulkMode ? ' is-on' : ''}`}
                onClick={() => setBulkMode((v) => !v)}
                aria-pressed={bulkMode}
              >
                <span className="bq-toggle-knob" />
                <span>Пакетный режим</span>
              </button>
            </div>

            <div className="bq-panel bq-schedule">
              <div className="bq-panel-title">
                <span>Когда показать игрокам</span>
                {sharedStart ? <em>{fmtDt(new Date(sharedStart).toISOString())}</em> : <em>сразу</em>}
              </div>
              <input
                className="bq-input"
                type="datetime-local"
                value={sharedStart}
                onChange={(e) => applySharedStart(e.target.value, null)}
              />
              <div className="bq-chip-row">
                {START_PRESETS.map((p) => (
                  <button
                    key={p.label}
                    type="button"
                    className={`bq-chip-btn${activePreset === p.minutes ? ' is-active' : ''}`}
                    onClick={() => applySharedStart(presetStart(p.minutes), p.minutes)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <p className="bq-hint">Если поле пустое — задание появится сразу. Если указать дату — игроки увидят его только после этого времени.</p>
            </div>

            {mode === 'subs' ? (
              <div className="bq-rows">
                {(bulkMode ? subRows : subRows.slice(0, 1)).map((row, idx) => (
                  <div key={row.key} className="bq-row" style={{ '--i': idx }}>
                    <div className="bq-row-head">
                      <span>Карточка {idx + 1}</span>
                      {bulkMode && subRows.length > 1 && (
                        <button type="button" className="bq-link-danger" onClick={() => setSubRows((rows) => rows.filter((r) => r.key !== row.key))}>
                          Убрать
                        </button>
                      )}
                    </div>
                    <label className="bq-field">
                      <span>Канал или чат (@username / ссылка)</span>
                      <input
                        className="bq-input"
                        placeholder="@CuteGamingNews или t.me/…"
                        value={row.chatRef}
                        onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, chatRef: e.target.value } : r)))}
                      />
                    </label>
                    <div className="bq-grid-2">
                      <label className="bq-field">
                        <span>Награда игроку</span>
                        <input
                          className="bq-input"
                          value={row.reward}
                          onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, reward: e.target.value } : r)))}
                        />
                      </label>
                      <label className="bq-field">
                        <span>Время старта</span>
                        <input
                          className="bq-input"
                          type="datetime-local"
                          value={row.startsAt}
                          onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, startsAt: e.target.value } : r)))}
                        />
                      </label>
                    </div>
                    <div className="bq-seg">
                      {[
                        ['unlimited', 'Без лимита'],
                        ['cap', 'Лимит людей'],
                        ['ttl', 'Время жизни'],
                      ].map(([id, label]) => (
                        <button
                          key={id}
                          type="button"
                          className={row.limitMode === id ? 'is-active' : ''}
                          onClick={() => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, limitMode: id } : r)))}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    {row.limitMode === 'cap' && (
                      <label className="bq-field">
                        <span>Макс. людей</span>
                        <input
                          className="bq-input"
                          type="number"
                          min={1}
                          value={row.totalCap}
                          onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, totalCap: e.target.value } : r)))}
                        />
                      </label>
                    )}
                    {row.limitMode === 'ttl' && (
                      <div className="bq-grid-2">
                        <label className="bq-field">
                          <span>TTL</span>
                          <input
                            className="bq-input"
                            type="number"
                            min={1}
                            value={row.ttlValue}
                            onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, ttlValue: e.target.value } : r)))}
                          />
                        </label>
                        <label className="bq-field">
                          <span>Единица</span>
                          <select
                            className="bq-input"
                            value={row.ttlUnit}
                            onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, ttlUnit: e.target.value } : r)))}
                          >
                            <option value="s">сек</option>
                            <option value="m">мин</option>
                            <option value="h">час</option>
                            <option value="d">день</option>
                          </select>
                        </label>
                      </div>
                    )}
                  </div>
                ))}
                {bulkMode && (
                  <button type="button" className="bq-btn bq-btn-ghost bq-btn-block" onClick={() => setSubRows((rows) => [...rows, emptySubRow(sharedStart)])}>
                    + Ещё канал
                  </button>
                )}
              </div>
            ) : (
              <div className="bq-rows">
                {(bulkMode ? gcRows : gcRows.slice(0, 1)).map((row, idx) => (
                  <div key={row.key} className="bq-row" style={{ '--i': idx }}>
                    <div className="bq-row-head">
                      <span>Челлендж {idx + 1}</span>
                      {bulkMode && gcRows.length > 1 && (
                        <button type="button" className="bq-link-danger" onClick={() => setGcRows((rows) => rows.filter((r) => r.key !== row.key))}>
                          Убрать
                        </button>
                      )}
                    </div>
                    <div className="bq-grid-3">
                      <label className="bq-field">
                        <span>Стартовый баланс</span>
                        <input className="bq-input" type="number" min={1} value={row.startAmount} onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, startAmount: e.target.value } : r)))} />
                      </label>
                      <label className="bq-field">
                        <span>Цель баланса</span>
                        <input className="bq-input" type="number" min={1} value={row.targetAmount} onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, targetAmount: e.target.value } : r)))} />
                      </label>
                      <label className="bq-field">
                        <span>Награда КУТ</span>
                        <input className="bq-input" type="number" min={1} value={row.rewardAmount} onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, rewardAmount: e.target.value } : r)))} />
                      </label>
                    </div>
                    <div className="bq-progress-preview" aria-hidden="true">
                      <div className="bq-progress-track">
                        <div
                          className="bq-progress-fill"
                          style={{
                            width: `${Math.min(100, Math.max(8, (Number(row.startAmount) / Math.max(Number(row.targetAmount) || 1, 1)) * 100))}%`,
                          }}
                        />
                      </div>
                      <span>{row.startAmount || 0} → {row.targetAmount || 0}</span>
                    </div>
                    <div className="bq-grid-2">
                      <label className="bq-field">
                        <span>Макс. ставка (0 = без лимита)</span>
                        <input className="bq-input" type="number" min={0} placeholder="0 = нет" value={row.maxBet} onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, maxBet: e.target.value } : r)))} />
                      </label>
                      <label className="bq-field">
                        <span>Слоты игроков (пусто = ∞)</span>
                        <input className="bq-input" type="number" min={0} placeholder="∞" value={row.maxUsers} onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, maxUsers: e.target.value } : r)))} />
                      </label>
                    </div>
                    <label className="bq-field">
                      <span>Чат (опционально)</span>
                      <input className="bq-input" placeholder="@CuteGamingChat" value={row.chatRef} onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, chatRef: e.target.value } : r)))} />
                    </label>
                    <div className="bq-grid-2">
                      <label className="bq-field">
                        <span>Старт</span>
                        <input className="bq-input" type="datetime-local" value={row.startsAt} onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, startsAt: e.target.value } : r)))} />
                      </label>
                      <div className="bq-seg bq-seg-end">
                        <button type="button" className={row.free === '-' ? 'is-active' : ''} onClick={() => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, free: '-' } : r)))}>Обычный</button>
                        <button type="button" className={row.free === '+' ? 'is-active' : ''} onClick={() => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, free: '+' } : r)))}>Бесплатный</button>
                      </div>
                    </div>
                  </div>
                ))}
                {bulkMode && (
                  <div className="bq-bulk-actions">
                    <button type="button" className="bq-btn bq-btn-ghost" onClick={() => setGcRows((rows) => [...rows, emptyGcRow(sharedStart)])}>+ Ещё</button>
                    <button
                      type="button"
                      className="bq-btn bq-btn-ghost"
                      onClick={() => {
                        const base = gcRows[0] || emptyGcRow(sharedStart)
                        setGcRows((rows) => [
                          ...rows,
                          {
                            ...emptyGcRow(sharedStart),
                            startAmount: base.startAmount,
                            targetAmount: String(Number(base.targetAmount) + 100),
                            rewardAmount: base.rewardAmount,
                            maxBet: base.maxBet,
                            chatRef: base.chatRef,
                            maxUsers: base.maxUsers,
                            free: base.free,
                          },
                        ])
                      }}
                    >
                      Клон +100 цели
                    </button>
                  </div>
                )}
              </div>
            )}

            <div className="bq-preview">
              <div className="bq-preview-top">
                <span>Так выглядела бы команда в чате</span>
                <button
                  type="button"
                  className="bq-link"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(cmdPreview)
                      notifyAdmin('Команда скопирована')
                    } catch {
                      notifyAdmin('Не удалось скопировать', { error: true })
                    }
                  }}
                >
                  Копировать
                </button>
              </div>
              <code>{cmdPreview}</code>
            </div>

            <button
              type="button"
              className="bq-btn bq-btn-primary bq-btn-block bq-save"
              disabled={saving}
              onClick={mode === 'subs' ? saveSubs : saveGcs}
            >
              {saving
                ? 'Сохраняю…'
                : bulkMode
                  ? `Создать ${readyCount} ${mode === 'subs' ? 'заданий' : 'челленджей'}`
                  : mode === 'subs'
                    ? 'Создать задание'
                    : 'Создать челлендж'}
            </button>
          </aside>
        )}

        <section className="bq-list">
          <div className="bq-list-head">
            <h3>{mode === 'subs' ? 'Список заданий на подписку' : 'Список челленджей'}</h3>
            <span>Показано {filtered.length} из {list.length}</span>
          </div>

          {loading ? (
            <div className="bq-empty">
              <div className="bq-loader" />
              <strong>Загружаю задания…</strong>
            </div>
          ) : filtered.length === 0 ? (
            <div className="bq-empty">
              <strong>Пока пусто</strong>
              <p>Создайте задание в конструкторе или снимите фильтр / поиск.</p>
            </div>
          ) : (
            <div className="bq-cards">
              {filtered.map((item, idx) => {
                const st = statusMeta(item)
                const busy = busyId === item.id
                if (mode === 'subs') {
                  return (
                    <article key={item.id} className={`bq-card bq-card-sub is-${st.cls}`} style={{ '--i': idx }}>
                      <div className="bq-card-top">
                        <div>
                        <h4>{item.chatRef}</h4>
                        <p>Номер задания <b>#{item.id}</b> · награда <b>{item.reward}</b></p>
                        </div>
                        <span className={`bq-status is-${st.cls}${st.pulse ? ' is-pulse' : ''}`}>{st.text}</span>
                      </div>
                      <div className="bq-card-stats">
                        <div><em>{item.stats?.clicks ?? 0}</em><span>Клики</span></div>
                        <div><em>{item.stats?.subs ?? 0}</em><span>Подписки</span></div>
                        <div><em>{item.stats?.skips ?? 0}</em><span>Пропуски</span></div>
                        <div><em>{item.stats?.rewardTotal ?? 0}</em><span>Выдано</span></div>
                      </div>
                      <div className="bq-card-meta">
                        <span><b>Старт:</b> {fmtDt(item.startsAt)}</span>
                        <span>
                          {item.totalCap != null
                            ? <><b>Лимит людей:</b> {item.stats?.subs ?? 0} из {item.totalCap}</>
                            : item.ttlExpiresAt
                              ? <><b>До:</b> {fmtDt(item.ttlExpiresAt)}</>
                              : <><b>Лимит:</b> без ограничений</>}
                        </span>
                      </div>
                      <div className="bq-card-actions">
                        {item.scheduled && (
                          <button type="button" className="bq-btn-mini is-accent" disabled={busy} onClick={() => runCardAction(item.id, () => patchBotSubTask(item.id, { activateNow: true }), 'Запущено сейчас')}>
                            Запустить
                          </button>
                        )}
                        <button type="button" className="bq-btn-mini" disabled={busy} onClick={() => runCardAction(item.id, () => patchBotSubTask(item.id, { active: !item.active }))}>
                          {item.active ? 'Пауза' : 'Включить'}
                        </button>
                        <button type="button" className="bq-btn-mini is-danger" disabled={busy} onClick={() => setDeleteTarget({ kind: 'sub', id: item.id, label: item.chatRef })}>
                          Удалить задание
                        </button>
                      </div>
                    </article>
                  )
                }
                const slotPct = item.maxUsers
                  ? Math.min(100, Math.round((item.completedUsers / item.maxUsers) * 100))
                  : 0
                return (
                  <article key={item.id} className={`bq-card bq-card-gc is-${st.cls}`} style={{ '--i': idx }}>
                    <div className="bq-card-top">
                      <div>
                        <h4>
                          {item.startAmount}
                          <span className="bq-arrow">→</span>
                          {item.targetAmount}
                          <span className="bq-reward">+{item.rewardAmount}</span>
                        </h4>
                        <p>Номер <b>#{item.id}</b> · {item.targetChatRef || 'любой чат'} · {item.free === '+' ? 'бесплатный' : 'обычный'}</p>
                      </div>
                      <span className={`bq-status is-${st.cls}${st.pulse ? ' is-pulse' : ''}`}>{st.text}</span>
                    </div>
                    <div className="bq-card-stats bq-card-stats-3">
                      <div>
                        <em>{item.completedUsers}{item.maxUsers != null ? `/${item.maxUsers}` : ''}</em>
                        <span>Занято слотов</span>
                        {item.maxUsers != null && (
                          <div className="bq-mini-bar"><i style={{ width: `${slotPct}%` }} /></div>
                        )}
                      </div>
                      <div><em>{item.betLimit ?? '∞'}</em><span>Макс. ставка</span></div>
                      <div><em>{fmtDt(item.startsAt)}</em><span>Время старта</span></div>
                    </div>
                    <div className="bq-card-actions">
                      {item.scheduled && (
                        <button type="button" className="bq-btn-mini is-accent" disabled={busy} onClick={() => runCardAction(item.id, () => patchBotChallenge(item.id, { activateNow: true }), 'Челлендж в эфире')}>
                          Запустить
                        </button>
                      )}
                      <button type="button" className="bq-btn-mini" disabled={busy} onClick={() => duplicateGc(item)}>
                        Дублировать
                      </button>
                      {item.status !== 'disabled' ? (
                        <button
                          type="button"
                          className="bq-btn-mini"
                          disabled={busy}
                          onClick={() => runCardAction(item.id, () => disableBotChallenge(item.id), 'Челлендж выключен')}
                        >
                          Выключить
                        </button>
                      ) : (
                        <button type="button" className="bq-btn-mini is-accent" disabled={busy} onClick={() => runCardAction(item.id, () => patchBotChallenge(item.id, { status: 'active' }), 'Включено')}>
                          Включить
                        </button>
                      )}
                      <button
                        type="button"
                        className="bq-btn-mini is-danger"
                        disabled={busy}
                        onClick={() => setDeleteTarget({ kind: 'gc', id: item.id, label: `#${item.id} ${item.startAmount}→${item.targetAmount}` })}
                      >
                        Удалить задание
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>
      </div>

      <AdminActionModal
        open={Boolean(deleteTarget)}
        title="Удалить задание?"
        description={`«${deleteTarget?.label || ''}» будет удалено навсегда. Это действие нельзя отменить.`}
        confirmText="Удалить задание"
        danger
        loading={saving}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
