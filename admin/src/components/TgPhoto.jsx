import { useEffect, useRef, useState } from 'react'
import { getAdminToken, getPhotoProxyUrl } from '../lib/adminClient'

const API_PREFIX = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'
const LOCAL_FILE_RE = /^[a-f0-9]{32}\.(jpg|jpeg|png|gif|webp)$/i
const BLOB_CACHE_MAX = 48
const blobCache = new Map()

function rememberBlob(key, url) {
  if (blobCache.has(key)) blobCache.delete(key)
  blobCache.set(key, url)
  while (blobCache.size > BLOB_CACHE_MAX) {
    const oldest = blobCache.keys().next().value
    const oldUrl = blobCache.get(oldest)
    blobCache.delete(oldest)
    if (oldUrl && String(oldUrl).startsWith('blob:')) {
      try { URL.revokeObjectURL(oldUrl) } catch { /* ignore */ }
    }
  }
  return url
}

function authHeaders() {
  const token = getAdminToken()
  const headers = {
    Authorization: `Bearer ${token}`,
    'ngrok-skip-browser-warning': '1',
  }
  const initData = window.Telegram?.WebApp?.initData
  if (initData) headers['X-Telegram-Init-Data'] = initData
  return headers
}

function localUrl(fileId) {
  return `${API_PREFIX}/users/evidence/${encodeURIComponent(fileId)}`
}

function cacheKey(fileId, size) {
  return `${fileId}:${size}`
}

async function fetchAsObjectUrl(url) {
  const resp = await fetch(url, { headers: authHeaders(), credentials: 'same-origin' })
  if (resp.status === 410) {
    const err = new Error('gone')
    err.code = 'gone'
    throw err
  }
  if (resp.status === 401) {
    const err = new Error('auth')
    err.code = 'auth'
    throw err
  }
  if (!resp.ok) throw new Error('fetch failed')
  const type = resp.headers.get('content-type') || ''
  if (type.includes('text/html') || type.includes('application/json')) {
    const err = new Error('not-image')
    err.code = 'fail'
    throw err
  }
  const blob = await resp.blob()
  if (!blob || !blob.size || (blob.type && blob.type.includes('text/html'))) {
    const err = new Error('empty')
    err.code = 'fail'
    throw err
  }
  return URL.createObjectURL(blob)
}

export async function loadTgPhotoUrl(fileId, size = 'full') {
  if (!fileId) return ''
  const kind = size === 'thumb' ? 'thumb' : 'full'
  const key = cacheKey(fileId, kind)
  const cached = blobCache.get(key)
  if (cached) return cached
  if (LOCAL_FILE_RE.test(fileId)) {
    return localUrl(fileId)
  }
  const objectUrl = await fetchAsObjectUrl(getPhotoProxyUrl(fileId, kind))
  return rememberBlob(key, objectUrl)
}

export default function TgPhoto({
  fileId,
  className = '',
  style = {},
  onClick,
  size = 'full',
  lazy = true,
  alt = 'фото',
}) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(!lazy)
  const [src, setSrc] = useState(null)
  const [err, setErr] = useState('')
  const [retryTick, setRetryTick] = useState(0)

  useEffect(() => {
    if (!lazy || visible) return undefined
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') {
      setVisible(true)
      return undefined
    }
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setVisible(true)
        io.disconnect()
      }
    }, { rootMargin: '120px' })
    io.observe(el)
    return () => io.disconnect()
  }, [lazy, visible, fileId])

  useEffect(() => {
    if (!fileId || !visible) return undefined
    let objectUrl = null
    let cancelled = false
    const key = cacheKey(fileId, size)
    const kind = size === 'thumb' ? 'thumb' : 'full'

    const apply = (value, owned) => {
      if (cancelled) {
        if (owned && value) URL.revokeObjectURL(value)
        return
      }
      setErr('')
      setSrc(value)
    }

    const cached = blobCache.get(key)
    if (cached) {
      apply(cached, false)
      return undefined
    }

    const run = async () => {
      try {
        if (LOCAL_FILE_RE.test(fileId)) {
          const url = localUrl(fileId)
          if (getAdminToken()) {
            apply(url, false)
            return
          }
          objectUrl = await fetchAsObjectUrl(url)
          rememberBlob(key, objectUrl)
          apply(objectUrl, true)
          return
        }
        objectUrl = await loadTgPhotoUrl(fileId, kind)
        apply(objectUrl, true)
      } catch (exc) {
        if (!cancelled) {
          if (exc.code === 'gone') setErr('gone')
          else if (exc.code === 'auth') setErr('auth')
          else setErr('fail')
        }
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [fileId, size, visible, retryTick])

  if (!fileId) return null

  const open = async () => {
    if (!onClick) return
    if (LOCAL_FILE_RE.test(fileId)) {
      onClick(src || localUrl(fileId))
      return
    }
    try {
      const full = await loadTgPhotoUrl(fileId, 'full')
      onClick(full || src)
    } catch {
      onClick(src || getPhotoProxyUrl(fileId, 'full'))
    }
  }

  if (err) {
    return (
      <div
        ref={ref}
        className={`tg-photo-fallback ${className}`.trim()}
        style={style}
        onClick={(e) => {
          e.stopPropagation()
          setErr('')
          setRetryTick((n) => n + 1)
        }}
      >
        {err === 'gone' ? 'файл в Telegram исчез' : err === 'auth' ? 'нужен повторный вход' : 'не загрузилось · нажмите ещё раз'}
      </div>
    )
  }

  if (!src) {
    return (
      <span
        ref={ref}
        className={`tg-photo-ph ${className}`.trim()}
        style={style}
        aria-hidden="true"
      />
    )
  }

  return (
    <img
      ref={ref}
      src={src}
      alt={alt}
      className={className}
      loading={lazy ? 'lazy' : 'eager'}
      referrerPolicy="no-referrer"
      style={{
        maxWidth: '100%', maxHeight: 300, borderRadius: 8,
        objectFit: 'contain', display: 'block',
        cursor: onClick ? 'zoom-in' : 'default',
        ...style,
      }}
      onClick={onClick ? open : undefined}
      onError={() => setErr('fail')}
    />
  )
}
