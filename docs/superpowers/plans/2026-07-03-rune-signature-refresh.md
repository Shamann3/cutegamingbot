# Rune Signature Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the decorative rune overlay on each farm plot into a functional growth indicator and harvest control, consolidate the two near-duplicate gold hexes into one token system, and reduce the 8-tab bottom nav to 5 primary tabs + a "More" sheet for the meta tabs (Quests/Profile/Settings).

**Architecture:** Pure-CSS-variable palette tokens layered on top of the existing Tailwind setup (no broad repaint of existing `amber-*` utility classes — those stay untouched). A new pure function (`getRuneState`) maps existing plot status/growth-stage data to a rune visual state; `RuneOverlay` becomes a controlled component driven by that state, with an optional tap-to-harvest affordance. Tab consolidation reuses the existing `BottomSheet` component rather than building a new sheet primitive.

**Tech Stack:** React 18 (JSX, function components), Tailwind CSS (utility classes) + a large hand-written `src/index.css` (component classes), Vite, Vitest for unit tests, Playwright MCP for visual verification (no visual regression tooling exists in this repo — Playwright screenshots are a manual-inspection aid, not an automated pass/fail gate).

## Global Constraints

- This project directory has **no git repository** (`git status` fails with "not a git repository"). Do **not** include `git add`/`git commit` steps. After each task's verification passes, just mark the checkbox and move on.
- Keep all user-facing strings in Russian, matching existing copy style (plain, direct, no filler) — see `STATUS_LABELS` in `src/components/PlotCard.jsx` for tone reference.
- Do not touch the existing `amber-*`/`orange-*`/`sky-*`/`emerald-*` Tailwind utility classes used throughout buttons, borders, and chip text — those are working and out of scope. New tokens apply only to the rune system and the two call sites named in each task.
- Respect `prefers-reduced-motion: reduce` for every new `@keyframes` animation added (existing codebase does not currently do this consistently — new code should).
- Visual verification uses the existing no-backend preview mode: run `VITE_FARM_PREVIEW=true npm run dev` (do not edit the committed `.env` — the shell-level env var overrides it because Vite gives `process.env` priority over `.env` file values) and drive it with the Playwright MCP tools already available in this session.
- Vitest is already configured (`npm test` → `vitest run`); new pure-logic files get a colocated `*.test.js`, matching the existing pattern in `src/utils/plotActions.test.js`.

---

### Task 1: Rune palette tokens

**Files:**
- Modify: `src/index.css:1-8` (insert `:root` token block)
- Modify: `src/index.css:37-44` (body background/text → use tokens)
- Modify: `index.html:6` (`theme-color` meta)

**Interfaces:**
- Produces: CSS custom properties `--rune-night`, `--rune-parchment`, `--rune-ember`, `--rune-moss`, `--rune-teal`, `--rune-warn`, available globally to every later task.

- [ ] **Step 1: Add the token block to `src/index.css`**

Current top of file:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

* {
  -webkit-tap-highlight-color: transparent;
  -webkit-touch-callout: none;
}
```

Replace with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --rune-night: #0b140f;
  --rune-parchment: #f1e3c6;
  --rune-ember: #d9a544;
  --rune-moss: #3e7a52;
  --rune-teal: #1f9e8b;
  --rune-warn: #c4622d;
}

* {
  -webkit-tap-highlight-color: transparent;
  -webkit-touch-callout: none;
}
```

- [ ] **Step 2: Point `body` at the tokens**

Current:

```css
body {
  margin: 0;
  min-height: 100vh;
  min-height: 100dvh;
  overflow-x: hidden;
  background-color: #070f0a;
  color: #f5e6c8;
}
```

Replace with:

```css
body {
  margin: 0;
  min-height: 100vh;
  min-height: 100dvh;
  overflow-x: hidden;
  background-color: var(--rune-night);
  color: var(--rune-parchment);
}
```

- [ ] **Step 3: Update the browser theme-color meta tag**

In `index.html`, change:

```html
<meta name="theme-color" content="#070f0a" />
```

to:

```html
<meta name="theme-color" content="#0b140f" />
```

- [ ] **Step 4: Verify visually**

Run:

```bash
VITE_FARM_PREVIEW=true npm run dev
```

