import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StatDesk from './StatDesk'
import { fetchStatBoard, fetchStatCatalog, fetchStatGroups, fetchStatPerson, saveStatValue } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', () => ({
  fetchStatCatalog: vi.fn(),
  fetchStatGroups: vi.fn(),
  fetchStatBoard: vi.fn(),
  fetchStatPerson: vi.fn(),
  saveStatValue: vi.fn(),
  copyStatSeason: vi.fn(),
  clearStatSeason: vi.fn(),
}))

vi.mock('../../components/UserLookupPreview', () => ({
  default: ({ onResolved }) => (
    <>
      <button type="button" onClick={() => onResolved(null)}>сбросить</button>
      <button type="button" onClick={() => onResolved({ userId: 7, username: 'ivan' })}>выбрать Ивана</button>
    </>
  ),
}))

const CATALOG = {
  metrics: [
    {
      id: 'messages',
      title: 'Топ сообщений',
      blurb: 'Нужна группа.',
      needsGroup: true,
      periods: [
        { id: 'day', label: 'За день' },
        { id: 'all', label: 'За всё время' },
      ],
      fields: [{ key: 'messages', label: 'Сообщений' }],
      rowUnit: 'сообщений',
      topLimit: 30,
    },
    {
      id: 'donors',
      title: 'Донатеры',
      blurb: 'Без группы.',
      needsGroup: false,
      periods: [{ id: 'all', label: 'За всё время' }],
      fields: [{ key: 'donate', label: 'Донат' }],
      rowUnit: 'кут',
      topLimit: 10,
    },
  ],
}

beforeEach(() => {
  vi.mocked(fetchStatCatalog).mockResolvedValue(CATALOG)
  vi.mocked(fetchStatGroups).mockResolvedValue({
    period: 'day',
    periodLabel: '30.09.2026',
    items: [{ chatId: -100, title: 'Альфа', username: 'alpha', amount: 12 }],
  })
  vi.mocked(fetchStatBoard).mockImplementation(async ({ metric, period }) => {
    if (metric === 'messages' && period === 'all') {
      return {
        metric: 'messages',
        period: 'all',
        periodLabel: 'За всё время',
        rowUnit: 'сообщений',
        total: 9,
        rows: [{ place: 1, userId: 3, name: 'Год', username: '', seen: 9, raw: 9 }],
        season: null,
      }
    }
    if (metric === 'messages') {
      return {
        metric: 'messages',
        period: 'day',
        periodLabel: '30.09.2026',
        rowUnit: 'сообщений',
        total: 5,
        rows: [{ place: 1, userId: 2, name: 'День', username: '', seen: 5, raw: 5 }],
        season: null,
      }
    }
    return {
      metric: 'donors',
      period: 'all',
      periodLabel: 'За всё время',
      rowUnit: 'кут',
      total: null,
      rows: [{ place: 1, userId: 7, name: 'Иван', username: 'ivan', seen: 40, raw: 40 }],
      season: null,
    }
  })
  vi.mocked(fetchStatPerson).mockResolvedValue({
    userId: 7,
    name: 'Иван',
    username: 'ivan',
    fields: [{ key: 'donate', label: 'Донат', raw: 40, seen: 40, copied: null, gained: 0 }],
    season: null,
  })
  vi.mocked(saveStatValue).mockResolvedValue({ ok: true })
})

afterEach(() => cleanup())

