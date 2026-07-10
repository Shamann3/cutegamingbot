import { useMemo, useState } from 'react'
import AdminSelect from './AdminSelect'
import DexItemSearchPicker from './DexItemSearchPicker'
import { notifyAdmin } from '../lib/notify'

const STEPS = [
  { id: 1, label: '1. Предметы' },
  { id: 2, label: '2. Рецепт' },
  { id: 3, label: '3. Условия' },
]

function dexItem(items, id) {
  if (!id) return null
  return items.find((item) => String(item.id) === String(id)) || null
}

function QuickDexCreate({ label, onCreate, creating }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [emoji, setEmoji] = useState('📦')

  const handleCreate = async () => {
    if (!name.trim()) return
    await onCreate({ name: name.trim(), emoji: emoji.trim() || '📦' })
    setName('')
    setEmoji('📦')
    setOpen(false)
  }

  return (
    <div className="panel-craft-quick-create">
      {!open ? (
        <button type="button" className="panel-users-btn panel-craft-quick-btn" onClick={() => setOpen(true)}>
          + Создать {label}
        </button>
      ) : (
        <div className="panel-craft-quick-form">
          <p className="panel-shelf-muted">Новый предмет: {label}</p>
          <div className="panel-content-inline-2">
            <input
              className="panel-users-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название"
            />
            <input
              className="panel-users-input"
              value={emoji}
              onChange={(e) => setEmoji(e.target.value)}
              placeholder="Emoji"
            />
          </div>
          <div className="panel-content-crop-actions">
            <button type="button" className="panel-users-btn panel-users-btn-primary" disabled={creating || !name.trim()} onClick={handleCreate}>
              {creating ? '…' : 'Создать'}
            </button>
            <button type="button" className="panel-users-btn" onClick={() => setOpen(false)}>Отмена</button>
          </div>
        </div>
      )}
    </div>
  )
}

function CraftPreview({ form, items }) {
  const ingA = dexItem(items, form.ingredientAId)
  const ingB = dexItem(items, form.ingredientBId)
  const result = dexItem(items, form.resultItemId)
  const title = form.displayName?.trim() || form.key || 'Новый крафт'

  return (
    <div className="panel-craft-preview">
      <p className="panel-shelf-label">Предпросмотр</p>
      <p className="panel-craft-preview-title">{title}</p>
      <div className="panel-craft-preview-row">
        <span className="panel-craft-preview-slot">
          {ingA ? `${ingA.emoji} ${ingA.name}` : '?'}
        </span>
        <span className="panel-craft-preview-plus">+</span>
        <span className="panel-craft-preview-slot">
          {ingB ? `${ingB.emoji} ${ingB.name}` : '?'}
        </span>
        <span className="panel-craft-preview-arrow">→</span>
        <span className="panel-craft-preview-slot panel-craft-preview-result">
          {result ? `${result.emoji} ${result.name}` : '?'}
        </span>
      </div>
      <p className="panel-shelf-muted">Шанс успеха: {form.successPercent || '100'}%</p>
      {form.remains > 0 ? (
        <p className="panel-shelf-muted">Лимит: {form.remains} шт.</p>
      ) : (
        <p className="panel-shelf-muted">Безлимит</p>
      )}
    </div>
  )
}

