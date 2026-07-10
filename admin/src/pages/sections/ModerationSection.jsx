import { useCallback, useEffect, useRef, useState } from 'react'
import TgPhoto from '../../components/TgPhoto'
import {
  deleteModerationLog, fetchAppealMessages, fetchAppeals, fetchModerationLogs,
  fetchModeratorStats, fetchPlayerModerationHistory,
  getAdminToken, postModerationUnban, resolveAppeal, sendAppealMessage,
  takeAppeal, uploadAppealPhoto,
} from '../../lib/adminClient'

const API_PREFIX = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmtDate(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('ru-RU', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit' }) }
  catch { return iso }
}
function fmtDateShort(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('ru-RU', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' }) }
  catch { return iso }
}
function fmtDuration(m) {
  if (!m) return null
  if (m < 60) return `${m} мин`
  if (m < 1440) return `${Math.floor(m/60)} ч ${m%60} мин`
  return `${Math.floor(m/1440)} дн`
}
function timeSince(iso) {
  if (!iso) return '—'
  const d = Date.now() - new Date(iso).getTime()
  if (d < 60000) return 'только что'
  if (d < 3600000) return `${Math.floor(d/60000)} мин назад`
  if (d < 86400000) return `${Math.floor(d/3600000)} ч назад`
  return `${Math.floor(d/86400000)} дн назад`
}

// Базовые характеристики каждой системы наказаний / снятия. Точный ярлык
// (БАН/БАНАЛЛ/БАНФУЛЛ и т.п.) собирается из base + охвата (scope) в actionMeta().
const ACTION_BASE = {
  ban:    { color:'#ef4444', glow:'#ef444440', bg:'#ef444412', icon:'🔨', root:'БАН',    nounChat:'Блокировка в группе',        removal:false },
  unban:  { color:'#22c55e', glow:'#22c55e40', bg:'#22c55e12', icon:'✅', root:'РАЗБАН',  nounChat:'Снятие блокировки',          removal:true  },
  mute:   { color:'#f97316', glow:'#f9731640', bg:'#f9731612', icon:'🔇', root:'МУТ',    nounChat:'Запрет писать в группе',     removal:false },
  unmute: { color:'#2dd4bf', glow:'#2dd4bf40', bg:'#2dd4bf12', icon:'🔊', root:'РАЗМУТ', nounChat:'Снятие мута',                removal:true  },
  kick:   { color:'#a855f7', glow:'#a855f740', bg:'#a855f712', icon:'👢', root:'КИК',    nounChat:'Исключение из группы',       removal:false },
  warn:   { color:'#eab308', glow:'#eab30840', bg:'#eab30812', icon:'⚠️', root:'ВАРН',   nounChat:'Предупреждение',             removal:false },
  unwarn: { color:'#84cc16', glow:'#84cc1640', bg:'#84cc1612', icon:'🧹', root:'РАЗВАРН',nounChat:'Снятие предупреждения',      removal:true  },
}

// Суффикс к корню и человекочитаемый охват. mute/kick не имеют «фулл».
const SCOPE_SUFFIX = { chat:'', all:'АЛЛ', full:'ФУЛЛ' }
const SCOPE_LABEL  = { chat:'в группе', all:'во всех группах', full:'во всём проекте' }
const NO_FULL = new Set(['mute', 'unmute', 'kick'])

function actionMeta(actionType, scope) {
  const base = ACTION_BASE[actionType] || ACTION_BASE.warn
  let sc = scope || 'chat'
  if (sc === 'full' && NO_FULL.has(actionType)) sc = 'all'
  const label = base.root + (SCOPE_SUFFIX[sc] || '')
  const scopeLabel = SCOPE_LABEL[sc] || ''
  // Описание: «Блокировка · во всех группах» и т.п.
  const desc = sc === 'chat' ? base.nounChat : `${base.nounChat.split(' в ')[0].split(' из ')[0]} · ${scopeLabel}`
  return { ...base, label, scope: sc, scopeLabel, desc }
}

const FILTER_TYPES = [
  { value:'', label:'Все' },
  { value:'ban', label:'Баны' },
  { value:'mute', label:'Муты' },
  { value:'kick', label:'Кики' },
  { value:'warn', label:'Предупреждения' },
  { value:'removals', label:'Снятия' },
]

// ---------------------------------------------------------------------------
// Mini history list (used inside case modal)
// ---------------------------------------------------------------------------
function MiniHistory({ items, currentId, emptyText }) {
  if (!items || items.length === 0) return <div className="mini-empty">{emptyText}</div>
  return (
    <div className="mini-list">
      {items.map((h) => {
        const m = actionMeta(h.actionType, h.scope)
        const isCurrent = h.id === currentId
        return (
          <div key={h.id} className={`mini-row${isCurrent ? ' mini-row-current' : ''}`}>
            <span className="mini-badge" style={{ background: m.color }}>{m.icon} {m.label}</span>
            <div className="mini-info">
              <span className="mini-reason">{h.reason || '—'}</span>
              <span className="mini-date">{m.scopeLabel} · {fmtDateShort(h.createdAt)}</span>
            </div>
            {isCurrent && <span className="mini-current-tag">текущее</span>}
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Case modal
// ---------------------------------------------------------------------------
function CaseModal({ item, role, onClose, onUnbanned }) {
  const meta = actionMeta(item.actionType, item.scope)
  const [unbanLoading, setUnbanLoading] = useState(false)
  const [unbanDone, setUnbanDone] = useState(false)
  const [playerHistory, setPlayerHistory] = useState([])
  const [playerHistoryLoading, setPlayerHistoryLoading] = useState(false)
  const [modHistory, setModHistory] = useState([])
  const [modHistoryLoading, setModHistoryLoading] = useState(false)
  const [tab, setTab] = useState('case') // 'case' | 'player' | 'mod'

  useEffect(() => {
    if (!item.targetId) return
    setPlayerHistoryLoading(true)
    fetchPlayerModerationHistory(item.targetId)
      .then((d) => setPlayerHistory(d.items || []))
      .catch(() => {})
      .finally(() => setPlayerHistoryLoading(false))
  }, [item.targetId])

  useEffect(() => {
    if (!item.adminId) return
    setModHistoryLoading(true)
    fetchPlayerModerationHistory(item.adminId) // reuse endpoint filtered differently
      // actually get all actions by this admin — we'll filter from full list
      .catch(() => {})
      .finally(() => setModHistoryLoading(false))
    fetchModerationLogs({ limit: 50 })
      .then(d => {
        const byMod = (d.items || []).filter(x => x.adminId === item.adminId)
        setModHistory(byMod)
      })
      .catch(() => {})
      .finally(() => setModHistoryLoading(false))
  }, [item.adminId])

  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  async function handleUnban() {
    if (!window.confirm(`Разбанить игрока ${item.targetName || item.targetId}?`)) return
    setUnbanLoading(true)
    try {
      await postModerationUnban(item.targetId)
      setUnbanDone(true)
      onUnbanned?.(item.targetId)
    } catch (e) {
      const msg = e.message || 'Ошибка разбана'
      alert(msg)
      // если сервер говорит "не забанен" — тоже скрываем кнопку
      if (msg.includes('не забанен')) setUnbanDone(true)
    }
    finally { setUnbanLoading(false) }
  }

  // кнопка видна только owner, только на бане, и только пока не разбанили в этой сессии
  const canUnban = role === 'owner' && item.actionType === 'ban' && !unbanDone
  const playerOffenseCount = playerHistory.filter(h => ['ban','mute','kick','warn'].includes(h.actionType)).length
  const isRecidivist = playerOffenseCount > 2

  return (
    <div className="case-backdrop" onClick={onClose}>
      <div className="case-modal" onClick={(e) => e.stopPropagation()}>

        {/* Обложка */}
        <div className="case-cover" style={{ '--cc': meta.color, '--cb': meta.bg, '--cg': meta.glow }}>
          <div className="case-cover-glow" />
          <div className="case-cover-inner">
            <div className="case-cover-left">
              <div className="case-stamp" style={{ borderColor: meta.color, color: meta.color }}>
                {meta.icon} {meta.label}
              </div>
              <div className="case-num">Дело #{String(item.id).padStart(6, '0')}</div>
              <div className="case-desc">{meta.desc}</div>
              {isRecidivist && (
                <div className="case-recidivist">⚠️ Рецидивист · {playerOffenseCount} нарушений</div>
              )}
            </div>
            <div className="case-cover-right">
              <div className="case-date-label">Дата</div>
              <div className="case-date-val">{fmtDate(item.createdAt)}</div>
            </div>
          </div>
          <button className="case-close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Табы */}
        <div className="case-tabs">
          <button className={`case-tab${tab==='case'?' case-tab-on':''}`} onClick={() => setTab('case')}>📋 Дело</button>
          <button className={`case-tab${tab==='player'?' case-tab-on':''}`} onClick={() => setTab('player')}>
            👤 История игрока
            {playerHistory.length > 1 && <span className="case-tab-badge">{playerHistory.length}</span>}
          </button>
          <button className={`case-tab${tab==='mod'?' case-tab-on':''}`} onClick={() => setTab('mod')}>
            🛡 Модератор
          </button>
        </div>

        {/* Тело — Дело */}
        {tab === 'case' && (
          <div className="case-body">
            <div className="case-block">
              <div className="case-block-title">👤 Участники</div>
              <div className="case-participants">
                <div className="case-side case-side-left">
                  <div className="case-side-role">Модератор</div>
                  <div className="case-side-name">{item.adminName || '—'}</div>
                  <div className="case-side-id">ID: {item.adminId}</div>
                </div>
                <div className="case-divider">
                  <div className="case-div-line" style={{ background: meta.color }} />
                  <div className="case-div-icon" style={{ color: meta.color }}>{meta.icon}</div>
                  <div className="case-div-line" style={{ background: meta.color }} />
                </div>
                <div className="case-side case-side-right">
                  <div className="case-side-role">Нарушитель</div>
                  <div className="case-side-name">{item.targetName || '—'}</div>
                  <div className="case-side-id">ID: {item.targetId}</div>
                </div>
              </div>
            </div>

            <div className="case-block">
              <div className="case-block-title">📋 Детали</div>
              <div className="case-table">
                <div className="case-row">
                  <span className="case-key">Тип</span>
                  <span className="case-val" style={{ color: meta.color, fontWeight: 700 }}>{meta.icon} {meta.label}</span>
                </div>
                <div className="case-row">
                  <span className="case-key">Охват</span>
                  <span className="case-val">{meta.scopeLabel}</span>
                </div>
                {meta.scope === 'chat' && item.chatId ? (
                  <div className="case-row">
                    <span className="case-key">Группа</span>
                    <span className="case-val" style={{ fontFamily:'monospace' }}>{item.chatId}</span>
                  </div>
                ) : null}
                {item.durationMinutes && (
                  <div className="case-row">
                    <span className="case-key">Длительность</span>
                    <span className="case-val">{fmtDuration(item.durationMinutes)}</span>
                  </div>
                )}
                <div className="case-row">
                  <span className="case-key">Причина</span>
                  <span className="case-val">{item.reason || '—'}</span>
                </div>
                {item.evidence && (
                  <div className="case-row">
                    <span className="case-key">Примечание</span>
                    <span className="case-val">{item.evidence}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="case-block">
              <div className="case-block-title">📷 Доказательство</div>
              <div className="case-proof-box">
                {item.hasProof && item.proofMediaId
                  ? <TgPhoto fileId={item.proofMediaId} onClick className="case-proof-img" />
                  : <span className="case-no-proof">Не прикреплено</span>}
              </div>
            </div>

            {canUnban && (
              <div className="case-actions">
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-success"
                  onClick={handleUnban}
                  disabled={unbanLoading}
                >
                  {unbanLoading ? 'Разбаниваем...' : 'Разбанить игрока'}
                </button>
              </div>
            )}
            {unbanDone && <div className="case-actions"><span className="case-unban-done">Игрок разбанен</span></div>}

            {role === 'owner' && (
              <div className="case-delete-zone">
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-danger"
                  onClick={async () => {
                    if (!window.confirm('Удалить запись из архива? Это действие нельзя отменить.')) return
                    try {
                      await deleteModerationLog(item.id)
                      onUnbanned?.() // reuse to trigger reload
                      onClose()
                    } catch (e) { alert(e.message || 'Ошибка удаления') }
                  }}
                >
                  Удалить из архива
                </button>
              </div>
            )}
          </div>
        )}

        {/* Тело — История игрока */}
        {tab === 'player' && (
          <div className="case-body">
            <div className="case-block">
              <div className="case-block-title">
                История нарушений · {item.targetName || `#${item.targetId}`}
                {isRecidivist && <span className="case-rec-badge">⚠️ Рецидивист</span>}
              </div>
              {playerHistoryLoading
                ? <div className="case-hist-loading">Загрузка...</div>
                : <MiniHistory items={playerHistory} currentId={item.id} emptyText="Нарушений не найдено" />
              }
            </div>

            {/* Счётчики */}
            {!playerHistoryLoading && playerHistory.length > 0 && (
              <div className="case-player-counts">
                {['ban','mute','kick','warn','unban','unmute','unwarn'].map(type => {
                  const m = actionMeta(type, 'chat')
                  const cnt = playerHistory.filter(h => h.actionType === type).length
                  return cnt > 0 ? (
                    <div key={type} className="case-pcount" style={{ borderColor: m.color + '40', background: m.bg }}>
                      <span className="case-pcount-val" style={{ color: m.color }}>{cnt}</span>
                      <span className="case-pcount-label">{m.root}</span>
                    </div>
                  ) : null
                })}
              </div>
            )}
          </div>
        )}

        {/* Тело — Модератор */}
        {tab === 'mod' && (
          <div className="case-body">
            <div className="case-block">
              <div className="case-block-title">Информация о модераторе</div>
              <div className="case-table">
                <div className="case-row">
                  <span className="case-key">Имя</span>
                  <span className="case-val">{item.adminName || '—'}</span>
                </div>
                <div className="case-row">
                  <span className="case-key">Telegram ID</span>
                  <span className="case-val" style={{ fontFamily: 'monospace' }}>{item.adminId}</span>
                </div>
                <div className="case-row">
                  <span className="case-key">Действий</span>
                  <span className="case-val">{modHistoryLoading ? '...' : modHistory.length} (из последних 20)</span>
                </div>
              </div>
            </div>

            <div className="case-block">
              <div className="case-block-title">Последние действия модератора</div>
              {modHistoryLoading
                ? <div className="case-hist-loading">Загрузка...</div>
                : <MiniHistory items={modHistory} currentId={item.id} emptyText="Нет недавних действий" />
              }
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------
function ActionCard({ item, onClick }) {
  const meta = actionMeta(item.actionType, item.scope)
  return (
    <div className="arc-card" style={{ '--cc': meta.color, '--cg': meta.glow, '--cb': meta.bg }}
      onClick={onClick} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}>
      <div className="arc-card-num">#{String(item.id).padStart(5, '0')}</div>
      <div className="arc-card-top">
        <span className="arc-card-badge" style={{ background: meta.color }}>{meta.icon} {meta.label}</span>
        <span className="arc-card-date">{fmtDateShort(item.createdAt)}</span>
      </div>
      {meta.scopeLabel && (
        <div className="arc-card-scope" style={{ color: meta.color, borderColor: meta.color + '40', background: meta.bg }}>
          {meta.scopeLabel}
        </div>
      )}
      <div className="arc-card-who">
        <div className="arc-card-person">
          <div className="arc-card-person-label">Выдал</div>
          <div className="arc-card-person-name">{item.adminName || `#${item.adminId}`}</div>
        </div>
        <div className="arc-card-arrow" style={{ color: meta.color }}>→</div>
        <div className="arc-card-person arc-card-person-right">
          <div className="arc-card-person-label">Игрок</div>
          <div className="arc-card-person-name">{item.targetName || `#${item.targetId}`}</div>
        </div>
      </div>
      {item.reason
        ? <div className="arc-card-reason"><span className="arc-card-reason-key">Причина:</span><span className="arc-card-reason-val">{item.reason}</span></div>
        : <div className="arc-card-reason arc-card-reason-empty">Причина не указана</div>
      }
      {item.hasProof && item.proofMediaId && (
        <div className="arc-card-proof">
          <TgPhoto fileId={item.proofMediaId} style={{ width:'100%', maxHeight:110, objectFit:'cover', borderRadius:8, cursor:'pointer' }} />
        </div>
      )}
      <div className="arc-card-tags">
        {item.durationMinutes && <span className="arc-card-tag arc-card-tag-dur">⏱ {fmtDuration(item.durationMinutes)}</span>}
        {item.hasProof && <span className="arc-card-tag arc-card-tag-proof">📷 Фото</span>}
        <span className="arc-card-tag arc-card-tag-open">Открыть →</span>
      </div>
      <div className="arc-card-stripe" style={{ background: meta.color }} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Moderator stats tab
// ---------------------------------------------------------------------------
function ModeratorStatsTab() {
  const [period, setPeriod] = useState('week')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchModeratorStats(period)
      .then((d) => setItems(d.items || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [period])

  return (
    <div className="mst-wrap">
      <div className="mst-period">
        {[['week','Неделя'],['month','Месяц'],['all','Всё время']].map(([v,l]) => (
          <button key={v} className={`mst-period-btn${period===v?' mst-period-on':''}`}
            onClick={() => setPeriod(v)}>{l}</button>
        ))}
      </div>

      {loading && <div className="arc-loading"><div className="arc-spinner" /> Загрузка...</div>}

      {!loading && items.length === 0 && (
        <div className="arc-empty"><div className="arc-empty-icon">📭</div><div className="arc-empty-text">Нет данных за период</div></div>
      )}

      {!loading && items.length > 0 && (
        <div className="mst-grid">
          {items.map((mod, i) => (
            <div key={mod.adminId} className="mst-card">
              <div className="mst-card-top">
                <div className="mst-rank" style={{ color: i === 0 ? '#d4a84b' : i === 1 ? '#94a3b8' : i === 2 ? '#cd7f32' : '#374151' }}>
                  #{i + 1}
                </div>
                <div className="mst-name-block">
                  <div className="mst-name">{mod.adminName}</div>
                  <div className="mst-last">Последнее: {timeSince(mod.lastActionAt)}</div>
                </div>
                <div className="mst-total-badge">{mod.total} дел</div>
              </div>
              <div className="mst-bars">
                {[
                  { label:'Баны',   val: mod.bans,   color:'#ef4444' },
                  { label:'Муты',   val: mod.mutes,  color:'#f97316' },
                  { label:'Кики',   val: mod.kicks,  color:'#a855f7' },
                  { label:'Варны',  val: mod.warns,  color:'#eab308' },
                  { label:'Снятия', val: (mod.unbans||0)+(mod.unmutes||0)+(mod.unwarns||0), color:'#22c55e' },
                ].map(({ label, val, color }) => {
                  const pct = mod.total > 0 ? Math.round((val / mod.total) * 100) : 0
                  return val > 0 ? (
                    <div key={label} className="mst-bar-row">
                      <span className="mst-bar-label">{label}</span>
                      <div className="mst-bar-track">
                        <div className="mst-bar-fill" style={{ width: `${pct}%`, background: color }} />
                      </div>
                      <span className="mst-bar-val" style={{ color }}>{val}</span>
                    </div>
                  ) : null
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Stats bar
// ---------------------------------------------------------------------------
function StatsBar({ items, total }) {
  const c = { ban:0, mute:0, kick:0, warn:0, removals:0 }
  items.forEach((i) => {
    if (['unban','unmute','unwarn'].includes(i.actionType)) c.removals++
    else if (c[i.actionType] !== undefined) c[i.actionType]++
  })
  return (
    <div className="arc-stats">
      {[['ban','#ef4444','баны'],['mute','#f97316','муты'],['kick','#a855f7','кики'],['warn','#eab308','предупр.'],['removals','#22c55e','снятия']].map(([k,color,label]) => (
        <div key={k} className="arc-stat">
          <span className="arc-stat-val" style={{ color }}>{c[k]}</span>
          <span className="arc-stat-label">{label}</span>
        </div>
      ))}
      <div className="arc-stat-div" />
      <div className="arc-stat">
        <span className="arc-stat-val" style={{ color:'#d4a84b' }}>{total}</span>
        <span className="arc-stat-label">всего дел</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main section
// ---------------------------------------------------------------------------
const PAGE_SIZE = 24
const MAIN_TABS = [
  { id: 'archive',  label: '📁 Архив' },
  { id: 'appeals',  label: '📬 Апелляции' },
  { id: 'stats',    label: '📊 Статистика' },
]

// ---------------------------------------------------------------------------
// Appeals tab
// ---------------------------------------------------------------------------
const APPEAL_STATUS = {
  pending:  { label: 'Ожидает',   color: '#eab308', bg: '#eab30812' },
  taken:    { label: 'Взято',     color: '#60a5fa', bg: '#60a5fa12' },
  approved: { label: 'Одобрено', color: '#22c55e', bg: '#22c55e12' },
  rejected: { label: 'Отклонено',color: '#ef4444', bg: '#ef444412' },
}

function AppealCard({ item, onUpdate }) {
  const s = APPEAL_STATUS[item.status] || APPEAL_STATUS.pending
  const [taking, setTaking] = useState(false)
  const [resolving, setResolving] = useState(null)
  const [resolution, setResolution] = useState('')
  const [showResolve, setShowResolve] = useState(false)
  const [messages, setMessages] = useState([])
  const [msgsLoaded, setMsgsLoaded] = useState(false)
  const [msgText, setMsgText] = useState('')
  const [photoFile, setPhotoFile] = useState(null)
  const [photoPreview, setPhotoPreview] = useState(null)
  const [sending, setSending] = useState(false)
  const [open, setOpen] = useState(false)
  const fileRef = useRef()

  async function loadMessages() {
    try {
      const data = await fetchAppealMessages(item.id)
      setMessages(data.items || [])
      setMsgsLoaded(true)
    } catch { }
  }

  function toggle() {
    if (!open && !msgsLoaded) loadMessages()
    setOpen(v => !v)
  }

  async function handleTake() {
    setTaking(true)
    try { await takeAppeal(item.id); onUpdate() }
    catch (e) { alert(e.message || 'Ошибка') }
    finally { setTaking(false) }
  }

  async function handleResolve(approve) {
    setResolving(approve ? 'approve' : 'reject')
    try { await resolveAppeal(item.id, { approve, resolution }); onUpdate() }
    catch (e) { alert(e.message || 'Ошибка') }
    finally { setResolving(null) }
  }

  function pickPhoto(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setPhotoFile(file)
    setPhotoPreview(URL.createObjectURL(file))
    e.target.value = ''
  }

  function removePhoto() {
    setPhotoFile(null)
    if (photoPreview) URL.revokeObjectURL(photoPreview)
    setPhotoPreview(null)
  }

  async function handleSend() {
    if (!msgText.trim() && !photoFile) return
    setSending(true)
    try {
      if (photoFile) {
        await uploadAppealPhoto(item.id, photoFile, msgText.trim())
      } else {
        await sendAppealMessage(item.id, { text: msgText.trim() })
      }
      setMsgText('')
      removePhoto()
      await loadMessages()
    } catch (e) { alert(e.message || 'Ошибка') }
    finally { setSending(false) }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isClosed = item.status === 'approved' || item.status === 'rejected'

  return (
    <div className="apl-card" style={{ '--apl-color': s.color, '--apl-bg': s.bg }}>
      {/* Header */}
      <div className="apl-card-top" onClick={toggle} style={{ cursor: 'pointer' }}>
        <span className="apl-badge" style={{ background: s.bg, color: s.color, border: `1px solid ${s.color}40` }}>
          {s.label}
        </span>
        <div className="apl-player-inline">
          <span className="apl-player-name">{item.firstName || item.username || `#${item.userId}`}</span>
          {item.username && <span className="apl-username">@{item.username}</span>}
          <span className="apl-uid">ID: {item.userId}</span>
        </div>
        <span className="apl-date">{fmtDateShort(item.createdAt)}</span>
        <span className="apl-chevron">{open ? '▲' : '▼'}</span>
      </div>

      {open && (
        <>
          {item.banReason && (
            <div className="apl-ban-reason">
              <span className="apl-label">Причина бана:</span> {item.banReason}
            </div>
          )}

          {/* Переписка */}
          <div className="apl-thread">
            {/* Первое сообщение — текст апелляции */}
            <div className="apl-msg apl-msg-user">
              <div className="apl-msg-meta">👤 Игрок · {fmtDateShort(item.createdAt)}</div>
              <div className="apl-msg-body">{item.appealText}</div>
            </div>

            {messages.map(msg => (
              <div key={msg.id} className={`apl-msg ${msg.fromUser ? 'apl-msg-user' : 'apl-msg-admin'}`}>
                <div className="apl-msg-meta">
                  {msg.fromUser ? '👤 Игрок' : `🛡 ${msg.adminName || 'Администратор'}`}
                  {' · '}{fmtDateShort(msg.createdAt)}
                </div>
                {msg.text && <div className="apl-msg-body">{msg.text}</div>}
                {msg.photoFileId && (
                  <TgPhoto fileId={msg.photoFileId} onClick style={{ marginBottom: msg.text ? 6 : 0, borderRadius: 8 }} />
                )}
              </div>
            ))}
          </div>

          {/* Поле ответа — мессенджер стиль */}
          {!isClosed && (
            <div className="apl-composer">
              {photoPreview && (
                <div className="apl-photo-preview">
                  <img src={photoPreview} alt="preview" className="apl-preview-img" />
                  <button className="apl-preview-remove" onClick={removePhoto}>✕</button>
                </div>
              )}
              <div className="apl-composer-row">
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  onChange={pickPhoto}
                />
                <button className="apl-attach-btn" onClick={() => fileRef.current?.click()} title="Прикрепить фото">
                  📎
                </button>
                <textarea
                  className="apl-composer-input"
                  placeholder="Сообщение..."
                  rows={1}
                  value={msgText}
                  onChange={e => setMsgText(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
                <button
                  className="apl-send-btn"
                  onClick={handleSend}
                  disabled={sending || (!msgText.trim() && !photoFile)}
                  title="Отправить (Enter)"
                >
                  {sending ? '⏳' : '➤'}
                </button>
              </div>
            </div>
          )}

          {item.resolution && (
            <div className="apl-resolution">
              <span className="apl-label">Решение:</span> {item.resolution}
            </div>
          )}

          {/* Actions */}
          <div className="apl-actions">
            {item.status === 'pending' && (
              <button className="apl-btn apl-btn-take" onClick={handleTake} disabled={taking}>
                {taking ? '...' : '👀 Взять в работу'}
              </button>
            )}
            {item.status === 'taken' && !showResolve && (
              <>
                <button className="apl-btn apl-btn-approve" onClick={() => setShowResolve(true)}>✅ Одобрить</button>
                <button className="apl-btn apl-btn-reject" onClick={() => setShowResolve(true)}>❌ Отклонить</button>
              </>
            )}
            {item.status === 'taken' && showResolve && (
              <div className="apl-resolve-form">
                <input className="apl-resolution-input" placeholder="Причина решения..." value={resolution} onChange={e => setResolution(e.target.value)} />
                <div className="apl-resolve-btns">
                  <button className="apl-btn apl-btn-approve" onClick={() => handleResolve(true)} disabled={resolving === 'approve'}>
                    {resolving === 'approve' ? '...' : '✅ Одобрить и разбанить'}
                  </button>
                  <button className="apl-btn apl-btn-reject" onClick={() => handleResolve(false)} disabled={resolving === 'reject'}>
                    {resolving === 'reject' ? '...' : '❌ Отклонить'}
                  </button>
                  <button className="apl-btn apl-btn-cancel" onClick={() => setShowResolve(false)}>Отмена</button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function AppealsTab({ role }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState('')

  const canManage = role === 'owner' || role === 'senior_admin'

  const load = useCallback(async (status = filterStatus) => {
    setLoading(true)
    try {
      const data = await fetchAppeals({ status, limit: 50 })
      setItems(data.items || [])
      setTotal(data.total || 0)
    } catch { }
    finally { setLoading(false) }
  }, [filterStatus])

  useEffect(() => { load() }, [load])

  if (!canManage) {
    return (
      <div className="apl-no-access">
        🔒 Апелляции доступны только владельцам и старшим администраторам
      </div>
    )
  }

  const pendingCount = items.filter(i => i.status === 'pending').length

  return (
    <div className="apl-wrap">
      <div className="apl-filters">
        {[['', 'Все'], ['pending', 'Ожидают'], ['taken', 'В работе'], ['approved', 'Одобрены'], ['rejected', 'Отклонены']].map(([v, l]) => (
          <button key={v}
            className={`arc-tab${filterStatus === v ? ' arc-tab-on' : ''}`}
            onClick={() => { setFilterStatus(v); load(v) }}>
            {l}{v === 'pending' && pendingCount > 0 ? ` (${pendingCount})` : ''}
          </button>
        ))}
      </div>

      {loading && <div className="arc-loading"><div className="arc-spinner" /> Загрузка...</div>}

      {!loading && items.length === 0 && (
        <div className="arc-empty">
          <div className="arc-empty-icon">📭</div>
          <div className="arc-empty-text">Апелляций не найдено</div>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="apl-grid">
          {items.map(item => (
            <AppealCard key={item.id} item={item} onUpdate={() => load()} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function ModerationSection({ role }) {
  const [mainTab, setMainTab] = useState('archive')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filterType, setFilterType] = useState('')
  const [filterPlayer, setFilterPlayer] = useState('')
  const [sortBy, setSortBy] = useState('date')
  const [playerInput, setPlayerInput] = useState('')
  const [offset, setOffset] = useState(0)
  const [liveCount, setLiveCount] = useState(0)
  const [openCase, setOpenCase] = useState(null)
  const wsRef = useRef(null)

  const load = useCallback(async (opts = {}) => {
    setLoading(true); setError('')
    try {
      const data = await fetchModerationLogs({
        actionType: opts.actionType ?? filterType,
        playerId: opts.playerId ?? filterPlayer,
        sortBy: opts.sortBy ?? sortBy,
        limit: PAGE_SIZE,
        offset: opts.offset ?? offset,
      })
      setItems(data.items || []); setTotal(data.total || 0)
    } catch (e) { setError(e.message || 'Ошибка загрузки') }
    finally { setLoading(false) }
  }, [filterType, filterPlayer, offset])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const token = getAdminToken()
    if (!token) return
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${proto}://${window.location.host}${API_PREFIX}/ws/moderation?token=${token}`
    let ws, dead = false
    function connect() {
      if (dead) return
      ws = new WebSocket(wsUrl)
      ws.onmessage = (e) => {
        try { const msg = JSON.parse(e.data); if (msg.event === 'new_moderation_log') setLiveCount(n => n+1) } catch {}
      }
      ws.onclose = () => { if (!dead) setTimeout(connect, 4000) }
      wsRef.current = ws
    }
    connect()
    return () => { dead = true; ws?.close() }
  }, [])

  function applySort(s) { setSortBy(s); setOffset(0); load({ sortBy: s, offset: 0 }) }
  function applyFilter(type) { setFilterType(type); setOffset(0); load({ actionType:type, offset:0 }) }
  function applyPlayerFilter() {
    const id = parseInt(playerInput.trim(), 10)
    const pid = isNaN(id) ? '' : String(id)
    setFilterPlayer(pid); setOffset(0); load({ playerId:pid, offset:0 })
  }
  function clearPlayer() { setPlayerInput(''); setFilterPlayer(''); setOffset(0); load({ playerId:'', offset:0 }) }
  function goPage(dir) { const next = Math.max(0, offset + dir * PAGE_SIZE); setOffset(next); load({ offset:next }) }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div className="arc-shell">
      {openCase && (
        <CaseModal item={openCase} role={role}
          onClose={() => setOpenCase(null)}
          onUnbanned={() => { setOpenCase(null); load() }} />
      )}

      {/* Шапка */}
      <div className="arc-header">
        <div className="arc-header-row">
          <div className="arc-title-block">
            <div className="arc-title">⚖ Архив модерации</div>
            <div className="arc-subtitle">Муты · кики · баны · варны и снятия — с охватом и пруфами · {total.toLocaleString('ru-RU')} записей</div>
          </div>
          {liveCount > 0 && (
            <button className="arc-live" onClick={() => { setLiveCount(0); load() }}>
              +{liveCount} новых — обновить
            </button>
          )}
        </div>

        {!loading && items.length > 0 && mainTab === 'archive' && <StatsBar items={items} total={total} />}

        {/* Главные табы */}
        <div className="arc-main-tabs">
          {MAIN_TABS.map(t => (
            <button key={t.id} className={`arc-main-tab${mainTab===t.id?' arc-main-tab-on':''}`}
              onClick={() => setMainTab(t.id)}>{t.label}</button>
          ))}
        </div>

        {/* Фильтры — только в архиве */}
        {mainTab === 'archive' && (
          <div className="arc-filters">
            <div className="arc-tabs">
              {FILTER_TYPES.map(f => (
                <button key={f.value}
                  className={`arc-tab${filterType===f.value?' arc-tab-on':''}`}
                  onClick={() => applyFilter(f.value)}>{f.label}</button>
              ))}
            </div>
            <div className="arc-sort">
              <span className="arc-sort-label">Сортировка:</span>
              <button className={`arc-sort-btn${sortBy==='date'?' arc-sort-on':''}`} onClick={() => applySort('date')}>По дате</button>
              <button className={`arc-sort-btn${sortBy==='type'?' arc-sort-on':''}`} onClick={() => applySort('type')}>По типу</button>
            </div>
            <div className="arc-search">
              <input className="arc-input" placeholder="Telegram ID игрока..."
                value={playerInput} onChange={e => setPlayerInput(e.target.value)}
                onKeyDown={e => e.key==='Enter' && applyPlayerFilter()} />
              <button className="arc-search-btn" onClick={applyPlayerFilter}>Найти</button>
              {filterPlayer && <button className="arc-clear-btn" onClick={clearPlayer}>✕</button>}
            </div>
          </div>
        )}
      </div>

      {/* Апелляции */}
      {mainTab === 'appeals' && <AppealsTab role={role} />}

      {/* Статистика модераторов */}
      {mainTab === 'stats' && <ModeratorStatsTab />}

      {/* Архив */}
      {mainTab === 'archive' && (
        <>
          {loading && <div className="arc-loading"><div className="arc-spinner" /> Загружаем архив...</div>}
          {error && <div className="arc-error">{error}</div>}
          {!loading && !error && items.length === 0 && (
            <div className="arc-empty"><div className="arc-empty-icon">📭</div><div className="arc-empty-text">Записей не найдено</div></div>
          )}
          {!loading && items.length > 0 && (
            <div className="arc-grid">
              {items.map(item => <ActionCard key={item.id} item={item} onClick={() => setOpenCase(item)} />)}
            </div>
          )}
          {totalPages > 1 && (
            <div className="arc-pages">
              <button className="arc-page-btn" onClick={() => goPage(-1)} disabled={offset===0}>← Назад</button>
              <span className="arc-page-info">{currentPage} / {totalPages}</span>
              <button className="arc-page-btn" onClick={() => goPage(1)} disabled={offset+PAGE_SIZE>=total}>Вперёд →</button>
            </div>
          )}
        </>
      )}

      <style>{`
        .arc-shell { padding: 24px 28px; max-width: 1400px; }
        .arc-header { margin-bottom: 24px; }
        .arc-header-row { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:16px; flex-wrap:wrap; }
        .arc-title { font-size:24px; font-weight:800; color:#f5e6c8; letter-spacing:0.02em; margin-bottom:4px; }
        .arc-subtitle { font-size:12px; color:#4b5563; }
        .arc-live { background:#d4a84b18; border:1px solid #d4a84b60; color:#d4a84b; padding:7px 16px; border-radius:20px; font-size:12px; font-weight:700; cursor:pointer; animation:arc-pulse 2s infinite; white-space:nowrap; }
        @keyframes arc-pulse { 0%,100%{box-shadow:0 0 0 0 #d4a84b40}50%{box-shadow:0 0 0 6px transparent} }

        /* Stats */
        .arc-stats { display:flex; align-items:center; background:#0e0e18; border:1px solid #1e1e2e; border-radius:12px; padding:14px 20px; margin-bottom:16px; flex-wrap:wrap; gap:4px; }
        .arc-stat { display:flex; flex-direction:column; align-items:center; gap:2px; padding:0 16px; }
        .arc-stat-val { font-size:22px; font-weight:800; line-height:1; }
        .arc-stat-label { font-size:10px; color:#4b5563; text-transform:uppercase; letter-spacing:0.06em; }
        .arc-stat-div { width:1px; height:32px; background:#1e1e2e; }

        /* Main tabs */
        .arc-main-tabs { display:flex; gap:4px; margin-bottom:16px; border-bottom:1px solid #1e1e2e; padding-bottom:0; }
        .arc-main-tab { padding:8px 20px; font-size:13px; font-weight:600; color:#4b5563; background:transparent; border:none; border-bottom:2px solid transparent; cursor:pointer; transition:all 0.2s; margin-bottom:-1px; }
        .arc-main-tab:hover { color:#d4a84b; }
        .arc-main-tab-on { color:#d4a84b; border-bottom-color:#d4a84b; }

        /* Filters */
        .arc-filters { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
        .arc-tabs { display:flex; gap:6px; flex-wrap:wrap; }
        .arc-tab { padding:6px 16px; border-radius:20px; border:1px solid #1e1e2e; background:transparent; color:#6b7280; font-size:12px; font-weight:500; cursor:pointer; transition:all 0.2s; }
        .arc-tab:hover { border-color:#d4a84b60; color:#d4a84b; }
        .arc-tab-on { background:#d4a84b18; border-color:#d4a84b; color:#d4a84b; font-weight:700; }
        .arc-search { display:flex; gap:6px; align-items:center; margin-left:auto; }
        .arc-input { background:#0e0e18; border:1px solid #1e1e2e; border-radius:8px; color:#e2e8f0; padding:7px 12px; font-size:13px; width:190px; outline:none; transition:border-color 0.2s; }
        .arc-input:focus { border-color:#d4a84b80; }
        .arc-input::placeholder { color:#2d3748; }
        .arc-search-btn { background:#d4a84b18; border:1px solid #d4a84b60; color:#d4a84b; padding:7px 14px; border-radius:8px; font-size:12px; font-weight:600; cursor:pointer; }
        .arc-search-btn:hover { background:#d4a84b30; }
        .arc-clear-btn { background:transparent; border:1px solid #374151; color:#6b7280; padding:7px 10px; border-radius:8px; font-size:12px; cursor:pointer; }
        .arc-sort { display:flex; align-items:center; gap:6px; }
        .arc-sort-label { font-size:11px; color:#4b5563; }
        .arc-sort-btn { padding:5px 12px; border-radius:8px; border:1px solid #1e1e2e; background:transparent; color:#6b7280; font-size:12px; cursor:pointer; transition:all 0.2s; }
        .arc-sort-btn:hover { border-color:#d4a84b60; color:#d4a84b; }
        .arc-sort-on { background:#d4a84b18; border-color:#d4a84b; color:#d4a84b; font-weight:700; }

        /* States */
        .arc-loading { display:flex; align-items:center; gap:12px; color:#6b7280; padding:60px 0; font-size:14px; }
        .arc-spinner { width:18px; height:18px; border:2px solid #1e1e2e; border-top-color:#d4a84b; border-radius:50%; animation:spin 0.8s linear infinite; }
        @keyframes spin { to{transform:rotate(360deg)} }
        .arc-error { background:#ef444418; border:1px solid #ef444440; color:#ef4444; padding:16px 20px; border-radius:10px; font-size:14px; }
        .arc-empty { display:flex; flex-direction:column; align-items:flex-start; padding:60px 0; gap:10px; }
        .arc-empty-icon { font-size:40px; opacity:0.3; }
        .arc-empty-text { color:#374151; font-size:14px; }

        /* Grid */
        .arc-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:14px; align-content:start; margin-bottom:28px; }

        /* Card */
        .arc-card { position:relative; background:#0b0b14; border:1px solid #1a1a28; border-radius:12px; padding:16px 16px 14px; display:flex; flex-direction:column; gap:11px; cursor:pointer; transition:border-color 0.2s, box-shadow 0.2s, transform 0.18s; overflow:hidden; min-height:170px; }
        .arc-card:hover { border-color:var(--cc); box-shadow:0 0 20px var(--cg),0 4px 24px #00000060; transform:translateY(-3px); }
        .arc-card-stripe { position:absolute; bottom:0; left:0; right:0; height:3px; opacity:0.7; border-radius:0 0 12px 12px; transition:opacity 0.2s; }
        .arc-card:hover .arc-card-stripe { opacity:1; }
        .arc-card-num { position:absolute; top:10px; right:12px; font-size:10px; color:#2d3748; font-family:monospace; letter-spacing:0.06em; }
        .arc-card-top { display:flex; align-items:center; gap:10px; padding-right:52px; }
        .arc-card-badge { padding:3px 10px; border-radius:20px; font-size:11px; font-weight:800; letter-spacing:0.05em; color:#fff; flex-shrink:0; }
        .arc-card-date { font-size:11px; color:#6b7280; font-family:monospace; }
        .arc-card-scope { align-self:flex-start; font-size:10px; font-weight:700; padding:2px 9px; border-radius:12px; border:1px solid; text-transform:lowercase; letter-spacing:0.02em; }
        .arc-card-proof { border-radius:8px; overflow:hidden; border:1px solid #1a1a28; background:#12121e; }
        .arc-card-who { display:flex; align-items:center; gap:8px; background:#12121e; border-radius:8px; padding:9px 12px; }
        .arc-card-person { flex:1; min-width:0; }
        .arc-card-person-right { text-align:right; }
        .arc-card-person-label { font-size:9px; color:#374151; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:2px; }
        .arc-card-person-name { font-size:13px; font-weight:700; color:#e2e8f0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .arc-card-arrow { font-size:14px; flex-shrink:0; }
        .arc-card-reason { font-size:12px; color:#6b7280; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; line-height:1.5; }
        .arc-card-reason-key { color:#4b5563; font-weight:600; margin-right:4px; }
        .arc-card-reason-val { color:#9ca3af; }
        .arc-card-reason-empty { color:#2d3748; font-style:italic; }
        .arc-card-tags { display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-top:auto; }
        .arc-card-tag { font-size:10px; padding:2px 8px; border-radius:10px; border:1px solid; font-weight:600; }
        .arc-card-tag-dur { border-color:#f9731630; color:#f97316; background:#f9731610; }
        .arc-card-tag-proof { border-color:#60a5fa30; color:#60a5fa; background:#60a5fa10; }
        .arc-card-tag-open { margin-left:auto; border-color:transparent; color:#2d3748; background:transparent; transition:color 0.2s; }
        .arc-card:hover .arc-card-tag-open { color:var(--cc); }

        /* Pagination */
        .arc-pages { display:flex; align-items:center; gap:16px; padding:20px 0; }
        .arc-page-btn { background:#0e0e18; border:1px solid #1e1e2e; color:#6b7280; padding:8px 20px; border-radius:8px; font-size:13px; cursor:pointer; transition:all 0.2s; }
        .arc-page-btn:hover:not(:disabled) { border-color:#d4a84b60; color:#d4a84b; }
        .arc-page-btn:disabled { opacity:0.3; cursor:not-allowed; }
        .arc-page-info { color:#4b5563; font-size:13px; }

        /* Moderator stats */
        .mst-wrap { padding-top:8px; }
        .mst-period { display:flex; gap:6px; margin-bottom:20px; }
        .mst-period-btn { padding:6px 18px; border-radius:20px; border:1px solid #1e1e2e; background:transparent; color:#6b7280; font-size:12px; font-weight:500; cursor:pointer; transition:all 0.2s; }
        .mst-period-btn:hover { border-color:#d4a84b60; color:#d4a84b; }
        .mst-period-on { background:#d4a84b18; border-color:#d4a84b; color:#d4a84b; font-weight:700; }
        .mst-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px; align-content:start; }
        .mst-card { background:#0b0b14; border:1px solid #1a1a28; border-radius:12px; padding:18px; display:flex; flex-direction:column; gap:14px; transition:border-color 0.2s; }
        .mst-card:hover { border-color:#d4a84b40; }
        .mst-card-top { display:flex; align-items:center; gap:12px; }
        .mst-rank { font-size:20px; font-weight:900; width:28px; flex-shrink:0; }
        .mst-name-block { flex:1; min-width:0; }
        .mst-name { font-size:15px; font-weight:700; color:#f5e6c8; }
        .mst-last { font-size:11px; color:#4b5563; margin-top:2px; }
        .mst-total-badge { background:#d4a84b18; border:1px solid #d4a84b40; color:#d4a84b; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:700; flex-shrink:0; }
        .mst-bars { display:flex; flex-direction:column; gap:8px; }
        .mst-bar-row { display:flex; align-items:center; gap:8px; }
        .mst-bar-label { font-size:11px; color:#4b5563; width:60px; flex-shrink:0; }
        .mst-bar-track { flex:1; height:6px; background:#1a1a28; border-radius:3px; overflow:hidden; }
        .mst-bar-fill { height:100%; border-radius:3px; transition:width 0.4s ease; }
        .mst-bar-val { font-size:12px; font-weight:700; width:24px; text-align:right; flex-shrink:0; }

        /* ===== CASE MODAL ===== */
        .case-backdrop { position:fixed; inset:0; background:rgba(0,0,0,0.85); backdrop-filter:blur(8px); z-index:9999; display:flex; align-items:center; justify-content:center; padding:20px; animation:fade-in 0.18s ease; }
        @keyframes fade-in { from{opacity:0}to{opacity:1} }
        .case-modal { background:#080810; border:1px solid #1e1e2e; border-radius:18px; max-width:680px; width:100%; max-height:88vh; overflow-y:auto; box-shadow:0 40px 120px rgba(0,0,0,0.9); animation:slide-up 0.22s ease; }
        @keyframes slide-up { from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)} }

        .case-cover { position:relative; padding:26px 24px 22px; background:var(--cb); border-bottom:1px solid #1e1e2e; border-radius:18px 18px 0 0; overflow:hidden; }
        .case-cover-glow { position:absolute; inset:0; background:radial-gradient(ellipse at 0% 0%, var(--cg) 0%, transparent 65%); pointer-events:none; }
        .case-cover-inner { position:relative; display:flex; align-items:flex-start; justify-content:space-between; gap:16px; padding-right:40px; }
        .case-cover-left { display:flex; flex-direction:column; gap:6px; }
        .case-stamp { display:inline-flex; align-items:center; gap:8px; border:2px solid; border-radius:8px; padding:6px 16px; font-size:17px; font-weight:900; letter-spacing:0.1em; width:fit-content; }
        .case-num { font-size:11px; color:#4b5563; font-family:monospace; letter-spacing:0.1em; }
        .case-desc { font-size:13px; color:#9ca3af; }
        .case-recidivist { font-size:12px; color:#f97316; font-weight:700; background:#f9731615; border:1px solid #f9731630; padding:3px 10px; border-radius:8px; width:fit-content; }
        .case-cover-right { display:flex; flex-direction:column; gap:3px; flex-shrink:0; padding-top:2px; }
        .case-date-label { font-size:9px; color:#4b5563; text-transform:uppercase; letter-spacing:0.1em; }
        .case-date-val { font-size:12px; color:#9ca3af; font-family:monospace; white-space:nowrap; }
        .case-close-btn { position:absolute; top:14px; right:16px; background:rgba(0,0,0,0.3); border:1px solid #1e1e2e; color:#6b7280; width:30px; height:30px; border-radius:8px; cursor:pointer; font-size:13px; display:flex; align-items:center; justify-content:center; transition:all 0.2s; z-index:1; }
        .case-close-btn:hover { background:#1e1e2e; color:#e2e8f0; }

        .case-tabs { display:flex; border-bottom:1px solid #1e1e2e; }
        .case-tab { padding:10px 18px; font-size:13px; font-weight:500; color:#4b5563; background:transparent; border:none; border-bottom:2px solid transparent; cursor:pointer; transition:all 0.2s; display:flex; align-items:center; gap:6px; margin-bottom:-1px; }
        .case-tab:hover { color:#d4a84b; }
        .case-tab-on { color:#d4a84b; border-bottom-color:#d4a84b; font-weight:700; }
        .case-tab-badge { background:#ef4444; color:#fff; font-size:10px; font-weight:800; padding:1px 6px; border-radius:10px; }

        .case-body { padding:22px 24px; display:flex; flex-direction:column; gap:20px; }
        .case-block { display:flex; flex-direction:column; gap:10px; }
        .case-block-title { font-size:10px; text-transform:uppercase; letter-spacing:0.1em; color:#374151; font-weight:700; border-bottom:1px solid #1a1a28; padding-bottom:7px; display:flex; align-items:center; gap:8px; }
        .case-rec-badge { font-size:10px; color:#f97316; background:#f9731615; border:1px solid #f9731630; padding:2px 8px; border-radius:8px; font-weight:700; }

        .case-participants { display:flex; align-items:stretch; background:#0e0e18; border:1px solid #1e1e2e; border-radius:10px; overflow:hidden; }
        .case-side { flex:1; padding:16px 18px; display:flex; flex-direction:column; gap:4px; }
        .case-side-left { border-right:1px solid #1e1e2e; }
        .case-side-role { font-size:9px; text-transform:uppercase; letter-spacing:0.08em; color:#374151; font-weight:700; }
        .case-side-name { font-size:16px; font-weight:800; color:#f5e6c8; }
        .case-side-id { font-size:11px; color:#2d3748; font-family:monospace; }
        .case-divider { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; padding:0 14px; }
        .case-div-line { width:1px; flex:1; }
        .case-div-icon { font-size:18px; }

        .case-table { background:#0e0e18; border:1px solid #1e1e2e; border-radius:10px; overflow:hidden; }
        .case-row { display:flex; align-items:flex-start; gap:16px; padding:11px 18px; border-bottom:1px solid #1a1a28; }
        .case-row:last-child { border-bottom:none; }
        .case-key { font-size:12px; color:#374151; font-weight:600; width:100px; flex-shrink:0; padding-top:1px; }
        .case-val { font-size:13px; color:#d1d5db; line-height:1.5; }

        .case-proof-box { background:#0e0e18; border:1px solid #1e1e2e; border-radius:10px; padding:16px; min-height:80px; display:flex; align-items:center; justify-content:center; }
        .case-no-proof { font-size:13px; color:#2d3748; }
        .case-proof-loading { font-size:13px; color:#4b5563; }
        .case-proof-err { font-size:13px; color:#ef4444; }
        .case-proof-img { max-width:100%; max-height:380px; border-radius:8px; object-fit:contain; cursor:zoom-in; transition:opacity 0.15s; }
        .case-proof-img:hover { opacity:0.9; }

        .case-actions { display:flex; justify-content:center; padding:4px 0; }
        .case-unban-btn { background:#22c55e18; border:1px solid #22c55e50; color:#22c55e; padding:12px 36px; border-radius:10px; font-size:14px; font-weight:700; cursor:pointer; transition:all 0.2s; }
        .case-unban-btn:hover:not(:disabled) { background:#22c55e28; box-shadow:0 0 20px #22c55e25; }
        .case-unban-btn:disabled { opacity:0.5; cursor:not-allowed; }
        .case-unban-done { color:#22c55e; font-size:14px; font-weight:700; }
        .case-delete-zone { border-top:1px solid #1a1a28; padding-top:16px; display:flex; justify-content:center; }
        .case-delete-btn { background:transparent; border:1px solid #374151; color:#4b5563; padding:8px 20px; border-radius:8px; font-size:12px; cursor:pointer; transition:all 0.2s; }
        .case-delete-btn:hover { border-color:#ef444460; color:#ef4444; background:#ef444410; }

        /* Mini history */
        .mini-list { display:flex; flex-direction:column; gap:6px; }
        .mini-row { display:flex; align-items:center; gap:10px; background:#0e0e18; border:1px solid #1a1a28; border-radius:8px; padding:10px 12px; transition:border-color 0.2s; }
        .mini-row-current { border-color:#d4a84b40; background:#d4a84b08; }
        .mini-badge { padding:2px 8px; border-radius:12px; font-size:10px; font-weight:800; color:#fff; flex-shrink:0; }
        .mini-info { flex:1; min-width:0; display:flex; flex-direction:column; gap:2px; }
        .mini-reason { font-size:12px; color:#9ca3af; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .mini-date { font-size:10px; color:#374151; font-family:monospace; }
        .mini-current-tag { font-size:10px; color:#d4a84b; background:#d4a84b15; border:1px solid #d4a84b30; padding:2px 8px; border-radius:8px; flex-shrink:0; }
        .mini-empty { font-size:13px; color:#2d3748; padding:8px 0; }
        .case-hist-loading { font-size:13px; color:#4b5563; }

        /* Player counts */
        .case-player-counts { display:flex; gap:10px; flex-wrap:wrap; }
        .case-pcount { padding:12px 18px; border-radius:10px; border:1px solid; display:flex; flex-direction:column; align-items:center; gap:2px; min-width:80px; }
        .case-pcount-val { font-size:22px; font-weight:800; }
        .case-pcount-label { font-size:10px; color:#6b7280; text-transform:uppercase; letter-spacing:0.06em; }

        /* Appeals */
        .apl-no-access { color:#4b5563; font-size:14px; padding:40px 0; }
        .apl-wrap { padding-top:8px; }
        .apl-filters { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:20px; }
        .apl-grid { display:flex; flex-direction:column; gap:14px; }
        .apl-card { background:#0b0b14; border:1px solid #1a1a28; border-radius:12px; padding:18px; display:flex; flex-direction:column; gap:12px; transition:border-color 0.2s; }
        .apl-card:hover { border-color:var(--apl-color,#d4a84b); }
        .apl-card-top { display:flex; align-items:center; justify-content:space-between; }
        .apl-badge { padding:3px 10px; border-radius:20px; font-size:11px; font-weight:700; }
        .apl-date { font-size:11px; color:#4b5563; font-family:monospace; }
        .apl-player { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
        .apl-player-name { font-size:15px; font-weight:800; color:#f5e6c8; }
        .apl-username { font-size:12px; color:#6b7280; }
        .apl-uid { font-size:11px; color:#374151; font-family:monospace; margin-left:auto; }
        .apl-ban-reason { font-size:12px; color:#ef4444; background:#ef444410; border:1px solid #ef444430; border-radius:8px; padding:8px 12px; }
        .apl-label { font-size:11px; color:#4b5563; font-weight:600; margin-right:4px; }
        .apl-text { font-size:13px; color:#9ca3af; display:flex; flex-direction:column; gap:4px; }
        .apl-text-body { margin:0; line-height:1.6; color:#d1d5db; background:#12121e; border-radius:8px; padding:10px 12px; }
        .apl-resolution { font-size:12px; color:#6b7280; }
        .apl-actions { display:flex; gap:8px; flex-wrap:wrap; }
        .apl-btn { padding:7px 16px; border-radius:8px; font-size:12px; font-weight:700; cursor:pointer; border:1px solid; transition:all 0.2s; }
        .apl-btn:disabled { opacity:0.5; cursor:not-allowed; }
        .apl-btn-take { background:#60a5fa12; border-color:#60a5fa40; color:#60a5fa; }
        .apl-btn-take:hover:not(:disabled) { background:#60a5fa20; }
        .apl-btn-approve { background:#22c55e12; border-color:#22c55e40; color:#22c55e; }
        .apl-btn-approve:hover:not(:disabled) { background:#22c55e20; }
        .apl-btn-reject { background:#ef444412; border-color:#ef444440; color:#ef4444; }
        .apl-btn-reject:hover:not(:disabled) { background:#ef444420; }
        .apl-btn-cancel { background:transparent; border-color:#374151; color:#6b7280; }
        .apl-resolve-form { width:100%; display:flex; flex-direction:column; gap:8px; }
        .apl-resolution-input { background:#12121a; border:1px solid #1e1e2e; border-radius:8px; color:#e2e8f0; padding:8px 12px; font-size:13px; outline:none; width:100%; box-sizing:border-box; }
        .apl-resolution-input:focus { border-color:#d4a84b60; }
        .apl-resolve-btns { display:flex; gap:8px; flex-wrap:wrap; }
        .apl-player-inline { display:flex; align-items:center; gap:6px; flex:1; min-width:0; overflow:hidden; }
        .apl-chevron { font-size:10px; color:#4b5563; flex-shrink:0; }
        .apl-thread { display:flex; flex-direction:column; gap:8px; max-height:400px; overflow-y:auto; padding:4px 0; }
        .apl-msg { display:flex; flex-direction:column; gap:4px; padding:10px 12px; border-radius:10px; }
        .apl-msg-user { background:#1a1a2e; border:1px solid #2d2d4e; align-self:flex-start; max-width:90%; }
        .apl-msg-admin { background:#0e1a0e; border:1px solid #1a3a1a; align-self:flex-end; max-width:90%; }
        .apl-msg-meta { font-size:10px; color:#4b5563; }
        .apl-msg-body { font-size:13px; color:#d1d5db; line-height:1.5; white-space:pre-wrap; }
        .apl-msg-photo { font-size:12px; color:#60a5fa; }
        .apl-photo-id { font-family:monospace; font-size:11px; }
        /* Composer */
        .apl-composer { background:#0a0a14; border:1px solid #1e1e2e; border-radius:12px; overflow:hidden; }
        .apl-photo-preview { position:relative; padding:10px 12px 0; }
        .apl-preview-img { max-height:180px; max-width:100%; border-radius:8px; object-fit:cover; display:block; }
        .apl-preview-remove { position:absolute; top:6px; right:8px; background:#00000080; border:none; color:#fff; width:22px; height:22px; border-radius:50%; cursor:pointer; font-size:11px; display:flex; align-items:center; justify-content:center; }
        .apl-composer-row { display:flex; align-items:flex-end; gap:4px; padding:8px 10px; }
        .apl-attach-btn { background:transparent; border:none; color:#4b5563; font-size:18px; cursor:pointer; padding:4px 6px; border-radius:6px; flex-shrink:0; transition:color 0.2s; line-height:1; }
        .apl-attach-btn:hover { color:#d4a84b; }
        .apl-composer-input { flex:1; background:transparent; border:none; color:#e2e8f0; font-size:13px; outline:none; resize:none; font-family:inherit; line-height:1.5; max-height:120px; overflow-y:auto; padding:4px 0; }
        .apl-composer-input::placeholder { color:#2d3748; }
        .apl-send-btn { background:#d4a84b; border:none; color:#000; width:32px; height:32px; border-radius:50%; cursor:pointer; font-size:14px; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:all 0.2s; font-weight:700; }
        .apl-send-btn:hover:not(:disabled) { background:#e8c05a; transform:scale(1.05); }
        .apl-send-btn:disabled { background:#2d2d2d; color:#4b5563; cursor:not-allowed; transform:none; }

        @media (max-width:600px) {
          .arc-shell { padding:16px; }
          .arc-grid { grid-template-columns:1fr; }
          .arc-title { font-size:20px; }
          .arc-stats { gap:0; }
          .arc-stat { padding:0 10px; }
          .mst-grid { grid-template-columns:1fr; }
          .case-modal { max-height:92vh; border-radius:14px; }
          .case-body { padding:16px; }
          .case-cover { padding:18px; }
          .case-cover-inner { flex-direction:column; }
          .case-participants { flex-direction:column; }
          .case-side-left { border-right:none; border-bottom:1px solid #1e1e2e; }
          .case-divider { flex-direction:row; padding:10px 0; }
          .case-div-line { width:40px; height:1px; }

          /* Апелляции — компактный заголовок карточки */
          .apl-card { padding:12px; }
          .apl-card-top { flex-wrap:wrap; gap:6px; }
          .apl-player-inline { flex-wrap:wrap; gap:4px; }
          .apl-username { display:none; }
          .apl-uid { display:none; }
          .apl-date { font-size:10px; margin-left:auto; }
          .apl-thread { max-height:300px; }

          /* Архив — карточки */
          .arc-card-top { flex-wrap:wrap; }

          /* Общий фикс overflow */
          .apl-card, .arc-card { overflow:hidden; max-width:100%; }
          .arc-shell { overflow-x:hidden; }
          .apl-ban-reason { word-break:break-word; }
        }
      `}</style>
    </div>
  )
}
