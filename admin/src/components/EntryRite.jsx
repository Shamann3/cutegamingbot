import { useEffect, useRef, useState } from 'react'

const FAULTS = [
  ['связь оборвана', 'связь есть'],
  ['ключ не тот', 'ключ ваш'],
  ['цифры не сошлись', 'цифры сошлись'],
  ['устройство чужое', 'устройство это'],
  ['должность снята', 'должность на месте'],
  ['панель закрыта', 'панель открыта'],
  ['проверка с ошибкой', 'проверка верна'],
  ['вход отказан', 'вход разрешён'],
]

function riteClock() {
  const still = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
  const lite = document.body.classList.contains('perf-light')
    || (navigator.hardwareConcurrency || 4) <= 2
  if (still) return { still: true, spell: 0, dark: 0, step: 0, tail: 400 }
  if (lite) return { still: false, spell: 640, dark: 260, step: 140, tail: 280 }
  return { still: false, spell: 1180, dark: 460, step: 240, tail: 520 }
}

/**
 * Шесть цифр сходятся в шифр, экран гаснет, ошибки по одной становятся верными.
 * Дальше открывается обычная заставка входа.
 */
export default function EntryRite({ digits = '', onDone }) {
  const doneRef = useRef(onDone)
  doneRef.current = onDone
  const marks = String(digits || '').replace(/\D/g, '').slice(0, 6).split('')
  const [phase, setPhase] = useState('spell')
  const [healed, setHealed] = useState(0)

  useEffect(() => {
    const clock = riteClock()
    if (clock.still) {
      setPhase('faults')
      setHealed(FAULTS.length)
      const timer = window.setTimeout(() => doneRef.current?.(), clock.tail)
      return () => window.clearTimeout(timer)
    }
    const start = clock.spell + clock.dark
    const timers = [
      window.setTimeout(() => setPhase('dark'), clock.spell),
      window.setTimeout(() => setPhase('faults'), start),
    ]
    FAULTS.forEach((_, index) => {
      timers.push(window.setTimeout(() => setHealed(index + 1), start + 160 + index * clock.step))
    })
    timers.push(window.setTimeout(
      () => doneRef.current?.(),
      start + 160 + FAULTS.length * clock.step + clock.tail,
    ))
    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [])

  return (
    <div className={`rite is-${phase}`} role="status" aria-live="polite" aria-label="Вход открывается">
      <p className="rite-sr">Вход открывается</p>
      {phase !== 'faults' && (
        <div className="rite-spell" aria-hidden="true">
          <span className="rite-ring" />
          <p className="rite-cipher">
            {marks.map((mark, index) => (
              <span key={index} className="rite-digit" style={{ '--i': index }}>{mark}</span>
            ))}
          </p>
        </div>
      )}
      {phase === 'faults' && (
        <div className="rite-board" aria-hidden="true">
          <p className="rite-cipher rite-cipher-ghost">
            {marks.map((mark, index) => (
              <span key={index} className="rite-digit rite-digit-still">{mark}</span>
            ))}
          </p>
          <ol className="rite-faults">
            {FAULTS.map(([bad, ok], index) => (
              <li key={bad} className={index < healed ? 'is-healed' : 'is-fault'}>
                <span className="rite-mark">
                  <i className="rite-x" />
                  <i className="rite-dot" />
                </span>
                <span className="rite-bad">{bad}</span>
                <span className="rite-ok">{ok}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
