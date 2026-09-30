import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  PREVIEW_BLOCKED_MESSAGE,
  fetchPanelAccess,
  refreshAdminSession,
  saveGroupPosition,
  setPanelPreviewMode,
  setPanelRoleDefault,
} from './adminClient'

function jsonResponse(data) {
  return { ok: true, status: 200, text: async () => JSON.stringify(data) }
}

describe('копия панели в тестовом режиме', () => {
  let fetchMock

  beforeEach(() => {
    fetchMock = vi.fn(async () => jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    setPanelPreviewMode(false)
    vi.unstubAllGlobals()
  })

  it('reads data as usual', async () => {
    setPanelPreviewMode(true)
    await expect(fetchPanelAccess()).resolves.toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('stops every write before it reaches the server and tells the copy strip', async () => {
    setPanelPreviewMode(true)
    const seen = []
    const onBlocked = (event) => seen.push(event.detail)
    window.addEventListener('epsilon-preview-blocked', onBlocked)
    try {
      await expect(setPanelRoleDefault({ role: 'moderator', sectionId: 'users', enabled: true }))
        .rejects.toMatchObject({ message: PREVIEW_BLOCKED_MESSAGE, preview: true })
      await expect(saveGroupPosition(7, { title: 'Глава' })).rejects.toMatchObject({ preview: true })
    } finally {
      window.removeEventListener('epsilon-preview-blocked', onBlocked)
    }
    expect(fetchMock).not.toHaveBeenCalled()
    expect(seen).toEqual([
      { method: 'PUT', path: '/panel-access/role-default' },
      { method: 'POST', path: '/group-realm/positions/7' },
    ])
  })

  it('keeps the creator session alive inside the copy', async () => {
    setPanelPreviewMode(true)
    await refreshAdminSession()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('writes normally again once the copy is closed', async () => {
    setPanelPreviewMode(true)
    setPanelPreviewMode(false)
    await setPanelRoleDefault({ role: 'moderator', sectionId: 'users', enabled: true })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
