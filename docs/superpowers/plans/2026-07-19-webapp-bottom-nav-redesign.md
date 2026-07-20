# Редизайн нижней навигации webapp — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить нижнюю навигацию (3 таба + «Ещё» с 5 спрятанными пунктами) на 5 табов первого уровня (Ферма, Торговля, Розыгрыши, Задания, Профиль), слить Магазин+Биржу в единый хаб «Торговля», и перенести Инвентарь/Крафты/Настройки в контекстные точки входа на Ферме и в Профиле.

**Architecture:** Магазин (`ExchangeModule`) и Биржа (`MarketplaceModule`) не переписываются с нуля — они получают `embedded`/`section`-пропы, которые прячут их собственный хедер/фон, и хостятся внутри нового тонкого `TradeModule` с одним общим хедером и плоским 3-сегментным переключателем (Магазин/Биржа/Продать). Крафты и Настройки остаются полностью нетронутыми полноэкранными табами в `App.jsx` — меняется только точка входа (иконки на Ферме/Профиле вместо пункта в «Ещё»). Deep-link'и (`?startapp=shop|market`, события `farm:go-to-shop|market`) продолжают работать через чистую функцию алиас-маппинга.

**Tech Stack:** React 18 (без роутера, `tab`-state в `App.jsx`), Vite, обычный CSS (без CSS-модулей/Tailwind-only — смесь utility-классов и кастомных `.farm-*`/`.shop-*`/`.market-*` классов), Vitest для юнит-тестов чистой логики (компонентных тестов в проекте нет).

## Global Constraints

- Копирайт/лейблы — только на русском, в стиле существующих (`Ферма`, `Задания`, `Профиль` и т.д.).
- В проекте нет фреймворка для тестирования React-компонентов (`@testing-library/react` не установлен) — юнит-тесты (`vitest`) пишем только для чистой логики (`src/utils/*.js`). Для задач, трогающих JSX/CSS, шаг «тест» — это ручная/браузерная проверка через дев-сервер (`preview_start` + `read_page`/`screenshot`), а не автотест. Это соответствует текущей конвенции репозитория (см. `src/utils/*.test.js` — тестируется только логика, не компоненты).
- Не трогаем внутреннюю бизнес-логику `useShop`/`useMarketplace` (хуки остаются как есть) — меняется только то, что вокруг них рендерится.
- Не добавляем сегмент «Графики», логику розыгрышей/таймеров/бейджей, тап-по-грядке → инвентарь — всё это явно вне объёма по спеке ([2026-07-19-webapp-bottom-nav-redesign-design.md](../specs/2026-07-19-webapp-bottom-nav-redesign-design.md)).
- Каждая задача заканчивается рабочим состоянием приложения (без сломанных промежуточных коммитов) — там, где это невозможно (задача 3), это явно оговорено.

---

## File Structure

**Новые файлы:**
- `src/utils/tradeNav.js` — чистая функция алиас-маппинга deep-link'ов (`resolveStartTab`).
- `src/utils/tradeNav.test.js` — юнит-тесты для неё.
- `src/components/TradeModule.jsx` — хаб «Торговля»: общий хедер + 3-сегментный переключатель, хостит `ExchangeModule`/`MarketplaceModule` в `embedded`-режиме.
- `src/components/GiveawaysModule.jsx` — заглушка «Розыгрыши».
- `src/styles/trade.css` — стили хедера/сегментов `TradeModule`.
- `src/styles/giveaways.css` — стили заглушки `GiveawaysModule`.

**Модифицируются:**
- `src/lib/telegram.js` — `VALID_TABS` дополняется `trade`/`giveaways`.
- `src/components/TabIcons.jsx` — новая иконка `Gift`, акценты `trade`/`giveaways`.
- `src/styles/tabThemes.css` — тема/атмосфера `giveaways`, нижняя панель для `trade`/`giveaways`, удаление мёртвых правил для `shop`/`market` (после задачи 4 эти id никогда не становятся значением `tab`).
- `src/components/ExchangeModule.jsx` — проп `embedded`.
- `src/components/MarketplaceModule.jsx` — пропы `embedded`, `section` (`'browse' | 'sell'`).
- `src/App.jsx` — роутинг `trade`/`giveaways` вместо `shop`/`market`, проброс точек входа в `FarmModule`/`ProfileModule`.
- `src/components/TabBar.jsx` — 5 табов первого уровня вместо 3+«Ещё», без `MoreMenu`.
- `src/components/MoreMenu.jsx` — удаляется.
- `src/context/OnboardingContext.jsx` — пульс-подсказка теперь указывает на `trade`.
- `src/hooks/useSwipeTabs.js` — новый `TAB_ORDER`.
- `src/components/FarmHeader.jsx` — иконки-кнопки инвентаря/крафта.
- `src/components/FarmModule.jsx` — проброс `onOpenInventory`/`onOpenCraft` в `FarmHeader`.
- `src/components/ProfileModule.jsx` — иконка-кнопка настроek в хедере.
- `src/index.css` — грид на 5 колонок, стиль приподнятой кнопки «Розыгрыши», стили кнопок на Ферме/в Профиле.

---

## Task 1: Deep-link алиас-маппинг (чистая логика, TDD)

**Files:**
- Create: `src/utils/tradeNav.js`
- Create: `src/utils/tradeNav.test.js`
- Modify: `src/lib/telegram.js:54`

**Interfaces:**
- Produces: `resolveStartTab(rawTab: string) => { tab: string, tradeSegment: 'shop' | 'market' }` — используется в задаче 4 внутри `App.jsx` для инициализации `tab`/`tradeSegment` и нигде больше в этой задаче.

- [ ] **Step 1: Написать падающий тест**

Создать `src/utils/tradeNav.test.js`:

```js
import { describe, expect, it } from 'vitest'
import { resolveStartTab } from './tradeNav'

describe('resolveStartTab', () => {
  it('maps legacy "shop" deep-link to the trade tab on the shop segment', () => {
    expect(resolveStartTab('shop')).toEqual({ tab: 'trade', tradeSegment: 'shop' })
  })

  it('maps legacy "market" deep-link to the trade tab on the market segment', () => {
    expect(resolveStartTab('market')).toEqual({ tab: 'trade', tradeSegment: 'market' })
  })

  it('defaults a direct "trade" deep-link to the shop segment', () => {
    expect(resolveStartTab('trade')).toEqual({ tab: 'trade', tradeSegment: 'shop' })
  })

  it('passes through unrelated tabs unchanged', () => {
    expect(resolveStartTab('quests')).toEqual({ tab: 'quests', tradeSegment: 'shop' })
    expect(resolveStartTab('farm')).toEqual({ tab: 'farm', tradeSegment: 'shop' })
  })
})
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `npx vitest run src/utils/tradeNav.test.js`
Expected: FAIL — `Cannot find module './tradeNav'` (файл ещё не создан).

- [ ] **Step 3: Реализовать `resolveStartTab`**

Создать `src/utils/tradeNav.js`:

```js
const LEGACY_TRADE_SEGMENT = {
  shop: 'shop',
  market: 'market',
}

