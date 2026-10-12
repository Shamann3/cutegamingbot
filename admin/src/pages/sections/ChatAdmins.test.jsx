import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ChatAdmins from './ChatAdmins'
import { actChatAdmin, adviseChatApplication, fetchChatAdmins, fetchChatApplications, fetchPersonHistory } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', () => ({
  fetchChatAdmins: vi.fn(),
  actChatAdmin: vi.fn(),
  fetchChatApplications: vi.fn(),
  adviseChatApplication: vi.fn(),
  fetchPersonHistory: vi.fn(),
}))

const BOARD = {
  admins: [
    {
      userId: 5,
      name: 'Аня',
      username: 'anya',
      status: 'administrator',
      title: '',
      isBot: false,
      isSelfBot: false,
      canDelete: true,
      canRestrict: true,
      canPromote: false,
      stats: { day: 4, week: 18, month: 40, total: 900, last: 'вчера' },
      deeds: { mute: 2, ban: 0, kick: 1, warn: 3 },
    },
  ],
  history: [
    {
      id: 1,
      action: 'chat_admin_demote',
      detail: 'Снял админку: Иван · 9',
      actorName: 'Босс',
      at: '2026-10-11T18:27:00Z',
    },
  ],
  canAct: true,
  creator: true,
  botCanPromote: true,
  selfId: 1,
  error: '',
}

describe('chat admins', () => {
  afterEach(() => cleanup())

  it('lists the group admins and asks before removing one', async () => {
    vi.mocked(fetchChatAdmins).mockResolvedValue(BOARD)
    vi.mocked(actChatAdmin).mockResolvedValue({ ...BOARD, note: 'Админка снята', history: BOARD.history })
    render(<ChatAdmins chatId={-100} />)
    expect(await screen.findByText('Аня')).toBeTruthy()
    expect(screen.getByText(/вчера/)).toBeTruthy()
    expect(screen.getByText('40')).toBeTruthy()
    expect(screen.getByText(/Муты 2/)).toBeTruthy()
    expect(screen.getByText(/@JerichoCute/)).toBeTruthy()
    expect(screen.getByText('@anya · 5')).toBeTruthy()
    expect(screen.queryByText('Создатель Создатель')).toBeNull()
    expect(screen.getByText('Босс')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Ограничить' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Снять' }))
    expect(screen.getByText(/Снять админку: Аня станет обычным участником/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить' }))
    await waitFor(() => {
      expect(actChatAdmin).toHaveBeenCalledWith(-100, 5, 'demote')
    })
    expect(await screen.findByText('Админка снята')).toBeTruthy()
  })

  it('punishes a junior admin with any span the seat allows', async () => {
    vi.mocked(fetchChatAdmins).mockResolvedValue({
      ...BOARD,
      admins: [{ ...BOARD.admins[0], junior: true, rank: 1 }],
      botCanRestrict: true,
    })
    vi.mocked(fetchPersonHistory).mockResolvedValue({
      name: 'Аня',
      username: 'anya',
      items: [],
      available: true,
    })
    const punish = vi.fn().mockResolvedValue({})
    render(<ChatAdmins chatId={-100} actions={[
      { id: 'mute', label: 'Мут', needsUntil: true, hint: 'В этой группе можете закрыть человеку сообщения и потом открыть.' },
      { id: 'warn', label: 'Предупредить', needsUntil: true },
      { id: 'kick', label: 'Кикнуть', needsUntil: false },
    ]} onPunish={punish} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Мут' }))
    const sheet = await screen.findByRole('dialog')
    expect(within(sheet).getByText('Раньше наказаний не было. Первое можно выдать снизу.')).toBeTruthy()
    expect(within(sheet).getByRole('button', { name: 'До секунды' })).toBeTruthy()
    fireEvent.click(within(sheet).getByRole('button', { name: 'Предупредить' }))
    expect(within(sheet).getByRole('button', { name: 'Выдать: Предупредить · 1 час' })).toBeTruthy()
    fireEvent.click(within(sheet).getByRole('button', { name: 'До секунды' }))
    fireEvent.change(within(sheet).getByLabelText('Часы'), { target: { value: '0' } })
    fireEvent.change(within(sheet).getByLabelText('Минуты'), { target: { value: '12' } })
    fireEvent.change(within(sheet).getByPlaceholderText('что человек сделал'), { target: { value: 'флуд' } })
    fireEvent.click(within(sheet).getByRole('button', { name: 'Выдать: Предупредить · 12 минут' }))
    await waitFor(() => {
      expect(punish).toHaveBeenCalledWith({
        userId: '5',
        action: 'warn',
        untilSec: 12 * 60,
        reason: 'флуд',
      })
    })
  })

  it('opens a person from the name and does not offer a rights cut', async () => {
    vi.mocked(fetchChatAdmins).mockResolvedValue(BOARD)
    const open = vi.fn()
    render(<ChatAdmins chatId={-100} onOpenUser={open} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Аня' }))
    expect(open).toHaveBeenCalledWith(5)
    expect(screen.queryByRole('button', { name: 'Ограничить' })).toBeNull()
  })

  it('asks the creator before a group admin removes someone', async () => {
    vi.mocked(fetchChatAdmins).mockResolvedValue({ ...BOARD, creator: false })
    render(<ChatAdmins chatId={-100} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Снять' }))
    expect(screen.getByText(/Заявка создателю @JerichoCute/)).toBeTruthy()
  })

  it('sends a fit recommendation and does not approve the application', async () => {
    vi.mocked(fetchChatAdmins).mockResolvedValue(BOARD)
    vi.mocked(fetchChatApplications).mockResolvedValue({
      items: [{
        id: 9,
        userId: 77,
        name: 'Лена',
        username: 'lena',
        position: 'Модератор',
        body: 'Хочу помогать в чате',
        status: 'pending',
        advice: [],
      }],
    })
    vi.mocked(adviseChatApplication).mockResolvedValue({ ok: true })
    render(<ChatAdmins chatId={-100} />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Заявки' }))
    expect(await screen.findByText('Лена')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Одобрить' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Подходит' }))
    fireEvent.change(screen.getByLabelText('Пояснение, если нужно'), { target: { value: 'Пишет спокойно' } })
    fireEvent.click(screen.getByRole('button', { name: 'Отправить рекомендацию' }))
    await waitFor(() => {
      expect(adviseChatApplication).toHaveBeenCalledWith(-100, 9, 'fit', 'Пишет спокойно')
    })
  })
})
