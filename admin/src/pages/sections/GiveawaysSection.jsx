import { useEffect, useState } from 'react'
import AdminSelect from '../../components/AdminSelect'
import AdminActionModal from '../../components/AdminActionModal'
import {
  fetchGiveawaysAdmin,
  createGiveawayAdmin,
  patchGiveawayAdmin,
  deleteGiveawayAdmin,
  completeGiveawayAdmin,
} from '../../lib/adminClient'

const RARITY_OPTIONS = [
  { value: 'common', label: 'Обычный' },
  { value: 'rare', label: 'Редкий' },
  { value: 'legendary', label: 'Легендарный' },
]

const PRIZE_TYPE_OPTIONS = [
  { value: 'kut', label: 'КУТ (автоначисление)' },
  { value: 'manual', label: 'NFT / подарок (вручную)' },
]

const DRAW_TYPE_OPTIONS = [
  { value: 'instant', label: 'Мгновенно всем выполнившим' },
  { value: 'timer', label: 'Случайно по таймеру' },
]

const CONDITION_KIND_OPTIONS = [
  { value: 'balance', label: 'Баланс КУТ ≥' },
  { value: 'harvest_count', label: 'Урожаев собрано ≥' },
  { value: 'item_count', label: 'Предмет в рюкзаке ≥' },
  { value: 'channel_sub', label: 'Подписка на Telegram-канал' },
  { value: 'referral_count', label: 'Пригласить друзей ≥' },
]

function emptyForm() {
  return {
    title: '',
    description: '',
    emoji: '🎁',
    rarity: 'common',
    prizeType: 'kut',
    prizeKutAmount: 100,
    prizeTitle: '',
    prizeEmoji: '🎁',
    prizeDescription: '',
    drawType: 'instant',
    startsAt: '',
    endsAt: '',
    enabled: true,
    conditions: [],
  }
}

