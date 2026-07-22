# Группа-получатель у пополнений баланса чата (бч) в истории кут

## Проблема

Когда игрок пополняет баланс чата («бч»), бот в
`bot/handlers/chatbalance.py:347` пишет
`db.cutehistory_minus(user_id, amount, "положено на баланс группы")` — **без
указания, в какую именно группу** ушли куты. В админской вкладке «Кут (полная)»
(`server/admin_cute_history.py`) такая строка видна как обычное списание, но
понять группу-получателя нельзя.

Нужно: при пополнении бч записывать `chat_id` группы в историю и показывать в
админке, в какую группу игрок отправил куты — по аналогии с контрагентом у
переводов (`p2p_transfers`).

## Ключевое требование по атрибуции

Строку `cutehistory` при пополнении пишет **сам плательщик**: `user_id` = тот, кто
пополнил, `"-"` = сумма, а новый `chat_id` = группа-получатель. Запрос истории
игрока фильтрует `WHERE ch.user_id = <игрок>`, поэтому в полной истории кут
конкретного игрока показываются **только его собственные** пополнения бч (и в
какую группу каждое ушло) — никогда чужие. Это свойство обеспечивается тем, что
`chat_id` пишется в ту же строку плательщика, а не в отдельную запись группы.

## Данные (текущее состояние)

- **`cutehistory`** — уже расширена в
  [2026-07-21](2026-07-21-admin-player-cute-history-design.md) колонкой
  `transfer_id`. Колонки: `user_id, "+", "-", cause, data, first_name, username,
  balance, transfer_id`.
- **`chat`** (legacy) — по одной строке на группу: `chat_id`, `namechat`
  (название группы), `usernamechat` (@username), `chatlink`, `chatbalance` и др.
  Именно её показал пользователь как источник названий групп.
- Пополнение бч (`chatbalance.py`, блок «ПОПОЛНЕНИЕ БАЛАНСА ГРУППЫ») —
  неатомарная последовательность: `update_user_balance` (SET) →
  `cutehistory_minus(..., "положено на баланс группы")` → `update_chat_balance`.

## Решение

Лёгкий, точечный подход: записать `chat_id` в строку `cutehistory` пополнения и
резолвить название группы в админке из таблицы `chat` (JOIN по `chat_id`) — не
дублируя данные о группе.

### 1. Схема: `cutehistory.chat_id`

Добавить nullable-колонку и индекс — тем же bootstrap-паттерном, что `transfer_id`:

- `server/schema.sql`: в блок `CREATE TABLE IF NOT EXISTS cutehistory (...)`
  добавить колонку `chat_id BIGINT` (для свежих БД).
- `server/db.py` (блок миграций, рядом с `cutehistory.transfer_id`):
  ```sql
  ALTER TABLE cutehistory ADD COLUMN IF NOT EXISTS chat_id BIGINT;
  CREATE INDEX IF NOT EXISTS cutehistory_chat_idx ON cutehistory (chat_id);
  ```
  (idempotent, безопасно на legacy и на пустой БД).

### 2. Бот: `cutehistory_minus` принимает `chat_id`

В `bot/db_create/db.py::cutehistory_minus` добавить необязательный параметр:

```python
async def cutehistory_minus(self, user_id, amount, cause, chat_id=None):
    ...
    INSERT INTO cutehistory ("user_id", "-", cause, data, first_name, username, balance, chat_id)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    ...  # + chat_id последним аргументом
```

`chat_id` по умолчанию `None` — **все существующие вызовы `cutehistory_minus`
не меняются** (пишут `NULL`, как и раньше).

В `bot/handlers/chatbalance.py:347` (единственное место с причиной «положено на
баланс группы») передать группу:

```python
await db.cutehistory_minus(user_id, amount, "положено на баланс группы", chat_id=chat_id)
```

`chat_id` в этом обработчике уже есть (используется в `update_chat_balance`).

Вне рамок: неатомарность потока пополнения (SET-баланс, раздельные вызовы) **не
трогаем** — задача только про запись группы. `cutehistory_plus` и снятия не
меняем.

### 3. Админ-бэкенд: резолв группы через JOIN

В `server/admin_cute_history.py::get_user_cute_history` в основном запросе по
`cutehistory` добавить:

```sql
SELECT ch."+" AS plus, ch."-" AS minus, ch.cause, ch.balance, ch.transfer_id,
       ch.chat_id,
       to_timestamp(ch.data,'HH24:MI DD.MM.YYYY') AS ts,
       p.sender_id, p.receiver_id,
       c.namechat AS group_name, c.usernamechat AS group_username
FROM cutehistory ch
LEFT JOIN p2p_transfers p ON p.id = ch.transfer_id
LEFT JOIN chat c ON c.chat_id = ch.chat_id
WHERE {where}
ORDER BY ts DESC NULLS LAST
LIMIT ...
```

Фильтры/COUNT/пагинация не меняются (COUNT по `cutehistory` без JOIN — количество
не зависит от JOIN, т.к. `chat.chat_id` уникален; при отсутствии группы LEFT JOIN
даёт NULL, строка остаётся).

В `normalize_cute_row` определять вид строки детерминированно и прикладывать
группу:

```python
is_transfer = row["transfer_id"] is not None
is_chat_deposit = (not is_transfer) and row["chat_id"] is not None
kind = "transfer" if is_transfer else ("chat_deposit" if is_chat_deposit else "cute")
...
if is_chat_deposit:
    item["group"] = {
        "chatId": int(row["chat_id"]),
        "name": row["group_name"],          # может быть None, если группы нет в chat
        "username": row["group_username"],  # может быть None
    }
```

Форма элемента дополняется опциональным ключом `group` (аналог `counterparty`).

### 4. Админ-фронт: показ группы

В `admin/src/pages/sections/UsersSection.jsx` (`CuteHistoryFeed`) для строк с
`it.group` показывать строку-получателя, как контрагента переводов:

- `→ группа {name || '—'} {username ? '@'+username : ''} (id {chatId})`
- бейдж «бч» (аналог бейджей «перевод»/«донат»), `kind === "chat_deposit"`.

Если группы нет в `chat` (`name`/`username` = null) — показываем только `chatId`.

## Вне рамок

- Не переписываем поток пополнения на атомарную транзакцию (только добавляем
  `chat_id` в существующую запись истории).
- Не логируем снятия с баланса чата и прочие движения — только пользовательское
  пополнение.
- Старые пополнения (до внедрения `chat_id`) остаются с `chat_id = NULL` — группа
  ретроспективно не восстанавливается.
- Право доступа не меняем: вкладка «Кут (полная)» уже только для владельцев.

## Проверка

- **Схема**: после старта сервера у `cutehistory` есть `chat_id` и индекс
  (idempotent при повторном старте).
- **Бот**: пополнение бч → строка `cutehistory` плательщика имеет `"-"` = сумма,
  `cause` = «положено на баланс группы», `chat_id` = группа. Прочие вызовы
  `cutehistory_minus` пишут `chat_id = NULL`.
- **Backend**: `get_user_cute_history(<плательщик>)` возвращает эту строку с
  `kind="chat_deposit"` и `group = {chatId, name, username}` из `chat`. Для
  строки без `chat_id` — `kind` прежний, `group` отсутствует. Пополнение,
  сделанное ДРУГИМ игроком, в истории первого **не появляется** (фильтр по
  `user_id`).
- **Frontend**: строка пополнения бч показывает «→ группа …» и бейдж «бч»;
  строка без группы — как раньше.
