import { useCallback, useEffect, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import {
  createGroupPostCampaign,
  deleteGroupPostCampaign,
  fetchGroupPostCampaignLog,
  fetchGroupPostCampaignPhotoBlob,
  fetchGroupPostCampaigns,
  fetchKnownChats,
  pauseGroupPostCampaign,
  resumeGroupPostCampaign,
  runGroupPostCampaignNow,
  updateGroupPostCampaign,
} from '../../lib/adminClient'

const FAIL_REASON_LABEL = {
  blocked: 'бота удалили/кикнули из группы',
  chat_not_found: 'группа не найдена',
  deactivated: 'группа недоступна',
  rate_limited: 'лимит Telegram (повторится позже)',
  other: 'другая ошибка',
}

function formatDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

function ButtonsBuilder({ rows, onChange }) {
  const updateRow = (rowIdx, nextRow) => {
    onChange(rows.map((row, i) => (i === rowIdx ? nextRow : row)))
  }
  const addRow = () => onChange([...rows, [{ text: '', url: '', type: 'url' }]])
  const removeRow = (rowIdx) => onChange(rows.filter((_, i) => i !== rowIdx))
  const addButton = (rowIdx) => updateRow(rowIdx, [...rows[rowIdx], { text: '', url: '', type: 'url' }])
  const removeButton = (rowIdx, btnIdx) => updateRow(rowIdx, rows[rowIdx].filter((_, i) => i !== btnIdx))
  const updateButton = (rowIdx, btnIdx, field, value) => {
    updateRow(rowIdx, rows[rowIdx].map((btn, i) => (i === btnIdx ? { ...btn, [field]: value } : btn)))
  }

  return (
    <div className="panel-grouppost-buttons">
      {rows.map((row, rowIdx) => (
        <div key={rowIdx} className="panel-grouppost-button-row">
          {row.map((btn, btnIdx) => (
            <div key={btnIdx} className="panel-grouppost-button">
              <input
                className="panel-users-input"
                placeholder="Текст кнопки"
                value={btn.text}
                onChange={(e) => updateButton(rowIdx, btnIdx, 'text', e.target.value)}
              />
              <input
                className="panel-users-input"
                placeholder="https://..."
                value={btn.url}
                onChange={(e) => updateButton(rowIdx, btnIdx, 'url', e.target.value)}
              />
              <select
                className="panel-users-input"
                value={btn.type}
                onChange={(e) => updateButton(rowIdx, btnIdx, 'type', e.target.value)}
              >
                <option value="url">Ссылка</option>
                <option value="web_app">WebApp</option>
              </select>
              <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => removeButton(rowIdx, btnIdx)}>
                ✕
              </button>
            </div>
          ))}
          <div className="panel-grouppost-row-actions">
            <button type="button" className="panel-users-btn panel-users-btn-sm" onClick={() => addButton(rowIdx)}>
              + кнопка в ряд
            </button>
            <button type="button" className="panel-users-btn panel-users-btn-sm panel-users-btn-danger" onClick={() => removeRow(rowIdx)}>
              Убрать ряд
            </button>
          </div>
        </div>
      ))}
      <button type="button" className="panel-users-btn" onClick={addRow}>
        + новый ряд кнопок
      </button>
    </div>
  )
}

