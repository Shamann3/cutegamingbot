import { useCallback, useEffect, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import AdminSelect from '../../components/AdminSelect'
import {
  cancelBroadcastRun,
  countBroadcastRecipients,
  deleteBroadcastTemplate,
  fetchBroadcastHistory,
  fetchBroadcastOverview,
  fetchDailyRotationSettings,
  previewBroadcast,
  saveBroadcastTemplate,
  saveDailyRotationSettings,
  sendBroadcast,
} from '../../lib/adminClient'

const AUDIENCE_LABEL = {
  all: 'Все игроки',
  online: 'Онлайн',
  filtered: 'По фильтру',
}

function toIsoUtc(localStr) {
  if (!localStr) return null
  return new Date(localStr).toISOString()
}

function formatDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

function channelsLabel(channels) {
  const parts = []
  if (channels?.webapp) parts.push('WebApp')
  if (channels?.telegram) parts.push('Telegram')
  return parts.length ? parts.join(' + ') : '-'
}

const FAIL_REASON_LABEL = {
  blocked: 'заблокировали бота',
  chat_not_found: 'не открывали чат с ботом',
  deactivated: 'аккаунт деактивирован',
  rate_limited: 'лимит Telegram (повторить позже)',
  other: 'другая ошибка',
}

function failReasonsSummary(reasons) {
  if (!reasons || typeof reasons !== 'object') return ''
  const entries = Object.entries(reasons).filter(([, count]) => count > 0)
  if (!entries.length) return ''
  return entries
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => `${FAIL_REASON_LABEL[key] || key}: ${count}`)
    .join(' · ')
}

function formatDuration(seconds) {
  if (seconds == null) return '-'
  const value = Number(seconds)
  if (!Number.isFinite(value) || value < 0) return '-'
  if (value < 60) return `${value}с`
  const minutes = Math.floor(value / 60)
  const rest = value % 60
  if (minutes < 60) return rest ? `${minutes}м ${rest}с` : `${minutes}м`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return mins ? `${hours}ч ${mins}м` : `${hours}ч`
}

function isActiveRun(row) {
  return row?.status === 'pending' || row?.status === 'running'
}

function isCancellableRun(row) {
  return isActiveRun(row) || row?.status === 'scheduled'
}

function progressLabel(row) {
  const pct = row.progressPercent ?? 0
  if (row.status === 'done') return '100%'
  if (row.recipientCount > 0) {
    const sent = Math.max(row.telegramSent ?? 0, row.webappSent ?? 0)
    return `${pct}% · ${sent}/${row.recipientCount}`
  }
  return `${pct}%`
}

function statusLabel(status) {
  if (status === 'done') return 'Готово'
  if (status === 'running') return 'Отправка…'
  if (status === 'scheduled') return 'Запланировано'
  if (status === 'cancelled') return 'Отменено'
  if (status === 'failed') return 'Ошибка'
  return 'В очереди'
}

function statusClass(status) {
  if (status === 'done') return 'done'
  if (status === 'running') return 'running'
  if (status === 'scheduled') return 'scheduled'
  if (status === 'cancelled') return 'cancelled'
  if (status === 'failed') return 'failed'
  return 'pending'
}

function renderTelegramPreview(html) {
  if (!html) return '-'
  return html
    .replace(/<b>/gi, '')
    .replace(/<\/b>/gi, '')
    .replace(/<i>/gi, '')
    .replace(/<\/i>/gi, '')
    .replace(/<br\s*\/?>/gi, '\n')
}

