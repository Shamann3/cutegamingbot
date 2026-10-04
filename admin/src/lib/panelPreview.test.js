import { describe, expect, it } from 'vitest'
import { splitDockSections, visibleSections } from '../constants/panelNav'
import {
  enabledPunish,
  groupCabinetTabs,
  groupPeople,
  groupPersonPreview,
  groupPositionPreview,
  previewAccessFromDefaults,
  previewStandIn,
  previewTitle,
  ruCount,
  staffMemberPreview,
  staffPreviewNav,
  staffRolePreview,
} from './panelPreview'

const ROLES = [
  { id: 'moderator', label: 'Модератор' },
  { id: 'senior_admin', label: 'Старший админ' },
]

const navIds = (preview, creatorId = null) => staffPreviewNav(preview, creatorId).map((item) => item.id)

describe('previewAccessFromDefaults', () => {
  it('keeps open pages and only the open inner tabs', () => {
    const access = previewAccessFromDefaults({
      users: true,
      economy: false,
      'staff.applications': true,
      'staff.salaries': false,
      staff: true,
    })
    expect(access.sections).toEqual(['users', 'staff'])
    expect(access.tabs.staff).toEqual(['applications'])
    expect(access.tabs.economy).toBeUndefined()
  })

  it('leaves a page without child keys unfiltered', () => {
    const access = previewAccessFromDefaults({ dashboard: true })
    expect(access.sections).toEqual(['dashboard'])
    expect(access.tabs.dashboard).toBeUndefined()
  })
})

describe('ruCount', () => {
  it('picks the Russian plural form', () => {
    const forms = ['раздел', 'раздела', 'разделов']
    expect(ruCount(1, ...forms)).toBe('1 раздел')
    expect(ruCount(3, ...forms)).toBe('3 раздела')
    expect(ruCount(5, ...forms)).toBe('5 разделов')
    expect(ruCount(11, ...forms)).toBe('11 разделов')
    expect(ruCount(21, ...forms)).toBe('21 раздел')
    expect(ruCount(114, ...forms)).toBe('114 разделов')
  })
})

describe('enabledPunish', () => {
  it('tells "not loaded" apart from "no punishments"', () => {
    expect(enabledPunish(null, 'moderator')).toBeNull()
    expect(enabledPunish([], 'moderator')).toEqual([])
  })

  it('returns only the switched-on punishments of that role', () => {
    const rows = [
      { role: 'moderator', permissions: { MUTE: true, ban: false, Kick: 1 } },
      { role: 'senior_admin', permissions: { banfull: true } },
    ]
    expect(enabledPunish(rows, 'moderator')).toEqual(['mute', 'kick'])
  })
})

describe('staff copy', () => {
  it('uses the access the server computes for a real login', () => {
    const data = {
      roles: ROLES,
      roleDefaults: { moderator: { economy: true } },
      rolePreview: {
        moderator: { sections: ['dashboard', 'users', 'economy', 'nika'], tabs: { users: ['search'] }, permissions: ['view_players'] },
      },
    }
    const preview = staffRolePreview(data, 'moderator', [{ role: 'moderator', permissions: { mute: true } }])
    expect(preview).toMatchObject({
      kind: 'staff',
      who: 'role',
      role: 'moderator',
      roleLabel: 'Модератор',
      tabs: { users: ['search'] },
      permissions: ['view_players'],
      staffPerms: ['mute'],
    })
    expect(navIds(preview)).toEqual(['dashboard', 'users'])
  })

  it('opens «Стафф» for whoever may configure panel access, but never the access matrix itself', () => {
    const data = {
      roles: ROLES,
      rolePreview: { senior_admin: { sections: ['dashboard'], tabs: {}, permissions: ['manage_panel_access'] } },
    }
    expect(navIds(staffRolePreview(data, 'senior_admin'))).toEqual(['dashboard', 'staff'])
  })

  it('falls back to role defaults when the server is older', () => {
    const data = {
      roles: ROLES,
      roleDefaults: { moderator: { users: true, economy: true, staff: true, 'staff.applications': true } },
    }
    const preview = staffRolePreview(data, 'moderator')
    expect(preview.permissions).toBeNull()
    expect(preview.staffPerms).toBeNull()
    expect(preview.tabs.staff).toEqual(['applications'])
    expect(navIds(preview)).toEqual(['users', 'economy', 'staff'])
  })

  it('copies one person with their own exceptions', () => {
    const member = {
      userId: 7,
      firstName: 'Иван',
      username: 'ivan',
      role: 'moderator',
      roleLabel: 'Модератор',
      effectiveSections: ['dashboard', 'users', 'groupGuard'],
      effectiveTabs: {},
      permissions: ['view_players'],
    }
    const preview = staffMemberPreview(member, [])
    expect(preview).toMatchObject({ who: 'person', name: 'Иван', userId: 7, staffPerms: [] })
    expect(navIds(preview, 42)).toEqual(['dashboard', 'users'])
  })

  it('names a person without a first name by username, then by ID', () => {
    expect(staffMemberPreview({ firstName: '  ', username: 'ivan', role: 'moderator' }).name).toBe('@ivan')
    expect(staffMemberPreview({ userId: 12, role: 'moderator' }).name).toBe('ID 12')
  })
})

