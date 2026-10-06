import { describe, expect, it } from 'vitest'
import {
  PUSH_GONE_REASON,
  PUSH_OWNER_REASON,
  PUSH_TWIN_REASON,
  planPush,
  pushDetail,
  pushNotice,
  pushPages,
  pushShiftLine,
  pushStateLabel,
} from './positionPush'

const MEMBER = [
  'can_send_messages',
  'can_send_photos',
  'can_send_videos',
  'can_send_audios',
  'can_send_documents',
  'can_send_voice_notes',
  'can_send_video_notes',
  'can_send_polls',
  'can_send_other_messages',
  'can_add_web_page_previews',
]
const VOICE = [...MEMBER, 'can_manage_video_chats']

function source() {
  return [
    { id: 1, title: 'Создатель группы', kind: 'post', rank: 5, ladder: 0, rights: [] },
    { id: 2, title: 'Администратор ГЧ', kind: 'post', rank: 4, ladder: 0, rights: VOICE, prefix: 'ГЧ', pages: null },
    {
      id: 3,
      title: 'Администратор',
      kind: 'post',
      rank: 3,
      ladder: 1,
      rights: ['view_members', 'view_archive', 'punish_mute', 'punish_ban', 'can_delete_messages', 'banfull'],
      pages: ['work', 'archive', 'activity'],
    },
    { id: 4, title: 'Модератор', kind: 'post', rank: 2, ladder: 2, rights: ['view_members', 'punish_mute', 'punish_warn'], pages: null },
    { id: 5, title: 'Хелпер', kind: 'post', rank: 1, ladder: 3, rights: ['view_members', 'punish_warn'], pages: null },
    { id: 6, title: 'Обычный пользователь', kind: 'member', rank: 0, ladder: 0, rights: MEMBER, pages: null },
    { id: 7, title: 'Спам блок', kind: 'spamblock', rank: 0, ladder: 0, rights: [], prefix: 'спам блок', pages: null },
  ]
}

function freshGroup() {
  return [
    { id: 11, title: 'Создатель группы', kind: 'post', rank: 5, ladder: 0, rights: [] },
    {
      id: 12,
      title: 'Администратор',
      kind: 'post',
      rank: 3,
      ladder: 0,
      rights: ['view_members', 'view_archive', 'punish_mute', 'punish_ban', 'punish_kick', 'punish_warn'],
      pages: null,
    },
    {
      id: 13,
      title: 'Модератор',
      kind: 'post',
      rank: 2,
      ladder: 0,
      rights: ['view_members', 'view_archive', 'punish_mute', 'punish_kick', 'punish_warn'],
      pages: null,
    },
    { id: 14, title: 'Хелпер', kind: 'post', rank: 1, ladder: 0, rights: ['view_members', 'punish_warn'], pages: null },
    { id: 15, title: 'Обычный пользователь', kind: 'member', rank: 0, ladder: 0, rights: MEMBER, pages: null },
    { id: 16, title: 'Спам блок', kind: 'spamblock', rank: 0, ladder: 0, rights: [], prefix: 'спам блок', pages: null },
  ]
}

const byTitle = (plan) => new Map(plan.items.map((item) => [item.title, item]))