Use the Playwright MCP tools to navigate to the printed local URL (default `http://127.0.0.1:5173`) and take a screenshot. Confirm: page background reads as a deep green-black (not pure black), no console errors about unknown CSS properties, layout unchanged from before (this task changes color values only, not structure). Stop the dev server after checking.

---

### Task 2: `runeState` pure function + tests

**Files:**
- Create: `src/utils/runeState.js`
- Create: `src/utils/runeState.test.js`

**Interfaces:**
- Consumes: `PlotStatus` from `src/types/farm.js` (`EMPTY`, `GROWING`, `READY`, `WITHERED`), `GrowthStage` from `src/utils/farmTiming.js` (`SEED`, `SPROUT`, `BUSH`, `TREE`).
- Produces: `RuneState` enum object `{ DORMANT, EMBER, BREATHING, BLAZING, HARVEST }` and `getRuneState(status, growthStage)` — used by Task 3 (`RuneOverlay`) and Task 4 (`PlotCard`).

- [ ] **Step 1: Write the failing test**

Create `src/utils/runeState.test.js`:

```js
import { describe, expect, it } from 'vitest'
import { PlotStatus } from '../types/farm'
import { GrowthStage } from './farmTiming'
import { getRuneState, RuneState } from './runeState'

describe('runeState', () => {
  it('is dormant on an empty or withered plot', () => {
    expect(getRuneState(PlotStatus.EMPTY, null)).toBe(RuneState.DORMANT)
    expect(getRuneState(PlotStatus.WITHERED, null)).toBe(RuneState.DORMANT)
  })

  it('is ember while seed and sprout', () => {
    expect(getRuneState(PlotStatus.GROWING, GrowthStage.SEED)).toBe(RuneState.EMBER)
    expect(getRuneState(PlotStatus.GROWING, GrowthStage.SPROUT)).toBe(RuneState.EMBER)
  })

  it('is breathing at bush stage', () => {
    expect(getRuneState(PlotStatus.GROWING, GrowthStage.BUSH)).toBe(RuneState.BREATHING)
  })

  it('is blazing at tree stage', () => {
    expect(getRuneState(PlotStatus.GROWING, GrowthStage.TREE)).toBe(RuneState.BLAZING)
  })

  it('is harvest once ready, regardless of stage', () => {
    expect(getRuneState(PlotStatus.READY, GrowthStage.TREE)).toBe(RuneState.HARVEST)
    expect(getRuneState(PlotStatus.READY, null)).toBe(RuneState.HARVEST)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/utils/runeState.test.js`
