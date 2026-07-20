# Розыгрыши (Giveaways) v1 — логика и интерфейс

Дата: 2026-07-20
Файлы: `server/*`, `admin/src/*`, `src/*` (полный список — в разделе «Файлы»)

## Задача

Сейчас «Розыгрыши» — чистая заглушка (`src/components/GiveawaysModule.jsx`), без бэкенда. Нужно построить полноценную фичу: админ создаёт розыгрыш (приз, условия, срок, редкость), игрок видит список активных розыгрышей как красивые билеты, выполняет условия прямо в игре, участвует, и получает приз — либо сразу (если розыгрыш «гарантированный»), либо после случайного розыгрыша по таймеру.

## Объём v1 и то, что сознательно вынесено

**В v1 входит:**
- Ядро розыгрышей: модель данных, обе механики определения победителя (по таймеру / мгновенно всем выполнившим), участие, история.
- Условия участия — только **внутриигровые**, проверяемые по данным, которые уже есть в БД: баланс КУТ, счётчик урожаев, количество конкретного предмета в рюкзаке.
- Админ-панель для создания/редактирования/просмотра розыгрышей.
- Фронтенд: карточки-билеты с цветовой редкостью, свайп-участие, модалка деталей на 3 зоны, авто-обновление статуса без кнопки «Проверить».

**Явно вне v1** (архитектура условий расширяемая, эти типы добавляются позже без переделки ядра):
- Условие «подписка на Telegram-канал» — требует интеграции с отдельным aiogram-ботом (`bot/design/sub.py` содержит рабочий прецедент `check_sub_channel`/`getChatMember`, но это отдельный процесс от FastAPI-сервера вебаппа — нужно отдельно решать, как сервер вебаппа получит этот статус).
- Условие «выполни N заданий» — переиспользует `quest_progress`, но не в этом заходе.
- Условие «пригласи друзей» — в проекте вообще нет реферальной системы (проверено: ни `referral`, ни `invited_by` нигде не встречается), это отдельная фича с нуля.
- Автоматическая выплата Telegram Stars через Bot API. Приз может быть NFT/подарком/Stars, но **выдаёт его вручную администрация** — вебапп только красиво показывает приз и результат розыгрыша, начисление касается только КУТ.

## Данные (Postgres, `server/schema.sql`)

Следую конвенции `quests`/`quest_rewards` (`schema.sql:170-207`): `id SERIAL PRIMARY KEY`, `created_at`/`updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `user_id BIGINT` без FK-констрейнта на `users` (в этой схеме FK на `users(user_id)` нигде не объявляются, включая `farm_plots.user_id`, `audit_events.user_id`).

```sql
CREATE TABLE IF NOT EXISTS giveaways (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    emoji TEXT NOT NULL DEFAULT '🎁',
    rarity TEXT NOT NULL CHECK (rarity IN ('common', 'rare', 'legendary')),
    prize_type TEXT NOT NULL CHECK (prize_type IN ('kut', 'manual')),
    prize_kut_amount INT,               -- обязателен при prize_type='kut'
    prize_title TEXT,                   -- обязателен при prize_type='manual' (напр. "NFT «Золотой Феникс»")
    prize_emoji TEXT,                   -- напр. '🖼️', '🎁', '⭐'
    prize_description TEXT,             -- напр. "Уникальный NFT, получите его от администрации в ЛС"
    draw_type TEXT NOT NULL CHECK (draw_type IN ('timer', 'instant')),
    ends_at TIMESTAMPTZ,                -- обязателен при draw_type='timer'
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    winner_user_id BIGINT,              -- заполняется при завершении timer-розыгрыша
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drawn_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS giveaway_conditions (
    id SERIAL PRIMARY KEY,
    giveaway_id INT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('balance', 'harvest_count', 'item_count')),
    target_value INT NOT NULL CHECK (target_value >= 1),
    item_id TEXT,                       -- обязателен при kind='item_count'; ключ как в users.items (напр. "Ключ")
    sort_order INT NOT NULL DEFAULT 0
);

