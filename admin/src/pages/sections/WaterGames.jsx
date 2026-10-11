import { useEffect, useRef, useState } from 'react'
import { fetchWaterBoard, saveWaterPrice, saveWaterRules, saveWaterStock } from '../../lib/adminClient'
import OpenUserLink from '../../components/OpenUserLink'
import '../../styles/water-games.css'

function quietName(name) {
  const text = String(name || '').replace(/@/g, '').trim()
  return text || 'Игрок'
}

const OUTCOME = {
  hit: 'попадание',
  broke: 'брать нечего',
  shield: 'защита',
}

function money(value) {
  return new Intl.NumberFormat('ru-RU').format(Number(value) || 0)
}

const FALLBACK_GROUPS = [
  { id: '-1004324787050', name: 'Игры' },
  { id: '-1004318525471', name: 'Фон' },
  { id: '-1003855337972', name: 'Дом игр' },
  { id: '-1004238101266', name: 'Копилка' },
]

const FALLBACK_RULES = {
  percentLow: 4,
  percentHigh: 8,
  shotCap: 1500,
  dayCap: 4000,
  poorBalance: 50,
  commissionPercent: 10,
  feeChatId: FALLBACK_GROUPS[0].id,
  pistolDayOn: false,
  pistolDayMax: 10,
}

function pourAmount(balance, percent, cap, dayLeft, poor) {
  if (balance < poor) return 0
  let raw = Math.floor(balance * percent / 100)
  if (raw < 1) raw = 1
  const room = Math.min(cap, dayLeft, balance)
  if (room < 1) return 0
  return Math.min(raw, room)
}

function digits(value) {
  return String(value ?? '').replace(/[^\d]/g, '')
}

function cutOf(amount, rate) {
  const fee = Math.floor(Number(amount) * Number(rate) / 100)
  return { shooter: Number(amount) - fee, project: fee }
}

function rangeLine(label, low, high) {
  if (low === high) return `${label} ${money(low)} кут`
  return `${label} от ${money(low)} до ${money(high)} кут`
}

