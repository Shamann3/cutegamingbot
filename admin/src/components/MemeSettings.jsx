import { useEffect, useState } from 'react'
import { fetchMemeMode, saveMemeMode } from '../lib/adminClient'
import { clampChance, parseExcludedIds } from '../lib/memeSounds'
import { notifyAdmin } from '../lib/notify'

export default function MemeSettings() {
  const [chance, setChance] = useState(10)
  const [rawIds, setRawIds] = useState('')
  const [saving, setSaving] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let stop = false
    fetchMemeMode()
      .then((data) => {
        if (stop) return
        setChance(clampChance(data?.chance))
        setRawIds((data?.excludedIds || []).join('\n'))
      })
      .catch((err) => {
        if (!stop) notifyAdmin(err.message || 'Шанс мемов не открылся', { error: true })
      })
      .finally(() => { if (!stop) setReady(true) })
    return () => { stop = true }
  }, [])

  const ids = parseExcludedIds(rawIds)

  const save = async () => {
    setSaving(true)
    try {
      const saved = await saveMemeMode({ chance: clampChance(chance), excludedIds: ids })
      setChance(clampChance(saved?.chance))
      setRawIds((saved?.excludedIds || []).join('\n'))
      notifyAdmin('Шанс мемов сохранён. Он применится со следующего входа.')
    } catch (err) {
      notifyAdmin(err.message || 'Шанс не сохранился', { error: true })
    } finally {
      setSaving(false)
    }
  }

  return (
    <article className="panel-shelf meme-settings">
      <div className="meme-settings-head">
        <h3>Мемный режим</h3>
        <strong>{chance}%</strong>
      </div>
      <p className="realm-copy">
        При входе панель один раз бросает этот шанс. Остальные входы идут без мемов.
        Выключение дополнительных звуков выключает мемы у всех. Новый шанс — со следующего входа.
        Люди из списка не услышат мемы даже при ста процентах.
      </p>
      <label className="meme-chance">
        <span>Шанс при входе</span>
        <input
          className="panel-music-slider"
          type="range"
          min="0"
          max="100"
          step="1"
          value={chance}
          disabled={!ready || saving}
          style={{ '--vol-pct': `${chance}%` }}
          onChange={(event) => setChance(clampChance(event.target.value))}
          aria-label="Шанс мемного режима"
          aria-valuetext={`${chance} процентов`}
        />
      </label>
      <label className="meme-ids">
        <span>Никогда не включать этим людям</span>
        <p className="meme-id-example">Пример: 123456789, 987654321. Каждый с новой строки или через запятую.</p>
        <textarea
          value={rawIds}
          disabled={!ready || saving}
          rows={4}
          placeholder={'123456789\n987654321'}
          onChange={(event) => setRawIds(event.target.value)}
          aria-label="Идентификаторы без мемов"
        />
      </label>
      {ids.length > 0 && (
        <ul className="meme-id-list">
          {ids.map((id) => <li key={id}>{id}</li>)}
        </ul>
      )}
      <button type="button" className="sec-btn" disabled={!ready || saving} onClick={save}>
        {saving ? 'Запись…' : 'Сохранить шанс'}
      </button>
    </article>
  )
}
