import { blocksOf, inlineParts, stepStates } from './guideText.js'
import { OFFICE_SCREENS, SCREENS, WORDS, t } from '../entry_design.js'

function assert(cond, message) {
  if (!cond) throw new Error(message)
}

const flat = (parts) => parts.map((part) => (typeof part === 'string' ? part : `[${part.tag}:${flat(part.kids)}]`)).join('')

assert(flat(inlineParts('Нажмите <b>«Войти»</b>.')) === 'Нажмите [b:«Войти»].', 'жирный')
assert(flat(inlineParts('<b>Ключ <u>шесть</u></b> цифр')) === '[b:Ключ [u:шесть]] цифр', 'вложенные теги')
assert(flat(inlineParts('a <script>x</script> b')) === 'a <script>x</script> b', 'чужие теги остаются текстом')
assert(flat(inlineParts('лишний </b> закрывающий')) === 'лишний </b> закрывающий', 'одинокий закрывающий тег — текст')
assert(flat(inlineParts('<i>не закрыт')) === '[i:не закрыт]', 'незакрытый тег держит хвост')
assert(flat(inlineParts('')) === '', 'пусто')

const blocks = blocksOf(t(`
  # Шаг 1
  Панель на компьютере:
  1. Откройте приложение.
  2. Нажмите «+».

  • первый
  • второй
  3. дальше
`))
assert(blocks.map((b) => b.kind).join(',') === 'head,para,steps,list,steps', 'порядок блоков')
assert(blocks[2].start === 1 && blocks[2].lines.length === 2, 'шаги по порядку')
assert(blocks[4].start === 3, 'нумерация продолжается с указанной цифры')
assert(blocks[3].lines[0] === 'первый', 'маркер списка срезан')

assert(stepStates([{ id: 'a' }, { id: 'b' }, { id: 'c' }], 'b').join(',') === 'done,now,later', 'текущий шаг')
assert(stepStates([{ id: 'a' }, { id: 'b' }], 'zzz').join(',') === 'now,later', 'незнакомый шаг — первый')

for (const [office, ids] of Object.entries(OFFICE_SCREENS)) {
  for (const id of ids) {
    const screen = SCREENS[id]
    assert(screen, `${office}: экран ${id} есть`)
    assert(screen.tab && screen.title && screen.more, `${id}: подписи на месте`)
    assert(screen.steps.length >= 2, `${id}: шагов хотя бы два`)
    assert(new Set(screen.steps.map((s) => s.id)).size === screen.steps.length, `${id}: id шагов не повторяются`)
    assert(blocksOf(screen.more).some((b) => b.kind === 'head'), `${id}: в «Подробнее» есть разделы`)
    assert(!screen.more.startsWith(' '), `${id}: отступ срезан`)
  }
}
assert(WORDS.enter === 'Войти' && WORDS.groupKey === 'Ключ кабинета' && WORDS.code === 'Код из приложения', 'подписи, на которые смотрят тесты')

console.log('guideText ok')