function BroadcastRunCard({ row, expanded, onToggle, onCancel, cancelling }) {
  const active = isActiveRun(row)
  const cancellable = isCancellableRun(row)
  const timing = active
    ? formatDuration(row.elapsedSeconds)
    : formatDuration(row.durationSeconds)
  const pct = row.progressPercent ?? 0

  return (
    <article
      className={`panel-broadcast-run-card panel-broadcast-run-card-${statusClass(row.status)}${active ? ' panel-broadcast-run-card-active' : ''}`}
    >
      <div className="panel-broadcast-run-head">
        <div className="panel-broadcast-run-main">
          <div className="panel-broadcast-run-title-row">
            <span className="panel-broadcast-run-id">#{row.id}</span>
            <h4 className="panel-broadcast-run-title">{row.title}</h4>
            <span className={`panel-broadcast-status panel-broadcast-status-${statusClass(row.status)}`}>
              {statusLabel(row.status)}
            </span>
            {row.isDailyRotation && (
              <span className="panel-broadcast-status panel-broadcast-status-auto" title="Ежедневная авто-рассылка (напоминалка), не ручная отправка админом">
                🤖 Авто
              </span>
            )}
          </div>
          <p className="panel-shelf-muted panel-broadcast-run-meta">
            {formatDate(row.createdAt)}
            {' · '}
            {row.isDailyRotation ? 'система' : `админ ${row.adminUserId}`}
            {' · '}
            {AUDIENCE_LABEL[row.audience] || row.audience}
            {' · '}
            {channelsLabel(row.channels)}
            {row.status === 'scheduled' && row.scheduledAt && (
              <> · отправка {formatDate(row.scheduledAt)}</>
            )}
          </p>
          {row.label && <p className="panel-shelf-muted panel-broadcast-run-filter">Метка: {row.label}</p>}
          <p className="panel-shelf-muted panel-broadcast-run-filter">{row.filterSummary}</p>
        </div>
        <div className="panel-broadcast-run-actions">
          {cancellable && (
            <button
              type="button"
              className="panel-users-btn panel-users-btn-danger"
              disabled={cancelling}
              onClick={(e) => {
                e.stopPropagation()
                onCancel(row)
              }}
            >
              {cancelling ? '…' : 'Отменить'}
            </button>
          )}
          <button
            type="button"
            className="panel-users-btn"
            onClick={onToggle}
          >
            {expanded ? 'Свернуть' : 'Подробнее'}
          </button>
        </div>
      </div>

      <div className="panel-broadcast-run-stats">
        <div className="panel-broadcast-run-stat">
          <span className="panel-broadcast-run-stat-label">Получатели</span>
          <strong>{row.recipientCount?.toLocaleString('ru-RU') ?? '-'}</strong>
        </div>
        <div className="panel-broadcast-run-stat">
          <span className="panel-broadcast-run-stat-label">WebApp</span>
          <strong>{row.channels?.webapp ? row.webappSent?.toLocaleString('ru-RU') : '-'}</strong>
        </div>
        <div className="panel-broadcast-run-stat">
          <span className="panel-broadcast-run-stat-label">Telegram</span>
          <strong>
            {row.channels?.telegram ? (
              <>
                {row.telegramSent?.toLocaleString('ru-RU')}
                {row.telegramFailed > 0 && (
                  <span className="panel-broadcast-history-fail"> −{row.telegramFailed}</span>
                )}
              </>
            ) : '-'}
          </strong>
        </div>
        <div className="panel-broadcast-run-stat">
          <span className="panel-broadcast-run-stat-label">Время</span>
          <strong>{timing}</strong>
        </div>
      </div>

      <div className="panel-broadcast-run-progress-wrap">
        <div className="panel-broadcast-progress">
          <div
            className={`panel-broadcast-progress-bar${active && pct === 0 ? ' panel-broadcast-progress-bar-pulse' : ''}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="panel-broadcast-progress-label">{progressLabel(row)}</span>
      </div>

      {row.telegramFailed > 0 && failReasonsSummary(row.telegramFailedReasons) && (
        <p className="panel-shelf-muted panel-broadcast-run-fail-reasons">
          Не доставлено: {failReasonsSummary(row.telegramFailedReasons)}
        </p>
      )}

      {row.errorMessage && (
        <p className="panel-shelf-error panel-broadcast-run-error">{row.errorMessage}</p>
      )}

      {expanded && (
        <div className="panel-broadcast-history-details">
          <div className="panel-broadcast-history-details-grid">
            <div className="panel-broadcast-run-preview">
              <p className="panel-shelf-label">WebApp</p>
              <div className="panel-broadcast-preview-web">
                <p className="panel-broadcast-preview-title">{row.title}</p>
                {row.body && <p className="panel-broadcast-preview-body">{row.body}</p>}
                {row.detail && <p className="panel-broadcast-preview-detail">{row.detail}</p>}
              </div>
            </div>
            <div className="panel-broadcast-run-preview">
              <p className="panel-shelf-label">Telegram</p>
              <div className="panel-broadcast-preview-web panel-broadcast-preview-telegram-rendered">
                <pre className="panel-broadcast-preview-telegram">{renderTelegramPreview(row.telegramText)}</pre>
              </div>
            </div>
          </div>
          <p className="panel-shelf-muted">
            Админ ID {row.adminUserId}
            {row.templateKey && ` · шаблон ${row.templateKey}`}
            {row.finishedAt && ` · завершено ${formatDate(row.finishedAt)}`}
          </p>
        </div>
      )}
    </article>
  )
}

export default function BroadcastSection() {
  const [overview, setOverview] = useState(null)
  const [history, setHistory] = useState([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyStatus, setHistoryStatus] = useState('')
  const [historyOffset, setHistoryOffset] = useState(0)
  const [expandedRunId, setExpandedRunId] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [activeBroadcasts, setActiveBroadcasts] = useState(0)
  const [cancelTarget, setCancelTarget] = useState(null)
  const [cancellingId, setCancellingId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const [templateKey, setTemplateKey] = useState('')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [detail, setDetail] = useState('')
  const [telegramText, setTelegramText] = useState('')

  const [audience, setAudience] = useState('all')
  const [excludeBanned, setExcludeBanned] = useState(true)
  const [minBalance, setMinBalance] = useState('')
  const [maxBalance, setMaxBalance] = useState('')
  const [hasPlots, setHasPlots] = useState(false)
  const [usernameFilter, setUsernameFilter] = useState('')
  const [userIdsFilter, setUserIdsFilter] = useState('')

  const [channelWebapp, setChannelWebapp] = useState(true)
  const [channelTelegram, setChannelTelegram] = useState(true)

  const [scheduledAt, setScheduledAt] = useState('')

  const [recipientCount, setRecipientCount] = useState(null)
  const [countLoading, setCountLoading] = useState(false)
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const [sendOpen, setSendOpen] = useState(false)
  const [sending, setSending] = useState(false)
  const [savingTemplate, setSavingTemplate] = useState(false)
  const [templateName, setTemplateName] = useState('')

  const [rotation, setRotation] = useState(null)
  const [rotationLoading, setRotationLoading] = useState(true)
  const [rotationEnabled, setRotationEnabled] = useState(true)
  const [rotationHour, setRotationHour] = useState('12')
  const [rotationMinute, setRotationMinute] = useState('0')
  const [rotationCooldown, setRotationCooldown] = useState('2')
  const [rotationSampleRate, setRotationSampleRate] = useState('50')
  const [rotationSaving, setRotationSaving] = useState(false)

  const buildFilter = useCallback(() => {
    const filter = { excludeBanned }
    if (audience !== 'filtered') {
      return filter
    }
    if (minBalance.trim()) filter.minBalance = Number(minBalance)
    if (maxBalance.trim()) filter.maxBalance = Number(maxBalance)
    if (hasPlots) filter.hasPlots = true
    const un = usernameFilter.trim().replace(/^@/, '')
    if (un) filter.username = un
    const ids = userIdsFilter
      .split(/[\s,;]+/)
      .map((v) => Number(v.trim()))
      .filter((v) => v > 0)
    if (ids.length) filter.userIds = ids
    return filter
  }, [audience, excludeBanned, hasPlots, maxBalance, minBalance, userIdsFilter, usernameFilter])

  const buildPayload = useCallback(() => ({
    audience,
    filter: buildFilter(),
    channels: { webapp: channelWebapp, telegram: channelTelegram },
    title: title.trim(),
    body: body.trim(),
    detail: detail.trim(),
    telegramText: telegramText.trim(),
    templateKey: templateKey || null,
    scheduledAt: scheduledAt ? toIsoUtc(scheduledAt) : null,
  }), [
    audience,
    body,
    buildFilter,
    channelTelegram,
    channelWebapp,
    detail,
    scheduledAt,
    telegramText,
    templateKey,
    title,
  ])

  const loadOverview = useCallback(async () => {
    setError('')
    try {
      const data = await fetchBroadcastOverview()
      setOverview(data)
      setHistory(data.history || [])
      setHistoryTotal(data.historyTotal ?? 0)
      setActiveBroadcasts(data.activeBroadcasts ?? 0)
      setHistoryOffset(data.history?.length ?? 0)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить рассылку')
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshHistory = useCallback(async ({ append = false, offset = 0 } = {}) => {
    setHistoryLoading(true)
    try {
      const data = await fetchBroadcastHistory({
        limit: 20,
        offset,
        status: historyStatus,
      })
      setHistoryTotal(data.total ?? 0)
      setActiveBroadcasts(data.activeCount ?? 0)
      setHistory((prev) => (append ? [...prev, ...(data.items || [])] : data.items || []))
      setHistoryOffset(offset + (data.items?.length ?? 0))
    } catch (err) {
      setError(err.message || 'Не удалось загрузить историю')
    } finally {
      setHistoryLoading(false)
    }
  }, [historyStatus])

  const loadRotation = useCallback(async () => {
    setRotationLoading(true)
    try {
      const data = await fetchDailyRotationSettings()
      setRotation(data)
      setRotationEnabled(Boolean(data.enabled))
      setRotationHour(String(data.hourUtc))
      setRotationMinute(String(data.minuteUtc))
      setRotationCooldown(String(data.cooldownDays))
      setRotationSampleRate(String(Math.round(data.sampleRate * 100)))
    } catch (err) {
      setError(err.message || 'Не удалось загрузить настройки ежедневной рассылки')
    } finally {
      setRotationLoading(false)
    }
  }, [])

  useEffect(() => {
    loadOverview()
    loadRotation()
  }, [loadOverview, loadRotation])

  useEffect(() => {
    setHistoryOffset(0)
    refreshHistory({ offset: 0 })
  }, [historyStatus, refreshHistory])

  useEffect(() => {
    const hasActive = activeBroadcasts > 0 || history.some(isActiveRun)
    const intervalMs = hasActive ? 2000 : 12000
    const timer = window.setInterval(() => refreshHistory({ offset: 0 }), intervalMs)
    return () => clearInterval(timer)
  }, [activeBroadcasts, history, refreshHistory])

  const applyTemplate = (tpl) => {
    if (!tpl) return
    setTemplateKey(tpl.key || '')
    setTitle(tpl.title || '')
    setBody(tpl.body || '')
    setDetail(tpl.detail || '')
    setTelegramText(tpl.telegramText || '')
    setPreview(null)
    setRecipientCount(null)
  }

  const handlePreview = async () => {
    if (!title.trim()) {
      setError('Укажите заголовок для превью')
      return
    }
    setPreviewLoading(true)
    setError('')
    try {
      const data = await previewBroadcast({
        title: title.trim(),
        body: body.trim(),
        detail: detail.trim(),
        telegramText: telegramText.trim(),
      })
      setPreview(data)
    } catch (err) {
      setError(err.message || 'Ошибка превью')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleCount = async () => {
    setCountLoading(true)
    setError('')
    try {
      const data = await countBroadcastRecipients({
        audience,
        filter: buildFilter(),
      })
      setRecipientCount(data.count)
      return data.count
    } catch (err) {
      setError(err.message || 'Не удалось посчитать')
      setRecipientCount(null)
      return null
    } finally {
      setCountLoading(false)
    }
  }

  const confirmSend = async () => {
    if (recipientCount == null) {
      setError('Сначала посчитайте получателей')
      setSendOpen(false)
      return
    }
    if (recipientCount <= 0) {
      setError('Нет получателей для рассылки')
      setSendOpen(false)
      return
    }
    if (!channelWebapp && !channelTelegram) {
      setError('Выберите хотя бы один канал доставки')
      setSendOpen(false)
      return
    }
    setSending(true)
    setError('')
    setInfo('')
    try {
      const result = await sendBroadcast(buildPayload())
      setSendOpen(false)
      setInfo(
        scheduledAt
          ? `Рассылка #${result.runId} запланирована на ${new Date(scheduledAt).toLocaleString('ru-RU')} — ${result.recipientCount} получателей`
          : `Рассылка #${result.runId} запущена — ${result.recipientCount} получателей`,
      )
      setScheduledAt('')
      await loadOverview()
      await refreshHistory({ offset: 0 })
    } catch (err) {
      setError(err.message || 'Не удалось отправить')
    } finally {
      setSending(false)
    }
  }

  const handleSaveTemplate = async () => {
    const name = templateName.trim() || title.trim()
    if (!name) {
      setError('Укажите название шаблона')
      return
    }
    const templateMatch = templateKey?.match(/^custom:(\d+)$/)
    const templateId = templateMatch ? Number.parseInt(templateMatch[1], 10) : undefined
    setSavingTemplate(true)
    setError('')
    try {
      const tpl = await saveBroadcastTemplate({
        name,
        title: title.trim(),
        body: body.trim(),
        detail: detail.trim(),
        telegramText: telegramText.trim(),
        ...(templateId ? { templateId } : {}),
      })
      setInfo(`Шаблон «${tpl.name}» сохранён`)
      setTemplateName('')
      await loadOverview()
      applyTemplate(tpl)
    } catch (err) {
      setError(err.message || 'Не удалось сохранить шаблон')
    } finally {
      setSavingTemplate(false)
    }
  }

  const handleSaveRotation = async () => {
    const hour = Number(rotationHour)
    const minute = Number(rotationMinute)
    const cooldownDays = Number(rotationCooldown)
    const sampleRate = Number(rotationSampleRate) / 100
    if (!Number.isFinite(hour) || hour < 0 || hour > 23) {
      setError('Час должен быть от 0 до 23')
      return
    }
    if (!Number.isFinite(minute) || minute < 0 || minute > 59) {
      setError('Минута должна быть от 0 до 59')
      return
    }
    if (!Number.isFinite(cooldownDays) || cooldownDays < 1 || cooldownDays > 30) {
      setError('Кулдаун должен быть от 1 до 30 дней')
      return
    }
    if (!Number.isFinite(sampleRate) || sampleRate <= 0 || sampleRate >= 1) {
      setError('Доля выборки должна быть от 1 до 99%')
      return
    }
    setRotationSaving(true)
    setError('')
    try {
      const data = await saveDailyRotationSettings({
        enabled: rotationEnabled,
        hour,
        minute,
        cooldownDays,
        sampleRate,
      })
      setRotation(data)
      setInfo('Настройки ежедневной рассылки сохранены')
    } catch (err) {
      setError(err.message || 'Не удалось сохранить настройки')
    } finally {
      setRotationSaving(false)
    }
  }

  const handleDeleteTemplate = async (tpl) => {
    if (!tpl?.id || String(tpl.key || '').startsWith('builtin:')) return
    setError('')
    try {
      await deleteBroadcastTemplate(tpl.id)
      setInfo('Шаблон удалён')
      if (templateKey === tpl.key) setTemplateKey('')
      await loadOverview()
    } catch (err) {
      setError(err.message || 'Не удалось удалить')
    }
  }

  const confirmCancel = async () => {
    if (!cancelTarget) return
    setCancellingId(cancelTarget.id)
    setError('')
    try {
      await cancelBroadcastRun(cancelTarget.id)
      setCancelTarget(null)
      setInfo(`Рассылка #${cancelTarget.id} отменена`)
      await refreshHistory({ offset: 0 })
      await loadOverview()
    } catch (err) {
      setError(err.message || 'Не удалось отменить')
    } finally {
      setCancellingId(null)
    }
  }

  const templates = overview?.templates || []

  return (
    <div className="panel-broadcast">
      <AdminActionModal
        open={cancelTarget != null}
        title={`Отменить рассылку #${cancelTarget?.id ?? ''}?`}
        description="Отправка остановится. Уже доставленные сообщения не отзываются."
        confirmText="Отменить"
        danger
        loading={cancellingId != null}
        onConfirm={confirmCancel}
        onCancel={() => {
          if (cancellingId == null) setCancelTarget(null)
        }}
      />
      <AdminActionModal
        open={sendOpen}
        title={scheduledAt ? 'Запланировать рассылку?' : 'Отправить рассылку?'}
        description={
          recipientCount != null
            ? `Получателей: ${recipientCount}. WebApp: ${channelWebapp ? 'да' : 'нет'}, Telegram: ${channelTelegram ? 'да' : 'нет'}.`
              + (scheduledAt ? ` Отправка: ${new Date(scheduledAt).toLocaleString('ru-RU')}.` : '')
            : 'Сначала посчитайте получателей.'
        }
        confirmText={scheduledAt ? 'Запланировать' : 'Отправить'}
        danger
        loading={sending}
        onConfirm={confirmSend}
        onCancel={() => {
          if (!sending) setSendOpen(false)
        }}
      />

      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Broadcast · Рассылка</p>
        <h2 className="panel-page-title">Рассылка игрокам</h2>
        <p className="panel-page-lead">
          WebApp toast + Telegram DM через игрового бота
        </p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
      </article>

      <div className="panel-economy-stats">
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Онлайн</p>
          <p className="panel-economy-stat-value">{loading ? '…' : overview?.onlineNow ?? '—'}</p>
          <p className="panel-shelf-muted">окно {overview?.windowSeconds ?? 30}с</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Игроков</p>
          <p className="panel-economy-stat-value">{loading ? '…' : overview?.totalUsers ?? '—'}</p>
          <p className="panel-shelf-muted">не в бане</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Получатели</p>
          <p className="panel-economy-stat-value">
            {countLoading ? '…' : recipientCount ?? '—'}
          </p>
          <button type="button" className="panel-users-btn" disabled={countLoading} onClick={handleCount}>
            Посчитать
          </button>
        </article>
      </div>

      <article className="panel-shelf panel-broadcast-rotation">
        <p className="panel-shelf-label">Ежедневная авто-рассылка · напоминалки 🤖</p>
        <p className="panel-shelf-muted">
          Раз в день боту случайного набора игроков уходит одно из напоминаний
          (см. историю ниже, карточки с бейджем «🤖 Авто»). Кулдаун не даёт слать
          одному игроку чаще, чем раз в N дней; доля выборки — сколько % подходящих
          игроков получат сообщение за один запуск.
        </p>
        {rotationLoading ? (
          <p className="panel-shelf-muted">Загрузка…</p>
        ) : (
          <div className="panel-economy-settings-form">
            <label className="panel-market-check">
              <input
                type="checkbox"
                checked={rotationEnabled}
                onChange={(e) => setRotationEnabled(e.target.checked)}
              />
              Включена
            </label>
            <div className="panel-broadcast-rotation-grid">
              <label className="panel-economy-field">
                <span>Час отправки (UTC)</span>
                <input
                  className="panel-users-input"
                  value={rotationHour}
                  onChange={(e) => setRotationHour(e.target.value.replace(/[^\d]/g, ''))}
                  maxLength={2}
                />
              </label>
              <label className="panel-economy-field">
                <span>Минута</span>
                <input
                  className="panel-users-input"
                  value={rotationMinute}
                  onChange={(e) => setRotationMinute(e.target.value.replace(/[^\d]/g, ''))}
                  maxLength={2}
                />
              </label>
              <label className="panel-economy-field">
                <span>Кулдаун (дни)</span>
                <input
                  className="panel-users-input"
                  value={rotationCooldown}
                  onChange={(e) => setRotationCooldown(e.target.value.replace(/[^\d]/g, ''))}
                  maxLength={2}
                />
              </label>
              <label className="panel-economy-field">
                <span>Доля выборки (%)</span>
                <input
                  className="panel-users-input"
                  value={rotationSampleRate}
                  onChange={(e) => setRotationSampleRate(e.target.value.replace(/[^\d]/g, ''))}
                  maxLength={2}
                />
              </label>
            </div>
            <p className="panel-shelf-muted">
              Следующий запуск:{' '}
              {rotation?.nextFireAt ? formatDate(rotation.nextFireAt) : 'ещё не запланирован'}
              {' · '}
              {rotation?.templateCount ?? 0} шаблонов в ротации
            </p>
            <button
              type="button"
              className="panel-users-btn panel-users-btn-primary"
              disabled={rotationSaving}
              onClick={handleSaveRotation}
            >
              {rotationSaving ? '…' : 'Сохранить настройки'}
            </button>
          </div>
        )}
      </article>

      <div className="panel-economy-grid-2">
        <article className="panel-shelf">
          <p className="panel-shelf-label">Сообщение</p>
          <div className="panel-broadcast-templates">
            <label className="panel-economy-field">
              <span>Шаблон</span>
              <AdminSelect
                value={templateKey}
                placeholder="— свой текст —"
                onChange={(key) => {
                  setTemplateKey(key)
                  const tpl = templates.find((t) => t.key === key)
                  if (tpl) applyTemplate(tpl)
                }}
                options={[
                  { value: '', label: '— свой текст —' },
                  ...templates.map((tpl) => ({ value: tpl.key, label: tpl.name })),
                ]}
              />
            </label>
            {templateKey?.startsWith('custom:') && (
              <button
                type="button"
                className="panel-users-btn panel-users-btn-danger"
                onClick={() => {
                  const tpl = templates.find((t) => t.key === templateKey)
                  handleDeleteTemplate(tpl)
                }}
              >
                Удалить шаблон
              </button>
            )}
          </div>

          <div className="panel-economy-settings-form">
            <label className="panel-economy-field">
              <span>Заголовок (WebApp toast)</span>
              <input className="panel-users-input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} />
            </label>
            <label className="panel-economy-field">
              <span>Текст</span>
              <textarea className="panel-users-input panel-broadcast-textarea" value={body} onChange={(e) => setBody(e.target.value)} rows={3} maxLength={500} />
            </label>
            <label className="panel-economy-field">
              <span>Подпись (detail)</span>
              <input className="panel-users-input" value={detail} onChange={(e) => setDetail(e.target.value)} maxLength={300} />
            </label>
            <label className="panel-economy-field">
              <span>Telegram (HTML)</span>
              <textarea className="panel-users-input panel-broadcast-textarea" value={telegramText} onChange={(e) => setTelegramText(e.target.value)} rows={4} maxLength={2000} placeholder="<b>Заголовок</b>&#10;Текст сообщения" />
            </label>
            <p className="panel-shelf-muted">Переменные: {'{{name}}'}, {'{{username}}'}, {'{{balance}}'}</p>

            <div className="panel-broadcast-actions">
              <button type="button" className="panel-users-btn" disabled={previewLoading} onClick={handlePreview}>
                {previewLoading ? '…' : 'Превью'}
              </button>
              <input
                className="panel-users-input panel-broadcast-template-name"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="Имя шаблона"
              />
              <button type="button" className="panel-users-btn" disabled={savingTemplate} onClick={handleSaveTemplate}>
                {savingTemplate ? '…' : 'Сохранить шаблон'}
              </button>
            </div>
          </div>
        </article>

        <article className="panel-shelf panel-broadcast-preview-shelf">
          <p className="panel-shelf-label">Превью</p>
          {!preview ? (
            <p className="panel-shelf-muted">Нажмите «Превью» — покажем toast WebApp и текст Telegram.</p>
          ) : (
            <>
              <p className="panel-shelf-muted">
                Пример: {preview.sampleUser?.displayName}
                {preview.sampleUser?.username && ` @${preview.sampleUser.username}`}
                {' · '}
                {preview.sampleUser?.balance} КУТ
              </p>
              <div className="panel-broadcast-preview-web">
                <p className="panel-broadcast-preview-title">{preview.webapp?.title}</p>
                <p className="panel-broadcast-preview-body">{preview.webapp?.body}</p>
                {preview.webapp?.detail && (
                  <p className="panel-broadcast-preview-detail">{preview.webapp.detail}</p>
                )}
              </div>
              <pre className="panel-broadcast-preview-telegram">{preview.telegramHtml}</pre>
            </>
          )}
        </article>
      </div>

      <div className="panel-economy-grid-2">
        <article className="panel-shelf">
          <p className="panel-shelf-label">Аудитория</p>
          <div className="panel-broadcast-audience">
            {['all', 'online', 'filtered'].map((key) => (
              <label key={key} className="panel-market-check">
                <input type="radio" name="audience" checked={audience === key} onChange={() => setAudience(key)} />
                {AUDIENCE_LABEL[key]}
              </label>
            ))}
          </div>

          {(audience === 'filtered' || audience === 'online') && (
            <div className="panel-economy-settings-form">
              <label className="panel-market-check">
                <input type="checkbox" checked={excludeBanned} onChange={(e) => setExcludeBanned(e.target.checked)} />
                Исключить забаненных
              </label>
              {audience === 'filtered' && (
                <>
                  <label className="panel-economy-field">
                    <span>Мин. баланс КУТ</span>
                    <input className="panel-users-input" value={minBalance} onChange={(e) => setMinBalance(e.target.value.replace(/[^\d]/g, ''))} />
                  </label>
                  <label className="panel-economy-field">
                    <span>Макс. баланс КУТ</span>
                    <input className="panel-users-input" value={maxBalance} onChange={(e) => setMaxBalance(e.target.value.replace(/[^\d]/g, ''))} />
                  </label>
                  <label className="panel-market-check">
                    <input type="checkbox" checked={hasPlots} onChange={(e) => setHasPlots(e.target.checked)} />
                    Только с активными грядками
                  </label>
                  <label className="panel-economy-field">
                    <span>Username / имя</span>
                    <input className="panel-users-input" value={usernameFilter} onChange={(e) => setUsernameFilter(e.target.value)} placeholder="@nick или имя" />
                  </label>
                  <label className="panel-economy-field">
                    <span>ID игроков</span>
                    <input className="panel-users-input" value={userIdsFilter} onChange={(e) => setUserIdsFilter(e.target.value)} placeholder="123, 456" />
                  </label>
                </>
              )}
            </div>
          )}
        </article>

        <article className="panel-shelf">
          <p className="panel-shelf-label">Каналы</p>
          <div className="panel-broadcast-channels">
            <label className="panel-market-check">
              <input type="checkbox" checked={channelWebapp} onChange={(e) => setChannelWebapp(e.target.checked)} />
              WebApp — toast в игре (мгновенно если онлайн)
            </label>
            <label className="panel-market-check">
              <input type="checkbox" checked={channelTelegram} onChange={(e) => setChannelTelegram(e.target.checked)} />
              Telegram — личное сообщение от игрового бота
            </label>
          </div>
          <label className="panel-economy-field">
            <span>Запланировать на (необязательно — пусто = отправить сразу)</span>
            <input
              type="datetime-local"
              className="panel-users-input"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
            />
          </label>
          <button
            type="button"
            className="panel-users-btn panel-users-btn-primary panel-broadcast-send"
            disabled={!title.trim() || (!channelWebapp && !channelTelegram) || countLoading}
            onClick={async () => {
              const count = await handleCount()
              if (count == null) return
              if (count <= 0) {
                setError('Нет получателей для рассылки')
                return
              }
              setSendOpen(true)
            }}
          >
            {countLoading ? 'Считаем…' : scheduledAt ? 'Запланировать рассылку' : 'Отправить рассылку'}
          </button>
        </article>
      </div>

      <article className="panel-shelf">
        <div className="panel-broadcast-history-head">
          <div>
            <p className="panel-shelf-label">История</p>
            <p className="panel-shelf-muted">
              {historyTotal} рассылок
              {activeBroadcasts > 0 && ` · ${activeBroadcasts} активных`}
            </p>
          </div>
          <div className="panel-broadcast-history-tools">
            <AdminSelect
              value={historyStatus}
              onChange={setHistoryStatus}
              placeholder="Все статусы"
              options={[
                { value: '', label: 'Все статусы' },
                { value: 'running', label: 'Отправка…' },
                { value: 'pending', label: 'В очереди' },
                { value: 'scheduled', label: 'Запланировано' },
                { value: 'done', label: 'Готово' },
                { value: 'cancelled', label: 'Отменено' },
                { value: 'failed', label: 'Ошибка' },
              ]}
            />
            <button
              type="button"
              className="panel-users-btn"
              disabled={historyLoading}
              onClick={() => refreshHistory({ offset: 0 })}
            >
              {historyLoading ? '…' : 'Обновить'}
            </button>
          </div>
        </div>

        <div className="panel-broadcast-history-list">
          {history.length === 0 && !historyLoading && (
            <p className="panel-shelf-muted panel-broadcast-history-empty">Пока пусто</p>
          )}
          {history.map((row) => (
            <BroadcastRunCard
              key={row.id}
              row={row}
              expanded={expandedRunId === row.id}
              cancelling={cancellingId === row.id}
              onToggle={() => setExpandedRunId((prev) => (prev === row.id ? null : row.id))}
              onCancel={setCancelTarget}
            />
          ))}
        </div>

        {history.length < historyTotal && (
          <button
            type="button"
            className="panel-users-btn panel-broadcast-history-more"
            disabled={historyLoading}
            onClick={() => refreshHistory({ append: true, offset: historyOffset })}
          >
            {historyLoading ? '…' : `Показать ещё (${history.length}/${historyTotal})`}
          </button>
        )}
      </article>
    </div>
  )
}
