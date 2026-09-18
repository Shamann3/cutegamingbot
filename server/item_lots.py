"""Себестоимость предметов: партии (лоты), списание по FIFO, журнал сгорания.

Слой ЧИСТО НАБЛЮДАТЕЛЬНЫЙ и АДДИТИВНЫЙ. Он не меняет ни одного игрового
правила и не может помешать игровой операции:

* единственный источник правды по КОЛИЧЕСТВУ предметов — users.items;
  лоты это параллельный слой СТОИМОСТИ и ничего не решают;
* каждая публичная функция обёрнута в SAVEPOINT (вложенный
  conn.transaction() у asyncpg) и НИКОГДА не бросает наружу. Если запись
  лота сорвалась, откатывается только савпоинт — внешняя игровая
  транзакция остаётся живой и коммитится как обычно;
* молча ошибки не глотаем: каждый срыв пишется в item_cost_anomalies.

Себестоимость считается ОДИН раз, в момент получения предмета:
    магазин  — фактически уплаченная цена (со скидкой/купоном);
    биржа    — цена сделки для покупателя;
    подарок  — копируется из списанных лотов дарителя (цепочка передач
               разворачивается сама собой, без рекурсии в горячем пути);
    крафт    — сумма себестоимостей списанных ингредиентов;
    награда/
    админка  — 0 с явным источником;
    остальное— NULL (НЕИЗВЕСТНА, это не ноль).

Предметы, которые уже лежали у игроков до появления этого учёта, не
мигрируются: лот «неизвестного происхождения» с unit_cost = NULL заводится
лениво, в момент первого списания.

Модуль общий для сервера и бота (бот подключает server/ в sys.path так же,
как это делает bot/funcs/tiktok_earn.py).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

logger = logging.getLogger("cute-farm.item-lots")

# --- источники появления предмета -------------------------------------------
SOURCE_SHOP = "shop"           # магазин (веб или бот)
SOURCE_MARKET = "market"       # покупка на бирже
SOURCE_MARKET_RETURN = "market_return"  # снятие своего лота с биржи
SOURCE_TRADE = "trade"         # платная сделка между игроками напрямую
SOURCE_GIFT = "gift"           # подарок/передача между игроками
SOURCE_CRAFT = "craft"         # результат крафта
SOURCE_REWARD = "reward"       # квесты, гивы, TikTok, сундуки, царь чата
SOURCE_ADMIN = "admin"         # админская выдача
SOURCE_HARVEST = "harvest"     # урожай с фермы
SOURCE_UNKNOWN = "unknown"     # ленивый лот для предметов без истории

# --- причины выбытия ---------------------------------------------------------
REASON_CRAFT_FAIL = "craft_fail"
REASON_CRAFT_SPEND = "craft_spend"
REASON_FARM_PLANT = "farm_plant"
REASON_FARM_WATER = "farm_water"
REASON_FARM_AUTOWATER = "farm_autowater"
REASON_FARM_TOOL = "farm_tool"
REASON_COUPON_SPEND = "coupon_spend"
REASON_MARKET_LIST = "market_list"
REASON_MARKET_SOLD = "market_sold"
REASON_GIFT_SENT = "gift_sent"
REASON_TRADE_SOLD = "trade_sold"
REASON_ADMIN_TAKE = "admin_take"
REASON_CASE_OPEN = "case_open"
REASON_ITEM_USED = "item_used"

ESCROW_MARKET_LISTING = "market_listing"

# Схема поднимается один раз на процесс из lifespan/старта бота. Если её нет
# (старая БД, нет прав) — учёт сам себя глушит на _RETRY_COOLDOWN секунд,
# чтобы не долбить БД заведомо провальными запросами в горячем пути.
_RETRY_COOLDOWN = 300.0
_DEX_ALIAS_TTL = 600.0
_MAX_FIFO_PASSES = 4

_schema_ready = False
_disabled_until = 0.0


class _AliasCache:
    """Алиасы dex (id / name / name1 / emoji) → канонический dex id.

    На сервере каталог уже поднят в памяти (dex_catalog), у бота его нет —
    поэтому здесь свой ленивый кэш с TTL: один SELECT на процесс в 10 минут,
    в горячем пути запросов не будет.
    """

    __slots__ = ("_map", "_loaded_at")

    def __init__(self) -> None:
        self._map: dict[str, str] = {}
        self._loaded_at = 0.0

    def lookup(self, key: str) -> str | None:
        if not self._map:
            return None
        hit = self._map.get(key)
        if hit is not None:
            return hit
        return self._map.get(key.casefold())

    def fresh(self) -> bool:
        return bool(self._map) and (time.monotonic() - self._loaded_at) < _DEX_ALIAS_TTL

    async def refresh(self, conn) -> None:
        rows = await conn.fetch("SELECT id, name, name1, emoji FROM dex")
        alias: dict[str, str] = {}
        by_emoji: dict[str, str] = {}
        for row in rows:
            dex_id = str(row["id"]).strip()
            if not dex_id:
                continue
            for raw in (dex_id, row["name1"], row["name"]):
                token = str(raw or "").strip()
                if token:
                    alias[token] = dex_id
                    alias[token.casefold()] = dex_id
            emoji = str(row["emoji"] or "").strip()
            if emoji and emoji not in by_emoji:
                by_emoji[emoji] = dex_id
                alias.setdefault(emoji, dex_id)
        self._map = alias
        self._loaded_at = time.monotonic()


_alias_cache = _AliasCache()


@dataclass
class CostPart:
    """Кусок списания: qty единиц с одной и той же себестоимостью."""

    unit_cost: int | None
    quantity: int


@dataclass
class ConsumeResult:
    """Что именно списал FIFO.

    parts     — по одному элементу на каждую цену (в порядке FIFO);
    known_cost— сумма себестоимости по известным единицам;
    unknown_qty — сколько единиц ушло с неизвестной себестоимостью;
    ok        — False, если учёт сорвался (игровая операция при этом цела).
    """

    parts: list[CostPart] = field(default_factory=list)
    known_cost: int = 0
    unknown_qty: int = 0
    quantity: int = 0
    ok: bool = True

    @property
    def total_cost(self) -> int | None:
        """Себестоимость всей партии или None, если хоть часть неизвестна."""
        if self.unknown_qty or not self.ok:
            return None
        return self.known_cost


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS item_cost_lots (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    item_id TEXT NOT NULL,
    qty_initial INTEGER NOT NULL CHECK (qty_initial > 0),
    qty_left INTEGER NOT NULL CHECK (qty_left >= 0),
    unit_cost BIGINT,
    source TEXT NOT NULL,
    ref_kind TEXT NOT NULL DEFAULT '',
    ref_id TEXT NOT NULL DEFAULT '',
    parent_lot_ids BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS item_cost_lots_fifo_idx
    ON item_cost_lots (user_id, item_id, created_at, id)
    WHERE qty_left > 0;
CREATE INDEX IF NOT EXISTS item_cost_lots_user_idx
    ON item_cost_lots (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS item_cost_lots_created_idx
    ON item_cost_lots (created_at DESC);

CREATE TABLE IF NOT EXISTS item_cost_burns (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    item_id TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    cost_total BIGINT NOT NULL DEFAULT 0,
    unknown_qty INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    destroyed BOOLEAN NOT NULL DEFAULT TRUE,
    ref_kind TEXT NOT NULL DEFAULT '',
    ref_id TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS item_cost_burns_created_idx
    ON item_cost_burns (created_at DESC);
CREATE INDEX IF NOT EXISTS item_cost_burns_reason_idx
    ON item_cost_burns (reason, created_at DESC);
CREATE INDEX IF NOT EXISTS item_cost_burns_user_idx
    ON item_cost_burns (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS item_cost_burns_destroyed_idx
    ON item_cost_burns (created_at DESC) WHERE destroyed;

CREATE TABLE IF NOT EXISTS item_cost_escrow (
    id BIGSERIAL PRIMARY KEY,
    holder_kind TEXT NOT NULL,
    holder_id TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    item_id TEXT NOT NULL,
    qty_left INTEGER NOT NULL CHECK (qty_left >= 0),
    unit_cost BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS item_cost_escrow_holder_idx
    ON item_cost_escrow (holder_kind, holder_id, id)
    WHERE qty_left > 0;

CREATE TABLE IF NOT EXISTS item_cost_anomalies (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    item_id TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS item_cost_anomalies_created_idx
    ON item_cost_anomalies (created_at DESC);
CREATE INDEX IF NOT EXISTS item_cost_anomalies_kind_idx
    ON item_cost_anomalies (kind, created_at DESC);
"""


