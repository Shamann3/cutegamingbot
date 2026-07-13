import { useCallback, useEffect, useRef, useState } from 'react'
import {
  claimSupportTicket,
  closeSupportTicket,
  fetchSupportStats,
  fetchSupportTicket,
  fetchSupportTickets,
  replySupportTicket,
  uploadTicketPhoto,
} from '../../lib/adminClient'
import { showToast } from '../../components/ToastHost'
import TgPhoto from '../../components/TgPhoto'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}

function timeSince(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return 'только что'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}м`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}ч`
  return `${Math.floor(diff / 86_400_000)}д`
}

function userName(t) {
  return t.firstName || (t.username ? `@${t.username}` : `ID ${t.userId}`)
}

// ---------------------------------------------------------------------------
// Thread view
// ---------------------------------------------------------------------------

function TicketThread({ ticket: initialTicket, onBack, onClosed }) {
  const [ticket, setTicket] = useState(initialTicket)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [photo, setPhoto] = useState(null)        // File | null
  const [photoPreview, setPhotoPreview] = useState(null)
  const [photoUploading, setPhotoUploading] = useState(false)
  const [photoFileId, setPhotoFileId] = useState('')
  const fileInputRef = useRef(null)
  const [claiming, setClaiming] = useState(false)
  const [closing, setClosing] = useState(false)
  const bottomRef = useRef(null)
  const messagesRef = useRef(null)
  const pollRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const data = await fetchSupportTicket(ticket.id)
      setTicket(data.ticket)
      setMessages(data.messages || [])
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [ticket.id])

  useEffect(() => {
    load()
    pollRef.current = setInterval(load, 4000)
    return () => clearInterval(pollRef.current)
  }, [load])

  useEffect(() => {
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages.length])

  const handleClaim = async () => {
    setClaiming(true)
    try {
      const res = await claimSupportTicket(ticket.id)
      setTicket((t) => ({ ...t, assignedAdminName: res.assignedAdminName }))
      showToast('Тикет взят в работу')
    } catch (err) {
      showToast(err?.message || 'Ошибка', 'error')
    } finally {
      setClaiming(false)
    }
  }

  const handleSend = async () => {
    const trimmed = text.trim()
    if (!trimmed && !photo) return
    if (sending) return
    setSending(true)
    try {
      if (photo) {
        await uploadTicketPhoto(ticket.id, photo, trimmed)
      } else {
        await replySupportTicket(ticket.id, trimmed, '')
      }
      setText('')
      setPhoto(null)
      setPhotoPreview(null)
      setPhotoFileId('')
      await load()
      showToast('Ответ отправлен')
    } catch (err) {
      showToast(err?.message || 'Ошибка', 'error')
    } finally {
      setSending(false)
    }
  }

  const handlePhotoSelect = (file) => {
    if (!file) return
    if (photoPreview) URL.revokeObjectURL(photoPreview)
    setPhoto(file)
    setPhotoPreview(URL.createObjectURL(file))
    setPhotoFileId('')
  }

  const removePhoto = () => {
    if (photoPreview) URL.revokeObjectURL(photoPreview)
    setPhoto(null)
    setPhotoPreview(null)
    setPhotoFileId('')
  }

  const handleClose = async () => {
    if (!confirm('Закрыть тикет? Пользователь получит уведомление.')) return
    setClosing(true)
    try {
      await closeSupportTicket(ticket.id)
      showToast('Тикет закрыт и отправлен в архив')
      onClosed()
    } catch (err) {
      showToast(err?.message || 'Ошибка', 'error')
    } finally {
      setClosing(false)
    }
  }

  const isOpen = ticket.status === 'open'
  const isClaimed = Boolean(ticket.assignedAdminName)

  // Экран обязательного взятия тикета
  if (isOpen && !isClaimed) {
    return (
      <div className="support-thread-wrap support-claim-wall">
        <div className="support-thread-header">
          <button className="sec-btn sec-btn-ghost sec-btn-sm" onClick={onBack}>← Назад</button>
          <div className="support-thread-title">
            <span className="support-thread-name">{userName(ticket)}</span>
            {ticket.username && <span className="support-thread-sub">@{ticket.username}</span>}
            {ticket.subject && <span className="support-thread-sub">· {ticket.subject}</span>}
            <span className="staff-badge support-badge-open" style={{ '--badge-color': '#34d399' }}>
              открыт
            </span>
          </div>
        </div>

        {/* Превью первых сообщений (readonly) */}
        <div className="support-messages support-messages-preview">
          {loading && <p className="sec-loading">Загрузка…</p>}
          {messages.slice(0, 3).map((msg) => (
            <div key={msg.id} className={`support-msg ${msg.fromUser ? 'support-msg-user' : 'support-msg-admin'}`}>
              <div className="support-msg-bubble">
                <p className="support-msg-text">{msg.text}</p>
                <span className="support-msg-time">{fmtDate(msg.createdAt)}</span>
              </div>
            </div>
          ))}
          {!loading && messages.length > 3 && (
            <p className="support-preview-more">… ещё {messages.length - 3} сообщ.</p>
          )}
        </div>

        {/* Блок взятия */}
        <div className="support-claim-block">
          <p className="support-claim-hint">
            Чтобы ответить — возьмите тикет в работу. Это зафиксируется в логах.
          </p>
          <button
            className="support-claim-btn"
            disabled={claiming}
            onClick={handleClaim}
          >
            {claiming ? '…' : '✋ Взять тикет в работу'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="support-thread-wrap">
      {/* Header */}
      <div className="support-thread-header">
        <button className="sec-btn sec-btn-ghost sec-btn-sm" onClick={onBack}>← Назад</button>
        <div className="support-thread-title">
          <span className="support-thread-name">{userName(ticket)}</span>
          {ticket.username && <span className="support-thread-sub">@{ticket.username}</span>}
          {ticket.subject && <span className="support-thread-sub">· {ticket.subject}</span>}
          <span
            className={`staff-badge ${isOpen ? 'support-badge-open' : ''}`}
            style={{ '--badge-color': isOpen ? '#34d399' : '#94a3b8' }}
          >
            {isOpen ? 'открыт' : 'архив'}
          </span>
          {isClaimed && (
            <span className="staff-badge" style={{ '--badge-color': '#a78bfa' }}>
              ✋ {ticket.assignedAdminName}
            </span>
          )}
        </div>
        {isOpen && (
          <div className="support-thread-actions">
            <button className="sec-btn sec-btn-sm" disabled={closing} onClick={handleClose}>
              {closing ? '…' : '🔒 Закрыть'}
            </button>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="support-messages" ref={messagesRef}>
        {loading && <p className="sec-loading">Загрузка…</p>}
        {messages.map((msg) => {
          const side = msg.isSystem ? 'support-msg-system' : (msg.fromUser ? 'support-msg-user' : 'support-msg-admin')
          return (
            <div key={msg.id} className={`support-msg ${side}`}>
              <div className="support-msg-bubble">
                {!msg.fromUser && !msg.isSystem && msg.adminName && (
                  <span className="support-msg-sender">{msg.adminName}</span>
                )}
                {msg.photoFileId && (
                  <TgPhoto fileId={msg.photoFileId} onClick style={{ marginBottom: msg.text ? 6 : 0 }} />
                )}
                {msg.text && (
                  <p className="support-msg-text">
                    {msg.isSystem ? msg.text.replace(/<[^>]+>/g, '') : msg.text}
                  </p>
                )}
                <span className="support-msg-time">{fmtDate(msg.createdAt)}</span>
              </div>
            </div>
          )
        })}
        {!loading && messages.length === 0 && <p className="sec-empty">Сообщений нет</p>}
        <div ref={bottomRef} />
      </div>

      {/* Reply */}
      {isOpen && (
        <div className="support-reply-box">
          <div className="support-reply-inner">
            {/* Превью фото */}
            {photoPreview && (
              <div className="support-reply-photo-wrap">
                <img src={photoPreview} alt="" className="support-reply-photo" />
                {photoUploading
                  ? <div className="support-reply-photo-spin" />
                  : photoFileId
                    ? <div className="support-reply-photo-ok">✓</div>
                    : null
                }
                <button className="support-reply-photo-remove" onClick={removePhoto} disabled={sending}>✕</button>
              </div>
            )}
            <textarea
              className="support-reply-input"
              placeholder={photo ? 'Подпись к фото (необязательно)…' : 'Ваш ответ… (Enter — отправить, Shift+Enter — новая строка)'}
              rows={photo ? 2 : 3}
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={sending}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault(); // Предотвращаем перенос строки при простом нажатии Enter
                  handleSend();
                }
                // Если нажат Shift+Enter, сработает стандартное поведение (перенос строки)
              }}
            />
          </div>
          <div className="support-reply-actions">
            <div className="support-reply-left">
              <button
                className="support-reply-attach-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={sending || !!photo}
                title="Прикрепить фото"
              >
                📎
              </button>
              <span className="support-reply-hint">Ответ придёт в бот</span>
            </div>
            <button
              className="support-reply-send-btn"
              disabled={(!text.trim() && !photo) || sending}
              onClick={handleSend}
            >
              {sending ? '…' : 'Отправить'}
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handlePhotoSelect(f); e.target.value = '' }}
          />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Ticket list
// ---------------------------------------------------------------------------

const FILTERS = [
  { id: 'open',   label: 'Открытые' },
  { id: 'closed', label: 'Архив' },
]

function TicketList({ onSelect, selectedId, reload }) {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('open')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchSupportTickets(filter)
      setTickets(data.tickets || [])
    } catch { setTickets([]) } finally { setLoading(false) }
  }, [filter])

  useEffect(() => { load() }, [load, reload])

  // Авто-обновление списка каждые 8 секунд
  useEffect(() => {
    const id = setInterval(load, 8000)
    return () => clearInterval(id)
  }, [load])

  return (
    <div className="support-list-wrap">
      <div className="sec-audit-filters">
        <div className="sec-tabs">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              className={`sec-tab ${filter === f.id ? 'sec-tab-active' : ''}`}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button className="sec-btn sec-btn-ghost" onClick={load}>↻</button>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="support-ticket-list">
        {tickets.map((t) => (
          <button
            key={t.id}
            className={`support-ticket-row${selectedId === t.id ? ' support-ticket-row-active' : ''}`}
            onClick={() => onSelect(t)}
          >
            <div className="support-ticket-row-top">
              <span className="support-ticket-name">{userName(t)}</span>
              {t.unread > 0 && (
                <span className="support-unread-badge">{t.unread}</span>
              )}
              <span className="support-ticket-time">{timeSince(t.updatedAt)}</span>
            </div>
            {t.subject && <span className="support-ticket-subject">{t.subject}</span>}
            {t.assignedAdminName && (
              <span className="support-ticket-claimed">✋ {t.assignedAdminName}</span>
            )}
            <p className="support-ticket-preview">
              {t.lastFromUser === false && '→ '}
              {t.lastText
                ? (t.lastText.length > 80 ? t.lastText.slice(0, 80) + '…' : t.lastText)
                : 'Нет сообщений'}
            </p>
          </button>
        ))}
        {!loading && tickets.length === 0 && (
          <p className="sec-empty">{filter === 'open' ? 'Нет открытых обращений' : 'Архив пуст'}</p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main section
// ---------------------------------------------------------------------------

export default function SupportSection() {
  const [selected, setSelected] = useState(null)
  const [reload, setReload] = useState(0)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    const load = () => fetchSupportStats().then(setStats).catch(() => {})
    load()
    const id = setInterval(load, 10_000)
    return () => clearInterval(id)
  }, [reload])

  const handleClosed = () => {
    setSelected(null)
    setReload((r) => r + 1)
  }

  return (
    <div className="panel-shelf support-section">
      <div className="support-section-header">
        <h2 className="sec-title">Поддержка</h2>
        {stats?.openTickets > 0 && (
          <span className="staff-badge staff-badge-pulse" style={{ '--badge-color': '#fbbf24' }}>
            {stats.openTickets} открытых
          </span>
        )}
      </div>

      <div className={`support-layout${selected ? ' support-layout-thread-open' : ''}`}>
        <TicketList
          onSelect={setSelected}
          selectedId={selected?.id}
          reload={reload}
        />
        {selected ? (
          <TicketThread
            key={selected.id}
            ticket={selected}
            onBack={() => setSelected(null)}
            onClosed={handleClosed}
          />
        ) : (
          <div className="support-empty-state">
            <span className="support-empty-icon">💬</span>
            <p>Выберите обращение слева</p>
          </div>
        )}
      </div>
    </div>
  )
}