/** Разбирает id таба из deep-link (?startapp=... / start_param) в {tab, tradeSegment}. */
export function resolveStartTab(rawTab) {
  if (rawTab in LEGACY_TRADE_SEGMENT) {
    return { tab: 'trade', tradeSegment: LEGACY_TRADE_SEGMENT[rawTab] }
  }
  if (rawTab === 'trade') {
    return { tab: 'trade', tradeSegment: 'shop' }
  }
  return { tab: rawTab, tradeSegment: 'shop' }
}
```

- [ ] **Step 4: Убедиться, что тест проходит**

Run: `npx vitest run src/utils/tradeNav.test.js`
Expected: PASS (4 теста).

- [ ] **Step 5: Разрешить `trade`/`giveaways` в `getStartTab()`**

В `src/lib/telegram.js:54` заменить:

```js
const VALID_TABS = new Set(['farm', 'inventory', 'craft', 'quests', 'shop', 'market', 'settings'])
```

на:

```js
const VALID_TABS = new Set(['farm', 'inventory', 'craft', 'quests', 'shop', 'market', 'trade', 'giveaways', 'settings'])
```

(Значения `shop`/`market` остаются в множестве — это легаси-алиасы, которые разбирает `resolveStartTab`.)

- [ ] **Step 6: Прогнать весь набор юнит-тестов, убедиться что ничего не сломано**

Run: `npx vitest run`
Expected: все тесты (включая `chestPricing.test.js`, `plotActions.test.js`, `rouletteStrip.test.js`, новый `tradeNav.test.js`) — PASS.

- [ ] **Step 7: Commit**

```bash
git add src/utils/tradeNav.js src/utils/tradeNav.test.js src/lib/telegram.js
git commit -m "feat(webapp): add trade deep-link alias resolver"
```

---

## Task 2: Визуальный скелет для «Торговли» и «Розыгрышей» (только CSS/иконки, без поведения)

Ничего из этой задачи ещё не используется в приложении — это безопасное аддитивное расширение существующих файлов. Проверка — сборка не ломается и существующие вкладки выглядят как раньше.

**Files:**
- Modify: `src/components/TabIcons.jsx` (после строки 109, перед `export const TAB_ICONS`; и карты `TAB_ICONS`/`TAB_ACCENTS`)
- Modify: `src/styles/tabThemes.css` (добавить блоки, ничего не удалять в этой задаче)
- Create: `src/styles/trade.css`
- Create: `src/styles/giveaways.css`

**Interfaces:**
- Produces: `TAB_ICONS.trade`, `TAB_ICONS.giveaways`, `TAB_ACCENTS.trade`, `TAB_ACCENTS.giveaways` (использует задача 4 в `TabBar.jsx`); CSS-классы `.tab-theme-giveaways`, `.tab-atmosphere--giveaways`, `.trade-*`, `.giveaways-*` (использует задача 3/4).

- [ ] **Step 1: Добавить иконку `Gift` и новые записи в `TabIcons.jsx`**

В `src/components/TabIcons.jsx` после блока `const More = () => (...)` (строки 103-109) добавить:

```jsx
const Gift = () => (
  <Icon>
    <rect x="4" y="9" width="16" height="11" rx="1.5" />
    <path d="M4 9h16" />
    <path d="M12 9v11" />
    <path d="M12 9c-1.6-3.6-6-3.6-6-1 0 1 .9 1 2 1" />
    <path d="M12 9c1.6-3.6 6-3.6 6-1 0 1-.9 1-2 1" />
  </Icon>
)
```

Заменить блок `export const TAB_ICONS = {...}` (строки 111-122):

```jsx
export const TAB_ICONS = {
  farm: Farm,
  inventory: Inventory,
  craft: Craft,
  quests: Quests,
  shop: Shop,
  market: Market,
  chests: Chests,
  profile: Profile,
  settings: Settings,
  more: More,
  trade: Market,
  giveaways: Gift,
}
```

Заменить блок `export const TAB_ACCENTS = {...}` (строки 126-137):

```jsx
export const TAB_ACCENTS = {
  farm: { strong: '#34d399', glow: 'rgba(52, 211, 153, 0.32)' },
  inventory: { strong: '#d97706', glow: 'rgba(217, 119, 6, 0.3)' },
  craft: { strong: '#a78bfa', glow: 'rgba(124, 58, 237, 0.34)' },
  quests: { strong: '#f97316', glow: 'rgba(249, 115, 22, 0.32)' },
  shop: { strong: '#f59e0b', glow: 'rgba(251, 191, 36, 0.3)' },
  market: { strong: '#b87333', glow: 'rgba(184, 115, 51, 0.32)' },
  chests: { strong: '#e6b422', glow: 'rgba(230,180,34,0.5)' },
  profile: { strong: '#22d3ee', glow: 'rgba(34, 211, 238, 0.32)' },
  settings: { strong: '#64748b', glow: 'rgba(100, 116, 139, 0.32)' },
  more: { strong: '#d4af37', glow: 'rgba(212, 175, 55, 0.32)' },
  trade: { strong: '#cd9b5a', glow: 'rgba(184, 115, 51, 0.32)' },
  giveaways: { strong: '#f472b6', glow: 'rgba(244, 114, 182, 0.34)' },
}
```

- [ ] **Step 2: Добавить тему и атмосферу `giveaways` в `tabThemes.css`**

В `src/styles/tabThemes.css` после блока `.tab-theme-profile {...}` (строки 115-127) добавить:

```css
.tab-theme-giveaways {
  --tab-accent: #f9a8d4;
  --tab-accent-strong: #f472b6;
  --tab-accent-muted: rgba(249, 168, 212, 0.62);
  --tab-accent-soft: rgba(244, 114, 182, 0.16);
  --tab-accent-glow: rgba(244, 114, 182, 0.34);
  --tab-surface: rgba(30, 12, 22, 0.96);
  --tab-surface-alt: rgba(20, 8, 16, 0.94);
  --tab-frame-border: rgba(244, 114, 182, 0.32);
  --tab-title-color: #fce7f3;
  --tab-chip-border: rgba(244, 114, 182, 0.28);
  --tab-balance-frame: linear-gradient(135deg, #fce7f3 0%, #be185d 35%, #f472b6 65%, #500724 100%);
}
```

После блока `.tab-atmosphere--profile .tab-atmosphere-texture {...}` (строки 314-323), перед `.tab-atmosphere--chests` (строка 325), добавить:

```css
.tab-atmosphere--giveaways .tab-atmosphere-base {
  background:
    radial-gradient(ellipse 120% 70% at 50% -10%, rgba(244, 114, 182, 0.22) 0%, transparent 58%),
    linear-gradient(180deg, rgba(80, 7, 36, 0.24) 0%, rgba(20, 8, 16, 0.42) 100%);
}

.tab-atmosphere--giveaways .tab-atmosphere-glow-a {
  background: radial-gradient(circle at 14% 78%, rgba(249, 168, 212, 0.18) 0%, transparent 42%);
}

.tab-atmosphere--giveaways .tab-atmosphere-glow-b {
  background: radial-gradient(circle at 86% 22%, rgba(244, 114, 182, 0.14) 0%, transparent 38%);
}
```

В самом конце файла (после строки 687, блок `.app-tab-btn[data-tab='chests']...`) добавить строчку нижней панели для `trade`/`giveaways` (правила для `shop`/`market` пока не трогаем — они ещё используются до задачи 4):

```css
.app-shell[data-active-tab='trade'] .app-tab-bar-inner {
  background: linear-gradient(135deg, #fde8d0 0%, #9a5f2a 35%, #cd9b5a 65%, #3d2314 100%);
}

.app-shell[data-active-tab='giveaways'] .app-tab-bar-inner {
  background: linear-gradient(135deg, #fce7f3 0%, #be185d 35%, #f472b6 65%, #500724 100%);
}

.app-shell[data-active-tab='trade'] .app-tab-btn-active {
  color: #fde8d0;
  box-shadow: inset 0 0 20px rgba(184, 115, 51, 0.22), 0 2px 8px rgba(0, 0, 0, 0.35);
}

.app-shell[data-active-tab='giveaways'] .app-tab-btn-active {
  color: #fce7f3;
  box-shadow: inset 0 0 20px rgba(244, 114, 182, 0.22), 0 2px 8px rgba(0, 0, 0, 0.35);
}

.app-tab-btn[data-tab='trade'].app-tab-btn-active .app-tab-icon {
  filter: drop-shadow(0 0 6px rgba(205, 155, 90, 0.55));
}

.app-tab-btn[data-tab='giveaways'].app-tab-btn-active .app-tab-icon {
  filter: drop-shadow(0 0 6px rgba(244, 114, 182, 0.55));
}
```

- [ ] **Step 3: Создать `src/styles/trade.css`**

```css
/* Стили хаба «Торговля» — общий хедер и 3-сегментный переключатель. Согласовано с
   .shop-exchange-* (src/index.css) и .chest-subtabs (src/styles/chests.css). */

.trade-shell {
  width: 100%;
  max-width: 28rem;
  margin-left: auto;
  margin-right: auto;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
}

@media (min-width: 520px) {
  .trade-shell {
    max-width: 36rem;
  }
}

@media (min-width: 900px) {
  .trade-shell {
    max-width: 52rem;
  }
}

.trade-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.55rem;
  margin-bottom: 0.75rem;
}

.trade-header-main {
  min-width: 0;
}

.trade-header-eyebrow {
  margin: 0;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--tab-accent-muted);
}

.trade-header-title {
  margin: 0.1rem 0 0;
  font-family: Cinzel, Georgia, serif;
  font-size: 1.55rem;
  font-weight: 700;
  line-height: 1.1;
  color: var(--tab-title-color);
}

.trade-header-balance {
  flex-shrink: 0;
}

.trade-subtabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.4rem;
  margin-bottom: 0.75rem;
}

