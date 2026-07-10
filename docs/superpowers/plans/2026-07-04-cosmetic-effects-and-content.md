# Cosmetic Effects + Content + Chest UI Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make equipped cosmetics actually change the game (farm background, walking pet, plot skin, avatar frame + title), fill the catalog with themed content, show real items in the roulette, make the drop feed live, and add an item-detail sheet.

**Architecture:** Three phases over the existing chest feature (already in master). Phase 1 (backend): content overhaul + `description` column + `preview` in chest state + a `GET /api/cosmetics/equipped` endpoint. Phase 2 (UI): chest-tab reorder, non-empty roulette (fed by preview pool), live feed polling, item-detail BottomSheet. Phase 3 (effects): a `useEquippedCosmetics` hook whose data the farm/profile read to apply a background CSS variant, a walking `FarmPet`, plot skins, and avatar frame + title. All effects are emoji + CSS — no art assets.

**Tech Stack:** Python 3.11 / FastAPI / asyncpg / PostgreSQL (backend, no server test framework — pure-logic pytest only, DB via scratch verification); React 18 / Vite / vitest (frontend).

## Global Constraints

- Emoji + CSS only — no image assets in this round (spec §2, §8).
- Slots are exactly `background | pet | plot | frame | title`; rarities `common | rare | legendary`.
- "What an item does" is NEVER stored as text — it is derived from `slot` via a single client mapping so the description always matches real behavior (spec §4.2, §6.3).
- Equipping is one-active-per-slot (backend `set_equipped` already enforces this); equipping a slot auto-unequips the previous (spec §5).
- Effects apply immediately with no reload, via a `cosmetics:changed` window event that makes `useEquippedCosmetics` refetch (spec §6.4).
- Follow existing patterns: backend routes in `app.py` (`@app.get`/`@app.post` + `Depends(rate_limit)` + `try/except ValueError→_client_error / Exception→_server_error`); idempotent DDL (`ALTER ... ADD COLUMN IF NOT EXISTS`); idempotent seed (`ON CONFLICT DO NOTHING`); frontend uses `apiRequest`; user-facing strings Russian.
- Do NOT hard-delete cosmetics players may own — deactivate with `active=false` (spec §4.1).
- Local Postgres is up on 127.0.0.1:5432 (APP_MODE=test, dev user `6908672757`). venv `server/.venv/Scripts/python.exe`. Frontend: `npm run build`, `npm test`, `npm run dev`. Do NOT commit the user's pre-existing uncommitted files (`server/error_codes.py`, `server/error_reporter.py`, `src/lib/apiClient.js`) or `.pyc` artifacts.

---

## Phase 1 — Backend: content + description + preview + equipped endpoint

### Task 1: Content overhaul — description column, remove spring, themed series

**Files:**
- Modify: `server/schema.sql` (append one ALTER)
- Modify: `server/chest_db.py` (`_DDL`, `_SEED_SETS`, `_SEED_ITEMS`, `_seed_defaults`)

**Interfaces:**
- Produces: `cosmetic_items.description TEXT` column; a seeded catalog of ~30 active items across 5 sets + loose; the `spring` set and its items deactivated (`active=false`).

- [ ] **Step 1: Add the description column (schema.sql + _DDL)**

In `server/schema.sql`, after the `cosmetic_items` CREATE block, append:

```sql
ALTER TABLE cosmetic_items ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
```

In `server/chest_db.py`, add the same to the `_DDL` list (after the `cosmetic_items` CREATE string entry):

```python
    "ALTER TABLE cosmetic_items ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''",
```

- [ ] **Step 2: Replace the seed data**

In `server/chest_db.py`, replace `_SEED_SETS` and `_SEED_ITEMS` with the following. Items are `(code, name, emoji, slot, rarity, set_code, shard_cost, description)`:

