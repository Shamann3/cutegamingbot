import { useState } from 'react'
import DexItemSearchPicker from '../../DexItemSearchPicker'
import { createContentCraft } from '../../../lib/adminClient'
import { notifyAdmin } from '../../../lib/notify'
import { makeCraftKey } from '../graph/craftKey'

export default function AddCraftPanel({ onClose, onCreated }) {
  const [resultId, setResultId] = useState('')
  const [ingA, setIngA] = useState('')
  const [ingB, setIngB] = useState('')
  const [successPercent, setSuccessPercent] = useState('100')
  const [resultQty, setResultQty] = useState('1')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!resultId || !ingA || !ingB) { notifyAdmin('Выберите все три предмета', { error: true }); return }
    if (ingA === ingB) { notifyAdmin('Ингредиенты A и B должны быть разными', { error: true }); return }
    setSaving(true)
    try {
      const pct = parseInt(successPercent, 10)
      const qty = parseInt(resultQty, 10)
      await createContentCraft({
        key: makeCraftKey(resultId, ingA, ingB),
        displayName: '',
        resultItemId: resultId,
        ingredientAId: ingA,
        ingredientBId: ingB,
        successPercent: Number.isFinite(pct) ? Math.max(1, Math.min(100, pct)) : 100,
        enabled: true,
        remains: 0,
        resultQty: Number.isFinite(qty) ? Math.max(1, qty) : 1,
      })
      notifyAdmin('Крафт создан')
      onCreated()
    } catch (err) {
      notifyAdmin(err?.message || 'Не удалось создать крафт', { error: true })
    } finally {
      setSaving(false)
    }
  }

  return (
    <aside className="craftmap-add">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 className="panel-users-subtitle" style={{ margin: 0 }}>＋ Новый крафт</h3>
        <button className="pu-close-btn" onClick={onClose}>✕</button>
      </div>
      <p className="panel-shelf-label">Результат</p>
      <DexItemSearchPicker label="Предмет на выходе" value={resultId} onChange={setResultId} />
      <p className="panel-shelf-label" style={{ marginTop: 8 }}>Ингредиент A</p>
      <DexItemSearchPicker label="Первый" value={ingA} onChange={setIngA} />
      <p className="panel-shelf-label" style={{ marginTop: 8 }}>Ингредиент B</p>
      <DexItemSearchPicker label="Второй" value={ingB} onChange={setIngB} />
      <div className="panel-content-inline-2" style={{ marginTop: 10 }}>
        <label className="panel-economy-field">
          <span>Шанс %</span>
          <input className="panel-users-input" type="number" min={1} max={100} value={successPercent}
            onChange={(e) => setSuccessPercent(e.target.value.replace(/[^\d]/g, ''))} />
        </label>
        <label className="panel-economy-field">
          <span>Кол-во на выходе</span>
          <input className="panel-users-input" type="number" min={1} value={resultQty}
            onChange={(e) => setResultQty(e.target.value.replace(/[^\d]/g, ''))} />
        </label>
      </div>
      <div className="panel-content-form-actions" style={{ marginTop: 12 }}>
        <button className="panel-users-btn panel-users-btn-primary" disabled={saving} onClick={submit}>
          {saving ? 'Создаём…' : 'Создать'}
        </button>
        <button className="panel-users-btn" onClick={onClose}>Отмена</button>
      </div>
    </aside>
  )
}
