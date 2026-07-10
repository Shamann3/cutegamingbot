import { useEffect, useState } from 'react'
import { getAdminToken } from '../lib/adminClient'

const API_PREFIX = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'

// Локальные файлы сохранённые через /users/upload-evidence
const LOCAL_FILE_RE = /^[a-f0-9]{32}\.(jpg|jpeg|png|gif|webp)$/i

export default function TgPhoto({ fileId, className = '', style = {}, onClick }) {
  const [src, setSrc] = useState(null)
  const [err, setErr] = useState(false)

  useEffect(() => {
    if (!fileId) return
    let objectUrl = null
    let cancelled = false

    const token = getAdminToken()
    const headers = { Authorization: `Bearer ${token}` }
    if (import.meta.env.DEV) headers['ngrok-skip-browser-warning'] = '1'

    const initData = window.Telegram?.WebApp?.initData
    if (initData) headers['X-Telegram-Init-Data'] = initData

    // Выбираем URL в зависимости от типа файла
    const url = LOCAL_FILE_RE.test(fileId)
      ? `${API_PREFIX}/users/evidence/${encodeURIComponent(fileId)}`
      : `${API_PREFIX}/photo-proxy?file_id=${encodeURIComponent(fileId)}`

    fetch(url, { headers })
      .then(async (resp) => {
        if (!resp.ok) throw new Error('fetch failed')
        const blob = await resp.blob()
        objectUrl = URL.createObjectURL(blob)
        if (!cancelled) setSrc(objectUrl)
      })
      .catch(() => { if (!cancelled) setErr(true) })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [fileId])

  if (!fileId) return null
  if (err) return <span style={{ fontSize: 11, color: '#4b5563' }}>📷 фото недоступно</span>
  if (!src) return <span style={{ fontSize: 11, color: '#6b7280' }}>📷 загрузка...</span>

  return (
    <img
      src={src}
      alt="фото"
      className={className}
      style={{
        maxWidth: '100%', maxHeight: 300, borderRadius: 8,
        objectFit: 'contain', display: 'block',
        cursor: onClick ? 'zoom-in' : 'default',
        ...style,
      }}
      onClick={onClick ? () => window.open(src, '_blank') : undefined}
    />
  )
}