```python
_SEED_SETS = [
    ("pets_myth", "🐉 Мифические питомцы", "title", "Укротитель"),
    ("cosmos", "🌌 Космос", "frame", "Звёздная"),
    ("seasons", "🍂 Времена года", "title", "Хранитель сезонов"),
    ("farm_lux", "🌾 Ферма-люкс", "title", "Фермер-магнат"),
    ("cuties", "🐱 Милашки", "title", "Друг зверушек"),
    # legacy: keep the row so old owners' FK stays valid, but deactivate below
    ("spring", "🌸 Весенняя серия", "frame", "Цветущий"),
]

# (code, name, emoji, slot, rarity, set_code, shard_cost, description)
_SEED_ITEMS = [
    # Мифические питомцы
    ("pet_dragon", "Дракон-хранитель", "🐉", "pet", "legendary", "pets_myth", 150, "Древний дракон, охраняющий твою ферму."),
    ("pet_unicorn", "Единорог", "🦄", "pet", "legendary", "pets_myth", 150, "Волшебный единорог с радужной гривой."),
    ("pet_wyvern", "Виверна", "🐲", "pet", "legendary", "pets_myth", 150, "Крылатая виверна, спутник героев."),
    ("pet_griffin", "Грифон", "🦅", "pet", "rare", "pets_myth", 40, "Гордый грифон — полулев, полуорёл."),
    ("pet_wolf", "Лунный волк", "🐺", "pet", "rare", "pets_myth", 40, "Волк, воющий на луну по ночам."),
    # Космос
    ("bg_galaxy", "Фон «Галактика»", "🌌", "background", "legendary", "cosmos", 150, "Звёздная галактика над твоей фермой."),
    ("bg_starfall", "Фон «Звездопад»", "🌠", "background", "rare", "cosmos", 40, "Падающие звёзды в ночном небе."),
    ("frame_orbit", "Рамка «Орбита»", "🪐", "frame", "rare", "cosmos", 40, "Планетарная рамка вокруг аватара."),
    ("title_cosmo", "Титул «Космонавт»", "☄️", "title", "rare", "cosmos", 40, "Для покорителей звёзд."),
    ("bg_night", "Фон «Ночь»", "🌙", "background", "common", "cosmos", 10, "Спокойная звёздная ночь."),
    # Времена года
    ("bg_sunset", "Фон «Закат»", "🌅", "background", "rare", "seasons", 40, "Тёплый закат над грядками."),
    ("bg_winter", "Фон «Зима»", "❄️", "background", "rare", "seasons", 40, "Снежная зимняя ферма."),
    ("bg_autumn", "Фон «Осень»", "🍂", "background", "common", "seasons", 10, "Золотая осень и листопад."),
    ("bg_spring2", "Фон «Весна»", "🌸", "background", "common", "seasons", 10, "Цветущая весенняя ферма."),
    # Ферма-люкс
    ("plot_gold", "Скин грядки «Золотая»", "🟨", "plot", "legendary", "farm_lux", 150, "Золотые грядки для магната."),
    ("plot_emerald", "Скин грядки «Изумруд»", "🟩", "plot", "rare", "farm_lux", 40, "Изумрудные грядки."),
    ("plot_oak", "Скин грядки «Дубовая»", "🟫", "plot", "common", "farm_lux", 10, "Крепкие дубовые грядки."),
    ("frame_vine", "Рамка «Лоза»", "🌿", "frame", "common", "farm_lux", 10, "Живая лоза вокруг аватара."),
    ("title_magnate", "Титул «Магнат»", "👑", "title", "legendary", "farm_lux", 150, "Для самых богатых фермеров."),
    # Милашки
    ("pet_cat", "Кот-садовник", "🐱", "pet", "rare", "cuties", 40, "Пушистый кот помогает на ферме."),
    ("pet_dog", "Щенок", "🐶", "pet", "common", "cuties", 10, "Весёлый щенок бегает по ферме."),
    ("pet_rabbit", "Кролик", "🐰", "pet", "common", "cuties", 10, "Милый кролик грызёт морковку."),
    ("pet_chick", "Цыплёнок", "🐥", "pet", "common", "cuties", 10, "Пушистый цыплёнок."),
    ("frame_bow", "Рамка «Бантик»", "🎀", "frame", "common", "cuties", 10, "Милая рамка с бантиком."),
    # Loose
    ("title_legend", "Титул «Легенда»", "🔥", "title", "legendary", None, 150, "Легенда фермерского дела."),
    ("frame_crystal", "Рамка «Кристалл»", "💎", "frame", "rare", None, 40, "Сверкающая кристальная рамка."),
    ("plot_sunflower", "Скин грядки «Подсолнух»", "🌻", "plot", "common", None, 10, "Солнечные грядки с подсолнухами."),
]

# Items to deactivate (legacy spring content, replaced by seasons)
_DEACTIVATE_ITEM_CODES = ["spring_flower", "spring_tulip", "spring_sun", "spring_bfly", "bg_sunset_old"]
_DEACTIVATE_SET_CODES = ["spring"]
```

- [ ] **Step 3: Update `_seed_defaults` to write description + deactivate legacy**

In `server/chest_db.py`, replace the item-insert loop and add deactivation. The `_seed_defaults` body becomes:

```python
async def _seed_defaults(conn) -> None:
    for code, name, rtype, rval in _SEED_SETS:
        await conn.execute(
            """INSERT INTO cosmetic_sets (code, name, reward_type, reward_value)
               VALUES ($1,$2,$3,$4) ON CONFLICT (code) DO NOTHING""",
            code, name, rtype, rval,
        )
    for code, name, emoji, slot, rarity, set_code, shard_cost, description in _SEED_ITEMS:
        await conn.execute(
            """INSERT INTO cosmetic_items
               (code, name, emoji, slot, rarity, set_code, shard_cost, description)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (code) DO NOTHING""",
            code, name, emoji, slot, rarity, set_code, shard_cost, description,
        )
    # Deactivate legacy spring content (do not delete — owners keep FK integrity)
    if _DEACTIVATE_ITEM_CODES:
        await conn.execute(
            "UPDATE cosmetic_items SET active=FALSE WHERE code = ANY($1::text[])",
            _DEACTIVATE_ITEM_CODES,
        )
    if _DEACTIVATE_SET_CODES:
        await conn.execute(
            "UPDATE cosmetic_sets SET active=FALSE WHERE code = ANY($1::text[])",
            _DEACTIVATE_SET_CODES,
        )
    await conn.execute(
        """INSERT INTO box_catalog (code, name, price_stars, pool, active)
           VALUES ($1,$2,$3,$4,TRUE) ON CONFLICT (code) DO NOTHING""",
        DEFAULT_BOX_CODE,
        "Косметический сундук",
        25,
        json.dumps({"rarity_weights": DEFAULT_RARITY_WEIGHTS,
                    "shard_values": DEFAULT_SHARD_VALUES}),
    )
```

