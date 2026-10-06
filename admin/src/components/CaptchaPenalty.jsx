import { useEffect, useMemo, useState } from 'react'
import RightSwitch from './RightSwitch'
import SpanClock from './SpanClock'
import { fetchCaptchaPenalty, saveCaptchaPenalty } from '../lib/adminClient'
import { notifyAdmin } from '../lib/notify'
import { speakSpan } from '../lib/spanClock'

export default function CaptchaPenalty() {
  const [pack, setPack] = useState(null)
  const [enabled, setEnabled] = useState(false)
  const [strikes, setStrikes] = useState('5')
  const [action, setAction] = useState('mute')
  const [seconds, setSeconds] = useState(3600)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let stop = false
    fetchCaptchaPenalty()
      .then((data) => {
        if (stop || !data) return
        setPack(data)
        setEnabled(Boolean(data.enabled))
        setStrikes(String(data.strikes || 5))
        setAction(data.action || 'mute')
        setSeconds(Number(data.seconds) || 3600)
      })
      .catch((err) => {
        if (!stop) setError(err.message || 'Наказание капчи не открылось')
      })
    return () => { stop = true }
  }, [])

  const cards = pack?.cards || []
  const selected = cards.find((item) => item.id === action) || null
  const places = useMemo(() => {
    const order = []
    const map = new Map()
    cards.forEach((item) => {
      if (!map.has(item.place)) {
        map.set(item.place, [])
        order.push(item.place)
      }
      map.get(item.place).push(item)
    })
    return order.map((place) => ({ place, items: map.get(place) }))
  }, [cards])

  const count = Number(strikes)
  const spoken = selected?.needsUntil ? speakSpan(seconds) : ''
  const preview = !enabled
    ? 'Сейчас серия ошибок никого не наказывает.'
    : `После ${Number.isInteger(count) ? count : '…'} ошибок подряд — ${selected?.label || 'наказание'}${spoken ? `, ${spoken}` : ''}. ${selected?.place || ''}.`

  const save = async () => {
    if (!Number.isInteger(count) || count < 1 || count > 20) {
      setError('Ошибок подряд — от 1 до 20')
      return
    }
    setBusy(true)
    setError('')
    try {
      const saved = await saveCaptchaPenalty({
        enabled,
        strikes: count,
        action,
        seconds: selected?.needsUntil ? seconds : 0,
      })
      setPack(saved)
      setEnabled(Boolean(saved.enabled))
      notifyAdmin(saved.sentence || 'Наказание капчи записано')
    } catch (err) {
      setError(err.message || 'Наказание не записалось')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="grp-card cap-penalty">
      <h3 className="grp-card-title">Наказание за капчу</h3>
      <p className="grp-help">Одно правило на все группы. Человек несколько раз подряд выбирает не тот ответ на одной карточке — выдаётся одно наказание. Дальше эта карточка его не повторяет. Правильный ответ начинает счётчик заново.</p>
      {error ? <p className="realm-alert" role="alert">{error}</p> : null}
      <RightSwitch
        on={enabled}
        title="Наказывать за серию ошибок"
        hint="Пока выключено, неверный ответ только меняет карточку."
        onChange={setEnabled}
      />
      <label className="cap-strikes">Сколько ошибок подряд
        <input
          inputMode="numeric"
          aria-label="Сколько ошибок подряд"
          value={strikes}
          onChange={(event) => setStrikes(event.target.value.replace(/\D/g, '').slice(0, 2))}
        />
      </label>
      {places.map((group) => (
        <div key={group.place} className="cap-place">
          <h4>{group.place}</h4>
          {group.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`cap-pick${action === item.id ? ' is-on' : ''}`}
              aria-pressed={action === item.id}
              onClick={() => setAction(item.id)}
            >
              <strong>{item.label}</strong>
              <span>{item.hint}</span>
            </button>
          ))}
        </div>
      ))}
      {selected?.needsUntil ? <SpanClock seconds={seconds} onChange={setSeconds} /> : null}
      <p className="grp-help">{preview}</p>
      <button type="button" className="sec-btn" disabled={busy || !pack} onClick={save}>
        {busy ? 'Записываем…' : 'Записать наказание'}
      </button>
    </section>
  )
}