Expected: FAIL with a module-not-found or undefined-export error (`runeState.js` doesn't exist yet).

- [ ] **Step 3: Write the implementation**

Create `src/utils/runeState.js`:

```js
import { PlotStatus } from '../types/farm'
import { GrowthStage } from './farmTiming'

export const RuneState = {
  DORMANT: 'dormant',
  EMBER: 'ember',
  BREATHING: 'breathing',
  BLAZING: 'blazing',
  HARVEST: 'harvest',
}

const STAGE_TO_RUNE = {
  [GrowthStage.SEED]: RuneState.EMBER,
  [GrowthStage.SPROUT]: RuneState.EMBER,
  [GrowthStage.BUSH]: RuneState.BREATHING,
  [GrowthStage.TREE]: RuneState.BLAZING,
}

export function getRuneState(status, growthStage) {
  if (status === PlotStatus.READY) return RuneState.HARVEST
  if (status === PlotStatus.GROWING) return STAGE_TO_RUNE[growthStage] ?? RuneState.EMBER
  return RuneState.DORMANT
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/utils/runeState.test.js`
Expected: PASS, 5 tests.

---

### Task 3: Stateful `RuneOverlay` with tap-to-harvest burst

**Files:**
- Modify: `src/components/decor/RuneOverlay.jsx` (full rewrite)
- Modify: `src/index.css` (append new rune animation block near the end of the custom-classes section — exact insertion point is "end of file" since this is a new, self-contained block)

**Interfaces:**
- Consumes: `RuneState` from `src/utils/runeState.js` (Task 2).
- Produces: `RuneOverlay({ className, state, onHarvest })` — a controlled component. When `state === RuneState.HARVEST` and `onHarvest` is a function, the rune becomes a tappable/keyboard-focusable target that fires `onHarvest()` and plays a 700ms burst animation. Consumed by Task 4 (`PlotCard`).

- [ ] **Step 1: Rewrite `RuneOverlay.jsx`**

Replace the full contents of `src/components/decor/RuneOverlay.jsx` with:

```jsx
import { useEffect, useRef, useState } from 'react'
import { RuneState } from '../../utils/runeState'

const BURST_MS = 700

/** Руны на грядке — не декор, а индикатор роста. Тускнеют/разгораются по стадии,
 * на READY становятся дополнительной точкой сбора урожая (кроме основной кнопки). */
export default function RuneOverlay({ className = '', state = RuneState.DORMANT, onHarvest }) {
  const [bursting, setBursting] = useState(false)
  const burstTimeoutRef = useRef(null)

  useEffect(() => () => {
    if (burstTimeoutRef.current) window.clearTimeout(burstTimeoutRef.current)
  }, [])

  const canTap = state === RuneState.HARVEST && typeof onHarvest === 'function'

  const handleTap = () => {
    if (!canTap) return
    setBursting(true)
    onHarvest()
    burstTimeoutRef.current = window.setTimeout(() => setBursting(false), BURST_MS)
  }

  const handleKeyDown = (event) => {
    if (!canTap) return
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      handleTap()
    }
  }

  return (
    <svg
      viewBox="0 0 120 80"
      className={`rune-overlay rune-overlay--${state} ${bursting ? 'rune-overlay--bursting' : ''} absolute inset-0 w-full h-full ${className}`}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden={!canTap}
      role={canTap ? 'button' : undefined}
      aria-label={canTap ? 'Собрать урожай' : undefined}
      tabIndex={canTap ? 0 : undefined}
      onClick={canTap ? handleTap : undefined}
      onKeyDown={canTap ? handleKeyDown : undefined}
      style={{ pointerEvents: canTap ? 'auto' : 'none', cursor: canTap ? 'pointer' : undefined }}
    >
      <g fill="none" stroke="var(--rune-ember)" strokeWidth="1.2" className="rune-overlay-lines">
        <circle cx="30" cy="28" r="8" />
        <path d="M30 20 L30 36 M22 28 L38 28" />
        <path d="M60 40 L68 32 L76 40 L68 48 Z" />
        <circle cx="90" cy="24" r="6" />
        <path d="M90 18 L90 30 M84 24 L96 24" />
        <path d="M24 58 Q36 50 48 58 T72 58" />
        <path d="M82 52 L88 58 L82 64" />
      </g>
      <g fill="var(--rune-ember)" className="rune-overlay-sparks">
        <circle cx="48" cy="22" r="2" />
        <circle cx="72" cy="44" r="1.5" />
        <circle cx="36" cy="48" r="1.5" />
      </g>
    </svg>
  )
}
```

- [ ] **Step 2: Append the rune animation CSS**

Append this block to the end of `src/index.css`:

```css

/* Руны на грядке — состояние роста (см. src/utils/runeState.js) */

.rune-overlay-lines {
  opacity: 0.08;
  transition: opacity 0.6s ease;
}

.rune-overlay-sparks {
  opacity: 0;
  transition: opacity 0.6s ease;
}

.rune-overlay--ember .rune-overlay-lines {
  opacity: 0.22;
}

.rune-overlay--breathing .rune-overlay-lines {
  opacity: 0.32;
  animation: rune-breathe 3.2s ease-in-out infinite;
}

.rune-overlay--breathing .rune-overlay-sparks {
  opacity: 0.22;
}

.rune-overlay--blazing .rune-overlay-lines {
  opacity: 0.5;
  animation: rune-breathe 1.8s ease-in-out infinite;
}

.rune-overlay--blazing .rune-overlay-sparks {
  opacity: 0.4;
  animation: rune-spark-drift 4s ease-in-out infinite;
}

.rune-overlay--harvest .rune-overlay-lines {
  opacity: 0.65;
  animation: rune-blaze-pulse 1.1s ease-in-out infinite;
}

.rune-overlay--harvest .rune-overlay-sparks {
  opacity: 0.55;
  animation: rune-spark-drift 1.6s ease-in-out infinite;
}

.rune-overlay--bursting .rune-overlay-lines {
  animation: rune-burst-lines 0.7s ease-out;
}

.rune-overlay--bursting .rune-overlay-sparks {
  animation: rune-burst-sparks 0.7s ease-out;
}

@keyframes rune-breathe {
  0%, 100% { opacity: 0.22; }
  50% { opacity: 0.42; }
}

@keyframes rune-blaze-pulse {
  0%, 100% { opacity: 0.55; filter: drop-shadow(0 0 2px var(--rune-ember)); }
  50% { opacity: 1; filter: drop-shadow(0 0 6px var(--rune-ember)); }
}

@keyframes rune-spark-drift {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

@keyframes rune-burst-lines {
  0% { opacity: 1; filter: drop-shadow(0 0 8px var(--rune-ember)); }
  100% { opacity: 0.65; filter: drop-shadow(0 0 2px var(--rune-ember)); }
}

@keyframes rune-burst-sparks {
  0% { opacity: 1; transform: scale(1.6); }
  100% { opacity: 0.55; transform: scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .rune-overlay-lines,
  .rune-overlay-sparks {
    animation: none !important;
  }
}
```

- [ ] **Step 3: Confirm no other file still imports the old prop-less `RuneOverlay`**

Run: `grep -rn "RuneOverlay" src --include=*.jsx`
Expected: only `src/components/decor/RuneOverlay.jsx` (definition) and `src/components/PlotCard.jsx` (usage — updated in Task 4). If any other file renders `<RuneOverlay />` with no props, it will now render permanently dormant (opacity 0.08) instead of the old flat 0.22 — acceptable, but note it here if found so Task 4's reviewer knows every call site was accounted for.

---

### Task 4: Wire `PlotCard` to the rune state and shared harvest handler

**Files:**
- Modify: `src/components/PlotCard.jsx:180-203` (extract `handleHarvestTap`, wire button to it)
- Modify: `src/components/PlotCard.jsx:228` (pass `state`/`onHarvest` to `RuneOverlay`)
- Modify: `src/components/PlotCard.jsx:1-16` (import `getRuneState`)

**Interfaces:**
- Consumes: `getRuneState` from `src/utils/runeState.js` (Task 2), the rewritten `RuneOverlay` from Task 3.

- [ ] **Step 1: Import `getRuneState`**

At the top of `src/components/PlotCard.jsx`, change:

```js
import RuneOverlay from './decor/RuneOverlay'
```

to:

```js
import RuneOverlay from './decor/RuneOverlay'
import { getRuneState } from '../utils/runeState'
```

- [ ] **Step 2: Extract the harvest tap handler**

Find this block (currently around line 180-190):

```js
  const harvestBlockedByTool = status === PlotStatus.READY
    && (plotCrop?.requiresHarvestTool || plotCrop?.requiresAxe)
    && !canHarvestWithTool(plotCrop, axe)
  const harvestTool = plotCrop?.harvestTool
  const harvestLabel = harvestTool?.name
    ? `Собрать (${harvestTool.emoji || '🛠'} −${harvestTool.costPerHarvest ?? 1})`
    : plotCrop?.requiresAxe
      ? (plotCrop.key === 'tree'
        ? `Срубить ${plotCrop.harvestName ?? 'дерево'}`
        : `Собрать ${plotCrop.harvestName ?? 'урожай'}`)
      : `Собрать ${plotCrop?.harvestName ?? 'урожай'}`
```

Immediately after it, add:

```js

  const handleHarvestTap = () => {
    if (harvestBlockedByTool) {
      const toolName = plotCrop?.harvestTool?.name ?? 'Топор'
      window.dispatchEvent(new CustomEvent('farm:go-to-shop', { detail: { search: toolName } }))
    } else {
      onAction(plot.id, 'harvest')
    }
  }
```

- [ ] **Step 3: Point the harvest button at the extracted handler**

Find (currently around line 386-400):

```jsx
              <button
                type="button"
                className="farm-btn-harvest w-full"
                disabled={isBusy}
                onClick={() => {
                  if (harvestBlockedByTool) {
                    const toolName = plotCrop?.harvestTool?.name ?? 'Топор'
                    window.dispatchEvent(new CustomEvent('farm:go-to-shop', { detail: { search: toolName } }))
                  } else {
                    onAction(plot.id, 'harvest')
                  }
                }}
              >
                {harvestBlockedByTool ? `Купить ${plotCrop?.harvestTool?.name ?? 'инструмент'} ` : harvestLabel}
              </button>
```

Replace the `onClick` with the extracted handler:

```jsx
              <button
                type="button"
                className="farm-btn-harvest w-full"
                disabled={isBusy}
                onClick={handleHarvestTap}
              >
                {harvestBlockedByTool ? `Купить ${plotCrop?.harvestTool?.name ?? 'инструмент'} ` : harvestLabel}
              </button>
```

- [ ] **Step 4: Wire `RuneOverlay` to the growth state**

Find (currently around line 228):

```jsx
          <RuneOverlay />
```

Replace with:

```jsx
          <RuneOverlay
            state={getRuneState(status, growthStage)}
            onHarvest={status === PlotStatus.READY && !isBusy && !harvestBlockedByTool ? handleHarvestTap : undefined}
          />
```

- [ ] **Step 5: Verify with unit tests**

Run: `npx vitest run`
Expected: all existing tests still pass (`plotActions.test.js`, `runeState.test.js`) — this task doesn't change any tested logic, only wires it into JSX, so no new test is needed here (the logic itself is covered by Task 2's tests).