export default function GiveawaysSection() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [form, setForm] = useState(null) // null = список, объект = форма создания/редактирования
  const [saving, setSaving] = useState(false)
  const [cancelTarget, setCancelTarget] = useState(null)
  const [completeTarget, setCompleteTarget] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const data = await fetchGiveawaysAdmin()
      setItems(data)
      setError(null)
    } catch (e) {
      setError(e?.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const openCreate = () => setForm(emptyForm())

  const openEdit = (item) => setForm({
    id: item.id,
    title: item.title,
    description: item.description ?? '',
    emoji: item.emoji,
    rarity: item.rarity,
    prizeType: item.prizeType,
    prizeKutAmount: item.prizeKutAmount ?? 100,
    prizeTitle: item.prizeTitle ?? '',
    prizeEmoji: item.prizeEmoji ?? '🎁',
    prizeDescription: item.prizeDescription ?? '',
    drawType: item.drawType,
    startsAt: item.startsAt ? item.startsAt.slice(0, 16) : '',
    endsAt: item.endsAt ? item.endsAt.slice(0, 16) : '',
    enabled: item.enabled,
    conditions: item.conditions.map((c) => ({
      kind: c.kind, targetValue: c.targetValue, itemId: c.itemId ?? '',
    })),
  })

  const addCondition = () => setForm((f) => ({
    ...f,
    conditions: [...f.conditions, { kind: 'balance', targetValue: 1, itemId: '' }],
  }))

  const updateCondition = (idx, patch) => setForm((f) => ({
    ...f,
    conditions: f.conditions.map((c, i) => (i === idx ? { ...c, ...patch } : c)),
  }))

  const removeCondition = (idx) => setForm((f) => ({
    ...f,
    conditions: f.conditions.filter((_, i) => i !== idx),
  }))

  const save = async () => {
    if (!form) return
    setSaving(true)
    try {
      const payload = {
        title: form.title,
        description: form.description,
        emoji: form.emoji,
        rarity: form.rarity,
        prizeType: form.prizeType,
        prizeKutAmount: form.prizeType === 'kut' ? Number(form.prizeKutAmount) : null,
        prizeTitle: form.prizeType === 'manual' ? form.prizeTitle : null,
        prizeEmoji: form.prizeType === 'manual' ? form.prizeEmoji : null,
        prizeDescription: form.prizeType === 'manual' ? form.prizeDescription : null,
        drawType: form.drawType,
        startsAt: form.startsAt ? new Date(form.startsAt).toISOString() : null,
        endsAt: form.drawType === 'timer' && form.endsAt ? new Date(form.endsAt).toISOString() : null,
        enabled: form.enabled,
        conditions: form.conditions.map((c) => ({
          kind: c.kind,
          targetValue: c.kind === 'channel_sub' ? 1 : Number(c.targetValue),
          itemId: c.kind === 'item_count' || c.kind === 'channel_sub' ? c.itemId : null,
        })),
      }
      if (form.id) {
        await patchGiveawayAdmin(form.id, payload)
      } else {
        await createGiveawayAdmin(payload)
      }
      setForm(null)
      await load()
    } catch (e) {
      setError(e?.message || 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  const confirmCancel = async () => {
    if (!cancelTarget) return
    setSaving(true)
    try {
      await deleteGiveawayAdmin(cancelTarget.id)
      setCancelTarget(null)
      await load()
    } catch (e) {
      setError(e?.message || 'Ошибка отмены')
    } finally {
      setSaving(false)
    }
  }

  const confirmComplete = async () => {
    if (!completeTarget) return
    setSaving(true)
    try {
      await completeGiveawayAdmin(completeTarget.id)
      setCompleteTarget(null)
      await load()
    } catch (e) {
      setError(e?.message || 'Ошибка завершения')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="panel-content">
      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Giveaways · Розыгрыши</p>
        <h2 className="panel-page-title">Розыгрыши</h2>
        <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={openCreate}>
          + Новый розыгрыш
        </button>
        {error && <p className="panel-shelf-error">{error}</p>}
      </article>

      {loading ? (
        <p>Загрузка…</p>
      ) : (
        <table className="panel-economy-dex-table">
          <thead>
            <tr>
              <th>Приз</th>
              <th>Редкость</th>
              <th>Тип</th>
              <th>Старт</th>
              <th>Статус</th>
              <th>Участников</th>
              <th>Победитель</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.emoji} {item.title}</td>
                <td>{RARITY_OPTIONS.find((r) => r.value === item.rarity)?.label}</td>
                <td>{DRAW_TYPE_OPTIONS.find((d) => d.value === item.drawType)?.label}</td>
                <td>{item.startsAt ? new Date(item.startsAt).toLocaleString('ru-RU') : 'сразу'}</td>
                <td>{item.status}</td>
                <td>{item.entriesCount}</td>
                <td>{item.winnerUserId ?? '—'}</td>
                <td>
                  <button type="button" className="panel-users-btn" onClick={() => openEdit(item)}>
                    Изменить
                  </button>
                  {item.status === 'active' && (
                    <button
                      type="button"
                      className="panel-users-btn panel-users-btn-danger"
                      onClick={() => setCancelTarget(item)}
                    >
                      Отменить
                    </button>
                  )}
                  {item.status === 'active' && item.drawType === 'instant' && (
                    <button
                      type="button"
                      className="panel-users-btn"
                      onClick={() => setCompleteTarget(item)}
                    >
                      Завершить
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {form && (
        <div className="admin-modal-backdrop" role="presentation" onClick={() => setForm(null)}>
          <div className="admin-modal" role="dialog" onClick={(e) => e.stopPropagation()}>
            <h3>{form.id ? 'Редактировать розыгрыш' : 'Новый розыгрыш'}</h3>

            <label className="admin-modal-field">
              <span>Название</span>
              <input className="panel-users-input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </label>
            <label className="admin-modal-field">
              <span>Дата начала (необязательно — пусто значит «сразу»)</span>
              <input className="panel-users-input" type="datetime-local" value={form.startsAt} onChange={(e) => setForm({ ...form, startsAt: e.target.value })} />
            </label>
            <label className="admin-modal-field">
              <span>Описание</span>
              <textarea className="admin-modal-textarea" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </label>
            <label className="admin-modal-field">
              <span>Эмодзи</span>
              <input className="panel-users-input" value={form.emoji} onChange={(e) => setForm({ ...form, emoji: e.target.value })} maxLength={8} />
            </label>
            <label className="admin-modal-field">
              <span>Редкость</span>
              <AdminSelect value={form.rarity} onChange={(v) => setForm({ ...form, rarity: v })} options={RARITY_OPTIONS} />
            </label>

            <label className="admin-modal-field">
              <span>Тип приза</span>
              <AdminSelect value={form.prizeType} onChange={(v) => setForm({ ...form, prizeType: v })} options={PRIZE_TYPE_OPTIONS} />
            </label>
            {form.prizeType === 'kut' ? (
              <label className="admin-modal-field">
                <span>Сумма КУТ</span>
                <input className="panel-users-input" type="number" min={1} value={form.prizeKutAmount} onChange={(e) => setForm({ ...form, prizeKutAmount: e.target.value })} />
              </label>
            ) : (
              <>
                <label className="admin-modal-field">
                  <span>Название приза</span>
                  <input className="panel-users-input" value={form.prizeTitle} onChange={(e) => setForm({ ...form, prizeTitle: e.target.value })} />
                </label>
                <label className="admin-modal-field">
                  <span>Эмодзи приза</span>
                  <input className="panel-users-input" value={form.prizeEmoji} onChange={(e) => setForm({ ...form, prizeEmoji: e.target.value })} maxLength={8} />
                </label>
                <label className="admin-modal-field">
                  <span>Описание приза (для игрока)</span>
                  <textarea className="admin-modal-textarea" value={form.prizeDescription} onChange={(e) => setForm({ ...form, prizeDescription: e.target.value })} />
                </label>
              </>
            )}

            <label className="admin-modal-field">
              <span>Механика розыгрыша</span>
              <AdminSelect value={form.drawType} onChange={(v) => setForm({ ...form, drawType: v })} options={DRAW_TYPE_OPTIONS} />
            </label>
            {form.drawType === 'timer' && (
              <label className="admin-modal-field">
                <span>Дата окончания</span>
                <input className="panel-users-input" type="datetime-local" value={form.endsAt} onChange={(e) => setForm({ ...form, endsAt: e.target.value })} />
              </label>
            )}

            <div className="admin-modal-field">
              <span>Условия участия (все обязательны)</span>
              {form.conditions.map((cond, idx) => (
                <div key={idx} style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                  <AdminSelect
                    value={cond.kind}
                    onChange={(v) => updateCondition(idx, { kind: v })}
                    options={CONDITION_KIND_OPTIONS}
                  />
                  {cond.kind !== 'channel_sub' && (
                    <input
                      className="panel-users-input"
                      type="number"
                      min={1}
                      value={cond.targetValue}
                      onChange={(e) => updateCondition(idx, { targetValue: e.target.value })}
                      style={{ width: 90 }}
                    />
                  )}
                  {cond.kind === 'item_count' && (
                    <input
                      className="panel-users-input"
                      placeholder="id предмета"
                      value={cond.itemId}
                      onChange={(e) => updateCondition(idx, { itemId: e.target.value })}
                    />
                  )}
                  {cond.kind === 'channel_sub' && (
                    <input
                      className="panel-users-input"
                      placeholder="@username канала"
                      value={cond.itemId}
                      onChange={(e) => updateCondition(idx, { itemId: e.target.value })}
                    />
                  )}
                  <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => removeCondition(idx)}>
                    ✕
                  </button>
                </div>
              ))}
              <button type="button" className="panel-users-btn" onClick={addCondition}>+ Условие</button>
            </div>

            <label className="admin-modal-field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              <span>Включён</span>
            </label>

            <div className="admin-modal-actions">
              <button type="button" className="panel-users-btn" onClick={() => setForm(null)} disabled={saving}>
                Отмена
              </button>
              <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={save} disabled={saving}>
                {saving ? '…' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}

      <AdminActionModal
        open={Boolean(cancelTarget)}
        title="Отменить розыгрыш?"
        description={cancelTarget ? `«${cancelTarget.title}» — участники не смогут вступить, приз не разыгрывается.` : ''}
        confirmText="Отменить розыгрыш"
        danger
        loading={saving}
        onConfirm={confirmCancel}
        onCancel={() => setCancelTarget(null)}
      />

      <AdminActionModal
        open={Boolean(completeTarget)}
        title="Завершить розыгрыш?"
        description={completeTarget ? `«${completeTarget.title}» — уйдёт из «Активных»/«Скоро» и появится во вкладке «Прошедшие» игроков с числом получивших приз.` : ''}
        confirmText="Завершить"
        loading={saving}
        onConfirm={confirmComplete}
        onCancel={() => setCompleteTarget(null)}
      />
    </div>
  )
}
