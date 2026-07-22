import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import {
  adjustAdminUserBalance,
  adjustAdminUserItem,
  deletePlayerNote,
  exportPlayerProfile,
  fetchAdminUser,
  fetchAdminUserAudit,
  fetchAdminUserCuteHistory,
  fetchContentDex,
  fetchPlayerBans,
  fetchPlayerInventory,
  fetchPlayerNotes,
  fetchPlayerQuests,
  resetAdminUserOnboarding,
  searchAdminUsers,
  setAdminUserBanned,
  uploadBanEvidence,
  upsertPlayerNote,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'

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
  { id: 'quests', label: 'Квесты' },
  { id: 'bans', label: 'Баны' },
  { id: 'inventory', label: 'Инвентарь' },
  { id: 'notes', label: 'Заметки' },
]

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

function EmptyHint({ children }) {
  return <p className="panel-users-empty-hint">{children}</p>
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
function InventoryTab({ userId }) {
  const [items, setItems] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    fetchPlayerInventory(userId)
      .then((d) => setItems(d.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [userId])

  if (loading) return <p className="panel-shelf-muted">Загрузка…</p>
  if (error) return <p className="panel-shelf-error">{error}</p>
  if (!items || items.length === 0) return <p className="panel-shelf-muted">Инвентарь пуст</p>

  return (
    <div className="pu-inventory">
      <h4 className="pu-section-title">Инвентарь ({items.length} позиций)</h4>
      <div className="pu-inventory-grid">
        {items.map((item) => (
          <div key={item.itemId} className="pu-inv-item">
            <span className="pu-inv-emoji">{item.emoji}</span>
            <span className="pu-inv-name">{item.name}</span>
            <span className="pu-inv-count">×{item.count}</span>
          </div>
        ))}
      </div>
      <style>{`
        .pu-inventory { padding: 4px 0; }
        .pu-inventory-grid { display: flex; flex-direction: column; gap: 4px; margin-top: 10px; }
        .pu-inv-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #0a0a0c; border: 1px solid #1c1c20; border-radius: 8px; }
        .pu-inv-emoji { font-size: 18px; flex-shrink: 0; width: 24px; text-align: center; }
        .pu-inv-name { flex: 1; font-size: 13px; color: #e5e5e5; }
        .pu-inv-count { font-size: 13px; font-weight: 700; color: #cccccc; flex-shrink: 0; }
      `}</style>
    </div>
  )
}

// ---- Admin notes tab ----
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
              <span className="pu-note-admin">Admin {n.adminUserId}</span>
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
        placeholder="🔍 Поиск предмета…"
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
          💜 Донаты: {donations.count} шт · {donations.total.toLocaleString('ru-RU')} kut
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
              {it.direction === 'in' ? '+' : '−'}{Math.abs(it.amount)} kut
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
  const isOwner = role === 'owner'  // история кут — только для владельцев
  const perms = new Set(permissions)
  const canBan = perms.has('moderate_ban')
  const canUnban = perms.has('moderate_unban')
  const canBalance = perms.has('adjust_balance')
  const canItems = perms.has('give_items')
  const canManageSettings = perms.has('manage_settings')

  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [profile, setProfile] = useState(null)
  const [audit, setAudit] = useState(null)
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
  const [banReason, setBanReason] = useState('')
  const [banEvidence, setBanEvidence] = useState('')
  const [banPhotoIds, setBanPhotoIds] = useState([])
  const [unbanReason, setUnbanReason] = useState('')
  const [unbanEvidence, setUnbanEvidence] = useState('')
  const [unbanPhotoIds, setUnbanPhotoIds] = useState([])
  const [pendingAction, setPendingAction] = useState(null)

  // compare mode
  const [compareQuery, setCompareQuery] = useState('')
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
    } catch (err) {
      if (reqId !== loadReqRef.current) return
      setError(err.message || 'Не удалось загрузить игрока')
      setProfile(null)
      setAudit(null)
    } finally {
      if (reqId === loadReqRef.current) setLoading(false)
    }
  }, [])

  const handleLoadCompare = useCallback(async () => {
    const q = compareQuery.trim()
    if (!q) return
    setCompareLoading(true)
    setCompareError('')
    try {
      const data = await searchAdminUsers(q)
      const list = data.results || []
      if (list.length === 0) { setCompareError('Никого не найдено'); return }
      const first = list[0]
      const userData = await fetchAdminUser(first.userId)
      setCompareProfile(userData)
    } catch (e) {
      setCompareError(e.message || 'Ошибка')
    } finally {
      setCompareLoading(false)
    }
  }, [compareQuery])

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
        <p className="panel-shelf-label">Users · Игроки</p>
        <h2 className="panel-page-title">Поиск игрока</h2>
        <p className="panel-page-lead">ID или @username (минимум 2 символа для имени)</p>

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
            placeholder="6908672757 или @username"
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
                    ID {row.userId} · {row.balance} kut
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

        {/* ── Вкладки не-профиль: контент на всю ширину ── */}
        {hasProfile && profileTab !== 'profile' && (
          <article className="panel-shelf panel-users-card pu-tab-content-full">
            {profileTab === 'quests' && <QuestsTab userId={profile.userId} />}
            {profileTab === 'bans' && <BansTab userId={profile.userId} />}
            {profileTab === 'inventory' && <InventoryTab userId={profile.userId} />}
            {profileTab === 'notes' && <NotesTab userId={profile.userId} />}
          </article>
        )}

        {/* ── Вкладка «Профиль»: двухколоночный лейаут ── */}
        <article className={`panel-shelf panel-users-card panel-users-profile-card${hasProfile && profileTab !== 'profile' ? ' pu-hidden' : ''}`}>
          {(profileTab === 'profile' || !hasProfile) && (<>
          <div className="panel-users-avatar-wrap">
            {profile?.photoUrl ? (
              <img className="panel-users-avatar" src={profile.photoUrl} alt="" />
            ) : (
              <div className="panel-users-avatar panel-users-avatar-fallback" aria-hidden="true">
                {hasProfile ? initialsFromName(profile.displayName) : '?'}
              </div>
            )}
          </div>

          <h3 className={`panel-users-name${!hasProfile ? ' panel-users-placeholder' : ''}`}>
            {hasProfile ? profile.displayName : '-'}
            {hasProfile && profile.username && (
              <span className="panel-users-handle"> @{profile.username}</span>
            )}
          </h3>
          <p className="panel-users-id">
            ID {hasProfile ? profile.userId : '-'}
          </p>

          {hasProfile && profile.banned && (
            <span className="panel-users-badge panel-users-badge-ban">BAN</span>
          )}

          <div className="panel-users-stats">
            <div>
              <span className="panel-users-stat-label">Kut</span>
              <strong className={!hasProfile ? 'panel-users-placeholder' : ''}>
                {hasProfile ? profile.balance?.toLocaleString('ru-RU') : '-'}
              </strong>
            </div>
            <div>
              <span className="panel-users-stat-label">Грядки</span>
              <strong className={!hasProfile ? 'panel-users-placeholder' : ''}>
                {hasProfile ? `${profile.ownedPlots}/${profile.maxPlots}` : '-'}
              </strong>
            </div>
            <div>
              <span className="panel-users-stat-label">Биржа</span>
              <strong className={!hasProfile ? 'panel-users-placeholder' : ''}>
                {hasProfile ? profile.marketSalesCount ?? 0 : '-'}
              </strong>
            </div>
            <div>
              <span className="panel-users-stat-label">Обучение</span>
              <strong className={!hasProfile ? 'panel-users-placeholder' : ''}>
                {hasProfile
                  ? profile.onboarding?.done
                    ? 'пройдено'
                    : profile.onboarding?.active
                      ? 'активно'
                      : 'нет'
                  : '-'}
              </strong>
            </div>
          </div>

          <p className="panel-users-meta-line">
            <span className="panel-users-stat-label">Последняя активность</span>
            <span className={!hasProfile ? 'panel-users-placeholder' : ''}>
              {hasProfile && profile.lastSeenAt ? formatDate(profile.lastSeenAt) : '-'}
            </span>
          </p>

          {hasProfile && profile.banned && profile.bannedReason && (
            <p className="panel-users-ban-reason">Причина: {profile.bannedReason}</p>
          )}

          {!hasProfile && !loading && (
            <EmptyHint>Найди игрока и профиль заполнится здесь</EmptyHint>
          )}
          </>)}
        </article>

        {/* Compare panel */}
        {showCompare && hasProfile && (
          <article className="panel-shelf panel-users-card pu-compare-card">
            <div className="pu-compare-head">
              <p className="panel-shelf-label">⚖️ Сравнение</p>
              <button className="pu-close-btn" onClick={() => { setShowCompare(false); setCompareProfile(null) }}>✕</button>
            </div>
            <form
              className="panel-users-search-form"
              onSubmit={(e) => { e.preventDefault(); handleLoadCompare() }}
            >
              <input
                className="panel-users-input"
                value={compareQuery}
                onChange={(e) => setCompareQuery(e.target.value)}
                placeholder="ID или @username"
                disabled={compareLoading}
              />
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

        <div className={`panel-users-right${hasProfile && profileTab !== 'profile' ? ' pu-hidden' : ''}`}>
          <article className="panel-shelf panel-users-card panel-users-inventory-card">
            <p className="panel-shelf-label">Инвентарь</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">Предметы</h3>

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
                    {item.emoji} {item.name} ×{item.count}
                  </li>
                ))}
              </ul>
            )}

            {!hasProfile && !loading && (
              <EmptyHint>Список предметов после поиска</EmptyHint>
            )}
          </article>

          <article className="panel-shelf panel-users-card panel-users-actions-card">
            <p className="panel-shelf-label">Действия</p>
            <h3 className="panel-users-subtitle panel-users-subtitle-tight">Выдача и модерация</h3>

            <div className="panel-users-action-grid">
              {canBalance && (
              <form
                className="panel-users-action-block"
                onSubmit={(e) => {
                  e.preventDefault()
                  const delta = Number.parseInt(kutDelta, 10)
                  if (!Number.isFinite(delta) || delta === 0) return
                  runAction(() => adjustAdminUserBalance(profile.userId, delta, kutNote.trim()))
                  setKutDelta('')
                  setKutNote('')
                }}
              >
                <p className="panel-users-action-title">Kut (+ / −)</p>
                <input
                  className="panel-users-input"
                  value={kutDelta}
                  onChange={(e) => setKutDelta(e.target.value.replace(/[^\d-]/g, ''))}
                  placeholder="100 или -50"
                  disabled={!hasProfile || actionLoading}
                />
                <input
                  className="panel-users-input"
                  value={kutNote}
                  onChange={(e) => setKutNote(e.target.value)}
                  placeholder="Сообщение в боте (необязательно)"
                  disabled={!hasProfile || actionLoading}
                />
                <button type="submit" className="panel-users-btn" disabled={!hasProfile || actionLoading}>
                  Применить
                </button>
              </form>
              )}

              {canItems && (
              <form
                className="panel-users-action-block"
                onSubmit={(e) => {
                  e.preventDefault()
                  const delta = Number.parseInt(itemDelta, 10)
                  if (!itemId.trim() || !Number.isFinite(delta) || delta === 0) return
                  runAction(() =>
                    adjustAdminUserItem(profile.userId, itemId.trim(), delta, itemNote.trim()),
                  )
                  setItemDelta('')
                  setItemNote('')
                }}
              >
                <p className="panel-users-action-title">Предмет</p>
                <DexItemQuickPicker
                  dexItems={dexItems}
                  onSelect={(id) => setItemId(id)}
                  disabled={!hasProfile || actionLoading}
                />
                <input
                  className="panel-users-input"
                  value={itemId}
                  onChange={(e) => setItemId(e.target.value)}
                  placeholder="item_id (или выбери выше)"
                  disabled={!hasProfile || actionLoading}
                />
                <input
                  className="panel-users-input"
                  value={itemDelta}
                  onChange={(e) => setItemDelta(e.target.value.replace(/[^\d-]/g, ''))}
                  placeholder="± количество"
                  disabled={!hasProfile || actionLoading}
                />
                <input
                  className="panel-users-input"
                  value={itemNote}
                  onChange={(e) => setItemNote(e.target.value)}
                  placeholder="Сообщение в боте (необязательно)"
                  disabled={!hasProfile || actionLoading}
                />
                <button type="submit" className="panel-users-btn" disabled={!hasProfile || actionLoading}>
                  Выдать / списать
                </button>
              </form>
              )}

              {canBan && (
              <div className="panel-users-action-block">
                <p className="panel-users-action-title">Бан</p>
                <input
                  className="panel-users-input"
                  value={banReason}
                  onChange={(e) => setBanReason(e.target.value)}
                  placeholder="Причина (уйдёт в бот)"
                  disabled={!hasProfile || actionLoading || (hasProfile && profile.banned)}
                />
                <textarea
                  className="panel-users-input"
                  rows={2}
                  value={banEvidence}
                  onChange={(e) => setBanEvidence(e.target.value)}
                  placeholder="Доказательства"
                  disabled={!hasProfile || actionLoading || (hasProfile && profile.banned)}
                />
                <EvidencePhotoPicker
                  key={`ban-${profile?.userId ?? 'empty'}`}
                  fileIds={banPhotoIds}
                  onChange={setBanPhotoIds}
                  disabled={!hasProfile || actionLoading || (hasProfile && profile.banned)}
                />
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-danger"
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
              <div className="panel-users-action-block">
                <p className="panel-users-action-title">Разбан</p>
                {hasProfile && profile.banned && profile.bannedReason && (
                  <p className="panel-shelf-muted">Причина бана: {profile.bannedReason}</p>
                )}
                <input
                  className="panel-users-input"
                  value={unbanReason}
                  onChange={(e) => setUnbanReason(e.target.value)}
                  placeholder="Причина разбана"
                  disabled={!hasProfile || actionLoading || (hasProfile && !profile.banned)}
                />
                <textarea
                  className="panel-users-input"
                  rows={2}
                  value={unbanEvidence}
                  onChange={(e) => setUnbanEvidence(e.target.value)}
                  placeholder="Обоснование"
                  disabled={!hasProfile || actionLoading || (hasProfile && !profile.banned)}
                />
                <EvidencePhotoPicker
                  key={`unban-${profile?.userId ?? 'empty'}`}
                  fileIds={unbanPhotoIds}
                  onChange={setUnbanPhotoIds}
                  disabled={!hasProfile || actionLoading || (hasProfile && !profile.banned)}
                />
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-success"
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
              <div className="panel-users-action-block">
                <p className="panel-users-action-title">Обучение</p>
                <p className="panel-shelf-muted">Сброс + грядка №1</p>
                <button
                  type="button"
                  className="panel-users-btn"
                  disabled={!hasProfile || actionLoading}
                  onClick={() => setPendingAction('onboarding')}
                >
                  Сбросить
                </button>
              </div>
              )}
            </div>
          </article>
        </div>

        <article className="panel-shelf panel-users-card panel-users-bottom">
          <div className="panel-users-bottom-grid">
            <div className="panel-users-plots-block">
              <p className="panel-shelf-label">Ферма</p>
              <h3 className="panel-users-subtitle panel-users-subtitle-tight">Грядки</h3>
              <div className="panel-users-plot-grid">
                {Array.from({ length: plotSlots }, (_, i) => {
                  const plotId = i + 1
                  const plot = plots.find((p) => p.id === plotId)
                  return (
                    <div
                      key={plotId}
                      className={`panel-users-plot${plot ? '' : ' panel-users-plot-empty'}`}
                    >
                      <span className="panel-users-plot-id">{plotId}</span>
                      <span className="panel-users-plot-status">
                        {plot ? plot.status : '—'}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="panel-users-audit-block">
              <p className="panel-shelf-label">История</p>
              <h3 className="panel-users-subtitle panel-users-subtitle-tight">
                {historySource === 'audit'
                  ? <>События {hasProfile ? `(${audit?.total ?? 0})` : ''}</>
                  : 'Кут — полная история'}
              </h3>

              {hasProfile && isOwner && (
                <div className="pu-hist-switch">
                  <button
                    className={`pu-hist-tab${historySource === 'audit' ? ' active' : ''}`}
                    onClick={() => setHistorySource('audit')}
                  >Действия</button>
                  <button
                    className={`pu-hist-tab${historySource === 'cute' ? ' active' : ''}`}
                    onClick={() => setHistorySource('cute')}
                  >Кут (полная)</button>
                </div>
              )}

              <style>{`
                .pu-hist-switch { display: inline-flex; gap: 4px; margin: 6px 0 10px; }
                .pu-hist-tab { font-size: 12px; padding: 4px 10px; border-radius: 8px; border: 1px solid #1c1c20; background: #0a0a0c; color: #aaa; cursor: pointer; }
                .pu-hist-tab.active { background: #1c1c22; color: #fff; }
              `}</style>

              {hasProfile && isOwner && historySource === 'cute' && (
                <CuteHistoryFeed userId={profile.userId} />
              )}

              {historySource === 'audit' && (<>
                {!hasProfile && (
                  <ul className="panel-users-audit-list panel-users-audit-list-empty">
                    {[1, 2, 3].map((n) => (
                      <li key={n} className="panel-users-audit-ghost">
                        <span className="panel-users-ghost-bar panel-users-ghost-bar-wide" />
                      </li>
                    ))}
                  </ul>
                )}

                {hasProfile && (audit?.events || []).length === 0 && (
                  <p className="panel-shelf-muted">Записей пока нет</p>
                )}

                {hasProfile && (audit?.events || []).length > 0 && (
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
                            {ev.amount} kut
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

                {!hasProfile && !loading && (
                  <EmptyHint>История действий игрока</EmptyHint>
                )}
              </>)}
            </div>
          </div>
        </article>
      </div>
    </div>
  )
}
