import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchFlame,
  saveFlameGiftDrops,
  saveFlameRewards,
  saveFlameSettings,
  saveFlameSteps,
  saveFlameTitles,
  saveFlameWarmRewards,
} from '../../lib/adminClient'
import '../../styles/flame.css'

const TABS = [
  { id: 'norm', label: 'Норма' },
  { id: 'rewards', label: 'Награды' },
  { id: 'warm', label: 'Тёплый час' },
  { id: 'status', label: 'Статусы' },
  { id: 'gift', label: 'Предмет 🎁' },
  { id: 'live', label: 'Живое' },
]

const KINDS = [
  { id: 'bonus', label: 'Обычный бонус' },
  { id: 'bonus_x2', label: 'Бонус ×2' },
  { id: 'kuty', label: 'Куты' },
  { id: 'item', label: 'Предмет' },
]

const GIFT_KINDS = [
  { id: 'kuty', label: 'Куты' },
  { id: 'item', label: 'Предмет' },
]

function digits(value) {
  return String(value ?? '').replace(/[^\d]/g, '')
}

function kindLabel(kind) {
  return KINDS.find((row) => row.id === kind)?.label || 'Награда'
}

function sourceLabel(source) {
  if (source === 'warm') return 'тёплый час'
  if (source === 'gift') return '🎁'
  if (source === 'streak') return 'день серии'
  return source || 'награда'
}

