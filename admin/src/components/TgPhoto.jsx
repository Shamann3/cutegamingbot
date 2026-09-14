import { useEffect, useRef, useState } from 'react'
import { getAdminToken, getPhotoProxyUrl } from '../lib/adminClient'

const API_PREFIX = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'
const LOCAL_FILE_RE = /^[a-f0-9]{32}\.(jpg|jpeg|png|gif|webp)$/i
const blobCache = new Map()

function authHeaders() {
  const token = getAdminToken()
  const headers = { Authorization: `Bearer ${token}` }
  if (import.meta.env.DEV) headers['ngrok-skip-browser-warning'] = '1'
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
  const resp = await fetch(url, { headers: authHeaders() })
  if (resp.status === 410) {
    const err = new Error('gone')
    err.code = 'gone'
    throw err
  }
  if (!resp.ok) throw new Error('fetch failed')
  const blob = await resp.blob()
  return URL.createObjectURL(blob)
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
          const token = getAdminToken()
          if (token) {
            apply(url, false)
            return
          }
          objectUrl = await fetchAsObjectUrl(url)
          blobCache.set(key, objectUrl)
          apply(objectUrl, true)
          return
        }

        const token = getAdminToken()
        const proxyUrl = getPhotoProxyUrl(fileId, kind)
        if (token) {
          apply(proxyUrl, false)
          return
        }
        objectUrl = await fetchAsObjectUrl(`${API_PREFIX}/photo-proxy?file_id=${encodeURIComponent(fileId)}&size=${kind}`)
        blobCache.set(key, objectUrl)
        apply(objectUrl, true)
      } catch (exc) {
        if (!cancelled) setErr(exc.code === 'gone' ? 'gone' : 'fail')
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [fileId, size, visible, retryTick])

  if (!fileId) return null

  const open = () => {
    if (!onClick) return
    if (LOCAL_FILE_RE.test(fileId)) {
      onClick(src || localUrl(fileId))
      return
    }
    onClick(getPhotoProxyUrl(fileId, 'full') || src)
  }

  if (err) {
    return (
      <button
        ref={ref}
        type="button"
        className={`tg-photo-fallback ${className}`.trim()}
        style={style}
        onClick={() => { setErr(''); setRetryTick((n) => n + 1) }}
      >
        {err === 'gone' ? 'файл в Telegram исчез' : 'не загрузилось · нажми ещё раз'}
      </button>
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