> Note: the seed uses `ON CONFLICT DO NOTHING`, so on an existing DB the pre-existing `spring_*` items keep their rows (now deactivated by the UPDATE) and the new items get inserted. `bg_sunset` already existed as a loose item in the old seed — the new seed reuses code `bg_sunset` under the `seasons` set; since `ON CONFLICT DO NOTHING`, its set_code won't change on an already-seeded DB. To move it, the verify step below force-updates it once.

- [ ] **Step 4: One-time reconcile for the pre-existing `bg_sunset`**

Add to `_seed_defaults`, right before the `box_catalog` insert, a targeted update so the previously-loose `bg_sunset` joins the seasons set and gains a description (safe + idempotent):

```python
    await conn.execute(
        """UPDATE cosmetic_items
           SET set_code='seasons', description='Тёплый закат над грядками.'
           WHERE code='bg_sunset' AND (set_code IS NULL OR set_code <> 'seasons')""",
    )
```

- [ ] **Step 5: Verify against live DB**

Scratch `server/_scratch_content.py`:

```python
import asyncio, db, chest_db
async def main():
    await db.db.connect()
    await chest_db.ensure_tables()
    async with db.db.pool.acquire() as c:
        active = await c.fetchval("SELECT count(*) FROM cosmetic_items WHERE active")
        spring = await c.fetchval("SELECT count(*) FROM cosmetic_items WHERE set_code='spring' AND active")
        desc = await c.fetchval("SELECT count(*) FROM cosmetic_items WHERE active AND description<>''")
        slots = await c.fetch("SELECT slot, count(*) FROM cosmetic_items WHERE active GROUP BY slot ORDER BY slot")
    print("active items:", active, "| active spring:", spring, "| with description:", desc)
    print("by slot:", [(r['slot'], r['count']) for r in slots])
    await db.db.close()
asyncio.run(main())
```

Run: `cd server && .venv/Scripts/python.exe _scratch_content.py`
Expected: `active items` ≈ 28 (27 new + reconciled bg_sunset), `active spring` = 0, `with description` = all active, and `by slot` shows background/pet/plot/frame/title all present. Delete the scratch file.

- [ ] **Step 6: Commit**

```bash
git add server/schema.sql server/chest_db.py
git commit -m "feat(cosmetics): content overhaul — descriptions, themed series, deactivate spring"
```

---

### Task 2: `preview` pool in chest state

**Files:**
- Modify: `server/chest_db.py` (`get_chest_state`)

**Interfaces:**
- Produces: `get_chest_state` return dict gains `preview: [{"emoji": str, "rarity": str}, ...]` — up to ~16 active catalog items (mixed rarities) for the roulette to render.

- [ ] **Step 1: Add a preview query and include it in the state**

In `server/chest_db.py`, add a helper and extend `get_chest_state`:

```python
async def _preview_items(conn, limit: int = 16) -> list[dict]:
    rows = await conn.fetch(
        """SELECT emoji, rarity FROM cosmetic_items
           WHERE active ORDER BY random() LIMIT $1""",
        limit)
    return [{"emoji": r["emoji"], "rarity": r["rarity"]} for r in rows]
```

In `get_chest_state`, inside the `async with db.pool.acquire() as conn:` block, after computing `shards`, add `preview = await _preview_items(conn)` and include `"preview": preview` in the returned dict.

- [ ] **Step 2: Verify**

Scratch `server/_scratch_preview.py`:

```python
import asyncio, db, chest_db
async def main():
    await db.db.connect()
    st = await chest_db.get_chest_state(6908672757)
    print("preview count:", len(st["preview"]))
    print("sample:", st["preview"][:5])
    await db.db.close()
asyncio.run(main())
```

Run: `cd server && .venv/Scripts/python.exe _scratch_preview.py`
Expected: `preview count: 16` (or number of active items if fewer), each entry `{emoji, rarity}`. Delete scratch.

- [ ] **Step 3: Commit**

```bash
git add server/chest_db.py
git commit -m "feat(chests): preview item pool in chest state"
```

---

### Task 3: `get_equipped` + `GET /api/cosmetics/equipped`

**Files:**
- Modify: `server/chest_db.py` (add `get_equipped`)
- Modify: `server/app.py` (add route)

**Interfaces:**
- Produces:
  - `async def get_equipped(user_id: int) -> dict` → `{slot: {"code","emoji","name"} | None}` for slots `background,pet,plot,frame,title` (one active per slot).
  - `GET /api/cosmetics/equipped` returning that dict.

