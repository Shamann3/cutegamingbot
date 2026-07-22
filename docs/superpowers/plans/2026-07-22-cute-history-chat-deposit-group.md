# Группа-получатель у пополнений бч в истории кут — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Записывать `chat_id` группы при пополнении баланса чата (бч) в `cutehistory` и показывать в админской истории кут игрока, в какую группу ушли его куты.

**Architecture:** Новая nullable-колонка `cutehistory.chat_id` хранит группу-получателя в строке плательщика; бот пишет её при пополнении бч. Админ-бэкенд резолвит название группы `LEFT JOIN chat` по `chat_id` и отдаёт объект `group`; фронт показывает строку-получателя с бейджем «бч».

**Tech Stack:** Python 3 / asyncpg / FastAPI (сервер), aiogram-бот, React 18 / Vite (админка), Postgres.

## Global Constraints

- Вид строки определяется **детерминированно по колонке `chat_id`** (не по тексту `cause`): `transfer` при `transfer_id`, иначе `chat_deposit` при `chat_id`, иначе `cute`.
- `chat_id` в `cutehistory_minus` — необязательный (`None` по умолчанию); **все существующие вызовы `cutehistory_minus` не меняются** и пишут `NULL`. Единственный вызов, передающий `chat_id`, — `bot/handlers/chatbalance.py:347` (причина «положено на баланс группы»).
- **Не переписывать** поток пополнения на атомарную транзакцию — только добавить `chat_id` в существующую запись истории. `cutehistory_plus` и снятия не трогать.
- Атрибуция: строку пишет плательщик (`user_id`), `chat_id` = группа. История игрока фильтрует `WHERE ch.user_id = <игрок>` → показываются только **его** пополнения, никогда чужие.
- Форма элемента истории дополняется опциональным ключом `group: {chatId:int, name:str|None, username:str|None}` (аналог `counterparty`).
- Название/username группы берём из таблицы `chat` (`namechat`, `usernamechat`); при отсутствии группы в `chat` — `name`/`username` = `None`, показываем только `chatId`.
- Право доступа не меняем (вкладка «Кут (полная)» уже только для владельцев).
- Тесты сервера: `cd server && python -m pytest tests/ -v`. Фронт: `cd admin && npm run build`.

---

### Task 1: Схема — `cutehistory.chat_id` + индекс

**Files:**
- Modify: `server/schema.sql` (блок `CREATE TABLE IF NOT EXISTS cutehistory` — добавить колонку)
- Modify: `server/db.py` (блок миграций, рядом с `cutehistory.transfer_id`)

**Interfaces:**
- Produces: колонка `cutehistory.chat_id BIGINT` (nullable), индекс `cutehistory_chat_idx`.

- [ ] **Step 1: Добавить колонку в `CREATE TABLE` в `server/schema.sql`**

В блоке `CREATE TABLE IF NOT EXISTS cutehistory (...)` добавить строку `transfer_id BIGINT,` → рядом `chat_id BIGINT`. Итоговый список колонок:

```sql
CREATE TABLE IF NOT EXISTS cutehistory (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    "+" BIGINT,
    "-" BIGINT,
    cause TEXT,
    data TEXT,
    first_name TEXT,
    username TEXT,
    balance BIGINT,
    transfer_id BIGINT,
    chat_id BIGINT
);
```

- [ ] **Step 2: Добавить ALTER + индекс в `server/db.py`**

Сразу после существующего блока миграции `cutehistory.transfer_id` (там, где `ALTER TABLE cutehistory ADD COLUMN IF NOT EXISTS transfer_id BIGINT` и `CREATE INDEX ... cutehistory_transfer_idx`), внутри того же `try/except` дописать две строки:

```python
                await conn.execute(
                    "ALTER TABLE cutehistory ADD COLUMN IF NOT EXISTS chat_id BIGINT"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS cutehistory_chat_idx "
                    "ON cutehistory (chat_id)"
                )
```

(Идёт после `transfer_id`-миграции, в том же `try`, чтобы разделять `except`-логирование.)

- [ ] **Step 3: Проверить, что файлы валидны**

Run: `cd server && python -c "import pathlib; s=pathlib.Path('schema.sql').read_text(encoding='utf-8'); assert 'chat_id BIGINT' in s and 'CREATE TABLE IF NOT EXISTS cutehistory' in s; print('schema OK')"`
Expected: печатает `schema OK`

Run: `cd server && python -c "import ast,pathlib; ast.parse(pathlib.Path('db.py').read_text(encoding='utf-8')); print('db.py parses')"`
Expected: печатает `db.py parses`