.trade-subtab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-width: 0;
  padding: 0.42rem 0.45rem;
  border-radius: 999px;
  border: 1px solid var(--tab-chip-border);
  background: rgba(8, 18, 12, 0.92);
  color: rgba(254, 243, 199, 0.78);
  font-size: 0.68rem;
  font-weight: 800;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, color 0.15s, box-shadow 0.15s;
}

.trade-subtab-active {
  border-color: var(--tab-accent-strong);
  background: var(--tab-surface);
  color: var(--tab-title-color);
  box-shadow:
    inset 0 0 10px var(--tab-accent-soft),
    0 0 0 1px var(--tab-accent-soft);
}
```

- [ ] **Step 4: Создать `src/styles/giveaways.css`**

```css
/* Заглушка «Розыгрыши» — по образцу .market-board-empty (src/index.css). */

.giveaways-shell {
  width: 100%;
  max-width: 28rem;
  margin-left: auto;
  margin-right: auto;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
}

@media (min-width: 520px) {
  .giveaways-shell {
    max-width: 36rem;
  }
}

.giveaways-header {
  margin-bottom: 0.85rem;
}

.giveaways-header-eyebrow {
  margin: 0;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--tab-accent-muted);
}

.giveaways-header-title {
  margin: 0.1rem 0 0;
  font-family: Cinzel, Georgia, serif;
  font-size: 1.55rem;
  font-weight: 700;
  line-height: 1.1;
  color: var(--tab-title-color);
  text-shadow: 0 2px 18px var(--tab-accent-glow);
}

.giveaways-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  text-align: center;
  padding: 3rem 1.25rem;
}

.giveaways-empty-icon {
  font-size: 2.4rem;
  filter: drop-shadow(0 2px 10px var(--tab-accent-glow));
}

.giveaways-empty p {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  line-height: 1.45;
  color: var(--tab-title-color);
  max-width: 16rem;
}
```

- [ ] **Step 5: Проверить, что сборка не сломана**

Run: `npm run build`
Expected: сборка проходит без ошибок (новые файлы валидны, ничего пока не импортирует их, но синтаксис должен быть чист).

- [ ] **Step 6: Commit**

```bash
git add src/components/TabIcons.jsx src/styles/tabThemes.css src/styles/trade.css src/styles/giveaways.css
git commit -m "feat(webapp): add trade/giveaways icons, theme and CSS scaffolding"
```

---

## Task 3: `GiveawaysModule` + `TradeModule`, `embedded`-режим у Магазина и Биржи

Эта задача создаёт новые компоненты, но ещё не подключает их к навигации (это задача 4) — потрогать их в браузере штатно нельзя, поэтому проверка здесь — чистая сборка + внимательная сверка JSX с исходными файлами (diff должен быть чисто аддитивным для существующей — не embedded — ветки рендера).

**Files:**
- Create: `src/components/GiveawaysModule.jsx`
- Modify: `src/components/ExchangeModule.jsx:25-31` (сигнатура), `src/components/ExchangeModule.jsx:133-151` (рендер)
- Modify: `src/components/MarketplaceModule.jsx:34-40` (сигнатура), `src/components/MarketplaceModule.jsx:177-341` (рендер)
- Create: `src/components/TradeModule.jsx`

**Interfaces:**
- Consumes: `TAB_ICONS`/`TAB_ACCENTS` не нужны здесь напрямую; использует `FarmBackground`, `TabAtmosphere`, `VineFrame`, `KutBalance`, `DonateModal`, `useContextualDonate` (`../hooks/useContextualDonate`), `usePlayerSync` (`../context/PlayerSyncContext`) — все уже существуют.
- Produces: `<GiveawaysModule isActive />`, `<TradeModule isActive segment onSegmentChange shopSearch shopItemId shopHighlightOnly onShopSearchUsed marketSearch marketItemId marketHighlightOnly onMarketSearchUsed />` — используются в задаче 4 внутри `App.jsx`. `<ExchangeModule embedded ... />` и `<MarketplaceModule embedded section="browse"|"sell" ... />` — используются только внутри `TradeModule`.

- [ ] **Step 1: Создать `GiveawaysModule.jsx`**

```jsx
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import VineFrame from './VineFrame'
import '../styles/giveaways.css'

