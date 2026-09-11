import { useMemo, useState } from 'react'

const UNITS = [
  { id: 'sec', label: 'сек', sec: 1 },
  { id: 'min', label: 'мин', sec: 60 },
  { id: 'hour', label: 'час', sec: 3600 },
  { id: 'day', label: 'день', sec: 86400 },
  { id: 'week', label: 'нед', sec: 604800 },
  { id: 'month', label: 'мес', sec: 2592000 },
  { id: 'year', label: 'год', sec: 31536000 },
]

const PRESETS = [
  { label: '1ч', sec: 3600 },
  { label: '6ч', sec: 21600 },
  { label: '24ч', sec: 86400 },
  { label: '3д', sec: 259200 },
  { label: '7д', sec: 604800 },
  { label: '30д', sec: 2592000 },
  { label: 'навсегда', sec: 0 },
]

function toLocalInputValue(date) {
  const d = date instanceof Date ? date : new Date(date)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * Срок наказания: длительность (любые единицы) или точная дата снятия.
 * onChange(untilSec | null) — null/0 = навсегда.
 */
export default function DurationUntil({ valueSec = 3600, onChange, allowForever = true }) {
  const [mode, setMode] = useState('duration') // duration | date
  const [amount, setAmount] = useState(() => {
    const v = Number(valueSec) || 0
    if (v <= 0) return 0
    if (v % 86400 === 0) return v / 86400
    if (v % 3600 === 0) return v / 3600
    if (v % 60 === 0) return v / 60
    return v
  })
  const [unit, setUnit] = useState(() => {
    const v = Number(valueSec) || 0
    if (v <= 0) return 'hour'
    if (v % 86400 === 0) return 'day'
    if (v % 3600 === 0) return 'hour'
    if (v % 60 === 0) return 'min'
    return 'sec'
  })
  const [dateVal, setDateVal] = useState(() => {
    const v = Number(valueSec) || 0
    if (v <= 0) return ''
    return toLocalInputValue(Date.now() + v * 1000)
  })

  const unitMeta = UNITS.find((u) => u.id === unit) || UNITS[2]

  const emitDuration = (nextAmount, nextUnit) => {
    const u = UNITS.find((x) => x.id === nextUnit) || unitMeta
    const a = Math.max(0, Number(nextAmount) || 0)
    const sec = Math.round(a * u.sec)
    onChange?.(sec)
  }

  const emitDate = (raw) => {
    setDateVal(raw)
    if (!raw) {
      onChange?.(0)
      return
    }
    const ts = new Date(raw).getTime()
    if (Number.isNaN(ts)) return
    const sec = Math.max(0, Math.round((ts - Date.now()) / 1000))
    onChange?.(sec)
  }

  const human = useMemo(() => {
    const sec = Number(valueSec) || 0
    if (sec <= 0) return 'навсегда'
    if (sec < 60) return `${sec} сек`
    if (sec < 3600) return `${Math.round(sec / 60)} мин`
    if (sec < 86400) return `${Math.round(sec / 3600)} ч`
    if (sec < 604800) return `${Math.round(sec / 86400)} д`
    if (sec < 2592000) return `${Math.round(sec / 604800)} нед`
    if (sec < 31536000) return `${Math.round(sec / 2592000)} мес`
    return `${(sec / 31536000).toFixed(1)} г`
  }, [valueSec])

  return (
    <div className="dur-field">
      <div className="dur-modes">
        <button
          type="button"
          className={`dur-mode${mode === 'duration' ? ' is-on' : ''}`}
          onClick={() => setMode('duration')}
        >
          Длительность
        </button>
        <button
          type="button"
          className={`dur-mode${mode === 'date' ? ' is-on' : ''}`}
          onClick={() => setMode('date')}
        >
          Дата снятия
        </button>
      </div>

      {mode === 'duration' ? (
        <>
          <div className="dur-row">
            <input
              type="number"
              min={0}
              step={1}
              value={amount}
              onChange={(e) => {
                const a = e.target.value
                setAmount(a)
                emitDuration(a, unit)
              }}
            />
            <select
              value={unit}
              onChange={(e) => {
                setUnit(e.target.value)
                emitDuration(amount, e.target.value)
              }}
            >
              {UNITS.map((u) => (
                <option key={u.id} value={u.id}>{u.label}</option>
              ))}
            </select>
            <strong className="dur-human">{human}</strong>
          </div>
          <div className="grp-chip-row">
            {PRESETS.filter((p) => allowForever || p.sec > 0).map((p) => (
              <button
                key={p.label}
                type="button"
                className={`grp-chip${Number(valueSec) === p.sec ? ' grp-chip-on' : ''}`}
                onClick={() => {
                  onChange?.(p.sec)
                  if (p.sec <= 0) {
                    setAmount(0)
                    setUnit('hour')
                  } else if (p.sec % 86400 === 0) {
                    setAmount(p.sec / 86400)
                    setUnit('day')
                  } else {
                    setAmount(p.sec / 3600)
                    setUnit('hour')
                  }
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </>
      ) : (
        <label className="grp-field">
          <span>Снять автоматически</span>
          <input
            type="datetime-local"
            value={dateVal}
            min={toLocalInputValue(Date.now() + 60_000)}
            onChange={(e) => emitDate(e.target.value)}
          />
          <strong className="dur-human" style={{ marginTop: 4 }}>{human}</strong>
        </label>
      )}
    </div>
  )
}