Run: `cd server && python -c "import pathlib; s=pathlib.Path('db.py').read_text(encoding='utf-8'); assert 'cutehistory_chat_idx' in s and 'ADD COLUMN IF NOT EXISTS chat_id' in s; print('migration OK')"`
Expected: печатает `migration OK`

- [ ] **Step 4: Commit**

```bash
git add server/schema.sql server/db.py
git commit -m "feat(db): add cutehistory.chat_id column + index"
```

---

### Task 2: Бот — `cutehistory_minus(chat_id=None)` + запись группы при пополнении бч

**Files:**
- Modify: `bot/db_create/db.py` (`cutehistory_minus`, ~строки 7001-7032)
- Modify: `bot/handlers/chatbalance.py:347`

**Interfaces:**
- Consumes: колонка `cutehistory.chat_id` (Task 1).
- Produces: `cutehistory_minus(self, user_id, amount, cause, chat_id=None)` — при переданном `chat_id` пишет его в строку; строка пополнения бч получает `chat_id` группы.

- [ ] **Step 1: Добавить параметр `chat_id` в `cutehistory_minus`**

В `bot/db_create/db.py` заменить сигнатуру и INSERT метода `cutehistory_minus`:

```python
    async def cutehistory_minus(self , user_id , amount , cause , chat_id=None):
        """
        Записывает данные с минусом в таблицу cutehistory.
        :param user_id: ID пользователя.
        :param amount: Сумма.
        :param cause: Причина.
        :param chat_id: (необязательно) ID группы-получателя при пополнении баланса чата.
        """
        if not self.pool:
            raise RuntimeError("Подключение к базе данных не установлено.")

        # Получаем имя и username пользователя
        first_name = await self.get_name_by_user_id(user_id)
        username = await self.get_username_by_user_id(user_id)

        # Получаем текущий баланс пользователя
        balance = await self.get_user_balance(user_id)

        # Получаем текущую дату и время
        current_datetime = datetime.now()

        # Преобразуем datetime в строку в формате чч:мм дд.мм.гггг
        formatted_date = current_datetime.strftime("%H:%M %d.%m.%Y")

        try:
            query = """
                INSERT INTO cutehistory ("user_id", "-", cause, data, first_name, username, balance, chat_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            async with self.pool.acquire() as connection:
                await connection.execute(query , user_id , amount , cause , formatted_date , first_name , username, balance, chat_id)
        except Exception as e:
            print(f"[ERROR] Ошибка при записи данных с минусом в таблицу cutehistory: {e}")
```

(Единственные изменения: параметр `chat_id=None`, колонка `chat_id` + `$8` в INSERT, аргумент `chat_id` в `execute`. `cutehistory_plus` не трогаем.)

- [ ] **Step 2: Передать `chat_id` при пополнении бч**

В `bot/handlers/chatbalance.py:347` заменить:

```python
            await db.cutehistory_minus(user_id , amount , "положено на баланс группы")
```

на:

```python
            await db.cutehistory_minus(user_id , amount , "положено на баланс группы" , chat_id=chat_id)
```

(`chat_id` уже определён в этом обработчике — используется в `db.update_chat_balance(bot1, chat_id, amount)` и `db.get_chat_balance(bot1, chat_id)`.)

- [ ] **Step 3: Проверить парсинг и точечность правок**

Run: `cd bot && python -c "import ast,pathlib; ast.parse(pathlib.Path('db_create/db.py').read_text(encoding='utf-8')); ast.parse(pathlib.Path('handlers/chatbalance.py').read_text(encoding='utf-8')); print('parse OK')"`
Expected: печатает `parse OK`

Run: `python -c "import pathlib; s=pathlib.Path('bot/db_create/db.py').read_text(encoding='utf-8'); i=s.index('async def cutehistory_minus'); blk=s[i:i+1400]; assert 'chat_id=None' in blk and '\"balance\", chat_id' in blk and '\$8' in blk; print('minus OK')"`
Expected: печатает `minus OK`

Run: `python -c "import pathlib; s=pathlib.Path('bot/handlers/chatbalance.py').read_text(encoding='utf-8'); assert 'положено на баланс группы\" , chat_id=chat_id' in s or 'положено на баланс группы\", chat_id=chat_id' in s; print('call OK')"`
Expected: печатает `call OK`

- [ ] **Step 4: Commit**

```bash
git add bot/db_create/db.py bot/handlers/chatbalance.py
git commit -m "feat(chatbalance): record target group chat_id on бч deposit history"
```

---

### Task 3: Backend — резолв группы (JOIN chat) + `group` в элементе