- [ ] **Step 1: Add `get_equipped` to chest_db.py**

```python
EQUIP_SLOTS = ("background", "pet", "plot", "frame", "title")


async def get_equipped(user_id: int) -> dict:
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ci.slot, ci.code, ci.emoji, ci.name
               FROM user_cosmetics uc
               JOIN cosmetic_items ci ON ci.id = uc.cosmetic_id
               WHERE uc.user_id=$1 AND uc.equipped AND ci.active""",
            user_id)
    by_slot = {s: None for s in EQUIP_SLOTS}
    for r in rows:
        if r["slot"] in by_slot:
            by_slot[r["slot"]] = {"code": r["code"], "emoji": r["emoji"], "name": r["name"]}
    return by_slot
```

- [ ] **Step 2: Add the route in app.py**

Near the other chest routes (before `@app.get("/api/me")`), add:

```python
@app.get("/api/cosmetics/equipped")
async def cosmetics_equipped(request: Request, user_id: int = Depends(rate_limit)):
    import chest_db
    try:
        return await chest_db.get_equipped(user_id)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)
```

- [ ] **Step 3: Verify end-to-end**

Start the API (`cd server && .venv/Scripts/python.exe -m uvicorn app:app --port 8000`). Then, with a dev user that has something equipped (equip via the UI or set `user_cosmetics.equipped=true` for one row):

```bash
curl -s http://127.0.0.1:8000/api/cosmetics/equipped -H "X-Dev-User-Id: 6908672757"
```

Expected: JSON with keys `background,pet,plot,frame,title`, each `null` or `{code,emoji,name}`. Stop the server.

- [ ] **Step 4: Commit**

```bash
git add server/chest_db.py server/app.py
git commit -m "feat(cosmetics): equipped-per-slot endpoint"
```

---

## Phase 2 — UI polish

### Task 4: Roulette on top + fed by preview + live feed polling

**Files:**
- Modify: `src/components/ChestModule.jsx` (reorder; pass preview as pool)
- Modify: `src/hooks/useChests.js` (feed polling)

**Interfaces:**
- Consumes: `state.preview` (Task 2).
- Produces: chest section renders roulette above the feed; roulette `pool` = `state.preview`; feed refreshes on an interval while active.

- [ ] **Step 1: Reorder + feed the roulette pool in ChestModule**

In `src/components/ChestModule.jsx`, in the `section === 'chest'` block: move `<ChestFeed feed={feed} />` to render AFTER `<ChestRoulette .../>` (roulette first). Change the roulette's `pool` from the current `null`/`pool` to `state?.preview || []`:

```jsx
          <ChestRoulette result={revealResult} pool={state?.preview || []} spinning={spinning} onDone={handleRouletteDone} />
          <ChestFeed feed={feed} />
```

(Remove the now-unused `const pool = null` line if present.)

- [ ] **Step 2: Live feed polling in useChests**

In `src/hooks/useChests.js`, add an effect that polls the feed every 12s while active. After the existing initial-load effect, add:

```js
  useEffect(() => {
    if (!isActive) return undefined
    const id = setInterval(() => { refreshFeed() }, 12000)
    return () => clearInterval(id)
  }, [isActive, refreshFeed])
```

- [ ] **Step 3: Verify (build + visual)**

`npm run build` passes. `npm run dev`, open Сундуки: confirm the roulette sits ABOVE "🔥 Только что выбили", the idle roulette shows drifting items (not empty), and opening still lands correctly. Leave the tab open ~15s and confirm the feed refreshes (a new rare/legendary drop from another action appears without manual reload — you can force one by opening chests).

- [ ] **Step 4: Commit**

```bash
git add src/components/ChestModule.jsx src/hooks/useChests.js
git commit -m "feat(chests-ui): roulette on top, fed by preview pool, live feed polling"
```

---

### Task 5: Item-detail BottomSheet (what it is / does / equip-unequip) + effect mapping + cosmetics:changed

**Files:**
- Modify: `src/constants/chests.js` (add `SLOT_EFFECT`)
- Modify: `src/components/ChestCollection.jsx` (detail sheet; emit `cosmetics:changed`)

**Interfaces:**
- Produces: `SLOT_EFFECT` mapping; a detail BottomSheet on item tap with description + effect + Поставить/Снять/Купить; a `window` `cosmetics:changed` event dispatched after equip/unequip/buy.

- [ ] **Step 1: Add the slot→effect mapping**

In `src/constants/chests.js`, add:

```js
export const SLOT_EFFECT = {
  background: 'Меняет фон фермы',
  pet: 'Питомец будет ходить по твоей ферме',
  plot: 'Меняет вид грядок',
  frame: 'Рамка вокруг аватара в профиле',
  title: 'Титул в профиле (виден другим)',
}
```

- [ ] **Step 2: Detail sheet + equip/unequip + event in ChestCollection**