export default function GiveawaysModule({ isActive = true }) {
  return (
    <div className="relative min-h-screen tab-theme-giveaways giveaways-module" aria-hidden={!isActive}>
      <FarmBackground />
      <TabAtmosphere variant="giveaways" />

      <div className="relative z-10 giveaways-shell py-4 pb-2 animate-slide-up">
        <header className="giveaways-header">
          <p className="giveaways-header-eyebrow">Cute</p>
          <h1 className="giveaways-header-title">Розыгрыши</h1>
        </header>

        <VineFrame className="giveaways-frame">
          <div className="giveaways-empty">
            <span className="giveaways-empty-icon" aria-hidden>🎁</span>
            <p>Скоро здесь появятся розыгрыши призов</p>
          </div>
        </VineFrame>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Добавить проп `embedded` в `ExchangeModule.jsx`**

В `src/components/ExchangeModule.jsx:25-31` заменить сигнатуру:

```jsx
export default function ExchangeModule({
  isActive = true,
  initialSearch = '',
  initialItemId = '',
  initialHighlightOnly = false,
  onSearchUsed,
}) {
```

на:

```jsx
export default function ExchangeModule({
  isActive = true,
  initialSearch = '',
  initialItemId = '',
  initialHighlightOnly = false,
  onSearchUsed,
  embedded = false,
}) {
```

В `src/components/ExchangeModule.jsx:133-151` заменить:

```jsx
  return (
    <div className="relative min-h-screen tab-theme-shop shop-exchange">
      <FarmBackground />
      <TabAtmosphere variant="shop" />

      <div className="relative z-10 shop-exchange-shell py-4 pb-2 animate-slide-up">
        <header className="shop-exchange-header">
          <div className="shop-exchange-header-main">
            <div>
              <p className="shop-exchange-eyebrow">Cute</p>
              <h1 className="shop-exchange-title">Магазин</h1>
            </div>
          </div>
          <KutBalance
            value={kut}
            className="shop-exchange-balance"
            onDonate={openDonate}
          />
        </header>

        <ShopSearch
```

на:

```jsx
  return (
    <div className={embedded ? 'relative shop-exchange' : 'relative min-h-screen tab-theme-shop shop-exchange'}>
      {!embedded && <FarmBackground />}
      {!embedded && <TabAtmosphere variant="shop" />}

      <div className={embedded ? 'relative z-10 shop-exchange-shell' : 'relative z-10 shop-exchange-shell py-4 pb-2 animate-slide-up'}>
        {!embedded && (
          <header className="shop-exchange-header">
            <div className="shop-exchange-header-main">
              <div>
                <p className="shop-exchange-eyebrow">Cute</p>
                <h1 className="shop-exchange-title">Магазин</h1>
              </div>
            </div>
            <KutBalance
              value={kut}
              className="shop-exchange-balance"
              onDonate={openDonate}
            />
          </header>
        )}

        <ShopSearch
```

Остальная часть файла (от `<ShopSearch` до закрывающих тегов) не меняется.

- [ ] **Step 3: Добавить пропы `embedded`/`section` в `MarketplaceModule.jsx`**

В `src/components/MarketplaceModule.jsx:34-40` заменить сигнатуру:

```jsx
export default function MarketplaceModule({
  isActive = true,
  initialSearch = '',
  initialItemId = '',
  initialHighlightOnly = false,
  onSearchUsed,
}) {
```

на:

```jsx
export default function MarketplaceModule({
  isActive = true,
  initialSearch = '',
  initialItemId = '',
  initialHighlightOnly = false,
  onSearchUsed,
  embedded = false,
  section = 'browse',
}) {
```

В `src/components/MarketplaceModule.jsx:177-341` заменить весь `return (...)` на:

```jsx
  return (
    <div className={embedded ? 'relative market-exchange' : 'relative min-h-screen tab-theme-market market-exchange'}>
      {!embedded && <FarmBackground />}
      {!embedded && <TabAtmosphere variant="market" />}

      <div className={embedded ? 'relative z-10 market-shell' : 'relative z-10 market-shell py-4 pb-2 animate-slide-up'}>
        {!embedded && (
          <header className="market-hero">
            <div className="market-hero-copy">
              <p className="market-hero-eyebrow">Игроки · торговля</p>
              <h1 className="market-hero-title">Биржа</h1>
            </div>
            <KutBalance
              value={kut}
              className="market-hero-balance"
              onDonate={openDonate}
            />
          </header>
        )}

        {actionMessage ? (
          <p className="market-toast market-toast-ok" role="status">
            {actionMessage}
          </p>
        ) : null}

        {error ? (
          <p className={`market-toast ${errorClass(errorCode)}`} role="alert">
            {error}
          </p>
        ) : null}

        {section === 'sell' && (
          <section className="market-sell-card" aria-label="Выставить предмет">
            <div className="market-sell-card-glow" aria-hidden />
            <div className="market-sell-card-content">
              <span className="market-sell-card-icon" aria-hidden>📤</span>
              <div className="market-sell-card-text">
                <p className="market-sell-card-title">Продать из рюкзака</p>
                <p className="market-sell-card-sub">Комиссия {commissionPercent}% при продаже · саженцы и вода запрещены</p>
              </div>
            </div>
            <button
              type="button"
              className="market-sell-card-btn"
              disabled={catalogBusy}
              onClick={openSell}
            >
              Выставить лот
            </button>
          </section>
        )}

        {section === 'browse' && (
          <>
            <div className="market-tools-row">
              <ShopSearch
                className="market-search"
                value={search}
                onChange={setSearch}
                disabled={catalogBusy && !search}
                placeholder="Искать лоты игроков…"
                ariaLabel="Поиск лотов на бирже"
              />
              <ShopToolbar
                className="market-toolbar"
                priceFilter={priceFilter}
                sortBy={sortBy}
                sortOrder={sortOrder}
                onPriceFilterChange={changePriceFilter}
                onSortChange={changeSort}
                disabled={catalogBusy}
              />
            </div>

            {!initialLoading && totalItems > 0 ? (
              <p className="market-lots-badge" role="status">
                <span className="market-lots-badge-dot" aria-hidden />
                {totalItems} {totalItems === 1 ? 'лот' : totalItems < 5 ? 'лота' : 'лотов'} на бирже
              </p>
            ) : null}

            <VineFrame className="market-board-frame">
              <section id="onboarding-market-board" className="market-board" aria-label="Лоты игроков">
                <div className={`market-board-showroom ${refreshing ? 'market-board-showroom-refresh' : ''}`}>
                  {initialLoading ? (
                    <ShopSkeletonGrid count={pageSize} gridClassName={gridClassName} />
                  ) : emptyCatalog ? (
                    <div className="market-board-empty">
                      <span className="market-board-empty-icon" aria-hidden>💱</span>
                      <p>{marketEmptyMessage(activeCategory, hasSearch)}</p>
                    </div>
                  ) : (
                    <div className={`market-shelf-grid ${gridClassName}`}>
                      {items.map((item) => (
                        <MarketShelfTile
                          key={item.id}
                          item={item}
                          kut={kut}
                          onSelect={setSelectedItem}
                          onOpenSellerProfile={setProfileUserId}
                          isBusy={busyListingId === item.id}
                          disabled={catalogBusy && busyListingId !== item.id}
                          isHighlighted={highlightItemId != null && String(highlightItemId) === String(item.itemId)}
                        />
                      ))}
                    </div>
                  )}
                </div>

                <ShopNavigation
                  className="market-nav"
                  sortFilters={sortFilters}
                  activeCategory={activeCategory}
                  page={page}
                  totalPages={totalPages}
                  totalItems={totalItems}
                  disabled={catalogBusy}
                  onSelectSort={selectSort}
                  onResetSort={resetSort}
                  onGoToPage={goToPage}
                  ariaLabel="Навигация по лотам"
                  categoriesLabel="Тип предмета"
                  allChipEmoji="💱"
                />
              </section>
            </VineFrame>
          </>
        )}
      </div>

      <MarketListingModal
        item={selectedItem}
        kut={kut}
        isOpen={Boolean(selectedItem)}
        isBusy={busyListingId === selectedItem?.id}
        commissionPercent={commissionPercent}
        onClose={() => setSelectedItem(null)}
        onConfirmBuy={handleBuy}
        onCancelListing={handleCancel}
        onOpenSellerProfile={setProfileUserId}
        onContextualDonate={(payload) => {
          openContextualDonate(payload)
          setSelectedItem(null)
        }}
      />

      <PlayerProfileModal
        userId={profileUserId}
        isOpen={Boolean(profileUserId)}
        onClose={() => setProfileUserId(null)}
      />

      <MarketSellModal
        items={sellableItems}
        isOpen={sellOpen}
        isLoading={sellableLoading}
        isBusy={listingBusy}
        error={sellableError}
        commissionPercent={commissionPercent}
        onClose={() => setSellOpen(false)}
        onConfirm={handleSell}
        onRetry={() => loadSellable().catch(() => {})}
      />

      <DonateModal
        isOpen={donateOpen}
        onClose={closeDonate}
        context={donateContext}
      />
    </div>
  )
}
```

Обрати внимание: тосты (`actionMessage`/`error`) переехали выше обоих условных блоков — теперь они видны независимо от активного сегмента (ошибка продажи должна быть видна в сегменте «Продать», ошибка покупки — в «Бирже»).

- [ ] **Step 4: Создать `TradeModule.jsx`**

```jsx
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import KutBalance from './KutBalance'
import DonateModal from './DonateModal'
import ExchangeModule from './ExchangeModule'
import MarketplaceModule from './MarketplaceModule'
import { useContextualDonate } from '../hooks/useContextualDonate'
import { usePlayerSync } from '../context/PlayerSyncContext'
import '../styles/trade.css'

const SEGMENTS = [
  { id: 'shop', label: 'Магазин' },
  { id: 'market', label: 'Биржа' },
  { id: 'sell', label: 'Продать' },
]

export default function TradeModule({
  isActive = true,
  segment,
  onSegmentChange,
  shopSearch = '',
  shopItemId = '',
  shopHighlightOnly = false,
  onShopSearchUsed,
  marketSearch = '',
  marketItemId = '',
  marketHighlightOnly = false,
  onMarketSearchUsed,
}) {
  const { kut } = usePlayerSync()
  const { donateOpen, donateContext, openDonate, closeDonate } = useContextualDonate()

  const theme = segment === 'shop' ? 'shop' : 'market'

  return (
    <div className={`relative min-h-screen tab-theme-${theme} trade-module`} aria-hidden={!isActive}>
      <FarmBackground />
      <TabAtmosphere variant={theme} />

      <div className="relative z-10 trade-shell py-4 pb-2 animate-slide-up">
        <header className="trade-header">
          <div className="trade-header-main">
            <p className="trade-header-eyebrow">Cute</p>
            <h1 className="trade-header-title">Торговля</h1>
          </div>
          <KutBalance value={kut ?? 0} className="trade-header-balance" onDonate={openDonate} />
        </header>

        <div className="trade-subtabs" role="tablist" aria-label="Разделы торговли">
          {SEGMENTS.map((s) => (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={segment === s.id}
              className={`trade-subtab${segment === s.id ? ' trade-subtab-active' : ''}`}
              onClick={() => onSegmentChange(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>

        {segment === 'shop' ? (
          <ExchangeModule
            embedded
            isActive={isActive}
            initialSearch={shopSearch}
            initialItemId={shopItemId}
            initialHighlightOnly={shopHighlightOnly}
            onSearchUsed={onShopSearchUsed}
          />
        ) : (
          <MarketplaceModule
            embedded
            section={segment === 'sell' ? 'sell' : 'browse'}
            isActive={isActive}
            initialSearch={marketSearch}
            initialItemId={marketItemId}
            initialHighlightOnly={marketHighlightOnly}
            onSearchUsed={onMarketSearchUsed}
          />
        )}
      </div>

      <DonateModal isOpen={donateOpen} onClose={closeDonate} context={donateContext} />
    </div>
  )
}
```

Обрати внимание: `MarketplaceModule` монтируется один раз и переиспользуется для сегментов `market` и `sell` (проп `section` просто переключается) — так каталог лотов не перезапрашивается заново при переключении Биржа↔Продать. При переключении на `shop` этот инстанс размонтируется и монтируется `ExchangeModule` — это ожидаемо и не требует доп. работы.

- [ ] **Step 5: Проверить сборку**

Run: `npm run build`
Expected: сборка проходит без ошибок. Ошибки здесь означали бы опечатку в JSX/пропах — внимательно перепроверь diff по `MarketplaceModule.jsx`/`ExchangeModule.jsx` построчно против шага 2/3 этой задачи.

- [ ] **Step 6: Прогнать юнит-тесты (regression-check)**

Run: `npx vitest run`
Expected: PASS — эта задача не трогает `src/utils/*`, но проверяем, что ничего не сломалось попутно.

- [ ] **Step 7: Commit**

```bash
git add src/components/GiveawaysModule.jsx src/components/ExchangeModule.jsx src/components/MarketplaceModule.jsx src/components/TradeModule.jsx
git commit -m "feat(webapp): build TradeModule hub and Giveaways placeholder"
```

---

## Task 4: Подключить «Торговлю»/«Розыгрыши» в навигацию, убрать «Ещё»

Это основная интеграционная задача — после неё приложение полностью рабочее с новой навигацией (Крафты/Настройки/Инвентарь пока без своих кнопок-входа на Ферме/в Профиле — это задача 5, но они остаются доступны, если явно выставить `tab` через `?startapp=craft`/`=settings`/`=inventory`, то есть ничего не удаляется, просто временно нет UI-входа).

**Files:**
- Modify: `src/App.jsx` (импорты, `AppWithOnboarding`, `AppShell`, обработчики, блок `<main>`)
- Modify: `src/components/TabBar.jsx` (полностью)
- Delete: `src/components/MoreMenu.jsx`
- Modify: `src/context/OnboardingContext.jsx:6-8,51,54`
- Modify: `src/hooks/useSwipeTabs.js:4`
- Modify: `src/index.css:1264` (грид), добавить блок после строки 1350
- Modify: `src/styles/tabThemes.css` (удалить мёртвые правила `shop`/`market` из блока «Нижняя панель вкладок»)

**Interfaces:**
- Consumes: `resolveStartTab` из `src/utils/tradeNav.js` (задача 1), `TradeModule`/`GiveawaysModule` (задача 3), `TAB_ICONS.trade`/`.giveaways` (задача 2).
- Produces: `tab` теперь принимает значения `'farm' | 'inventory' | 'craft' | 'quests' | 'trade' | 'giveaways' | 'chests' | 'profile' | 'settings'` (было + `'shop'`/`'market'` вместо `'trade'`). `FarmModule` получает новые пропы `onOpenInventory`/`onOpenCraft` (пока без реализации в `FarmHeader` — это задача 5, но проп уже должен приниматься без ошибок благодаря деструктуризации с дефолтом `undefined`). `ProfileModule` получает `onOpenSettings` (аналогично).

- [ ] **Step 1: Переписать `TabBar.jsx`**

Заменить весь файл `src/components/TabBar.jsx` на:

```jsx
import { useOnboardingOptional } from '../context/OnboardingContext'
import { useQuestBadge } from '../hooks/useQuests'
import { TAB_ACCENTS, TAB_ICONS } from './TabIcons'

const PRIMARY = [
  { id: 'farm', label: 'Ферма' },
  { id: 'trade', label: 'Торговля' },
  { id: 'giveaways', label: 'Розыгрыши' },
  { id: 'quests', label: 'Задания' },
  { id: 'profile', label: 'Профиль' },
]

export default function TabBar({ active, onChange }) {
  const onboarding = useOnboardingOptional()
  const pulseTab = onboarding?.pulseTab ?? null
  const questBadge = useQuestBadge()

  return (
    <nav className="app-tab-bar" aria-label="Разделы приложения">
      <div className="app-tab-bar-inner">
        {PRIMARY.map((tab) => {
          const isActive = active === tab.id
          const isPulsing = pulseTab === tab.id
          const TabIcon = TAB_ICONS[tab.id]
          const accent = TAB_ACCENTS[tab.id]
          const showBadge = tab.id === 'quests' && questBadge > 0 && !isActive
          return (
            <button
              key={tab.id}
              type="button"
              className={`app-tab-btn ${isActive ? 'app-tab-btn-active' : ''} ${isPulsing ? 'app-tab-btn-pulse' : ''} ${tab.id === 'giveaways' ? 'app-tab-btn-giveaways' : ''}`}
              data-onboarding-tab={tab.id}
              data-tab={tab.id}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => onChange(tab.id)}
              style={accent ? { '--tab-icon-strong': accent.strong, '--tab-icon-glow': accent.glow } : undefined}
            >
              <span className="app-tab-icon-wrap">
                <span className="app-tab-icon">{TabIcon && <TabIcon />}</span>
                {showBadge ? (
                  <span className="app-tab-badge" aria-label={`${questBadge} наград`}>
                    {questBadge > 9 ? '9+' : questBadge}
                  </span>
                ) : null}
              </span>
              <span className="app-tab-label">{tab.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
```

- [ ] **Step 2: Удалить `MoreMenu.jsx`**

```bash
git rm src/components/MoreMenu.jsx
```

- [ ] **Step 3: Обновить импорты в `App.jsx`**

В `src/App.jsx:4-28` заменить:

```jsx
import FarmModule from './components/FarmModule'
import CraftModule from './components/CraftModule'
import ExchangeModule from './components/ExchangeModule'
import MarketplaceModule from './components/MarketplaceModule'
import ChestModule from './components/ChestModule'
import InventoryModule from './components/InventoryModule'
import QuestsModule from './components/QuestsModule'
import SettingsModule from './components/SettingsModule'
import ProfileModule from './components/ProfileModule'
import TabBar from './components/TabBar'
import Onboarding from './components/Onboarding'
import BackgroundMusic from './components/BackgroundMusic'
import MaintenanceScreen from './components/MaintenanceScreen'
import AppLoadingScreen from './components/AppLoadingScreen'
import BannedScreen from './components/BannedScreen'
import SaleNotificationLayer from './components/SaleNotificationLayer'
import ShopPurchaseGuideLayer from './components/ShopPurchaseGuideLayer'
import MarketPurchaseGuideLayer from './components/MarketPurchaseGuideLayer'
import ItemGuideToastLayer from './components/ItemGuideToastLayer'
import { useEquippedCosmetics } from './hooks/useEquippedCosmetics'
import { useSwipeTabs } from './hooks/useSwipeTabs'
import { usePresencePing } from './hooks/usePresencePing'
import { syncSession } from './lib/sessionClient'
import { canAuthenticate, getStartTab } from './lib/telegram'
import { fetchAppStatus } from './lib/apiClient'
```

на:

```jsx
import FarmModule from './components/FarmModule'
import CraftModule from './components/CraftModule'
import TradeModule from './components/TradeModule'
import GiveawaysModule from './components/GiveawaysModule'
import ChestModule from './components/ChestModule'
import InventoryModule from './components/InventoryModule'
import QuestsModule from './components/QuestsModule'
import SettingsModule from './components/SettingsModule'
import ProfileModule from './components/ProfileModule'
import TabBar from './components/TabBar'
import Onboarding from './components/Onboarding'
import BackgroundMusic from './components/BackgroundMusic'
import MaintenanceScreen from './components/MaintenanceScreen'
import AppLoadingScreen from './components/AppLoadingScreen'
import BannedScreen from './components/BannedScreen'
import SaleNotificationLayer from './components/SaleNotificationLayer'
import ShopPurchaseGuideLayer from './components/ShopPurchaseGuideLayer'
import MarketPurchaseGuideLayer from './components/MarketPurchaseGuideLayer'
import ItemGuideToastLayer from './components/ItemGuideToastLayer'
import { useEquippedCosmetics } from './hooks/useEquippedCosmetics'
import { useSwipeTabs } from './hooks/useSwipeTabs'
import { usePresencePing } from './hooks/usePresencePing'
import { syncSession } from './lib/sessionClient'
import { canAuthenticate, getStartTab } from './lib/telegram'
import { resolveStartTab } from './utils/tradeNav'
import { fetchAppStatus } from './lib/apiClient'
```

- [ ] **Step 4: Обновить `AppWithOnboarding` — инициализация `tab`/`tradeSegment` через `resolveStartTab`**

В `src/App.jsx:105-113` заменить:

```jsx
function AppWithOnboarding() {
  const [tab, setTab] = useState(() => getStartTab() ?? 'farm')

  return (
    <OnboardingProvider activeTab={tab}>
      <AppShell tab={tab} setTab={setTab} />
    </OnboardingProvider>
  )
}
```

на:

```jsx
function AppWithOnboarding() {
  const [tab, setTab] = useState(() => resolveStartTab(getStartTab() ?? 'farm').tab)
  const [tradeSegment, setTradeSegment] = useState(() => resolveStartTab(getStartTab() ?? 'farm').tradeSegment)

  return (
    <OnboardingProvider activeTab={tab}>
      <AppShell
        tab={tab}
        setTab={setTab}
        tradeSegment={tradeSegment}
        setTradeSegment={setTradeSegment}
      />
    </OnboardingProvider>
  )
}
```

- [ ] **Step 5: Обновить сигнатуру `AppShell` и гайд-навигацию**

В `src/App.jsx:115` заменить:

```jsx
function AppShell({ tab, setTab }) {
```

на:

```jsx
function AppShell({ tab, setTab, tradeSegment, setTradeSegment }) {
```

В `src/App.jsx:126-138` заменить:

```jsx
  const handleGuideNavigateShop = useCallback((item) => {
    setShopSearch(item?.name ?? '')
    setShopItemId(item?.id ? String(item.id) : '')
    setShopHighlightOnly(true)
    setTab('shop')
  }, [setTab])

  const handleGuideNavigateMarket = useCallback((item) => {
    setMarketSearch(item?.name ?? '')
    setMarketItemId(item?.itemId ? String(item.itemId) : '')
    setMarketHighlightOnly(true)
    setTab('market')
  }, [setTab])
```

на:

```jsx
  const handleGuideNavigateShop = useCallback((item) => {
    setShopSearch(item?.name ?? '')
    setShopItemId(item?.id ? String(item.id) : '')
    setShopHighlightOnly(true)
    setTab('trade')
    setTradeSegment('shop')
  }, [setTab, setTradeSegment])

  const handleGuideNavigateMarket = useCallback((item) => {
    setMarketSearch(item?.name ?? '')
    setMarketItemId(item?.itemId ? String(item.itemId) : '')
    setMarketHighlightOnly(true)
    setTab('trade')
    setTradeSegment('market')
  }, [setTab, setTradeSegment])
```

- [ ] **Step 6: Обновить обработчики `farm:go-to-shop`/`farm:go-to-market`**

В `src/App.jsx:142-166` заменить оба `useEffect`:

```jsx
  useEffect(() => {
    const handler = (e) => {
      const search = e.detail?.search ?? ''
      const itemId = e.detail?.itemId ?? ''
      setShopSearch(search)
      setShopItemId(itemId ? String(itemId) : '')
      setShopHighlightOnly(Boolean(e.detail?.highlightOnly))
      setTab('shop')
    }
    window.addEventListener('farm:go-to-shop', handler)
    return () => window.removeEventListener('farm:go-to-shop', handler)
  }, [setTab])

  useEffect(() => {
    const handler = (e) => {
      const search = e.detail?.search ?? ''
      const itemId = e.detail?.itemId ?? ''
      setMarketSearch(search)
      setMarketItemId(itemId ? String(itemId) : '')
      setMarketHighlightOnly(Boolean(e.detail?.highlightOnly))
      setTab('market')
    }
    window.addEventListener('farm:go-to-market', handler)
    return () => window.removeEventListener('farm:go-to-market', handler)
  }, [setTab])
```

на:

```jsx
  useEffect(() => {
    const handler = (e) => {
      const search = e.detail?.search ?? ''
      const itemId = e.detail?.itemId ?? ''
      setShopSearch(search)
      setShopItemId(itemId ? String(itemId) : '')
      setShopHighlightOnly(Boolean(e.detail?.highlightOnly))
      setTab('trade')
      setTradeSegment('shop')
    }
    window.addEventListener('farm:go-to-shop', handler)
    return () => window.removeEventListener('farm:go-to-shop', handler)
  }, [setTab, setTradeSegment])

  useEffect(() => {
    const handler = (e) => {
      const search = e.detail?.search ?? ''
      const itemId = e.detail?.itemId ?? ''
      setMarketSearch(search)
      setMarketItemId(itemId ? String(itemId) : '')
      setMarketHighlightOnly(Boolean(e.detail?.highlightOnly))
      setTab('trade')
      setTradeSegment('market')
    }
    window.addEventListener('farm:go-to-market', handler)
    return () => window.removeEventListener('farm:go-to-market', handler)
  }, [setTab, setTradeSegment])
```

- [ ] **Step 7: Переписать блок `<main>`**

В `src/App.jsx:176-224` заменить весь блок от `<main className="app-main">` до `<TabBar active={tab} onChange={setTab} />` на:

```jsx
      <main className="app-main">
        <div className={tab === 'farm' ? '' : 'hidden'} aria-hidden={tab !== 'farm'}>
          <FarmModule
            isActive={tab === 'farm'}
            onOpenInventory={() => setTab('inventory')}
            onOpenCraft={() => setTab('craft')}
          />
        </div>
        <div className={tab === 'inventory' ? '' : 'hidden'} aria-hidden={tab !== 'inventory'}>
          <InventoryModule isActive={tab === 'inventory'} />
        </div>
        <div className={tab === 'craft' ? '' : 'hidden'} aria-hidden={tab !== 'craft'}>
          <CraftModule isActive={tab === 'craft'} />
        </div>
        <div className={tab === 'quests' ? '' : 'hidden'} aria-hidden={tab !== 'quests'}>
          <QuestsModule isActive={tab === 'quests'} />
        </div>
        <div className={tab === 'trade' ? '' : 'hidden'} aria-hidden={tab !== 'trade'}>
          <TradeModule
            isActive={tab === 'trade'}
            segment={tradeSegment}
            onSegmentChange={setTradeSegment}
            shopSearch={shopSearch}
            shopItemId={shopItemId}
            shopHighlightOnly={shopHighlightOnly}
            onShopSearchUsed={() => {
              setShopSearch('')
              setShopItemId('')
              setShopHighlightOnly(false)
            }}
            marketSearch={marketSearch}
            marketItemId={marketItemId}
            marketHighlightOnly={marketHighlightOnly}
            onMarketSearchUsed={() => {
              setMarketSearch('')
              setMarketItemId('')
              setMarketHighlightOnly(false)
            }}
          />
        </div>
        <div className={tab === 'giveaways' ? '' : 'hidden'} aria-hidden={tab !== 'giveaways'}>
          <GiveawaysModule isActive={tab === 'giveaways'} />
        </div>
        <div className={tab === 'chests' ? '' : 'hidden'} aria-hidden={tab !== 'chests'}>
          <ChestModule isActive={tab === 'chests'} />
        </div>
        <div className={tab === 'profile' ? '' : 'hidden'} aria-hidden={tab !== 'profile'}>
          <ProfileModule isActive={tab === 'profile'} onOpenSettings={() => setTab('settings')} />
        </div>
        <div className={tab === 'settings' ? '' : 'hidden'} aria-hidden={tab !== 'settings'}>
          <SettingsModule />
        </div>
      </main>
      <TabBar active={tab} onChange={setTab} />
```

- [ ] **Step 8: Обновить пульс-подсказку в `OnboardingContext.jsx`**

В `src/context/OnboardingContext.jsx:6-8` заменить комментарий:

```js
// После закрытия приветствия тихая подсказка-пульс на вкладке «Магазин»,
// сама гаснет по таймауту или как только игрок туда заходит.
```

на:

```js
// После закрытия приветствия тихая подсказка-пульс на вкладке «Торговля»,
// сама гаснет по таймауту или как только игрок туда заходит.
```

В `src/context/OnboardingContext.jsx:51` заменить:

```js
    if (shopHintActive && activeTab === 'shop') setShopHintActive(false)
```

на:

```js
    if (shopHintActive && activeTab === 'trade') setShopHintActive(false)
```

В `src/context/OnboardingContext.jsx:54` заменить:

```js
  const pulseTab = shopHintActive ? 'shop' : null
```

на:

```js
  const pulseTab = shopHintActive ? 'trade' : null
```

- [ ] **Step 9: Обновить порядок свайпа в `useSwipeTabs.js`**

В `src/hooks/useSwipeTabs.js:4` заменить:

```js
const TAB_ORDER = ['farm', 'inventory', 'craft', 'quests', 'shop', 'market', 'settings']
```

на:

```js
const TAB_ORDER = ['farm', 'trade', 'giveaways', 'quests', 'profile']
```

- [ ] **Step 10: Грид на 5 колонок и стиль приподнятой кнопки «Розыгрыши» в `index.css`**

В `src/index.css:1264` заменить:

```css
    grid-template-columns: repeat(4, minmax(0, 1fr));
```

на:

```css
    grid-template-columns: repeat(5, minmax(0, 1fr));
```

После блока `.app-tab-label {...}` (`src/index.css:1341-1350`), перед комментарием `/* Рюкзак */` (строка 1352), добавить:

```css
  .app-tab-btn-giveaways {
    transform: translateY(-0.55rem);
    padding-top: 0.5rem;
    padding-bottom: 0.4rem;
    border-radius: 999px;
    background: linear-gradient(180deg, rgba(80, 7, 36, 0.98) 0%, rgba(30, 4, 14, 0.98) 100%);
    box-shadow:
      inset 0 0 16px rgba(244, 114, 182, 0.22),
      0 0 18px rgba(244, 114, 182, 0.55),
      0 4px 14px rgba(0, 0, 0, 0.45);
  }

  .app-tab-btn-giveaways .app-tab-icon {
    width: 1.4rem;
    height: 1.4rem;
    color: #f9a8d4;
    filter: drop-shadow(0 0 6px rgba(244, 114, 182, 0.65));
  }

  .app-tab-btn-giveaways.app-tab-btn-active {
    background: linear-gradient(180deg, rgba(110, 10, 50, 0.98) 0%, rgba(40, 6, 20, 0.98) 100%);
  }
```

Обрати внимание: свечение `.app-tab-btn-giveaways` не зависит от `.app-tab-btn-active` — кнопка светится всегда, это и есть постоянный акцент «магнита» из спеки, без какой-либо логики таймера.

- [ ] **Step 11: Убрать мёртвые CSS-правила `shop`/`market` из нижней панели в `tabThemes.css`**

После этой задачи `tab` никогда не принимает значения `'shop'`/`'market'` (только `'trade'`), поэтому следующие правила в `src/styles/tabThemes.css` больше никогда не совпадут — удалить их:

```css
.app-shell[data-active-tab='shop'] .app-tab-bar-inner {
  background: linear-gradient(135deg, #fff4c4 0%, #d4a72c 38%, #fbbf24 68%, #4a3018 100%);
}

.app-shell[data-active-tab='market'] .app-tab-bar-inner {
  background: linear-gradient(135deg, #fde8d0 0%, #9a5f2a 35%, #cd9b5a 65%, #3d2314 100%);
}
```

```css
.app-shell[data-active-tab='shop'] .app-tab-btn-active {
  color: #fffbeb;
  box-shadow: inset 0 0 20px rgba(251, 191, 36, 0.2), 0 2px 8px rgba(0, 0, 0, 0.35);
}

.app-shell[data-active-tab='market'] .app-tab-btn-active {
  color: #fde8d0;
  box-shadow: inset 0 0 20px rgba(184, 115, 51, 0.22), 0 2px 8px rgba(0, 0, 0, 0.35);
}
```

```css
.app-tab-btn[data-tab='shop'].app-tab-btn-active .app-tab-icon {
  filter: drop-shadow(0 0 6px rgba(251, 191, 36, 0.55));
}

.app-tab-btn[data-tab='market'].app-tab-btn-active .app-tab-icon {
  filter: drop-shadow(0 0 6px rgba(205, 155, 90, 0.55));
}
```

(Правила для `craft`/`settings`/`inventory`/`chests` — **не трогать**, они по-прежнему нужны: эти табы остаются доступны через `tab`-state, просто без кнопки в баре.)

- [ ] **Step 12: Проверить сборку и юнит-тесты**

Run: `npm run build`
Expected: без ошибок.

Run: `npx vitest run`
Expected: PASS.

- [ ] **Step 13: Проверить в браузере**

Запустить дев-сервер (`preview_start` с конфигом `dev` из `.claude/launch.json`, команда `npm run dev`), открыть приложение и через `read_page`/`computer`:
1. Убедиться, что внизу 5 кнопок: Ферма, Торговля, Розыгрыши, Задания, Профиль — без кнопки «Ещё».
2. Кнопка «Розыгрыши» по центру визуально крупнее/приподнята и светится, даже если не активна.
3. Тап «Торговля» → открывается хаб с сегментами Магазин/Биржа/Продать; переключение между ними работает, каталог семян и лоты биржи отображаются как раньше.
4. Тап «Розыгрыши» → заглушка «Скоро здесь появятся розыгрыши призов».
5. Тап «Задания» и «Профиль» — работают как раньше (без визуальных регрессий).
6. Убедиться, что переход из фермы на биржу через существующую фичу «подскажи где купить предмет» (если легко воспроизводима вручную) по-прежнему открывает Торговлю на нужном сегменте с подсветкой предмета — если сложно воспроизвести вручную, хотя бы прочитать код `itemPurchaseGuide.js`/`ShopPurchaseGuideLayer.jsx`/`MarketPurchaseGuideLayer.jsx` ещё раз и убедиться, что `onNavigateShop`/`onNavigateMarket` теперь корректно вызывают `setTab('trade')`+`setTradeSegment(...)` (это уже сделано в Step 5, просто финальная сверка).

- [ ] **Step 14: Commit**

```bash
git add src/App.jsx src/components/TabBar.jsx src/context/OnboardingContext.jsx src/hooks/useSwipeTabs.js src/index.css src/styles/tabThemes.css
git rm src/components/MoreMenu.jsx
git commit -m "feat(webapp): wire trade/giveaways tabs into navigation, remove Ещё menu"
```

---

## Task 5: Точки входа в Инвентарь/Крафты (Ферма) и Настройки (Профиль)

**Files:**
- Modify: `src/components/FarmHeader.jsx` (полностью)
- Modify: `src/components/FarmModule.jsx:25` (сигнатура), `:255` (рендер `FarmHeader`)
- Modify: `src/components/ProfileModule.jsx` (импорт, сигнатура, хедер)
- Modify: `src/index.css` (новые блоки стилей)

**Interfaces:**
- Consumes: `TAB_ICONS.inventory`/`.craft`/`.settings` из `src/components/TabIcons.jsx` (уже существуют, не менялись).
- Produces: клик по иконке рюкзака/верстака на Ферме и по шестерёнке в Профиле вызывает `setTab('inventory' | 'craft' | 'settings')`, проброшенный из `App.jsx` (задача 4, Step 7).

- [ ] **Step 1: Добавить иконки-кнопки в `FarmHeader.jsx`**

Заменить весь файл `src/components/FarmHeader.jsx` на:

```jsx
import { TAB_ICONS } from './TabIcons'

export default function FarmHeader({ isPreview, onOpenInventory, onOpenCraft }) {
  const InventoryIcon = TAB_ICONS.inventory
  const CraftIcon = TAB_ICONS.craft

  return (
    <header className="farm-header text-center">
      <div className="farm-header-tools">
        <button type="button" className="farm-header-tool-btn" onClick={onOpenInventory} aria-label="Инвентарь">
          <InventoryIcon />
        </button>
        <button type="button" className="farm-header-tool-btn" onClick={onOpenCraft} aria-label="Крафты">
          <CraftIcon />
        </button>
      </div>

      <div className="farm-header-crest-wrap mx-auto">
        <div className="farm-header-crest-glow" aria-hidden />
        <img
          src="/assets/cute-crest.png?v=2"
          alt="Cute Farming"
          draggable={false}
          className="farm-header-crest-img"
        />
      </div>

      <div className="farm-header-titles">
        <p className="farm-header-cute farm-title-serif">CUTE</p>
        <h1 className="farm-header-title farm-title-serif">Фермерство</h1>
      </div>

      {isPreview && (
        <p className="farm-header-preview-badge">
          Превью UI без сервера
        </p>
      )}
    </header>
  )
}
```

- [ ] **Step 2: Пробросить пропы через `FarmModule.jsx`**

В `src/components/FarmModule.jsx:25` заменить:

```jsx
export default function FarmModule({ isActive = true }) {
```

на:

```jsx
export default function FarmModule({ isActive = true, onOpenInventory, onOpenCraft }) {
```

В `src/components/FarmModule.jsx:255` заменить:

```jsx
        <FarmHeader isPreview={isPreview} />
```

на:

```jsx
        <FarmHeader isPreview={isPreview} onOpenInventory={onOpenInventory} onOpenCraft={onOpenCraft} />
```

- [ ] **Step 3: Добавить кнопку настроек в `ProfileModule.jsx`**

В начало `src/components/ProfileModule.jsx` (после существующих импортов, рядом с `import { RARITY_ACCENT } from '../constants/chests'`) добавить:

```jsx
import { TAB_ICONS } from './TabIcons'
```

Заменить сигнатуру компонента:

```jsx
export default function ProfileModule({ isActive = true }) {
```

на:

```jsx
export default function ProfileModule({ isActive = true, onOpenSettings }) {
```

Внутри тела компонента, перед `return (`, добавить:

```jsx
  const SettingsIcon = TAB_ICONS.settings
```

Заменить хедер (`src/components/ProfileModule.jsx:108-116`):

```jsx
        <header className="profile-module-header">
          <div className="profile-module-header-main">
            <p className="profile-module-eyebrow">Игрок · статистика</p>
            <h1 className="profile-module-title">
              <span aria-hidden>👤</span> Профиль
            </h1>
          </div>
          {profile && <KutBalance value={profile.balance} className="profile-module-balance" />}
        </header>
```

на:

```jsx
        <header className="profile-module-header">
          <div className="profile-module-header-main">
            <p className="profile-module-eyebrow">Игрок · статистика</p>
            <h1 className="profile-module-title">
              <span aria-hidden>👤</span> Профиль
            </h1>
          </div>
          <div className="profile-module-header-actions">
            {profile && <KutBalance value={profile.balance} className="profile-module-balance" />}
            <button type="button" className="profile-settings-btn" onClick={onOpenSettings} aria-label="Настройки">
              <SettingsIcon />
            </button>
          </div>
        </header>
```

- [ ] **Step 4: Добавить CSS для кнопок на Ферме**

В `src/index.css:1039-1041` заменить:

```css
  .farm-header {
    margin-bottom: 0.85rem;
  }
```

на:

```css
  .farm-header {
    position: relative;
    margin-bottom: 0.85rem;
  }
```

После блока `.farm-header-preview-badge {...}` (`src/index.css:1102-1112`), перед `.maintenance-screen` (строка 1114), добавить:

```css
  .farm-header-tools {
    position: absolute;
    top: 0.4rem;
    right: 0.6rem;
    display: flex;
    gap: 0.4rem;
    z-index: 2;
  }

  .farm-header-tool-btn {
    display: grid;
    place-items: center;
    width: 2.1rem;
    height: 2.1rem;
    border-radius: 999px;
    border: 1px solid rgba(212, 175, 55, 0.32);
    background: linear-gradient(180deg, rgba(10, 24, 16, 0.92) 0%, rgba(6, 16, 10, 0.96) 100%);
    color: rgba(245, 230, 200, 0.75);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  .farm-header-tool-btn svg {
    width: 1.05rem;
    height: 1.05rem;
  }
```

- [ ] **Step 5: Добавить CSS для кнопки настроек в Профиле**

После блока `.profile-module-balance {...}` (`src/index.css:10578-10580`), перед `.profile-loading` (строка 10582), добавить:

```css
.profile-module-header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.profile-settings-btn {
  display: grid;
  place-items: center;
  width: 2.1rem;
  height: 2.1rem;
  flex-shrink: 0;
  border-radius: 999px;
  border: 1px solid var(--tab-chip-border, rgba(100, 116, 139, 0.28));
  background: linear-gradient(180deg, rgba(10, 24, 16, 0.92) 0%, rgba(6, 16, 10, 0.96) 100%);
  color: rgba(245, 230, 200, 0.75);
}

.profile-settings-btn svg {
  width: 1.05rem;
  height: 1.05rem;
}
```

- [ ] **Step 6: Проверить сборку**

Run: `npm run build`
Expected: без ошибок.

- [ ] **Step 7: Проверить в браузере**

Через `preview_start`/`read_page`/`computer`:
1. На вкладке «Ферма» в правом верхнем углу шапки — две круглые иконки (рюкзак, верстак).
2. Тап по рюкзаку → открывается Инвентарь (та же вкладка, что раньше открывалась из «Ещё»), тап «Ферма» в нижнем баре возвращает обратно.
3. Тап по верстаку → открывается Крафт, аналогично возвращается через «Ферма».
4. На вкладке «Профиль» в шапке справа — иконка-шестерёнка рядом с балансом.
5. Тап по шестерёнке → открываются Настройки, возврат через «Профиль» в нижнем баре.
6. Сделать скриншот шапки Фермы и шапки Профиля для финальной проверки.

- [ ] **Step 8: Commit**

```bash
git add src/components/FarmHeader.jsx src/components/FarmModule.jsx src/components/ProfileModule.jsx src/index.css
git commit -m "feat(webapp): add inventory/craft entry points on Farm and settings entry on Profile"
```

---

## Self-Review

**1. Spec coverage:**
- Новая нижняя панель из 5 табов (Ферма/Торговля/Розыгрыши/Задания/Профиль), «Ещё» убрано — Task 4. ✅
- Слияние Магазина+Биржи в «Торговлю» с сегментами Магазин/Биржа/Продать, без сегмента «Графики» — Task 3. ✅
- Deep-link совместимость (`?startapp=shop|market`, `farm:go-to-shop|market`) — Task 1 (алиас-логика) + Task 4 Step 5-6 (обработчики). ✅
- Инвентарь через иконку на Ферме — Task 5. ✅ (второй путь из спеки — сегмент «Продать» в Торговле — уже покрыт Task 3, ничего дополнительно делать не нужно, поскольку `sellableItems` и есть содержимое инвентаря, доступное для продажи).
- Крафты через иконку на Ферме — Task 5. ✅
- Настройки через иконку в Профиле — Task 5. ✅
- Розыгрыши — только заглушка, приподнятая акцентная кнопка в баре — Task 2 (иконка/тема) + Task 3 (компонент) + Task 4 (CSS приподнятой кнопки, подключение). ✅
- «Мои лоты» отдельным блоком не делаем (уже работает через `item.isMine` в `MarketShelfTile`/`MarketListingModal`) — сознательно не создавали лишнюю задачу под это, см. секцию «Продать»/«Биржа» в Task 3. ✅
- `chests`-таб не трогаем — нигде в плане не появляется. ✅

**2. Placeholder scan:** По всем задачам — код полный, без «TODO»/«implement later»/«similar to Task N». Комментарии в коде — только там, где объясняют неочевидное (переиспользование `MarketplaceModule` без ремонта, независимость свечения `.app-tab-btn-giveaways` от активного состояния).

**3. Type consistency:**
- `resolveStartTab` возвращает `{ tab, tradeSegment }` — везде далее (Task 4) деструктурируется именно так (`.tab`, `.tradeSegment`), совпадает.
- `TradeModule` пропы (`segment`, `onSegmentChange`, `shopSearch`/`shopItemId`/`shopHighlightOnly`/`onShopSearchUsed`, `marketSearch`/`marketItemId`/`marketHighlightOnly`/`onMarketSearchUsed`) — имена совпадают между определением компонента (Task 3) и вызовом в `App.jsx` (Task 4 Step 7).
- `MarketplaceModule` проп `section` — значения `'browse'`/`'sell'` совпадают между определением (Task 3, деструктуризация с дефолтом `'browse'`) и вызовом из `TradeModule` (`segment === 'sell' ? 'sell' : 'browse'`).
- `ExchangeModule`/`MarketplaceModule` проп `embedded` — используется одинаково (булево, дефолт `false`) в обоих файлах и при вызове из `TradeModule`.
- `FarmModule` пропы `onOpenInventory`/`onOpenCraft` — определены в Task 5 Step 2, используются в `App.jsx` Task 4 Step 7 (порядок: Task 4 уже передаёт эти пропы в `FarmModule`, хотя `FarmModule`/`FarmHeader` ещё не умеют их использовать до Task 5 — это безопасно: непринятый проп в React просто игнорируется, ошибок не будет; после Task 5 они начинают работать).
- `ProfileModule` проп `onOpenSettings` — аналогично: передаётся в Task 4, начинает использоваться в Task 5.
