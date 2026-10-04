import { useCallback, useEffect, useState } from 'react'
import { fetchDeedAnalytics, isPanelPreviewMode, tuneDeedRates } from '../../../lib/adminClient'

function messageOf(error) {
  return error?.message || 'Подстройка не открылась'
}

export function TuneControls({ auto, busy, note, compact = false, onApply }) {
  const lead = note || (auto
    ? 'Группы сами держат нормы: за неделю зарплаты забирают не больше 15% их кут и не трогают последние 40%.'
    : 'Нормы зафиксированы вручную. Они не изменятся, пока не нажмёте «Подстроить сейчас».')
  return (
    <div className={`rate-tune${compact ? ' is-compact' : ''}`}>
      <p className="deed-lead">{lead}</p>
      <div className="rate-tune-row">
        <label className="deed-check">
          <input
            type="checkbox"
            checked={auto}
            disabled={Boolean(busy)}
            onChange={(event) => onApply(event.target.checked, false)}
          />
          <span>{auto ? 'Группы сами держат нормы' : 'Нормы зафиксированы вручную'}</span>
        </label>
        <button type="button" className="sec-btn" disabled={Boolean(busy)} onClick={() => onApply(true, true)}>
          {busy === 'tune' ? 'Считаем группы…' : 'Подстроить сейчас'}
        </button>
      </div>
    </div>
  )
}

export default function RateTune({ compact = false, stamp = 0, onDone }) {
  const [tune, setTune] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    try {
      const data = await fetchDeedAnalytics()
      setTune(data?.tune || { auto: true, note: '' })
      setError('')
    } catch (err) {
      setError(messageOf(err))
    }
  }, [])

  useEffect(() => { load() }, [load, stamp])

  const apply = async (auto, now) => {
    setBusy(now ? 'tune' : 'auto')
    setError('')
    try {
      const data = await tuneDeedRates({ auto, now })
      setTune(data?.tune || { auto, note: '' })
      onDone?.(data)
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy('')
    }
  }

  if (isPanelPreviewMode()) return null
  if (!tune && !error) return <p className="staff-hint">Открываем подстройку…</p>

  return (
    <>
      {error && <p className="staff-hint" role="alert">{error}</p>}
      {tune && (
        <TuneControls
          auto={Boolean(tune.auto)}
          busy={busy}
          note={tune.note}
          compact={compact}
          onApply={apply}
        />
      )}
    </>
  )
}
