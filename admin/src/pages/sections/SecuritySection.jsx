import { useCallback, useEffect, useState } from 'react'
import {
  addIpBan,
  fetchAdminAuditActions,
  fetchAdminAuditLog,
  fetchAdminSessions,
  fetchIpBans,
  forceReauth,
  removeIpBan,
} from '../../lib/adminClient'
import { filterSectionTabs } from '../../constants/panelAccessTree'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  } catch { return iso }
}

function timeSince(iso) {
  if (!iso) return 'никогда'
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return 'только что'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} мин назад`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} ч назад`
  return `${Math.floor(diff / 86_400_000)} дн назад`
}

// ---------------------------------------------------------------------------
// Tab: Audit log
// ---------------------------------------------------------------------------

const ACTION_COLORS = {
  login: '#4ade80',
  logout: '#94a3b8',
  ban_user: '#f87171',
  unban_user: '#4ade80',
  balance_change: '#fbbf24',
  item_grant: '#a78bfa',
  settings_change: '#60a5fa',
  quest_create: '#34d399',
  quest_update: '#34d399',
  quest_delete: '#f87171',
  dex_item_create: '#34d399',
  dex_item_update: '#34d399',
  dex_item_delete: '#f87171',
  ip_ban_add: '#f87171',
  ip_ban_remove: '#4ade80',
  force_reauth: '#f97316',
  broadcast_schedule: '#60a5fa',
  broadcast_cancel: '#f87171',
  maintenance_toggle: '#fbbf24',
}

function AuditRow({ row }) {
  const color = ACTION_COLORS[row.action] || '#94a3b8'
  return (
    <div className="sec-audit-row">
      <time className="sec-audit-time">{fmtDate(row.createdAt)}</time>
      <span className="sec-audit-badge" style={{ '--badge-color': color }}>
        {row.actionLabel}
      </span>
      <span className="sec-audit-admin">admin {row.adminUserId}</span>
      {row.targetLabel && (
        <span className="sec-audit-target">→ {row.targetLabel}</span>
      )}
      {row.ip && <span className="sec-audit-ip">{row.ip}</span>}
    </div>
  )
}