- [ ] **Step 6: Verify visually**

Run:

```bash
VITE_FARM_PREVIEW=true npm run dev
```

Use the Playwright MCP tools to navigate to the farm tab and screenshot a plot. Confirm:
- No console errors.
- The rune lines under a growing plant render more visible than the old flat `opacity-[0.22]` baseline (preview data seeds a couple of already-growing plots — check whichever stage is showing renders *some* gold linework, not fully invisible).
- Tapping directly on the rune area of a plot that is NOT ready to harvest does nothing (no `pointer-events`, confirmed by the `style` inline check in the DOM snapshot).

Stop the dev server after checking.

---

### Task 5: Add the "More" tab icon and accent color

**Files:**
- Modify: `src/components/TabIcons.jsx`

**Interfaces:**
- Produces: `TAB_ICONS.more` (component) and `TAB_ACCENTS.more` (`{ strong, glow }`), consumed by Task 7 (`TabBar`).

- [ ] **Step 1: Add the `More` icon and register it**

In `src/components/TabIcons.jsx`, after the `Settings` icon definition and before `export const TAB_ICONS = {`, add:

```jsx
const More = () => (
  <Icon>
    <circle cx="12" cy="12" r="8.5" />
    <circle cx="8.6" cy="12" r="1" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
    <circle cx="15.4" cy="12" r="1" fill="currentColor" stroke="none" />
  </Icon>
)
```

