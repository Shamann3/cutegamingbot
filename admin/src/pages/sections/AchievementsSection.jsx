import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  deleteOfficialAchievement,
  fetchAchievementsOverview,
  fetchUserAchievements,
  grantFreeAchievement,
  grantOfficialAchievement,
  revokeAchievement,
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
  sort: 10,
  enabled: true,
}

const SORT_MIN = 0
const SORT_MAX = 100

function Field({ label, help, children }) {
  return (
    <label className="ach-field">
      <span className="ach-field-label">{label}</span>
      {help ? <span className="ach-field-help">{help}</span> : null}
      <div className="ach-field-control">{children}</div>
    </label>
  )
}

function SliderRow({ label, help, value, min, max, step = 1, onChange, suffix = '' }) {
  const v = Number(value)
  const safe = Number.isFinite(v) ? v : min
  return (
    <Field label={`${label}: ${safe}${suffix}`} help={help}>
      <input
        className="ach-range"
        type="range"
        min={min}
        max={max}
        step={step}
        value={safe}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </Field>
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
  const [granting, setGranting] = useState(false)
  const [grantUserId, setGrantUserId] = useState('')
  const [grantMode, setGrantMode] = useState('official') // official | free
  const [grantOfficialId, setGrantOfficialId] = useState('')
  const [grantFreeTitle, setGrantFreeTitle] = useState('')
  const [grantFreeEmoji, setGrantFreeEmoji] = useState('⭐')
  const [userItems, setUserItems] = useState([])
  const [loadingUser, setLoadingUser] = useState(false)
  const [revokingId, setRevokingId] = useState('')

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

  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const ds = (Number(a.sort) || 0) - (Number(b.sort) || 0)
      if (ds !== 0) return ds
      return (Number(a.id) || 0) - (Number(b.id) || 0)
    })
  }, [items])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return sortedItems
    return sortedItems.filter((it) =>
      String(it.code || '').toLowerCase().includes(needle)
      || String(it.title || '').toLowerCase().includes(needle),
    )
  }, [sortedItems, q])

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

  const persistItem = async (payload) => {
    const res = await saveOfficialAchievement(payload)
    return res.item
  }

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
        sort: Math.max(SORT_MIN, Math.min(SORT_MAX, Number(draft.sort) || 0)),
        enabled: !!draft.enabled,
      }
      const item = await persistItem(payload)
      notifyAdmin('Достижение сохранено')
      if (item) edit(item)
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

  const moveItem = async (id, direction) => {
    const list = sortedItems
    const idx = list.findIndex((x) => x.id === id)
    if (idx < 0) return
    const j = idx + direction
    if (j < 0 || j >= list.length) return
    const a = list[idx]
    const b = list[j]
    const sortA = Number(a.sort) || 0
    const sortB = Number(b.sort) || 0
    // Swap sort; if equal, nudge so order sticks
    let nextA = sortB
    let nextB = sortA
    if (nextA === nextB) {
      nextA = Math.max(SORT_MIN, Math.min(SORT_MAX, sortA + (direction < 0 ? -1 : 1)))
      nextB = sortA
    }
    setSaving(true)
    try {
      await persistItem({ ...a, sort: nextA })
      await persistItem({ ...b, sort: nextB })
      if (draft.id === a.id) setDraft((d) => ({ ...d, sort: nextA }))
      if (draft.id === b.id) setDraft((d) => ({ ...d, sort: nextB }))
      await load()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onGrant = async () => {
    const uid = Number(String(grantUserId).trim())
    if (!Number.isFinite(uid) || uid <= 0) {
      notifyAdmin('Укажите user_id игрока', { error: true })
      return
    }
    setGranting(true)
    try {
      if (grantMode === 'official') {
        const oid = Number(grantOfficialId || draft.id || 0)
        const code = !oid ? String(draft.code || '').trim() : ''
        if (!oid && !code) {
          notifyAdmin('Выберите официальное достижение в каталоге или укажите id', { error: true })
          return
        }
        const res = await grantOfficialAchievement({
          user_id: uid,
          official_id: oid || undefined,
          code: code || undefined,
        })
        notifyAdmin(
          res.already
            ? `Уже есть: ${res.title || res.code} → ${uid}`
            : `Выдано: ${res.title || res.code} → ${uid}`,
        )
      } else {
        const title = String(grantFreeTitle || '').trim()
        if (!title) {
          notifyAdmin('Введите текст свободной награды', { error: true })
          return
        }
        const res = await grantFreeAchievement({
          user_id: uid,
          title,
          icon_fallback: String(grantFreeEmoji || '⭐').slice(0, 8),
        })
        notifyAdmin(`Свободная награда выдана → ${uid}: ${res.title || title}`)
        setGrantFreeTitle('')
      }
      await onLoadUser()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setGranting(false)
    }
  }

  const onLoadUser = async () => {
    const uid = Number(String(grantUserId).trim())
    if (!Number.isFinite(uid) || uid <= 0) {
      notifyAdmin('Укажите user_id игрока', { error: true })
      return
    }
    setLoadingUser(true)
    try {
      const data = await fetchUserAchievements(uid)
      setUserItems(Array.isArray(data.items) ? data.items : [])
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
      setUserItems([])
    } finally {
      setLoadingUser(false)
    }
  }

  const onRevoke = async (instanceId) => {
    const uid = Number(String(grantUserId).trim())
    if (!Number.isFinite(uid) || uid <= 0 || !instanceId) return
    if (!window.confirm('Снять это достижение у игрока?')) return
    setRevokingId(String(instanceId))
    try {
      const res = await revokeAchievement({
        user_id: uid,
        instance_id: String(instanceId),
      })
      notifyAdmin(`Снято: ${res.title || instanceId} ← ${uid}`)
      await onLoadUser()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setRevokingId('')
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
            Официальные награды (коды <code>gbl_level_1…5</code> — метки уровней баланса группы)
            и свободные — через панель или команды в боте.
            Названия официальных меняйте здесь: при покупке уровня группы подтянется новый текст.
            Выдача и снятие из панели пишутся в журнал с админом; красивые уведомления игроку подключим отдельно.
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
            <SliderRow
              label={`Редкость ${rarityDots(draft.rarity)}`}
              help={help.rarity}
              value={draft.rarity}
              min={1}
              max={5}
              onChange={(n) => setDraft({ ...draft, rarity: n })}
            />
            <SliderRow
              label="Позиция в каталоге"
              help="Меньше — выше в списке выдачи. Тяните ползунок или сдвигайте стрелками справа."
              value={draft.sort}
              min={SORT_MIN}
              max={SORT_MAX}
              onChange={(n) => setDraft({ ...draft, sort: n })}
            />
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
              rarity {draft.rarity}/5 · pos {draft.sort} · {draft.enabled ? 'on' : 'off'}
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
                <div className="ach-card-move">
                  <button type="button" className="ach-move-btn" disabled={saving} onClick={() => moveItem(it.id, -1)} title="Выше">↑</button>
                  <button type="button" className="ach-move-btn" disabled={saving} onClick={() => moveItem(it.id, 1)} title="Ниже">↓</button>
                </div>
                <button type="button" className="ach-card-main" onClick={() => edit(it)}>
                  <span className="ach-card-icon">{it.icon_fallback || '⭐'}</span>
                  <span className="ach-card-body">
                    <strong>{it.title}</strong>
                    <span className="ach-card-code">{it.code} · pos {it.sort} · {rarityDots(it.rarity)}</span>
                  </span>
                </button>
                <button type="button" className="ach-card-del" onClick={() => onDelete(it.id)} title="Удалить">×</button>
              </article>
            ))}
            {!filtered.length && <p className="ach-empty">Пока пусто — создайте первое официальное достижение.</p>}
          </div>
        </section>
      </div>

      <section className="ach-panel ach-grant" style={{ marginTop: '1rem' }}>
        <h2 className="ach-panel-title">Выдать игроку</h2>
        <p className="ach-field-help" style={{ marginBottom: '0.75rem' }}>
          Официальные — из каталога (в т.ч. <code>gbl_level_1…5</code>).
          Свободные — свой текст. Нужны права выдачи в доступе панели.
        </p>
        <div className="ach-grid">
          <Field label="User ID" help={help.grant_user_id || 'Telegram user_id игрока'}>
            <input
              value={grantUserId}
              onChange={(e) => setGrantUserId(e.target.value)}
              placeholder="123456789"
              inputMode="numeric"
            />
          </Field>
          <Field label="Тип выдачи">
            <select value={grantMode} onChange={(e) => setGrantMode(e.target.value)}>
              <option value="official">Официальное</option>
              <option value="free">Свободное</option>
            </select>
          </Field>
          {grantMode === 'official' ? (
            <Field label="Официальное из каталога" help="Или откройте карточку слева — подставится выбранное.">
              <select
                value={grantOfficialId || (draft.id ? String(draft.id) : '')}
                onChange={(e) => setGrantOfficialId(e.target.value)}
              >
                <option value="">— выбрать —</option>
                {sortedItems.filter((x) => x.enabled).map((it) => (
                  <option key={it.id} value={it.id}>
                    {it.title} ({it.code})
                  </option>
                ))}
              </select>
            </Field>
          ) : (
            <>
              <Field label="Текст награды" help={help.grant_free_title || 'Без ссылок'}>
                <input
                  value={grantFreeTitle}
                  onChange={(e) => setGrantFreeTitle(e.target.value)}
                  placeholder="За вклад в атмосферу клуба"
                />
              </Field>
              <Field label="Emoji">
                <input
                  value={grantFreeEmoji}
                  onChange={(e) => setGrantFreeEmoji(e.target.value)}
                  maxLength={8}
                />
              </Field>
            </>
          )}
        </div>
        <div className="ach-hero-actions" style={{ marginTop: '0.85rem' }}>
          <button type="button" className="ach-btn ach-btn-primary" disabled={granting} onClick={onGrant}>
            {granting ? 'Выдача…' : 'Выдать достижение'}
          </button>
          <button type="button" className="ach-btn" disabled={loadingUser} onClick={onLoadUser}>
            {loadingUser ? 'Загрузка…' : 'Показать у игрока'}
          </button>
        </div>
        {userItems.length > 0 || loadingUser ? (
          <div className="ach-list-scroll" style={{ marginTop: '0.85rem', maxHeight: 220 }}>
            {userItems.map((it) => (
              <article key={it.instance_id} className="ach-card">
                <div className="ach-card-main" style={{ cursor: 'default' }}>
                  <span className="ach-card-icon">{it.icon_fallback || '⭐'}</span>
                  <span className="ach-card-body">
                    <strong>{it.title}</strong>
                    <span className="ach-card-code">
                      {it.kind === 'official' ? 'офиц.' : 'своб.'}
                      {it.unique_code ? ` · ${it.unique_code}` : ''}
                      {it.granted_by_name ? ` · выдал: ${it.granted_by_name}` : ''}
                    </span>
                  </span>
                </div>
                <button
                  type="button"
                  className="ach-card-del"
                  disabled={revokingId === it.instance_id}
                  onClick={() => onRevoke(it.instance_id)}
                  title="Снять"
                >
                  {revokingId === it.instance_id ? '…' : '×'}
                </button>
              </article>
            ))}
            {!userItems.length && !loadingUser ? (
              <p className="ach-empty">У игрока пока нет достижений профиля.</p>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  )
}
