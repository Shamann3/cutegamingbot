# Розыгрыши v3 — условия «Подписка на канал» и «Пригласить друзей»

## Контекст

После v2 (вкладки/анонсы/лента победителей) остаются два независимых запроса от владельца проекта:

1. **Новые типы условий участия** (эта спека): подписка на Telegram-канал и «пригласить N друзей», в дополнение к существующим `balance`/`harvest_count`/`item_count`.
2. **Несколько мест/призов для таймер-розыгрыша** (отдельная спека, будет написана после этой).

Условие «Запуск бота» из исходного запроса исключено как избыточное: чтобы увидеть розыгрыш в вебаппе, пользователь уже обязан был запустить бота. По уточнению владельца, это условие и имелось в виду как «Пригласить друга».

## Существующий контекст (уже в коде)

- `server/giveaway_conditions.py` — реестр `VALID_CONDITION_KINDS = frozenset({"balance", "harvest_count", "item_count"})`, чекеры-функции, `all_conditions_met(ctx, conditions)`. Докстринг файла уже анонсирует `referral_count` как будущий тип.
- Реферальная система уже реализована в `bot/db_create/db.py`: `users.refferals` (INT) — счётчик подтверждённых рефералов текущего пользователя. `get_refferals_count(user_id)` (`bot/db_create/db.py:8572`) — готовый способ прочитать значение. Реферал засчитывается только когда приглашённый сыграл хотя бы одну игру (не на голом `/start`).
- `users` в `server/schema.sql` объявлен лишь с 3 колонками (`user_id, balance, items`), но это `CREATE TABLE IF NOT EXISTS` — физически это та же таблица, что и в `bot/`, с уже существующими `username`, `first_name`, `refferals` и т.д. (это подтверждено: `server/db.py` уже джойнит `u.username`/`u.first_name` из этой же таблицы). Значит `refferals` читается из `server/db.py` без каких-либо дополнительных миграций/связей между базами.
- `server/telegram_notify.py` — у `server/` (FastAPI-процесс) уже есть собственный HTTP-клиент к `api.telegram.org` (используя `BOT_TOKEN` из `server/config.py:387`), используемый для `sendMessage`. Значит для `getChatMember` не нужно ничего согласовывать с отдельным процессом `bot/` — это прямой HTTP-вызов из `server/`.
- Название бота для реферальной ссылки: `bot/config/config.py:556` → `BOT_USERNAME = "CuteGamingBot"`.

## 1. Модель данных

- Расширить `CHECK` на `giveaway_conditions.kind`, добавив `'channel_sub'` и `'referral_count'` (миграция: `DROP CONSTRAINT` + `ADD CONSTRAINT` с новым списком значений — существующие строки не трогаем).
- **`channel_sub`**: переиспользует существующую колонку `item_id` (тот же паттерн, что уже используется для `item_count`) — хранит `@username` канала без `@`. `target_value` не используется по смыслу, но столбец `NOT NULL CHECK (>= 1)` — храним `1` по соглашению.
- **`referral_count`**: использует `target_value` как требуемое число рефералов. `item_id` не используется (`NULL`).
- Новая таблица `giveaway_channel_sub_cache`:
  ```sql
  CREATE TABLE IF NOT EXISTS giveaway_channel_sub_cache (
      user_id BIGINT NOT NULL,
      channel TEXT NOT NULL,
      is_member BOOLEAN NOT NULL,
      checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (user_id, channel)
  );
  ```
  TTL (5–10 минут) не хранится в схеме — проверяется в коде по возрасту `checked_at`.

## 2. Логика проверки условия и работа с пулом соединений

- `server/giveaway_conditions.py`: добавить `check_referral_count(ctx, cond)` → `ctx["referral_count"] >= cond["target_value"]`; `check_channel_sub(ctx, cond)` → `ctx["channel_sub"].get(cond["item_id"], False)`.
- Новый модуль `server/telegram_membership.py`:
  - `async def check_channel_membership(channel: str, user_id: int, *, force_refresh: bool = False) -> bool` — если не `force_refresh` и в `giveaway_channel_sub_cache` есть запись свежее TTL, возвращает её. Иначе делает `getChatMember` через `aiohttp` (без блокировки event loop) и апсертит кэш. Статус `member`/`administrator`/`creator` → `True`, иначе/при ошибке API (таймаут, бот не админ канала, канал не найден) → `False` (fail-closed — тот же принцип, что в уже существующей legacy-проверке подписки в `bot/`).
  - **Правило пула** (то же ограничение, что действовало в v2): нельзя держать соединение из `pool.acquire()` открытым во время внешнего HTTP-вызова к Telegram. Поэтому чтение кэша, HTTP-вызов и запись кэша — три раздельных шага, из которых только первый и третий держат соединение из пула (коротко), а сам HTTP-вызов идёт без открытого соединения.