Then update the exports:

```jsx
export const TAB_ICONS = {
  farm: Farm,
  inventory: Inventory,
  craft: Craft,
  quests: Quests,
  shop: Shop,
  market: Market,
  profile: Profile,
  settings: Settings,
  more: More,
}

// Те же значения, что в src/styles/tabThemes.css (--tab-accent-strong / --tab-accent-glow) —
// держать в синхроне, если поменяются там.
export const TAB_ACCENTS = {
  farm: { strong: '#34d399', glow: 'rgba(52, 211, 153, 0.32)' },
  inventory: { strong: '#d97706', glow: 'rgba(217, 119, 6, 0.3)' },
  craft: { strong: '#a78bfa', glow: 'rgba(124, 58, 237, 0.34)' },
  quests: { strong: '#f97316', glow: 'rgba(249, 115, 22, 0.32)' },
  shop: { strong: '#f59e0b', glow: 'rgba(251, 191, 36, 0.3)' },
  market: { strong: '#b87333', glow: 'rgba(184, 115, 51, 0.32)' },
  profile: { strong: '#22d3ee', glow: 'rgba(34, 211, 238, 0.32)' },
  settings: { strong: '#64748b', glow: 'rgba(100, 116, 139, 0.32)' },
  more: { strong: '#d9a544', glow: 'rgba(217, 165, 68, 0.32)' },
}
```

