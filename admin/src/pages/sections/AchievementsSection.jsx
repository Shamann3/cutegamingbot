import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  deleteOfficialAchievement,
  fetchAchievementsOverview,
  saveOfficialAchievement,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'

const EMPTY = {
  id: null,
  code: '',
  title: '',
  icon_emoji_id: '',
  icon_fallback: '⭐',
  description: '',
  rarity: 1,
  sort: 0,
  enabled: true,
}

function Field({ label, help, children }) {
  return (
    <label className="ach-field">
      <span className="ach-field-label">{label}</span>
      {help ? <span className="ach-field-help">{help}</span> : null}
      <div className="ach-field-control">{children}</div>
    </label>
  )
}

function rarityDots(n) {
  const v = Math.max(1, Math.min(5, Number(n) || 1))
  return '●'.repeat(v) + '○'.repeat(5 - v)
}

export default function AchievementsSection() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [items, setItems] = useState([])
  const [help, setHelp] = useState({})
  const [draft, setDraft] = useState({ ...EMPTY })
  const [q, setQ] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAchievementsOverview()
      setItems(Array.isArray(data.items) ? data.items : [])
      setHelp(data.help || {})
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return items
    return items.filter((it) =>
      String(it.code || '').toLowerCase().includes(needle)
      || String(it.title || '').toLowerCase().includes(needle),
    )
  }, [items, q])

  const edit = (it) => {
    setDraft({
      id: it.id,
      code: it.code || '',
      title: it.title || '',
      icon_emoji_id: it.icon_emoji_id || '',
      icon_fallback: it.icon_fallback || '⭐',
      description: it.description || '',
      rarity: Number(it.rarity) || 1,
      sort: Number(it.sort) || 0,
      enabled: !!it.enabled,
    })
  }

  const resetDraft = () => setDraft({ ...EMPTY })

  const onSave = async () => {
    setSaving(true)
    try {
      const payload = {
        ...draft,
        id: draft.id || undefined,
        code: String(draft.code || '').trim(),
        title: String(draft.title || '').trim(),
        icon_emoji_id: String(draft.icon_emoji_id || '').trim() || null,
        icon_fallback: String(draft.icon_fallback || '⭐').slice(0, 8),
        description: String(draft.description || '').slice(0, 400),
        rarity: Math.max(1, Math.min(5, Number(draft.rarity) || 1)),
        sort: Number(draft.sort) || 0,
        enabled: !!draft.enabled,
      }
      const res = await saveOfficialAchievement(payload)
      notifyAdmin('Достижение сохранено')
      if (res.item) edit(res.item)
      await load()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onDelete = async (id) => {
    if (!id) return
    if (!window.confirm('Удалить официальное достижение из каталога?')) return
    try {
      await deleteOfficialAchievement(id)
      notifyAdmin('Удалено')
      if (draft.id === id) resetDraft()
      await load()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    }
  }

  if (loading && !items.length) {
    return <div className="ach-page ach-loading">Загрузка каталога…</div>
  }

  return (
    <div className="ach-page">
      <header className="ach-hero">
        <div>
          <p className="ach-kicker">Official catalog</p>
          <h1 className="ach-title">Достижения</h1>
          <p className="ach-sub">
            Официальные награды профиля. Создатель настраивает каталог;
            выдача в боте — по правам матрицы «Админ панель».
          </p>
        </div>
        <div className="ach-hero-actions">
          <button type="button" className="ach-btn" onClick={resetDraft}>Новое</button>
          <button type="button" className="ach-btn ach-btn-primary" disabled={saving} onClick={onSave}>
            {saving ? 'Сохранение…' : 'Сохранить'}
          </button>
        </div>
      </header>

      <div className="ach-layout">
        <section className="ach-editor ach-panel">
          <h2 className="ach-panel-title">{draft.id ? `Редактирование #${draft.id}` : 'Новое достижение'}</h2>
          <div className="ach-grid">
            <Field label="Код" help={help.code}>
              <input value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value })} placeholder="legend_spring" />
            </Field>
            <Field label="Название" help={help.title}>
              <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} placeholder="Легенда сезона" />
            </Field>
            <Field label="Premium emoji id" help={help.icon_emoji_id}>
              <input value={draft.icon_emoji_id} onChange={(e) => setDraft({ ...draft, icon_emoji_id: e.target.value })} />
            </Field>
            <Field label="Fallback emoji">
              <input value={draft.icon_fallback} onChange={(e) => setDraft({ ...draft, icon_fallback: e.target.value })} maxLength={8} />
            </Field>
            <Field label={`Редкость ${rarityDots(draft.rarity)}`} help={help.rarity}>
              <input
                className="ach-range"
                type="range"
                min={1}
                max={5}
                value={draft.rarity}
                onChange={(e) => setDraft({ ...draft, rarity: Number(e.target.value) })}
              />
            </Field>
            <Field label="Сортировка" help={help.sort}>
              <input type="number" value={draft.sort} onChange={(e) => setDraft({ ...draft, sort: Number(e.target.value) })} />
            </Field>
            <Field label="Описание">
              <textarea
                rows={3}
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                placeholder="Короткий лор для команды"
              />
            </Field>
            <label className="ach-toggle">
              <input type="checkbox" checked={!!draft.enabled} onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })} />
              <span>Включено в выдаче</span>
            </label>
          </div>

          <div className="ach-preview">
            <span className="ach-preview-label">Превью витрины</span>
            <div className="ach-preview-card">
              <span className="ach-preview-icon">{draft.icon_fallback || '⭐'}</span>
              <span className="ach-preview-title">{draft.title || 'Название достижения'}</span>
            </div>
            <div className="ach-preview-meta">
              rarity {draft.rarity}/5 · sort {draft.sort} · {draft.enabled ? 'on' : 'off'}
            </div>
          </div>
        </section>

        <section className="ach-list ach-panel">
          <div className="ach-list-head">
            <h2 className="ach-panel-title">Каталог · {filtered.length}</h2>
            <input
              className="ach-search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Поиск по коду / названию"
            />
          </div>
          <div className="ach-list-scroll">
            {filtered.map((it) => (
              <article key={it.id} className={`ach-card ${draft.id === it.id ? 'ach-card-active' : ''} ${it.enabled ? '' : 'ach-card-off'}`}>
                <button type="button" className="ach-card-main" onClick={() => edit(it)}>
                  <span className="ach-card-icon">{it.icon_fallback || '⭐'}</span>
                  <span className="ach-card-body">
                    <strong>{it.title}</strong>
                    <span className="ach-card-code">{it.code} · {rarityDots(it.rarity)}</span>
                  </span>
                </button>
                <button type="button" className="ach-card-del" onClick={() => onDelete(it.id)} title="Удалить">×</button>
              </article>
            ))}
            {!filtered.length && <p className="ach-empty">Пока пусто — создайте первое официальное достижение.</p>}
          </div>
        </section>
      </div>
    </div>
  )
}
