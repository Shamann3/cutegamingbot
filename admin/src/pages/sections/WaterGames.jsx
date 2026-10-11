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

const FALLBACK_RULES = {
  percentLow: 4,
  percentHigh: 8,
  shotCap: 1500,
  dayCap: 4000,
  poorBalance: 50,
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

function RulesCard({ rules, sample, busy, saved, onChange, onSample, onSave }) {
  const low = Number(rules.percentLow)
  const high = Number(rules.percentHigh)
  const cap = Number(rules.shotCap)
  const day = Number(rules.dayCap)
  const poor = Number(rules.poorBalance)
  const balance = Number(sample || 0)
  const ready = low >= 1 && high >= low && high <= 100 && cap >= 1 && day >= 1 && poor >= 0 && sample !== ''
  const from = ready ? pourAmount(balance, low, cap, day, poor) : 0
  const to = ready ? pourAmount(balance, high, cap, day, poor) : 0
  const span = Math.max(1, high - low)
  const set = (key) => (event) => onChange({ ...rules, [key]: digits(event.target.value) })

  let verdict = 'Укажите процент от и до'
  if (ready && balance < poor) verdict = 'С такого баланса брать нечего'
  else if (ready && from === to) verdict = `Заберёт ${money(from)} кут`
  else if (ready) verdict = `Заберёт от ${money(from)} до ${money(to)} кут`

  return (
    <section className={`water-rules${saved ? ' is-saved' : ''}`}>
      <h4 className="sec-title">Сколько забирает выстрел</h4>
      <p className="sec-subtitle">Процент от баланса того, кого облили. Число каждый раз случайное, внутри диапазона.</p>
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
        <label className="water-field water-rule-span">
          <span>Ниже этого баланса брать нечего</span>
          <input className="sec-input" inputMode="numeric" aria-label="Порог бедности" value={rules.poorBalance} onChange={set('poorBalance')} />
        </label>
      </div>
      <label className="water-field">
        <span>Если у человека, кут</span>
        <input className="sec-input" inputMode="numeric" aria-label="Пример баланса" value={sample} onChange={(event) => onSample(digits(event.target.value))} />
      </label>
      <p className="water-pour" key={verdict}>{verdict}</p>
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
                  <span className="water-note">{OUTCOME[row.outcome] || row.outcome}{row.amount ? ` · ${money(row.amount)} кут` : ''}</span>
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