**Files:**
- Modify: `server/admin_cute_history.py` (`normalize_cute_row` + SQL в `get_user_cute_history`)
- Modify: `server/tests/test_cute_history.py` (тест на `chat_deposit`)

**Interfaces:**
- Consumes: `cutehistory.chat_id` (Task 1), таблица `chat` (`chat_id, namechat, usernamechat`).
- Produces: элемент истории с `kind` ∈ {`transfer`,`chat_deposit`,`cute`}; при `chat_deposit` — ключ `group: {chatId:int, name:str|None, username:str|None}`.

- [ ] **Step 1: Написать тест на `chat_deposit` в `server/tests/test_cute_history.py`**

Дописать в конец файла (использует те же plain-dict строки, что и другие тесты `normalize_cute_row`):

```python
def test_normalize_chat_deposit_attaches_group():
    row = {"plus": None, "minus": 300, "cause": "положено на баланс группы",
           "balance": 1200, "transfer_id": None, "ts": TS_A,
           "sender_id": None, "receiver_id": None,
           "chat_id": -1001921925861, "group_name": "Cute Chat", "group_username": "LegendaryChat"}
    item = normalize_cute_row(row, {})
    assert item["kind"] == "chat_deposit"
    assert item["direction"] == "out"
    assert item["amount"] == 300
    assert "counterparty" not in item
    assert item["group"] == {"chatId": -1001921925861, "name": "Cute Chat", "username": "LegendaryChat"}


def test_normalize_chat_deposit_unknown_group_keeps_chat_id():
    row = {"plus": None, "minus": 50, "cause": "положено на баланс группы",
           "balance": 0, "transfer_id": None, "ts": TS_A,
           "sender_id": None, "receiver_id": None,
           "chat_id": -100500, "group_name": None, "group_username": None}
    item = normalize_cute_row(row, {})
    assert item["group"] == {"chatId": -100500, "name": None, "username": None}


def test_normalize_transfer_takes_precedence_over_chat_id():
    row = {"plus": None, "minus": 500, "cause": "дать", "balance": 1500,
           "transfer_id": 7, "ts": TS_A, "sender_id": 111, "receiver_id": 222,
           "chat_id": -100999, "group_name": "X", "group_username": "x"}
    item = normalize_cute_row(row, {222: {"name": "Аня", "username": "anya"}})
    assert item["kind"] == "transfer"
    assert "group" not in item
    assert item["counterparty"]["userId"] == 222
```

- [ ] **Step 2: Запустить тесты — убедиться, что падают**

Run: `cd server && python -m pytest tests/test_cute_history.py -k "chat_deposit or precedence" -v`
Expected: FAIL — `normalize_cute_row` пока не проставляет `kind="chat_deposit"`/`group` (AssertionError / KeyError на `item["group"]`).

- [ ] **Step 3: Обновить `normalize_cute_row` в `server/admin_cute_history.py`**

Заменить тело `normalize_cute_row` на версию с определением `chat_deposit` (новые поля читаются через `.get()`, чтобы не ломать существующие тесты/строки без этих ключей — `.get()` поддерживают и `dict`, и asyncpg `Record`):

```python
def normalize_cute_row(row: Any, name_map: dict) -> dict:
    """Строка cutehistory (+ данные джойнов) → элемент фида."""
    plus = row["plus"]
    minus = row["minus"]
    direction = cute_direction(plus, minus)
    amount = int(plus if direction == "in" else minus)
    is_transfer = row["transfer_id"] is not None
    chat_id = row.get("chat_id")
    is_chat_deposit = (not is_transfer) and chat_id is not None
    kind = "transfer" if is_transfer else ("chat_deposit" if is_chat_deposit else "cute")
    item = {
        "ts": _iso(row["ts"]),
        "cause": row["cause"],
        "amount": amount,
        "direction": direction,
        "balance": int(row["balance"]) if row["balance"] is not None else None,
        "kind": kind,
    }
    if is_transfer:
        cp_id = counterparty_id(direction, row["sender_id"], row["receiver_id"])
        if cp_id is not None:
            info = name_map.get(cp_id) or {}
            item["counterparty"] = {
                "userId": int(cp_id),
                "name": info.get("name"),
                "username": info.get("username"),
            }
    elif is_chat_deposit:
        item["group"] = {
            "chatId": int(chat_id),
            "name": row.get("group_name"),
            "username": row.get("group_username"),
        }
    return item
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `cd server && python -m pytest tests/test_cute_history.py -v`
Expected: PASS (включая новые `chat_deposit`/`precedence` и все прежние — они не передают новых ключей, `.get()` возвращает `None`).

- [ ] **Step 5: Добавить JOIN `chat` и колонки в SQL `get_user_cute_history`**

В `server/admin_cute_history.py` в основном запросе по `cutehistory` (список строк) добавить `ch.chat_id`, `LEFT JOIN chat` и колонки названия группы. Заменить блок `cute_rows = await db.pool.fetch(...)` на:

```python
    cute_rows = await db.pool.fetch(
        f"""
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
        LIMIT ${idx}
        """,
        *params, fetch_n,
    )
