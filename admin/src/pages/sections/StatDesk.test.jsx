import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StatDesk from './StatDesk'
import { fetchStatBoard, fetchStatCatalog, fetchStatPerson } from '../../lib/adminClient'

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
    <button type="button" onClick={() => onResolved({ userId: 7, username: 'ivan' })}>выбрать Ивана</button>
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
  vi.mocked(fetchStatBoard).mockResolvedValue({
    periodLabel: 'За всё время',
    rowUnit: 'кут',
    total: null,
    rows: [{ place: 1, userId: 7, name: 'Иван', username: 'ivan', seen: 40, raw: 40 }],
    season: null,
  })
  vi.mocked(fetchStatPerson).mockResolvedValue({
    userId: 7,
    name: 'Иван',
    username: 'ivan',
    fields: [{ key: 'donate', label: 'Донат', raw: 40, seen: 40, copied: null, gained: 0 }],
  })
})

afterEach(() => cleanup())

describe('StatDesk', () => {
  it('asks for a group on message stats and not on donors', async () => {
    render(<StatDesk />)
    expect(await screen.findByRole('tab', { name: 'Топ сообщений' })).toBeTruthy()
    expect(screen.getByPlaceholderText('ID, @username или имя группы')).toBeTruthy()
    expect(screen.queryByRole('heading', { name: /Изменить число/ })).toBeNull()

    fireEvent.click(screen.getByRole('tab', { name: 'Донатеры' }))
    expect(screen.queryByPlaceholderText('ID, @username или имя группы')).toBeNull()
    expect(await screen.findByText('Иван')).toBeTruthy()
    expect(screen.getByText('40 кут')).toBeTruthy()
  })

  it('shows the current number before a save', async () => {
    render(<StatDesk />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Донатеры' }))
    fireEvent.click(await screen.findByRole('button', { name: 'выбрать Ивана' }))
    expect(await screen.findByText('в базе 40')).toBeTruthy()
    expect(screen.getByText('люди видят 40')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeTruthy()
  })
})