async def ensure_item_cost_schema(pool) -> bool:
    """Идемпотентная схема. Зовётся из lifespan сервера и старта бота."""
    global _schema_ready, _disabled_until

    if _schema_ready:
        return True
    if pool is None:
        return False
    try:
        await pool.execute(SCHEMA_SQL)
    except Exception:
        _disabled_until = time.monotonic() + _RETRY_COOLDOWN
        logger.exception("item_cost schema init failed — учёт себестоимости выключен")
        return False
    _schema_ready = True
    _disabled_until = 0.0
    return True


def accounting_enabled() -> bool:
    return _schema_ready and time.monotonic() >= _disabled_until


def _mark_unavailable() -> None:
    global _schema_ready, _disabled_until

    _schema_ready = False
    _disabled_until = time.monotonic() + _RETRY_COOLDOWN


def reset_state_for_tests() -> None:
    """Только для тестов: сбросить кэш схемы и алиасов."""
    global _schema_ready, _disabled_until

    _schema_ready = True
    _disabled_until = 0.0
    _alias_cache._map = {}
    _alias_cache._loaded_at = 0.0


async def canonical_item_key(conn, ref: Any) -> str:
    """id / name / name1 / emoji / legacy-ключ → канонический dex id.

    Ключ лота обязан совпадать у бота и у сервера, иначе слои разъедутся:
    бот оперирует именами предметов, сервер — dex id. Если dex не знает
    предмет, возвращаем исходный ключ как есть (лот всё равно заведём).
    """
    key = str(ref or "").strip()
    if not key:
        return ""

    try:
        from dex_catalog import dex_catalog

        if dex_catalog.loaded:
            return dex_catalog.canonical_key(key)
    except ImportError:
        pass

    hit = _alias_cache.lookup(key)
    if hit is not None:
        return hit
    if _alias_cache.fresh():
        return key
    await _alias_cache.refresh(conn)
    return _alias_cache.lookup(key) or key