describe('StatDesk', () => {
  it('shows groups for the selected period and a single board after a group is chosen', async () => {
    render(<StatDesk />)
    expect(await screen.findByRole('button', { name: /Альфа/ })).toBeTruthy()
    expect(screen.getByText('12 сообщений')).toBeTruthy()
    expect(fetchStatBoard).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Сохранить в этот топ' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Альфа/ }))
    expect(await screen.findByRole('button', { name: /День/ })).toBeTruthy()
    expect(screen.getByText('5 сообщений')).toBeTruthy()
    expect(screen.queryByText('Год')).toBeNull()

    fireEvent.click(screen.getByRole('tab', { name: 'За всё время' }))
    expect(await screen.findByRole('button', { name: /Год/ })).toBeTruthy()
    expect(screen.queryByText('День')).toBeNull()
    expect(screen.getByText('9 сообщений')).toBeTruthy()
    expect(fetchStatBoard).toHaveBeenLastCalledWith(expect.objectContaining({
      metric: 'messages',
      period: 'all',
      chat_id: -100,
    }))
  })

  it('opens donors without a group and saves the person from the row', async () => {
    render(<StatDesk />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Донатеры' }))
    expect(screen.queryByPlaceholderText('ID, @username или имя группы')).toBeNull()
    expect(screen.queryByText('Альфа')).toBeNull()
    expect(await screen.findByText('40 кут')).toBeTruthy()
    expect(fetchStatBoard).toHaveBeenCalledWith(expect.objectContaining({
      metric: 'donors',
      period: 'all',
    }))

    fireEvent.click(screen.getByRole('button', { name: /40 кут/ }))
    fireEvent.click(screen.getByRole('button', { name: 'сбросить' }))
    expect(await screen.findByDisplayValue('40')).toBeTruthy()
    expect(await screen.findByText('40 сейчас в топе')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить в этот топ' }))

    expect(saveStatValue).toHaveBeenCalledWith(expect.objectContaining({
      metric: 'donors',
      period: 'all',
      user_id: 7,
      values: { donate: 40 },
    }))
    expect(await screen.findByText('Сохранено. В этом топе теперь 40.')).toBeTruthy()
  })

  it('explains a game copy without a date window that hides the top', async () => {
    vi.mocked(fetchStatCatalog).mockResolvedValue({
      metrics: [
        ...CATALOG.metrics,
        {
          id: 'players',
          title: 'Лучшие игроки',
          blurb: 'Игры.',
          needsGroup: false,
          periods: [
            { id: 'day', label: 'За день' },
            { id: 'all', label: 'За всё время' },
          ],
          fields: [
            { key: 'wins', label: 'Победы' },
            { key: 'losses', label: 'Проигрыши' },
          ],
          rowUnit: 'сыгранных игр',
          topLimit: 10,
        },
      ],
    })
    vi.mocked(fetchStatBoard).mockImplementation(async ({ metric, period }) => ({
      metric,
      period,
      periodLabel: period === 'all' ? 'За всё время' : '30.09.2026',
      rowUnit: metric === 'players' ? 'сыгранных игр' : 'кут',
      total: null,
      rows: [{
        place: 1,
        userId: 3,
        name: 'Аня',
        username: 'anya',
        seen: 4,
        raw: 40,
        wins: 30,
        losses: 10,
        games: 4,
      }],
      season: {
        phase: 'zero',
        zeroFrom: '2026-09-30',
        zeroUntil: '2026-10-02',
        note: 'Копия уже снята.',
      },
    }))
    render(<StatDesk />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Лучшие игроки' }))
    expect(await screen.findByText('4 сыгранных игр')).toBeTruthy()
    expect(screen.queryByText(/люди видят нули/)).toBeNull()
    fireEvent.click(screen.getByRole('tab', { name: 'За всё время' }))
    expect(await screen.findByText(/только игры после копии/)).toBeTruthy()
    fireEvent.click(screen.getByText('Копия игр'))
    expect(screen.getByLabelText('С этого момента')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Снять новую копию' })).toBeTruthy()
    expect(screen.queryByText('С какого числа')).toBeNull()
  })

  it('refreshes the open top every second without wiping a number being typed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      render(<StatDesk />)
      fireEvent.click(await screen.findByRole('tab', { name: 'Донатеры' }))
      expect(await screen.findByText('40 кут')).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: /40 кут/ }))
      const input = await screen.findByDisplayValue('40')
      fireEvent.change(input, { target: { value: '77' } })
      vi.mocked(fetchStatBoard).mockResolvedValue({
        metric: 'donors',
        period: 'all',
        periodLabel: 'За всё время',
        rowUnit: 'кут',
        total: null,
        rows: [{ place: 1, userId: 7, name: 'Иван', username: 'ivan', seen: 55, raw: 55 }],
        season: null,
      })
      vi.mocked(fetchStatPerson).mockResolvedValue({
        userId: 7,
        name: 'Иван',
        username: 'ivan',
        fields: [{ key: 'donate', label: 'Донат', raw: 55, seen: 55, copied: null, gained: 0 }],
        season: null,
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
      expect(await screen.findByText('55 кут')).toBeTruthy()
      expect(screen.getByDisplayValue('77')).toBeTruthy()
    } finally {
      vi.useRealTimers()
    }
  })
})
