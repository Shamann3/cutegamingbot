import { StrictMode } from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import StaffPunishRole from './StaffPunishRole'
import { showToast } from './ToastHost'
import { fetchStaffPunishRights, saveStaffPunishRights } from '../lib/adminClient'

vi.mock('../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchStaffPunishRights: vi.fn(),
  saveStaffPunishRights: vi.fn(),
}))

vi.mock('./ToastHost', () => ({ showToast: vi.fn() }))

const RIGHTS = {
  columns: ['mute', 'ban', 'banfull'],
  roles: [
    { role: 'senior_admin', title: 'Старший админ', importance: 4, permissions: { mute: true, ban: true, banfull: false }, locked: false },
    { role: 'moderator', title: 'Модератор', importance: 2, permissions: { mute: true, ban: false, banfull: false }, locked: false },
  ],
  problem: null,
}

const switchFor = async (label) => (await screen.findByText(label, { selector: 'strong' })).closest('button')

afterEach(() => {
  cleanup()
})

describe('StaffPunishRole', () => {
  it('offers a retry instead of the staff_rules hint when the server fails', async () => {
    vi.mocked(fetchStaffPunishRights)
      .mockRejectedValueOnce(new Error('Сервер API не ответил (ошибка 503). Повторите через минуту.'))
      .mockResolvedValueOnce(RIGHTS)
    render(<StaffPunishRole role="senior_admin" />)

    expect((await screen.findByRole('alert')).textContent).toContain('ошибка 503')
    expect(screen.queryByText(/называется иначе|нет строки/)).toBeNull()
    expect(screen.queryByRole('switch')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await switchFor('Мут')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(fetchStaffPunishRights).toHaveBeenCalledTimes(2)
  })

  it('keeps the newest answer when an older request fails later', async () => {
    let failOlder
    vi.mocked(fetchStaffPunishRights)
      .mockImplementationOnce(() => new Promise((_, reject) => { failOlder = reject }))
      .mockResolvedValueOnce(RIGHTS)
    render(<StrictMode><StaffPunishRole role="senior_admin" /></StrictMode>)

    expect(await switchFor('Мут')).toBeTruthy()
    await act(async () => failOlder(new Error('Сервер API не ответил (ошибка 503). Повторите через минуту.')))
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getAllByRole('switch')).toHaveLength(3)
    expect(fetchStaffPunishRights).toHaveBeenCalledTimes(2)
  })

  it('saves only the switched punishment and confirms it', async () => {
    vi.mocked(fetchStaffPunishRights).mockResolvedValue(RIGHTS)
    vi.mocked(saveStaffPunishRights).mockResolvedValue({
      ok: true,
      role: { ...RIGHTS.roles[0], permissions: { mute: true, ban: false, banfull: false } },
    })
    render(<StaffPunishRole role="senior_admin" />)

    const ban = await switchFor('Бан')
    expect(screen.getByText(/нельзя обойти/)).toBeTruthy()
    expect(screen.getByText('Старший админ')).toBeTruthy()
    expect(screen.queryByRole('navigation', { name: 'Строки staff_rules' })).toBeNull()
    expect(ban.getAttribute('aria-checked')).toBe('true')

    fireEvent.click(ban)
    expect(saveStaffPunishRights).toHaveBeenCalledWith('senior_admin', { ban: false })
    await waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('Сохранено для «Старший админ». Бот применит изменение в течение минуты.')
    })
    expect(ban.getAttribute('aria-checked')).toBe('false')
  })

  it('confirms a burst of changes to one position once', async () => {
    vi.mocked(fetchStaffPunishRights).mockResolvedValue(RIGHTS)
    vi.mocked(saveStaffPunishRights).mockResolvedValue({ ok: true })
    render(<StaffPunishRole role="senior_admin" />)

    const mute = await switchFor('Мут')
    const banfull = await switchFor('Банфулл')
    fireEvent.click(mute)
    fireEvent.click(banfull)
    await waitFor(() => {
      expect(mute.disabled).toBe(false)
      expect(banfull.disabled).toBe(false)
    })
    expect(saveStaffPunishRights).toHaveBeenCalledTimes(2)
    expect(showToast).toHaveBeenCalledTimes(1)
  })

  it('puts the switch back and explains when saving fails', async () => {
    vi.mocked(fetchStaffPunishRights).mockResolvedValue(RIGHTS)
    vi.mocked(saveStaffPunishRights).mockRejectedValue(new Error('База не приняла изменение. Подробности в логах сервера.'))
    render(<StaffPunishRole role="senior_admin" />)

    const mute = await switchFor('Мут')
    fireEvent.click(mute)
    await waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('База не приняла изменение. Подробности в логах сервера.', 'error')
    })
    expect(mute.getAttribute('aria-checked')).toBe('true')
    expect(mute.disabled).toBe(false)
    expect(screen.getAllByRole('switch')).toHaveLength(3)
  })

  it('lets the creator pick a row when the panel role has none', async () => {
    vi.mocked(fetchStaffPunishRights).mockResolvedValue(RIGHTS)
    render(<StaffPunishRole role="junior_admin" />)

    expect(await screen.findByText(/нет строки в staff_rules/)).toBeTruthy()
    expect(screen.queryByRole('switch')).toBeNull()
    const rows = screen.getByRole('navigation', { name: 'Строки staff_rules' })
    fireEvent.click(within(rows).getByRole('button', { name: 'Модератор' }))
    expect(screen.getAllByRole('switch')).toHaveLength(3)
  })

  it('explains a broken staff_rules table without calling it a network error', async () => {
    vi.mocked(fetchStaffPunishRights).mockResolvedValue({
      columns: [],
      roles: [],
      problem: 'В базе нет таблицы staff_rules: бот не знает, кому можно наказывать.',
    })
    render(<StaffPunishRole role="senior_admin" />)

    expect(await screen.findByText(/нет таблицы staff_rules/)).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByRole('button', { name: 'Проверить снова' })).toBeTruthy()
  })
})
