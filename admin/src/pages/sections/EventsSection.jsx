import { useCallback, useEffect, useRef, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import {
  cancelBroadcastRun,
  fetchScheduledBroadcasts,
  fetchTimedQuests,
  fetchUpcomingEvents,
  scheduleQuestEvent,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'
import { filterSectionTabs } from '../../constants/panelAccessTree'

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

function TimedQuestsTab({ onRefreshTimeline }) {
  const [quests, setQuests] = useState([])
  const [loading, setLoading] = useState(true)
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

      <p className="panel-shelf-muted">
        Здесь только расписание уже существующих заданий. Создание и редактирование самих квестов — в разделе «Контент».
      </p>

      {loading && <p className="panel-shelf-muted">Загрузка…</p>}

      {!loading && quests.length === 0 && (
        <p className="panel-shelf-muted">Нет заданий с расписанием. Добавьте расписание к существующему заданию в разделе «Контент».</p>
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

    </div>
  )
}

// ---------------------------------------------------------------------------
// Scheduled broadcasts tab
// ---------------------------------------------------------------------------

function ScheduledBroadcastsTab({ onRefreshTimeline }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [cancelTarget, setCancelTarget] = useState(null)
  const [cancelling, setCancelling] = useState(false)

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

  const handleCancel = async () => {
    if (!cancelTarget) return
    setCancelling(true)
    try {
      await cancelBroadcastRun(cancelTarget.id)
      notifyAdmin('Рассылка отменена')
      setCancelTarget(null)
      await load()
      onRefreshTimeline?.()
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка', { error: true })
    } finally {
      setCancelling(false)
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
        loading={cancelling}
        onConfirm={handleCancel}
        onCancel={() => { if (!cancelling) setCancelTarget(null) }}
      />

      <p className="panel-shelf-muted">
        Здесь только мониторинг очереди. Запланировать рассылку — в разделе «Рассылки» (поле «Запланировать на»).
        {' '}Рассылок в очереди: {total}
      </p>

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

export default function EventsSection({ panelTabs = null }) {
  const tabs = filterSectionTabs('events', TABS, panelTabs)
  const [tab, setTab] = useState(tabs[0]?.id || 'timeline')
  const activeTab = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id
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
        {tabs.map((t) => (
          <button key={t.id} className={`sys-tab${activeTab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="ev-content">
        {activeTab === 'timeline' && (
          <article className="panel-shelf">
            <p className="panel-shelf-label">Ближайшие события</p>
            <UpcomingTimeline refreshKey={timelineKey} />
          </article>
        )}
        {activeTab === 'quests' && <TimedQuestsTab onRefreshTimeline={refreshTimeline} />}
        {activeTab === 'broadcasts' && <ScheduledBroadcastsTab onRefreshTimeline={refreshTimeline} />}
      </div>
    </div>
  )
}
