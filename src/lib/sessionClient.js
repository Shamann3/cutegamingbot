import { canAuthenticate } from './telegram'
import { getApiAuthHeaders } from './apiClient'
import { collectClientInfo } from './clientInfo'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

function syncHeaders() {
  return {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': '1',
    ...getApiAuthHeaders(),
  }
}

function syncBody() {
  return JSON.stringify(
    Object.fromEntries(
      Object.entries(collectClientInfo()).filter(([, value]) => value != null && value !== ''),
    ),
  )
}

/** Сразу при входе в WebApp - устройство, IP, Telegram в БД. */
export function syncSession() {
  if (!canAuthenticate()) return Promise.resolve({ ok: false })

  return fetch(`${API_BASE}/api/session/sync`, {
    method: 'POST',
    headers: syncHeaders(),
    body: syncBody(),
  }).then(async (response) => {
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || `Session sync failed: ${response.status}`)
    }
    return response.json()
  })
}