In `src/components/ChestCollection.jsx`:
- Import `BottomSheet` (already imported for the buy sheet) and `SLOT_EFFECT`, `RARITY_LABEL` from constants.
- Change item tap: instead of directly toggling equip / opening buy, set `setSelected(item)` for ALL items (owned or not), and render ONE detail `BottomSheet` for the selected item showing: big emoji (use the existing glow-wrapped emoji style), name, rarity label, `description` (from `item.description` — ensure the collection API returns it; if not present in the item shape, it is available because `get_collection` selects from `cosmetic_items` — add `description` to that SELECT and to `_item_public` in a tiny backend follow-up IF missing; verify first), the effect line `SLOT_EFFECT[item.slot]` with the emoji, and the action:
  - not owned → «Купить за {shardCost} осколков» (disabled + «Не хватает осколков» when `data.shards < shardCost`) → calls existing `doBuy`.
  - owned & not equipped → «Поставить» → `doEquip(item, true)`.
  - owned & equipped → «Снять» → `doEquip(item, false)`.
- After a successful `doBuy`/`doEquip`, dispatch `window.dispatchEvent(new Event('cosmetics:changed'))` (in addition to the existing `load()`/`onChanged()`), then close the sheet.

> Backend note: confirm `get_collection`'s item shape includes `description`. If it does not, add `description` to the `SELECT` in `get_collection` and to `_item_public` in `server/chest_db.py` (one-line each) and reseed — do this as the first sub-step and commit it with this task.

