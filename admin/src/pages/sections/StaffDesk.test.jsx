import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StaffSection from './StaffSection'
import StaffPreviewPane from './StaffPreviewPane'
import GroupPreviewPane from './GroupPreviewPane'
import { fetchPanelAccess, fetchRightsBoard, fetchStaffPunishRights } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchPanelAccess: vi.fn(),
  fetchStaffPunishRights: vi.fn(),
  fetchRightsBoard: vi.fn(),
}))

vi.mock('./StaffAccessPane', async () => {
  const { createElement } = await import('react')
  return { default: () => createElement('p', null, 'Настройка доступа') }
})

vi.mock('./RightsSection', async () => {
  const { createElement } = await import('react')
  return { default: () => createElement('p', null, 'Должности групп') }
})

vi.mock('./GroupApplicationsPane', async () => {
  const { createElement } = await import('react')
  return { default: () => createElement('p', null, 'Заявки в группу') }
})

const ACCESS = {
  roles: [
    { id: 'moderator', label: 'Модератор' },
    { id: 'senior_admin', label: 'Старший админ' },
  ],
  roleDefaults: {},
  rolePreview: {
    moderator: { sections: ['dashboard', 'users'], tabs: {}, permissions: ['view_players'] },
    senior_admin: { sections: [], tabs: {}, permissions: [] },
  },
  members: [
    {
      userId: 7,
      firstName: 'Иван',
      username: 'ivan',
      role: 'moderator',
      roleLabel: 'Модератор',
      effectiveSections: ['dashboard'],
      effectiveTabs: {},
      permissions: [],
      overrides: { users: false },
    },
  ],
}

const BOARD = {
  groups: [
    {
      chatId: -1,
      title: 'Альфа',
      username: 'alpha',
      positions: [
        { id: 1, title: 'Глава', rank: 5, rights: ['punish_ban', 'manage_positions'] },
        { id: 2, title: 'Помощник', rank: 1, rights: [] },
      ],
      seats: [
        { userId: 5, name: 'Аня', username: 'anya', staff: true, positionId: 1, position: 'Глава', rank: 5, rights: ['punish_ban', 'manage_positions'] },
      ],
    },
    { chatId: -2, title: 'Бета', positions: [], seats: [] },
  ],
}

const buttonLabels = (nav) => within(nav).getAllByRole('button').map((button) => button.textContent)

beforeEach(() => {
  vi.mocked(fetchPanelAccess).mockResolvedValue(ACCESS)
  vi.mocked(fetchStaffPunishRights).mockResolvedValue({ roles: [{ role: 'moderator', permissions: { mute: true, ban: false } }] })
  vi.mocked(fetchRightsBoard).mockResolvedValue(BOARD)
})

afterEach(() => {
  cleanup()
})

describe('StaffSection', () => {
  it('splits the creator desk into «Сотрудники» and «Администраторы», each with its own copy', async () => {
    const onOpenPreview = vi.fn()
    render(<StaffSection role="owner" isProjectCreator onOpenPreview={onOpenPreview} />)

    const staff = screen.getByRole('tab', { name: /Сотрудники/ })
    const admins = screen.getByRole('tab', { name: /Администраторы/ })
    expect(staff.getAttribute('aria-selected')).toBe('true')
    expect(screen.getByText('Настройка доступа')).toBeTruthy()
    const staffTabs = screen.getByRole('navigation', { name: 'Сотрудники' })
    expect(buttonLabels(staffTabs)).toEqual(['Доступ', 'Копия панели', 'Команда'])

    fireEvent.click(within(staffTabs).getByRole('button', { name: 'Копия панели' }))
    const card = (await screen.findByText('Модератор')).closest('li')
    fireEvent.click(within(card).getByRole('button', { name: 'Войти в копию' }))
    expect(onOpenPreview).toHaveBeenLastCalledWith(expect.objectContaining({ kind: 'staff', role: 'moderator' }))

    fireEvent.click(admins)
    expect(admins.getAttribute('aria-selected')).toBe('true')
    const groupTabs = screen.getByRole('navigation', { name: 'Администраторы' })
    expect(buttonLabels(groupTabs)).toEqual(['Должности', 'Копия кабинета', 'Заявки', 'Ключи'])
    expect(screen.getByText('Должности групп')).toBeTruthy()

    fireEvent.click(within(groupTabs).getByRole('button', { name: 'Копия кабинета' }))
    const post = (await screen.findByText('Глава')).closest('li')
    fireEvent.click(within(post).getByRole('button', { name: 'Войти в копию' }))
    expect(onOpenPreview).toHaveBeenLastCalledWith(expect.objectContaining({ kind: 'group', roleLabel: 'Глава' }))

    fireEvent.click(staff)
    expect(await screen.findByText('Модератор')).toBeTruthy()
  })

  it('comes back to the copy list after leaving a copy', async () => {
    render(<StaffSection role="owner" isProjectCreator onOpenPreview={vi.fn()} entry={{ office: 'group', slice: 'view' }} />)
    expect(screen.getByRole('tab', { name: /Администраторы/ }).getAttribute('aria-selected')).toBe('true')
    expect(await screen.findByText('Глава')).toBeTruthy()
  })

  it('shows a senior admin only the staff desk and no copies', () => {
    render(<StaffSection role="senior_admin" permissions={['manage_panel_access', 'review_applications']} onOpenPreview={vi.fn()} />)
    expect(screen.queryByRole('tablist')).toBeNull()
    expect(buttonLabels(screen.getByRole('navigation', { name: 'Сотрудники' }))).toEqual(['Доступ', 'Заявки', 'Команда'])
  })
})