function AuditTab() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(false)
  const LIMIT = 50

  const load = useCallback(async (off = 0, act = action) => {
    setLoading(true)
    try {
      const data = await fetchAdminAuditLog({ action: act || undefined, limit: LIMIT, offset: off })
      setItems(data.items || [])
      setTotal(data.total || 0)
      setOffset(off)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [action])

  useEffect(() => {
    load(0)
    fetchAdminAuditActions()
      .then(d => setActions(d.actions || []))
      .catch(() => {})
  }, [])

  const handleActionChange = (e) => {
    const val = e.target.value
    setAction(val)
    load(0, val)
  }

  return (
    <div className="sec-tab-body">
      <div className="sec-audit-filters">
        <select className="sec-select" value={action} onChange={handleActionChange}>
          <option value="">Все действия</option>
          {actions.map(a => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        <button className="sec-btn sec-btn-ghost" onClick={() => load(0)}>
          Обновить
        </button>
        <span className="sec-audit-count">{total} записей</span>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="sec-audit-list">
        {items.map(row => <AuditRow key={row.id} row={row} />)}
        {!loading && items.length === 0 && (
          <p className="sec-empty">Действий пока нет</p>
        )}
      </div>

      {total > LIMIT && (
        <div className="sec-pagination">
          <button
            className="sec-btn"
            disabled={offset === 0}
            onClick={() => load(Math.max(0, offset - LIMIT))}
          >
            ← Назад
          </button>
          <span>{Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}</span>
          <button
            className="sec-btn"
            disabled={offset + LIMIT >= total}
            onClick={() => load(offset + LIMIT)}
          >
            Вперёд →
          </button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: IP Bans
// ---------------------------------------------------------------------------

function IpBansTab() {
  const [bans, setBans] = useState([])
  const [loading, setLoading] = useState(false)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ ipOrCidr: '', reason: '', expiresAt: '' })
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchIpBans()
      setBans(data.bans || [])
    } catch {
      setBans([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [])

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!form.ipOrCidr.trim()) { setError('Введите IP или CIDR'); return }
    setError('')
    setAdding(true)
    try {
      await addIpBan({
        ipOrCidr: form.ipOrCidr.trim(),
        reason: form.reason.trim(),
        expiresAt: form.expiresAt || null,
      })
      setForm({ ipOrCidr: '', reason: '', expiresAt: '' })
      await load()
    } catch (err) {
      setError(err?.detail || err?.message || 'Ошибка')
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (id) => {
    if (!confirm('Снять IP-бан?')) return
    await removeIpBan(id)
    await load()
  }

  const active = bans.filter(b => b.active)
  const inactive = bans.filter(b => !b.active)

  return (
    <div className="sec-tab-body">
      {/* Add form */}
      <form className="sec-ipban-form" onSubmit={handleAdd}>
        <h3 className="sec-ipban-form-title">Добавить IP-бан</h3>
        <div className="sec-ipban-fields">
          <div className="sec-field">
            <label>IP или CIDR</label>
            <input
              className="sec-input"
              placeholder="1.2.3.4 или 1.2.3.0/24"
              value={form.ipOrCidr}
              onChange={e => setForm(f => ({ ...f, ipOrCidr: e.target.value }))}
            />
          </div>
          <div className="sec-field">
            <label>Причина</label>
            <input
              className="sec-input"
              placeholder="Необязательно"
              value={form.reason}
              onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
            />
          </div>
          <div className="sec-field">
            <label>Истекает (опционально)</label>
            <input
              className="sec-input"
              type="datetime-local"
              value={form.expiresAt}
              onChange={e => setForm(f => ({ ...f, expiresAt: e.target.value }))}
            />
          </div>
        </div>
        {error && <p className="sec-error">{error}</p>}
        <button type="submit" className="sec-btn sec-btn-danger" disabled={adding}>
          {adding ? 'Добавление…' : '🚫 Заблокировать'}
        </button>
      </form>

      {/* Active bans */}
      <div className="sec-ipban-section">
        <h3 className="sec-ipban-section-title">
          Активные баны <span className="sec-count">{active.length}</span>
        </h3>
        {loading && <p className="sec-loading">Загрузка…</p>}
        {!loading && active.length === 0 && (
          <p className="sec-empty">Нет активных IP-банов</p>
        )}
        {active.map(ban => (
          <div key={ban.id} className="sec-ipban-row">
            <span className="sec-ipban-ip">{ban.ipOrCidr}</span>
            {ban.reason && <span className="sec-ipban-reason">{ban.reason}</span>}
            <span className="sec-ipban-meta">
              {fmtDate(ban.bannedAt)}
              {ban.expiresAt && ` → до ${fmtDate(ban.expiresAt)}`}
            </span>
            <button
              className="sec-btn sec-btn-ghost sec-btn-sm"
              onClick={() => handleRemove(ban.id)}
            >
              ✕ Снять
            </button>
          </div>
        ))}
      </div>

      {/* Inactive bans */}
      {inactive.length > 0 && (
        <details className="sec-ipban-history">
          <summary>История снятых банов ({inactive.length})</summary>
          {inactive.map(ban => (
            <div key={ban.id} className="sec-ipban-row sec-ipban-row-inactive">
              <span className="sec-ipban-ip">{ban.ipOrCidr}</span>
              {ban.reason && <span className="sec-ipban-reason">{ban.reason}</span>}
              <span className="sec-ipban-meta">{fmtDate(ban.bannedAt)}</span>
              <span className="sec-badge-inactive">снят</span>
            </div>
          ))}
        </details>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Sessions & 2FA
// ---------------------------------------------------------------------------

function SessionsTab() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(false)
  const [acting, setActing] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAdminSessions()
      setSessions(data.sessions || [])
    } catch {
      setSessions([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [])

  const handleForceReauth = async (userId) => {
    const who = userId ? `администратора ${userId}` : 'всех администраторов'
    if (!confirm(`Принудительно выйти из сессии ${who}?`)) return
    setActing(userId ?? 'all')
    try {
      await forceReauth(userId)
      await load()
    } catch {
      // forceReauth error is tolerable - reload anyway
      await load()
    } finally {
      setActing(null)
    }
  }

  return (
    <div className="sec-tab-body">
      <div className="sec-sessions-header">
        <p className="sec-sessions-desc">
          При сбросе сессии администратор должен будет повторно войти и подтвердить 2FA-код.
          Также сбрасывается зарегистрированный отпечаток устройства.
        </p>
        <button
          className="sec-btn sec-btn-danger"
          disabled={acting === 'all'}
          onClick={() => handleForceReauth(null)}
        >
          {acting === 'all' ? 'Сброс…' : '⚠️ Сбросить все сессии'}
        </button>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="sec-sessions-list">
        {sessions.map(s => (
          <div key={s.userId} className="sec-session-row">
            <div className="sec-session-info">
              <span className="sec-session-name">
                {s.firstName || s.username || `ID ${s.userId}`}
              </span>
              <span className="sec-session-id">#{s.userId}</span>
              <span
                className={`sec-session-status ${s.hasFingerprint ? 'sec-session-active' : 'sec-session-new'}`}
              >
                {s.hasFingerprint ? '🔒 устройство зарегистрировано' : '⚪ устройство не установлено'}
              </span>
            </div>
            <div className="sec-session-meta">
              <span>IP: {s.lastIp || '-'}</span>
              <span>Был: {timeSince(s.lastSeenAt)}</span>
              {s.forceReauthAt && (
                <span className="sec-session-forced">
                  Сброс: {fmtDate(s.forceReauthAt)}
                </span>
              )}
            </div>
            <button
              className="sec-btn sec-btn-ghost sec-btn-sm"
              disabled={acting === s.userId}
              onClick={() => handleForceReauth(s.userId)}
            >
              {acting === s.userId ? '…' : 'Сбросить'}
            </button>
          </div>
        ))}
        {!loading && sessions.length === 0 && (
          <p className="sec-empty">Нет зарегистрированных администраторов</p>
        )}
      </div>

      <div className="sec-sessions-notice">
        <h4>Как работает 2FA при смене устройства</h4>
        <ul>
          <li>При каждом входе в панель система запоминает отпечаток браузера (User-Agent)</li>
          <li>Если следующий запрос приходит с другим браузером/устройством - сессия аннулируется</li>
          <li>Администратор видит сообщение «Обнаружено новое устройство» и должен войти заново</li>
          <li>Вход всегда требует 2FA-код из Google Authenticator</li>
        </ul>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'audit', label: '🔍 Аудит действий' },
  { id: 'ipbans', label: '🚫 IP-баны' },
  { id: 'sessions', label: '🔐 Сессии и 2FA' },
]

export default function SecuritySection({ panelTabs = null }) {
  const tabs = filterSectionTabs('security', TABS, panelTabs)
  const [tab, setTab] = useState(tabs[0]?.id || 'audit')
  const activeTab = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id

  return (
    <section className="panel-security">
      <header className="sec-header">
        <h2 className="sec-title">Управление доступом</h2>
        <p className="sec-subtitle">
          Аудит действий администраторов, блокировка IP-адресов и управление 2FA-сессиями
        </p>
      </header>

      <nav className="sec-tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            className={`sec-tab${activeTab === t.id ? ' sec-tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {activeTab === 'audit' && <AuditTab />}
      {activeTab === 'ipbans' && <IpBansTab />}
      {activeTab === 'sessions' && <SessionsTab />}
      {!activeTab && <p className="sec-empty sec-tab-body">Нет доступных разделов</p>}
    </section>
  )
}
