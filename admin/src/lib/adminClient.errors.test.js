import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchStaffPunishRights, nonJsonMessage } from './adminClient'

function textResponse(status, text) {
  return { ok: status < 400, status, text: async () => text }
}

describe('ответ API не JSON', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('says only that the API is down', () => {
    expect(nonJsonMessage(200, '<!DOCTYPE html><title>ngrok</title>')).toBe('API не отвечает')
    expect(nonJsonMessage(503, '<html>Service Unavailable</html>')).toBe('API не отвечает')
    expect(nonJsonMessage(502, 'Bad gateway')).toBe('API не отвечает')
    expect(nonJsonMessage(200, '<!doctype html><div id="root"></div>')).toBe('API не отвечает')
  })

  it('reaches the screen through a real request', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => textResponse(503, '<!DOCTYPE html><h1>Service Unavailable</h1>')))
    await expect(fetchStaffPunishRights()).rejects.toThrow('API не отвечает')

    vi.stubGlobal('fetch', vi.fn(async () => textResponse(500, '')))
    await expect(fetchStaffPunishRights()).rejects.toThrow('API не отвечает')
  })

  it('keeps the API detail for JSON errors', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => textResponse(503, JSON.stringify({ detail: 'База данных не подключена. Повторите через минуту.' }))))
    await expect(fetchStaffPunishRights()).rejects.toThrow('База данных не подключена. Повторите через минуту.')
  })
})