async def _record_anomaly(conn, kind: str, user_id: int | None, item_id: str, detail: dict) -> None:
    """Запись рассогласования. Своим савпоинтом — внешняя транзакция цела."""
    try:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO item_cost_anomalies (user_id, item_id, kind, detail)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                user_id,
                str(item_id or "")[:255],
                kind,
                json.dumps(detail, ensure_ascii=False, default=str),
            )
    except Exception:
        logger.exception(
            "item_cost anomaly insert failed kind=%s user=%s item=%s detail=%s",
            kind,
            user_id,
            item_id,
            detail,
        )


def _is_missing_schema(exc: BaseException) -> bool:
    return type(exc).__name__ in ("UndefinedTableError", "UndefinedTable", "UndefinedColumnError",
                                  "UndefinedColumn", "InsufficientPrivilegeError")


async def _guarded(conn, coro_factory, *, kind: str, user_id: int | None, item_id: str, detail: dict):
    """Выполнить учётную операцию в SAVEPOINT. Наружу не бросает никогда."""
    if not accounting_enabled():
        return None
    try:
        async with conn.transaction():
            return await coro_factory()
    except Exception as exc:
        if _is_missing_schema(exc):
            _mark_unavailable()
        payload = dict(detail)
        payload["error"] = f"{type(exc).__name__}: {exc}"
        await _record_anomaly(conn, kind, user_id, item_id, payload)
        logger.warning("item_cost %s failed (%s): %r", kind, item_id, exc)
        return None


# ---------------------------------------------------------------------------
# Приход
# ---------------------------------------------------------------------------


async def _insert_lot(
    conn,
    user_id: int,
    item_id: str,
    quantity: int,
    unit_cost: int | None,
    source: str,
    ref_kind: str,
    ref_id: str,
    parent_lot_ids: Sequence[int],
) -> int:
    return int(
        await conn.fetchval(
            """
            INSERT INTO item_cost_lots (
                user_id, item_id, qty_initial, qty_left, unit_cost,
                source, ref_kind, ref_id, parent_lot_ids
            )
            VALUES ($1, $2, $3, $3, $4, $5, $6, $7, $8::bigint[])
            RETURNING id
            """,
            int(user_id),
            item_id,
            int(quantity),
            unit_cost,
            source,
            str(ref_kind or "")[:64],
            str(ref_id or "")[:128],
            list(parent_lot_ids or ()),
        )
    )


