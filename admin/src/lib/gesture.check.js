import { swipeAxis, tapVerdict } from './gesture.js'

function assert(cond, message) {
  if (!cond) throw new Error(message)
}

assert(swipeAxis(3, 4) === null, 'дрожь пальца ещё не жест')
assert(swipeAxis(20, 3) === 'x', 'вбок — карточка')
assert(swipeAxis(-20, 3) === 'x', 'влево — тоже карточка')
assert(swipeAxis(3, 20) === 'y', 'вверх-вниз — страница')
assert(swipeAxis(10, 10) === 'y', 'ровно наискось — страница')
assert(swipeAxis(11, 10) === 'y', 'почти наискось — всё ещё страница')
assert(swipeAxis(14, 10) === 'x', 'заметно вбок — карточка')

const still = { kind: 'touch', moved: false, scrolledBefore: false, scrolledDuring: false }
assert(tapVerdict(still) === 'tap', 'неподвижное касание — нажатие')
assert(tapVerdict({ ...still, moved: true }) === 'scroll', 'палец поехал — не нажатие')
assert(tapVerdict({ ...still, scrolledBefore: true }) === 'scroll', 'остановка ленты — не нажатие')
assert(tapVerdict({ ...still, scrolledDuring: true }) === 'scroll', 'лента поехала под пальцем — не нажатие')
assert(tapVerdict({ ...still, kind: 'mouse', scrolledBefore: true }) === 'tap', 'мышь после колёсика нажимает')
assert(tapVerdict({ ...still, kind: 'mouse', moved: true }) === 'scroll', 'мышь протащили — не нажатие')

console.log('gesture ok')
