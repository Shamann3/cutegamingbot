import { useEffect, useState } from 'react'
import { fetchCaptchaArchiveStat } from '../lib/adminClient'

function fmt(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0'
  return n.toLocaleString('ru-RU')
}

/** Короткая строка: скольких людей убрала капча. */
export default function CaptchaArchiveNote({ stat = null, load = false }) {
  const [own, setOwn] = useState(null)

  useEffect(() => {
    if (!load) return undefined
    let alive = true
    fetchCaptchaArchiveStat()
      .then((data) => {
        if (alive) setOwn(data || null)
      })
      .catch(() => {
        if (alive) setOwn(null)
      })
    return () => {
      alive = false
    }
  }, [load])

  const view = stat || own
  if (!view) return null

  return (
    <p className="cap-archive-note" aria-label="Кого убрала капча">
      <span><strong>{fmt(view.people)}</strong> убрала капча</span>
      <span><strong>{fmt(view.month)}</strong> за 30 дней</span>
      <span><strong>{fmt(view.active)}</strong> сейчас в бане</span>
    </p>
  )
}
