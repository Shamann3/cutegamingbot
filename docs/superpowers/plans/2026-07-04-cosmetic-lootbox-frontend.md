# Cosmetic Loot Boxes — Frontend Implementation Plan (Plan 2 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the player-facing chest UI (new "Сундуки" tab: CS-style roulette open, x1/xN result, collection album with set progress and shard purchase, profile showcase, live drop feed) wired to the Plan-1 backend API.

**Architecture:** A new tab `chests` mounted in `App.jsx` alongside the others, backed by a data hook (`useChests`) and a thin API client (`chestClient.js`) over the existing `apiRequest`. Pure logic (quantity→price, roulette strip + landing offset, collection grouping) lives in unit-tested utils (vitest). Buying keys reuses the existing donate-bot deep-link mechanism with a new `chest_{N}` payload. Components follow existing module conventions (functional components, `isActive` prop, `FarmBackground`/`TabAtmosphere` backdrop, `Portal`/`BottomSheet` for sheets, Tailwind + component CSS).

**Tech Stack:** React 18, Vite, Tailwind, vitest. No new dependencies.

## Global Constraints

- Backend is DONE (Plan 1, already in `master`). Endpoints, all under existing auth (`apiRequest` sends Telegram initData / dev header automatically):
  - `GET /api/chests/state` → `{keys, shards, box:{code,name,priceStars}, chances:{common,rare,legendary}}`
  - `POST /api/chests/open` body `{count:1..10}` → `{results:[{cosmeticId,code,name,emoji,rarity,slot,wasDupe,shardsGranted}],keys,shards}`
  - `GET /api/chests/collection` → `{shards, sets:[{code,name,rewardType,rewardValue,owned,total,items:[item]}], loose:[item]}` where item = `{cosmeticId,code,name,emoji,slot,rarity,owned,equipped,shardCost}`
  - `POST /api/chests/buy` body `{cosmeticId}` → `{shards,cosmeticId}`
  - `POST /api/chests/equip` body `{cosmeticId,equipped}` → `{cosmeticId,slot,equipped}`
  - `GET /api/chests/feed` → `[{name,emoji,itemName,rarity,openedAt}]` (rare/legendary only)
- Rarities are exactly `common | rare | legendary`. Rarity accent colors: common `#c9c1ad`, rare `#5b9be0`, legendary `#e6b422` (from the approved mockups).
- Chest price is **25★ per chest** (use `state.box.priceStars`, do not hardcode 25 in logic — read it). Quantity selector: player picks N (1..10), total = `priceStars × N`.
- Buying keys goes through the **donate bot** (fire-and-forget) with payload `chest_{N}` (charset `[A-Za-z0-9_-]`), NOT native Stars. Reuse `openTelegramBotLink` from `src/lib/telegram.js` (same call DonateModal uses).
- Roulette: strip scrolls **left**, decelerates, lands on the already-known result under a fixed center pointer (~3.4s). x1 = full roulette; xN = results grid after a single combined spin. Legendary result gets a stronger reveal effect.
- Feed shows rare/legendary only, with player name; lives at the top of the chest tab.
- Follow existing patterns: new tab id `chests`; module receives `isActive`; data via a hook; user-facing strings in Russian matching the app's tone.
- Match the file's existing import/style conventions. Don't restructure unrelated code.

---

### Task 1: Chest API client + pure price util (with tests)

**Files:**
- Create: `src/lib/chestClient.js`
- Create: `src/utils/chestPricing.js`
- Create: `src/utils/chestPricing.test.js`
- Create: `src/constants/chests.js`

**Interfaces:**
- Produces:
  - `src/constants/chests.js`: `RARITY_ORDER = ['common','rare','legendary']`; `RARITY_ACCENT = {common:'#c9c1ad', rare:'#5b9be0', legendary:'#e6b422'}`; `RARITY_LABEL = {common:'Обычный', rare:'Редкий', legendary:'Легендарный'}`; `MAX_OPEN = 10`; `CHEST_BOT_USERNAME` (from `import.meta.env.VITE_DONATE_BOT_USERNAME || 'CuteGamingBot'`).
  - `src/utils/chestPricing.js`: `clampCount(n) -> int in 1..MAX_OPEN`; `totalStars(count, priceStars) -> int`; `buildChestStartPayload(count) -> "chest_{clamped}"`; `buildChestBotUrl(count) -> "https://t.me/{user}?start=chest_{n}"`.
  - `src/lib/chestClient.js`: `fetchChestState()`, `openChests(count)`, `fetchCollection()`, `buyCosmetic(cosmeticId)`, `equipCosmetic(cosmeticId, equipped)`, `fetchDropFeed()` — each returns the parsed JSON from `apiRequest`.

- [ ] **Step 1: Write failing tests for pricing util**

Create `src/utils/chestPricing.test.js`:

```js
import { describe, expect, it } from 'vitest'
import { clampCount, totalStars, buildChestStartPayload, buildChestBotUrl } from './chestPricing'

describe('chestPricing', () => {
  it('clamps count to 1..10', () => {
    expect(clampCount(0)).toBe(1)
    expect(clampCount(1)).toBe(1)
    expect(clampCount(10)).toBe(10)
    expect(clampCount(11)).toBe(10)
    expect(clampCount(3.7)).toBe(3)
    expect(clampCount(NaN)).toBe(1)
  })
  it('computes total stars from price and count', () => {
    expect(totalStars(3, 25)).toBe(75)
    expect(totalStars(1, 25)).toBe(25)
    expect(totalStars(0, 25)).toBe(25) // clamped to 1
  })
  it('builds a telegram-safe start payload', () => {
    expect(buildChestStartPayload(3)).toBe('chest_3')
    expect(buildChestStartPayload(99)).toBe('chest_10')
    expect(/^[A-Za-z0-9_-]+$/.test(buildChestStartPayload(5))).toBe(true)
  })
  it('builds a bot url with the payload', () => {
    expect(buildChestBotUrl(2)).toContain('?start=chest_2')
    expect(buildChestBotUrl(2)).toContain('t.me/')
  })
})
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `npm test -- src/utils/chestPricing.test.js`
Expected: FAIL — cannot resolve `./chestPricing`.

- [ ] **Step 3: Implement constants + pricing util**

Create `src/constants/chests.js`:

```js
export const RARITY_ORDER = ['common', 'rare', 'legendary']
export const RARITY_ACCENT = { common: '#c9c1ad', rare: '#5b9be0', legendary: '#e6b422' }
export const RARITY_LABEL = { common: 'Обычный', rare: 'Редкий', legendary: 'Легендарный' }
export const MAX_OPEN = 10
export const CHEST_BOT_USERNAME = import.meta.env.VITE_DONATE_BOT_USERNAME || 'CuteGamingBot'
```

Create `src/utils/chestPricing.js`:

```js
import { MAX_OPEN, CHEST_BOT_USERNAME } from '../constants/chests'