describe('planPush', () => {
  it('lands the whole group as here and keeps the creator', () => {
    const plan = planPush({ source: source(), target: freshGroup(), ids: [1, 2, 3, 4, 5, 6, 7] })
    const items = byTitle(plan)
    expect(items.get('Создатель группы')).toMatchObject({ state: 'skip', reason: PUSH_OWNER_REASON })
    expect(items.get('Администратор ГЧ')).toMatchObject({ state: 'new', rank: 4, prefix: 'ГЧ' })
    expect(items.get('Администратор')).toMatchObject({ state: 'update', targetId: 12, rank: 3, changes: ['rights'] })
    expect(items.get('Администратор').added).toEqual(['can_delete_messages', 'banfull'])
    expect(items.get('Модератор')).toMatchObject({ state: 'update', changes: ['rights', 'pages'], rank: 2 })
    expect(items.get('Хелпер').state).toBe('same')
    expect(items.get('Обычный пользователь').state).toBe('same')
    expect(items.get('Спам блок').state).toBe('same')
    expect(plan.shifts).toEqual([])
    expect(plan.rewrite).toBe(true)
    expect(plan.changed).toBe(true)
    expect(plan.items.map((item) => item.title)).toEqual([
      'Создатель группы', 'Администратор ГЧ', 'Администратор', 'Модератор', 'Хелпер', 'Обычный пользователь', 'Спам блок',
    ])
  })

  it('puts one post next to the same neighbours as here', () => {
    const target = freshGroup()
    target[1].rank = 3
    target[2].rank = 4
    target[3].rank = 2
    const plan = planPush({ source: source(), target, ids: [4] })
    const moved = plan.items[0]
    expect(moved).toMatchObject({ title: 'Модератор', rankFrom: 4, rank: 3 })
    expect(moved.changes).toContain('rank')
    expect(plan.shifts).toEqual([{ id: 12, title: 'Администратор', from: 3, to: 4 }])
    expect(pushShiftLine(plan.shifts)).toBe('Сдвинутся: Администратор 3 → 4')
  })

  it('closes applications when they are open there and closed here', () => {
    const plan = planPush({
      source: [{ id: 5, title: 'Хелпер', kind: 'post', rank: 1, ladder: 0, rights: ['view_members'], accepting: false }],
      target: [{ id: 14, title: 'Хелпер', kind: 'post', rank: 1, ladder: 0, rights: ['view_members'], accepting: true }],
      ids: [5],
    })
    expect(plan.items[0]).toMatchObject({ state: 'update', changes: ['accepting'], accepting: false })
    expect(pushDetail(plan.items[0])).toEqual(['заявки на должность закроются'])
  })

  it('changes nothing when the place and the rights already match', () => {
    const plan = planPush({ source: source(), target: freshGroup(), ids: [5] })
    expect(plan.items.map((item) => item.state)).toEqual(['same'])
    expect(plan.rewrite).toBe(false)
    expect(plan.changed).toBe(false)
  })

  it('uses the rank from here when the groups share no posts', () => {
    const lone = [{ id: 1, title: 'Стажёр', kind: 'post', rank: 2, ladder: 0, rights: ['view_members'] }]
    const target = [
      { id: 21, title: 'Старший', kind: 'post', rank: 4, ladder: 0, rights: [] },
      { id: 22, title: 'Дежурный', kind: 'post', rank: 3, ladder: 1, rights: [] },
    ]
    const low = planPush({ source: lone, target, ids: [1] })
    expect(low.items[0]).toMatchObject({ state: 'new', rank: 2 })
    expect(low.shifts).toEqual([])
    const high = planPush({ source: [{ ...lone[0], rank: 4 }], target, ids: [1] })
    expect(high.items[0]).toMatchObject({ state: 'new', rank: 3 })
    expect(high.shifts).toEqual([{ id: 22, title: 'Дежурный', from: 3, to: 2 }])
  })

  it('never takes a name that belongs to another kind', () => {
    const rows = [
      { id: 1, title: 'Спам блок', kind: 'post', rank: 2, ladder: 0, rights: [] },
      { id: 2, title: 'создатель  группы', kind: 'post', rank: 3, ladder: 0, rights: [] },
      { id: 3, title: 'Хелпер', kind: 'post', rank: 1, ladder: 1, rights: [] },
      { id: 4, title: 'Хелпер', kind: 'post', rank: 1, ladder: 2, rights: [] },
    ]
    const plan = planPush({ source: rows, target: freshGroup(), ids: [1, 2, 3, 4, 99] })
    const reasons = new Map(plan.items.filter((item) => item.state === 'skip').map((item) => [item.sourceId, item.reason]))
    expect(reasons.get(99)).toBe(PUSH_GONE_REASON)
    expect(reasons.get(1)).toBe('Так в той группе называется спам-блок')
    expect(reasons.get(2)).toBe('Так в той группе называется создатель группы')
    expect(reasons.get(4)).toBe(PUSH_TWIN_REASON)
    expect(plan.items.find((item) => item.sourceId === 3).state).toBe('update')
  })

  it('matches member and spam block by kind and renames only into a free name', () => {
    const rows = source()
    rows[5].title = 'Участник'
    rows[6].prefix = ''
    const plan = planPush({ source: rows, target: freshGroup(), ids: [6, 7] })
    expect(plan.items[0]).toMatchObject({ title: 'Участник', targetId: 15, changes: ['title'] })
    expect(pushDetail(plan.items[0])).toEqual(['название: «Обычный пользователь» → «Участник»'])
    expect(plan.items[1].state).toBe('same')
    const target = [...freshGroup(), { id: 17, title: 'Участник', kind: 'post', rank: 1, ladder: 5, rights: [] }]
    const kept = planPush({ source: rows, target, ids: [6] })
    expect(kept.items[0]).toMatchObject({ state: 'same', title: 'Обычный пользователь' })
  })
})

describe('push wording', () => {
  it('names the rights, the tabs and the people that change', () => {
    const admin = planPush({ source: source(), target: freshGroup(), ids: [3] }).items[0]
    expect(pushDetail(admin, 2)).toEqual([
      'права: + Удалять сообщения, Банфулл · − Кик, Варн',
      'в Telegram права обновятся у 2 человек',
    ])
    expect(pushStateLabel(admin)).toBe('обновится')
    const moderator = planPush({ source: source(), target: freshGroup(), ids: [4] }).items[0]
    expect(pushDetail(moderator)).toEqual([
      'права: − Карточки, Кик',
      'вкладки: − Работа, Архив',
    ])
  })

  it('reads the server receipt without inventing numbers', () => {
    expect(pushNotice([
      { chatId: -1, title: 'A', created: [{ title: 'X' }], updated: [{ title: 'Y' }, { title: 'Z' }], telegram: { failed: 0 } },
      { chatId: -2, title: 'B', created: [], updated: [], same: [{ title: 'Y' }], telegram: { failed: 0 } },
      { chatId: -3, title: 'C', error: 'Эта группа больше не официальная' },
    ])).toBe('Перенесено в 1 группу: 1 новая, 2 обновлены. Не обновились: C.')
    expect(pushNotice([])).toBe('')
  })

  it('derives tabs from rights only while no list is saved', () => {
    expect([...pushPages(['view_archive'], null)].sort()).toEqual(['archive', 'work'])
    expect([...pushPages(['view_archive'], ['rights', 'pay', 'bogus'])]).toEqual(['rights', 'pay'])
  })
})
