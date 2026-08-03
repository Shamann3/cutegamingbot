import {
  canAuthenticate,
  getAuthErrorMessage,
  getTelegramInitData,
} from './telegram'
import { getClientInfoHeaders } from './clientInfo'
import { reportApiFailure } from './reportApiFailure'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'unknown' } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

function detailToText(detail, status) {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const loc = Array.isArray(item.loc) ? item.loc.filter((x) => x !== 'body' && x !== 'query').join('.') : ''
          const msg = item.msg || item.message || ''
          if (loc && msg) return `${loc}: ${msg}`
          return msg || ''
        }
        return ''
      })
      .filter(Boolean)
    if (parts.length) return parts.join('; ')
  }
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    return detail.message
  }
  return `Ошибка ${status}`
}

export function mapApiError(status, detail) {
  const text = detailToText(detail, status)
  if (status === 401) {
    return new ApiError(
      typeof detail === 'string' && detail
        ? detail
        : 'Сессия истекла. Пожалуйста, перезапустите приложение из Telegram бота',
      { status, code: 'auth' },
    )
  }
  if (status === 429) {
    return new ApiError(
      'Слишком часто. Пожалуйста, подождите 10 секунд и попробуйте снова',
      { status, code: 'rate_limit' },
    )
  }
  if (status === 503) {
    const text = typeof detail === 'string' ? detail : `Ошибка ${status}`
    const isMaintenance = text.includes('Технические работы')
    return new ApiError(
      isMaintenance ? 'Технические работы. Пожалуйста, зайдите позже' : text,
      { status, code: isMaintenance ? 'maintenance' : 'unavailable' },
    )
  }
  return new ApiError(text, { status, code: 'api' })
}

function buildAuthHeaders() {
  if (!canAuthenticate()) {
    throw new ApiError(getAuthErrorMessage(), { status: 401, code: 'auth' })
  }

  const initData = getTelegramInitData()
  if (initData) {
    return { 'X-Telegram-Init-Data': initData, ...getClientInfoHeaders() }
  }

  const devUserId = import.meta.env.VITE_DEV_USER_ID
  return { 'X-Dev-User-Id': devUserId, ...getClientInfoHeaders() }
}

export function getApiAuthHeaders() {
  return buildAuthHeaders()
}

export async function apiRequest(path, { method = 'GET', body, timeoutMs = 15000 } = {}) {
  const authHeaders = buildAuthHeaders()

  const headers = {
    Accept: 'application/json',
    'ngrok-skip-browser-warning': '1',
    ...authHeaders,
    ...(body ? { 'Content-Type': 'application/json' } : {}),
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      const apiErr = mapApiError(response.status, error.detail ?? error.message)
      if (response.status === 403) {
        window.dispatchEvent(new CustomEvent('api:forbidden', { detail: apiErr }))
      }
      if (response.status === 503 && apiErr.code === 'maintenance') {
        window.dispatchEvent(new CustomEvent('api:maintenance', { detail: apiErr }))
      }
      throw apiErr
    }

    return response.json()
  } catch (error) {
    if (error instanceof ApiError) {
      reportApiFailure(error, path)
      throw error
    }
    if (error.name === 'AbortError') {
      const timeoutError = new ApiError(
        'Сервер не отвечает. Пожалуйста, запустите .\\start-server.ps1 в папке server (порт 8000).',
        { status: 0, code: 'timeout' },
      )
      reportApiFailure(timeoutError, path)
      throw timeoutError
    }
    if (error instanceof TypeError) {
      const networkError = new ApiError(
        'Нет связи с API. Пожалуйста, проверьте: start-server.ps1 + npm run dev + ngrok http 5173.',
        { status: 0, code: 'network' },
      )
      reportApiFailure(networkError, path)
      throw networkError
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

export async function submitComplaint({ reason, subject = '' }) {
  return apiRequest('/api/complaints', {
    method: 'POST',
    body: { reason, subject },
  })
}

/** Fallback совпадает с BannedScreen / SUPPORT_BOT_URL в .env */
export const DEFAULT_SUPPORT_BOT_URL = 'https://t.me/cutegamingsupportbot'

let _supportBotUrl = String(import.meta.env.VITE_SUPPORT_BOT_URL || '').trim()
const _supportUrlListeners = new Set()

function _setSupportBotUrl(next) {
  const url = String(next || '').trim()
  if (!url || url === _supportBotUrl) return
  _supportBotUrl = url
  _supportUrlListeners.forEach((fn) => {
    try { fn(_supportBotUrl) } catch { /* ignore */ }
  })
}

export function getSupportBotUrl() {
  return _supportBotUrl || DEFAULT_SUPPORT_BOT_URL
}

/** Подписка на обновление URL с /api/status (для кнопок, смонтированных до ответа). */
export function subscribeSupportBotUrl(listener) {
  if (typeof listener !== 'function') return () => {}
  _supportUrlListeners.add(listener)
  return () => _supportUrlListeners.delete(listener)
}

export async function fetchAppStatus() {
  const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''
  let authHeaders = {}
  try { authHeaders = buildAuthHeaders() } catch { /* не в Telegram ок */ }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 8000)

  try {
    const response = await fetch(`${API_BASE_URL}/api/status`, {
      headers: { Accept: 'application/json', 'ngrok-skip-browser-warning': '1', ...authHeaders },
      signal: controller.signal,
    })
    if (!response.ok) {
      return { ok: false, maintenance: false }
    }
    const data = await response.json()
    if (data.supportBotUrl) _setSupportBotUrl(data.supportBotUrl)
    return data
  } catch {
    return { ok: false, maintenance: false }
  } finally {
    clearTimeout(timeoutId)
  }
}
