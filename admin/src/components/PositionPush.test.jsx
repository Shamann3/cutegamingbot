import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PositionPush from './PositionPush'
import { fetchRightsBoard, pushGroupPositions } from '../lib/adminClient'

vi.mock('../lib/adminClient', () => ({
  fetchRightsBoard: vi.fn(),
  pushGroupPositions: vi.fn(),
}))

const board = {
  groups: [
    {
      chatId: -5,
      title: 'CuteGamingChat',
      positions: [
        { id: 1, title: 'Создатель группы', rank: 5, kind: 'post', ladder: 0, rights: [] },
        { id: 2, title: 'Администратор ГЧ', rank: 4, kind: 'post', ladder: 0, rights: ['can_manage_video_chats'], prefix: 'ГЧ', pages: null },
        { id: 4, title: 'Модератор', rank: 3, kind: 'post', ladder: 1, rights: ['view_members', 'punish_mute', 'punish_warn'], pages: null },
      ],
      seats: [],
    },
    {
      chatId: -9,
      title: 'Новая группа',
      positions: [
        { id: 8, title: 'Создатель группы', rank: 5, kind: 'post', ladder: 0, rights: [] },
        { id: 9, title: 'Модератор', rank: 2, kind: 'post', ladder: 0, rights: ['view_members', 'punish_mute', 'punish_kick', 'punish_warn'], pages: null },
      ],
      seats: [{ userId: 77, positionId: 9 }],
    },
    {
      chatId: -12,
      title: 'Флудилка',
      positions: [{ id: 20, title: 'Создатель группы', rank: 5, kind: 'post', ladder: 0, rights: [] }],
      seats: [],
    },
  ],
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  document.documentElement.classList.remove('is-push-dragging')
})

function zone(title) {
  return screen.getByText(title, { selector: '.push-zone-name strong' }).closest('[data-push-zone]')
}

describe('PositionPush', () => {
  it('keeps the creator out and lays a picked post into one group by tap', async () => {
    vi.mocked(fetchRightsBoard).mockResolvedValue(board)
    vi.mocked(pushGroupPositions).mockResolvedValue({
      ok: true,
      groups: [{
        chatId: -9,
        title: '-9',
        created: [],
        updated: [{ title: 'Модератор', rank: 2, rankFrom: 2, changes: ['rights'] }],
        same: [],
        skipped: [],
        shifted: [],
        telegram: { synced: 1, failed: 0, note: '' },
        error: '',
      }],
    })
    const onClose = vi.fn()
    render(<PositionPush chatId={-5} onClose={onClose} />)

    const moderator = await screen.findByRole('button', { name: 'Модератор, ранг 3' })
    expect(screen.queryByRole('button', { name: /^Создатель группы/ })).toBeNull()
    fireEvent.click(moderator)
    expect(moderator.getAttribute('aria-pressed')).toBe('true')

    fireEvent.click(screen.getByRole('button', { name: 'Сюда · 1 — Новая группа' }))
    const target = zone('Новая группа')
    expect(within(target).getByText('обновится')).toBeTruthy()
    expect(within(target).getByText('права: − Кик')).toBeTruthy()
    expect(within(target).getByText('в Telegram права обновятся у 1 человека')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Перенести в 1 группу · 1 изменение' }))
    await waitFor(() => expect(pushGroupPositions).toHaveBeenCalledWith({
      source_chat_id: -5,
      targets: [{ chat_id: -9, ids: [4] }],
    }))
    expect(await screen.findByText('Перенос записан')).toBeTruthy()
    expect(screen.getByText('Обновлены: Модератор')).toBeTruthy()
    expect(screen.getByText('В Telegram права обновлены у 1 человека')).toBeTruthy()
    await waitFor(() => expect(fetchRightsBoard).toHaveBeenCalledTimes(2))

    fireEvent.click(screen.getByRole('button', { name: 'Готово' }))
    expect(onClose).toHaveBeenCalledWith('Перенесено в 1 группу: 1 обновлена.')
  })

  it('drops a dragged post on the group under the finger and lets it be taken back', async () => {
    vi.mocked(fetchRightsBoard).mockResolvedValue(board)
    render(<PositionPush chatId={-5} onClose={() => {}} />)
    const token = await screen.findByRole('button', { name: 'Администратор ГЧ, ранг 4' })
    const target = zone('Флудилка')
    const before = document.elementFromPoint
    document.elementFromPoint = () => target
    try {
      const grip = token.querySelector('.push-token-grip')
      fireEvent.pointerDown(grip, { pointerId: 3, pointerType: 'touch', button: 0, clientX: 10, clientY: 10 })
      await act(async () => {
        fireEvent.pointerMove(window, { pointerId: 3, pointerType: 'touch', clientX: 200, clientY: 400 })
      })
      expect(document.documentElement.classList.contains('is-push-dragging')).toBe(true)
      expect(target.classList.contains('is-over')).toBe(true)
      await act(async () => {
        fireEvent.pointerUp(window, { pointerId: 3, pointerType: 'touch', clientX: 200, clientY: 400 })
        await new Promise((resolve) => setTimeout(resolve, 0))
      })
    } finally {
      document.elementFromPoint = before
    }
    expect(document.documentElement.classList.contains('is-push-dragging')).toBe(false)
    expect(within(target).getByText('новая · ранг 4')).toBeTruthy()
    expect(within(target).getByText('префикс «ГЧ»')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Перенести в 1 группу · 1 изменение' })).toBeTruthy()

    fireEvent.click(within(target).getByRole('button', { name: 'Не переносить «Администратор ГЧ» в Флудилка' }))
    await waitFor(() => expect(within(target).queryByText('новая · ранг 4')).toBeNull())
    expect(screen.getByRole('button', { name: 'Перенести' }).disabled).toBe(true)
  })

  it('sends everything to every group from the shared drop zone', async () => {
    vi.mocked(fetchRightsBoard).mockResolvedValue(board)
    render(<PositionPush chatId={-5} onClose={() => {}} />)
    await screen.findByRole('button', { name: 'Модератор, ранг 3' })
    const every = screen.getByText('Во все группы').closest('[data-push-zone]')
    fireEvent.click(within(every).getByRole('button', { name: 'Всё сюда' }))
    expect(within(zone('Флудилка')).getAllByText(/^новая · ранг/)).toHaveLength(2)
    expect(within(zone('Новая группа')).getByText('новая · ранг 4')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Перенести в 2 группы · 4 изменения' })).toBeTruthy()
  })
})
