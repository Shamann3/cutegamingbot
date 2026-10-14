import { useEffect, useState } from 'react'
import { fetchBalanceCalm, saveBalanceCalm } from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'

export default function BalancesCalm() {
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let gone = false
    fetchBalanceCalm()
      .then((data) => {
        if (!gone) setForm(data)
      })
      .catch((err) => {
        if (!gone) setError(err.message || 'Не открылось')
      })
    return () => {
      gone = true
    }
  }, [])

  async function save() {
    if (!form) return
    setSaving(true)
    try {
      const next = await saveBalanceCalm({
        enabled: Boolean(form.enabled),
        games: Number(form.games),
        hours: Number(form.hours),
      })
      setForm(next)
      notifyAdmin('Балансы сохранены')
    } catch (err) {
      notifyAdmin(err.message || 'Не сохранилось', { error: true })
    } finally {
      setSaving(false)
    }
  }

  if (!form) {
    return <p className="panel-shelf-muted" style={{ padding: '1rem' }}>{error || 'Загрузка…'}</p>
  }

  const games = Number(form.games) || 5
  const hours = Number(form.hours) || 24

  return (
    <article className="panel-shelf sys-group">
      <div className="sys-group-head">
        <span className="sys-group-emoji">◎</span>
        <h3 className="sys-group-title">Покой баланса</h3>
      </div>
      <p className="panel-shelf-muted" style={{ margin: '0 0 1rem' }}>
        Только создатель. Игры считаются в любой группе. Пока за этот срок их набрано достаточно,
        обливать нельзя и куты в покое. Зонтик, дождевик, навес и сейф закрывают сразу, даже без этих игр.
      </p>
      <div className={`sys-toggle-row${form.enabled ? ' is-on' : ''}`}>
        <div className="sys-toggle-copy">
          <strong>Покой включён</strong>
          <em>Выключено — пистолетик снова берёт куты у всех, у кого нет купленной защиты.</em>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={Boolean(form.enabled)}
          className={`panel-toggle${form.enabled ? ' panel-toggle-on' : ''}`}
          disabled={saving}
          onClick={() => setForm((row) => ({ ...row, enabled: !row.enabled }))}
        >
          <span className="panel-toggle-thumb" />
        </button>
      </div>
      <label className="sys-toggle-copy" style={{ display: 'block', marginTop: '1rem' }}>
        <strong>Игр за срок</strong>
        <input
          className="sec-input"
          type="number"
          min="1"
          max="100"
          value={form.games}
          aria-label="Игр за срок"
          onChange={(event) => setForm((row) => ({ ...row, games: event.target.value }))}
        />
      </label>
      <label className="sys-toggle-copy" style={{ display: 'block', marginTop: '0.75rem' }}>
        <strong>Срок, часы</strong>
        <input
          className="sec-input"
          type="number"
          min="1"
          max="168"
          value={form.hours}
          aria-label="Срок, часы"
          onChange={(event) => setForm((row) => ({ ...row, hours: event.target.value }))}
        />
      </label>
      <p className="panel-shelf-muted" style={{ margin: '0.75rem 0' }}>
        {form.enabled
          ? `Сейчас: ${games} игр за ${hours} ч. В балансе человек видит, сколько уже есть и сколько ещё.`
          : 'Сейчас покой выключен.'}
      </p>
      <button type="button" className="sec-btn" disabled={saving} onClick={save}>
        {saving ? 'Сохраняю…' : 'Сохранить'}
      </button>
    </article>
  )
}
