import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OwnKeyControl from './OwnKeyControl'
import { doorKeyLine } from '../lib/doorKeys'

vi.mock('../lib/adminClient', () => ({
  isPanelPreviewMode: () => false,
  fetchMyDoorKeys: vi.fn(),
}))

import { fetchMyDoorKeys } from '../lib/adminClient'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('doorKeyLine', () => {
  it('не подставляет чужой текст вместо отсутствующего ключа', () => {
    expect(doorKeyLine('staff', 'none')).toMatch(/нет/)
    expect(doorKeyLine('group', 'closed')).toMatch(/не действует/)
    expect(doorKeyLine('staff', 'server')).toMatch(/не показывает/)
  })
})

describe('OwnKeyControl', () => {
  it('открывает оба своих ключа изнутри панели', async () => {
    vi.mocked(fetchMyDoorKeys).mockResolvedValue({
      staff: { state: 'ready', key: 'staff-key-1' },
      group: { state: 'ready', key: 'group-key-1' },
    })
    render(<OwnKeyControl />)
    fireEvent.click(screen.getByRole('button', { name: /Мой ключ/ }))
    expect(await screen.findByText('staff-key-1')).toBeTruthy()
    expect(screen.getByText('group-key-1')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Панель сотрудника' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Панель администратора' })).toBeTruthy()
    expect(fetchMyDoorKeys).toHaveBeenCalledTimes(1)
  })
})
