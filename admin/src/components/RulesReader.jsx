import { useEffect, useRef, useState } from 'react'

const DWELL_MS = 700

export default function RulesReader({ messages, known, onKnown }) {
  const [seen, setSeen] = useState(() => new Set())
  const timers = useRef(new Map())
  const scroller = useRef(null)

  useEffect(() => {
    const root = scroller.current
    const nodes = root ? root.querySelectorAll('[data-rule-end]') : []
    if (!nodes.length) return undefined
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        const id = Number(entry.target.getAttribute('data-rule-end'))
        if (!Number.isFinite(id)) return
        const pending = timers.current.get(id)
        if (entry.isIntersecting && entry.intersectionRatio >= 0.9) {
          if (pending) return
          const timer = window.setTimeout(() => {
            timers.current.delete(id)
            setSeen((prev) => {
              if (prev.has(id)) return prev
              const next = new Set(prev)
              next.add(id)
              return next
            })
          }, DWELL_MS)
          timers.current.set(id, timer)
          return
        }
        if (pending) {
          window.clearTimeout(pending)
          timers.current.delete(id)
        }
      })
    }, { root, threshold: [0.9] })
    nodes.forEach((node) => observer.observe(node))
    return () => {
      observer.disconnect()
      timers.current.forEach((timer) => window.clearTimeout(timer))
      timers.current.clear()
    }
  }, [messages])

  const total = messages.length
  const read = messages.filter((item) => seen.has(item.id)).length
  const ready = total > 0 && read === total

  return (
    <div className="rules-reader">
      <p className="auth-form-lead">Прочитайте каждое сообщение из канала правил.</p>
      <p className="rules-progress">Прочитано {read} из {total}</p>
      <div className="rules-scroll" ref={scroller}>
        {messages.map((item) => (
          <article className="rules-message" key={item.id}>
            <p>{item.text}</p>
            <span className="rules-end" data-rule-end={item.id} />
          </article>
        ))}
      </div>
      <button
        type="button"
        className="auth-btn auth-btn-primary"
        disabled={!ready || known}
        onClick={onKnown}
      >
        {known ? 'Правила отмечены' : 'Я знаю правила'}
      </button>
      {!ready && (
        <p className="auth-form-lead">Кнопка откроется, когда дочитаете все сообщения.</p>
      )}
    </div>
  )
}
