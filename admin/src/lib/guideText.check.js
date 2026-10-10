import { blocksOf, inlineParts, stepStates } from './guideText.js'
import { AUTH_FIXES, AUTH_STEPS, AUTH_STORES, OFFICE_SCREENS, SCREENS, WORDS, t } from '../entry_design.js'

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
assert(AUTH_STEPS.length === 4, 'четыре картинки аутентификатора')
assert(new Set(AUTH_STEPS.map((step) => step.id)).size === 4, 'id картинок не повторяются')
for (const step of AUTH_STEPS) {
  assert(step.file.endsWith('.jpg') && step.title && step.line, `${step.id}: файл, заголовок и пояснение`)
  assert(step.line.split('\n').every((piece) => piece.trim()), `${step.id}: пустая строка после переноса`)
  assert(!/can_/.test(step.line), `${step.id}: пояснение без сырых прав`)
}
assert(AUTH_STEPS.find((step) => step.id === 'details').line.includes('\n'), 'перенос в подписи четвёртого кадра')
assert(WORDS.walkAsk === 'Я не знаю как зайти', 'кнопка первого входа')
assert(AUTH_STORES.length === 2, 'два магазина')
assert(AUTH_STORES.every((store) => store.href.startsWith('https://')), 'магазины — прямые ссылки')
assert(AUTH_FIXES.length >= 6, 'варианты, если не получается')
for (const fix of AUTH_FIXES) {
  assert(fix.ask && fix.do && fix.id, `${fix.id}: проблема и что сделать`)
}
assert(AUTH_FIXES.some((fix) => fix.stores), 'если приложения нет — кнопки магазинов')
assert(AUTH_FIXES.some((fix) => fix.copy), 'если ключ не тот — его можно скопировать')
assert(AUTH_FIXES.some((fix) => fix.clock && /код не подош/.test(fix.match)), 'неверный код сам предлагает дождаться новых цифр')

console.log('guideText ok')
