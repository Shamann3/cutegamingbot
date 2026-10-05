import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ActivityBoard from './ActivityBoard'
import GroupArchive from './GroupArchive'
import { fetchGroupActivity, fetchPersonHistory } from '../lib/adminClient'

vi.mock('../lib/adminClient', () => ({
  fetchGroupActivity: vi.fn(),
  fetchPersonHistory: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

beforeEach(() => {
  vi.mocked(fetchPersonHistory).mockResolvedValue({ available: true, counts: [] })
})

const report = {
  available: true,
  messages: 40,
  writers: 2,
  periodMessages: 100,
  periodWriters: 4,
  previousMessages: 80,
  series: [{ date: '2026-10-01', messages: 40, writers: 2 }],
  people: [
    { userId: 7, name: 'Анна', username: 'anna', messages: 40 },
  ],
}

describe('ActivityBoard', () => {
  it('opens a person and can send them to the archive', async () => {
    vi.mocked(fetchGroupActivity).mockResolvedValue(report)
    const onOpenArchive = vi.fn()
    render(
      <ActivityBoard
        chatId={1}
        canArchive
        onOpenArchive={onOpenArchive}
        watch={[{ userId: 7, warns: 2 }]}
        repeats={new Map([[7, 3]])}
      />,
    )
    fireEvent.click(await screen.findByRole('button', { name: /Анна, 40 сообщений/ }))
    expect(screen.getByText('40%')).toBeTruthy()
    expect(screen.getByText(/Ещё одно предупреждение — бан в этом чате/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Наказания этого человека' }))
    expect(onOpenArchive).toHaveBeenCalledWith(7)
  })

  it('lists only the punishments that already happened', async () => {
    vi.mocked(fetchGroupActivity).mockResolvedValue(report)
    vi.mocked(fetchPersonHistory).mockResolvedValue({
      available: true,
      counts: [
        { action: 'banfull', label: 'Банфулл', hint: 'весь проект', count: 2 },
        { action: 'unban', label: 'Разбан', hint: 'этот чат', count: 1 },
        { action: 'warnfull', label: 'Варнфулл', hint: 'весь проект', count: 1 },
      ],
    })
    render(<ActivityBoard chatId={1} canArchive onOpenArchive={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: /Анна, 40 сообщений/ }))
    expect(await screen.findByText('Банфулл')).toBeTruthy()
    expect(screen.getByText('Разбан')).toBeTruthy()
    expect(screen.getByText('Варнфулл')).toBeTruthy()
    expect(screen.getAllByText('весь проект')).toHaveLength(2)
    expect(screen.queryByText('Размут')).toBeNull()
    expect(screen.queryByText('Мут')).toBeNull()
  })

  it('compares the period and opens one day', async () => {
    vi.mocked(fetchGroupActivity).mockResolvedValue(report)
    render(<ActivityBoard chatId={1} />)
    expect(await screen.findByText(/\+25%/)).toBeTruthy()
    expect(screen.queryByRole('tab', { name: 'Обзор' })).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Сравнение' }))
    expect(screen.getByText(/на 25% больше/)).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Дни' }))
    fireEvent.click(screen.getByRole('button', { name: '1 окт: 40 сообщений' }))
    expect(await screen.findByRole('button', { name: /Снова весь срок/ })).toBeTruthy()
  })

  it('stays a name list on the home day', async () => {
    vi.mocked(fetchGroupActivity).mockResolvedValue(report)
    render(<ActivityBoard chatId={1} peopleOnly seedPeriod="week" seedSlice="2026-10-01" />)
    expect(await screen.findByRole('button', { name: /Анна, 40 сообщений/ })).toBeTruthy()
    expect(screen.queryByRole('tab', { name: 'Обзор' })).toBeNull()
  })
})

describe('GroupArchive', () => {
  it('puts the lift on the card and asks for a reason there', () => {
    const onAct = vi.fn()
    render(
      <GroupArchive
        rows={[{ id: 1, action: 'ban', target_user_id: 7, targetName: 'Игрок', admin: 'Анна', reason: 'спам', at: '2026-10-01T12:00:00Z' }]}
        actions={[{ id: 'unban', label: 'Разбан' }, { id: 'ban', label: 'Бан', needsUntil: true }]}
        onAct={onAct}
      />,
    )
    expect(screen.getByRole('button', { name: 'Разбанить' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Разбанить' }))
    expect(screen.getByLabelText('Причина снятия')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Разбанить' })).toBeTruthy()
  })

  it('shows a new punishment in the open list and names one the filter hides', () => {
    const { rerender } = render(
      <GroupArchive
        rows={[{ id: 4, action: 'mute', target_user_id: 3, admin: 'Анна', reason: 'флуд', at: '2026-10-05T01:00:00Z' }]}
        actions={[]}
      />,
    )
    rerender(
      <GroupArchive
        rows={[
          { id: 9, action: 'ban', target_user_id: 8, admin: 'Анна', reason: 'спам', at: '2026-10-05T01:02:00Z' },
          { id: 4, action: 'mute', target_user_id: 3, admin: 'Анна', reason: 'флуд', at: '2026-10-05T01:00:00Z' },
        ]}
        actions={[]}
        arrived={[{ id: 9, action: 'ban', target_user_id: 8 }]}
      />,
    )
    expect(screen.getByRole('status').textContent).toBe('Новый бан уже в этом списке.')
    fireEvent.click(screen.getByRole('button', { name: 'Муты' }))
    expect(screen.getByRole('status').textContent).toBe('Новый бан уже в архиве. Этот фильтр его не показывает.')
  })
})