function ChatPicker({ selectedIds, onChange }) {
  const [chats, setChats] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [manualId, setManualId] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchKnownChats()
      .then((data) => { if (!cancelled) setChats(data.items || []) })
      .catch((err) => { if (!cancelled) setError(err.message || 'Не удалось загрузить группы') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const toggle = (chatId) => {
    onChange(
      selectedIds.includes(chatId)
        ? selectedIds.filter((id) => id !== chatId)
        : [...selectedIds, chatId],
    )
  }

  const addManual = () => {
    const id = Number(manualId.trim())
    if (!Number.isFinite(id) || id === 0) return
    if (!selectedIds.includes(id)) onChange([...selectedIds, id])
    setManualId('')
  }

  const query = search.trim().toLowerCase()
  const filtered = query
    ? chats.filter((c) => (c.name || '').toLowerCase().includes(query) || String(c.chatId).includes(query))
    : chats

  const knownIds = new Set(chats.map((c) => c.chatId))
  const manualSelected = selectedIds.filter((id) => !knownIds.has(id))

  const selectAll = () => {
    const filteredIds = filtered.map((c) => c.chatId)
    onChange([...new Set([...selectedIds, ...filteredIds])])
  }
  const clearAll = () => onChange([])

  return (
    <div className="panel-grouppost-chatpicker">
      <div className="panel-grouppost-chatpicker-toolbar">
        <input
          className="panel-users-input"
          placeholder="Поиск группы по названию или ID"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button type="button" className="panel-users-btn panel-users-btn-sm" disabled={loading || filtered.length === 0} onClick={selectAll}>
          Выбрать все{query ? ' (найденные)' : ''}
        </button>
        <button type="button" className="panel-users-btn panel-users-btn-sm panel-users-btn-danger" disabled={selectedIds.length === 0} onClick={clearAll}>
          Снять все
        </button>
      </div>
      {loading && <p className="panel-shelf-muted">Загрузка групп…</p>}
      {error && <p className="panel-shelf-error">{error}</p>}
      {!loading && !error && (
        <div className="panel-grouppost-chatpicker-list">
          {filtered.length === 0 && <p className="panel-shelf-muted">Ничего не найдено</p>}
          {filtered.map((c) => (
            <label key={c.chatId} className="panel-market-check panel-grouppost-chatpicker-item">
              <input type="checkbox" checked={selectedIds.includes(c.chatId)} onChange={() => toggle(c.chatId)} />
              <span>{c.name || `Группа ${c.chatId}`}</span>
              <span className="panel-shelf-muted"> · ID {c.chatId}</span>
            </label>
          ))}
        </div>
      )}
      {manualSelected.length > 0 && (
        <div className="panel-grouppost-chatpicker-manual-list">
          {manualSelected.map((id) => (
            <span key={id} className="panel-grouppost-chip">
              ID {id}
              <button type="button" onClick={() => toggle(id)}>✕</button>
            </span>
          ))}
        </div>
      )}
      <div className="panel-grouppost-chatpicker-add">
        <input
          className="panel-users-input"
          placeholder="Добавить group ID вручную (если группы нет в списке)"
          value={manualId}
          onChange={(e) => setManualId(e.target.value.replace(/[^\d-]/g, ''))}
        />
        <button type="button" className="panel-users-btn panel-users-btn-sm" onClick={addManual}>
          + добавить
        </button>
      </div>
      <p className="panel-shelf-muted">Выбрано групп: {selectedIds.length}</p>
    </div>
  )
}

function CampaignLog({ campaignId }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)

  const load = useCallback(async ({ append = false, offset = 0 } = {}) => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchGroupPostCampaignLog(campaignId, { limit: 50, offset })
      setTotal(data.total ?? 0)
      setItems((prev) => (append ? [...prev, ...(data.items || [])] : data.items || []))
      setLoaded(true)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить историю')
    } finally {
      setLoading(false)
    }
  }, [campaignId])

  useEffect(() => {
    if (!loaded && !loading) load({ offset: 0 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, loading])

  return (
    <div className="panel-grouppost-log">
      {error && <p className="panel-shelf-error">{error}</p>}
      {loading && items.length === 0 && <p className="panel-shelf-muted">Загрузка…</p>}
      {!loading && loaded && items.length === 0 && <p className="panel-shelf-muted">Пока пусто</p>}
      {items.length > 0 && (
        <ul className="panel-broadcast-recipients-list">
          {items.map((item, i) => (
            <li key={`${item.chatId}-${item.createdAt}-${i}`} className="panel-broadcast-recipient-row">
              <span className="panel-broadcast-recipient-name">Группа {item.chatId}</span>
              <span className="panel-shelf-muted">{formatDate(item.createdAt)}</span>
              <span className={`panel-broadcast-recipient-status panel-broadcast-recipient-status-${item.status}`}>
                {item.status === 'sent' ? 'Доставлено' : 'Ошибка'}
                {item.failReason && ` · ${FAIL_REASON_LABEL[item.failReason] || item.failReason}`}
              </span>
            </li>
          ))}
        </ul>
      )}
      {items.length < total && (
        <button
          type="button"
          className="panel-users-btn panel-broadcast-recipients-more"
          disabled={loading}
          onClick={() => load({ append: true, offset: items.length })}
        >
          {loading ? '…' : `Показать ещё (${items.length}/${total})`}
        </button>
      )}
    </div>
  )
}

function CampaignCard({ campaign, onEdit, onPause, onResume, onDelete, onRunNow, busy, expanded, onToggle }) {
  return (
    <article className={`panel-broadcast-run-card panel-broadcast-run-card-${campaign.status === 'active' ? 'running' : 'pending'}`}>
      <div className="panel-broadcast-run-head">
        <div className="panel-broadcast-run-main">
          <div className="panel-broadcast-run-title-row">
            <span className="panel-broadcast-run-id">#{campaign.id}</span>
            <h4 className="panel-broadcast-run-title">{campaign.label || `Кампания #${campaign.id}`}</h4>
            <span className={`panel-broadcast-status panel-broadcast-status-${campaign.status === 'active' ? 'running' : 'cancelled'}`}>
              {campaign.status === 'active' ? 'Активна' : 'На паузе'}
            </span>
          </div>
          <p className="panel-shelf-muted panel-broadcast-run-meta">
            {campaign.chatIds.length} {campaign.chatIds.length === 1 ? 'группа' : 'групп'}
            {' · '}каждые {campaign.intervalMinutes} мин
            {' · '}отправлено {campaign.totalSent} раз
            {campaign.nextFireAt && ` · след. отправка ${formatDate(campaign.nextFireAt)}`}
          </p>
          {campaign.lastError && <p className="panel-shelf-error">{campaign.lastError}</p>}
        </div>
        <div className="panel-broadcast-run-actions">
          {campaign.status === 'active' ? (
            <button type="button" className="panel-users-btn" disabled={busy} onClick={() => onPause(campaign)}>Пауза</button>
          ) : (
            <button type="button" className="panel-users-btn" disabled={busy} onClick={() => onResume(campaign)}>Возобновить</button>
          )}
          <button type="button" className="panel-users-btn" disabled={busy} onClick={() => onRunNow(campaign)}>▶ Сейчас</button>
          <button type="button" className="panel-users-btn" disabled={busy} onClick={() => onEdit(campaign)}>Изменить</button>
          <button type="button" className="panel-users-btn panel-users-btn-danger" disabled={busy} onClick={() => onDelete(campaign)}>Удалить</button>
          <button type="button" className="panel-users-btn" onClick={onToggle}>{expanded ? 'Свернуть' : 'История'}</button>
        </div>
      </div>
      {expanded && (
        <div className="panel-broadcast-history-details">
          <p className="panel-shelf-label">Текст поста</p>
          <pre className="panel-broadcast-preview-telegram">{campaign.telegramText || '(пусто, только фото)'}</pre>
          {campaign.hasPhoto && <p className="panel-shelf-muted">📷 Фото прикреплено</p>}
          <p className="panel-shelf-label">История отправок</p>
          <CampaignLog campaignId={campaign.id} />
        </div>
      )}
    </article>
  )
}

const emptyForm = {
  label: '',
  chatIds: [],
  telegramText: '',
  buttons: [],
  intervalMinutes: '10',
  photoFile: null,
  clearPhoto: false,
  existingHasPhoto: false,
}

export default function GroupPostsPanel() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [expandedId, setExpandedId] = useState(null)

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const data = await fetchGroupPostCampaigns()
      setCampaigns(data.items || [])
    } catch (err) {
      setError(err.message || 'Не удалось загрузить кампании')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyForm)
    setFormOpen(true)
  }

  const openEdit = (campaign) => {
    setEditingId(campaign.id)
    setForm({
      label: campaign.label,
      chatIds: campaign.chatIds,
      telegramText: campaign.telegramText,
      buttons: campaign.buttons,
      intervalMinutes: String(campaign.intervalMinutes),
      photoFile: null,
      clearPhoto: false,
      existingHasPhoto: campaign.hasPhoto,
    })
    setFormOpen(true)
  }

  const [photoPreviewUrl, setPhotoPreviewUrl] = useState('')
  const [photoPreviewLoading, setPhotoPreviewLoading] = useState(false)

  useEffect(() => {
    let revokeUrl = null
    let cancelled = false

    if (form.photoFile) {
      const url = URL.createObjectURL(form.photoFile)
      revokeUrl = url
      setPhotoPreviewUrl(url)
    } else if (editingId && form.existingHasPhoto && !form.clearPhoto) {
      setPhotoPreviewLoading(true)
      fetchGroupPostCampaignPhotoBlob(editingId)
        .then((blob) => {
          if (cancelled) return
          const url = URL.createObjectURL(blob)
          revokeUrl = url
          setPhotoPreviewUrl(url)
        })
        .catch(() => { if (!cancelled) setPhotoPreviewUrl('') })
        .finally(() => { if (!cancelled) setPhotoPreviewLoading(false) })
    } else {
      setPhotoPreviewUrl('')
    }

    return () => {
      cancelled = true
      if (revokeUrl) URL.revokeObjectURL(revokeUrl)
    }
  }, [form.photoFile, form.clearPhoto, form.existingHasPhoto, editingId])

  const handleRemovePhoto = () => {
    if (form.photoFile) {
      setForm({ ...form, photoFile: null })
    } else {
      setForm({ ...form, clearPhoto: true })
    }
  }

  const handleSave = async () => {
    const interval = Number(form.intervalMinutes)
    if (!Number.isFinite(interval) || interval < 1) {
      setError('Интервал должен быть не меньше 1 минуты')
      return
    }
    if (form.chatIds.length === 0) {
      setError('Укажите хотя бы одну группу')
      return
    }
    setSaving(true)
    setError('')
    try {
      if (editingId) {
        await updateGroupPostCampaign(editingId, {
          label: form.label,
          chatIds: form.chatIds.join(','),
          telegramText: form.telegramText,
          buttons: form.buttons,
          intervalMinutes: interval,
          photoFile: form.photoFile,
          clearPhoto: form.clearPhoto,
        })
        setInfo('Кампания обновлена')
      } else {
        await createGroupPostCampaign({
          label: form.label,
          chatIds: form.chatIds.join(','),
          telegramText: form.telegramText,
          buttons: form.buttons,
          intervalMinutes: interval,
          photoFile: form.photoFile,
        })
        setInfo('Кампания создана')
      }
      setFormOpen(false)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось сохранить кампанию')
    } finally {
      setSaving(false)
    }
  }

  const handlePause = async (campaign) => {
    setBusyId(campaign.id)
    setError('')
    try {
      await pauseGroupPostCampaign(campaign.id)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось поставить на паузу')
    } finally {
      setBusyId(null)
    }
  }

  const handleResume = async (campaign) => {
    setBusyId(campaign.id)
    setError('')
    try {
      await resumeGroupPostCampaign(campaign.id)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось возобновить')
    } finally {
      setBusyId(null)
    }
  }

  const handleRunNow = async (campaign) => {
    setBusyId(campaign.id)
    setError('')
    setInfo('')
    try {
      const result = await runGroupPostCampaignNow(campaign.id)
      setInfo(`Отправлено сейчас: успешно ${result.sent}, ошибок ${result.failed}`)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось отправить')
    } finally {
      setBusyId(null)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    setError('')
    try {
      await deleteGroupPostCampaign(deleteTarget.id)
      setDeleteTarget(null)
      setInfo('Кампания удалена')
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось удалить')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="panel-broadcast">
      <AdminActionModal
        open={deleteTarget != null}
        title={`Удалить кампанию «${deleteTarget?.label || deleteTarget?.id}»?`}
        description="Циклическая отправка остановится немедленно. Действие необратимо."
        confirmText="Удалить"
        danger
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => { if (!deleting) setDeleteTarget(null) }}
      />

      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Group Posts · Посты в группы</p>
        <h2 className="panel-page-title">Циклические посты в группы</h2>
        <p className="panel-page-lead">Текст + фото + кнопки, на повторяющемся интервале, в выбранные chat_id</p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
        <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={openCreate}>
          + Новая кампания
        </button>
      </article>

      {formOpen && (
        <article className="panel-shelf">
          <p className="panel-shelf-label">{editingId ? `Кампания #${editingId}` : 'Новая кампания'}</p>
          <div className="panel-economy-settings-form">
            <label className="panel-economy-field">
              <span>Название (для себя)</span>
              <input className="panel-users-input" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} maxLength={120} />
            </label>
            <label className="panel-economy-field">
              <span>Группы</span>
              <ChatPicker selectedIds={form.chatIds} onChange={(chatIds) => setForm({ ...form, chatIds })} />
            </label>
            <label className="panel-economy-field">
              <span>Текст поста (HTML)</span>
              <textarea className="panel-users-input panel-broadcast-textarea" value={form.telegramText} onChange={(e) => setForm({ ...form, telegramText: e.target.value })} rows={4} maxLength={2000} />
            </label>
            <label className="panel-economy-field">
              <span>Фото (необязательно)</span>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setForm({ ...form, photoFile: e.target.files?.[0] || null, clearPhoto: false })}
              />
            </label>
            {photoPreviewLoading && <p className="panel-shelf-muted">Загрузка превью…</p>}
            {photoPreviewUrl && (
              <div className="panel-grouppost-photo-preview">
                <img src={photoPreviewUrl} alt="Превью фото поста" />
                <button type="button" className="panel-users-btn panel-users-btn-danger panel-users-btn-sm" onClick={handleRemovePhoto}>
                  ✕ Убрать фото
                </button>
              </div>
            )}
            <label className="panel-economy-field">
              <span>Кнопки</span>
              <ButtonsBuilder rows={form.buttons} onChange={(buttons) => setForm({ ...form, buttons })} />
            </label>
            <label className="panel-economy-field">
              <span>Интервал (минуты)</span>
              <input className="panel-users-input" value={form.intervalMinutes} onChange={(e) => setForm({ ...form, intervalMinutes: e.target.value.replace(/[^\d]/g, '') })} maxLength={6} />
            </label>
            <div className="panel-broadcast-rotation-actions">
              <button type="button" className="panel-users-btn panel-users-btn-primary" disabled={saving} onClick={handleSave}>
                {saving ? '…' : editingId ? 'Сохранить изменения' : 'Создать кампанию'}
              </button>
              <button type="button" className="panel-users-btn" disabled={saving} onClick={() => setFormOpen(false)}>
                Отмена
              </button>
            </div>
          </div>
        </article>
      )}

      <article className="panel-shelf">
        <p className="panel-shelf-label">Кампании</p>
        {loading && <p className="panel-shelf-muted">Загрузка…</p>}
        {!loading && campaigns.length === 0 && <p className="panel-shelf-muted">Пока нет кампаний</p>}
        <div className="panel-broadcast-history-list">
          {campaigns.map((campaign) => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              busy={busyId === campaign.id}
              expanded={expandedId === campaign.id}
              onToggle={() => setExpandedId((prev) => (prev === campaign.id ? null : campaign.id))}
              onEdit={openEdit}
              onPause={handlePause}
              onResume={handleResume}
              onRunNow={handleRunNow}
              onDelete={setDeleteTarget}
            />
          ))}
        </div>
      </article>
    </div>
  )
}