- `_giveaway_condition_ctx` — расширяется: после существующего запроса (`balance`, `harvest_count`, `items`) добавляется `ctx["referral_count"] = <refferals из той же строки users>`. `ctx["channel_sub"]` заполняется отдельно — вызывающий код (см. ниже) собирает множество различных `@channel`, встречающихся в условиях текущего запроса, и разрешает их через `check_channel_membership` до вызова `all_conditions_met`.
- `get_giveaways_state` (список): условия для ВСЕХ отдаваемых игроку розыгрышей уже читаются в цикле (`_giveaway_conditions` на каждый розыгрыш) — до вызова `all_conditions_met` для КАЖДОГО из них нужно один раз собрать множество уникальных каналов по всем условиям пачки и один раз (не по одному на каждый розыгрыш!) вызвать разрешение подписки на каждый уникальный канал, положить результат в общий `ctx["channel_sub"]`, и только затем пройтись по розыгрышам, вычисляя `conditions_met`.
- `get_giveaway_detail` (один розыгрыш) — тот же принцип, но без пакетной агрегации (там всего один набор условий).
- `participate_in_giveaway` — прямо перед финальной проверкой `all_conditions_met`, для каждого `channel_sub`-условия вызывается `check_channel_membership(..., force_refresh=True)` — то есть здесь кэш игнорируется, проверка всегда живая, чтобы нельзя было «проскочить» на устаревшем «да, подписан».

## 3. Админ-панель

`admin/src/pages/sections/GiveawaysSection.jsx`:

- `CONDITION_KIND_OPTIONS` дополняется:
  - `{ value: 'channel_sub', label: 'Подписка на Telegram-канал' }`
  - `{ value: 'referral_count', label: 'Пригласить друзей ≥' }`
- Существующий блок условного поля `itemId` (сейчас показывается только для `item_count`, с placeholder «id предмета») расширяется до `cond.kind === 'item_count' || cond.kind === 'channel_sub'`, с разным placeholder-текстом («id предмета» / «@username канала»).
- Для `channel_sub` числовое поле `targetValue` скрывается в форме (не показывается администратору), при сохранении всегда отправляется `1`.
- Для `referral_count` используется уже существующее числовое поле `targetValue` без `itemId`.

## 4. Вебапп — отображение условия и кнопка «Перейти»

`src/components/GiveawayDetailModal.jsx`:

- `CONDITION_LABEL` дополняется:
  - `channel_sub`: `` `Подписка на @${cond.itemId}` ``
  - `referral_count`: `` `Приглашено друзей: ${cond.current} из ${cond.targetValue}` ``
- Кнопка «Перейти» у невыполненного условия сейчас всегда вызывает `onNavigateCondition(CONDITION_NAV_TARGET[cond.kind])` (внутренняя навигация по вкладкам приложения). Для новых типов это неприменимо — вводится специальный путь, использующий уже существующий хелпер `openTelegramBotLink(url)` из `src/lib/telegram.js:63` (пробует `tg.openTelegramLink` → `tg.openLink` → `window.location.assign`, в этом порядке):
  - `channel_sub` → кнопка «Перейти» вызывает `openTelegramBotLink('https://t.me/' + cond.itemId)`.
  - `referral_count` → кнопка «Перейти» вызывает `openTelegramBotLink('https://t.me/share/url?url=https://t.me/CuteGamingBot?start=<user_id>')` — тот же формат реферальной ссылки (`https://t.me/CuteGamingBot?start=<user_id>`), что уже используется в существующей реферальной механике бота.

## Границы (что НЕ входит в эту спеку)

- Несколько мест/призов для таймер-розыгрыша — отдельная спека.
- Любые изменения существующих условий `balance`/`harvest_count`/`item_count` — не трогаем.
- Условие «Запуск бота» как отдельный тип — исключено (см. «Контекст»).
- UI для просмотра/управления самим кэшем подписок в админке — не требуется, это внутренний implementation detail.