export default function CraftRecipeWizard({
  form,
  setForm,
  step,
  setStep,
  dexItems,
  saving,
  onSave,
  onCancel,
  onCreateDexItem,
}) {
  const [creatingSlot, setCreatingSlot] = useState(null)

  const validateStep1 = () => {
    if (!form.resultItemId) throw new Error('Выберите предмет результата')
    if (!form.ingredientAId) throw new Error('Выберите ингредиент A')
    if (!form.ingredientBId) throw new Error('Выберите ингредиент B')
    if (form.ingredientAId === form.ingredientBId) {
      throw new Error('Ингредиенты A и B должны быть разными')
    }
  }

  const validateStep2 = () => {
    if (form.mode === 'create') {
      if (!/^[a-z][a-z0-9_]{1,48}$/.test(form.key.trim())) {
        throw new Error('Ключ: латиница, цифры, _, от 2 символов')
      }
    }
  }

  const goNext = () => {
    try {
      if (step === 1) validateStep1()
      if (step === 2) validateStep2()
      setStep(Math.min(3, step + 1))
    } catch (err) {
      notifyAdmin(err.message || 'Проверьте поля', { error: true })
    }
  }

  const handleQuickCreate = async (slot, field, data) => {
    setCreatingSlot(slot)
    try {
      const created = await onCreateDexItem(data)
      setForm({ ...form, [field]: String(created.id) })
    } finally {
      setCreatingSlot(null)
    }
  }

  const setField = (patch) => setForm({ ...form, ...patch })

  return (
    <article className="panel-shelf panel-content-editor panel-craft-wizard">
      <div className="panel-craft-wizard-head">
        <h3 className="panel-users-subtitle">
          {form.mode === 'create' ? 'Новый крафт' : `Редактирование: ${form.displayName || form.key}`}
        </h3>
        <div className="panel-craft-steps">
          {STEPS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`panel-craft-step${step === s.id ? ' panel-craft-step-active' : ''}${step > s.id ? ' panel-craft-step-done' : ''}`}
              onClick={() => {
                try {
                  if (s.id > step) {
                    if (step === 1 && s.id > 1) validateStep1()
                    if (step <= 2 && s.id > 2) {
                      validateStep1()
                      validateStep2()
                    }
                  }
                  setStep(s.id)
                } catch (err) {
                  notifyAdmin(err.message || 'Проверьте поля', { error: true })
                }
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {step === 1 && (
        <div className="panel-craft-step-body">
          <p className="panel-shelf-muted">
            Сначала выберите или создайте три предмета: что получится и два ингредиента для крафта.
          </p>
          <div className="panel-craft-item-grid">
            <div className="panel-craft-item-panel">
              <p className="panel-shelf-label">Результат</p>
              <DexItemSearchPicker
                label="Предмет на выходе"
                value={form.resultItemId}
                onChange={(v) => setField({ resultItemId: v })}
              />
              <QuickDexCreate
                label="результат"
                creating={creatingSlot === 'result'}
                onCreate={(data) => handleQuickCreate('result', 'resultItemId', data)}
              />
            </div>
            <div className="panel-craft-item-panel">
              <p className="panel-shelf-label">Ингредиент A</p>
              <DexItemSearchPicker
                label="Первый слот"
                value={form.ingredientAId}
                onChange={(v) => setField({ ingredientAId: v })}
              />
              <QuickDexCreate
                label="ингредиент A"
                creating={creatingSlot === 'ingA'}
                onCreate={(data) => handleQuickCreate('ingA', 'ingredientAId', data)}
              />
            </div>
            <div className="panel-craft-item-panel">
              <p className="panel-shelf-label">Ингредиент B</p>
              <DexItemSearchPicker
                label="Второй слот"
                value={form.ingredientBId}
                onChange={(v) => setField({ ingredientBId: v })}
              />
              <QuickDexCreate
                label="ингредиент B"
                creating={creatingSlot === 'ingB'}
                onCreate={(data) => handleQuickCreate('ingB', 'ingredientBId', data)}
              />
            </div>
          </div>
          <CraftPreview form={form} items={dexItems} />
        </div>
      )}

      {step === 2 && (
        <div className="panel-craft-step-body">
          <p className="panel-shelf-muted">
            Задайте ключ рецепта (для системы) и название, которое видно в админке.
          </p>
          <div className="panel-economy-settings-form">
            {form.mode === 'create' && (
              <label className="panel-economy-field">
                <span>Ключ (латиница, уникальный)</span>
                <input
                  className="panel-users-input"
                  value={form.key}
                  onChange={(e) => setField({ key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '') })}
                  placeholder="paper_craft"
                />
              </label>
            )}
            <label className="panel-economy-field">
              <span>Название рецепта</span>
              <input
                className="panel-users-input"
                value={form.displayName}
                onChange={(e) => setField({ displayName: e.target.value })}
                placeholder={form.key || 'Бумага из бревна'}
              />
            </label>
          </div>
          <CraftPreview form={form} items={dexItems} />
        </div>
      )}

      {step === 3 && (
        <div className="panel-craft-step-body">
          <p className="panel-shelf-muted">
            Шанс успеха, лимит использований и включение рецепта в игру.
          </p>
          <div className="panel-economy-settings-form">
            <label className="panel-economy-field">
              <span>Шанс успеха %</span>
              <input
                className="panel-users-input"
                type="number"
                min={1}
                max={100}
                value={form.successPercent}
                onChange={(e) => setField({ successPercent: e.target.value.replace(/[^\d]/g, '') })}
              />
            </label>
            <label className="panel-economy-field">
              <span>Количество на выходе</span>
              <input
                className="panel-users-input"
                type="number"
                min={1}
                value={form.resultQty ?? 1}
                onChange={(e) => setField({ resultQty: Math.max(1, parseInt(e.target.value || '1', 10) || 1) })}
              />
              <span className="panel-shelf-muted" style={{ fontSize: 11, marginTop: 2 }}>
                Сколько предметов получит игрок при успешном крафте.
              </span>
            </label>
            <label className="panel-economy-field">
              <span>Лимит использований</span>
              <input
                className="panel-users-input"
                type="number"
                min={0}
                value={form.remains ?? 0}
                onChange={(e) => setField({ remains: Math.max(0, parseInt(e.target.value || '0', 10) || 0) })}
              />
              <span className="panel-shelf-muted" style={{ fontSize: 11, marginTop: 2 }}>
                0 = безлимит. Больше 0 = крафт доступен ровно N раз на весь сервер (потом автоматически отключается).
              </span>
            </label>
            <label className="panel-economy-field panel-craft-enabled-row">
              <span>Включён в игре</span>
              <input
                type="checkbox"
                checked={form.enabled !== false}
                onChange={(e) => setField({ enabled: e.target.checked })}
              />
            </label>
          </div>
          <CraftPreview form={form} items={dexItems} />
        </div>
      )}

      <div className="panel-content-form-actions panel-craft-wizard-actions">
        {step > 1 && (
          <button type="button" className="panel-users-btn" onClick={() => setStep(step - 1)}>
            Назад
          </button>
        )}
        {step < 3 ? (
          <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={goNext}>
            Далее
          </button>
        ) : (
          <button type="button" className="panel-users-btn panel-users-btn-primary" disabled={saving} onClick={onSave}>
            {saving ? 'Сохраняем…' : form.mode === 'create' ? 'Создать крафт' : 'Сохранить крафт'}
          </button>
        )}
        <button type="button" className="panel-users-btn" onClick={() => onCancel()}>Отмена</button>
      </div>
    </article>
  )
}