(`more`'s accent intentionally matches `--rune-ember` from Task 1 — it's the gateway to the rune-token part of the UI.)

- [ ] **Step 2: Verify**

Run: `npx vitest run` — no test touches this file, so this step is just confirming the dev server still boots without a syntax error:

```bash
VITE_FARM_PREVIEW=true npm run dev
```

Check the terminal output for compile errors, then stop the server. Full visual check happens in Task 9 once `TabBar` actually renders the new icon.

---

### Task 6: `TabMoreSheet` component

**Files:**
- Create: `src/components/TabMoreSheet.jsx`
- Modify: `src/index.css` (append `.tab-more-grid` / `.tab-more-btn` block)

**Interfaces:**
- Consumes: `BottomSheet` from `src/components/BottomSheet.jsx`, `TAB_ICONS` from `src/components/TabIcons.jsx` (Task 5).
- Produces: `TabMoreSheet({ isOpen, onClose, active, onSelect, questBadge })`, consumed by Task 7 (`TabBar`).

- [ ] **Step 1: Create the component**

Create `src/components/TabMoreSheet.jsx`:

```jsx
import BottomSheet from './BottomSheet'
import { TAB_ICONS } from './TabIcons'

const MORE_TABS = [
  { id: 'quests', label: 'Задания' },
  { id: 'profile', label: 'Профиль' },
  { id: 'settings', label: 'Настройки' },
]

export default function TabMoreSheet({ isOpen, onClose, active, onSelect, questBadge = 0 }) {
  return (
    <BottomSheet isOpen={isOpen} onClose={onClose} title="Ещё" showApply={false}>
      <div className="tab-more-grid">
        {MORE_TABS.map((tab) => {
          const TabIcon = TAB_ICONS[tab.id]
          const showBadge = tab.id === 'quests' && questBadge > 0
          return (
            <button
              key={tab.id}
              type="button"
              className={`tab-more-btn ${active === tab.id ? 'tab-more-btn-active' : ''}`}
              onClick={() => {
                onSelect(tab.id)
                onClose()
              }}
            >
              <span className="app-tab-icon-wrap">
                <span className="app-tab-icon">{TabIcon && <TabIcon />}</span>
                {showBadge && (
                  <span className="app-tab-badge" aria-label={`${questBadge} наград`}>
                    {questBadge > 9 ? '9+' : questBadge}
                  </span>
                )}
              </span>
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>
    </BottomSheet>
  )
}
```

- [ ] **Step 2: Append the grid CSS**

Append to the end of `src/index.css` (after the rune animation block from Task 3):

```css

/* Раскрывающийся список "Ещё" в нижнем таб-баре */

.tab-more-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.6rem;
  padding: 0.4rem 0 0.6rem;
}

.tab-more-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 0.9rem 0.4rem;
  border-radius: 14px;
  border: 1px solid rgba(212, 175, 55, 0.18);
  background: rgba(255, 255, 255, 0.03);
  color: rgba(241, 227, 198, 0.85);
  font-size: 0.7rem;
  font-weight: 700;
}

.tab-more-btn svg {
  width: 22px;
  height: 22px;
}

.tab-more-btn-active {
  border-color: var(--rune-ember);
  color: var(--rune-parchment);
  background: rgba(217, 165, 68, 0.12);
}
```

- [ ] **Step 3: Verify component compiles**

Run:

```bash
VITE_FARM_PREVIEW=true npm run dev
```

Check the terminal for compile errors (this component isn't wired into `TabBar` yet, so there's nothing to click — Task 7 wires it, Task 9 verifies the full flow). Stop the server after checking.

---

### Task 7: Consolidate `TabBar` to 5 primary tabs + More

**Files:**
- Modify: `src/components/TabBar.jsx` (full rewrite)

**Interfaces:**
- Consumes: `TabMoreSheet` from Task 6, `TAB_ICONS`/`TAB_ACCENTS` from Task 5.
- Produces: same public interface as before — `TabBar({ active, onChange })` — no caller changes needed in `src/App.jsx`.

- [ ] **Step 1: Confirm no onboarding spotlight targets a tab being moved**

