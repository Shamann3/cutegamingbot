import { portraitFrom, punishmentHours } from './gateRecovery.js'

function assert(cond, message) {
  if (!cond) throw new Error(message)
}

const owner = portraitFrom({ isOwner: true, role: null, status: null })
assert(owner.staffCanEnter && owner.groupCanEnter, 'создатель открывает обе двери')

const staff = portraitFrom({ role: 'moderator', status: 'active', isOwner: false })
assert(staff.staffCanEnter && !staff.groupCanEnter, 'сотрудник без групп не открывает кабинет групп')

const pending = portraitFrom({ role: 'applicant', status: 'pending', applicationStatus: 'pending' })
assert(!pending.staffCanEnter && pending.applicationStatus === 'pending', 'заявка не пускает в панель')

const stranger = portraitFrom(null)
assert(!stranger.staffCanEnter && !stranger.groupCanEnter, 'пустой ответ закрывает обе двери')

const broken = portraitFrom({ groups: 'nope', staffCanEnter: false, groupCanEnter: false })
assert(Array.isArray(broken.groups) && broken.groups.length === 0, 'битый список групп не роняет двери')

assert(punishmentHours('1') === 3600, 'час')
assert(punishmentHours('1,5') === 5400, 'запятая')
assert(punishmentHours('0') === null, 'ноль')
assert(punishmentHours('') === null, 'пусто')
assert(punishmentHours('abc') === null, 'текст')
assert(punishmentHours('100000') === null, 'слишком долго')

console.log('gateRecovery ok')