export default function FlameSection() {
  const [tab, setTab] = useState('norm')
  const [board, setBoard] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [form, setForm] = useState({})
  const [steps, setSteps] = useState([])
  const [rewards, setRewards] = useState([])
  const [titles, setTitles] = useState([])
  const [warmRewards, setWarmRewards] = useState([])
  const [giftDrops, setGiftDrops] = useState([])

  const apply = useCallback((data) => {
    setBoard(data)
    const s = data?.settings || {}
    setForm({
      enabled: Boolean(s.enabled),
      baseMessages: String(s.base_messages || 200),
      warmEnabled: Boolean(s.warm_enabled),
      warmMinDay: String(s.warm_min_day || 3),
      warmEvery: String(s.warm_every || 40),
      warmCap: String(s.warm_cap || 3),
      warmFrom: String(s.warm_from ?? 15),
      warmTo: String(s.warm_to ?? 24),
      statusEnabled: s.status_enabled !== false,
      profitEnabled: s.profit_enabled !== false,
      profitHour: String(s.profit_hour ?? 21),
      minWords: String(s.min_words || 2),
      blockDup: s.block_dup !== false,
      giftEnabled: s.gift_enabled !== false,
      giftMult: String(s.gift_mult || 1),
      giftKutyMin: String(s.gift_kuty_min || 1),
      giftKutyMax: String(s.gift_kuty_max || 3),
    })
    setSteps((data?.steps || []).map((row) => ({
      fromDay: String(row.from_day),
      messages: String(row.messages),
    })))
    setRewards((data?.rewards || []).map((row) => ({
      day: String(row.day),
      kind: row.kind,
      amount: String(row.amount || 1),
      itemName: row.item_name || '',
    })))
    setTitles((data?.titles || []).map((row) => ({
      fromDay: String(row.from_day),
      title: row.title || '',
      emojiId: row.emoji_id || '',
    })))
    setWarmRewards((data?.warm?.rewards || []).map((row) => ({
      kind: row.kind,
      amount: String(row.amount || 1),
      itemName: row.item_name || '',
      weight: String(row.weight || 1),
    })))
    setGiftDrops((data?.gift?.drops || []).map((row) => ({
      kind: row.kind,
      amountMin: String(row.amount_min || 1),
      amountMax: String(row.amount_max || 1),
      itemName: row.item_name || '',
      weight: String(row.weight || 1),
    })))
  }, [])

  const load = useCallback(async () => {
    try {
      apply(await fetchFlame())
      setError('')
    } catch (err) {
      setError(err?.message || 'Не удалось открыть огонёк')
    }
  }, [apply])

  useEffect(() => { load() }, [load])

  const run = async (key, job) => {
    setBusy(key)
    setError('')
    try {
      apply(await job())
    } catch (err) {
      setError(err?.message || 'Не сохранилось')
    } finally {
      setBusy('')
    }
  }

  const patch = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const saveAllSettings = () => run('settings', () => saveFlameSettings({
    enabled: form.enabled,
    baseMessages: Math.max(1, Number(form.baseMessages) || 1),
    warmEnabled: form.warmEnabled,
    warmMinDay: Math.max(1, Number(form.warmMinDay) || 1),
    warmEvery: Math.max(1, Number(form.warmEvery) || 1),
    warmCap: Math.max(1, Number(form.warmCap) || 1),
    warmFrom: Math.max(0, Math.min(23, Number(form.warmFrom) || 0)),
    warmTo: Math.max(1, Math.min(24, Number(form.warmTo) || 24)),
    statusEnabled: form.statusEnabled,
    profitEnabled: form.profitEnabled,
    profitHour: Math.max(0, Math.min(23, Number(form.profitHour) || 0)),
    minWords: Math.max(1, Number(form.minWords) || 2),
    blockDup: form.blockDup,
    giftEnabled: form.giftEnabled,
    giftMult: Math.max(1, Number(form.giftMult) || 1),
    giftKutyMin: Math.max(1, Number(form.giftKutyMin) || 1),
    giftKutyMax: Math.max(1, Number(form.giftKutyMax) || 1),
  }))

  const items = board?.items || []
  const preview = board?.gift?.preview || {}
  const warmHour = board?.warm?.hour

  const warmHint = useMemo(() => {
    if (!form.warmEnabled) return 'Тёплый час выключен.'
    if (warmHour == null) return 'Час выберется сам после включения.'
    const next = (Number(warmHour) + 1) % 24
    return `Сегодня тёплый час: ${String(warmHour).padStart(2, '0')}:00–${String(next).padStart(2, '0')}:00 МСК`
  }, [form.warmEnabled, warmHour])

  return (
    <section className="flame-page">
      <header className="flame-hero">
        <span className="flame-orb" aria-hidden="true" />
        <div>
          <h2>Огонёк</h2>
          <p>
            Серия сообщений, тёплый час, статусы, вечерняя карточка и предмет 🎁 —
            всё в одном месте. Награда должна звучать одной фразой другу.
          </p>
        </div>
      </header>

      {error && <p className="flame-error" role="alert">{error}</p>}
      {!board && !error && <p className="staff-hint">Открываем огонёк…</p>}

      {board && (
        <>
          <div className="flame-stats">
            <article>
              <strong>{board.alive || 0}</strong>
              <span>живых серий</span>
            </article>
            <article>
              <strong>{board.keptToday || 0}</strong>
              <span>закрыли сегодня</span>
            </article>
            <article>
              <strong>{warmHour == null ? '—' : `${String(warmHour).padStart(2, '0')}:00`}</strong>
              <span>тёплый час</span>
            </article>
          </div>

          <nav className="flame-tabs" aria-label="Разделы огонька">
            {TABS.map((row) => (
              <button
                key={row.id}
                type="button"
                className={`flame-tab${tab === row.id ? ' is-on' : ''}`}
                onClick={() => setTab(row.id)}
              >
                {row.label}
              </button>
            ))}
          </nav>

          {tab === 'norm' && (
            <section className="flame-card flame-rise">
              <div className="flame-card-head">
                <h3>Норма и защита</h3>
                <label className="flame-switch">
                  <input type="checkbox" checked={form.enabled} onChange={(e) => patch('enabled', e.target.checked)} />
                  <span>{form.enabled ? 'Огонёк включён' : 'Огонёк выключен'}</span>
                </label>
              </div>
              <div className="flame-grid-2">
                <label className="flame-field">
                  <span>Сообщений в первый день</span>
                  <input inputMode="numeric" value={form.baseMessages} onChange={(e) => patch('baseMessages', digits(e.target.value))} />
                </label>
                <label className="flame-field">
                  <span>Минимум слов в сообщении</span>
                  <input inputMode="numeric" value={form.minWords} onChange={(e) => patch('minWords', digits(e.target.value))} />
                </label>
              </div>
              <label className="flame-switch">
                <input type="checkbox" checked={form.blockDup} onChange={(e) => patch('blockDup', e.target.checked)} />
                <span>Не считать одинаковый текст подряд</span>
              </label>
              <label className="flame-switch">
                <input type="checkbox" checked={form.profitEnabled} onChange={(e) => patch('profitEnabled', e.target.checked)} />
                <span>Вечерняя карточка профита в личку</span>
              </label>
              <label className="flame-field">
                <span>Час карточки (МСК)</span>
                <input inputMode="numeric" value={form.profitHour} onChange={(e) => patch('profitHour', digits(e.target.value))} />
              </label>
              <p className="flame-note">
                В счёт идут живые сообщения в официальных группах. Команды, игры и копипаст не кормят огонёк.
              </p>
              <div className="flame-card-head">
                <h3>Рост нормы</h3>
                <button type="button" className="sec-btn sec-btn-ghost" onClick={() => setSteps((rows) => [...rows, { fromDay: '', messages: '' }])}>
                  Добавить день
                </button>
              </div>
              <ul className="flame-rows">
                {steps.map((row, index) => (
                  <li key={`step-${index}`}>
                    <label>
                      <span>С дня</span>
                      <input inputMode="numeric" value={row.fromDay} onChange={(e) => {
                        const value = digits(e.target.value)
                        setSteps((rows) => rows.map((item, i) => i === index ? { ...item, fromDay: value } : item))
                      }} />
                    </label>
                    <label>
                      <span>Сообщений</span>
                      <input inputMode="numeric" value={row.messages} onChange={(e) => {
                        const value = digits(e.target.value)
                        setSteps((rows) => rows.map((item, i) => i === index ? { ...item, messages: value } : item))
                      }} />
                    </label>
                    <button type="button" className="sec-btn sec-btn-ghost flame-drop" onClick={() => setSteps((rows) => rows.filter((_, i) => i !== index))}>Убрать</button>
                  </li>
                ))}
              </ul>
              <div className="flame-actions">
                <button type="button" className="sec-btn" disabled={busy === 'settings'} onClick={saveAllSettings}>
                  {busy === 'settings' ? 'Сохраняем…' : 'Сохранить настройки'}
                </button>
                <button
                  type="button"
                  className="sec-btn"
                  disabled={busy === 'steps'}
                  onClick={() => run('steps', () => saveFlameSteps({
                    steps: steps
                      .map((row) => ({ fromDay: Number(row.fromDay), messages: Number(row.messages) }))
                      .filter((row) => row.fromDay >= 1 && row.messages >= 1),
                  }))}
                >
                  {busy === 'steps' ? 'Сохраняем…' : 'Сохранить ступени'}
                </button>
              </div>
            </section>
          )}

          {tab === 'rewards' && (
            <section className="flame-card flame-rise">
              <div className="flame-card-head">
                <h3>Награды за дни серии</h3>
                <button type="button" className="sec-btn sec-btn-ghost" onClick={() => setRewards((rows) => [...rows, { day: '', kind: 'kuty', amount: '1', itemName: '' }])}>
                  Добавить
                </button>
              </div>
              <p className="flame-note">Один раз в тот день. Фраза другу: «за 7 дней огонька мне дали бесплатный ×2».</p>
              <ul className="flame-rows is-reward">
                {rewards.map((row, index) => (
                  <li key={`reward-${index}`}>
                    <label>
                      <span>День</span>
                      <input inputMode="numeric" value={row.day} onChange={(e) => {
                        const value = digits(e.target.value)
                        setRewards((rows) => rows.map((item, i) => i === index ? { ...item, day: value } : item))
                      }} />
                    </label>
                    <label>
                      <span>Что дать</span>
                      <select value={row.kind} onChange={(e) => {
                        const kind = e.target.value
                        setRewards((rows) => rows.map((item, i) => i === index ? { ...item, kind } : item))
                      }}>
                        {KINDS.map((kind) => <option key={kind.id} value={kind.id}>{kind.label}</option>)}
                      </select>
                    </label>
                    <label>
                      <span>{row.kind === 'item' ? 'Штук' : row.kind === 'kuty' ? 'Кут' : 'Раз'}</span>
                      <input inputMode="numeric" value={row.amount} onChange={(e) => {
                        const value = digits(e.target.value)
                        setRewards((rows) => rows.map((item, i) => i === index ? { ...item, amount: value } : item))
                      }} />
                    </label>
                    {row.kind === 'item' && (
                      <label className="is-wide">
                        <span>Предмет</span>
                        <select value={row.itemName} onChange={(e) => {
                          const itemName = e.target.value
                          setRewards((rows) => rows.map((item, i) => i === index ? { ...item, itemName } : item))
                        }}>
                          <option value="">Выберите</option>
                          {items.map((name) => <option key={name} value={name}>{name}</option>)}
                        </select>
                      </label>
                    )}
                    <button type="button" className="sec-btn sec-btn-ghost flame-drop" aria-label={`Убрать ${kindLabel(row.kind)}`} onClick={() => setRewards((rows) => rows.filter((_, i) => i !== index))}>Убрать</button>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="sec-btn"
                disabled={busy === 'rewards'}
                onClick={() => run('rewards', () => saveFlameRewards({
                  rewards: rewards
                    .map((row) => ({
                      day: Number(row.day),
                      kind: row.kind,
                      amount: Math.max(1, Number(row.amount) || 1),
                      itemName: row.kind === 'item' ? row.itemName : '',
                    }))
                    .filter((row) => row.day >= 1 && row.kind && (row.kind !== 'item' || row.itemName)),
                }))}
              >
                {busy === 'rewards' ? 'Сохраняем…' : 'Сохранить награды'}
              </button>
            </section>
          )}

          {tab === 'warm' && (
            <section className="flame-card flame-rise">
              <div className="flame-card-head">
                <h3>Тёплый час</h3>
                <label className="flame-switch">
                  <input type="checkbox" checked={form.warmEnabled} onChange={(e) => patch('warmEnabled', e.target.checked)} />
                  <span>{form.warmEnabled ? 'Включён' : 'Выключен'}</span>
                </label>
              </div>
              <p className="flame-note">{warmHint}. Каждый день между 15:00 и 0:00 код сам выбирает один час.</p>
              <div className="flame-grid-2">
                <label className="flame-field">
                  <span>С какого дня серии</span>
                  <input inputMode="numeric" value={form.warmMinDay} onChange={(e) => patch('warmMinDay', digits(e.target.value))} />
                </label>
                <label className="flame-field">
                  <span>Каждые N сообщений</span>
                  <input inputMode="numeric" value={form.warmEvery} onChange={(e) => patch('warmEvery', digits(e.target.value))} />
                </label>
                <label className="flame-field">
                  <span>Макс. наград за день</span>
                  <input inputMode="numeric" value={form.warmCap} onChange={(e) => patch('warmCap', digits(e.target.value))} />
                </label>
              </div>
              <div className="flame-card-head">
                <h3>Что может выпасть</h3>
                <button type="button" className="sec-btn sec-btn-ghost" onClick={() => setWarmRewards((rows) => [...rows, { kind: 'kuty', amount: '10', itemName: '', weight: '1' }])}>
                  Добавить
                </button>
              </div>
              <ul className="flame-rows is-warm">
                {warmRewards.map((row, index) => (
                  <li key={`warm-${index}`}>
                    <label>
                      <span>Что</span>
                      <select value={row.kind} onChange={(e) => {
                        const kind = e.target.value
                        setWarmRewards((rows) => rows.map((item, i) => i === index ? { ...item, kind } : item))
                      }}>
                        {KINDS.map((kind) => <option key={kind.id} value={kind.id}>{kind.label}</option>)}
                      </select>
                    </label>
                    <label>
                      <span>Сколько</span>
                      <input inputMode="numeric" value={row.amount} onChange={(e) => {
                        const value = digits(e.target.value)
                        setWarmRewards((rows) => rows.map((item, i) => i === index ? { ...item, amount: value } : item))
                      }} />
                    </label>
                    <label>
                      <span>Вес</span>
                      <input inputMode="numeric" value={row.weight} onChange={(e) => {
                        const value = digits(e.target.value)
                        setWarmRewards((rows) => rows.map((item, i) => i === index ? { ...item, weight: value } : item))
                      }} />
                    </label>
                    {row.kind === 'item' && (
                      <label className="is-wide">
                        <span>Предмет</span>
                        <select value={row.itemName} onChange={(e) => {
                          const itemName = e.target.value
                          setWarmRewards((rows) => rows.map((item, i) => i === index ? { ...item, itemName } : item))
                        }}>
                          <option value="">Выберите</option>
                          {items.map((name) => <option key={name} value={name}>{name}</option>)}
                        </select>
                      </label>
                    )}
                    <button type="button" className="sec-btn sec-btn-ghost flame-drop" onClick={() => setWarmRewards((rows) => rows.filter((_, i) => i !== index))}>Убрать</button>
                  </li>
                ))}
              </ul>
              <div className="flame-actions">
                <button type="button" className="sec-btn" disabled={busy === 'settings'} onClick={saveAllSettings}>
                  Сохранить час
                </button>
                <button
                  type="button"
                  className="sec-btn"
                  disabled={busy === 'warm'}
                  onClick={() => run('warm', () => saveFlameWarmRewards({
                    rewards: warmRewards
                      .map((row) => ({
                        kind: row.kind,
                        amount: Math.max(1, Number(row.amount) || 1),
                        itemName: row.kind === 'item' ? row.itemName : '',
                        weight: Math.max(1, Number(row.weight) || 1),
                      }))
                      .filter((row) => row.kind && (row.kind !== 'item' || row.itemName)),
                  }))}
                >
                  {busy === 'warm' ? 'Сохраняем…' : 'Сохранить награды часа'}
                </button>
              </div>
            </section>
          )}

          {tab === 'status' && (
            <section className="flame-card flame-rise">
              <div className="flame-card-head">
                <h3>Статусы огонька</h3>
                <label className="flame-switch">
                  <input type="checkbox" checked={form.statusEnabled} onChange={(e) => patch('statusEnabled', e.target.checked)} />
                  <span>{form.statusEnabled ? 'В профиле видны' : 'Скрыты'}</span>
                </label>
              </div>
              <p className="flame-note">Короткий титул в профиле и в топе. Пример: «Искра», «Живой огонь», «Негасимый».</p>
              <button type="button" className="sec-btn sec-btn-ghost" onClick={() => setTitles((rows) => [...rows, { fromDay: '', title: '', emojiId: '' }])}>
                Добавить статус
              </button>
              <ul className="flame-rows is-title">
                {titles.map((row, index) => (
                  <li key={`title-${index}`}>
                    <label>
                      <span>С дня</span>
                      <input inputMode="numeric" value={row.fromDay} onChange={(e) => {
                        const value = digits(e.target.value)
                        setTitles((rows) => rows.map((item, i) => i === index ? { ...item, fromDay: value } : item))
                      }} />
                    </label>
                    <label className="is-wide">
                      <span>Название</span>
                      <input value={row.title} maxLength={60} onChange={(e) => {
                        const title = e.target.value
                        setTitles((rows) => rows.map((item, i) => i === index ? { ...item, title } : item))
                      }} />
                    </label>
                    <button type="button" className="sec-btn sec-btn-ghost flame-drop" onClick={() => setTitles((rows) => rows.filter((_, i) => i !== index))}>Убрать</button>
                  </li>
                ))}
              </ul>
              <div className="flame-actions">
                <button type="button" className="sec-btn" disabled={busy === 'settings'} onClick={saveAllSettings}>Сохранить переключатель</button>
                <button
                  type="button"
                  className="sec-btn"
                  disabled={busy === 'titles'}
                  onClick={() => run('titles', () => saveFlameTitles({
                    titles: titles
                      .map((row) => ({ fromDay: Number(row.fromDay), title: row.title.trim(), emojiId: row.emojiId }))
                      .filter((row) => row.fromDay >= 1 && row.title),
                  }))}
                >
                  {busy === 'titles' ? 'Сохраняем…' : 'Сохранить статусы'}
                </button>
              </div>
            </section>
          )}

          {tab === 'gift' && (
            <section className="flame-card flame-rise">
              <div className="flame-card-head">
                <h3>Предмет 🎁</h3>
                <label className="flame-switch">
                  <input type="checkbox" checked={form.giftEnabled} onChange={(e) => patch('giftEnabled', e.target.checked)} />
                  <span>{form.giftEnabled ? 'Работает' : 'Выключен'}</span>
                </label>
              </div>
              <p className="flame-note">
                Тот же интерфейс, что у «бонус». Нужна приписка Cute. Победа в игре не нужна.
                Предмет в магазине должен иметь код <code>freebonus</code>.
              </p>
              <div className="flame-grid-2">
                <label className="flame-field">
                  <span>Умножение</span>
                  <input inputMode="numeric" value={form.giftMult} onChange={(e) => patch('giftMult', digits(e.target.value))} />
                </label>
                <label className="flame-field">
                  <span>Куты на клетке: от</span>
                  <input inputMode="numeric" value={form.giftKutyMin} onChange={(e) => patch('giftKutyMin', digits(e.target.value))} />
                </label>
                <label className="flame-field">
                  <span>Куты на клетке: до</span>
                  <input inputMode="numeric" value={form.giftKutyMax} onChange={(e) => patch('giftKutyMax', digits(e.target.value))} />
                </label>
              </div>

              <div className="flame-preview">
                <h4>Что увидит игрок в среднем</h4>
                <div className="flame-preview-grid">
                  <article>
                    <strong>{preview.kutyMin ?? '—'}–{preview.kutyMax ?? '—'}</strong>
                    <span>кут с клетки</span>
                  </article>
                  <article>
                    <strong>{preview.avgPerOpen ?? '—'}</strong>
                    <span>кут за одно открытие</span>
                  </article>
                  <article>
                    <strong>{preview.avgPer100 ?? '—'}</strong>
                    <span>кут за 100 открытий</span>
                  </article>
                  <article>
                    <strong>{preview.itemChancePct ?? 0}%</strong>
                    <span>шанс предмета</span>
                  </article>
                </div>
                {(preview.items || []).length > 0 && (
                  <ul className="flame-preview-items">
                    {preview.items.map((row) => (
                      <li key={row.name}><strong>{row.name}</strong><span>{row.chance}%</span></li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="flame-card-head">
                <h3>Доп. дроп после открытия</h3>
                <button type="button" className="sec-btn sec-btn-ghost" onClick={() => setGiftDrops((rows) => [...rows, { kind: 'item', amountMin: '1', amountMax: '1', itemName: '', weight: '1' }])}>
                  Добавить
                </button>
              </div>
              <ul className="flame-rows is-gift">
                {giftDrops.map((row, index) => (
                  <li key={`gift-${index}`}>
                    <label>
                      <span>Тип</span>
                      <select value={row.kind} onChange={(e) => {
                        const kind = e.target.value
                        setGiftDrops((rows) => rows.map((item, i) => i === index ? { ...item, kind } : item))
                      }}>
                        {GIFT_KINDS.map((kind) => <option key={kind.id} value={kind.id}>{kind.label}</option>)}
                      </select>
                    </label>
                    <label>
                      <span>Вес</span>
                      <input inputMode="numeric" value={row.weight} onChange={(e) => {
                        const value = digits(e.target.value)
                        setGiftDrops((rows) => rows.map((item, i) => i === index ? { ...item, weight: value } : item))
                      }} />
                    </label>
                    {row.kind === 'kuty' ? (
                      <>
                        <label>
                          <span>От</span>
                          <input inputMode="numeric" value={row.amountMin} onChange={(e) => {
                            const value = digits(e.target.value)
                            setGiftDrops((rows) => rows.map((item, i) => i === index ? { ...item, amountMin: value } : item))
                          }} />
                        </label>
                        <label>
                          <span>До</span>
                          <input inputMode="numeric" value={row.amountMax} onChange={(e) => {
                            const value = digits(e.target.value)
                            setGiftDrops((rows) => rows.map((item, i) => i === index ? { ...item, amountMax: value } : item))
                          }} />
                        </label>
                      </>
                    ) : (
                      <label className="is-wide">
                        <span>Предмет</span>
                        <select value={row.itemName} onChange={(e) => {
                          const itemName = e.target.value
                          setGiftDrops((rows) => rows.map((item, i) => i === index ? { ...item, itemName } : item))
                        }}>
                          <option value="">Выберите</option>
                          {items.map((name) => <option key={name} value={name}>{name}</option>)}
                        </select>
                      </label>
                    )}
                    <button type="button" className="sec-btn sec-btn-ghost flame-drop" onClick={() => setGiftDrops((rows) => rows.filter((_, i) => i !== index))}>Убрать</button>
                  </li>
                ))}
              </ul>
              <div className="flame-actions">
                <button type="button" className="sec-btn" disabled={busy === 'settings'} onClick={saveAllSettings}>Сохранить умножение</button>
                <button
                  type="button"
                  className="sec-btn"
                  disabled={busy === 'gift'}
                  onClick={() => run('gift', () => saveFlameGiftDrops({
                    drops: giftDrops
                      .map((row) => ({
                        kind: row.kind,
                        amountMin: Math.max(1, Number(row.amountMin) || 1),
                        amountMax: Math.max(1, Number(row.amountMax) || 1),
                        itemName: row.kind === 'item' ? row.itemName : '',
                        weight: Math.max(1, Number(row.weight) || 1),
                      }))
                      .filter((row) => row.kind && (row.kind !== 'item' || row.itemName)),
                  }))}
                >
                  {busy === 'gift' ? 'Сохраняем…' : 'Сохранить дроп'}
                </button>
              </div>
            </section>
          )}

          {tab === 'live' && (
            <>
              <section className="flame-card flame-rise">
                <h3>Живые серии</h3>
                {(board.people || []).length === 0 && <p className="flame-empty">Пока никто не держит огонёк.</p>}
                <ol className="flame-people">
                  {(board.people || []).map((person) => (
                    <li key={person.userId}>
                      <strong>{person.name}{person.title ? ` · ${person.title}` : ''}</strong>
                      <span>{person.record ? `рекорд ${person.label}` : person.label}</span>
                    </li>
                  ))}
                </ol>
              </section>
              <section className="flame-card flame-rise">
                <h3>Последние награды</h3>
                <p className="flame-note">Всё, что люди реально получили: дни серии, тёплый час и 🎁.</p>
                {(board.loot || []).length === 0 && <p className="flame-empty">Пока пусто — награды появятся сами.</p>}
                <ul className="flame-loot">
                  {(board.loot || []).map((row) => (
                    <li key={row.id}>
                      <div>
                        <strong>{row.name}</strong>
                        <span>{sourceLabel(row.source)}</span>
                      </div>
                      <em>{row.label}</em>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </>
      )}
    </section>
  )
}