-- Билет участника. Для draw_type='instant' наличие строки = уже выиграл.
-- Для draw_type='timer' это пул кандидатов, победитель фиксируется в giveaways.winner_user_id.
CREATE TABLE IF NOT EXISTS giveaway_entries (
    giveaway_id INT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (giveaway_id, user_id)
);
```

Проверяемые поля игрока (уже существуют, ничего нового добавлять не нужно):
- `users.balance INT` (`schema.sql:4`)
- `users.harvest_count INT` (`schema.sql:256`)
- `users.items TEXT` — JSON-строка вида `{"Ключ": 7, "Вода": 98}`, читается через `parse_items()`/`decode_json_payload()` (`server/user_items.py:8-9`, `server/json_db_codec.py:60`)

## Реестр условий (расширяемая архитектура)

Новый файл `server/giveaway_conditions.py` — по одному чекеру на `kind`, как `VALID_ACTIONS` у квестов:

```python
def check_balance(user_row, cond) -> bool:
    return user_row["balance"] >= cond["target_value"]

def check_harvest_count(user_row, cond) -> bool:
    return user_row["harvest_count"] >= cond["target_value"]

def check_item_count(user_row, items: dict, cond) -> bool:
    return items.get(cond["item_id"], 0) >= cond["target_value"]