```

(COUNT-запрос `cute_total`, фильтры и пагинация не меняются: `chat.chat_id` уникален, LEFT JOIN не размножает строки.)

- [ ] **Step 6: Проверить, что весь набор тестов и импорт роутов целы**

Run: `cd server && python -m pytest tests/ -q`
Expected: PASS (все тесты, включая `test_cute_history_route_registered`).

- [ ] **Step 7: Commit**

```bash
git add server/admin_cute_history.py server/tests/test_cute_history.py
git commit -m "feat(admin): resolve бч deposit target group in cute-history"
```

---

### Task 4: Frontend — показ группы + бейдж «бч»

**Files:**
- Modify: `admin/src/pages/sections/UsersSection.jsx` (`CuteHistoryFeed` — рендер строки)

**Interfaces:**
- Consumes: элемент истории с `kind:"chat_deposit"` и `group:{chatId,name,username}` (Task 3).
- Produces: строка-получатель группы + бейдж «бч» в фиде «Кут (полная)».

- [ ] **Step 1: Добавить рендер группы и бейдж в строку фида**

В `admin/src/pages/sections/UsersSection.jsx`, в `CuteHistoryFeed`, в разметке элемента списка (`items.map(...)`) рядом с бейджами `donate`/`transfer` и строкой `CounterpartyLine`:

Добавить бейдж «бч» — после блока с бейджами `donate`/`transfer` (в том же `<span className="panel-users-audit-type">`), дописать:

```jsx
                {it.kind === 'chat_deposit' && <span className="pu-cute-badge pu-cute-badge-bch">бч</span>}
```

И строку группы — сразу после `{it.counterparty && (<CounterpartyLine .../>)}` добавить:

```jsx
            {it.group && (
              <p className="panel-shelf-muted">
                → группа {it.group.name || '—'}
                {it.group.username ? ` @${it.group.username}` : ''}{' '}
                <span style={{ opacity: 0.6 }}>(id {it.group.chatId})</span>
              </p>
            )}
```

- [ ] **Step 2: Добавить стиль бейджа «бч»**

В `<style>`-блоке `CuteHistoryFeed` рядом с `.pu-cute-badge-tr` добавить:

```css
        .pu-cute-badge-bch { color: #57c785; }
```

- [ ] **Step 3: Собрать фронт**

Run: `cd admin && npm run build`
Expected: `✓ built in …`, без ошибок.

- [ ] **Step 4: Commit**

```bash
git add admin/src/pages/sections/UsersSection.jsx
git commit -m "feat(admin-ui): show бч deposit target group in cute-history feed"
```

---

## Self-Review

**Spec coverage:**
- Схема `cutehistory.chat_id` + индекс → Task 1. ✅
- Бот: `cutehistory_minus(chat_id=None)` + передача в `chatbalance.py:347`, прочие вызовы не тронуты → Task 2. ✅
- Атрибуция (строка плательщика, фильтр по user_id) — обеспечивается тем, что `chat_id` пишется в строку плательщика (Task 2) и запрос фильтрует по `user_id` (существующий код, не меняется). ✅
- Backend: JOIN `chat`, `group` в элементе, детерминированный `kind` по `chat_id` → Task 3. ✅
- Frontend: строка группы + бейдж «бч» → Task 4. ✅
- Вне рамок (не атомарим поток, не трогаем `cutehistory_plus`/снятия, старые строки `chat_id=NULL`, право доступа не меняем) — соблюдено, задач на эти изменения нет. ✅

**Placeholder scan:** плейсхолдеров нет — весь код и команды приведены полностью.

**Type consistency:** `normalize_cute_row(row, name_map)` — сигнатура неизменна (Task 3); новые поля читаются через `row.get("chat_id"/"group_name"/"group_username")`; SQL-алиасы `chat_id, group_name, group_username` (Task 3 Step 5) совпадают с ключами, которые читает `normalize_cute_row` (Task 3 Step 3). Форма `group: {chatId, name, username}` одинакова в бэкенде (Task 3) и фронте (Task 4). `kind:"chat_deposit"` согласован между Task 3 и Task 4.
