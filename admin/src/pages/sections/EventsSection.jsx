import { useCallback, useEffect, useRef, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import {
  cancelScheduledBroadcast,
  createTimedQuest,
  fetchScheduledBroadcasts,
  fetchTimedQuests,
  fetchUpcomingEvents,
  scheduleQuestEvent,
  sendBroadcast,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDt(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtDtLocal(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function toIsoUtc(localStr) {
  if (!localStr) return null
  return new Date(localStr).toISOString()
}

function relTime(iso) {
  if (!iso) return ''
  const diff = new Date(iso) - Date.now()
  const abs = Math.abs(diff)
  const past = diff < 0
  if (abs < 60_000) return past ? 'только что' : 'через <1 мин'
  if (abs < 3_600_000) return `${past ? '' : 'через '}${Math.round(abs / 60_000)} мин${past ? ' назад' : ''}`
  if (abs < 86_400_000) return `${past ? '' : 'через '}${Math.round(abs / 3_600_000)} ч${past ? ' назад' : ''}`
  return `${past ? '' : 'через '}${Math.round(abs / 86_400_000)} дн${past ? ' назад' : ''}`
}

const RECURRENCE_LABELS = { daily: 'Ежедневно', weekly: 'Еженедельно' }

const PERIOD_OPTIONS = [
  { value: 'hourly', label: '⏱ Почасовое' },
  { value: 'daily', label: '📅 Ежедневное' },
  { value: 'weekly', label: '📆 Недельное' },
]

const ACTION_OPTIONS = [
  { value: 'harvest', label: 'Сбор урожая' },
  { value: 'plant', label: 'Посадка' },
  { value: 'water', label: 'Полив' },
  { value: 'craft', label: 'Крафт' },
  { value: 'claim_daily_seed', label: 'Получить семя' },
  { value: 'buy', label: 'Купить в магазине' },
  { value: 'sell', label: 'Продать' },
]

// ---------------------------------------------------------------------------
// Upcoming timeline
// ---------------------------------------------------------------------------

function UpcomingTimeline({ refreshKey }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await fetchUpcomingEvents())
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка загрузки', { error: true })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  if (loading) return <p className="panel-shelf-muted">Загрузка…</p>
  if (!data || data.events.length === 0) {
    return <p className="panel-shelf-muted">Нет запланированных событий</p>
  }

  return (
    <div className="ev-timeline">
      {data.events.map((ev, i) => (
        <div key={i} className={`ev-timeline-item ev-type-${ev.type}`}>
          <div className="ev-timeline-dot" />
          <div className="ev-timeline-content">
            <div className="ev-timeline-head">
              <time className="ev-timeline-time">{fmtDt(ev.at)}</time>
              <span className="ev-timeline-rel">{relTime(ev.at)}</span>
              <span className={`ev-type-badge ev-type-${ev.type}`}>
                {ev.type === 'quest_activate' ? '🟢 Старт задания' :
                 ev.type === 'quest_deactivate' ? '🔴 Конец задания' :
                 '📢 Рассылка'}
              </span>
              {ev.recurrence && (
                <span className="ev-recur-badge">
                  🔁 {RECURRENCE_LABELS[ev.recurrence] || ev.recurrence}
                </span>
              )}
            </div>
            <p className="ev-timeline-title">
              {ev.questEmoji || ''} {ev.questTitle || ev.title || ev.label || ''}
              {ev.periodLabel ? <span className="ev-period-label"> · {ev.periodLabel}</span> : null}
            </p>
            {ev.recipientCount != null && (
              <p className="ev-timeline-meta">Получателей: {ev.recipientCount}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Timed quests tab
// ---------------------------------------------------------------------------

const EMPTY_TIMED_QUEST = {
  key: '',
  period: 'daily',
  action: 'harvest',
  target: 5,
  title: '',
  description: '',
  emoji: '⏰',
  enabled: true,
  targetScope: 'any',
  rewards: [{ kind: 'kut', amount: 50, itemId: null }],
  activeFrom: '',
  activeUntil: '',
  recurrence: '',
  recurrenceEnd: '',
}

function TimedQuestsTab({ onRefreshTimeline }) {
  const [quests, setQuests] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(EMPTY_TIMED_QUEST)
  const [saving, setSaving] = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [editSchedule, setEditSchedule] = useState({ activeFrom: '', activeUntil: '', recurrence: '', recurrenceEnd: '' })
  const [savingSched, setSavingSched] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await fetchTimedQuests()
      setQuests(d.quests || [])
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка', { error: true })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    setSaving(true)
    try {
      const body = {
        ...form,
        target: Number(form.target),
        activeFrom: form.activeFrom ? toIsoUtc(form.activeFrom) : undefined,
        activeUntil: form.activeUntil ? toIsoUtc(form.activeUntil) : undefined,
        recurrence: form.recurrence || undefined,
        recurrenceEnd: form.recurrenceEnd ? toIsoUtc(form.recurrenceEnd) : undefined,
      }
      await createTimedQuest(body)
      notifyAdmin(`Задание «${form.title}» создано`)
      setShowCreate(false)
      setForm(EMPTY_TIMED_QUEST)
      await load()
      onRefreshTimeline?.()
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка создания', { error: true })
    } finally {
      setSaving(false)
    }
  }

  const handleOpenSchedule = (q) => {
    setEditTarget(q)
    setEditSchedule({
      activeFrom: fmtDtLocal(q.activeFrom),
      activeUntil: fmtDtLocal(q.activeUntil),
      recurrence: q.recurrence || '',
      recurrenceEnd: fmtDtLocal(q.recurrenceEnd),
    })
  }

  const handleSaveSchedule = async () => {
    if (!editTarget) return
    setSavingSched(true)
    try {
      const fields = {
        activeFrom: editSchedule.activeFrom ? toIsoUtc(editSchedule.activeFrom) : null,
        activeUntil: editSchedule.activeUntil ? toIsoUtc(editSchedule.activeUntil) : null,
        recurrence: editSchedule.recurrence || null,
        recurrenceEnd: editSchedule.recurrenceEnd ? toIsoUtc(editSchedule.recurrenceEnd) : null,
        clearSchedule: !editSchedule.activeFrom && !editSchedule.activeUntil,
      }
      await scheduleQuestEvent(editTarget.id, fields)
      notifyAdmin('Расписание сохранено')
      setEditTarget(null)
      await load()
      onRefreshTimeline?.()
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка', { error: true })
    } finally {
      setSavingSched(false)
    }
  }

  return (
    <div className="ev-tab-content">
      {/* Schedule editor modal */}
      {editTarget && (
        <div className="admin-modal-backdrop" onClick={() => setEditTarget(null)}>
          <div className="admin-modal ev-sched-modal" onClick={(e) => e.stopPropagation()}>
            <p className="panel-shelf-label">Расписание задания</p>
            <h3 className="ev-modal-title">{editTarget.emoji} {editTarget.title}</h3>
            <div className="ev-sched-fields">
              <label className="ev-field-label">Начало события</label>
              <input type="datetime-local" className="panel-users-input" value={editSchedule.activeFrom}
                onChange={(e) => setEditSchedule(s => ({ ...s, activeFrom: e.target.value }))} />

              <label className="ev-field-label">Конец события</label>
              <input type="datetime-local" className="panel-users-input" value={editSchedule.activeUntil}
                onChange={(e) => setEditSchedule(s => ({ ...s, activeUntil: e.target.value }))} />

              <label className="ev-field-label">Повторение</label>
              <select className="panel-users-input" value={editSchedule.recurrence}
                onChange={(e) => setEditSchedule(s => ({ ...s, recurrence: e.target.value }))}>
                <option value="">Без повторения</option>
                <option value="daily">Ежедневно</option>
                <option value="weekly">Еженедельно</option>
              </select>

              {editSchedule.recurrence && <>
                <label className="ev-field-label">Конец серии (необязательно)</label>
                <input type="datetime-local" className="panel-users-input" value={editSchedule.recurrenceEnd}
                  onChange={(e) => setEditSchedule(s => ({ ...s, recurrenceEnd: e.target.value }))} />
              </>}
            </div>
            <div className="ev-modal-actions">
              <button className="panel-users-btn panel-users-btn-primary" onClick={handleSaveSchedule} disabled={savingSched}>
                {savingSched ? 'Сохранение…' : 'Сохранить'}
              </button>
              <button className="panel-users-btn" onClick={() => setEditTarget(null)}>Отмена</button>
            </div>
          </div>
        </div>
      )}

      <div className="ev-toolbar">
        <button className="panel-users-btn panel-users-btn-primary" onClick={() => setShowCreate(true)}>
          + Создать ивент
        </button>
      </div>

      {loading && <p className="panel-shelf-muted">Загрузка…</p>}

      {!loading && quests.length === 0 && (
        <p className="panel-shelf-muted">Нет заданий с расписанием. Создайте первый ивент или добавьте расписание к существующему заданию в разделе «Контент».</p>
      )}

      {!loading && quests.length > 0 && (
        <div className="ev-quest-list">
          {quests.map((q) => (
            <div key={q.id} className={`ev-quest-card sched-${q.schedStatus || 'none'}`}>
              <div className="ev-quest-head">
                <span className="ev-quest-emoji">{q.emoji}</span>
                <div className="ev-quest-info">
                  <span className="ev-quest-title">{q.title}</span>
                  <span className="ev-quest-meta">{q.periodLabel} · {q.actionLabel}</span>
                </div>
                <div className="ev-quest-badges">
                  {q.schedStatus === 'active' && <span className="ev-status-badge ev-status-active">🟢 Активно</span>}
                  {q.schedStatus === 'pending' && <span className="ev-status-badge ev-status-pending">🟡 Ожидает</span>}
                  {q.schedStatus === 'ended' && <span className="ev-status-badge ev-status-ended">⚫ Завершено</span>}
                  {q.recurrence && <span className="ev-recur-badge">🔁 {RECURRENCE_LABELS[q.recurrence]}</span>}
                </div>
                <button className="panel-users-btn ev-btn-sched" onClick={() => handleOpenSchedule(q)}>
                  📅 Расписание
                </button>
              </div>
              <div className="ev-quest-schedule">
                <span>Начало: <strong>{fmtDt(q.activeFrom)}</strong></span>
                <span>Конец: <strong>{fmtDt(q.activeUntil)}</strong></span>
                {q.recurrenceEnd && <span>Серия до: <strong>{fmtDt(q.recurrenceEnd)}</strong></span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="admin-modal-backdrop" onClick={() => setShowCreate(false)}>
          <div className="admin-modal ev-create-modal" onClick={(e) => e.stopPropagation()}>
            <p className="panel-shelf-label">Новый ивент-квест</p>
            <div className="ev-create-form">
              <div className="ev-form-row">
                <div className="ev-form-field">
                  <label className="ev-field-label">Ключ</label>
                  <input className="panel-users-input" placeholder="event_harvest_spring" value={form.key}
                    onChange={(e) => setForm(f => ({ ...f, key: e.target.value }))} />
                </div>
                <div className="ev-form-field">
                  <label className="ev-field-label">Эмодзи</label>
                  <input className="panel-users-input ev-emoji-input" value={form.emoji}
                    onChange={(e) => setForm(f => ({ ...f, emoji: e.target.value }))} />
                </div>
              </div>

              <div className="ev-form-field">
                <label className="ev-field-label">Название</label>
                <input className="panel-users-input" placeholder="Весенний сбор урожая" value={form.title}
                  onChange={(e) => setForm(f => ({ ...f, title: e.target.value }))} />
              </div>

              <div className="ev-form-field">
                <label className="ev-field-label">Описание</label>
                <input className="panel-users-input" value={form.description}
                  onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} />
              </div>

              <div className="ev-form-row">
                <div className="ev-form-field">
                  <label className="ev-field-label">Период</label>
                  <select className="panel-users-input" value={form.period}
                    onChange={(e) => setForm(f => ({ ...f, period: e.target.value }))}>
                    {PERIOD_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div className="ev-form-field">
                  <label className="ev-field-label">Действие</label>
                  <select className="panel-users-input" value={form.action}
                    onChange={(e) => setForm(f => ({ ...f, action: e.target.value }))}>
                    {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div className="ev-form-field">
                  <label className="ev-field-label">Цель (кол-во)</label>
                  <input className="panel-users-input" type="number" min={1} max={9999} value={form.target}
                    onChange={(e) => setForm(f => ({ ...f, target: e.target.value }))} />
                </div>
              </div>

              <div className="ev-form-divider">📅 Расписание</div>

              <div className="ev-form-row">
                <div className="ev-form-field">
                  <label className="ev-field-label">Начало</label>
                  <input type="datetime-local" className="panel-users-input" value={form.activeFrom}
                    onChange={(e) => setForm(f => ({ ...f, activeFrom: e.target.value }))} />
                </div>
                <div className="ev-form-field">
                  <label className="ev-field-label">Конец</label>
                  <input type="datetime-local" className="panel-users-input" value={form.activeUntil}
                    onChange={(e) => setForm(f => ({ ...f, activeUntil: e.target.value }))} />
                </div>
              </div>

              <div className="ev-form-row">
                <div className="ev-form-field">
                  <label className="ev-field-label">Повторение</label>
                  <select className="panel-users-input" value={form.recurrence}
                    onChange={(e) => setForm(f => ({ ...f, recurrence: e.target.value }))}>
                    <option value="">Без повторения (разовый)</option>
                    <option value="daily">Ежедневно</option>
                    <option value="weekly">Еженедельно</option>
                  </select>
                </div>
                {form.recurrence && (
                  <div className="ev-form-field">
                    <label className="ev-field-label">Конец серии</label>
                    <input type="datetime-local" className="panel-users-input" value={form.recurrenceEnd}
                      onChange={(e) => setForm(f => ({ ...f, recurrenceEnd: e.target.value }))} />
                  </div>
                )}
              </div>

              <div className="ev-form-divider">🏆 Награда</div>
              <div className="ev-form-row">
                <div className="ev-form-field">
                  <label className="ev-field-label">Тип</label>
                  <select className="panel-users-input" value={form.rewards[0]?.kind || 'kut'}
                    onChange={(e) => setForm(f => ({ ...f, rewards: [{ ...f.rewards[0], kind: e.target.value }] }))}>
                    <option value="kut">KUT</option>
                    <option value="item">Предмет</option>
                  </select>
                </div>
                <div className="ev-form-field">
                  <label className="ev-field-label">Количество</label>
                  <input type="number" className="panel-users-input" min={1} value={form.rewards[0]?.amount || 50}
                    onChange={(e) => setForm(f => ({ ...f, rewards: [{ ...f.rewards[0], amount: Number(e.target.value) }] }))} />
                </div>
              </div>
            </div>
            <div className="ev-modal-actions">
              <button className="panel-users-btn panel-users-btn-primary" onClick={handleCreate} disabled={saving}>
                {saving ? 'Создание…' : 'Создать ивент'}
              </button>
              <button className="panel-users-btn" onClick={() => { setShowCreate(false); setForm(EMPTY_TIMED_QUEST) }}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Scheduled broadcasts tab
// ---------------------------------------------------------------------------

const EMPTY_BROADCAST = {
  title: '',
  body: '',
  telegramText: '',
  audience: 'all',
  label: '',
  scheduledAt: '',
}

function ScheduledBroadcastsTab({ onRefreshTimeline }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(EMPTY_BROADCAST)
  const [saving, setSaving] = useState(false)
  const [cancelTarget, setCancelTarget] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await fetchScheduledBroadcasts()
      setItems(d.items || [])
      setTotal(d.total || 0)
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка', { error: true })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSchedule = async () => {
    setSaving(true)
    try {
      await sendBroadcast({
        title: form.title,
        body: form.body,
        telegramText: form.telegramText,
        audience: form.audience,
        label: form.label,
        scheduledAt: form.scheduledAt ? toIsoUtc(form.scheduledAt) : null,
        channels: { webapp: true, telegram: !!form.telegramText },
      })
      notifyAdmin(`Рассылка запланирована на ${fmtDt(toIsoUtc(form.scheduledAt))}`)
      setShowCreate(false)
      setForm(EMPTY_BROADCAST)
      await load()
      onRefreshTimeline?.()
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка', { error: true })
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = async () => {
    if (!cancelTarget) return
    try {
      await cancelScheduledBroadcast(cancelTarget.id)
      notifyAdmin('Рассылка отменена')
      setCancelTarget(null)
      await load()
      onRefreshTimeline?.()
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка', { error: true })
    }
  }

  return (
    <div className="ev-tab-content">
      <AdminActionModal
        open={!!cancelTarget}
        title="Отменить рассылку"
        description={`Вы уверены, что хотите отменить запланированную рассылку «${cancelTarget?.title}»?`}
        confirmText="Отменить рассылку"
        danger
        onConfirm={handleCancel}
        onCancel={() => setCancelTarget(null)}
      />

      <div className="ev-toolbar">
        <button className="panel-users-btn panel-users-btn-primary" onClick={() => setShowCreate(true)}>
          + Запланировать рассылку
        </button>
        <span className="ev-toolbar-hint">Рассылок в очереди: {total}</span>
      </div>

      {loading && <p className="panel-shelf-muted">Загрузка…</p>}
      {!loading && items.length === 0 && (
        <p className="panel-shelf-muted">Нет запланированных рассылок</p>
      )}

      {!loading && items.length > 0 && (
        <div className="ev-broadcast-list">
          {items.map((b) => (
            <div key={b.id} className="ev-broadcast-card">
              <div className="ev-broadcast-head">
                <div className="ev-broadcast-info">
                  <span className="ev-broadcast-title">{b.title}</span>
                  {b.label && <span className="ev-broadcast-label">{b.label}</span>}
                </div>
                <button className="panel-users-btn panel-users-btn-danger" onClick={() => setCancelTarget(b)}>
                  Отменить
                </button>
              </div>
              <div className="ev-broadcast-meta">
                <span>🕐 {fmtDt(b.scheduledAt)}</span>
                <span className="ev-meta-rel">{relTime(b.scheduledAt)}</span>
                <span>👥 {b.audience === 'all' ? 'Все' : b.audience} · {b.recipientCount} получателей</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create scheduled broadcast modal */}
      {showCreate && (
        <div className="admin-modal-backdrop" onClick={() => setShowCreate(false)}>
          <div className="admin-modal ev-broadcast-modal" onClick={(e) => e.stopPropagation()}>
            <p className="panel-shelf-label">Запланировать рассылку</p>
            <div className="ev-create-form">
              <div className="ev-form-field">
                <label className="ev-field-label">Метка (для себя)</label>
                <input className="panel-users-input" placeholder="Пятничный ивент" value={form.label}
                  onChange={(e) => setForm(f => ({ ...f, label: e.target.value }))} />
              </div>
              <div className="ev-form-field">
                <label className="ev-field-label">Заголовок рассылки *</label>
                <input className="panel-users-input" placeholder="Новое событие!" value={form.title}
                  onChange={(e) => setForm(f => ({ ...f, title: e.target.value }))} />
              </div>
              <div className="ev-form-field">
                <label className="ev-field-label">Текст (Web App)</label>
                <textarea className="panel-users-input ev-textarea" rows={3} value={form.body}
                  onChange={(e) => setForm(f => ({ ...f, body: e.target.value }))} />
              </div>
              <div className="ev-form-field">
                <label className="ev-field-label">Telegram-текст (оставьте пустым чтобы не отправлять в TG)</label>
                <textarea className="panel-users-input ev-textarea" rows={2} value={form.telegramText}
                  onChange={(e) => setForm(f => ({ ...f, telegramText: e.target.value }))} />
              </div>
              <div className="ev-form-row">
                <div className="ev-form-field">
                  <label className="ev-field-label">Аудитория</label>
                  <select className="panel-users-input" value={form.audience}
                    onChange={(e) => setForm(f => ({ ...f, audience: e.target.value }))}>
                    <option value="all">Все игроки</option>
                    <option value="online">Онлайн</option>
                  </select>
                </div>
                <div className="ev-form-field">
                  <label className="ev-field-label">Время отправки *</label>
                  <input type="datetime-local" className="panel-users-input" value={form.scheduledAt}
                    onChange={(e) => setForm(f => ({ ...f, scheduledAt: e.target.value }))} />
                </div>
              </div>
            </div>
            <div className="ev-modal-actions">
              <button className="panel-users-btn panel-users-btn-primary" onClick={handleSchedule}
                disabled={saving || !form.title || !form.scheduledAt}>
                {saving ? 'Планирование…' : 'Запланировать'}
              </button>
              <button className="panel-users-btn" onClick={() => { setShowCreate(false); setForm(EMPTY_BROADCAST) }}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'timeline', label: '📅 Расписание' },
  { id: 'quests', label: '⚡ Ивент-квесты' },
  { id: 'broadcasts', label: '📢 Рассылки' },
]

export default function EventsSection() {
  const [tab, setTab] = useState('timeline')
  const [timelineKey, setTimelineKey] = useState(0)

  const refreshTimeline = useCallback(() => setTimelineKey((k) => k + 1), [])

  return (
    <div className="panel-events">
      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Events · Ивенты и расписание</p>
        <h2 className="panel-page-title">Ивенты и расписание</h2>
        <p className="panel-page-lead">
          Временные задания, повторяющиеся ивенты и отложенные рассылки.
          Планировщик запускает события автоматически.
        </p>
      </article>

      <div className="sys-tabs">
        {TABS.map((t) => (
          <button key={t.id} className={`sys-tab${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="ev-content">
        {tab === 'timeline' && (
          <article className="panel-shelf">
            <p className="panel-shelf-label">Ближайшие события</p>
            <UpcomingTimeline refreshKey={timelineKey} />
          </article>
        )}
        {tab === 'quests' && <TimedQuestsTab onRefreshTimeline={refreshTimeline} />}
        {tab === 'broadcasts' && <ScheduledBroadcastsTab onRefreshTimeline={refreshTimeline} />}
      </div>
    </div>
  )
}
