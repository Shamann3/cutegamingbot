import { useEffect, useState } from 'react'
import { fetchCaseBoard, saveCasePrice, saveCaseRules, saveCaseStock } from '../../lib/adminClient'
import '../../styles/cases.css'

function money(value) {
  return new Intl.NumberFormat('ru-RU').format(Number(value) || 0)
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
        <p>{ok ? `В среднем ${money(mean)} кут из ${money(draft.max)}` : 'Шансы должны сложиться в 100'}</p>
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
            <label>
              Шанс, %
              <input
                inputMode="numeric"
                aria-label={`Шанс ${index + 1} ${draft.name}`}
                value={row.chance}
                onChange={(event) => setBand(index, 'chance', event.target.value)}
              />
            </label>
            <label>
              Приз, кут
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

export default function CasesSection() {
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
        <p>Цена и количество — в магазине. Ниже — потолок, который игрок может выиграть. Комиссии нет: открытие отдаёт ровно выпавшее число.</p>
      </header>
      {error && <p className="case-fault">{error}</p>}
      {!board && !error && <p>Считаем кейсы…</p>}
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
      <div className="case-grid">
        {(board?.cases || []).map((card, index) => (
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
    </section>
  )
}
