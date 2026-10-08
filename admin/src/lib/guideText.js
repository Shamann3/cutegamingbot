/**
 * Разметка подсказок входа из entry_design.js.
 * Без React и DOM, поэтому проверяется обычным node.
 */

const TAG_RE = /<(\/?)(b|i|u|code)>/g

/** Строка с <b> <i> <u> <code> → строки и узлы { tag, kids }. Прочее остаётся текстом. */
export function inlineParts(text) {
  const src = String(text ?? '')
  const root = { tag: '', kids: [] }
  const stack = [root]
  const top = () => stack[stack.length - 1]
  let last = 0
  TAG_RE.lastIndex = 0
  let match = TAG_RE.exec(src)
  while (match) {
    if (match.index > last) top().kids.push(src.slice(last, match.index))
    last = match.index + match[0].length
    const closing = match[1] === '/'
    const tag = match[2]
    if (!closing) {
      const node = { tag, kids: [] }
      top().kids.push(node)
      stack.push(node)
    } else {
      let at = -1
      for (let i = stack.length - 1; i > 0; i -= 1) {
        if (stack[i].tag === tag) {
          at = i
          break
        }
      }
      if (at > 0) stack.length = at
      else top().kids.push(match[0])
    }
    match = TAG_RE.exec(src)
  }
  if (last < src.length) top().kids.push(src.slice(last))
  return root.kids
}

const STEP_RE = /^(\d+)[.)]\s+/
const ITEM_RE = /^•\s*/

/**
 * Текст «Подробнее» → блоки по порядку:
 * { kind: 'head' | 'para' | 'steps' | 'list', lines: [...], start? }.
 */
export function blocksOf(text) {
  const blocks = []
  let current = null
  const flush = () => {
    if (current) blocks.push(current)
    current = null
  }
  for (const raw of String(text ?? '').split('\n')) {
    const line = raw.trim()
    if (!line) {
      flush()
      continue
    }
    if (line.startsWith('# ')) {
      flush()
      blocks.push({ kind: 'head', lines: [line.slice(2).trim()] })
      continue
    }
    const step = line.match(STEP_RE)
    let kind = 'para'
    let body = line
    if (step) {
      kind = 'steps'
      body = line.slice(step[0].length)
    } else if (ITEM_RE.test(line)) {
      kind = 'list'
      body = line.replace(ITEM_RE, '')
    }
    if (!current || current.kind !== kind) {
      flush()
      current = { kind, lines: [] }
      if (step) current.start = Number(step[1])
    }
    current.lines.push(body)
  }
  flush()
  return blocks
}

/** Состояние каждого шага: 'done' — позади, 'now' — сейчас, 'later' — впереди. */
export function stepStates(steps, at) {
  const list = Array.isArray(steps) ? steps : []
  const index = list.findIndex((step) => step.id === at)
  const now = index < 0 ? 0 : index
  return list.map((_, i) => (i < now ? 'done' : i === now ? 'now' : 'later'))
}
