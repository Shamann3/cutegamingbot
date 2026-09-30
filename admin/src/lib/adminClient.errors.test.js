import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchStaffPunishRights, nonJsonMessage } from './adminClient'

function textResponse(status, text) {
  return { ok: status < 400, status, text: async () => text }
}

describe('ответ API не JSON', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('blames ngrok only for a real ngrok page', () => {
    expect(nonJsonMessage(200, '<!DOCTYPE html><title>ngrok</title>')).toMatch(/ngrok/)
    expect(nonJsonMessage(503, '<!DOCTYPE html><h1>503 Service Unavailable</h1>')).not.toMatch(/ngrok/)
  })

  it('names the status when the API is down', () => {
    expect(nonJsonMessage(503, '<html>Service Unavailable</html>')).toMatch(/ошибка 503/)
    expect(nonJsonMessage(502, 'Bad gateway')).toMatch(/ошибка 502/)
  })

  it('points at a wrong API address when a site page answers', () => {
    expect(nonJsonMessage(200, '<!doctype html><div id="root"></div>')).toMatch(/веб-страница/)
  })

  it('reaches the screen through a real request', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => textResponse(503, '<!DOCTYPE html><h1>Service Unavailable</h1>')))
    await expect(fetchStaffPunishRights()).rejects.toThrow(/ошибка 503/)

    vi.stubGlobal('fetch', vi.fn(async () => textResponse(500, '')))
    await expect(fetchStaffPunishRights()).rejects.toThrow(/ошибка 500/)
  })

  it('keeps the API detail for JSON errors', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => textResponse(503, JSON.stringify({ detail: 'База данных не подключена. Повторите через минуту.' }))))
    await expect(fetchStaffPunishRights()).rejects.toThrow('База данных не подключена. Повторите через минуту.')
  })
})