function RulesCard({ rules, groups, sample, busy, saved, onChange, onSample, onSave }) {
  const low = Number(rules.percentLow)
  const high = Number(rules.percentHigh)
  const cap = Number(rules.shotCap)
  const day = Number(rules.dayCap)
  const poor = Number(rules.poorBalance)
  const rate = Number(rules.commissionPercent)
  const shotsOn = rules.pistolDayOn === true
  const shots = Number(rules.pistolDayMax)
  const balance = Number(sample || 0)
  const wallets = groups && groups.length ? groups : FALLBACK_GROUPS
  const feeId = String(rules.feeChatId || wallets[0].id)
  const feeName = (wallets.find((item) => String(item.id) === feeId) || wallets[0]).name
  const shotsReady = !shotsOn || (rules.pistolDayMax !== '' && shots >= 1 && shots <= 100000)
  const ready = low >= 1 && high >= low && high <= 100 && cap >= 1 && day >= 1 && poor >= 0
    && rules.commissionPercent !== '' && rate >= 0 && rate <= 100 && shotsReady && sample !== ''
  const from = ready ? pourAmount(balance, low, cap, day, poor) : 0
  const to = ready ? pourAmount(balance, high, cap, day, poor) : 0
  const fromCut = cutOf(from, rate)
  const toCut = cutOf(to, rate)
  const span = Math.max(1, high - low)
  const set = (key) => (event) => onChange({ ...rules, [key]: digits(event.target.value) })

  let verdict = 'Укажите процент от и до'
  if (ready && balance < poor) verdict = 'С такого баланса брать нечего'
  else if (ready && from === to) verdict = `Заберёт ${money(from)} кут`
  else if (ready) verdict = `Заберёт от ${money(from)} до ${money(to)} кут`
  const showCut = ready && balance >= poor && (from > 0 || to > 0)
  const shooterLine = rangeLine('Облившему', fromCut.shooter, toCut.shooter)
  const projectLine = rangeLine(`В «${feeName}»`, fromCut.project, toCut.project)
  const pistolLine = shotsOn
    ? `Пистолетик: не больше ${money(shots || 0)} раз в сутки`
    : 'Пистолетик без лимита в сутки'
  const recap = ready
    ? `${low}–${high}% · за раз до ${money(cap)} · за сутки до ${money(day)} · ниже ${money(poor)} не берём · комиссия ${rate}% · ${feeName}`
    : ''

  return (
    <section className={`water-rules${saved ? ' is-saved' : ''}`}>
      <h4 className="sec-title">Сколько забирает выстрел</h4>
      <p className="sec-subtitle">Процент, потолки, комиссия и лимит пистолетика. Комиссия — доля уже снятой суммы, она падает на баланс выбранной технической группы.</p>
      <div className="water-rule-grid">
        <label className="water-field">
          <span>От, %</span>
          <input className="sec-input" inputMode="numeric" aria-label="Процент от" value={rules.percentLow} onChange={set('percentLow')} />
        </label>
        <label className="water-field">
          <span>До, %</span>
          <input className="sec-input" inputMode="numeric" aria-label="Процент до" value={rules.percentHigh} onChange={set('percentHigh')} />
        </label>
      </div>
      <div className="water-meter" aria-hidden>
        <i style={{ left: `${Math.min(Math.max(low, 0), 100)}%`, width: `${Math.min(span, 100)}%` }} />
      </div>
      <div className="water-rule-grid">
        <label className="water-field">
          <span>Не больше за раз, кут</span>
          <input className="sec-input" inputMode="numeric" aria-label="Потолок выстрела" value={rules.shotCap} onChange={set('shotCap')} />
        </label>
        <label className="water-field">
          <span>Не больше за сутки, кут</span>
          <input className="sec-input" inputMode="numeric" aria-label="Потолок за сутки" value={rules.dayCap} onChange={set('dayCap')} />
        </label>
        <label className="water-field">
          <span>Ниже этого баланса брать нечего</span>
          <input className="sec-input" inputMode="numeric" aria-label="Порог бедности" value={rules.poorBalance} onChange={set('poorBalance')} />
        </label>
        <label className="water-field">
          <span>Комиссия проекта, %</span>
          <input className="sec-input" inputMode="numeric" aria-label="Комиссия проекта" value={rules.commissionPercent ?? ''} onChange={set('commissionPercent')} />
        </label>
        <label className="water-field water-rule-span">
          <span>Куда падает комиссия</span>
          <select className="sec-input" aria-label="Техническая группа" value={feeId} onChange={(event) => onChange({ ...rules, feeChatId: event.target.value })}>
            {wallets.map((item) => (
              <option key={item.id} value={String(item.id)}>{item.name}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="water-note">В «Игры», «Фон» и «Копилку» приходит сообщение «+». «Дом игр» копится без сообщения.</p>
      <button
        type="button"
        role="switch"
        aria-checked={shotsOn}
        aria-label="Лимит пистолетика в сутки"
        className={`water-switch${shotsOn ? ' is-on' : ''}`}
        onClick={() => onChange({ ...rules, pistolDayOn: !shotsOn })}
      >
        <span>Лимит пистолетика в сутки</span>
        <i />
      </button>
      <div className={`water-drawer${shotsOn ? ' is-open' : ''}`}>
        <div>
          <label className="water-field">
            <span>Сколько раз в сутки</span>
            <input className="sec-input" inputMode="numeric" aria-label="Сколько раз в сутки" value={rules.pistolDayMax ?? ''} onChange={set('pistolDayMax')} />
          </label>
        </div>
      </div>
      <label className="water-field">
        <span>Если у человека, кут</span>
        <input className="sec-input" inputMode="numeric" aria-label="Пример баланса" value={sample} onChange={(event) => onSample(digits(event.target.value))} />
      </label>
      {recap && <p className="water-note">{recap}</p>}
      <p className="water-pour" key={verdict}>{verdict}</p>
      {showCut && <p className="water-pour water-cut" key={shooterLine}>{shooterLine}</p>}
      {showCut && <p className="water-pour water-cut" key={projectLine}>{projectLine}</p>}
      <p className="water-pour water-cut" key={pistolLine}>{pistolLine}</p>
      <button type="button" className="sec-btn" disabled={!ready || busy} onClick={onSave}>
        {busy ? 'Сохраняем…' : saved ? 'Правила сохранены' : 'Сохранить правила'}
      </button>
    </section>
  )
}

export default function WaterGames({ onOpenUser = null, page = false }) {
  const [board, setBoard] = useState(null)
  const [error, setError] = useState('')
  const [drafts, setDrafts] = useState({})
  const [stocks, setStocks] = useState({})
  const [busy, setBusy] = useState('')
  const [savedId, setSavedId] = useState('')
  const [savedKind, setSavedKind] = useState('')
  const [rulesDraft, setRulesDraft] = useState(FALLBACK_RULES)
  const [sample, setSample] = useState('1000')
  const [rulesBusy, setRulesBusy] = useState(false)
  const [rulesSaved, setRulesSaved] = useState(false)
  const [ledger, setLedger] = useState('pours')
  const savedTimer = useRef(0)

  const load = () => {
    setError('')
    return fetchWaterBoard()
      .then((data) => {
        setBoard(data)
        const next = {}
        const nextStock = {}
        for (const item of data.items || []) {
          next[item.id] = String(item.price)
          nextStock[item.id] = String(item.remains ?? 0)
        }
        setDrafts(next)
        setStocks(nextStock)
        setRulesDraft({ ...FALLBACK_RULES, ...(data.rules || {}) })
      })
      .catch((err) => setError(err.message || 'Не удалось открыть водные игры'))
  }

  useEffect(() => { load() }, [])
  useEffect(() => () => window.clearTimeout(savedTimer.current), [])

  const remember = (item, patch, kind) => {
    setBoard((prev) => ({
      ...prev,
      items: prev.items.map((row) => (row.id === item.id ? { ...row, ...patch } : row)),
    }))
    setSavedId(item.id)
    setSavedKind(kind)
    window.clearTimeout(savedTimer.current)
    savedTimer.current = window.setTimeout(() => {
      setSavedId((current) => (current === item.id ? '' : current))
    }, 1400)
  }

  const saveStock = async (item) => {
    const stock = String(stocks[item.id] ?? '')
    if (stock === '' || Number(stock) === Number(item.remains)) return
    setBusy(`stock:${item.id}`)
    setError('')
    try {
      const saved = await saveWaterStock({ id: Number(item.id), remains: Number(stock) })
      setStocks((prev) => ({ ...prev, [item.id]: String(saved.remains) }))
      remember(item, { remains: saved.remains }, 'stock')
    } catch (err) {
      setError(err.message || 'Количество не сохранилось')
    } finally {
      setBusy('')
    }
  }

  const savePrice = async (item) => {
    const draft = String(drafts[item.id] ?? '')
    if (draft === '' || Number(draft) === Number(item.price)) return
    setBusy(`price:${item.id}`)
    setError('')
    try {
      const saved = await saveWaterPrice({ id: Number(item.id), price: Number(draft) })
      setDrafts((prev) => ({ ...prev, [item.id]: String(saved.price) }))
      remember(item, { price: saved.price }, 'price')
    } catch (err) {
      setError(err.message || 'Цена не сохранилась')
    } finally {
      setBusy('')
    }
  }

  const totals = board?.totals || {}

  return (
    <div className="water-desk">
      <header className="sec-header">
        {page ? <h2 className="sec-title">Водные игры</h2> : <h3 className="sec-title">Водные игры</h3>}
        <p className="sec-subtitle">Количество в магазине, цены и кто кого облил. Вкладка только у создателя.</p>
      </header>
      {error && <p className="sec-empty">{error}</p>}
      {!board && !error && <p className="sec-empty">Собираем статистику…</p>}
      {board && (
        <>
          <RulesCard
            rules={rulesDraft}
            groups={(board.feeGroups && board.feeGroups.length) ? board.feeGroups : FALLBACK_GROUPS}
            sample={sample}
            busy={rulesBusy}
            saved={rulesSaved}
            onChange={(next) => {
              setRulesSaved(false)
              setRulesDraft(next)
            }}
            onSample={setSample}
            onSave={async () => {
              setRulesBusy(true)
              setError('')
              setRulesSaved(false)
              try {
                const saved = await saveWaterRules({
                  percentLow: Number(rulesDraft.percentLow),
                  percentHigh: Number(rulesDraft.percentHigh),
                  shotCap: Number(rulesDraft.shotCap),
                  dayCap: Number(rulesDraft.dayCap),
                  poorBalance: Number(rulesDraft.poorBalance),
                  commissionPercent: Number(rulesDraft.commissionPercent),
                  feeChatId: String(rulesDraft.feeChatId || FALLBACK_GROUPS[0].id),
                  pistolDayOn: rulesDraft.pistolDayOn === true,
                  pistolDayMax: Number(rulesDraft.pistolDayMax || 0),
                })
                setRulesDraft(saved.rules)
                setRulesSaved(true)
              } catch (err) {
                setError(err.message || 'Правила не сохранились')
              } finally {
                setRulesBusy(false)
              }
            }}
          />

          <section className="water-shop">
            <h4 className="sec-title">Количество в магазине</h4>
            <p className="sec-subtitle">Число — сколько штук сейчас можно купить. Покупка уменьшает его. Ноль снимает предмет с продажи.</p>
            <div className="water-shop-list">
              {(board.items || []).map((item) => {
                const draft = String(drafts[item.id] ?? '')
                const stock = String(stocks[item.id] ?? '')
                const stockSame = stock !== '' && Number(stock) === Number(item.remains)
                const priceSame = draft !== '' && Number(draft) === Number(item.price)
                const stockBusy = busy === `stock:${item.id}`
                const priceBusy = busy === `price:${item.id}`
                const savedStock = savedId === item.id && savedKind === 'stock'
                return (
                  <article key={item.id} className={`water-card${savedId === item.id ? ' is-saved' : ''}`}>
                    <strong>{item.emoji} {item.name}</strong>
                    <p className="water-now">Сейчас в продаже: {Number(item.remains) > 0 ? `${money(item.remains)} шт.` : 'нет'}</p>
                    <label className="water-field">
                      <span>Количество, шт.</span>
                      <input
                        className="sec-input"
                        inputMode="numeric"
                        aria-label={`Количество: ${item.name}`}
                        value={stock}
                        onChange={(event) => setStocks((prev) => ({ ...prev, [item.id]: event.target.value.replace(/[^\d]/g, '') }))}
                      />
                    </label>
                    <button type="button" className="sec-btn" disabled={stockBusy || stock === '' || stockSame} onClick={() => saveStock(item)}>
                      {stockBusy ? 'Сохраняем…' : savedStock && stockSame ? 'Количество сохранено' : stockSame ? 'Это текущее количество' : 'Сохранить количество'}
                    </button>
                    <label className="water-field">
                      <span>Цена, кут</span>
                      <input
                        className="sec-input"
                        inputMode="numeric"
                        aria-label={`Цена: ${item.name}`}
                        value={draft}
                        onChange={(event) => setDrafts((prev) => ({ ...prev, [item.id]: event.target.value.replace(/[^\d]/g, '') }))}
                      />
                    </label>
                    <button type="button" className="sec-btn sec-btn-ghost" disabled={priceBusy || draft === '' || priceSame} onClick={() => savePrice(item)}>
                      {priceBusy ? 'Сохраняем…' : priceSame ? 'Это текущая цена' : 'Сохранить цену'}
                    </button>
                  </article>
                )
              })}
            </div>
            {(board.items || []).length === 0 && <p className="sec-empty">Предметов водных игр в магазине ещё нет.</p>}
          </section>

          <div className="water-stats">
            <div className="water-stat" style={{ animationDelay: '0ms' }}><b>{money(totals.hits)}</b><span>попаданий всего</span></div>
            <div className="water-stat" style={{ animationDelay: '40ms' }}><b>{money(totals.moved)}</b><span>кут перешло из рук в руки</span></div>
            <div className="water-stat" style={{ animationDelay: '80ms' }}><b>{money(totals.hitsToday)}</b><span>попаданий за сутки · {money(totals.movedToday)} кут</span></div>
            <div className="water-stat" style={{ animationDelay: '120ms' }}><b>{money(totals.shields)}</b><span>сейчас под защитой · сейфов {money(totals.forever)}</span></div>
            <div className="water-stat" style={{ animationDelay: '160ms' }}><b>{money(totals.project)}</b><span>кут получил проект</span></div>
          </div>

          <section className="water-ledger">
            <h4 className="sec-title">Сколько раз обливали</h4>
            <p className="sec-subtitle">Имя открывает карточку. Человека это не упоминает и не будит.</p>
            <div className="water-views" role="tablist" aria-label="Статистика обливаний">
              <button type="button" role="tab" aria-selected={ledger === 'pours'} className={ledger === 'pours' ? 'is-on' : ''} onClick={() => setLedger('pours')}>Кто обливал</button>
              <button type="button" role="tab" aria-selected={ledger === 'soaked'} className={ledger === 'soaked' ? 'is-on' : ''} onClick={() => setLedger('soaked')}>Кого обливали</button>
              <button type="button" role="tab" aria-selected={ledger === 'pairs'} className={ledger === 'pairs' ? 'is-on' : ''} onClick={() => setLedger('pairs')}>Кто кого</button>
            </div>
            <div key={ledger} className="water-pane">
            {ledger === 'pours' && (
              <ol className="water-rank">
                {(board.pours || []).map((row, index) => (
                  <li key={row.userId} style={{ animationDelay: `${index * 30}ms` }}>
                    <b>{index + 1}</b>
                    <OpenUserLink userId={row.userId} name={quietName(row.name)} onOpenUser={onOpenUser} />
                    <span className="water-note">{row.pours} раз · попаданий {row.hits} · унёс {money(row.taken)} кут</span>
                  </li>
                ))}
              </ol>
            )}
            {ledger === 'soaked' && (
              <ol className="water-rank">
                {(board.soaked || []).map((row, index) => (
                  <li key={row.userId} style={{ animationDelay: `${index * 30}ms` }}>
                    <b>{index + 1}</b>
                    <OpenUserLink userId={row.userId} name={quietName(row.name)} onOpenUser={onOpenUser} />
                    <span className="water-note">{row.pours} раз · попаданий {row.hits} · ушло {money(row.lost)} кут</span>
                  </li>
                ))}
              </ol>
            )}
            {ledger === 'pairs' && (
              <ol className="water-rank">
                {(board.pairs || []).map((row, index) => (
                  <li key={`${row.shooter.userId}-${row.target.userId}`} style={{ animationDelay: `${index * 30}ms` }}>
                    <b>{index + 1}</b>
                    <span className="water-pair">
                      <OpenUserLink userId={row.shooter.userId} name={quietName(row.shooter.name)} onOpenUser={onOpenUser} />
                      <i>облил</i>
                      <OpenUserLink userId={row.target.userId} name={quietName(row.target.name)} onOpenUser={onOpenUser} />
                    </span>
                    <span className="water-note">{row.times} раз · попаданий {row.hits} · {money(row.taken)} кут</span>
                  </li>
                ))}
              </ol>
            )}
            {ledger === 'pours' && (board.pours || []).length === 0 && <p className="sec-empty">Ещё никто не обливал.</p>}
            {ledger === 'soaked' && (board.soaked || []).length === 0 && <p className="sec-empty">Ещё никого не обливали.</p>}
            {ledger === 'pairs' && (board.pairs || []).length === 0 && <p className="sec-empty">Пар ещё нет.</p>}
            </div>
          </section>

          <section>
            <h4 className="sec-title">Последние выстрелы</h4>
            <ul className="water-recent">
              {(board.recent || []).map((row, index) => (
                <li key={`${row.at}-${index}`} style={{ animationDelay: `${index * 30}ms` }}>
                  <span className="water-pair">
                    <OpenUserLink userId={row.shooter.userId} name={quietName(row.shooter.name)} onOpenUser={onOpenUser} />
                    <i>→</i>
                    <OpenUserLink userId={row.target.userId} name={quietName(row.target.name)} onOpenUser={onOpenUser} />
                  </span>
                  <span className="water-note">{OUTCOME[row.outcome] || row.outcome}{row.amount ? ` · ${money(row.amount)} кут` : ''}{row.fee ? ` · проект ${money(row.fee)}` : ''}</span>
                </li>
              ))}
            </ul>
            {board.recent?.length === 0 && <p className="sec-empty">Лента пустая. Первый выстрел появится здесь.</p>}
          </section>

        </>
      )}
    </div>
  )
}
