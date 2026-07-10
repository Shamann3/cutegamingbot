import { useCallback, useEffect, useState } from 'react'
import {
  fetchAdminAccount,
  fetchRecentAdminAccounts,
  searchAdminAccounts,
} from '../../lib/adminClient'

const PLATFORM_LABELS = {
  ios: 'iPhone / iOS',
  android: 'Android',
  tdesktop: 'Telegram Desktop',
  macos: 'macOS',
  web: 'Web',
  weba: 'Web (A)',
  unigram: 'Unigram',
  unknown: 'Неизвестно',
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

function formatPlatform(value) {
  if (!value) return '—'
  return PLATFORM_LABELS[value] || value
}

function initials(name) {
  const parts = String(name || '?').trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return (parts[0]?.[0] || '?').toUpperCase()
}

function countryFlag(code) {
  if (!code || code.length !== 2) return ''
  return String.fromCodePoint(
    ...[...code.toUpperCase()].map((char) => 127397 + char.charCodeAt(0)),
  )
}

function formatGeo(geo) {
  if (!geo) return null
  const flag = geo.countryCode ? countryFlag(geo.countryCode) : ''
  const label = geo.label || '—'
  if (geo.private) return label
  const parts = [flag ? `${flag} ${label}` : label]
  if (geo.isp) parts.push(geo.isp)
  return parts.join(' · ')
}

async function copyText(text) {
  if (!text) return false
  try {
    await navigator.clipboard.writeText(String(text))
    return true
  } catch {
    return false
  }
}

function InfoRow({ label, value, mono }) {
  return (
    <div className="panel-account-info-row">
      <span className="panel-account-info-label">{label}</span>
      <span className={`panel-account-info-value${mono ? ' panel-account-mono' : ''}`}>
        {value ?? '—'}
      </span>
    </div>
  )
}

function SearchResult({ row, active, onSelect }) {
  return (
    <button
      type="button"
      className={`panel-account-search-item${active ? ' panel-account-search-item-active' : ''}`}
      onClick={() => onSelect(row.userId)}
    >
      <span className="panel-account-search-name">{row.displayName}</span>
      <span className="panel-account-search-meta">
        ID {row.userId}
        {row.username ? ` · @${row.username}` : ''}
        {row.lastClientIp ? ` · ${row.lastClientIp}` : ''}
      </span>
      {row.onlineNow && (
        <span className="panel-account-badge panel-account-badge-online panel-account-search-online">
          Online
        </span>
      )}
      {row.lastPlatform && (
        <span className="panel-account-search-platform">{formatPlatform(row.lastPlatform)}</span>
      )}
    </button>
  )
}

function LoginHistoryItem({ row }) {
  return (
    <div className="panel-account-history-item">
      <div className="panel-account-history-head">
        <time className="panel-log-time">{formatDate(row.createdAt)}</time>
        <span className="panel-account-history-ip">{row.clientIp || '—'}</span>
        <span className="panel-account-history-platform">{formatPlatform(row.platform)}</span>
        {row.isPremium && (
          <span className="panel-account-badge panel-account-badge-premium">Premium</span>
        )}
      </div>
      <div className="panel-account-history-details">
        {row.deviceModel && (
          <span className="panel-account-history-tag">Модель: {row.deviceModel}</span>
        )}
        {row.appVersion && (
          <span className="panel-account-history-tag">TG {row.appVersion}</span>
        )}
        {row.screenWidth && row.screenHeight && (
          <span className="panel-account-history-tag">
            {row.screenWidth}×{row.screenHeight}
          </span>
        )}
        {row.timezone && (
          <span className="panel-account-history-tag">{row.timezone}</span>
        )}
        {row.languageCode && (
          <span className="panel-account-history-tag">lang: {row.languageCode}</span>
        )}
      </div>
      {row.userAgent && (
        <p className="panel-account-history-ua">{row.userAgent}</p>
      )}
    </div>
  )
}

export default function AccountsSection({ onOpenInUsers }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [recent, setRecent] = useState([])
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [recentLoading, setRecentLoading] = useState(false)
  const [error, setError] = useState('')
  const [copyHint, setCopyHint] = useState('')

  const loadAccount = useCallback(async (userId) => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchAdminAccount(userId)
      setProfile(data)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить пользователя')
      setProfile(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadRecent = useCallback(async () => {
    setRecentLoading(true)
    try {
      const data = await fetchRecentAdminAccounts(30)
      setRecent(data.results || [])
    } catch (err) {
      setRecent([])
      setError(err.message || 'Не удалось загрузить список аккаунтов')
    } finally {
      setRecentLoading(false)
    }
  }, [])

  useEffect(() => {
    loadRecent()
  }, [loadRecent])

  const handleSearch = useCallback(async () => {
    const q = query.trim()
    if (!q) return
    setLoading(true)
    setError('')
    try {
      const data = await searchAdminAccounts(q)
      const list = data.results || []
      setResults(list)
      if (list.length === 1) {
        await loadAccount(list[0].userId)
      } else if (list.length === 0) {
        setProfile(null)
        setError('Никого не найдено')
      } else {
        setProfile(null)
      }
    } catch (err) {
      setError(err.message || 'Ошибка поиска')
      setResults([])
      setProfile(null)
    } finally {
      setLoading(false)
    }
  }, [query, loadAccount])

  const handleRefresh = useCallback(async () => {
    if (!profile?.userId) return
    await loadAccount(profile.userId)
    await loadRecent()
  }, [profile?.userId, loadAccount, loadRecent])

  const handleCopy = useCallback(async (text, label) => {
    const ok = await copyText(text)
    setCopyHint(ok ? `${label} скопирован` : 'Не удалось скопировать')
    window.setTimeout(() => setCopyHint(''), 2000)
  }, [])

  const device = profile?.device || {}
  const network = profile?.network || {}
  const telegram = profile?.telegram || {}
  const geoLabel = formatGeo(network.geo)

  return (
    <div className="panel-accounts">
      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Accounts · Пользователи</p>
        <h2 className="panel-page-title">Карточка пользователя</h2>
        <p className="panel-page-lead">
          Данные подтягиваются при входе в игровой WebApp: Telegram-профиль, устройство, IP и история сессий.
        </p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {copyHint && <p className="panel-shelf-ok">{copyHint}</p>}
      </article>

      <article className="panel-shelf">
        <form
          className="panel-accounts-search"
          onSubmit={(e) => {
            e.preventDefault()
            handleSearch()
          }}
        >
          <input
            className="panel-users-input panel-accounts-search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="ID или @username"
          />
          <button type="submit" className="panel-users-btn panel-users-btn-primary" disabled={loading}>
            {loading ? '…' : 'Найти'}
          </button>
        </form>

        {results.length > 1 && (
          <div className="panel-account-search-list">
            {results.map((row) => (
              <SearchResult
                key={row.userId}
                row={row}
                active={profile?.userId === row.userId}
                onSelect={loadAccount}
              />
            ))}
          </div>
        )}
      </article>

      <article className="panel-shelf panel-account-recent">
        <div className="panel-account-recent-head">
          <p className="panel-shelf-label">Последние онлайн</p>
          <button
            type="button"
            className="panel-users-btn panel-account-recent-refresh"
            onClick={loadRecent}
            disabled={recentLoading}
          >
            {recentLoading ? '…' : 'Обновить список'}
          </button>
        </div>
        {!recent.length && !recentLoading && (
          <p className="panel-shelf-muted">Сейчас никого нет в онлайне.</p>
        )}
        {recent.length > 0 && (
          <div className="panel-account-search-list">
            {recent.map((row) => (
              <SearchResult
                key={row.userId}
                row={row}
                active={profile?.userId === row.userId}
                onSelect={loadAccount}
              />
            ))}
          </div>
        )}
      </article>

      {profile && (
        <>
          <article className="panel-shelf panel-account-hero">
            <div className="panel-account-hero-left">
              <div className="panel-account-avatar" aria-hidden="true">
                {profile.photoUrl ? (
                  <img src={profile.photoUrl} alt="" />
                ) : (
                  <span>{initials(profile.displayName)}</span>
                )}
              </div>
              <div>
                <h3 className="panel-account-name">{profile.displayName}</h3>
                {profile.username && (
                  <p className="panel-account-username">@{profile.username}</p>
                )}
                <p className="panel-account-id">Telegram ID {profile.userId}</p>
                <div className="panel-account-badges">
                  {profile.onlineNow && (
                    <span className="panel-account-badge panel-account-badge-online">Online</span>
                  )}
                  {profile.banned && (
                    <span className="panel-account-badge panel-account-badge-banned">Banned</span>
                  )}
                  {telegram.isPremium && (
                    <span className="panel-account-badge panel-account-badge-premium">Premium</span>
                  )}
                </div>
                <div className="panel-account-actions">
                  <button
                    type="button"
                    className="panel-users-btn panel-account-action-btn"
                    onClick={handleRefresh}
                    disabled={loading}
                  >
                    {loading ? '…' : 'Обновить'}
                  </button>
                  <button
                    type="button"
                    className="panel-users-btn panel-account-action-btn"
                    onClick={() => handleCopy(String(profile.userId), 'ID')}
                  >
                    Копировать ID
                  </button>
                  {network.lastIp && (
                    <button
                      type="button"
                      className="panel-users-btn panel-account-action-btn"
                      onClick={() => handleCopy(network.lastIp, 'IP')}
                    >
                      Копировать IP
                    </button>
                  )}
                  {onOpenInUsers && (
                    <button
                      type="button"
                      className="panel-users-btn panel-users-btn-primary panel-account-action-btn"
                      onClick={() => onOpenInUsers(profile.userId)}
                    >
                      Открыть в Игроках
                    </button>
                  )}
                </div>
              </div>
            </div>
            <div className="panel-account-hero-stats">
              <div>
                <span className="panel-account-stat-label">КУТ</span>
                <strong>{profile.balance?.toLocaleString('ru-RU')}</strong>
              </div>
              <div>
                <span className="panel-account-stat-label">Регистрация</span>
                <strong>{formatDate(profile.createdAt)}</strong>
              </div>
              <div>
                <span className="panel-account-stat-label">Последний визит</span>
                <strong>{formatDate(profile.lastSeenAt)}</strong>
              </div>
            </div>
          </article>

          <div className="panel-account-grid">
            <article className="panel-shelf panel-account-card">
              <p className="panel-shelf-label">Telegram</p>
              <InfoRow label="Имя" value={[profile.firstName, profile.lastName].filter(Boolean).join(' ') || profile.displayName} />
              <InfoRow label="Username" value={profile.username ? `@${profile.username}` : '—'} mono />
              <InfoRow label="Язык" value={telegram.languageCode} />
              <InfoRow label="Premium" value={telegram.isPremium == null ? '—' : telegram.isPremium ? 'Да' : 'Нет'} />
              <InfoRow label="Профиль обновлён" value={formatDate(profile.profileUpdatedAt)} />
              <p className="panel-account-note">{telegram.phoneNote}</p>
            </article>

            <article className="panel-shelf panel-account-card">
              <p className="panel-shelf-label">Устройство</p>
              <InfoRow label="Платформа" value={formatPlatform(device.platform)} />
              <InfoRow label="Модель" value={device.deviceModel} />
              <InfoRow label="Версия Telegram" value={device.appVersion} mono />
              <InfoRow label="Экран" value={
                device.screenWidth && device.screenHeight
                  ? `${device.screenWidth}×${device.screenHeight}`
                  : '—'
              } />
              <InfoRow label="Viewport" value={
                device.viewportWidth && device.viewportHeight
                  ? `${device.viewportWidth}×${device.viewportHeight}`
                  : '—'
              } />
              <InfoRow label="Часовой пояс" value={device.timezone} />
              <InfoRow label="Тема" value={device.colorScheme} />
              <InfoRow label="Язык браузера" value={device.navigatorLanguage} />
              {device.userAgent && (
                <p className="panel-account-ua">{device.userAgent}</p>
              )}
              <p className="panel-account-note">
                Обновлено: {formatDate(device.updatedAt)}
              </p>
            </article>

            <article className="panel-shelf panel-account-card">
              <p className="panel-shelf-label">Сеть и аккаунт</p>
              <InfoRow label="Последний IP" value={network.lastIp} mono />
              {geoLabel && (
                <InfoRow label="Геолокация" value={geoLabel} />
              )}
              <InfoRow label="Обучение" value={profile.onboardingDone ? 'Пройдено' : 'Не пройдено'} />
              <InfoRow label="Продаж на бирже" value={String(profile.marketSalesCount ?? 0)} />
              <InfoRow label="Предметов продано" value={String(profile.marketItemsSold ?? 0)} />
              {profile.banned && (
                <>
                  <InfoRow label="Бан с" value={formatDate(profile.bannedAt)} />
                  <InfoRow label="Причина" value={profile.bannedReason || '—'} />
                </>
              )}
            </article>
          </div>

          <article className="panel-shelf panel-account-history">
            <p className="panel-shelf-label">История входов</p>
            {!profile.loginHistory?.length && (
              <p className="panel-shelf-muted">Пока нет записей — появятся после следующего входа в WebApp.</p>
            )}
            {profile.loginHistory?.length > 0 && (
              <div className="panel-account-history-list">
                {profile.loginHistory.map((row) => (
                  <LoginHistoryItem key={row.id} row={row} />
                ))}
              </div>
            )}
          </article>
        </>
      )}
    </div>
  )
}
