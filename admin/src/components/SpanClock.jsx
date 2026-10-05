import { useState } from 'react'
import {
  SPAN_FLOOR_SEC,
  SPAN_MAX_SEC,
  SPAN_PRESETS,
  carrySpan,
  spanToSend,
  speakSpan,
  splitSpan,
  sumSpan,
} from '../lib/spanClock'

const FIELDS = [
  { id: 'seconds', label: 'Секунды', short: 'секунды' },
  { id: 'minutes', label: 'Минуты', short: 'минуты' },
  { id: 'hours', label: 'Часы', short: 'часы' },
  { id: 'days', label: 'Дни', short: 'дни' },
]

function draftFrom(total) {
  const parts = splitSpan(total)
  return {
    days: String(parts.days),
    hours: String(parts.hours),
    minutes: String(parts.minutes),
    seconds: String(parts.seconds),
  }
}

function digits(value) {
  return String(value || '').replace(/\D/g, '').slice(0, 4)
}

export default function SpanClock({ seconds = 3600, onChange }) {
  const [precise, setPrecise] = useState(false)
  const [draft, setDraft] = useState(() => draftFrom(seconds))
  const raw = sumSpan(draft)
  const sent = spanToSend(raw)
  const spoken = sent ? `Держать ${speakSpan(sent)}` : 'Нужен срок больше нуля'
  const note = raw > SPAN_MAX_SEC
    ? 'Дольше 366 дней нельзя.'
    : raw > 0 && raw < SPAN_FLOOR_SEC
      ? 'Короче 35 секунд Telegram считает вечным, поэтому уйдёт на 35.'
      : ''

  const publish = (nextDraft) => {
    setDraft(nextDraft)
    onChange?.(sumSpan(nextDraft))
  }

  const pick = (sec) => {
    const next = draftFrom(sec)
    setDraft(next)
    onChange?.(sec)
  }

  const flush = () => {
    const carried = carrySpan(draft)
    const next = draftFrom(carried.total)
    setDraft(next)
    onChange?.(carried.total)
  }

  return (
    <div className="span-clock">
      <p className="person-issue-title">Сколько держать</p>
      <div className="person-acts" role="group" aria-label="Срок">
        {SPAN_PRESETS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={raw === item.sec ? 'is-on' : ''}
            aria-pressed={raw === item.sec}
            onClick={() => pick(item.sec)}
          >
            {item.label}
          </button>
        ))}
        <button
          type="button"
          className={precise ? 'is-open' : ''}
          aria-expanded={precise}
          onClick={() => setPrecise((open) => !open)}
        >
          До секунды
        </button>
      </div>
      {precise && (
        <div className="span-precise">
          <div className="span-parts">
            {FIELDS.map((field) => (
              <label key={field.id}>
                <input
                  aria-label={field.label}
                  inputMode="numeric"
                  autoComplete="off"
                  value={draft[field.id]}
                  onChange={(event) => publish({ ...draft, [field.id]: digits(event.target.value) })}
                  onBlur={flush}
                />
                <span>{field.short}</span>
              </label>
            ))}
          </div>
        </div>
      )}
      <p className="span-read" key={spoken}>{spoken}</p>
      {note ? <p className="span-note">{note}</p> : null}
    </div>
  )
}