async def record_acquire(
    conn,
    user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    unit_cost: int | None,
    source: str,
    ref_kind: str = "",
    ref_id: str = "",
    parent_lot_ids: Sequence[int] = (),
) -> int | None:
    """Завести лот на полученные предметы. Возвращает id лота или None."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return None
    if unit_cost is not None:
        unit_cost = max(0, int(unit_cost))

    async def _run():
        item_id = await canonical_item_key(conn, item_ref)
        if not item_id:
            raise ValueError("пустой item_id")
        return await _insert_lot(
            conn, user_id, item_id, quantity, unit_cost, source, ref_kind, ref_id, parent_lot_ids
        )

    return await _guarded(
        conn,
        _run,
        kind="acquire_failed",
        user_id=user_id,
        item_id=str(item_ref),
        detail={"quantity": quantity, "source": source, "ref_kind": ref_kind, "ref_id": ref_id},
    )


def split_cost(total_paid: int, quantity: int) -> list[CostPart]:
    """Разложить уплаченную сумму на целые цены за единицу без потери копеек.

    Купон даёт скидку на всю покупку сразу, поэтому total/qty часто не
    делится нацело. Округление в одну сторону исказило бы себестоимость
    партии, поэтому остаток раскидываем по единицам.
    """
    quantity = max(1, int(quantity))
    total_paid = max(0, int(total_paid))
    base, rem = divmod(total_paid, quantity)
    parts = []
    if rem:
        parts.append(CostPart(base + 1, rem))
    if quantity - rem:
        parts.append(CostPart(base, quantity - rem))
    return parts


async def record_acquire_parts(
    conn,
    user_id: int,
    item_ref: Any,
    parts: Iterable[CostPart],
    *,
    source: str,
    ref_kind: str = "",
    ref_id: str = "",
    parent_lot_ids: Sequence[int] = (),
) -> list[int]:
    """Завести по лоту на каждую цену — так подарок сохраняет себестоимость
    поштучно, а не усреднённую (и цепочка передач не «плывёт»)."""
    parts = [p for p in parts if p.quantity > 0]
    if not parts:
        return []

    async def _run():
        item_id = await canonical_item_key(conn, item_ref)
        if not item_id:
            raise ValueError("пустой item_id")
        created: list[int] = []
        for part in parts:
            created.append(
                await _insert_lot(
                    conn,
                    user_id,
                    item_id,
                    part.quantity,
                    part.unit_cost,
                    source,
                    ref_kind,
                    ref_id,
                    parent_lot_ids,
                )
            )
        return created

    return (
        await _guarded(
            conn,
            _run,
            kind="acquire_failed",
            user_id=user_id,
            item_id=str(item_ref),
            detail={
                "parts": [[p.unit_cost, p.quantity] for p in parts],
                "source": source,
                "ref_kind": ref_kind,
                "ref_id": ref_id,
            },
        )
        or []
    )


# ---------------------------------------------------------------------------
# Расход (FIFO)
# ---------------------------------------------------------------------------


async def _fifo_take(conn, user_id: int, item_id: str, quantity: int) -> tuple[list[CostPart], list[int]]:
    """Списать quantity единиц по FIFO. Возвращает куски цен и id лотов.

    Гонки: два воркера uvicorn и процесс бота могут списывать одновременно.
    Берём строки `FOR UPDATE` строго в порядке FIFO — вторая транзакция
    ждёт первую, а после разблокировки Postgres (READ COMMITTED) заново
    проверяет qty_left > 0 и не выдаёт уже опустошённый лот. SKIP LOCKED
    здесь нельзя: он проскочил бы занятый лот и нарушил и порядок FIFO,
    и учёт остатка.

    LIMIT $3 хватает по построению (в лоте минимум 1 единица), но при
    EvalPlanQual отфильтрованные строки не «добираются» — поэтому цикл.
    """
    parts: list[CostPart] = []
    touched: list[int] = []
    left = quantity

    for _ in range(_MAX_FIFO_PASSES):
        if left <= 0:
            break
        rows = await conn.fetch(
            """
            SELECT id, qty_left, unit_cost
            FROM item_cost_lots
            WHERE user_id = $1 AND item_id = $2 AND qty_left > 0
            ORDER BY created_at, id
            LIMIT $3
            FOR UPDATE
            """,
            int(user_id),
            item_id,
            int(left),
        )
        if not rows:
            break
        for row in rows:
            if left <= 0:
                break
            available = int(row["qty_left"])
            if available <= 0:
                continue
            take = min(available, left)
            await conn.execute(
                "UPDATE item_cost_lots SET qty_left = qty_left - $2 WHERE id = $1",
                row["id"],
                take,
            )
            unit_cost = row["unit_cost"]
            parts.append(CostPart(None if unit_cost is None else int(unit_cost), take))
            touched.append(int(row["id"]))
            left -= take

    if left > 0:
        # Старые предметы без истории: массовой миграции нет, лот
        # «неизвестного происхождения» заводим лениво — сразу пустым,
        # он нужен только как след в учёте.
        lot_id = await conn.fetchval(
            """
            INSERT INTO item_cost_lots (
                user_id, item_id, qty_initial, qty_left, unit_cost, source
            )
            VALUES ($1, $2, $3, 0, NULL, $4)
            RETURNING id
            """,
            int(user_id),
            item_id,
            int(left),
            SOURCE_UNKNOWN,
        )
        parts.append(CostPart(None, left))
        touched.append(int(lot_id))

    return _merge_parts(parts), touched


def _merge_parts(parts: Sequence[CostPart]) -> list[CostPart]:
    merged: list[CostPart] = []
    for part in parts:
        if part.quantity <= 0:
            continue
        if merged and merged[-1].unit_cost == part.unit_cost:
            merged[-1].quantity += part.quantity
            continue
        merged.append(CostPart(part.unit_cost, part.quantity))
    return merged


def _summarize(parts: Sequence[CostPart]) -> tuple[int, int, int]:
    known = 0
    unknown = 0
    total_qty = 0
    for part in parts:
        total_qty += part.quantity
        if part.unit_cost is None:
            unknown += part.quantity
        else:
            known += part.unit_cost * part.quantity
    return known, unknown, total_qty


async def _write_burn(
    conn,
    user_id: int,
    item_id: str,
    quantity: int,
    known_cost: int,
    unknown_qty: int,
    reason: str,
    destroyed: bool,
    ref_kind: str,
    ref_id: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO item_cost_burns (
            user_id, item_id, quantity, cost_total, unknown_qty,
            reason, destroyed, ref_kind, ref_id
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        int(user_id),
        item_id,
        int(quantity),
        int(known_cost),
        int(unknown_qty),
        reason,
        bool(destroyed),
        str(ref_kind or "")[:64],
        str(ref_id or "")[:128],
    )


async def record_consume(
    conn,
    user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    reason: str,
    destroyed: bool = True,
    ref_kind: str = "",
    ref_id: str = "",
    log_event: bool = True,
) -> ConsumeResult:
    """Списать предметы по FIFO и (по умолчанию) записать выбытие в журнал."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return ConsumeResult(quantity=0)

    async def _run():
        item_id = await canonical_item_key(conn, item_ref)
        if not item_id:
            raise ValueError("пустой item_id")
        parts, _lots = await _fifo_take(conn, user_id, item_id, quantity)
        known, unknown, taken = _summarize(parts)
        if log_event:
            await _write_burn(
                conn, user_id, item_id, taken, known, unknown, reason, destroyed, ref_kind, ref_id
            )
        return ConsumeResult(parts=parts, known_cost=known, unknown_qty=unknown, quantity=taken)

    result = await _guarded(
        conn,
        _run,
        kind="consume_failed",
        user_id=user_id,
        item_id=str(item_ref),
        detail={"quantity": quantity, "reason": reason, "ref_kind": ref_kind, "ref_id": ref_id},
    )
    if result is None:
        return ConsumeResult(quantity=quantity, unknown_qty=quantity, ok=False)
    return result


