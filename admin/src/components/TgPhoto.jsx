import { useEffect, useRef, useState } from 'react'
import { getAdminToken, getPhotoProxyUrl } from '../lib/adminClient'

const API_PREFIX = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'
const LOCAL_FILE_RE = /^[a-f0-9]{32}\.(jpg|jpeg|png|gif|webp)$/i
const BLOB_CACHE_MAX = 48
const blobCache = new Map()
const inflight = new Map()

function rememberBlob(key, url) {
  if (blobCache.has(key)) blobCache.delete(key)
  blobCache.set(key, url)
  while (blobCache.size > BLOB_CACHE_MAX) {
    const oldest = blobCache.keys().next().value
    blobCache.delete(oldest)
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

export function sniffImageType(bytes, headerType = '') {
  const declared = String(headerType || '').split(';')[0].trim().toLowerCase()
  if (declared.startsWith('image/') && declared !== 'image/svg+xml') return declared
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'image/jpeg'
  if (bytes.length >= 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) return 'image/png'
  if (bytes.length >= 6 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46) return 'image/gif'
  if (
    bytes.length >= 12
    && bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46
    && bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50
  ) return 'image/webp'
  return ''
}

function fail(code) {
  const err = new Error(code)
  err.code = code
  return err
}

async function fetchAsObjectUrl(url) {
  const resp = await fetch(url, { headers: authHeaders(), credentials: 'same-origin' })
  if (resp.status === 410) throw fail('gone')
  if (resp.status === 401 || resp.status === 403) throw fail('auth')
  if (!resp.ok) throw fail('fail')
  const type = resp.headers.get('content-type') || ''
  if (type.includes('text/html') || type.includes('application/json')) throw fail('fail')
  const bytes = new Uint8Array(await resp.arrayBuffer())
  const sniffed = sniffImageType(bytes, type)
  if (!sniffed || !bytes.length) throw fail('fail')
  return URL.createObjectURL(new Blob([bytes], { type: sniffed }))
}

function wait(ms) {
  return new Promise((resolve) => { window.setTimeout(resolve, ms) })
}

export async function loadTgPhotoUrl(fileId, size = 'full') {
  if (!fileId) return ''
  const kind = size === 'thumb' ? 'thumb' : 'full'
  const key = cacheKey(fileId, kind)
  const cached = blobCache.get(key)
  if (cached) return cached
  const pending = inflight.get(key)
  if (pending) return pending
  const url = LOCAL_FILE_RE.test(fileId) ? localUrl(fileId) : getPhotoProxyUrl(fileId, kind)
  const job = fetchAsObjectUrl(url)
    .then((objectUrl) => rememberBlob(key, objectUrl))
    .finally(() => { inflight.delete(key) })
  inflight.set(key, job)
  return job
}

export function dropTgPhoto(fileId, size = 'full') {
  if (!fileId) return
  blobCache.delete(cacheKey(fileId, size === 'thumb' ? 'thumb' : 'full'))
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
  const imgTries = useRef(0)

  useEffect(() => {
    imgTries.current = 0
    setSrc(null)
    setErr('')
  }, [fileId])

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
    }, { rootMargin: '240px' })
    io.observe(el)
    return () => io.disconnect()
  }, [lazy, visible, fileId])

  useEffect(() => {
    if (!fileId || !visible) return undefined
    let cancelled = false
    const kind = size === 'thumb' ? 'thumb' : 'full'

    const run = async () => {
      for (let attempt = 0; attempt < 4; attempt += 1) {
        try {
          const objectUrl = await loadTgPhotoUrl(fileId, kind)
          if (cancelled) return
          setErr('')
          setSrc(objectUrl)
          return
        } catch (exc) {
          if (cancelled) return
          const code = exc?.code === 'gone' || exc?.code === 'auth' ? exc.code : 'fail'
          if (code !== 'fail' || attempt === 3) {
            setErr(code)
            return
          }
          dropTgPhoto(fileId, kind)
          await wait(350 * (attempt + 1))
        }
      }
    }

    run()
    return () => { cancelled = true }
  }, [fileId, size, visible, retryTick])

  if (!fileId) return null

  const open = async () => {
    if (!onClick) return
    try {
      const full = await loadTgPhotoUrl(fileId, 'full')
      onClick(full || src)
    } catch {
      onClick(src || '')
    }
  }

  const retry = () => {
    dropTgPhoto(fileId, size)
    setSrc(null)
    setErr('')
    setRetryTick((n) => n + 1)
  }

  if (err) {
    return (
      <button
        ref={ref}
        type="button"
        className={`tg-photo-fallback ${className}`.trim()}
        style={style}
        onClick={(event) => {
          event.stopPropagation()
          retry()
        }}
      >
        {err === 'gone' ? 'файл в Telegram исчез' : err === 'auth' ? 'нужен повторный вход' : 'не загрузилось · нажмите ещё раз'}
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
        maxWidth: '100%',
        maxHeight: 300,
        borderRadius: 8,
        objectFit: 'contain',
        display: 'block',
        cursor: onClick ? 'zoom-in' : 'default',
        ...style,
      }}
      onClick={onClick ? open : undefined}
      onError={() => {
        dropTgPhoto(fileId, size)
        if (imgTries.current < 2) {
          imgTries.current += 1
          setSrc(null)
          setRetryTick((n) => n + 1)
          return
        }
        setErr('fail')
      }}
    />
  )
}