describe('group cabinet copy', () => {
  it('shows the same cabinet pages the rights allow', () => {
    const ids = (rights, creator) => groupCabinetTabs(rights, creator).map((item) => item.id)
    expect(ids([])).toEqual(['overview', 'pay', 'more'])
    expect(ids(['punish_mute'])).toEqual(['overview', 'activity', 'pay', 'more'])
    expect(ids(new Set(['view_archive', 'manage_positions']))).toEqual(['overview', 'work', 'archive', 'rights', 'pay', 'more'])
    expect(ids([], true)).toEqual(['overview', 'work', 'archive', 'activity', 'rights', 'switches', 'pay', 'more'])
    expect(groupCabinetTabs(['view_archive'], false, ['archive'], 2).map((item) => item.id))
      .toEqual(['overview', 'archive', 'more'])
    expect(groupCabinetTabs(['view_archive'], false, [], 2).map((item) => item.id))
      .toEqual(['overview', 'more'])
    expect(groupCabinetTabs([], false, null, 5).map((item) => item.id))
      .toEqual(['overview', 'work', 'archive', 'activity', 'rights', 'pay', 'more'])
    expect(groupCabinetTabs([], false, ['work'], 0).map((item) => item.id))
      .toEqual(['overview', 'work', 'more'])
    expect(groupCabinetTabs([], false, ['archive'], 5).map((item) => item.id))
      .toEqual(['overview', 'archive', 'more'])
  })

  it('never treats the top position as the project creator', () => {
    const preview = groupPositionPreview(
      { chatId: -3, title: 'Чат', username: 'chat' },
      { id: 1, title: 'Глава', rank: 5, rights: ['punish_ban'] },
    )
    expect(preview.portrait).toEqual({
      isOwner: false,
      staffCanEnter: false,
      groups: [{ chatId: -3, title: 'Чат', username: 'chat', position: 'Глава', rank: 5, rights: ['punish_ban'] }],
    })
  })

  it('gathers one person across every group they hold a seat in', () => {
    const board = [
      {
        chatId: -1,
        title: 'Бета',
        username: 'beta',
        seats: [
          { userId: 5, name: 'Аня', username: 'anya', staff: true, position: 'Модератор', rank: 2, rights: ['punish_mute'] },
          { userId: 9, name: 'Борис', username: '', staff: false, position: 'Помощник', rank: 1, rights: [] },
        ],
      },
      {
        chatId: -2,
        title: 'Альфа',
        seats: [
          { userId: 5, name: 'Аня', username: 'anya', staff: true, position: 'Старший', rank: 4, rights: ['punish_ban'] },
        ],
      },
    ]
    const people = groupPeople(board)
    expect(people.map((person) => person.userId)).toEqual([5, 9])
    expect(people[0].groups.map((group) => group.title)).toEqual(['Альфа', 'Бета'])
    expect(people[0].groups[0]).toMatchObject({ chatId: -2, position: 'Старший', rank: 4, rights: ['punish_ban'] })

    const preview = groupPersonPreview(people[0])
    expect(preview.roleLabel).toBe('Старший')
    expect(preview.portrait).toEqual({ isOwner: false, staffCanEnter: true, groups: people[0].groups })
    expect(groupPersonPreview(people[1]).portrait.staffCanEnter).toBe(false)
  })
})

describe('copy strip and stand-in profile', () => {
  it('says whose panel is open', () => {
    expect(previewTitle({ kind: 'staff', who: 'role', roleLabel: 'Модератор' })).toBe('Копия панели сотрудника · Модератор')
    expect(previewTitle({ kind: 'staff', who: 'person', name: 'Иван', roleLabel: 'Модератор' }))
      .toBe('Копия панели сотрудника · Иван (Модератор)')
    expect(previewTitle({ kind: 'group', who: 'person', name: 'Аня', roleLabel: 'Старший' })).toBe('Копия кабинета группы · Аня')
    expect(previewTitle({ kind: 'group', who: 'role', roleLabel: 'Глава' })).toBe('Копия кабинета группы · Глава')
  })

  it('greets as the person, or as the position for a role copy', () => {
    expect(previewStandIn({ who: 'person', name: 'Иван', username: 'ivan', userId: 7, roleLabel: 'Модератор' }))
      .toEqual({ displayName: 'Иван', username: 'ivan', userId: 7 })
    expect(previewStandIn({ who: 'role', roleLabel: 'Модератор' }))
      .toEqual({ displayName: 'Модератор', username: null, userId: null })
    expect(previewStandIn(null)).toBeNull()
  })
})

describe('work sits with the main tabs', () => {
  it('puts work on the dock beside home, players and the archive', () => {
    const visible = visibleSections(
      ['view_players'],
      ['dashboard', 'work', 'users', 'moderation', 'support'],
      'moderator',
    )
    expect(splitDockSections(visible).dock.map((item) => item.id)).toEqual([
      'dashboard', 'work', 'users', 'moderation', 'more',
    ])
  })

  it('gives the creator a work tab and keeps the owner out of the staff check', () => {
    const creator = visibleSections([], null, 'senior_admin', { isProjectCreator: true })
    const owner = visibleSections([], null, 'owner')
    expect(creator.some((item) => item.id === 'work')).toBe(true)
    expect(owner.some((item) => item.id === 'work')).toBe(false)
  })
})