async def record_consume_many(
    conn,
    user_id: int,
    items: Mapping[Any, int],
    *,
    reason: str,
    destroyed: bool = True,
    ref_kind: str = "",
    ref_id: str = "",
    log_event: bool = True,
) -> ConsumeResult:
    """Списать несколько предметов одной операцией (крафт, пакетный расход).

    Лоты берём в порядке отсортированного item_id: одинаковый порядок
    блокировок у всех вызывающих исключает взаимную блокировку двух
    параллельных крафтов с зеркальным списком ингредиентов.
    """
    wanted = {k: int(v or 0) for k, v in (items or {}).items() if int(v or 0) > 0}
    if not wanted:
        return ConsumeResult()

    async def _run():
        resolved: dict[str, int] = {}
        for ref, qty in wanted.items():
            item_id = await canonical_item_key(conn, ref)
            if not item_id:
                raise ValueError("пустой item_id")
            resolved[item_id] = resolved.get(item_id, 0) + qty

        all_parts: list[CostPart] = []
        total_known = 0
        total_unknown = 0
        total_qty = 0
        for item_id in sorted(resolved):
            qty = resolved[item_id]
            parts, _lots = await _fifo_take(conn, user_id, item_id, qty)
            known, unknown, taken = _summarize(parts)
            if log_event:
                await _write_burn(
                    conn, user_id, item_id, taken, known, unknown, reason, destroyed, ref_kind, ref_id
                )
            all_parts.extend(parts)
            total_known += known
            total_unknown += unknown
            total_qty += taken
        return ConsumeResult(
            parts=all_parts, known_cost=total_known, unknown_qty=total_unknown, quantity=total_qty
        )

    result = await _guarded(
        conn,
        _run,
        kind="consume_failed",
        user_id=user_id,
        item_id=",".join(str(k) for k in list(wanted)[:8]),
        detail={"items": {str(k): v for k, v in wanted.items()}, "reason": reason, "ref_id": ref_id},
    )
    if result is None:
        total = sum(wanted.values())
        return ConsumeResult(quantity=total, unknown_qty=total, ok=False)
    return result