Already confirmed during planning: `src/components/OnboardingSpotlight.jsx` only targets `[data-onboarding-tab="shop"]` and `[data-onboarding-tab="market"]` (both stay in the primary 5). No further action needed — this step is a documented check, not a code change.

- [ ] **Step 2: Rewrite `TabBar.jsx`**

Replace the full contents of `src/components/TabBar.jsx` with:

```jsx
import { useState } from 'react'
import { useOnboardingOptional } from '../context/OnboardingContext'
import { useQuestBadge } from '../hooks/useQuests'
import { TAB_ACCENTS, TAB_ICONS } from './TabIcons'
import TabMoreSheet from './TabMoreSheet'

const PRIMARY_TABS = [
  { id: 'farm', label: 'Ферма' },
  { id: 'inventory', label: 'Инвентарь' },
  { id: 'craft', label: 'Крафты' },
  { id: 'shop', label: 'Магазин' },
  { id: 'market', label: 'Биржа' },
]

const MORE_TAB_IDS = ['quests', 'profile', 'settings']

export default function TabBar({ active, onChange }) {
  const onboarding = useOnboardingOptional()
  const pulseTab = onboarding?.pulseTab ?? null
  const questBadge = useQuestBadge()
  const [moreOpen, setMoreOpen] = useState(false)

  const activeInMore = MORE_TAB_IDS.includes(active)
  const moreBadge = active === 'quests' ? 0 : questBadge
  const moreAccent = TAB_ACCENTS.more
  const MoreIcon = TAB_ICONS.more

  return (
    <>
      <nav className="app-tab-bar" aria-label="Разделы приложения">
        <div className="app-tab-bar-inner">
          {PRIMARY_TABS.map((tab) => {
            const isActive = active === tab.id
            const isPulsing = pulseTab === tab.id
            const TabIcon = TAB_ICONS[tab.id]
            const accent = TAB_ACCENTS[tab.id]
            return (
              <button
                key={tab.id}
                type="button"
                className={`app-tab-btn ${isActive ? 'app-tab-btn-active' : ''} ${isPulsing ? 'app-tab-btn-pulse' : ''}`}
                data-onboarding-tab={tab.id}
                data-tab={tab.id}
                aria-current={isActive ? 'page' : undefined}
                onClick={() => onChange(tab.id)}
                style={accent ? { '--tab-icon-strong': accent.strong, '--tab-icon-glow': accent.glow } : undefined}
              >
                <span className="app-tab-icon-wrap">
                  <span className="app-tab-icon">{TabIcon && <TabIcon />}</span>
                </span>
                <span className="app-tab-label">{tab.label}</span>
              </button>
            )
          })}

          <button
            type="button"
            className={`app-tab-btn ${activeInMore ? 'app-tab-btn-active' : ''}`}
            data-tab="more"
            aria-haspopup="dialog"
            aria-expanded={moreOpen}
            onClick={() => setMoreOpen(true)}
            style={moreAccent ? { '--tab-icon-strong': moreAccent.strong, '--tab-icon-glow': moreAccent.glow } : undefined}
          >
            <span className="app-tab-icon-wrap">
              <span className="app-tab-icon">{MoreIcon && <MoreIcon />}</span>
              {moreBadge > 0 && (
                <span className="app-tab-badge" aria-label={`${moreBadge} наград`}>
                  {moreBadge > 9 ? '9+' : moreBadge}
                </span>
              )}
            </span>
            <span className="app-tab-label">Ещё</span>
          </button>
        </div>
      </nav>

      <TabMoreSheet
        isOpen={moreOpen}
        onClose={() => setMoreOpen(false)}
        active={active}
        onSelect={onChange}
        questBadge={questBadge}
      />
    </>
  )
}
```

---

### Task 8: Rune-notch handle for the shared bottom sheet

**Files:**
- Modify: `src/index.css:3749-3755` (`.shop-sheet-handle`)

**Interfaces:** none — pure CSS, automatically applies to every `BottomSheet` consumer (`ShopToolbar`, `SettingsModule`, and the new `TabMoreSheet` from Task 6).

- [ ] **Step 1: Replace the plain handle with a rune-notch**

Find:

