import { useEffect, useState } from 'react'
import { fetchWaterBoard, saveWaterPrice } from '../../lib/adminClient'
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

export default function WaterGames({ onOpenUser = null }) {
  const [board, setBoard] = useState(null)
  const [error, setError] = useState('')
  const [drafts, setDrafts] = useState({})
  const [busy, setBusy] = useState('')
  const [ledger, setLedger] = useState('pours')

  const load = () => {
    setError('')
    return fetchWaterBoard()
      .then((data) => {
        setBoard(data)
        const next = {}
        for (const item of data.items || []) next[item.id] = String(item.price)
        setDrafts(next)
      })
      .catch((err) => setError(err.message || 'Не удалось открыть водные игры'))
  }

  useEffect(() => { load() }, [])

  const save = async (item) => {
    setBusy(item.id)
    setError('')
    try {
      const saved = await saveWaterPrice({ id: Number(item.id), price: Number(drafts[item.id] || 0) })
      setBoard((prev) => ({
        ...prev,
        items: prev.items.map((row) => (row.id === item.id ? { ...row, price: saved.price } : row)),
      }))
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
        <h3 className="sec-title">Водные игры</h3>
        <p className="sec-subtitle">Кто обливает, кого обливают, и почём защита. Вкладка только у создателя.</p>
      </header>
      {error && <p className="sec-empty">{error}</p>}
      {!board && !error && <p className="sec-empty">Собираем статистику…</p>}
      {board && (
        <>
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

          <section>
            <h4 className="sec-title">Цены в магазине</h4>
            <p className="sec-subtitle">Кнопка стоит под полем. Цена сразу становится ценой предмета в dex.</p>
            {(board.items || []).map((item) => (
              <div key={item.id} className="water-price">
                <strong>{item.emoji} {item.name}</strong>
                <span>в магазине сейчас {item.remains > 0 ? `${money(item.remains)} шт.` : 'нет остатка'}</span>
                <input
                  inputMode="numeric"
                  aria-label={`Цена: ${item.name}`}
                  value={drafts[item.id] ?? ''}
                  onChange={(event) => setDrafts((prev) => ({ ...prev, [item.id]: event.target.value.replace(/[^\d]/g, '') }))}
                />
                <button type="button" className="sec-tab" disabled={busy === item.id} onClick={() => save(item)}>
                  {busy === item.id ? 'Сохраняем…' : 'Сохранить цену'}
                </button>
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  )
}
