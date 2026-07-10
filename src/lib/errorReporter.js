import { getTelegramInitData } from './telegram'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

function buildReportHeaders() {
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': '1',
  }
  const initData = getTelegramInitData()
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData
    return headers
  }
  const devUserId = import.meta.env.VITE_DEV_USER_ID
  if (devUserId) {
    headers['X-Dev-User-Id'] = devUserId
  }
  return headers
}

export async function reportClientError({
  code,
  message = '',
  path = '',
  context = '',
}) {
  try {
    await fetch(`${API_BASE}/api/report-error`, {
      method: 'POST',
      headers: buildReportHeaders(),
      body: JSON.stringify({ code, message, path, context }),
    })
  } catch {
    // не мешаем UI
  }
}
