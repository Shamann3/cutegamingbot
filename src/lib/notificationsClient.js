import { ApiError, apiRequest, getApiAuthHeaders, mapApiError } from './apiClient'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export async function fetchNotifications() {
  return apiRequest('/api/notifications')
}

export async function ackNotifications(ids) {
  return apiRequest('/api/notifications/ack', {
    method: 'POST',
    body: { ids },
  })
}

function parseSseChunk(chunk, onNotification) {
  const lines = chunk.split('\n')
  for (const line of lines) {
    if (!line.startsWith('data: ')) continue
    try {
      const data = JSON.parse(line.slice(6))
      onNotification(data)
    } catch {
      // ignore malformed events
    }
  }
}

export async function connectNotificationStream({ onNotification, onOpen, signal }) {
  const headers = {
    Accept: 'text/event-stream',
    ...getApiAuthHeaders(),
  }
  if (import.meta.env.DEV) {
    headers['ngrok-skip-browser-warning'] = '1'
  }

  const response = await fetch(`${API_BASE}/api/notifications/stream`, {
    method: 'GET',
    headers,
    signal,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    if (response.status === 503 && error.code === 'ERR_SSE_LIMIT') {
      throw new ApiError(
        error.detail ?? 'SSE недоступен',
        { status: 503, code: 'sse_limit' },
      )
    }
    throw mapApiError(response.status, error.detail ?? error.message)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('Stream unavailable')
  }

  onOpen?.()

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      parseSseChunk(part, onNotification)
    }
  }

  if (buffer.trim()) {
    parseSseChunk(buffer, onNotification)
  }
}
