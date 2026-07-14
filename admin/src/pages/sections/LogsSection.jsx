import { useCallback, useEffect, useState } from 'react'
import AdminSelect from '../../components/AdminSelect'
import { fetchAuditLogs, fetchLogsOverview, fetchSystemLogs, fetchTransferLogs } from '../../lib/adminClient'

const TABS = [
  { id: 'audit', label: 'Audit', hint: 'действия игроков и админов' },
  { id: 'transfers', label: 'Переводы', hint: 'P2P-переводы «дать» игрок → игрок' },
  { id: 'security', label: 'Security', hint: 'подозрительная активность' },
  { id: 'errors', label: 'Сбои', hint: '500 и ошибки сервера' },
]

function formatDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatKut(value) {
  if (value == null) return null
  return Number(value).toLocaleString('ru-RU')
}

function hasBalanceChange(row) {
  if (row.amount != null && row.amount !== 0) return true
  if (row.balanceBefore == null && row.balanceAfter == null) return false
  return row.balanceBefore !== row.balanceAfter
}

function eventTone(type) {
  if (!type) return 'default'
  if (type.startsWith('admin_')) return 'admin'
  if (type.startsWith('market_')) return 'market'
  if (type.includes('craft')) return 'craft'
  if (type.includes('plot') || type.includes('farm')) return 'farm'
  return 'default'
}

function AuditCard({ row }) {
  const tone = eventTone(row.eventType)
  const balance = hasBalanceChange(row)
  const label = row.eventLabel || row.eventType || '—'

  return (
    <article className="panel-log-card">
      <div className="panel-log-card-head">
        <time className="panel-log-time">{formatDate(row.createdAt)}</time>
        <span className="panel-log-user">ID {row.userId}</span>
        <span className={`panel-log-badge panel-log-badge-${tone}`}>{label}</span>
      </div>

      {(row.summary || row.eventType) && (
        <p className="panel-log-summary">
          {row.summary || row.eventType}
        </p>
      )}

      {balance && (
        <div className="panel-log-balance">
          {row.amount != null && row.amount !== 0 && (
            <span className={row.amount > 0 ? 'panel-log-delta-plus' : 'panel-log-delta-minus'}>
              {row.amount > 0 ? '+' : ''}{formatKut(row.amount)} КУТ
            </span>
          )}
          {row.balanceBefore != null && row.balanceAfter != null && (
            <span className="panel-log-balance-flow">
              {formatKut(row.balanceBefore)} → {formatKut(row.balanceAfter)}
            </span>
          )}
        </div>
      )}
    </article>
  )
}

function TransferCard({ row }) {
  return (
    <article className="panel-log-card">
      <div className="panel-log-card-head">
        <time className="panel-log-time">{formatDate(row.createdAt)}</time>
        <span className="panel-log-badge panel-log-badge-default">{row.cause || 'дать'}</span>
      </div>

      <p className="panel-log-summary">
        ID {row.senderId} → ID {row.receiverId} · <strong>{formatKut(row.amount)} КУТ</strong>
      </p>

      <div className="panel-log-balance">
        <span className="panel-log-balance-flow">
          Отправитель: {formatKut(row.senderBalanceBefore)} → {formatKut(row.senderBalanceAfter)}
        </span>
        <span className="panel-log-balance-flow">
          Получатель: {formatKut(row.receiverBalanceBefore)} → {formatKut(row.receiverBalanceAfter)}
        </span>
      </div>
    </article>
  )
}

function SystemCard({ row, variant }) {
  const isError = variant === 'errors'
  const isSecurity = variant === 'security' || row.security

  return (
    <article className={`panel-log-card${isSecurity ? ' panel-log-card-security' : ''}${isError ? ' panel-log-card-error' : ''}`}>
      <div className="panel-log-card-head">
        <time className="panel-log-time">{formatDate(row.createdAt)}</time>
        {row.status != null && (
          <span className={`panel-log-http panel-log-http-${row.status >= 500 ? '5xx' : 'other'}`}>
            HTTP {row.status}
          </span>
        )}
        {row.userId != null && row.userId > 0 && (
          <span className="panel-log-user">ID {row.userId}</span>
        )}
      </div>

      <div className="panel-log-system-code">
        <span className="panel-log-code">{row.code}</span>
        {row.codeTitle && <span className="panel-log-code-title">{row.codeTitle}</span>}
      </div>

      {row.message && (
        <p className="panel-log-message">{row.message}</p>
      )}

      {(row.method || row.path || row.clientIp) && (
        <div className="panel-log-meta">
          {row.method && row.path && (
            <span><strong>{row.method}</strong> {row.path}</span>
          )}
          {row.clientIp && <span>IP {row.clientIp}</span>}
        </div>
      )}
    </article>
  )
}

