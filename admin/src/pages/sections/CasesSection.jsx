import { useEffect, useState } from 'react'
import { fetchCaseBoard, saveCasePrice, saveCaseRules, saveCaseStock } from '../../lib/adminClient'
import OpenUserLink from '../../components/OpenUserLink'
import '../../styles/cases.css'

function money(value) {
  return new Intl.NumberFormat('ru-RU').format(Number(value) || 0)
}

function quietName(name) {
  const text = String(name || '').replace(/@/g, '').trim()
  return text || 'Игрок'
}

function when(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function digits(value) {
  return String(value ?? '').replace(/[^\d]/g, '')
}

function averageOf(bands) {
  const rows = bands || []
  const sum = rows.reduce((total, row) => total + (Number(row.chance) || 0) * (Number(row.amount) || 0), 0)
  return sum / 100
}

function ready(card) {
  const bands = card.bands || []
  const max = Number(card.max)
  if (!max || bands.length < 2 || bands.length > 6) return false
  const chances = bands.reduce((total, row) => total + (Number(row.chance) || 0), 0)
  if (chances !== 100) return false
  return bands.every((row) => {
    const chance = Number(row.chance)
    const amount = Number(row.amount)
    return chance >= 1 && chance <= 100 && amount >= 1 && amount <= max
  }) && Math.max(...bands.map((row) => Number(row.amount) || 0)) === max
}

function bandRole(row, bands, max) {
  const amount = Number(row.amount) || 0
  const amounts = (bands || []).map((item) => Number(item.amount) || 0).filter((value) => value > 0)
  if (!amount || !amounts.length) return 'Сумма'
  const low = Math.min(...amounts)
  const top = Math.max(...amounts)
  if (amount === Number(max) && amount === top) return 'Потолок'
  if (amount === low) return 'Маленькая сумма'
  if (amount === top) return 'Большая сумма'
  return 'Средняя сумма'
}

function CaseCard({ card, onSave }) {
  const [draft, setDraft] = useState(card)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const ok = ready(draft)
  const chanceSum = (draft.bands || []).reduce((total, row) => total + (Number(row.chance) || 0), 0)
  const mean = averageOf(draft.bands)

  useEffect(() => {
    setDraft(card)
  }, [card])

  const setBand = (index, key, value) => {
    const bands = draft.bands.map((row, at) => (at === index ? { ...row, [key]: digits(value) } : row))
    setDraft({ ...draft, bands })
    setSaved(false)
  }

  const addBand = () => {
    if (draft.bands.length >= 6) return
    setDraft({ ...draft, bands: [...draft.bands, { chance: '', amount: '' }] })
    setSaved(false)
  }

  const dropBand = (index) => {
    if (draft.bands.length <= 2) return
    setDraft({ ...draft, bands: draft.bands.filter((_, at) => at !== index) })
    setSaved(false)
  }

  const save = async () => {
    setBusy(true)
    setError('')
    try {
      const next = await onSave({
        id: draft.id,
        max: Number(draft.max),
        bands: draft.bands.map((row) => ({ chance: Number(row.chance), amount: Number(row.amount) })),
      })
      setDraft(next)
      setSaved(true)
    } catch (err) {
      setError(err?.message || 'Кейс не сохранился')
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className={`case-card${saved ? ' is-saved' : ''}`}>
      <header>
        <h3>{draft.emoji} {draft.name}</h3>
        <p>
          {ok
            ? `В среднем ${money(mean)} кут. Потолок ${money(draft.max)} выпадает в ${draft.bands.find((row) => Number(row.amount) === Number(draft.max))?.chance || 0}% случаев.`
            : chanceSum !== 100
              ? `Шансы сейчас ${chanceSum} из 100`
              : 'Самая большая сумма должна равняться потолку'}
        </p>
      </header>
      <label>
        Потолок, кут
        <input
          inputMode="numeric"
          aria-label={`Потолок ${draft.name}`}
          value={draft.max}
          onChange={(event) => {
            setDraft({ ...draft, max: digits(event.target.value) })
            setSaved(false)
          }}
        />
      </label>
      <div className="case-meter" aria-hidden="true">
        {(draft.bands || []).map((row, index) => (
          <i key={index} style={{ width: `${Math.max(Number(row.chance) || 0, 0)}%` }} />
        ))}
      </div>
      <ul>
        {(draft.bands || []).map((row, index) => (
          <li key={index}>
            <span className="case-role">{bandRole(row, draft.bands, draft.max)}</span>
            <label>
              Как часто, %
              <input
                inputMode="numeric"
                aria-label={`Шанс ${index + 1} ${draft.name}`}
                value={row.chance}
                onChange={(event) => setBand(index, 'chance', event.target.value)}
              />
            </label>
            <label>
              Сумма, кут
              <input
                inputMode="numeric"
                aria-label={`Приз ${index + 1} ${draft.name}`}
                value={row.amount}
                onChange={(event) => setBand(index, 'amount', event.target.value)}
              />
            </label>
            <button type="button" onClick={() => dropBand(index)} disabled={draft.bands.length <= 2}>
              Убрать
            </button>
          </li>
        ))}
      </ul>
      <p className="case-sum">Сейчас {chanceSum} из 100</p>
      {error && <p className="case-fault">{error}</p>}
      <div className="case-actions">
        <button type="button" onClick={addBand} disabled={draft.bands.length >= 6}>Ещё исход</button>
        <button type="button" onClick={save} disabled={!ok || busy}>{busy ? 'Пишем…' : 'Сохранить'}</button>
      </div>
    </article>
  )
}

function ShelfCard({ item, delay = '0ms', onPrice, onStock }) {
  const [price, setPrice] = useState(String(item.price ?? 0))
  const [stock, setStock] = useState(String(item.remains ?? 0))
  const [busy, setBusy] = useState('')
  const [saved, setSaved] = useState('')
  const [error, setError] = useState('')
  const priceSame = price !== '' && Number(price) === Number(item.price)
  const stockSame = stock !== '' && Number(stock) === Number(item.remains)

  useEffect(() => {
    setPrice(String(item.price ?? 0))
    setStock(String(item.remains ?? 0))
  }, [item.price, item.remains])

  const run = async (kind) => {
    setBusy(kind)
    setError('')
    setSaved('')
    try {
      if (kind === 'price') await onPrice(Number(price))
      else await onStock(Number(stock))
      setSaved(kind)
    } catch (err) {
      setError(err?.message || 'Не сохранилось')
    } finally {
      setBusy('')
    }
  }

  return (
    <article className={`case-shelf${saved ? ' is-saved' : ''}${item.missing ? ' is-missing' : ''}`} style={{ animationDelay: delay }}>
      <header>
        <h3>{item.emoji} {item.name}</h3>
        <p>{item.missing ? 'В магазине ещё нет' : `Сейчас ${Number(item.remains) > 0 ? `${money(item.remains)} шт.` : 'нет в продаже'}`}</p>
      </header>
      <label>
        Количество, шт.
        <input
          inputMode="numeric"
          aria-label={`Количество ${item.name}`}
          value={stock}
          disabled={item.missing}
          onChange={(event) => { setStock(digits(event.target.value)); setSaved('') }}
        />
      </label>
      <label>
        Цена, кут
        <input
          inputMode="numeric"
          aria-label={`Цена ${item.name}`}
          value={price}
          disabled={item.missing}
          onChange={(event) => { setPrice(digits(event.target.value)); setSaved('') }}
        />
      </label>
      {error && <p className="case-fault">{error}</p>}
      <div className="case-actions">
        <button type="button" disabled={item.missing || busy === 'stock' || stock === '' || stockSame} onClick={() => run('stock')}>
          {busy === 'stock' ? 'Пишем…' : saved === 'stock' ? 'Количество записано' : 'Количество'}
        </button>
        <button type="button" disabled={item.missing || busy === 'price' || price === '' || priceSame} onClick={() => run('price')}>
          {busy === 'price' ? 'Пишем…' : saved === 'price' ? 'Цена записана' : 'Цена'}
        </button>
      </div>
    </article>
  )
}

function FundDesk({ board }) {
  const funds = board.funds || []
  const total = Number(board.fund) || 0
  const stats = board.stats || {}
  const winners = stats.winners || []
  const recent = stats.recent || []
  return (
    <>
      <section className="case-fund">
        <header>
          <h3>Касса</h3>
          <p>
            {total > 0
              ? `В технических группах ${money(total)} кут. Приз списывается отсюда.`
              : 'Кейсы временно недоступны. В технических группах нет кут — нужно немного подождать.'}
          </p>
        </header>
        <ul>
          {funds.length === 0 && <li className="is-empty">Касс пока нет</li>}
          {funds.map((row, index) => (
            <li key={row.id} style={{ animationDelay: `${index * 50}ms` }}>
              <span>{row.name}</span>
              <b>{money(row.balance)}</b>
            </li>
          ))}
        </ul>
      </section>
      <section className="case-ledger">
        <header>
          <h3>Кто выиграл</h3>
          <p>
            {Number(stats.opens) > 0
              ? `${money(stats.opens)} открытий · ${money(stats.paid)} кут · лучший ${money(stats.best)}`
              : 'Пока никто не открывал.'}
          </p>
        </header>
        <div className="case-kinds">
          {(stats.byCase || []).map((row) => (
            <p key={row.id}>
              <span>{row.emoji} {row.name}</span>
              <b>{money(row.opens)} · {money(row.paid)}</b>
            </p>
          ))}
        </div>
        {winners.length > 0 && (
          <ol>
            {winners.map((row, index) => (
              <li key={row.userId} style={{ animationDelay: `${index * 35}ms` }}>
                <OpenUserLink userId={row.userId} name={quietName(row.name)} onOpenUser={board.onOpenUser} />
                <span>{money(row.opens)} откр.</span>
                <b>{money(row.won)}</b>
              </li>
            ))}
          </ol>
        )}
        {recent.length > 0 && (
          <div className="case-recent">
            <h3>Последние</h3>
            <ul>
              {recent.map((row) => (
                <li key={row.id || `${row.userId}-${row.at}-${row.amount}`}>
                  <OpenUserLink userId={row.userId} name={quietName(row.name)} onOpenUser={board.onOpenUser} />
                  <span>{row.emoji} {row.caseName}</span>
                  <b>+{money(row.amount)}</b>
                  <time>{when(row.at)}</time>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </>
  )
}

export default function CasesSection({ onOpenUser }) {
  const [board, setBoard] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let stop = false
    fetchCaseBoard()
      .then((data) => { if (!stop) setBoard(data) })
      .catch((err) => { if (!stop) setError(err?.message || 'Кейсы не открылись') })
    return () => { stop = true }
  }, [])

  return (
    <section className="case-desk">
      <header className="case-head">
        <h2>Кейсы</h2>
        <p>Цена, количество и потолок. Приз списывается с технических групп. Комиссии нет: игрок получает ровно выпавшее число.</p>
      </header>
      {error && <p className="case-fault">{error}</p>}
      {!board && !error && <p>Считаем кейсы…</p>}
      {board && (
        <>
          <header className="case-odds">
            <h3>Как часто выпадает сумма</h3>
            <p>У каждого кейса свои шансы. Маленькая сумма и потолок настраиваются отдельно. В сумме должно быть 100.</p>
          </header>
          <div className="case-grid">
            {(board.cases || []).map((card, index) => (
              <div key={card.id} style={{ animationDelay: `${index * 70}ms` }}>
                <CaseCard
                  card={card}
                  onSave={async (body) => {
                    const saved = await saveCaseRules(body)
                    setBoard((prev) => ({
                      ...prev,
                      cases: (prev?.cases || []).map((item) => (item.id === saved.id ? saved : item)),
                    }))
                    return saved
                  }}
                />
              </div>
            ))}
          </div>
        </>
      )}
      {board && <FundDesk board={{ ...board, onOpenUser }} />}
      {board && (
        <div className="case-grid case-shop">
          {(board.items || []).map((item, index) => (
            <div key={item.name1 || item.name}>
              <ShelfCard
                item={item}
                delay={`${index * 60}ms`}
                onPrice={async (price) => {
                  const saved = await saveCasePrice({ id: Number(item.id), price })
                  setBoard((prev) => ({
                    ...prev,
                    items: (prev?.items || []).map((row) => (row.id === saved.id ? { ...row, price: saved.price } : row)),
                  }))
                }}
                onStock={async (remains) => {
                  const saved = await saveCaseStock({ id: Number(item.id), remains })
                  setBoard((prev) => ({
                    ...prev,
                    items: (prev?.items || []).map((row) => (row.id === saved.id ? { ...row, remains: saved.remains } : row)),
                  }))
                }}
              />
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
