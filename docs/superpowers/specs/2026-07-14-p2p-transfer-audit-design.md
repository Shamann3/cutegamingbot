# P2P transfer atomicity + audit trail — Фаза 2

## Проблема

`bot/funcs/give.py::_process_give_transfer` (команда "дать") двигает деньги четырьмя
независимыми DB-вызовами без общей транзакции:
`update_user_balance(sender, -)` → `update_user_balance(receiver, +)` →
`cutehistory_minus` → `cutehistory_plus` → `add_transaction`.

Это даёт два реальных бага, не только "нет журнала":

1. **Потеря денег при сбое между шагами.** Если процесс упадёт/перезапустится между
   списанием у отправителя и начислением получателю — деньги пропадают без следа.
2. **Гонка при записи баланса.** Оба вызова `update_user_balance` используют SET-режим
   (точное значение, посчитанное заранее), а не DELTA. Если баланс игрока изменился
   от чего-то ещё между чтением и записью — это значение затирается.

Плюс у `server/` (админка) вообще нет доступа к `cutehistory`/`moneyhistory` — это
таблицы legacy-бота, историю переводов нельзя посмотреть в панели.

## Решение

### 1. Новый метод `transfer_currency` в `bot/db_create/db.py`

```
async def transfer_currency(self, sender_id, receiver_id, amount, cause="дать") -> TransferResult
```

Одна транзакция (`pool.acquire()` + `conn.transaction()`) на весь перевод:

1. Блокировка/обновление в детерминированном порядке по `user_id` (меньший id первым)
   — исключает deadlock при параллельных встречных переводах.
2. `UPDATE users SET balance = balance - $amount WHERE user_id=$sender AND balance >= $amount
   RETURNING balance` — если строка не вернулась, поднимаем `InsufficientBalanceError`,
   транзакция откатывается целиком.
3. `UPDATE users SET balance = balance + $amount WHERE user_id=$receiver RETURNING balance`
   (с `ON CONFLICT DO UPDATE` фоллбэком как в `update_user_balance`, на случай если строки
   получателя ещё нет — хотя `give.py` и так проверяет существование заранее).
4. `INSERT INTO cutehistory` дважды (- отправителю, + получателю) — сохраняем текущий формат
   для обратной совместимости с существующими местами, что читают эту таблицу.
5. `INSERT INTO moneyhistory` — как сейчас.
6. `INSERT INTO p2p_transfers` — новая таблица, одна строка на весь перевод (см. ниже).
7. После успешного commit — write-through обновление кэша баланса (Redis `bal:val:{uid}`,
   pub/sub `bal:bus`, локальный `user_cache_balance`) для обеих сторон, тем же паттерном,
   что уже использует `update_user_balance`.

Возвращает `TransferResult(sender_before, sender_after, receiver_before, receiver_after,
transfer_id)`.

При ошибке (`InsufficientBalanceError`) — ничего не меняется, вызывающий код (`give.py`)
показывает то же сообщение "недостаточно кут", что и сейчас.

### 2. Новая таблица `p2p_transfers`

```sql
CREATE TABLE IF NOT EXISTS p2p_transfers (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sender_id BIGINT NOT NULL,
    receiver_id BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    sender_balance_before BIGINT NOT NULL,
    sender_balance_after BIGINT NOT NULL,
    receiver_balance_before BIGINT NOT NULL,
    receiver_balance_after BIGINT NOT NULL,
    cause TEXT NOT NULL DEFAULT 'дать'
);
CREATE INDEX IF NOT EXISTS p2p_transfers_sender_idx ON p2p_transfers (sender_id, created_at DESC);
CREATE INDEX IF NOT EXISTS p2p_transfers_receiver_idx ON p2p_transfers (receiver_id, created_at DESC);
CREATE INDEX IF NOT EXISTS p2p_transfers_created_idx ON p2p_transfers (created_at DESC);
```

Одна строка = полная картина перевода (кто, кому, сколько, баланс до/после у обеих сторон) —
не нужно сопоставлять две записи `cutehistory`, как сейчас.

Таблица создаётся в `server/schema.sql` (там уже живут `audit_events`, `system_logs` и т.п.,
выполняется при старте `server/app.py`) — и бот, и сервер смотрят в одну и ту же БД
(`cutebase`), поэтому bootstrap со стороны `server/` достаточно.

### 3. `bot/funcs/give.py::_process_give_transfer`

Проверки (себе/боту/дневной лимит, строки 1146-1174) остаются как есть — это дешёвые
проверки без побочных эффектов, выполняются до денег. Блок перемещения денег
(текущие строки 1179-1184) заменяется одним вызовом:

```python
try:
    result = await db.transfer_currency(sender_id, receiver_id, amount, cause="дать")
except InsufficientBalanceError:
    await message.reply(<текущее сообщение "недостаточно кут">)
    return
```

Текст подтверждения переводчику/получателю строится из `result.sender_after` /
`result.receiver_after` вместо самостоятельно вычисленных значений.

### 4. Админка — новый эндпоинт + вкладка

- `server/admin_logs.py` — новая функция `list_p2p_transfers(...)` с фильтрами
  `sender_id`, `receiver_id`, `date_from`, `date_to`, пагинацией — читает `p2p_transfers`
  напрямую (`server/` уже подключён к той же Postgres).
- `server/admin_routes.py` — роут `GET /admin/api/logs/transfers`.
- `admin/src/pages/sections/LogsSection.jsx` — новая вкладка "Переводы" рядом с
  Audit/Security/Сбои, таблица: время, отправитель, получатель, сумма,
  баланс до/после (обе стороны).

## Вне рамок

- Не трогаем существующие `cutehistory`/`moneyhistory` записи и их читателей — они
  продолжают писаться как раньше, `p2p_transfers` — дополнительный чистый источник
  правды именно для admin-проверки P2P-переводов.
- Не переписываем `update_user_balance` (используется много где ещё) — только не
  используем его в самом переводе, заменяя прямыми SQL-апдейтами внутри одной
  транзакции.
- Прочие admin-mint команды (`sypherдать` и т.п.) не меняются — это не P2P-переводы.

## Проверка

- Юнит-сценарий: перевод при достаточном балансе → баланс списан/начислен ровно один
  раз, одна строка в `p2p_transfers`, значения before/after совпадают с реальным
  списанием.
- Перевод при недостаточном балансе → ничего не меняется, ни одной новой строки.
- Параллельные встречные переводы A→B и B→A одновременно → нет дедлока (за счёт
  детерминированного порядка блокировки по `user_id`).
- Проверить в админке: тестовый перевод виден во вкладке "Переводы" с корректными
  балансами.