async def _canonical_totals(conn, items: Mapping[Any, int]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for ref, qty in (items or {}).items():
        try:
            qty = int(qty or 0)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        key = await canonical_item_key(conn, ref)
        if not key:
            continue
        totals[key] = totals.get(key, 0) + qty
    return totals


async def record_inventory_gain(
    conn,
    user_id: int,
    before: Mapping[Any, int],
    after: Mapping[Any, int],
    *,
    unit_cost: int | None,
    source: str,
    ref_kind: str = "",
    ref_id: str = "",
) -> dict[str, int]:
    """Завести лоты по РАЗНИЦЕ инвентаря до/после.

    Так учёт врезается в места, где выдача предметов размазана по чужой
    логике (награда за квест, стартовый набор, админская выдача): мы не
    повторяем их правила, а просто смотрим, что реально прибавилось.
    """

    async def _run():
        old = await _canonical_totals(conn, before)
        new = await _canonical_totals(conn, after)
        gained: dict[str, int] = {}
        for item_id, qty in new.items():
            delta = qty - old.get(item_id, 0)
            if delta > 0:
                gained[item_id] = delta
        for item_id in sorted(gained):
            await _insert_lot(
                conn, user_id, item_id, gained[item_id], unit_cost, source, ref_kind, ref_id, ()
            )
        return gained

    return (
        await _guarded(
            conn,
            _run,
            kind="acquire_failed",
            user_id=user_id,
            item_id="",
            detail={"source": source, "ref_kind": ref_kind, "ref_id": ref_id, "mode": "delta"},
        )
        or {}
    )


async def record_inventory_loss(
    conn,
    user_id: int,
    before: Mapping[Any, int],
    after: Mapping[Any, int],
    *,
    reason: str,
    destroyed: bool = True,
    ref_kind: str = "",
    ref_id: str = "",
) -> ConsumeResult:
    """Списать лоты по РАЗНИЦЕ инвентаря до/после (зеркало record_inventory_gain)."""

    old = await _canonical_totals_safe(conn, before)
    new = await _canonical_totals_safe(conn, after)
    lost = {}
    for item_id, qty in old.items():
        delta = qty - new.get(item_id, 0)
        if delta > 0:
            lost[item_id] = delta
    if not lost:
        return ConsumeResult()
    return await record_consume_many(
        conn,
        user_id,
        lost,
        reason=reason,
        destroyed=destroyed,
        ref_kind=ref_kind,
        ref_id=ref_id,
    )


async def _canonical_totals_safe(conn, items: Mapping[Any, int]) -> dict[str, int]:
    async def _run():
        return await _canonical_totals(conn, items)

    return await _guarded(
        conn, _run, kind="resolve_failed", user_id=None, item_id="", detail={"mode": "delta"}
    ) or {}


# ---------------------------------------------------------------------------
# Составные сценарии
# ---------------------------------------------------------------------------


async def record_gift(
    conn,
    from_user_id: int,
    to_user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    ref_kind: str = "",
    ref_id: str = "",
) -> ConsumeResult:
    """Подарок: себестоимость копируется из списанных лотов дарителя.

    Именно поэтому цепочка передач разворачивается сама собой — получатель
    сразу получает готовую цену, и при следующей передаче никакой рекурсии
    по предкам не нужно.
    """
    consumed = await record_consume(
        conn,
        from_user_id,
        item_ref,
        quantity,
        reason=REASON_GIFT_SENT,
        destroyed=False,
        ref_kind=ref_kind,
        ref_id=ref_id or str(to_user_id),
    )
    if not consumed.ok:
        # Списание не удалось — у получателя честно неизвестная себестоимость.
        await record_acquire(
            conn,
            to_user_id,
            item_ref,
            quantity,
            unit_cost=None,
            source=SOURCE_GIFT,
            ref_kind=ref_kind,
            ref_id=ref_id or str(from_user_id),
        )
        return consumed
    await record_acquire_parts(
        conn,
        to_user_id,
        item_ref,
        consumed.parts,
        source=SOURCE_GIFT,
        ref_kind=ref_kind,
        ref_id=ref_id or str(from_user_id),
    )
    return consumed


async def record_craft(
    conn,
    user_id: int,
    ingredients: Mapping[Any, int],
    *,
    success: bool,
    result_ref: Any = None,
    result_quantity: int = 1,
    ref_kind: str = "recipe",
    ref_id: str = "",
) -> ConsumeResult:
    """Крафт: ингредиенты списываются всегда, при успехе их стоимость
    целиком переходит в результат.

    Если хоть одна списанная единица была с неизвестной себестоимостью,
    сумма тоже неизвестна — результат получает NULL, а не заниженную цену.
    """
    consumed = await record_consume_many(
        conn,
        user_id,
        ingredients,
        reason=REASON_CRAFT_FAIL if not success else REASON_CRAFT_SPEND,
        destroyed=not success,
        ref_kind=ref_kind,
        ref_id=ref_id,
    )
    if not success or not result_ref:
        return consumed

    result_quantity = max(1, int(result_quantity or 1))
    total = consumed.total_cost
    unit_cost = None if total is None else total // result_quantity
    await record_acquire(
        conn,
        user_id,
        result_ref,
        result_quantity,
        unit_cost=unit_cost,
        source=SOURCE_CRAFT,
        ref_kind=ref_kind,
        ref_id=ref_id,
    )
    return consumed


# ---------------------------------------------------------------------------
# Эскроу биржи: выставленный лот ещё не продан и не уничтожен
# ---------------------------------------------------------------------------


async def escrow_hold(
    conn,
    user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    holder_id: Any,
    holder_kind: str = ESCROW_MARKET_LISTING,
) -> ConsumeResult:
    """Выставление на биржу: предмет ушёл из инвентаря, но не сгорел —
    его себестоимость паркуется до продажи или снятия лота."""
    consumed = await record_consume(
        conn,
        user_id,
        item_ref,
        quantity,
        reason=REASON_MARKET_LIST,
        destroyed=False,
        ref_kind=holder_kind,
        ref_id=str(holder_id),
    )
    if not consumed.ok:
        return consumed

    async def _run():
        item_id = await canonical_item_key(conn, item_ref)
        for part in consumed.parts:
            await conn.execute(
                """
                INSERT INTO item_cost_escrow (
                    holder_kind, holder_id, user_id, item_id, qty_left, unit_cost
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                holder_kind,
                str(holder_id),
                int(user_id),
                item_id,
                int(part.quantity),
                part.unit_cost,
            )
        return True

    await _guarded(
        conn,
        _run,
        kind="escrow_hold_failed",
        user_id=user_id,
        item_id=str(item_ref),
        detail={"quantity": quantity, "holder_kind": holder_kind, "holder_id": str(holder_id)},
    )
    return consumed


async def _escrow_take(conn, holder_kind: str, holder_id: Any, quantity: int) -> list[CostPart]:
    rows = await conn.fetch(
        """
        SELECT id, qty_left, unit_cost
        FROM item_cost_escrow
        WHERE holder_kind = $1 AND holder_id = $2 AND qty_left > 0
        ORDER BY id
        FOR UPDATE
        """,
        holder_kind,
        str(holder_id),
    )
    parts: list[CostPart] = []
    left = int(quantity)
    for row in rows:
        if left <= 0:
            break
        available = int(row["qty_left"])
        take = min(available, left)
        await conn.execute(
            "UPDATE item_cost_escrow SET qty_left = qty_left - $2 WHERE id = $1",
            row["id"],
            take,
        )
        unit_cost = row["unit_cost"]
        parts.append(CostPart(None if unit_cost is None else int(unit_cost), take))
        left -= take
    if left > 0:
        parts.append(CostPart(None, left))
    return _merge_parts(parts)


async def escrow_return(
    conn,
    user_id: int,
    item_ref: Any,
    quantity: int,
    *,
    holder_id: Any,
    holder_kind: str = ESCROW_MARKET_LISTING,
) -> None:
    """Снятие лота с биржи: себестоимость возвращается владельцу как была."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return

    async def _run():
        return await _escrow_take(conn, holder_kind, holder_id, quantity)

    parts = await _guarded(
        conn,
        _run,
        kind="escrow_return_failed",
        user_id=user_id,
        item_id=str(item_ref),
        detail={"quantity": quantity, "holder_kind": holder_kind, "holder_id": str(holder_id)},
    )
    await record_acquire_parts(
        conn,
        user_id,
        item_ref,
        parts if parts is not None else [CostPart(None, quantity)],
        source=SOURCE_MARKET_RETURN,
        ref_kind=holder_kind,
        ref_id=str(holder_id),
    )


async def escrow_settle_sale(
    conn,
    seller_id: int,
    item_ref: Any,
    quantity: int,
    *,
    holder_id: Any,
    holder_kind: str = ESCROW_MARKET_LISTING,
) -> None:
    """Продажа с биржи: у продавца предмет окончательно выбыл (не уничтожен),
    его себестоимость фиксируется в журнале — по ней вкладка заработка
    посчитает реальную прибыль продавца."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return

    async def _run():
        item_id = await canonical_item_key(conn, item_ref)
        parts = await _escrow_take(conn, holder_kind, holder_id, quantity)
        known, unknown, taken = _summarize(parts)
        await _write_burn(
            conn,
            seller_id,
            item_id,
            taken,
            known,
            unknown,
            REASON_MARKET_SOLD,
            False,
            holder_kind,
            str(holder_id),
        )
        return True

    await _guarded(
        conn,
        _run,
        kind="escrow_settle_failed",
        user_id=seller_id,
        item_id=str(item_ref),
        detail={"quantity": quantity, "holder_kind": holder_kind, "holder_id": str(holder_id)},
    )


# ---------------------------------------------------------------------------
# Сверка лотов с фактическим инвентарём
# ---------------------------------------------------------------------------


async def lot_totals(conn, user_id: int) -> dict[str, int]:
    rows = await conn.fetch(
        """
        SELECT item_id, SUM(qty_left)::bigint AS qty
        FROM item_cost_lots
        WHERE user_id = $1 AND qty_left > 0
        GROUP BY item_id
        """,
        int(user_id),
    )
    return {str(r["item_id"]): int(r["qty"] or 0) for r in rows}


async def reconcile_user(conn, user_id: int, inventory: Mapping[Any, int]) -> list[dict]:
    """Сверка: остатки лотов против фактического инвентаря.

    Ничего не чинит — только отдаёт расхождения (нужно и тестам, и будущей
    кнопке в админке). Недобор лотов это норма для предметов, которые уже
    лежали у игрока до появления учёта: такие строки помечены
    legacy_uncovered, а не ошибкой.
    """
    actual: dict[str, int] = {}
    for ref, qty in (inventory or {}).items():
        try:
            qty = int(qty or 0)
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            continue
        key = await canonical_item_key(conn, ref)
        if not key:
            continue
        actual[key] = actual.get(key, 0) + qty

    lots = await lot_totals(conn, user_id)
    report: list[dict] = []
    for item_id in sorted(set(actual) | set(lots)):
        have = actual.get(item_id, 0)
        tracked = lots.get(item_id, 0)
        if have == tracked:
            continue
        report.append(
            {
                "itemId": item_id,
                "inventory": have,
                "lots": tracked,
                "diff": tracked - have,
                "kind": "legacy_uncovered" if tracked < have else "lots_exceed_inventory",
            }
        )
    return report


async def reconcile_and_report(conn, user_id: int, inventory: Mapping[Any, int]) -> list[dict]:
    """Сверка + запись настоящих расхождений (лотов больше, чем предметов)
    в item_cost_anomalies, чтобы их было видно без ручного запуска."""
    report = await reconcile_user(conn, user_id, inventory)
    for row in report:
        if row["kind"] != "lots_exceed_inventory":
            continue
        await _record_anomaly(conn, "reconcile_drift", user_id, row["itemId"], row)
    return report