```css
  .shop-sheet-handle {
    width: 2.5rem;
    height: 0.28rem;
    margin: 0 auto 0.75rem;
    border-radius: 999px;
    background: rgba(251, 191, 36, 0.38);
  }
```

Replace with:

```css
  .shop-sheet-handle {
    position: relative;
    width: 2.75rem;
    height: 0.22rem;
    margin: 0 auto 0.85rem;
    border-radius: 999px;
    background: rgba(217, 165, 68, 0.3);
  }

  .shop-sheet-handle::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0.34rem;
    height: 0.34rem;
    transform: translate(-50%, -50%) rotate(45deg);
    background: var(--rune-ember);
    box-shadow: 0 0 6px rgba(217, 165, 68, 0.55);
  }
```

- [ ] **Step 2: Verify visually**

Run:

```bash
VITE_FARM_PREVIEW=true npm run dev
```

Navigate to the Shop tab, open its filter/search bottom sheet (or Settings, whichever is faster to trigger), and screenshot it with the Playwright MCP tools. Confirm the drag handle now shows a small gold diamond centered on the bar instead of a flat pill. Stop the dev server after checking.

---

### Task 9: Full-flow verification of the tab consolidation

**Files:** none (verification only)

- [ ] **Step 1: Run the full unit test suite**

Run: `npx vitest run`
Expected: all tests pass (including `runeState.test.js` from Task 2 and the pre-existing `plotActions.test.js`).

- [ ] **Step 2: Drive the app end-to-end with Playwright MCP tools**

Run:

```bash
VITE_FARM_PREVIEW=true npm run dev
```

Then, using the Playwright MCP tools:
1. Navigate to the local dev URL.
2. Take a snapshot of the bottom tab bar — confirm exactly 6 buttons are visible: Ферма, Инвентарь, Крафты, Магазин, Биржа, Ещё.
3. Click "Ещё" — confirm a bottom sheet opens titled "Ещё" with 3 buttons: Задания, Профиль, Настройки, and (if the preview seed data has any claimable quest) a badge on Задания.
4. Click "Профиль" inside the sheet — confirm the sheet closes and the Profile module renders (same content that used to be reachable directly from the bottom bar).
5. Reopen "Ещё" via the bottom bar and confirm the "Профиль" button now shows the active state (`tab-more-btn-active`).
6. Click the "Ферма" tab directly from the bottom bar — confirm it still works exactly as before (primary tabs are unchanged in behavior, only regrouped).

Report any step that doesn't match. Stop the dev server after checking.

- [ ] **Step 3: Confirm the onboarding flow is unaffected**

Using the Playwright MCP tools, if the running instance can reach the onboarding intro (preview mode auto-starts it on first load — check `src/lib/onboardingClient.js` for the preview trigger if it doesn't appear automatically), step through to the point where it highlights the Shop or Market tab and confirm the spotlight ring still lands correctly on those buttons in the bottom bar (this is the check that Task 7 Step 1 predicted would be safe — this step is the empirical confirmation).

---

## Explicitly out of scope for this plan

- **Tab-switch crossfade animation.** `App.jsx`'s `AppShell` currently swaps modules with a raw `hidden` class inside a normal-flow, page-scrolling `.app-main` container. A crossfade needs `display:none`-free hidden panels, which means restructuring `.app-main` into an absolute-position stack — that touches the scroll container of every module (Farm, Inventory, Craft, Quests, Shop, Market, Profile, Settings) and deserves its own isolated plan and testing pass, not a bundled task here.
- **Converting `InventoryItemModal` (or other modals) onto the shared `BottomSheet`.** Checked during planning: `InventoryItemModal` is a deliberately *centered* card reveal (`.inv-card-root` is `position: fixed; display:flex; align-items:center; justify-content:center`), not a slide-up sheet. Forcing it into `BottomSheet` would replace an intentional interaction pattern sized for its hero-icon-plus-price content, not fix an inconsistency. Left as-is.
- **Broad palette repaint.** The new `--rune-*` tokens apply only to the rune system and the bottom-sheet handle. The existing `amber-*`/`orange-*` Tailwind utility classes used across buttons, chips, and borders throughout the app are untouched — repainting those is a much larger, separate risk and wasn't part of what was agreed.