export function clampCount(n) {
  const v = Math.floor(Number(n))
  if (!Number.isFinite(v)) return 1
  return Math.max(1, Math.min(v, MAX_OPEN))
}

export function totalStars(count, priceStars) {
  return clampCount(count) * Math.max(0, Math.floor(Number(priceStars) || 0))
}

export function buildChestStartPayload(count) {
  return `chest_${clampCount(count)}`
}

export function buildChestBotUrl(count) {
  const user = String(CHEST_BOT_USERNAME).replace(/^@/, '')
  return `https://t.me/${user}?start=${buildChestStartPayload(count)}`
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `npm test -- src/utils/chestPricing.test.js`
Expected: PASS (4 tests).

- [ ] **Step 5: Implement the API client**

Create `src/lib/chestClient.js`:

```js
import { apiRequest } from './apiClient'

export function fetchChestState() {
  return apiRequest('/api/chests/state')
}

export function openChests(count) {
  return apiRequest('/api/chests/open', { method: 'POST', body: { count } })
}

export function fetchCollection() {
  return apiRequest('/api/chests/collection')
}

export function buyCosmetic(cosmeticId) {
  return apiRequest('/api/chests/buy', { method: 'POST', body: { cosmeticId } })
}

export function equipCosmetic(cosmeticId, equipped) {
  return apiRequest('/api/chests/equip', { method: 'POST', body: { cosmeticId, equipped } })
}

export function fetchDropFeed() {
  return apiRequest('/api/chests/feed')
}
```

- [ ] **Step 6: Commit**

```bash
git add src/lib/chestClient.js src/utils/chestPricing.js src/utils/chestPricing.test.js src/constants/chests.js
git commit -m "feat(chests-ui): api client, pricing util, constants"
```

---

### Task 2: Roulette strip builder (pure, with tests)

The animation-critical math: given the result and a pool of items, build a long strip and compute the pixel offset that lands the result cell under the center pointer.

**Files:**
- Create: `src/utils/rouletteStrip.js`
- Create: `src/utils/rouletteStrip.test.js`

**Interfaces:**
- Consumes: `RARITY_ORDER` from constants (only for typing; not required).
- Produces:
  - `buildStrip(result, pool, opts) -> { cells: Array<{key,emoji,rarity}>, resultIndex: number }` — returns a strip of `opts.length` (default 40) filler cells drawn cyclically from `pool`, with `result` placed at `resultIndex` (default near the end, e.g. `length - 5`). Each cell has a unique `key`.
  - `landingOffset(resultIndex, cellWidth, gap, viewportWidth) -> number` — the negative translateX (px) that centers `resultIndex`'s cell under the viewport center. Formula: `-(resultIndex * (cellWidth + gap) + cellWidth / 2 - viewportWidth / 2)`.

- [ ] **Step 1: Write failing tests**

Create `src/utils/rouletteStrip.test.js`:

```js
import { describe, expect, it } from 'vitest'
import { buildStrip, landingOffset } from './rouletteStrip'

const pool = [
  { emoji: '🌾', rarity: 'common' },
  { emoji: '🖼️', rarity: 'rare' },
  { emoji: '🐉', rarity: 'legendary' },
]
const result = { emoji: '👑', rarity: 'legendary' }

describe('rouletteStrip', () => {
  it('places the result at resultIndex and fills the rest from the pool', () => {
    const { cells, resultIndex } = buildStrip(result, pool, { length: 20, resultIndex: 15 })
    expect(cells).toHaveLength(20)
    expect(resultIndex).toBe(15)
    expect(cells[15].emoji).toBe('👑')
    expect(cells[15].rarity).toBe('legendary')
    // non-result cells come from the pool
    expect(pool.map((p) => p.emoji)).toContain(cells[0].emoji)
  })
  it('gives every cell a unique key', () => {
    const { cells } = buildStrip(result, pool, { length: 30 })
    const keys = new Set(cells.map((c) => c.key))
    expect(keys.size).toBe(30)
  })
  it('defaults resultIndex near the end when not given', () => {
    const { resultIndex, cells } = buildStrip(result, pool, { length: 40 })
    expect(resultIndex).toBe(35)
    expect(cells[35].emoji).toBe('👑')
  })
  it('computes a landing offset that centers the result cell', () => {
    // cell 15, width 78, gap 10, viewport 300
    // -(15*88 + 39 - 150) = -(1320 + 39 - 150) = -1209
    expect(landingOffset(15, 78, 10, 300)).toBe(-1209)
  })
  it('handles empty pool by filling with the result', () => {
    const { cells } = buildStrip(result, [], { length: 5, resultIndex: 3 })
    expect(cells).toHaveLength(5)
    expect(cells[3].emoji).toBe('👑')
  })
})
```

- [ ] **Step 2: Run tests, verify fail**

Run: `npm test -- src/utils/rouletteStrip.test.js`
Expected: FAIL — cannot resolve `./rouletteStrip`.

- [ ] **Step 3: Implement**

Create `src/utils/rouletteStrip.js`:

```js
export function buildStrip(result, pool, opts = {}) {
  const length = opts.length ?? 40
  const resultIndex = opts.resultIndex ?? Math.max(0, length - 5)
  const fillers = (pool && pool.length) ? pool : [result]
  const cells = []
  for (let i = 0; i < length; i += 1) {
    if (i === resultIndex) {
      cells.push({ key: `r-${i}`, emoji: result.emoji, rarity: result.rarity })
    } else {
      const src = fillers[i % fillers.length]
      cells.push({ key: `c-${i}`, emoji: src.emoji, rarity: src.rarity })
    }
  }
  return { cells, resultIndex }
}

export function landingOffset(resultIndex, cellWidth, gap, viewportWidth) {
  return -(resultIndex * (cellWidth + gap) + cellWidth / 2 - viewportWidth / 2)
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `npm test -- src/utils/rouletteStrip.test.js`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/utils/rouletteStrip.js src/utils/rouletteStrip.test.js
git commit -m "feat(chests-ui): pure roulette strip + landing offset"
```

---

### Task 3: Chest data hook (`useChests`)

**Files:**
- Create: `src/hooks/useChests.js`

**Interfaces:**
- Consumes: `chestClient.js` functions.
- Produces: `useChests(isActive)` returning `{ state, loading, error, refresh, open, feed, refreshFeed }` where:
  - `state` = last `fetchChestState` payload (or null); loads on first activation.
  - `open(count)` calls `openChests`, updates `state.keys`/`state.shards` from the response, returns the full response (results) for the UI to animate.
  - `feed` = last `fetchDropFeed` array; `refreshFeed()` reloads it.
  - `refresh()` reloads state.

- [ ] **Step 1: Implement the hook**

Create `src/hooks/useChests.js`:

```js
import { useCallback, useEffect, useState } from 'react'
import { fetchChestState, openChests, fetchDropFeed } from '../lib/chestClient'

export function useChests(isActive) {
  const [state, setState] = useState(null)
  const [feed, setFeed] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [loadedOnce, setLoadedOnce] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchChestState()
      setState(data)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
      setLoadedOnce(true)
    }
  }, [])

  const refreshFeed = useCallback(async () => {
    try { setFeed(await fetchDropFeed()) } catch { /* feed is best-effort */ }
  }, [])

  useEffect(() => {
    if (isActive && !loadedOnce) {
      refresh()
      refreshFeed()
    }
  }, [isActive, loadedOnce, refresh, refreshFeed])

  const open = useCallback(async (count) => {
    const res = await openChests(count)
    setState((prev) => (prev ? { ...prev, keys: res.keys, shards: res.shards } : prev))
    return res
  }, [])

  return { state, feed, loading, error, refresh, refreshFeed, open }
}
```

- [ ] **Step 2: Verify it builds (lint/import)**

Run: `npm run build` (or `npx vite build`) and confirm no import/parse error for the new module. (No unit test — this is glue over the tested client; behavior is exercised by the module in later tasks.)
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add src/hooks/useChests.js
git commit -m "feat(chests-ui): useChests data hook"
```

---

### Task 4: Register the "Сундуки" tab

**Files:**
- Modify: `src/components/TabBar.jsx` (add tab entry)
- Modify: `src/components/TabIcons.jsx` (add icon + accent for `chests`)
- Modify: `src/App.jsx` (import + mount `ChestModule`)
- Create: `src/components/ChestModule.jsx` (minimal placeholder shell for this task; filled in Task 5)

**Interfaces:**
- Produces: a visible `chests` tab that mounts `ChestModule` when active. `ChestModule` accepts `{ isActive }`.

- [ ] **Step 1: Add the tab to TabBar**

In `src/components/TabBar.jsx`, add to the `TABS` array (place after `market`, before `profile`):

```js
  { id: 'chests', label: 'Сундуки' },
```

- [ ] **Step 2: Add icon + accent**

Open `src/components/TabIcons.jsx`, find `TAB_ICONS` and `TAB_ACCENTS`. Add an entry for `chests` matching the existing style. Use an emoji-glyph or the same SVG-component convention the file uses (inspect an existing icon like `market` and mirror it). If icons are inline SVG components, add a `ChestsIcon` component rendering a simple chest/gift glyph and register it: `chests: ChestsIcon`. Add accent `chests: { strong: '#e6b422', glow: 'rgba(230,180,34,0.5)' }`. Follow whatever shape the other entries use exactly.

- [ ] **Step 3: Create the placeholder module**

Create `src/components/ChestModule.jsx`:

```jsx
export default function ChestModule({ isActive }) {
  return (
    <div className="chest-module" aria-hidden={!isActive}>
      <p style={{ padding: 16 }}>Сундуки скоро…</p>
    </div>
  )
}
```

- [ ] **Step 4: Mount it in App.jsx**

In `src/App.jsx`, add the import with the other module imports:

```js
import ChestModule from './components/ChestModule'
```

And add its panel inside `<main className="app-main">` (place after the `market` panel, before `profile`):

```jsx
        <div className={tab === 'chests' ? '' : 'hidden'} aria-hidden={tab !== 'chests'}>
          <ChestModule isActive={tab === 'chests'} />
        </div>
```

- [ ] **Step 5: Verify the tab renders**

Run `npm run dev`, open the app, confirm a "Сундуки" tab appears in the bottom bar and shows the placeholder when selected. (If the tab bar is crowded at 9 tabs, note it as a concern — a later polish can compact the bar — but do not restructure the bar in this task.)

- [ ] **Step 6: Commit**

```bash
git add src/components/TabBar.jsx src/components/TabIcons.jsx src/App.jsx src/components/ChestModule.jsx
git commit -m "feat(chests-ui): register Сундуки tab + placeholder module"
```

---

### Task 5: ChestRoulette component (CS-style animation)

**Files:**
- Create: `src/components/ChestRoulette.jsx`
- Create: `src/styles/chests.css` (roulette + shared chest styles; import it from ChestModule in Task 6)

**Interfaces:**
- Consumes: `buildStrip`, `landingOffset` (Task 2); `RARITY_ACCENT` (Task 1).
- Produces: `<ChestRoulette result={item} pool={items} spinning={bool} onDone={fn} />` — renders the horizontal strip with a fixed center pointer; when `spinning` goes true it animates the strip left to land on `result`, calling `onDone()` when the transition ends. Idle state shows a gently drifting strip.

- [ ] **Step 1: Implement the roulette**

Create `src/components/ChestRoulette.jsx`:

```jsx
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { buildStrip, landingOffset } from '../utils/rouletteStrip'
import { RARITY_ACCENT } from '../constants/chests'

const CELL = 78
const GAP = 10

export default function ChestRoulette({ result, pool, spinning, onDone }) {
  const viewportRef = useRef(null)
  const [offset, setOffset] = useState(0)
  const [animating, setAnimating] = useState(false)
  const strip = result ? buildStrip(result, pool || [], { length: 40, resultIndex: 35 }) : null

  useLayoutEffect(() => {
    if (!spinning || !result || !viewportRef.current) return
    const vw = viewportRef.current.clientWidth
    // start from 0, then next frame animate to the landing offset
    setOffset(0)
    setAnimating(false)
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setAnimating(true)
        setOffset(landingOffset(35, CELL, GAP, vw))
      })
    })
    return () => cancelAnimationFrame(id)
  }, [spinning, result])

  const handleTransitionEnd = () => {
    if (animating) {
      setAnimating(false)
      onDone?.()
    }
  }

  if (!strip) {
    return <div className="chest-roulette chest-roulette-empty" ref={viewportRef} />
  }

  return (
    <div className="chest-roulette" ref={viewportRef}>
      <div className="chest-roulette-pointer" />
      <div
        className={`chest-roulette-strip${!spinning ? ' chest-roulette-idle' : ''}`}
        style={animating
          ? { transform: `translateX(${offset}px)`, transition: 'transform 3.4s cubic-bezier(.12,.72,.16,1)' }
          : { transform: `translateX(${offset}px)` }}
        onTransitionEnd={handleTransitionEnd}
      >
        {strip.cells.map((c) => (
          <div key={c.key} className="chest-cell" style={{ borderColor: RARITY_ACCENT[c.rarity] }}>
            <span>{c.emoji}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add the CSS**

Create `src/styles/chests.css`:

```css
.chest-roulette { position: relative; height: 118px; overflow: hidden;
  background: linear-gradient(180deg,#efe2c4,#e6d5ad); border-block: 1px solid #d8c391; border-radius: 12px; }
.chest-roulette::before,.chest-roulette::after { content:""; position:absolute; top:0; bottom:0; width:46px; z-index:3; pointer-events:none; }
.chest-roulette::before { left:0; background:linear-gradient(90deg,#e9dab8,rgba(233,218,184,0)); }
.chest-roulette::after { right:0; background:linear-gradient(270deg,#e9dab8,rgba(233,218,184,0)); }
.chest-roulette-pointer { position:absolute; left:50%; top:0; bottom:0; width:0; transform:translateX(-50%); z-index:4;
  border-left:3px solid #e0692e; box-shadow:0 0 14px 3px rgba(224,105,46,.5); }
.chest-roulette-strip { display:flex; gap:10px; padding:20px 0; position:absolute; top:0; left:0; height:100%; align-items:center; box-sizing:border-box; will-change:transform; }
.chest-roulette-idle { animation: chest-drift 14s linear infinite; }
@keyframes chest-drift { from{transform:translateX(0)} to{transform:translateX(-528px)} }
.chest-cell { width:78px; height:78px; flex:0 0 78px; border-radius:14px; display:flex; align-items:center; justify-content:center;
  font-size:42px; background:#fff; border:3px solid #ccc; }
```

- [ ] **Step 3: Verify visually**

Temporarily render `<ChestRoulette result={{emoji:'🐉',rarity:'legendary'}} pool={[{emoji:'🌾',rarity:'common'},{emoji:'🖼️',rarity:'rare'}]} spinning onDone={()=>console.log('done')} />` in the placeholder ChestModule, `npm run dev`, and confirm the strip scrolls left and lands with the dragon cell under the orange pointer, then logs 'done'. Remove the temporary render after confirming.

- [ ] **Step 4: Commit**

```bash
git add src/components/ChestRoulette.jsx src/styles/chests.css
git commit -m "feat(chests-ui): CS-style roulette component"
```

---

### Task 6: ChestModule — open flow, quantity selector, buy keys, result screen

Replace the placeholder with the real "Сундук" section: feed at top, roulette center, quantity stepper + price, Open button (spends keys via `open`), buy-keys button (donate bot), and the result reveal (x1 roulette → card; xN grid).

**Files:**
- Modify: `src/components/ChestModule.jsx` (full implementation)
- Modify: `src/styles/chests.css` (append result/controls styles)

**Interfaces:**
- Consumes: `useChests` (Task 3), `ChestRoulette` (Task 5), `chestPricing` (Task 1), `openTelegramBotLink` from `src/lib/telegram.js`, `RARITY_LABEL`/`RARITY_ACCENT`, `FarmBackground`/`TabAtmosphere` for backdrop (match how QuestsModule wraps its content), `Portal` for the result overlay.
- Produces: a working single-chest and xN open experience. Sub-section tabs (Сундук/Коллекция/Осколки) are added here with Коллекция/Осколки delegating to `ChestCollection` (Task 7) — for THIS task, render the "Сундук" section fully and leave the other two sub-tabs mounting `ChestCollection` (import it; Task 7 creates it — until then a stub is acceptable but the import path must be correct).

- [ ] **Step 1: Implement ChestModule**

Replace `src/components/ChestModule.jsx` with:

```jsx
import { useState } from 'react'
import Portal from './Portal'
import ChestRoulette from './ChestRoulette'
import ChestCollection from './ChestCollection'
import ChestFeed from './ChestFeed'
import { useChests } from '../hooks/useChests'
import { clampCount, totalStars, buildChestBotUrl } from '../utils/chestPricing'
import { RARITY_LABEL, RARITY_ACCENT, MAX_OPEN } from '../constants/chests'
import { openTelegramBotLink } from '../lib/telegram'
import '../styles/chests.css'

export default function ChestModule({ isActive }) {
  const { state, feed, loading, open, refresh } = useChests(isActive)
  const [section, setSection] = useState('chest')
  const [count, setCount] = useState(1)
  const [spinning, setSpinning] = useState(false)
  const [results, setResults] = useState(null) // full open response
  const [revealResult, setRevealResult] = useState(null) // single item for the roulette

  const keys = state?.keys ?? 0
  const shards = state?.shards ?? 0
  const price = state?.box?.priceStars ?? 25
  const total = totalStars(count, price)

  const canOpen = keys >= count && !spinning
  const pool = null // pool for filler cells; optional — roulette falls back to result

  const handleOpen = async () => {
    if (!canOpen) return
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
    <div className="chest-module" aria-hidden={!isActive}>
      <header className="chest-head">
        <span className="chest-title">🎁 Сундуки</span>
        <span className="chest-balances">
          <span className="chest-pill">🔑 {keys}</span>
          <span className="chest-pill">💎 {shards}</span>
        </span>
      </header>

      <div className="chest-subtabs">
        {['chest', 'collection', 'shards'].map((s) => (
          <button key={s} className={`chest-subtab${section === s ? ' on' : ''}`} onClick={() => setSection(s)}>
            {s === 'chest' ? 'Сундук' : s === 'collection' ? 'Коллекция' : 'Осколки'}
          </button>
        ))}
      </div>

      {section === 'chest' && (
        <div className="chest-open-section">
          <ChestFeed feed={feed} />
          <div className="chest-title-center">{state?.box?.name || 'Косметический сундук'}</div>
          <ChestRoulette result={revealResult} pool={pool} spinning={spinning} onDone={handleRouletteDone} />
          <div className="chest-stepper">
            <button className="chest-step-btn" onClick={() => setCount((c) => clampCount(c - 1))} disabled={spinning}>−</button>
            <span className="chest-step-n">{count}</span>
            <button className="chest-step-btn" onClick={() => setCount((c) => clampCount(c + 1))} disabled={spinning || count >= MAX_OPEN}>+</button>
          </div>
          {canOpen ? (
            <button className="chest-open-btn" onClick={handleOpen} disabled={!canOpen}>Открыть ×{count}</button>
          ) : (
            <button className="chest-buy-btn" onClick={buyKeys}>Купить ×{count} · {total} ⭐</button>
          )}
          <div className="chest-hint">Ключей: {keys} · цена {price}⭐ за сундук</div>
        </div>
      )}

      {(section === 'collection' || section === 'shards') && (
        <ChestCollection isActive={isActive} focusShards={section === 'shards'} onChanged={refresh} />
      )}

      {results && !spinning && (
        <Portal>
          <div className="chest-result-overlay" onClick={closeOverlay}>
            <div className="chest-result-card" onClick={(e) => e.stopPropagation()}>
              {results.results.length === 1 ? (
                <SingleResult item={results.results[0]} />
              ) : (
                <GridResult res={results} />
              )}
              <button className="chest-open-btn" onClick={closeOverlay}>Забрать</button>
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
      <div className="chest-single-emoji">{item.emoji}</div>
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
```

- [ ] **Step 2: Append result/control styles to chests.css**

Append to `src/styles/chests.css`:

```css
.chest-module { min-height: 100%; }
.chest-head { display:flex; justify-content:space-between; align-items:center; padding:12px 14px 6px; font-weight:700; }
.chest-pill { background:#fff3d4; border:1px solid #f0d98f; border-radius:20px; padding:3px 10px; font-size:12px; color:#a9791b; font-weight:700; margin-left:6px; }
.chest-subtabs { display:flex; gap:6px; padding:6px 12px; }
.chest-subtab { flex:1; padding:7px; border-radius:12px; background:#efe6d2; color:#8a7752; font-weight:700; font-size:12px; border:none; }
.chest-subtab.on { background:#ffcf5c; color:#5b3d0c; }
.chest-title-center { text-align:center; font-weight:800; margin:6px 0 8px; }
.chest-stepper { display:flex; align-items:center; justify-content:center; gap:14px; margin:12px 0 6px; }
.chest-step-btn { width:34px; height:34px; border-radius:50%; background:#fff; border:1px solid #e6d7b6; font-size:20px; font-weight:700; color:#a9791b; }
.chest-step-n { font-size:26px; font-weight:800; min-width:34px; text-align:center; }
.chest-open-btn { display:block; width:calc(100% - 28px); margin:6px 14px; padding:13px; border:none; border-radius:16px; font-weight:800; font-size:15px; color:#5b3d0c; background:linear-gradient(180deg,#ffcf5c,#f2a93c); }
.chest-buy-btn { display:block; width:calc(100% - 28px); margin:6px 14px; padding:13px; border:none; border-radius:16px; font-weight:800; font-size:15px; color:#5b3d0c; background:linear-gradient(180deg,#ffe08a,#f2c24a); }
.chest-hint { text-align:center; font-size:12px; color:#a9791b; font-weight:700; }
.chest-result-overlay { position:fixed; inset:0; background:rgba(60,45,25,.55); display:flex; align-items:center; justify-content:center; z-index:1000; padding:20px; }
.chest-result-card { background:linear-gradient(180deg,#fdf6e9,#f6ead2); border-radius:22px; padding:18px; max-width:340px; width:100%; text-align:center; }
.chest-single-banner { font-size:13px; font-weight:900; letter-spacing:2px; }
.chest-single-emoji { font-size:110px; filter:drop-shadow(0 8px 18px rgba(230,180,34,.6)); animation:chest-pop .5s cubic-bezier(.2,1.4,.4,1); }
@keyframes chest-pop { from{transform:scale(.3);opacity:0} to{transform:scale(1);opacity:1} }
.chest-single.rarity-legendary .chest-single-emoji { filter:drop-shadow(0 8px 24px rgba(230,180,34,.9)); }
.chest-single-name { font-size:19px; font-weight:800; margin-top:4px; }
.chest-single-sub { font-size:12px; font-weight:700; color:#3a8f4a; margin-top:2px; }
.chest-grid-summary { font-weight:800; margin-bottom:8px; }
.chest-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
.chest-grid-tile { aspect-ratio:1; border-radius:14px; background:#fff; border:3px solid #ccc; display:flex; flex-direction:column; align-items:center; justify-content:center; font-size:36px; position:relative; }
.chest-grid-tag { font-size:8px; font-weight:800; position:absolute; bottom:4px; }
.chest-grid-shards { margin-top:10px; font-weight:700; color:#a9791b; }
```

- [ ] **Step 3: Verify the open flow**

`npm run dev`. On the Сундуки tab: if you have keys (grant via backend for your dev user, or use the buy button which opens the bot), set count and press Открыть — confirm the roulette spins, lands, and the result card/grid shows with correct new/dupe labels and updated key/shard counts after "Забрать". With 0 keys, confirm the button switches to "Купить ×N · {total}⭐" and opens the donate bot.

- [ ] **Step 4: Commit**

```bash
git add src/components/ChestModule.jsx src/styles/chests.css
git commit -m "feat(chests-ui): open flow, quantity, buy-keys, result reveal"
```

---

### Task 7: ChestCollection — album, set progress, shard purchase, equip

**Files:**
- Create: `src/components/ChestCollection.jsx`
- Modify: `src/styles/chests.css` (append collection styles)

**Interfaces:**
- Consumes: `fetchCollection`, `buyCosmetic`, `equipCosmetic` (Task 1 client); `RARITY_ACCENT`; `BottomSheet` for the buy/equip sheet (match how other modules use `BottomSheet`/`Portal`).
- Produces: `<ChestCollection isActive focusShards onChanged />` — loads collection on activation; renders sets (name, `owned/total` progress bar, reward chip) then `loose`; owned items are highlighted (rarity border) with an "Надеть/Снять" action; locked items show a shard price and open a purchase sheet; `onChanged()` is called after a successful buy/equip so the parent can refresh state (shard balance).

- [ ] **Step 1: Implement ChestCollection**

Create `src/components/ChestCollection.jsx`:

```jsx
import { useCallback, useEffect, useState } from 'react'
import { fetchCollection, buyCosmetic, equipCosmetic } from '../lib/chestClient'
import { RARITY_ACCENT } from '../constants/chests'

export default function ChestCollection({ isActive, onChanged }) {
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState(null)

  const load = useCallback(async () => {
    try { setData(await fetchCollection()) } catch { /* keep prior */ }
  }, [])

  useEffect(() => { if (isActive) load() }, [isActive, load])

  const doBuy = async (item) => {
    setBusy(true)
    try {
      await buyCosmetic(item.cosmeticId)
      setSelected(null)
      await load()
      onChanged?.()
    } catch (e) {
      window.alert(e?.message || 'Не удалось купить')
    } finally { setBusy(false) }
  }

  const doEquip = async (item, equipped) => {
    setBusy(true)
    try {
      await equipCosmetic(item.cosmeticId, equipped)
      await load()
    } catch (e) {
      window.alert(e?.message || 'Не удалось')
    } finally { setBusy(false) }
  }

  if (!data) return <div className="chest-collection-loading">Загрузка…</div>

  const renderItem = (item) => (
    <button
      key={item.cosmeticId}
      className={`chest-col-item${item.owned ? ' owned' : ' locked'}`}
      style={item.owned ? { borderColor: RARITY_ACCENT[item.rarity] } : undefined}
      onClick={() => (item.owned ? doEquip(item, !item.equipped) : setSelected(item))}
      disabled={busy}
    >
      <span className={`chest-col-emoji${item.owned ? '' : ' dim'}`}>{item.emoji}</span>
      {item.owned
        ? (item.equipped ? <span className="chest-col-badge">надето</span> : null)
        : <span className="chest-col-price">💎 {item.shardCost}</span>}
    </button>
  )

  return (
    <div className="chest-collection">
      <div className="chest-col-shards">💎 {data.shards} осколков</div>
      {data.sets.map((set) => (
        <section key={set.code} className="chest-col-set">
          <div className="chest-col-set-head">
            <span className="chest-col-set-name">{set.name}</span>
            <span className="chest-col-set-reward">🎁 {set.rewardValue}</span>
          </div>
          <div className="chest-col-bar"><i style={{ width: `${set.total ? (100 * set.owned / set.total) : 0}%` }} /></div>
          <div className="chest-col-prog">{set.owned} / {set.total} собрано</div>
          <div className="chest-col-grid">{set.items.map(renderItem)}</div>
        </section>
      ))}
      {data.loose.length > 0 && (
        <section className="chest-col-set">
          <div className="chest-col-set-name">Прочее</div>
          <div className="chest-col-grid">{data.loose.map(renderItem)}</div>
        </section>
      )}

      {selected && (
        <div className="chest-buy-sheet-overlay" onClick={() => setSelected(null)}>
          <div className="chest-buy-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="chest-buy-emoji">{selected.emoji}</div>
            <div className="chest-buy-name">{selected.name}</div>
            <div className="chest-buy-have">Стоит 💎 {selected.shardCost} · у тебя 💎 {data.shards}</div>
            <button className="chest-open-btn" disabled={busy || data.shards < selected.shardCost} onClick={() => doBuy(selected)}>
              {data.shards < selected.shardCost ? 'Не хватает осколков' : `Купить за ${selected.shardCost} осколков`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Append collection styles to chests.css**

Append to `src/styles/chests.css`:

```css
.chest-collection { padding: 4px 14px 24px; }
.chest-col-shards { text-align:right; font-weight:700; color:#a9791b; font-size:12px; margin:4px 0; }
.chest-col-set { margin-bottom:14px; }
.chest-col-set-head { display:flex; justify-content:space-between; align-items:center; }
.chest-col-set-name { font-weight:800; font-size:14px; }
.chest-col-set-reward { font-size:10px; font-weight:800; color:#b8860b; background:#fbeecb; padding:2px 8px; border-radius:20px; }
.chest-col-bar { height:7px; background:#e6dcc4; border-radius:20px; margin:7px 0 2px; overflow:hidden; }
.chest-col-bar > i { display:block; height:100%; background:linear-gradient(90deg,#ffcf5c,#f2a93c); border-radius:20px; }
.chest-col-prog { font-size:10px; color:#8a7752; font-weight:700; }
.chest-col-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-top:8px; }
.chest-col-item { aspect-ratio:1; border-radius:12px; border:2px solid transparent; background:#fff; position:relative; display:flex; align-items:center; justify-content:center; font-size:26px; }
.chest-col-item.locked { background:#e9e0cd; }
.chest-col-emoji.dim { filter:grayscale(1) brightness(.75); opacity:.5; }
.chest-col-badge { position:absolute; top:-4px; right:-4px; font-size:8px; font-weight:800; background:#3a8f4a; color:#fff; border-radius:8px; padding:1px 4px; }
.chest-col-price { position:absolute; bottom:2px; font-size:8px; font-weight:800; color:#a9791b; background:#fff3d4; border-radius:8px; padding:0 4px; }
.chest-buy-sheet-overlay { position:fixed; inset:0; background:rgba(60,45,25,.45); display:flex; align-items:flex-end; z-index:1000; }
.chest-buy-sheet { background:#fff; border-radius:22px 22px 0 0; padding:18px; width:100%; text-align:center; }
.chest-buy-emoji { font-size:70px; }
.chest-buy-name { font-weight:800; font-size:17px; margin:4px 0; }
.chest-buy-have { font-size:12px; color:#8a7752; font-weight:700; margin-bottom:8px; }
```

- [ ] **Step 3: Verify collection/buy/equip**

`npm run dev` → Сундуки → Коллекция. Confirm sets render with progress bars, owned items highlighted, locked items show shard price. Tap a locked item with enough shards → buy sheet → buy → it becomes owned and shard balance drops. Tap an owned item → toggles надето. Confirm the "Осколки" sub-tab also renders the collection (focus is cosmetic).

- [ ] **Step 4: Commit**

```bash
git add src/components/ChestCollection.jsx src/styles/chests.css
git commit -m "feat(chests-ui): collection album, set progress, shard purchase, equip"
```

---

### Task 8: ChestFeed component + profile showcase

**Files:**
- Create: `src/components/ChestFeed.jsx`
- Modify: `src/styles/chests.css` (append feed styles)
- Modify: `src/components/ProfileModule.jsx` (add equipped-cosmetics showcase row)

**Interfaces:**
- Consumes: `fetchCollection` (for the profile showcase — reuse the same endpoint to read equipped items) OR a passed-in list; `RARITY_ACCENT`.
- Produces:
  - `<ChestFeed feed={array} />` — renders the "🔥 Только что выбили" list of rare/legendary drops (name, emoji, rarity tag). Renders nothing if the array is empty.
  - Profile showcase: in `ProfileModule`, a row showing the player's equipped cosmetics (up to 3 filled slots from `fetchCollection().sets/loose` where `equipped === true`), matching the existing profile styling.

- [ ] **Step 1: Implement ChestFeed**

Create `src/components/ChestFeed.jsx`:

```jsx
import { RARITY_ACCENT, RARITY_LABEL } from '../constants/chests'

export default function ChestFeed({ feed }) {
  if (!feed || feed.length === 0) return null
  return (
    <div className="chest-feed">
      <div className="chest-feed-head">🔥 Только что выбили</div>
      {feed.slice(0, 6).map((row, i) => (
        <div key={i} className="chest-feed-row" style={{ borderLeftColor: RARITY_ACCENT[row.rarity] }}>
          <span className="chest-feed-emoji">{row.emoji}</span>
          <span className="chest-feed-text"><b>{row.name}</b> выбил <b>{row.itemName}</b></span>
          <span className="chest-feed-tag" style={{ color: RARITY_ACCENT[row.rarity] }}>{RARITY_LABEL[row.rarity]}</span>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Append feed styles**

Append to `src/styles/chests.css`:

```css
.chest-feed { padding: 4px 12px 8px; }
.chest-feed-head { font-weight:800; font-size:14px; padding:4px 2px; }
.chest-feed-row { display:flex; align-items:center; gap:10px; background:#fff; border-radius:14px; padding:9px 11px; margin-bottom:8px; border-left:4px solid #ccc; }
.chest-feed-emoji { font-size:26px; }
.chest-feed-text { flex:1; font-size:12px; line-height:1.35; }
.chest-feed-tag { font-size:9px; font-weight:800; }
```

- [ ] **Step 3: Add the profile showcase**

Read `src/components/ProfileModule.jsx` to find where the player's identity block renders. Add a "Витрина" row that fetches the collection once when the profile is active and shows equipped items (up to 3). Add near the top of the component body:

```jsx
import { useEffect, useState } from 'react'
import { fetchCollection } from '../lib/chestClient'
import { RARITY_ACCENT } from '../constants/chests'
// ... inside the component:
const [showcase, setShowcase] = useState([])
useEffect(() => {
  if (!isActive) return
  fetchCollection()
    .then((c) => {
      const equipped = [...c.sets.flatMap((s) => s.items), ...c.loose].filter((i) => i.equipped)
      setShowcase(equipped.slice(0, 3))
    })
    .catch(() => {})
}, [isActive])
```

And render this block where profile stats/decorations go (match surrounding markup/classes):

```jsx
{showcase.length > 0 && (
  <div className="profile-showcase">
    <div className="profile-showcase-label">Витрина</div>
    <div className="profile-showcase-row">
      {showcase.map((i) => (
        <div key={i.cosmeticId} className="profile-showcase-slot" style={{ borderColor: RARITY_ACCENT[i.rarity] }}>
          <span>{i.emoji}</span>
        </div>
      ))}
    </div>
  </div>
)}
```

Add matching styles to `src/styles/chests.css` (import the stylesheet in ProfileModule if not already global — check whether `chests.css` is already loaded app-wide; if not, `import '../styles/chests.css'` at the top of ProfileModule):

```css
.profile-showcase { padding: 8px 16px; }
.profile-showcase-label { font-size:10px; text-transform:uppercase; letter-spacing:1px; color:#a08a5f; font-weight:800; margin-bottom:4px; }
.profile-showcase-row { display:flex; gap:10px; }
.profile-showcase-slot { width:60px; height:60px; border-radius:14px; background:#fff; border:3px solid #ccc; display:flex; align-items:center; justify-content:center; font-size:30px; }
```

> Note: `ProfileModule` may take `isActive`; confirm from its signature (App.jsx passes `isActive={tab === 'profile'}`). If the prop name differs, adapt.

- [ ] **Step 4: Verify feed + showcase**

`npm run dev`. Confirm the feed shows at the top of the Сундуки tab when rare/legendary drops exist (open a few, or rely on other players' drops). On the Профиль tab, equip a cosmetic in Коллекция, then open Профиль and confirm the equipped item appears in the Витрина row.

- [ ] **Step 5: Commit**

```bash
git add src/components/ChestFeed.jsx src/components/ProfileModule.jsx src/styles/chests.css
git commit -m "feat(chests-ui): drop feed + profile showcase"
```

---

### Task 9: Visual consistency pass — match the app's design system

Added from user feedback: the chest UI must visually fit the rest of the tabs, not look like a bolted-on module with mockup colors. Re-skin the chest components to the app's real design system.

**Files:**
- Modify: `src/components/ChestModule.jsx` (wrap content in the app's backdrop like sibling modules)
- Modify: `src/styles/chests.css` (align palette, typography, radii, buttons, cards to the app)
- Possibly Modify: `src/components/ChestRoulette.jsx`, `src/components/ChestCollection.jsx`, `src/components/ChestFeed.jsx` (only style/class changes)

**Interfaces:** No behavior/prop changes. Pure visual alignment.

- [ ] **Step 1: Study the existing design system**

Read, to extract the real tokens/patterns (do NOT guess from the mockups):
- `src/index.css` (and any `src/styles/*.css`) — the app's color variables, font, surface/card styles, button styles.
- A representative module and its wrapper: `src/components/QuestsModule.jsx` + `src/components/FarmModule.jsx` — note how they wrap content in `FarmBackground` + `TabAtmosphere` (+ `VineFrame`), and how the header/`KutBalance` is rendered.
- `src/components/KutBalance.jsx` / `StatChip.jsx` — the shared balance/chip look.
- `tailwind.config.js` — font is `Nunito`; farm palette exists but modules mostly use component CSS.

Write down the actual values (background, card bg, primary button gradient/color, border radius scale, text colors) you will reuse.

- [ ] **Step 2: Wrap ChestModule in the shared backdrop**

Make `ChestModule` use the same backdrop wrapper the other tab modules use (`FarmBackground` + `TabAtmosphere`, and `VineFrame` if siblings use it), so the tab background matches. Keep the chest content (feed, roulette, stepper, buttons, subtabs) inside it. Match the sibling modules' outer structure exactly.

- [ ] **Step 3: Re-skin chests.css to the real tokens**

Replace the mockup-derived hardcoded colors in `src/styles/chests.css` with the app's actual tokens/values found in Step 1: same card surface, same primary button style (match `.chest-open-btn` to the app's primary button), same chip style for the 🔑/💎 balances (match `KutBalance`/`StatChip`), same font (Nunito is global), same border-radius scale, same subtab pill look as the app's segmented controls if one exists. Keep the rarity accent colors (common/rare/legendary) — those are intentional and meaningful — but everything else (backgrounds, buttons, chips, headers) must match the app. Apply the same class conventions to ChestRoulette/ChestCollection/ChestFeed as needed.

- [ ] **Step 4: Verify visually against sibling tabs**

`npm run dev` (Playwright available). Open the Сундуки tab side-by-side (by switching) with Задания/Ферма and confirm the background, header, balance chips, buttons, and cards read as the SAME app — not a different-looking module. Screenshot the chest tab and a sibling tab and compare the visual language. Confirm the open flow + collection still work (no behavior regression).

- [ ] **Step 5: Commit**

```bash
git add src/components/ChestModule.jsx src/styles/chests.css src/components/ChestRoulette.jsx src/components/ChestCollection.jsx src/components/ChestFeed.jsx
git commit -m "style(chests-ui): match chest UI to the app design system"
```

---

### Task 10: "Ещё" overflow navigation (declutter the tab bar)

Added from user feedback: the flat bar now has 9 tabs and wraps to 3 rows. Restore a "More" pattern — a few primary tabs + an "Ещё" button that opens a menu with the rest. USER-CHOSEN layout:
- **Primary (in the bar):** Ферма · Инвентарь · Магазин · Ещё
- **Under «Ещё»:** Крафты · Задания · Биржа · Сундуки · Профиль · Настройки

**Files:**
- Modify: `src/components/TabBar.jsx` (render 3 primary tabs + an "Ещё" button; the button opens a menu of the secondary tabs)
- Create: `src/components/MoreMenu.jsx` (the "Ещё" menu, built on the app's shared `BottomSheet`)
- Modify: `src/styles/tabThemes.css` or the relevant tab CSS (styles for the "Ещё" button + menu items), matching the app.
- App.jsx tab STATE and panels stay unchanged — only how a tab gets selected changes.

**Interfaces:** No change to the `tab` state values (`farm|inventory|craft|quests|shop|market|chests|profile|settings`). TabBar still calls `onChange(tabId)`.

- [ ] **Step 1: Study the current TabBar + a sheet usage**

Read `src/components/TabBar.jsx` (the flat `TABS` array, `TAB_ICONS`/`TAB_ACCENTS` usage, badge logic via `useQuestBadge`) and `src/components/BottomSheet.jsx` (props `isOpen`/`onClose`/`title`/`children`). Note the badge pattern (quests) so it survives when quests move under «Ещё».

- [ ] **Step 2: Split primary vs secondary**

In `TabBar.jsx`, define:
```js
const PRIMARY = [
  { id: 'farm', label: 'Ферма' },
  { id: 'inventory', label: 'Инвентарь' },
  { id: 'shop', label: 'Магазин' },
]
const SECONDARY = [
  { id: 'craft', label: 'Крафты' },
  { id: 'quests', label: 'Задания' },
  { id: 'market', label: 'Биржа' },
  { id: 'chests', label: 'Сундуки' },
  { id: 'profile', label: 'Профиль' },
  { id: 'settings', label: 'Настройки' },
]
```
Render the 3 primary tab buttons (same markup/icon/accent as today) + a 4th "Ещё" button. The "Ещё" button is `app-tab-btn-active` when the current `active` tab is in `SECONDARY` (so the user sees they're inside a «Ещё» section). If `useQuestBadge() > 0` and quests isn't active, show the badge dot on the "Ещё" button too (so quest rewards are still discoverable). Use a suitable "Ещё" icon (three dots / grid) added to `TAB_ICONS` as `more`, accent neutral.

- [ ] **Step 3: Build the MoreMenu**

Create `src/components/MoreMenu.jsx`: a `BottomSheet` (title "Ещё") listing the `SECONDARY` tabs as a grid/list of buttons, each with its `TAB_ICONS` icon + label; tapping calls `onChange(id)` then closes the sheet; the currently-active secondary tab is highlighted. Show the quest badge on Задания inside the menu. Props: `{ isOpen, onClose, active, onChange }`.

- [ ] **Step 4: Wire it in TabBar**

Add `const [moreOpen, setMoreOpen] = useState(false)` in TabBar; the "Ещё" button toggles it; render `<MoreMenu isOpen={moreOpen} onClose={() => setMoreOpen(false)} active={active} onChange={(id) => { onChange(id); setMoreOpen(false) }} />`. Ensure selecting a secondary tab closes the menu.

- [ ] **Step 5: Style + verify**

Style the "Ещё" button and menu to match the app (reuse existing tab/sheet classes; the menu items should look like the app's list/tab items). `npm run build` passes. Playwright: confirm the bar shows exactly 4 items in ONE row (Ферма · Инвентарь · Магазин · Ещё), no 3-row wrap; tapping «Ещё» opens the menu with the 6 secondary tabs including **Сундуки**; selecting Сундуки opens the chest tab and closes the menu; the quest badge still surfaces (on «Ещё» and inside the menu). Screenshot the new bar + open menu.

- [ ] **Step 6: Commit**

```bash
git add src/components/TabBar.jsx src/components/MoreMenu.jsx src/components/TabIcons.jsx src/styles/tabThemes.css
git commit -m "feat(nav): Ещё overflow menu — 3 primary tabs + secondary under More (chests in More)"
```

---

## Self-Review (completed by plan author)

**Spec coverage (§8 UI):**
- New "Сундуки" tab → Task 4.
- Roulette center, lands on known result, spins left, legendary effect → Tasks 2 (math), 5 (component), 6 (legendary reveal css).
- Quantity selector (25×N), buy keys via donate bot `chest_{N}` → Task 1 (pricing) + Task 6.
- x1 reveal + xN grid → Task 6.
- Collection album, set progress, locked+shard purchase, equip → Task 7.
- Profile showcase (equipped) → Task 8.
- Live feed (rare/legendary, name) → Task 8 (+ mounted in Task 6).
- Sub-sections Сундук/Коллекция/Осколки → Task 6.

**Placeholder scan:** No TBD/TODO; pure-logic tasks have full TDD; component tasks have complete code + a visual verification step. Two spots require reading an existing file to match conventions (TabIcons icon shape in Task 4; ProfileModule insertion point in Task 8) — these are explicit "inspect and mirror" instructions, not placeholders, because the exact surrounding markup is codebase-specific.

**Type consistency:** `state`/`results` shapes match the Plan-1 API (verified against backend). `clampCount`/`totalStars`/`buildChestBotUrl` (Task 1) consumed by Task 6. `buildStrip`/`landingOffset` (Task 2) consumed by Task 5. `useChests.open` returns the open response consumed by Task 6.

**Known follow-ups (not gaps):**
- 9 tabs may crowd the bottom bar (noted in Task 4 verify) — a compaction pass is a separate polish, not required for function.
- Roulette `pool` filler is optional (falls back to the result cell); a nicer filler pool from the catalog can be added later.
- Deferred backend Minors from Plan 1 (schema dup, weight rounding) are unrelated to this plan.