Concrete detail-sheet JSX (inside the component's return, replacing the old buy-only sheet):

```jsx
{selected && (
  <BottomSheet isOpen={!!selected} onClose={() => setSelected(null)} title={selected.name} showApply={false}>
    <div className="chest-detail">
      <div className="chest-detail-emoji-wrap"><span className="chest-detail-emoji">{selected.emoji}</span></div>
      <div className="chest-detail-rarity" style={{ color: RARITY_ACCENT[selected.rarity] }}>{RARITY_LABEL[selected.rarity]}</div>
      {selected.description ? <p className="chest-detail-desc">{selected.description}</p> : null}
      <p className="chest-detail-effect">✨ {SLOT_EFFECT[selected.slot] || ''}</p>
      {!selected.owned ? (
        <button className="farm-btn-primary chest-detail-btn" disabled={busy || data.shards < selected.shardCost}
          onClick={() => doBuyAndClose(selected)}>
          {data.shards < selected.shardCost ? 'Не хватает осколков' : `Купить за ${selected.shardCost} осколков`}
        </button>
      ) : selected.equipped ? (
        <button className="farm-btn-primary chest-detail-btn" disabled={busy} onClick={() => doEquipAndClose(selected, false)}>Снять</button>
      ) : (
        <button className="farm-btn-primary chest-detail-btn" disabled={busy} onClick={() => doEquipAndClose(selected, true)}>Поставить</button>
      )}
    </div>
  </BottomSheet>
)}
```

Add helper wrappers near `doBuy`/`doEquip`:

```jsx
const emitChanged = () => window.dispatchEvent(new Event('cosmetics:changed'))
const doBuyAndClose = async (item) => { await doBuy(item); emitChanged() }
const doEquipAndClose = async (item, val) => { await doEquip(item, val); emitChanged(); setSelected(null) }
```

(Ensure `RARITY_ACCENT` is imported; make item buttons call `setSelected(item)`.)

- [ ] **Step 3: Add detail-sheet styles**

Append to `src/styles/chests.css`:

```css
.chest-detail { text-align:center; padding:8px 4px 16px; }
.chest-detail-emoji-wrap { position:relative; display:inline-flex; align-items:center; justify-content:center; margin:4px 0; }
.chest-detail-emoji-wrap::before { content:""; position:absolute; inset:-14px; border-radius:50%;
  background:radial-gradient(circle, rgba(255,224,130,.55), rgba(255,224,130,0) 70%); filter:blur(6px); z-index:0; }
.chest-detail-emoji { position:relative; z-index:1; font-size:80px; }
.chest-detail-rarity { font-weight:800; font-size:13px; letter-spacing:1px; }
.chest-detail-desc { font-size:13px; color:#6b5a3c; margin:8px 12px; }
.chest-detail-effect { font-size:13px; font-weight:700; color:#a9791b; margin:6px 12px 12px; }
.chest-detail-btn { width:calc(100% - 24px); margin:0 12px; }
```

- [ ] **Step 4: Verify**

`npm run build`; `npm run dev` → Сундуки → Коллекция. Tap an OWNED item → sheet shows name/rarity/description/effect + «Поставить»; tap → becomes «Снять» on reopen. Tap a LOCKED item with enough shards → «Купить …»; buy works. Confirm a `cosmetics:changed` event fires (temporarily `window.addEventListener('cosmetics:changed', ()=>console.log('changed'))` in the console).

- [ ] **Step 5: Commit**

```bash
git add src/constants/chests.js src/components/ChestCollection.jsx src/styles/chests.css server/chest_db.py
git commit -m "feat(chests-ui): item-detail sheet with description, effect, equip/unequip"
```

---

## Phase 3 — Effects: equipped cosmetics change the game

### Task 6: `useEquippedCosmetics` hook + client

**Files:**
- Modify: `src/lib/chestClient.js` (add `fetchEquipped`)
- Create: `src/hooks/useEquippedCosmetics.js`

**Interfaces:**
- Produces:
  - `fetchEquipped()` → GET `/api/cosmetics/equipped`.
  - `useEquippedCosmetics()` → returns `{ equipped, refresh }` where `equipped` = `{background,pet,plot,frame,title}` (each `{code,emoji,name}|null`); auto-loads on mount and refetches on the `cosmetics:changed` window event.

- [ ] **Step 1: Add the client function**

In `src/lib/chestClient.js`:

```js
export function fetchEquipped() {
  return apiRequest('/api/cosmetics/equipped')
}
```

- [ ] **Step 2: Create the hook**

Create `src/hooks/useEquippedCosmetics.js`:

```js
import { useCallback, useEffect, useState } from 'react'
import { fetchEquipped } from '../lib/chestClient'

const EMPTY = { background: null, pet: null, plot: null, frame: null, title: null }

export function useEquippedCosmetics() {
  const [equipped, setEquipped] = useState(EMPTY)

  const refresh = useCallback(async () => {
    try { setEquipped(await fetchEquipped()) } catch { /* best-effort; keep prior */ }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    const handler = () => refresh()
    window.addEventListener('cosmetics:changed', handler)
    return () => window.removeEventListener('cosmetics:changed', handler)
  }, [refresh])

  return { equipped, refresh }
}
```

- [ ] **Step 3: Verify build**

`npm run build` passes (no unit test — glue over the tested client; exercised by the effect tasks).

- [ ] **Step 4: Commit**

```bash
git add src/lib/chestClient.js src/hooks/useEquippedCosmetics.js
git commit -m "feat(cosmetics): useEquippedCosmetics hook"
```

---

### Task 7: Farm background variant

**Files:**
- Modify: `src/components/FarmBackground.jsx` (accept `variant` prop)
- Modify: `src/components/FarmModule.jsx` (read equipped.background, pass variant)
- Modify: `src/styles` (background variant overlays — put in the farm CSS file or a new `src/styles/cosmetic-effects.css` imported by FarmModule)

**Interfaces:**
- Consumes: `useEquippedCosmetics().equipped.background.code`.
- Produces: `<FarmBackground variant={code} />` applies a CSS overlay class `farm-bg--{code}`.

- [ ] **Step 1: FarmBackground accepts variant**

Read `src/components/FarmBackground.jsx`. Change the signature to `export default function FarmBackground({ variant = null })` and add `variant && \`farm-bg--${variant}\`` to the root element's className (the `.farm-bg-root` div). Add a single overlay child at the end of the root (before closing div): `<div className="farm-bg-cosmetic-overlay" aria-hidden />`.

- [ ] **Step 2: FarmModule passes the equipped background**

Read `src/components/FarmModule.jsx`. Import `useEquippedCosmetics`, call it, and change the `<FarmBackground />` render to `<FarmBackground variant={equipped.background?.code || null} />`. (If FarmModule uses `FarmBackground` indirectly, pass the variant down.)

- [ ] **Step 3: Add the variant overlay CSS**

Create `src/styles/cosmetic-effects.css` (import it at the top of `FarmModule.jsx`):

```css
/* Cosmetic background variants — a tint overlay over the farm scene */
.farm-bg-cosmetic-overlay { position:absolute; inset:0; z-index:-1; pointer-events:none; opacity:0; transition:opacity .4s; }
.farm-bg--bg_sunset  .farm-bg-cosmetic-overlay { opacity:1; background:linear-gradient(180deg, rgba(255,140,60,.28), rgba(255,90,120,.18)); }
.farm-bg--bg_night   .farm-bg-cosmetic-overlay { opacity:1; background:linear-gradient(180deg, rgba(10,20,60,.45), rgba(20,10,50,.35)); }
.farm-bg--bg_winter  .farm-bg-cosmetic-overlay { opacity:1; background:linear-gradient(180deg, rgba(150,200,255,.28), rgba(200,230,255,.20)); }
.farm-bg--bg_autumn  .farm-bg-cosmetic-overlay { opacity:1; background:linear-gradient(180deg, rgba(200,120,40,.25), rgba(160,80,30,.18)); }
.farm-bg--bg_spring2 .farm-bg-cosmetic-overlay { opacity:1; background:linear-gradient(180deg, rgba(255,180,220,.22), rgba(180,255,180,.16)); }
.farm-bg--bg_galaxy  .farm-bg-cosmetic-overlay { opacity:1; background:radial-gradient(circle at 30% 20%, rgba(120,60,200,.4), rgba(10,10,40,.5)); }
.farm-bg--bg_starfall .farm-bg-cosmetic-overlay { opacity:1; background:linear-gradient(180deg, rgba(30,20,80,.4), rgba(10,10,40,.3)); }
```

- [ ] **Step 4: Verify visually**

`npm run build`; `npm run dev`. Equip «Фон Закат» in Коллекция, go to Ферма → confirm a warm sunset tint overlays the scene. Equip «Ночь» → dark-blue tint. Unequip → tint gone. Switching applies without reload (via `cosmetics:changed`).

- [ ] **Step 5: Commit**

```bash
git add src/components/FarmBackground.jsx src/components/FarmModule.jsx src/styles/cosmetic-effects.css
git commit -m "feat(effects): equipped background tints the farm scene"
```

---

### Task 8: Walking farm pet

**Files:**
- Create: `src/components/FarmPet.jsx`
- Modify: `src/components/FarmModule.jsx` (render FarmPet when a pet is equipped)
- Modify: `src/styles/cosmetic-effects.css` (walking animation)

**Interfaces:**
- Consumes: `useEquippedCosmetics().equipped.pet.emoji`.
- Produces: `<FarmPet emoji={...} />` — an emoji that walks left/right along the bottom of the farm.

- [ ] **Step 1: Create FarmPet**

Create `src/components/FarmPet.jsx`:

```jsx
export default function FarmPet({ emoji }) {
  if (!emoji) return null
  return (
    <div className="farm-pet" aria-hidden>
      <span className="farm-pet-glyph">{emoji}</span>
    </div>
  )
}
```

- [ ] **Step 2: Render it in FarmModule**

In `src/components/FarmModule.jsx`, where the farm scene content renders (near FarmBackground / inside the farm container), add `{equipped.pet && <FarmPet emoji={equipped.pet.emoji} />}` (import FarmPet). Reuse the `equipped` from Task 7's `useEquippedCosmetics()` call.

- [ ] **Step 3: Walking animation CSS**

Append to `src/styles/cosmetic-effects.css`:

```css
.farm-pet { position:fixed; bottom:78px; left:0; z-index:5; pointer-events:none;
  animation: farm-pet-walk 16s linear infinite; }
.farm-pet-glyph { display:inline-block; font-size:34px; animation: farm-pet-bob .6s ease-in-out infinite; }
@keyframes farm-pet-walk {
  0%   { transform: translateX(8vw) scaleX(1); }
  49%  { transform: translateX(82vw) scaleX(1); }
  50%  { transform: translateX(82vw) scaleX(-1); }
  99%  { transform: translateX(8vw) scaleX(-1); }
  100% { transform: translateX(8vw) scaleX(1); }
}
@keyframes farm-pet-bob { 0%,100%{ transform:translateY(0) } 50%{ transform:translateY(-4px) } }
```

> `bottom:78px` keeps the pet above the tab bar; adjust if it overlaps by checking the running app. Keep it out of the way of plot interaction (pointer-events:none).

- [ ] **Step 4: Verify**

`npm run build`; `npm run dev`. Equip a pet (e.g. 🐱), go to Ферма → the emoji walks left↔right along the bottom, flipping direction, bobbing. Unequip → it disappears. Confirm it doesn't block tapping plots.

- [ ] **Step 5: Commit**

```bash
git add src/components/FarmPet.jsx src/components/FarmModule.jsx src/styles/cosmetic-effects.css
git commit -m "feat(effects): equipped pet walks along the farm"
```

---

### Task 9: Plot skin

**Files:**
- Modify: `src/components/FarmModule.jsx` or `src/components/PlotCard.jsx` (apply plot skin class)
- Modify: `src/styles/cosmetic-effects.css` (plot skin styles)

**Interfaces:**
- Consumes: `useEquippedCosmetics().equipped.plot.code`.
- Produces: plots get class `plot-skin--{code}` when a plot skin is equipped.

- [ ] **Step 1: Apply the skin class**

Read `src/components/PlotCard.jsx` and `src/components/FarmModule.jsx`. Decide the smallest place to inject the class: if the plots grid container is in FarmModule, add `className={... (equipped.plot ? \`plot-skin--${equipped.plot.code}\` : '')}` to the grid wrapper (so a descendant selector styles the plots). If each plot is a `PlotCard`, pass a `skin={equipped.plot?.code}` prop and add the class on the card root. Choose the grid-wrapper approach if plots are mapped inside FarmModule (fewer touch points).

- [ ] **Step 2: Plot skin CSS**

Append to `src/styles/cosmetic-effects.css` (selectors target the plot tiles — adjust the inner class to the actual plot element class you find, e.g. `.plot-card` / `.farm-plot`):

```css
/* Plot skins — recolor the plot tile border/soil. Replace `.plot-card` with the real plot element class. */
.plot-skin--plot_gold      .plot-card { border-color:#e6b422 !important; box-shadow:0 0 8px rgba(230,180,34,.5); }
.plot-skin--plot_emerald   .plot-card { border-color:#3fbf7f !important; box-shadow:0 0 8px rgba(63,191,127,.4); }
.plot-skin--plot_oak       .plot-card { border-color:#8B5A2B !important; }
.plot-skin--plot_sunflower .plot-card { border-color:#f2c94c !important; box-shadow:0 0 8px rgba(242,201,76,.4); }
```

> Inspect the real plot element's class in `PlotCard.jsx` and substitute it for `.plot-card` in all four selectors. If plots have a fixed border set inline, override with the same specificity.

- [ ] **Step 3: Verify**

`npm run build`; `npm run dev`. Equip «Скин грядки Золотая» → farm plots get a gold border/glow. Equip «Изумруд» → green. Unequip → back to default.

- [ ] **Step 4: Commit**

```bash
git add src/components/FarmModule.jsx src/components/PlotCard.jsx src/styles/cosmetic-effects.css
git commit -m "feat(effects): equipped plot skin recolors farm plots"
```

---

### Task 10: Avatar frame + title in profile

**Files:**
- Modify: `src/components/ProfileModule.jsx` (frame around avatar + title text from equipped)
- Modify: `src/styles/cosmetic-effects.css` (frame/title styles)

**Interfaces:**
- Consumes: `useEquippedCosmetics().equipped.frame`, `.title`.
- Produces: the profile avatar shows the equipped frame emoji as a ring/badge; the equipped title renders as a labeled text under the name.

- [ ] **Step 1: Read ProfileModule and integrate**

Read `src/components/ProfileModule.jsx`. It already has a "Витрина" showcase (added earlier) and calls `fetchCollection`. Add `useEquippedCosmetics()` and render, near the avatar/name block:
- Frame: if `equipped.frame`, wrap or overlay the avatar with a frame element showing `equipped.frame.emoji` (e.g. a corner badge or a ring of the emoji). Keep it simple: a small badge `<span className="profile-frame-badge">{equipped.frame.emoji}</span>` positioned on the avatar, plus a class `profile-avatar--framed`.
- Title: if `equipped.title`, render `<div className="profile-title-chip">{equipped.title.emoji} {equipped.title.name}</div>` under the player name.

Concrete additions (adapt to the actual avatar/name markup you find):

```jsx
// near the top of the component body:
const { equipped } = useEquippedCosmetics()
// in the avatar block:
{equipped.frame && <span className="profile-frame-badge" aria-hidden>{equipped.frame.emoji}</span>}
// under the name:
{equipped.title && <div className="profile-title-chip">{equipped.title.emoji} {equipped.title.name}</div>}
```

- [ ] **Step 2: Styles**

Append to `src/styles/cosmetic-effects.css`:

```css
.profile-frame-badge { position:absolute; bottom:-4px; right:-4px; font-size:22px;
  filter:drop-shadow(0 1px 2px rgba(0,0,0,.3)); }
.profile-title-chip { display:inline-block; margin-top:6px; padding:3px 12px; border-radius:20px;
  background:#fbeecb; color:#b8860b; font-weight:800; font-size:12px; }
```

Ensure the avatar container is `position:relative` so the badge anchors to it (add the rule if needed, scoped to the profile avatar class you find).

- [ ] **Step 3: Verify**

`npm run build`; `npm run dev`. Equip a frame (🌿) and a title (👑 Магнат) in Коллекция, open Профиль → the frame badge shows on the avatar and the title chip shows under the name. Unequip → they disappear.

- [ ] **Step 4: Commit**

```bash
git add src/components/ProfileModule.jsx src/styles/cosmetic-effects.css
git commit -m "feat(effects): equipped frame + title show in profile"
```

---

## Self-Review (completed by plan author)

**Spec coverage:**
- §3.1 roulette on top + non-empty → Task 4 (reorder + preview pool) backed by Task 2 (preview).
- §3.2 live feed → Task 4 (polling).
- §4.1 remove spring → Task 1 (deactivate). §4.2 description → Task 1. §4.3 series → Task 1.
- §5 item detail sheet → Task 5.
- §6.1 equipped endpoint → Task 3; hook → Task 6. §6.2 effects → Tasks 7 (bg), 8 (pet), 9 (plot), 10 (frame+title). §6.3 effect mapping → Task 5 (`SLOT_EFFECT`). §6.4 immediacy → Task 6 (`cosmetics:changed`) + Task 5 (emit).
- §7 touched files all covered. §9 phases 1(Tasks1-3)/2(Tasks4-5)/3(Tasks6-10).

**Placeholder scan:** Backend tasks have complete code. Frontend modification tasks (7-10) use explicit "read the file and integrate with THIS code" because the exact surrounding markup (FarmModule/PlotCard/ProfileModule) is codebase-specific — the code to add is given; the insertion point requires reading. This is the same inspect-and-mirror pattern used successfully in the frontend plan, not a placeholder.

**Type consistency:** `get_equipped` slot dict shape (`{code,emoji,name}|null`) matches `useEquippedCosmetics` consumption and Tasks 7-10 (`equipped.background.code`, `equipped.pet.emoji`, `equipped.plot.code`, `equipped.frame.emoji`, `equipped.title.name`). `state.preview` `{emoji,rarity}` (Task 2) matches ChestRoulette's pool cell shape. `SLOT_EFFECT` keys = slot values.

**Open items flagged for implementers (not gaps):** exact plot element class (Task 9) and avatar markup (Task 10) require reading the file; `get_collection` must return `description` (Task 5 verifies + adds if missing); pet `bottom` offset may need a visual tweak.