export default function LogsSection() {
  const [tab, setTab] = useState('audit')
  const [overview, setOverview] = useState(null)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [userId, setUserId] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [offset, setOffset] = useState(0)

  const loadOverview = useCallback(async () => {
    try {
      const data = await fetchLogsOverview()
      setOverview(data)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить сводку логов')
    }
  }, [])

  const loadItems = useCallback(async ({ append = false, nextOffset = 0 } = {}) => {
    setLoading(true)
    setError('')
    try {
      const uid = userId.trim()
      const data = tab === 'audit'
        ? await fetchAuditLogs({
            userId: uid || undefined,
            eventType: typeFilter || undefined,
            limit: 50,
            offset: nextOffset,
          })
        : tab === 'transfers'
          ? await fetchTransferLogs({
              userId: uid || undefined,
              limit: 50,
              offset: nextOffset,
            })
          : await fetchSystemLogs({
              category: tab,
              userId: uid || undefined,
              code: typeFilter || undefined,
              limit: 50,
              offset: nextOffset,
            })
      setTotal(data.total ?? 0)
      setItems((prev) => (append ? [...prev, ...(data.items || [])] : data.items || []))
      setOffset(nextOffset + (data.items?.length ?? 0))
    } catch (err) {
      setError(err.message || 'Не удалось загрузить логи')
    } finally {
      setLoading(false)
    }
  }, [tab, typeFilter, userId])

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  useEffect(() => {
    setOffset(0)
    loadItems({ offset: 0 })
  }, [tab, typeFilter, loadItems])

  const typeOptions = tab === 'audit'
    ? [
        { value: '', label: 'Все типы' },
        ...(overview?.auditEventTypes || []).map((t) => ({
          value: t.value,
          label: `${t.label} (${t.count})`,
        })),
      ]
    : tab === 'security' || tab === 'errors'
      ? [
          { value: '', label: 'Все коды' },
          ...(overview?.systemCodes || [])
            .filter((c) => (tab === 'security'
              ? c.value.startsWith('ERR_SEC_')
              : !c.value.startsWith('ERR_SEC_')))
            .map((c) => ({
              value: c.value,
              label: `${c.label} (${c.count})`,
            })),
        ]
      : []

  const stats = tab === 'audit'
    ? {
        main: overview?.auditTotal,
        today: overview?.auditToday,
        label: 'Событий audit',
        sub: 'действия в игре и админке',
      }
    : tab === 'security'
      ? {
          main: overview?.securityTotal,
          today: overview?.securityToday,
          label: 'Security alerts',
          sub: 'подозрение на взлом / абьюз',
        }
      : tab === 'transfers'
        ? {
            main: total,
            today: null,
            label: 'Переводов по фильтру',
            sub: 'P2P «дать» с балансом до/после',
          }
        : {
            main: overview?.errorTotal,
            today: overview?.errorToday,
            label: 'Сбоев сервера',
            sub: 'HTTP 500, БД, необработанные ошибки',
          }

  const emptyMessage = tab === 'audit'
    ? 'Нет событий по выбранному фильтру'
    : tab === 'security'
      ? 'Подозрительной активности не зафиксировано'
      : tab === 'transfers'
        ? 'Переводов по выбранному фильтру нет'
        : 'Сбоев сервера нет - всё работает штатно'

  return (
    <div className="panel-logs">
      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Logs · Логи</p>
        <h2 className="panel-page-title">Логи и безопасность</h2>
        <p className="panel-page-lead">
          Audit - действия игроков. Security - подозрительные запросы. Сбои - только реальные поломки сервера.
        </p>
        {error && <p className="panel-shelf-error">{error}</p>}
      </article>

      <div className="panel-logs-tabs">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`panel-logs-tab${tab === item.id ? ' panel-logs-tab-active' : ''}`}
            onClick={() => {
              setTab(item.id)
              setTypeFilter('')
            }}
          >
            <span className="panel-logs-tab-label">{item.label}</span>
            <span className="panel-logs-tab-hint">{item.hint}</span>
          </button>
        ))}
      </div>

      <div className="panel-logs-stats">
        <article className={`panel-shelf panel-log-stat${tab === 'errors' && stats.main === 0 ? ' panel-log-stat-ok' : ''}`}>
          <p className="panel-shelf-label">{stats.label}</p>
          <p className="panel-log-stat-value">
            {loading && !overview ? '…' : stats.main ?? 0}
          </p>
          <p className="panel-shelf-muted">
            {stats.today != null ? `сегодня: ${stats.today} · ` : ''}{stats.sub}
          </p>
        </article>
        <article className="panel-shelf panel-log-stat">
          <p className="panel-shelf-label">В выборке</p>
          <p className="panel-log-stat-value">{items.length}</p>
          <p className="panel-shelf-muted">из {total} по фильтру</p>
        </article>
        {tab === 'errors' && (
          <article className="panel-shelf panel-log-stat">
            <p className="panel-shelf-label">Telegram</p>
            <p className="panel-log-stat-value">{overview?.telegramErrorsEnabled ? 'ON' : 'OFF'}</p>
            <p className="panel-shelf-muted">уведомления о сбоях</p>
          </article>
        )}
      </div>

      {tab === 'security' && (overview?.topSecurityIps?.length > 0) && (
        <article className="panel-shelf">
          <p className="panel-shelf-label">Топ IP за сегодня</p>
          <p className="panel-shelf-muted" style={{ marginBottom: '0.5rem' }}>
            20+ событий за 5 минут с одной IP банятся автоматически на 1 час
          </p>
          <div className="panel-log-list">
            {overview.topSecurityIps.map((row) => (
              <div key={row.ip} className="panel-log-card" style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                <span className="panel-log-code">{row.ip}</span>
                <span className="panel-shelf-muted">{row.count} событий · последнее {formatDate(row.lastSeen)}</span>
              </div>
            ))}
          </div>
        </article>
      )}

      <article className="panel-shelf panel-logs-feed">
        <form
          className="panel-logs-filters"
          onSubmit={(e) => {
            e.preventDefault()
            setOffset(0)
            loadItems({ offset: 0 })
          }}
        >
          <label className="panel-economy-field panel-logs-filter-user">
            <span>{tab === 'transfers' ? 'User ID (отправитель или получатель)' : 'User ID'}</span>
            <input
              className="panel-users-input"
              value={userId}
              onChange={(e) => setUserId(e.target.value.replace(/[^\d]/g, ''))}
              placeholder="необязательно"
            />
          </label>
          {tab !== 'transfers' && (
            <label className="panel-economy-field panel-logs-filter-type">
              <span>{tab === 'audit' ? 'Тип события' : 'Код'}</span>
              <AdminSelect
                value={typeFilter}
                onChange={setTypeFilter}
                placeholder={tab === 'audit' ? 'Все типы' : 'Все коды'}
                options={typeOptions}
              />
            </label>
          )}
          <button type="submit" className="panel-users-btn panel-users-btn-primary" disabled={loading}>
            {loading ? '…' : 'Применить'}
          </button>
        </form>

        <div className="panel-log-list">
          {!loading && items.length === 0 && (
            <div className={`panel-log-empty${tab === 'errors' ? ' panel-log-empty-ok' : ''}`}>
              <p className="panel-log-empty-title">{emptyMessage}</p>
              {tab === 'errors' && (
                <p className="panel-log-empty-text">
                  Сюда попадают только HTTP 500, ошибки БД и необработанные исключения - не обычные 400/401.
                </p>
              )}
            </div>
          )}

          {tab === 'audit' && items.map((row) => (
            <AuditCard key={row.id} row={row} />
          ))}

          {tab === 'transfers' && items.map((row) => (
            <TransferCard key={row.id} row={row} />
          ))}

          {tab !== 'audit' && tab !== 'transfers' && items.map((row) => (
            <SystemCard key={row.id} row={row} variant={tab} />
          ))}

          {loading && items.length === 0 && (
            <div className="panel-log-empty">
              <p className="panel-shelf-muted">Загрузка…</p>
            </div>
          )}
        </div>

        {items.length < total && (
          <button
            type="button"
            className="panel-users-btn panel-broadcast-history-more"
            disabled={loading}
            onClick={() => loadItems({ append: true, nextOffset: offset })}
          >
            {loading ? '…' : `Показать ещё (${items.length}/${total})`}
          </button>
        )}
      </article>
    </div>
  )
}
