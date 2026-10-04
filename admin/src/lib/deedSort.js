export const SORT_LABEL = {
  clear: 'Подходит',
  wrong: 'Неправильно',
  weak: 'Непонятно',
}

/** Полная подпись кнопки. На карточке и в архиве остаётся короткое «Неправильно». */
export const VERDICT_BUTTON = {
  clear: 'Подходит',
  wrong: 'Наказание выдано неправильно',
  weak: 'Непонятно',
}

export const BAND_LABEL = {
  photo: 'Есть фото',
  reason: 'Фото нет, есть причина',
  empty: 'Ни фото, ни причины',
}

export function sortLabel(verdict) {
  return SORT_LABEL[verdict] || ''
}

export function sortCountLine(counts) {
  const clear = Number(counts?.clear) || 0
  const wrong = Number(counts?.wrong) || 0
  const weak = Number(counts?.weak) || 0
  return `Подходит ${clear}. Неправильно ${wrong}. Непонятно ${weak}.`
}

export function payLabel(status) {
  if (status === 'kept') return 'В зарплате'
  if (status === 'dropped') return 'Не в зарплате'
  return ''
}

/** Кто проверял: «Анна: подходит», «Не смогли решить: Анна, Олег», «Некому было проверить». */
export function checkedBy(item) {
  const names = (item?.unclearNames || []).filter(Boolean)
  const precise = item?.sortVerdict && item.sortVerdict !== 'weak'
  if (precise) {
    const head = `${item.sorterName || 'Администратор'}: ${sortLabel(item.sortVerdict).toLowerCase()}`
    return names.length ? `${head} · до этого не смогли решить: ${names.join(', ')}` : head
  }
  if (names.length) return `Не смогли решить: ${names.join(', ')}`
  if (item?.sortVerdict === 'weak') return 'Не смогли решить'
  return 'Некому было проверить'
}

export function admins(n) {
  const num = Math.abs(Number(n) || 0)
  const n10 = num % 10
  const n100 = num % 100
  if (n10 === 1 && n100 !== 11) return `${num} администратор`
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return `${num} администратора`
  return `${num} администраторов`
}

export function punishments(n) {
  const num = Math.abs(Number(n) || 0)
  const n10 = num % 10
  const n100 = num % 100
  if (n10 === 1 && n100 !== 11) return 'наказание'
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return 'наказания'
  return 'наказаний'
}

const ROLE_WORD = {
  admin: 'администратор',
  staff: 'сотрудник',
}

/** «Анна (администратор): подходит · Игорь (сотрудник): неправильно». */
export function chainText(item) {
  const chain = Array.isArray(item?.chain) ? item.chain : []
  if (!chain.length) return ''
  return chain.map((step) => {
    const name = step?.name || 'Без имени'
    const role = ROLE_WORD[step?.role] || 'проверка'
    const word = (step?.label || sortLabel(step?.verdict) || 'ответ').toLowerCase()
    return `${name} (${role}): ${word}`
  }).join(' · ')
}

export function liftSuffix(item) {
  const status = item?.liftStatus || item?.lift?.status || ''
  if (status === 'lifted') return 'наказание снято'
  if (status === 'rejected') return 'заявка на разблокировку отклонена'
  if (status === 'pending') return 'заявка на разблокировку'
  return ''
}

/** Кто уже ответил, одной строкой. */
export function chainLine(item) {
  const head = chainText(item)
  const tail = liftSuffix(item)
  if (head && tail) return `${head} · ${tail}`
  if (head) return head
  if (tail) return tail
  return checkedBy(item)
}

export function openingOf(card) {
  if (card?.lift?.status === 'pending') {
    return {
      band: 'Заявка на разблокировку',
      tone: 'wrong',
      note: chainText(card) || `${card.lift.by || 'Сотрудник'} просит снять это наказание.`,
    }
  }
  const chain = card?.chain || []
  if (!chain.length) {
    return {
      band: 'Некому было проверить',
      tone: '',
      note: 'Администратора и сотрудника на эту карточку не нашлось. Решение сразу за вами.',
    }
  }
  const last = chain[chain.length - 1]
  const skipped = []
  if (!chain.some((step) => step.role === 'admin')) skipped.push('Администратор группы эту карточку не проверял.')
  if (!chain.some((step) => step.role === 'staff')) skipped.push('Сотрудник проекта эту карточку не проверял.')
  return {
    band: chainText(card),
    tone: last?.verdict || '',
    note: skipped.join(' '),
  }
}

export function creditHint(person) {
  if (person?.role === 'issue') {
    return 'Выдал наказание. Галочка засчитает его, если отправите карточку вправо.'
  }
  const who = person?.role === 'staff' ? 'Сотрудник проекта' : 'Администратор группы'
  if (person?.payable === 'never') {
    return `${who}: непонятно. В зарплату не входит — твёрдого ответа не было.`
  }
  if (person?.payable === 'drop') {
    return `${who}: наказание выдано неправильно. Галочка засчитает проверку, если отправите влево.`
  }
  return `${who}: подходит. Галочка засчитает проверку, если отправите вправо.`
}

/** Кого засчитать этим жестом. Снятая галочка исключает человека. */
export function chosenCredits(card, kind, off) {
  return (card?.credits || []).flatMap((person) => {
    if (person.payable === 'never') return []
    const hit = kind === 'keep' ? person.payable === 'keep' : person.payable === 'drop'
    if (!hit) return []
    if (off?.has?.(`${person.role}:${person.userId}`)) return []
    return [{ role: person.role, userId: person.userId }]
  })
}

export function people(n) {
  const num = Math.abs(Number(n) || 0)
  const n10 = num % 10
  const n100 = num % 100
  if (n10 === 1 && n100 !== 11) return `${num} человек`
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return `${num} человека`
  return `${num} человек`
}

/** «наказание ждёт вашей проверки», «наказания ждут вашего решения». */
export function waitCaption(n, tail) {
  const num = Math.abs(Number(n) || 0)
  const one = num % 10 === 1 && num % 100 !== 11
  return `${punishments(num)} ${one ? 'ждёт' : 'ждут'} ${tail}`
}