CONDITION_CHECKERS = {
    "balance": check_balance,
    "harvest_count": check_harvest_count,
    "item_count": check_item_count,
}
```

Розыгрыш считается доступным для участия, когда **все** его условия дают `True` (И-логика, подтверждено). Добавление `channel_sub`/`quest_count`/`referral_count` в будущем — это только новая запись в `CONDITION_CHECKERS` плюс своя логика чтения нужных данных; `participate`/список/детали не меняются.

## Бизнес-логика (`server/giveaways.py`, новый файл)

- `get_giveaways_state(user_id) -> dict` — список активных розыгрышей + для каждого: приз (кратко), редкость, `drawType`, `endsAt`, `status`, `conditionsMet: bool`, `joined: bool`. Используется и для первичной загрузки, и для тихого поллинга (см. фронтенд).
- `get_giveaway_detail(user_id, giveaway_id) -> dict` — полная карточка: приз (title/emoji/description/kutAmount), список условий с `satisfied: bool` и человекочитаемым прогрессом (напр. «320 из 500 КУТ»), `joined`, `result` (если розыгрыш завершён — `{won: bool, prizeSummary}`).
- `participate_in_giveaway(user_id, giveaway_id) -> dict` — сервер **сам** перепроверяет все условия (не доверяет фронтенду), иначе `409`/ошибка с понятным кодом. Если ОК:
  - `draw_type='instant'`: вставляет `giveaway_entries`, если `prize_type='kut'` — сразу `UPDATE users SET balance = balance + prize_kut_amount`, возвращает `{joined: true, result: {won: true, prize: {...}}}`.
  - `draw_type='timer'`: вставляет `giveaway_entries`, возвращает `{joined: true, result: null}` («вы в пуле, ждите розыгрыша»).
- `draw_timer_giveaways() -> None` — вызывается из общего тика планировщика (см. ниже). Для каждого `giveaways` с `status='active' AND draw_type='timer' AND ends_at <= now()`:
  1. `SELECT user_id FROM giveaway_entries WHERE giveaway_id = $1 ORDER BY random() LIMIT 1` внутри транзакции.
  2. Если участников нет — `status='cancelled'`, `drawn_at=now()` (розыгрыш без победителя, приз не выдаётся).
  3. Если есть победитель — `winner_user_id`, `status='completed'`, `drawn_at=now()`; если `prize_type='kut'` — начислить `prize_kut_amount` победителю.
  4. Отправить победителю уведомление: `schedule_player_telegram_dm(winner_user_id, text)` (fire-and-forget DM, `server/user_notify.py:104`) **и** `create_admin_message_notification(pool, winner_user_id, title=..., body=...)` (in-app пуш, `server/user_notify.py:178`) — оба канала, как это уже принято для важных игровых событий.

## Эндпоинты (`server/app.py`)

- `GET /api/giveaways` → `get_giveaways_state`
- `GET /api/giveaways/{giveaway_id}` → `get_giveaway_detail`
- `POST /api/giveaways/{giveaway_id}/participate` → `participate_in_giveaway`, тело запроса пустое (`extra="forbid"` Pydantic-модель без полей, для консистентности с `AcceptQuestBody`-стилем валидации)

Отклик — не полный дамп состояния, как у квестов, а точечный (проще: один розыгрыш — не весь список). Фронтенд обновляет список через свой обычный поллинг, а не через ответ `participate`.

## Планировщик (`server/event_scheduler.py`)

`_tick()` (строка ~71) уже дергается каждые 30 сек и вызывает `_fire_scheduled_broadcasts()`/`_fire_daily_rotation_broadcast()`. Добавляем туда же `await _fire_giveaway_draws()` (тонкая обёртка над `giveaways.draw_timer_giveaways()`) — отдельный asyncio-таск не нужен, тик уже общий.

## Админ-панель

Новый `admin/src/pages/sections/GiveawaysSection.jsx`, зарегистрированный в `PANEL_SECTIONS` (`admin/src/constants/panelNav.js`) и в `PanelShell.jsx` (по образцу `ContentSection`/`isContent`).

Бэкенд: `server/admin_giveaways.py` (обычные async-функции, без собственного роутера — как `admin_quests.py`) + маршруты в `admin_routes.py` на общем `router` (`prefix="/admin/api"`):
- `POST /admin/api/content/giveaways` — создание (все поля таблицы `giveaways` + список условий)
- `PATCH /admin/api/content/giveaways/{id}` — частичное обновление
- `DELETE /admin/api/content/giveaways/{id}` — отмена. Всегда мягкая (`status='cancelled'`), без физического удаления строки — даже если участников ещё нет, чтобы сохранялась история для админки и не ломались FK из `giveaway_conditions`/`giveaway_entries`
- `GET /admin/api/content/giveaways` — список активных/прошедших с бейджем статуса и (если завершён) победителем — по образцу `EventsSection.jsx`'s `UpcomingTimeline`

Все — `Depends(require_admin_permission("manage_content"))`, как у квестов.

Форма создания: title, description, emoji (обычный текстовый инпут — в проекте нигде нет загрузки картинок для наград, только эмодзи-строка, следуем этой конвенции), редкость (select), тип приза (переключатель КУТ-сумма / ручной приз title+emoji+description), тип розыгрыша (переключатель мгновенный / по таймеру с datetime-picker), список условий (repeater: тип + значение + предмет, если `item_count`), enabled-тумблер.

`admin/src/lib/adminClient.js` — добавить `fetchGiveaways`, `createGiveaway`, `updateGiveaway`, `deleteGiveaway` (тот же `adminFetch('/content/giveaways', ...)`-паттерн, что у quests-функций).

## Фронтенд вебаппа

### Клиент и хук

- `src/lib/giveawaysClient.js` — `fetchGiveaways()`, `fetchGiveaway(id)`, `participateInGiveaway(id)`, обёртки над `apiRequest` (паттерн как `questClient.js`/`chestClient.js`).
- `src/hooks/useGiveaways.js` — тот же паттерн, что `useQuests.js`: тихий поллинг раз в 30 сек (`ACTIVE_SYNC_MS`) пока таб активен, плюс `document.addEventListener('visibilitychange', ...)` — вернулся на вкладку → сразу тихий рефетч, никакой кнопки «Проверить».

### Редкость

Новый `src/constants/giveaways.js`:
```js
export const RARITY_ORDER = ['common', 'rare', 'legendary']
export const RARITY_LABEL = { common: 'Обычный', rare: 'Редкий', legendary: 'Легендарный' }
export const RARITY_ACCENT = {
  common: '#34d399',   // зелёный — фермерские бонусы/ресурсы
  rare: '#5b9be0',      // синий — крупные паки/редкие предметы (тот же синий, что у сундуков)
  legendary: '#f472b6', // розово-золотой — Stars/NFT/уникальные награды, тот же акцент, что уже задан для самой вкладки Розыгрыши в tabThemes.css
}
```

### Компоненты

- `src/components/GiveawaysModule.jsx` — переписывается: сетка карточек-билетов вместо заглушки «Скоро». Использует существующий shell-паттерн (`FarmBackground`/`TabAtmosphere variant="giveaways"`/`VineFrame`).
- `src/components/GiveawayTicketCard.jsx` (новый) — билет с перфорацией по бокам (CSS `border-image`/псевдоэлементы с вырезами, не картинка), рамка/свечение по `RARITY_ACCENT`, свой drag-обработчик (`pointerdown`/`pointermove`/`pointerup` на самом элементе, не глобальный слушатель) для свайпа вправо. Свайп-участие включено только если условий нет **или** все уже выполнены (`conditionsMet || conditions.length === 0`); иначе тап открывает модалку деталей. Карточка получает `data-no-swipe`, чтобы не конфликтовать с уже существующим глобальным свайпом между табами (`src/hooks/useSwipeTabs.js` уже игнорирует элементы с этим атрибутом).
- `src/components/GiveawayDetailModal.jsx` (новый) — 3 зоны без скролла:
  1. **Верх** — крупный эмодзи приза + название + обратный отсчёт (`draw_type='timer'`) или бейдж «Мгновенно» (`draw_type='instant'`).
  2. **Центр** — список условий (2-3 пункта), каждое с прогрессом («320 из 500 КУТ») и зелёной галочкой при выполнении; для внутриигровых условий кнопка «Перейти» ведёт на нужную вкладку (баланс → Торговля, урожаи → Ферма, предмет → Ферма/сегмент «Инвентарь») тем же паттерном событий, что `farm:go-to-shop`/`farm:go-to-market` (`src/utils/itemPurchaseGuide.js`, обработчики в `src/App.jsx`).
  3. **Низ** — большая кнопка «Участвовать»: пока не все условия выполнены — неактивна с подсказкой; когда все выполнены — начинает мягко пульсировать золотым свечением (новая CSS-анимация в стиле уже сделанного `giveaways-glow` для таб-бара) вместо смены текста в духе «нажми меня».

Для «Перейти» на сегмент «Инвентарь» внутри Фермы: `AppShell` (`src/App.jsx`) заводит `farmSegment`/`setFarmSegment` состояние (по образцу уже существующего `tradeSegment`/`setTradeSegment`) и передаёт его в `FarmModule`, которая перестаёт держать `farmSegment` только локально.

### Результат участия

- `draw_type='instant'` и выигрыш — модалка сразу показывает оверлей «🎉 Вы выиграли!» с описанием приза (для `manual`-приза — подсказка «дождитесь администрации»).
- `draw_type='timer'` — после закрытия модалки карточка билета показывает состояние «Вы в розыгрыше 🎟️»; когда планировщик проведёт розыгрыш, при следующем тихом поллинге карточка обновляется в «Розыгрыш завершён» + либо «Вы выиграли! 🏆», либо «В этот раз не повезло» для не-победивших участников (никакого спама уведомлениями всем, только победителю — см. бизнес-логику).

## Файлы

**Создать:**
- `server/giveaway_conditions.py`
- `server/giveaways.py`
- `server/admin_giveaways.py`
- `admin/src/pages/sections/GiveawaysSection.jsx`
- `src/lib/giveawaysClient.js`
- `src/hooks/useGiveaways.js`
- `src/constants/giveaways.js`
- `src/components/GiveawayTicketCard.jsx`
- `src/components/GiveawayDetailModal.jsx`

**Модифицировать:**
- `server/schema.sql` — три новые таблицы
- `server/event_scheduler.py` — вызов `_fire_giveaway_draws()` из `_tick()`
- `server/app.py` — 3 новых роута
- `server/admin_routes.py` — импорт + 4 новых роута
- `admin/src/constants/panelNav.js`, `admin/src/pages/PanelShell.jsx` — регистрация секции
- `admin/src/lib/adminClient.js` — 4 новые функции
- `src/components/GiveawaysModule.jsx` — полная замена содержимого
- `src/App.jsx` — `farmSegment`/`setFarmSegment` состояние, проброс в `FarmModule`
- `src/components/FarmModule.jsx` — принимает `farmSegment`/`setFarmSegment` вместо локального `useState`
- `src/styles/giveaways.css` — стили билетов/модалки/пульсации

## Нефункциональные моменты

- Участие — не более одного билета на человека на розыгрыш (подтверждено), обеспечивается `PRIMARY KEY (giveaway_id, user_id)` в `giveaway_entries` — повторный `POST /participate` для уже вступившего просто возвращает текущее состояние без ошибки (идемпотентно).
- Сервер всегда перепроверяет условия сам при `participate` — клиентский `conditionsMet` только для UI, не источник истины.
- Победитель по таймеру выбирается через `ORDER BY random() LIMIT 1` в транзакции БД — не на стороне Python-процесса, чтобы не тянуть весь пул участников в память при большом розыгрыше.
