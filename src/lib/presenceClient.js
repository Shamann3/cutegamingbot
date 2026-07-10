import { getApiAuthHeaders } from './apiClient'
import { collectClientInfo } from './clientInfo'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

function presenceHeaders() {
  return {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': '1',
    ...getApiAuthHeaders(),
  }
}

function presenceBody() {
  const info = collectClientInfo()
  return JSON.stringify(
    Object.fromEntries(
      Object.entries(info).filter(([, value]) => value != null && value !== ''),
    ),
  )
}

export function pingPresence() {
  let headers
  try {
    headers = presenceHeaders()
  } catch {
    return Promise.resolve(null)
  }
  return fetch(`${API_BASE}/api/presence`, {
    method: 'POST',
    headers,
    body: presenceBody(),
  }).then(async (response) => {
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || `Presence ping failed: ${response.status}`)
    }
    return response.json()
  })
}

/** При закрытии WebApp - снять с онлайна сразу (fetch keepalive). */
export function leavePresence() {
  try {
    fetch(`${API_BASE}/api/presence/leave`, {
      method: 'POST',
      headers: presenceHeaders(),
      body: presenceBody(),
      keepalive: true,
    }).catch(() => {})
  } catch {
    // ignore
  }
}
