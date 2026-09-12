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
import UserLookupPreview from '../../components/UserLookupPreview'

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

function Field({ label, help, children, className = '' }) {
  return (
    <label className={`ach-field ${className}`.trim()}>
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

// Значок «занят» — тем же правилом, что и на бэкенде (find_icon_conflict):
// если задан premium emoji-id, сравниваем по нему; иначе — по обычному
// fallback-смайлу. Считается вживую при вводе, до отправки на сервер.
function findIconConflict(items, { id, icon_emoji_id, icon_fallback }) {
  const eid = String(icon_emoji_id || '').trim()
  const fb = String(icon_fallback || '⭐').trim()
  return (items || []).find((it) => {
    if (id && String(it.id) === String(id)) return false
    if (eid) return String(it.icon_emoji_id || '').trim() === eid
    if (it.icon_emoji_id) return false
    return String(it.icon_fallback || '⭐').trim() === fb
  }) || null
}

export default function AchievementsSection({ onOpenUser } = {}) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [items, setItems] = useState([])
  const [help, setHelp] = useState({})
  const [draft, setDraft] = useState({ ...EMPTY })
  const [q, setQ] = useState('')
  const [granting, setGranting] = useState(false)
  const [grantUserId, setGrantUserId] = useState('')
  const [grantResolvedId, setGrantResolvedId] = useState(null)
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

  // Живая проверка «значок уже занят» — мгновенная подсказка до сохранения,
  // тем же правилом, что и сервер (уникальность premium emoji-id ИЛИ
  // обычного fallback-смайла среди всех официальных достижений).
  const iconConflict = useMemo(
    () => findIconConflict(items, draft),
    [items, draft.id, draft.icon_emoji_id, draft.icon_fallback],
  )

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
    if (iconConflict) {
      notifyAdmin(`Значок уже занят достижением «${iconConflict.title}» — выберите другой`, { error: true })
      return
    }
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
      // Если удалённое достижение было выбрано для выдачи — снимаем выбор,
      // чтобы «Выдать достижение» не указывал на уже несуществующую награду.
      if (String(grantOfficialId) === String(id)) setGrantOfficialId('')
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
    const uid = grantResolvedId || Number(String(grantUserId).trim())
    if (!Number.isFinite(uid) || uid <= 0) {
      notifyAdmin('Укажите user_id игрока', { error: true })
      return
    }
    setGranting(true)
    try {
      if (grantMode === 'official') {
        // ВАЖНО: берём ТОЛЬКО явный выбор карточки в «Award desk» — раньше тут
        // был неявный fallback на draft.id (то, что просто открыто в редакторе
        // каталога выше). Это путало навигацию: достаточно было кликнуть
        // достижение для редактирования — и выдача могла случайно уйти именно
        // по нему, даже если админ его не выбирал для выдачи.
        const oid = Number(grantOfficialId || 0)
        if (!oid) {
          notifyAdmin('Выберите карточку достижения ниже — «Официальное»', { error: true })
          return
        }
        const res = await grantOfficialAchievement({
          user_id: uid,
          official_id: oid,
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
    const uid = grantResolvedId || Number(String(grantUserId).trim())
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
    const uid = grantResolvedId || Number(String(grantUserId).trim())
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
            Официальные награды (коды <code>gbl_level_1…5</code> — уровни баланса группы)
            и свободные — через панель или команды в боте.
            Названия и значки из этого каталога подтягиваются при покупке уровня.
            За каждую группу выдаётся отдельный экземпляр с кликабельным названием чата
            (например «Спонсор группы · Cute»). Игрок может копить награды за разные группы.
            <br />
            <b>У каждой награды — свой уникальный значок</b> (premium-эмодзи или обычный emoji):
            панель не даст сохранить две награды с одинаковым значком.
          </p>
        </div>
        <div className="ach-hero-actions">
          <button type="button" className="ach-btn" onClick={resetDraft}>Новое</button>
          <button
            type="button"
            className="ach-btn ach-btn-primary"
            disabled={saving || !!iconConflict}
            title={iconConflict ? 'Значок уже занят другим достижением' : undefined}
            onClick={onSave}
          >
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
              <input
                className={iconConflict ? 'ach-input-error' : ''}
                value={draft.icon_emoji_id}
                onChange={(e) => setDraft({ ...draft, icon_emoji_id: e.target.value })}
                placeholder="пусто = обычный emoji справа"
              />
            </Field>
            <Field label="Fallback emoji" help={help.icon_fallback}>
              <input
                className={iconConflict ? 'ach-input-error' : ''}
                value={draft.icon_fallback}
                onChange={(e) => setDraft({ ...draft, icon_fallback: e.target.value })}
                maxLength={8}
              />
            </Field>
            {iconConflict ? (
              <p className="ach-icon-warning">
                ⚠️ Этот значок уже занят достижением «{iconConflict.title}» — выберите другой,
                чтобы награды не выглядели одинаково.
              </p>
            ) : null}
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
            <Field label="Описание" className="ach-field-wide">
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
              {draft.icon_emoji_id ? <span className="ach-pro-badge" title="Premium-эмодзи Telegram">PRO</span> : null}
            </div>
            <div className="ach-preview-meta">
              rarity {draft.rarity}/5 · pos {draft.sort} · {draft.enabled ? 'on' : 'off'}
              {draft.icon_emoji_id ? (
                <span className="ach-preview-meta-note"> · превью показывает fallback-emoji — реальный premium-значок увидите в Telegram</span>
              ) : null}
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
                  <span className="ach-card-icon">
                    {it.icon_fallback || '⭐'}
                    {it.icon_emoji_id ? <span className="ach-pro-dot" title="Premium-эмодзи" /> : null}
                  </span>
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

      <section className="ach-panel ach-grant">
        <div className="ach-grant-head">
          <div>
            <p className="ach-kicker">Award desk</p>
            <h2 className="ach-panel-title" style={{ marginBottom: 0 }}>Выдать игроку</h2>
            <p className="ach-field-help">
              Официальные награды — карточками. Свободные — свой текст. Права выдачи — в доступе панели.
            </p>
          </div>
          <div className="ach-grant-mode">
            <button
              type="button"
              className={`ach-mode-btn${grantMode === 'official' ? ' ach-mode-btn-on' : ''}`}
              onClick={() => setGrantMode('official')}
            >
              Официальное
            </button>
            <button
              type="button"
              className={`ach-mode-btn${grantMode === 'free' ? ' ach-mode-btn-on' : ''}`}
              onClick={() => setGrantMode('free')}
            >
              Свободное
            </button>
          </div>
        </div>

        <div className="ach-grant-grid">
          <UserLookupPreview
            label="Игрок"
            value={grantUserId}
            onChange={(v) => { setGrantUserId(v); setGrantResolvedId(null) }}
            onResolved={(u) => setGrantResolvedId(u ? Number(u.userId || u.user_id) : null)}
            onOpenUser={(id) => onOpenUser?.(id)}
            placeholder="ID, @username или имя"
          />
        </div>

        {grantMode === 'official' ? (
          <div className="ach-pick-grid">
            {sortedItems.filter((x) => x.enabled).map((it) => {
              // Выбор карточки для ВЫДАЧИ — независим от того, что сейчас
              // открыто в редакторе каталога выше (см. onGrant): один клик
              // здесь только выбирает получателя награды, не переключает
              // редактор на этот элемент, чтобы не путать два разных действия.
              const selected = String(grantOfficialId || '') === String(it.id)
              return (
                <button
                  key={it.id}
                  type="button"
                  className={`ach-pick-card ach-rarity-${Math.max(1, Math.min(5, Number(it.rarity) || 1))}${selected ? ' ach-pick-card-on' : ''}`}
                  onClick={() => setGrantOfficialId(String(it.id))}
                  title="Выбрать для выдачи (не открывает редактор выше)"
                >
                  <span className="ach-pick-icon">
                    {it.icon_fallback || '⭐'}
                    {it.icon_emoji_id ? <span className="ach-pro-dot" title="Premium-эмодзи" /> : null}
                  </span>
                  <span className="ach-pick-body">
                    <strong>{it.title}</strong>
                    <span>{rarityDots(it.rarity)} · {it.code}</span>
                  </span>
                  {selected ? <span className="ach-pick-check">выбрано</span> : null}
                </button>
              )
            })}
            {!sortedItems.filter((x) => x.enabled).length ? (
              <p className="ach-empty">В каталоге нет включённых официальных наград.</p>
            ) : null}
          </div>
        ) : (
          <div className="ach-grid" style={{ marginTop: '0.75rem' }}>
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
          </div>
        )}

        <div className="ach-hero-actions" style={{ marginTop: '0.95rem' }}>
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