describe('StaffPreviewPane', () => {
  it('lists every position with its menu and punishments', async () => {
    const onOpen = vi.fn()
    render(<StaffPreviewPane onOpen={onOpen} />)
    const card = (await screen.findByText('Модератор')).closest('li')
    expect(within(card).getByText('2 раздела')).toBeTruthy()
    expect(within(card).getByText('Главная')).toBeTruthy()
    expect(within(card).getByText('Игроки')).toBeTruthy()
    expect(within(card).getByText('Наказания: Мут')).toBeTruthy()
    const empty = screen.getByText('Старший админ').closest('li')
    expect(within(empty).getByText('Ни одного раздела — панель откроется пустой.')).toBeTruthy()

    fireEvent.click(within(card).getByRole('button', { name: 'Войти в копию' }))
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({
      who: 'role',
      role: 'moderator',
      permissions: ['view_players'],
      staffPerms: ['mute'],
    }))
  })

  it('opens one person and finds people by name, @username or ID', async () => {
    const onOpen = vi.fn()
    render(<StaffPreviewPane onOpen={onOpen} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Сотрудник · 1' }))
    const card = screen.getByText('Иван').closest('li')
    expect(within(card).getByText('@ivan · ID 7')).toBeTruthy()
    expect(within(card).getByText('1 раздел · 1 личное исключение')).toBeTruthy()

    fireEvent.click(within(card).getByRole('button', { name: 'Войти как Иван' }))
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ who: 'person', userId: 7, name: 'Иван' }))

    const search = screen.getByRole('searchbox', { name: 'Найти сотрудника' })
    fireEvent.change(search, { target: { value: '@IVAN' } })
    expect(screen.getByText('Иван')).toBeTruthy()
    fireEvent.change(search, { target: { value: 'пётр' } })
    expect(screen.getByText('Никто не подошёл под поиск')).toBeTruthy()
  })

  it('offers a retry when the list does not load', async () => {
    vi.mocked(fetchPanelAccess).mockRejectedValueOnce(new Error('Сервер не ответил'))
    render(<StaffPreviewPane onOpen={vi.fn()} />)
    expect(await screen.findByText('Сервер не ответил')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await screen.findByText('Модератор')).toBeTruthy()
  })
})

describe('GroupPreviewPane', () => {
  it('shows each position of the chosen group with its pages and seats', async () => {
    const onOpen = vi.fn()
    render(<GroupPreviewPane onOpen={onOpen} />)
    const head = (await screen.findByText('Глава')).closest('li')
    expect(within(head).getByText('Наказания: Бан')).toBeTruthy()
    expect(within(head).getByText('Права')).toBeTruthy()
    expect(within(head).getByText('На должности 1 человек')).toBeTruthy()
    expect(within(screen.getByText('Помощник').closest('li')).getByText('На должности пока никого')).toBeTruthy()

    fireEvent.click(within(head).getByRole('button', { name: 'Войти в копию' }))
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({
      kind: 'group',
      who: 'role',
      portrait: expect.objectContaining({ isOwner: false, groups: [expect.objectContaining({ chatId: -1, rank: 5 })] }),
    }))

    fireEvent.click(screen.getByRole('button', { name: 'Бета' }))
    expect(screen.getByText('В этой группе нет должностей. Создайте их во вкладке «Должности».')).toBeTruthy()
  })

  it('opens one administrator with every group they sit in', async () => {
    const onOpen = vi.fn()
    render(<GroupPreviewPane onOpen={onOpen} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Администратор · 1' }))
    const card = screen.getByText('Аня').closest('li')
    expect(within(card).getByText('@anya · ID 5 · ещё и сотрудник проекта')).toBeTruthy()
    expect(within(card).getByText('Альфа — Глава')).toBeTruthy()

    fireEvent.click(within(card).getByRole('button', { name: 'Войти как Аня' }))
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({
      who: 'person',
      userId: 5,
      portrait: expect.objectContaining({ staffCanEnter: true }),
    }))
  })

  it('says so when the server does not list administrators yet', async () => {
    vi.mocked(fetchRightsBoard).mockResolvedValueOnce({ groups: [{ chatId: -1, title: 'Альфа', positions: [] }] })
    render(<GroupPreviewPane onOpen={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Администратор' }))
    expect(await screen.findByText(/Сервер панели ещё не отдаёт список администраторов/)).toBeTruthy()
  })
})
