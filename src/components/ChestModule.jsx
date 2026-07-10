import { useState } from 'react'
import Portal from './Portal'
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import VineFrame from './VineFrame'
import StatChip from './StatChip'
import ChestRoulette from './ChestRoulette'
import ChestCollection from './ChestCollection'
import ChestFeed from './ChestFeed'
import { useChests } from '../hooks/useChests'
import { clampCount, totalStars, buildChestBotUrl } from '../utils/chestPricing'
import { RARITY_LABEL, RARITY_ACCENT, MAX_OPEN } from '../constants/chests'
import { openTelegramBotLink } from '../lib/telegram'
import '../styles/chests.css'

const SECTIONS = [
  { id: 'chest', label: 'Сундук' },
  { id: 'collection', label: 'Коллекция' },
  { id: 'shards', label: 'Осколки' },
]

export default function ChestModule({ isActive }) {
  const { state, feed, loading, error, open, refresh } = useChests(isActive)
  const [section, setSection] = useState('chest')
  const [count, setCount] = useState(1)
  const [spinning, setSpinning] = useState(false)
  const [results, setResults] = useState(null) // full open response
  const [revealResult, setRevealResult] = useState(null) // single item for the roulette

  const keys = state?.keys ?? 0
  const shards = state?.shards ?? 0
  const price = state?.box?.priceStars ?? 25
  const total = totalStars(count, price)

  const hasEnoughKeys = keys >= count

  const handleOpen = async () => {
    if (spinning || !hasEnoughKeys) return
    try {
      const res = await open(count)
      setResults(res)
      setRevealResult(res.results[0])
      setSpinning(true) // triggers roulette; grid shown after onDone for xN
    } catch (e) {
      // ValueError surfaces as ApiError; show a lightweight alert
      window.alert(e?.message || 'Не удалось открыть сундук')
    }
  }

  const handleRouletteDone = () => {
    setSpinning(false)
    // keep results shown (x1 card or xN grid) in the overlay
  }

  const closeOverlay = () => {
    setResults(null)
    setRevealResult(null)
    setSpinning(false)
    refresh()
  }

  const buyKeys = () => openTelegramBotLink(buildChestBotUrl(count))

  return (
    <div className="relative min-h-screen tab-theme-chests chest-module" aria-hidden={!isActive}>
      <FarmBackground />
      <TabAtmosphere variant="chests" />

      <div className="relative z-10 chest-shell py-4 pb-2 animate-slide-up">
        <header className="chest-hero">
          <div className="chest-hero-identity">
            <div className="chest-hero-avatar" aria-hidden>🎁</div>
            <div className="chest-hero-copy">
              <p className="chest-hero-eyebrow">Косметика</p>
              <h1 className="chest-hero-title">Сундуки</h1>
            </div>
          </div>
          <div className="chest-hero-balances" role="list">
            <StatChip icon="🔑" label="Ключи" value={keys} />
            <StatChip icon="💎" label="Осколки" value={shards} />
          </div>
        </header>

        <div className="chest-subtabs" role="tablist" aria-label="Разделы сундуков">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={section === s.id}
              className={`chest-subtab${section === s.id ? ' chest-subtab-active' : ''}`}
              onClick={() => setSection(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>

        {section === 'chest' && (
          <VineFrame className="chest-frame">
            <div className="chest-panel">
              <div className="chest-title-center">{state?.box?.name || 'Косметический сундук'}</div>
              {!state && error ? (
                <div className="chest-collection-error">
                  <p className="chest-collection-error-text">Не удалось загрузить сундук</p>
                  <button type="button" className="chest-collection-retry-btn" onClick={refresh}>Повторить</button>
                </div>
              ) : !state && loading ? (
                <div className="chest-collection-loading">Загрузка…</div>
              ) : (
                <>
                  <ChestRoulette result={revealResult} pool={state?.preview || []} spinning={spinning} onDone={handleRouletteDone} />
                  <ChestFeed feed={feed} />
                  <div className="chest-stepper">
                    <button className="chest-step-btn" onClick={() => setCount((c) => clampCount(c - 1))} disabled={spinning}>−</button>
                    <span className="chest-step-n">{count}</span>
                    <button className="chest-step-btn" onClick={() => setCount((c) => clampCount(c + 1))} disabled={spinning || count >= MAX_OPEN}>+</button>
                  </div>
                  {hasEnoughKeys ? (
                    <button className="chest-open-btn farm-btn-primary" onClick={handleOpen} disabled={spinning}>Открыть ×{count}</button>
                  ) : (
                    <button className="chest-buy-btn farm-btn-primary" onClick={buyKeys}>Купить ×{count} · {total} ⭐</button>
                  )}
                  <div className="chest-hint">Ключей: {keys} · цена {price}⭐ за сундук</div>
                </>
              )}
            </div>
          </VineFrame>
        )}

        {(section === 'collection' || section === 'shards') && (
          <VineFrame className="chest-frame">
            <ChestCollection isActive={isActive} focusShards={section === 'shards'} onChanged={refresh} />
          </VineFrame>
        )}
      </div>

      {results && !spinning && (
        <Portal>
          <div className="chest-result-overlay" onClick={closeOverlay}>
            <div className="chest-result-card" onClick={(e) => e.stopPropagation()}>
              {results.results.length === 1 ? (
                <SingleResult item={results.results[0]} />
              ) : (
                <GridResult res={results} />
              )}
              <button className="chest-open-btn farm-btn-primary" onClick={closeOverlay}>Забрать</button>
            </div>
          </div>
        </Portal>
      )}
    </div>
  )
}

function SingleResult({ item }) {
  return (
    <div className={`chest-single rarity-${item.rarity}`}>
      <div className="chest-single-banner" style={{ color: RARITY_ACCENT[item.rarity] }}>
        {RARITY_LABEL[item.rarity]}
      </div>
      <div className="chest-single-emoji-wrap">
        <div className="chest-single-emoji">{item.emoji}</div>
      </div>
      <div className="chest-single-name">{item.name}</div>
      <div className="chest-single-sub">
        {item.wasDupe ? `Дубль → +${item.shardsGranted} 💎` : '✓ Новое — в коллекции'}
      </div>
    </div>
  )
}

function GridResult({ res }) {
  const news = res.results.filter((r) => !r.wasDupe).length
  const dupes = res.results.length - news
  const shards = res.results.reduce((s, r) => s + (r.shardsGranted || 0), 0)
  return (
    <div className="chest-grid-result">
      <div className="chest-grid-summary">Открыто ×{res.results.length} · {news} новых · {dupes} дублей</div>
      <div className="chest-grid">
        {res.results.map((r, i) => (
          <div key={i} className={`chest-grid-tile`} style={{ borderColor: RARITY_ACCENT[r.rarity] }}>
            <span className="chest-grid-emoji">{r.emoji}</span>
            <span className="chest-grid-tag">{r.wasDupe ? 'ДУБЛЬ' : 'НОВОЕ'}</span>
          </div>
        ))}
      </div>
      {shards > 0 && <div className="chest-grid-shards">💎 Дубли → +{shards} осколков</div>}
    </div>
  )
}
