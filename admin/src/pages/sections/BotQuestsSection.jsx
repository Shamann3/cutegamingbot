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
  disableBotChallenge,
} from '../../lib/adminClient'

const START_PRESETS = [
  { label: 'Сейчас', minutes: 0 },
  { label: '+15 мин', minutes: 15 },
  { label: '+1 час', minutes: 60 },
  { label: '+3 часа', minutes: 180 },
  { label: '+1 день', minutes: 1440 },
  { label: '+3 дня', minutes: 4320 },
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

function statusChip(item) {
  if (item.status === 'disabled') return { cls: 'bq-chip-off', text: 'Выкл' }
  if (item.scheduled) return { cls: 'bq-chip-soon', text: 'Скоро' }
  if (item.effectiveActive) return { cls: 'bq-chip-live', text: 'В эфире' }
  if (item.active === false) return { cls: 'bq-chip-off', text: 'Пауза' }
  return { cls: 'bq-chip-muted', text: 'Неактивно' }
}

export default function BotQuestsSection() {
  const [mode, setMode] = useState('subs') // subs | gc
  const [overview, setOverview] = useState(null)
  const [subs, setSubs] = useState([])
  const [gcs, setGcs] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [filter, setFilter] = useState('all') // all | live | soon | off
  const [bulkMode, setBulkMode] = useState(false)
  const [sharedStart, setSharedStart] = useState('')
  const [subRows, setSubRows] = useState([emptySubRow()])
  const [gcRows, setGcRows] = useState([emptyGcRow()])
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [composerOpen, setComposerOpen] = useState(true)

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

  const applySharedStart = (value) => {
    setSharedStart(value)
    setSubRows((rows) => rows.map((r) => ({ ...r, startsAt: value })))
    setGcRows((rows) => rows.map((r) => ({ ...r, startsAt: value })))
  }

  const list = mode === 'subs' ? subs : gcs
  const filtered = useMemo(() => {
    return list.filter((item) => {
      if (filter === 'live') return item.effectiveActive
      if (filter === 'soon') return item.scheduled
      if (filter === 'off') return item.status === 'disabled' || item.active === false || (!item.effectiveActive && !item.scheduled)
      return true
    })
  }, [list, filter])

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
        if (res.errors?.length) {
          notifyAdmin(res.errors[0].error, { error: true })
        }
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
        if (res.errors?.length) {
          notifyAdmin(res.errors[0].error, { error: true })
        }
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

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setSaving(true)
    try {
      if (deleteTarget.kind === 'sub') {
        await deleteBotSubTask(deleteTarget.id)
        notifyAdmin('Задание удалено')
      } else {
        await disableBotChallenge(deleteTarget.id)
        notifyAdmin('Челлендж отключён')
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

  return (
    <div className="panel-content bq-root">
      <header className="bq-hero">
        <div className="bq-hero-glow" aria-hidden="true" />
        <div className="bq-hero-copy">
          <p className="bq-kicker">Owner · Telegram Bot</p>
          <h2 className="bq-title">Мастер заданий</h2>
          <p className="bq-lead">
            Создавайте задания на подписку и игровые челленджи так же, как команды
            <code> +задание </code> и <code> +заданиеч </code> — но быстрее, пачками и с отложенным стартом.
          </p>
        </div>
        <div className="bq-metrics">
          <div className="bq-metric" style={{ '--i': 0 }}>
            <span className="bq-metric-label">Подписки в эфире</span>
            <strong className="bq-metric-value">{ov.subTasks.active}</strong>
            <span className="bq-metric-sub">из {ov.subTasks.total} · скоро {ov.subTasks.scheduled}</span>
          </div>
          <div className="bq-metric" style={{ '--i': 1 }}>
            <span className="bq-metric-label">Челленджи в эфире</span>
            <strong className="bq-metric-value">{ov.challenges.active}</strong>
            <span className="bq-metric-sub">скоро {ov.challenges.scheduled} · выкл {ov.challenges.disabled}</span>
          </div>
          <div className="bq-metric" style={{ '--i': 2 }}>
            <span className="bq-metric-label">Выдано за подписки</span>
            <strong className="bq-metric-value">{ov.subRewardPaidTotal}</strong>
            <span className="bq-metric-sub">quebalance · всего</span>
          </div>
        </div>
      </header>

      <div className="bq-toolbar">
        <div className="bq-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'subs'}
            className={`bq-tab${mode === 'subs' ? ' bq-tab-active' : ''}`}
            onClick={() => setMode('subs')}
          >
            Подписки
            <span className="bq-tab-count">{subs.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'gc'}
            className={`bq-tab${mode === 'gc' ? ' bq-tab-active' : ''}`}
            onClick={() => setMode('gc')}
          >
            Челленджи
            <span className="bq-tab-count">{gcs.length}</span>
          </button>
        </div>

        <div className="bq-filters">
          {[
            ['all', 'Все'],
            ['live', 'В эфире'],
            ['soon', 'Скоро'],
            ['off', 'Выкл'],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`bq-pill${filter === id ? ' bq-pill-active' : ''}`}
              onClick={() => setFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="bq-toolbar-actions">
          <button type="button" className="panel-users-btn" onClick={load} disabled={loading}>
            Обновить
          </button>
          <button
            type="button"
            className="panel-users-btn panel-users-btn-primary"
            onClick={() => setComposerOpen((v) => !v)}
          >
            {composerOpen ? 'Скрыть мастер' : 'Открыть мастер'}
          </button>
        </div>
      </div>

      <div className={`bq-layout${composerOpen ? '' : ' bq-layout-wide'}`}>
        {composerOpen && (
          <aside className="bq-composer panel-shelf">
            <div className="bq-composer-head">
              <h3>{mode === 'subs' ? 'Новые подписки' : 'Новые челленджи'}</h3>
              <label className="bq-switch">
                <input
                  type="checkbox"
                  checked={bulkMode}
                  onChange={(e) => setBulkMode(e.target.checked)}
                />
                <span>Пакетный режим</span>
              </label>
            </div>

            <div className="bq-schedule">
              <span className="bq-field-label">Общий старт для пакета</span>
              <input
                className="panel-users-input"
                type="datetime-local"
                value={sharedStart}
                onChange={(e) => applySharedStart(e.target.value)}
              />
              <div className="bq-preset-row">
                {START_PRESETS.map((p) => (
                  <button
                    key={p.label}
                    type="button"
                    className="bq-mini"
                    onClick={() => applySharedStart(presetStart(p.minutes))}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <p className="bq-hint">
                Пусто = сразу в меню «Задания». Будущая дата — игроки увидят задание только после старта.
              </p>
            </div>

            {mode === 'subs' ? (
              <div className="bq-rows">
                {(bulkMode ? subRows : subRows.slice(0, 1)).map((row, idx) => (
                  <div key={row.key} className="bq-row" style={{ '--i': idx }}>
                    <label>
                      <span>Канал / чат</span>
                      <input
                        className="panel-users-input"
                        placeholder="@CuteGamingNews или https://t.me/…"
                        value={row.chatRef}
                        onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, chatRef: e.target.value } : r)))}
                      />
                    </label>
                    <div className="bq-grid-2">
                      <label>
                        <span>Награда</span>
                        <input
                          className="panel-users-input"
                          value={row.reward}
                          onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, reward: e.target.value } : r)))}
                        />
                      </label>
                      <label>
                        <span>Старт</span>
                        <input
                          className="panel-users-input"
                          type="datetime-local"
                          value={row.startsAt}
                          onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, startsAt: e.target.value } : r)))}
                        />
                      </label>
                    </div>
                    <div className="bq-limit-modes">
                      {[
                        ['unlimited', 'Безлимит'],
                        ['cap', 'Лимит людей'],
                        ['ttl', 'TTL'],
                      ].map(([id, label]) => (
                        <button
                          key={id}
                          type="button"
                          className={`bq-mini${row.limitMode === id ? ' bq-mini-active' : ''}`}
                          onClick={() => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, limitMode: id } : r)))}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    {row.limitMode === 'cap' && (
                      <label>
                        <span>Макс. людей (как 30ч)</span>
                        <input
                          className="panel-users-input"
                          type="number"
                          min={1}
                          value={row.totalCap}
                          onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, totalCap: e.target.value } : r)))}
                        />
                      </label>
                    )}
                    {row.limitMode === 'ttl' && (
                      <div className="bq-grid-2">
                        <label>
                          <span>TTL</span>
                          <input
                            className="panel-users-input"
                            type="number"
                            min={1}
                            value={row.ttlValue}
                            onChange={(e) => setSubRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, ttlValue: e.target.value } : r)))}
                          />
                        </label>
                        <label>
                          <span>Единица</span>
                          <select
                            className="panel-users-input"
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
                    {bulkMode && subRows.length > 1 && (
                      <button
                        type="button"
                        className="bq-row-remove"
                        onClick={() => setSubRows((rows) => rows.filter((r) => r.key !== row.key))}
                      >
                        Убрать строку
                      </button>
                    )}
                  </div>
                ))}
                {bulkMode && (
                  <button
                    type="button"
                    className="panel-users-btn"
                    onClick={() => setSubRows((rows) => [...rows, emptySubRow(sharedStart)])}
                  >
                    + Ещё канал
                  </button>
                )}
                <div className="bq-preview">
                  <span className="bq-preview-label">Эквивалент команды</span>
                  <code>
                    +задание {(subRows[0]?.chatRef || '@channel').trim() || '@channel'} {subRows[0]?.reward || '2'}
                    {subRows[0]?.limitMode === 'cap' ? ` ${subRows[0].totalCap}ч` : ''}
                    {subRows[0]?.limitMode === 'ttl' ? ` ${subRows[0].ttlValue}${subRows[0].ttlUnit}` : ''}
                  </code>
                </div>
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-primary bq-save"
                  disabled={saving}
                  onClick={saveSubs}
                >
                  {saving ? 'Сохраняю…' : bulkMode ? `Создать ${subRows.filter((r) => r.chatRef.trim()).length || 0} заданий` : 'Создать задание'}
                </button>
              </div>
            ) : (
              <div className="bq-rows">
                {(bulkMode ? gcRows : gcRows.slice(0, 1)).map((row, idx) => (
                  <div key={row.key} className="bq-row" style={{ '--i': idx }}>
                    <div className="bq-grid-3">
                      <label>
                        <span>Старт КУТ</span>
                        <input
                          className="panel-users-input"
                          type="number"
                          min={1}
                          value={row.startAmount}
                          onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, startAmount: e.target.value } : r)))}
                        />
                      </label>
                      <label>
                        <span>Цель КУТ</span>
                        <input
                          className="panel-users-input"
                          type="number"
                          min={1}
                          value={row.targetAmount}
                          onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, targetAmount: e.target.value } : r)))}
                        />
                      </label>
                      <label>
                        <span>Награда</span>
                        <input
                          className="panel-users-input"
                          type="number"
                          min={1}
                          value={row.rewardAmount}
                          onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, rewardAmount: e.target.value } : r)))}
                        />
                      </label>
                    </div>
                    <div className="bq-grid-2">
                      <label>
                        <span>Макс. ставка (0 = нет)</span>
                        <input
                          className="panel-users-input"
                          type="number"
                          min={0}
                          value={row.maxBet}
                          onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, maxBet: e.target.value } : r)))}
                        />
                      </label>
                      <label>
                        <span>Слоты (пусто = ∞)</span>
                        <input
                          className="panel-users-input"
                          type="number"
                          min={0}
                          placeholder="10"
                          value={row.maxUsers}
                          onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, maxUsers: e.target.value } : r)))}
                        />
                      </label>
                    </div>
                    <label>
                      <span>Чат (опционально)</span>
                      <input
                        className="panel-users-input"
                        placeholder="@CuteGamingChat или любой чат"
                        value={row.chatRef}
                        onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, chatRef: e.target.value } : r)))}
                      />
                    </label>
                    <div className="bq-grid-2">
                      <label>
                        <span>Старт</span>
                        <input
                          className="panel-users-input"
                          type="datetime-local"
                          value={row.startsAt}
                          onChange={(e) => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, startsAt: e.target.value } : r)))}
                        />
                      </label>
                      <div className="bq-limit-modes" style={{ alignSelf: 'end' }}>
                        <button
                          type="button"
                          className={`bq-mini${row.free === '-' ? ' bq-mini-active' : ''}`}
                          onClick={() => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, free: '-' } : r)))}
                        >
                          Обычный −
                        </button>
                        <button
                          type="button"
                          className={`bq-mini${row.free === '+' ? ' bq-mini-active' : ''}`}
                          onClick={() => setGcRows((rows) => rows.map((r) => (r.key === row.key ? { ...r, free: '+' } : r)))}
                        >
                          Бесплатный +
                        </button>
                      </div>
                    </div>
                    {bulkMode && gcRows.length > 1 && (
                      <button
                        type="button"
                        className="bq-row-remove"
                        onClick={() => setGcRows((rows) => rows.filter((r) => r.key !== row.key))}
                      >
                        Убрать строку
                      </button>
                    )}
                  </div>
                ))}
                {bulkMode && (
                  <div className="bq-bulk-actions">
                    <button
                      type="button"
                      className="panel-users-btn"
                      onClick={() => setGcRows((rows) => [...rows, emptyGcRow(sharedStart)])}
                    >
                      + Ещё челлендж
                    </button>
                    <button
                      type="button"
                      className="panel-users-btn"
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
                      + Клон с целью +100
                    </button>
                  </div>
                )}
                <div className="bq-preview">
                  <span className="bq-preview-label">Эквивалент команды</span>
                  <code>
                    +заданиеч {gcRows[0]?.startAmount || 100} {gcRows[0]?.targetAmount || 500} {gcRows[0]?.rewardAmount || 100}
                    {gcRows[0]?.maxBet ? ` ${gcRows[0].maxBet}` : ''}
                    {gcRows[0]?.chatRef ? ` ${gcRows[0].chatRef}` : ''}
                    {gcRows[0]?.maxUsers ? ` 0/${gcRows[0].maxUsers}` : ''}
                    {` ${gcRows[0]?.free || '-'}`}
                  </code>
                </div>
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-primary bq-save"
                  disabled={saving}
                  onClick={saveGcs}
                >
                  {saving ? 'Создаю…' : bulkMode ? `Создать ${gcRows.length} челленджей` : 'Создать челлендж'}
                </button>
              </div>
            )}
          </aside>
        )}

        <section className="bq-list">
          {loading ? (
            <div className="bq-empty">Загрузка…</div>
          ) : filtered.length === 0 ? (
            <div className="bq-empty">
              <strong>Пока пусто</strong>
              <p>Создайте первое задание в мастере слева — или снимите фильтр.</p>
            </div>
          ) : mode === 'subs' ? (
            <div className="bq-cards">
              {filtered.map((item, idx) => {
                const chip = statusChip(item)
                return (
                  <article key={item.id} className="bq-card" style={{ '--i': idx }}>
                    <div className="bq-card-top">
                      <div>
                        <h4 className="bq-card-title">{item.chatRef}</h4>
                        <p className="bq-card-sub">#{item.id} · награда {item.reward}</p>
                      </div>
                      <span className={`bq-chip ${chip.cls}`}>{chip.text}</span>
                    </div>
                    <div className="bq-card-stats">
                      <div><em>{item.stats?.clicks ?? 0}</em><span>клики</span></div>
                      <div><em>{item.stats?.subs ?? 0}</em><span>подписки</span></div>
                      <div><em>{item.stats?.skips ?? 0}</em><span>скипы</span></div>
                      <div><em>{item.stats?.rewardTotal ?? 0}</em><span>выдано</span></div>
                    </div>
                    <div className="bq-card-meta">
                      <span>Старт: {fmtDt(item.startsAt)}</span>
                      <span>
                        {item.totalCap != null
                          ? `Лимит: ${item.stats?.subs ?? 0}/${item.totalCap}`
                          : item.ttlExpiresAt
                            ? `До: ${fmtDt(item.ttlExpiresAt)}`
                            : 'Безлимит'}
                      </span>
                    </div>
                    <div className="bq-card-actions">
                      {item.scheduled && (
                        <button
                          type="button"
                          className="bq-mini bq-mini-active"
                          onClick={async () => {
                            try {
                              await patchBotSubTask(item.id, { activateNow: true })
                              notifyAdmin('Запущено сейчас')
                              await load()
                            } catch (e) {
                              notifyAdmin(e?.message || 'Ошибка', { error: true })
                            }
                          }}
                        >
                          Запустить сейчас
                        </button>
                      )}
                      <button
                        type="button"
                        className="bq-mini"
                        onClick={async () => {
                          try {
                            await patchBotSubTask(item.id, { active: !item.active })
                            await load()
                          } catch (e) {
                            notifyAdmin(e?.message || 'Ошибка', { error: true })
                          }
                        }}
                      >
                        {item.active ? 'Пауза' : 'Включить'}
                      </button>
                      <button
                        type="button"
                        className="bq-mini bq-mini-danger"
                        onClick={() => setDeleteTarget({ kind: 'sub', id: item.id, label: item.chatRef })}
                      >
                        Удалить
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          ) : (
            <div className="bq-cards">
              {filtered.map((item, idx) => {
                const chip = statusChip(item)
                return (
                  <article key={item.id} className="bq-card bq-card-gc" style={{ '--i': idx }}>
                    <div className="bq-card-top">
                      <div>
                        <h4 className="bq-card-title">
                          {item.startAmount} → {item.targetAmount}
                          <span className="bq-reward"> +{item.rewardAmount}</span>
                        </h4>
                        <p className="bq-card-sub">
                          #{item.id} · {item.targetChatRef || 'любой чат'} · {item.free === '+' ? 'бесплатный' : 'обычный'}
                        </p>
                      </div>
                      <span className={`bq-chip ${chip.cls}`}>{chip.text}</span>
                    </div>
                    <div className="bq-card-stats">
                      <div>
                        <em>
                          {item.completedUsers}
                          {item.maxUsers != null ? `/${item.maxUsers}` : ''}
                        </em>
                        <span>слоты</span>
                      </div>
                      <div><em>{item.betLimit ?? '∞'}</em><span>макс. ставка</span></div>
                      <div><em>{fmtDt(item.startsAt)}</em><span>старт</span></div>
                    </div>
                    <div className="bq-card-actions">
                      {item.scheduled && (
                        <button
                          type="button"
                          className="bq-mini bq-mini-active"
                          onClick={async () => {
                            try {
                              await patchBotChallenge(item.id, { activateNow: true })
                              notifyAdmin('Челлендж в эфире')
                              await load()
                            } catch (e) {
                              notifyAdmin(e?.message || 'Ошибка', { error: true })
                            }
                          }}
                        >
                          Запустить сейчас
                        </button>
                      )}
                      <button type="button" className="bq-mini" onClick={() => duplicateGc(item)}>
                        Дублировать
                      </button>
                      {item.status !== 'disabled' ? (
                        <button
                          type="button"
                          className="bq-mini bq-mini-danger"
                          onClick={() => setDeleteTarget({ kind: 'gc', id: item.id, label: `#${item.id} ${item.startAmount}→${item.targetAmount}` })}
                        >
                          Отключить
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="bq-mini"
                          onClick={async () => {
                            try {
                              await patchBotChallenge(item.id, { status: 'active' })
                              await load()
                            } catch (e) {
                              notifyAdmin(e?.message || 'Ошибка', { error: true })
                            }
                          }}
                        >
                          Включить
                        </button>
                      )}
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
        title={deleteTarget?.kind === 'sub' ? 'Удалить задание?' : 'Отключить челлендж?'}
        description={
          deleteTarget?.kind === 'sub'
            ? `«${deleteTarget?.label}» будет удалено вместе с привязкой. Статистика подписок сохранится в истории done.`
            : `«${deleteTarget?.label}» станет недоступен игрокам (soft-disable, как −заданиеч).`
        }
        confirmText={deleteTarget?.kind === 'sub' ? 'Удалить' : 'Отключить'}
        danger
        loading={saving}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
