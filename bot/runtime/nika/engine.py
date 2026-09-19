# -*- coding: utf-8 -*-
"""Ника: тик, атомарный перевод кут и самолечение сломанных операций.

Почему цикл живёт в процессе бота. add_to_chatbalance / minus пишут
fastlane-кэш в памяти этого процесса. Прямой UPDATE chat со стороны
FastAPI оставил бы игры со старым балансом и неверными выплатами.
Здесь деньги двигаются одним SQL-транзакционным блоком (списание и
зачисление либо оба, либо ни одного), после чего кэш обоих чатов
сбрасывается.

Самолечение на каждом тике:
  • зависший pending старше 2 минут помечается failed — куты не
    докручиваются второй раз, потому что перевод шёл в той же транзакции,
    что и строка журнала, и при обрыве откатился;
  • refund_failed пробует вернуть куты источнику ещё раз;
  • ручной откат из журнала проводится тем же атомарным путём;
  • нет строки chat у получателя — создаём её и повторяем;
  • нет таблицы — поднимаем схему и повторяем тик один раз;
  • источник пуст — берём следующий в лестнице;
  • все источники пусты — одно письмо владельцу с цифрами, не чаще кулдауна.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

import asyncpg

import bot.runtime.nika.incidents as incidents
import bot.runtime.nika.store as store
from bot.runtime.nika.policy import (
    SOURCE_LADDER,
    apply_sweep_speed,
    allocate_from_ladder,
    pick_sweep_dest,
    plan_sweep,
    plan_topup,
)
from bot.runtime.nika.schema import ensure_nika_schema
from bot.runtime.nika.store import policy_from_row

_TAG = "[NIKA]"


@dataclass
class MoveResult:
    ok: bool
    status: str
    amount: int = 0
    log_id: Optional[int] = None
    source_before: Optional[int] = None
    source_after: Optional[int] = None
    dest_before: Optional[int] = None
    dest_after: Optional[int] = None
    error: str = ""


def _slot(cooldown_sec: int) -> int:
    import time

    step = max(8, int(cooldown_sec or 8))
    return int(time.time()) // step


def idem_key(kind: str, chat_id: int, source: int, dest: int, cooldown_sec: int, extra: str = "") -> str:
    base = f"{kind}:{int(chat_id)}:{int(source)}:{int(dest)}:{_slot(cooldown_sec)}"
    return f"{base}:{extra}" if extra else base


def _print(msg: str) -> None:
    print(f"{_TAG} {msg}")


async def _chat_balance(db, bot, chat_id: int) -> int:
    try:
        return int(await db.get_chat_balance(bot, chat_id) or 0)
    except Exception as exc:
        _print(f"balance read fail chat={chat_id}: {type(exc).__name__}: {exc}")
        return 0


async def _ensure_chat_row(db, bot, chat_id: int) -> None:
    ensure = getattr(db, "__ensure_chatrow_exists__", None)
    if ensure is None:
        return
    try:
        await ensure(bot, int(chat_id))
    except Exception as exc:
        _print(f"ensure chat row fail chat={chat_id}: {type(exc).__name__}: {exc}")


async def _atomic_move(
    db,
    bot,
    *,
    kind: str,
    chat_id: int,
    source: int,
    dest: int,
    amount: int,
    reason: str,
    speed_mode: str = "",
    activity_tier: str = "",
    target_balance: int = 0,
    cooldown_sec: int = 180,
    extra_key: str = "",
    dry_run: bool = False,
) -> MoveResult:
    amount = int(amount)
    source = int(source)
    dest = int(dest)
    if amount <= 0 or source == dest:
        return MoveResult(False, "failed", error="invalid_move")

    await _ensure_chat_row(db, bot, source)
    await _ensure_chat_row(db, bot, dest)

    key = idem_key(kind, chat_id, source, dest, cooldown_sec, extra_key)
    first, second = (source, dest) if source < dest else (dest, source)

    if dry_run:
        src_before = await _chat_balance(db, bot, source)
        dst_before = await _chat_balance(db, bot, dest)
        async with db.pool.acquire() as conn:
            log_id = await conn.fetchval(
                """
                INSERT INTO nika_transfer_log (
                    idem_key, kind, chat_id, source_chat_id, dest_chat_id, amount,
                    status, reason, speed_mode, activity_tier, target_balance,
                    source_balance_before, dest_balance_before, finished_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6,
                    'dry_run', $7, $8, $9, $10,
                    $11, $12, NOW()
                )
                ON CONFLICT (idem_key) DO NOTHING
                RETURNING id
                """,
                key, kind, int(chat_id), source, dest, amount,
                reason[:500], speed_mode, activity_tier, int(target_balance),
                src_before, dst_before,
            )
        return MoveResult(True, "dry_run", amount=amount, log_id=log_id,
                          source_before=src_before, dest_before=dst_before)

    try:
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    SELECT chat_id FROM chat
                    WHERE chat_id = ANY($1::bigint[])
                    ORDER BY chat_id
                    FOR UPDATE
                    """,
                    [first, second],
                )
                src_row = await conn.fetchrow(
                    "SELECT COALESCE(chatbalance, 0)::bigint AS b FROM chat WHERE chat_id = $1",
                    source,
                )
                dst_row = await conn.fetchrow(
                    "SELECT COALESCE(chatbalance, 0)::bigint AS b FROM chat WHERE chat_id = $1",
                    dest,
                )
                if src_row is None:
                    raise RuntimeError(f"source_missing:{source}")
                if dst_row is None:
                    raise RuntimeError(f"dest_missing:{dest}")
                src_before = int(src_row["b"] or 0)
                dst_before = int(dst_row["b"] or 0)
                if src_before < amount:
                    raise RuntimeError(f"insufficient:{src_before}<{amount}")

                log_id = await conn.fetchval(
                    """
                    INSERT INTO nika_transfer_log (
                        idem_key, kind, chat_id, source_chat_id, dest_chat_id, amount,
                        status, reason, speed_mode, activity_tier, target_balance,
                        source_balance_before, dest_balance_before
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6,
                        'pending', $7, $8, $9, $10,
                        $11, $12
                    )
                    RETURNING id
                    """,
                    key, kind, int(chat_id), source, dest, amount,
                    reason[:500], speed_mode, activity_tier, int(target_balance),
                    src_before, dst_before,
                )
                src_after_row = await conn.fetchrow(
                    """
                    UPDATE chat
                    SET chatbalance = chatbalance - $1
                    WHERE chat_id = $2 AND chatbalance >= $1
                    RETURNING COALESCE(chatbalance, 0)::bigint AS b
                    """,
                    amount, source,
                )
                if src_after_row is None:
                    raise RuntimeError("source_update_missed")
                dst_after_row = await conn.fetchrow(
                    """
                    UPDATE chat
                    SET chatbalance = chatbalance + $1
                    WHERE chat_id = $2
                    RETURNING COALESCE(chatbalance, 0)::bigint AS b
                    """,
                    amount, dest,
                )
                if dst_after_row is None:
                    raise RuntimeError("dest_update_missed")
                src_after = int(src_after_row["b"] or 0)
                dst_after = int(dst_after_row["b"] or 0)
                await conn.execute(
                    """
                    UPDATE nika_transfer_log
                    SET status = 'done',
                        source_balance_after = $2,
                        dest_balance_after = $3,
                        finished_at = NOW()
                    WHERE id = $1
                    """,
                    int(log_id), src_after, dst_after,
                )
    except asyncpg.UniqueViolationError:
        return MoveResult(True, "already_done", amount=amount, error="idempotent")
    except Exception as exc:
        _print(f"move fail {kind} {source}->{dest} {amount}: {type(exc).__name__}: {exc}")
        return MoveResult(False, "failed", amount=amount, error=f"{type(exc).__name__}:{exc}")

    try:
        db.invalidate_balance_cache(source)
        db.invalidate_balance_cache(dest)
    except Exception as exc:
        _print(f"cache invalidate fail: {type(exc).__name__}: {exc}")

    _print(f"{kind} {amount} {source}->{dest} log={log_id} src {src_before}->{src_after} dst {dst_before}->{dst_after}")
    try:
        from bot.funcs.tech_plus import announce_tech_plus

        await announce_tech_plus(bot, dest, amount, reason=kind)
    except Exception as plus_exc:
        _print(f"tech plus fail: {type(plus_exc).__name__}: {plus_exc}")
    return MoveResult(
        True, "done", amount=amount, log_id=int(log_id),
        source_before=src_before, source_after=src_after,
        dest_before=dst_before, dest_after=dst_after,
    )


async def _mark_status(conn, log_id: int, status: str, error: str = "") -> None:
    await conn.execute(
        """
        UPDATE nika_transfer_log
        SET status = $2,
            error = $3,
            finished_at = NOW()
        WHERE id = $1
        """,
        int(log_id),
        status,
        (error or "")[:1000],
    )


async def _heal_one(db, bot, row: Any, dry_run: bool) -> str:
    status = str(row["status"] or "")
    log_id = int(row["id"])
    amount = int(row["amount"] or 0)
    source = int(row["source_chat_id"])
    dest = int(row["dest_chat_id"])
    chat_id = int(row["chat_id"])
    kind = str(row["kind"] or "")

    if status == "pending":
        # Перевод шёл в одной транзакции с журналом. Зависшая pending-строка
        # значит: либо чужой протокол, либо запись вставили без денег.
        # Деньги второй раз не двигаем.
        async with db.pool.acquire() as conn:
            await _mark_status(conn, log_id, "failed", "stale_pending_abandoned")
        _print(f"heal pending#{log_id} -> failed (без движения кут)")
        return "pending_abandoned"

    if status == "refund_failed" or (
        row["revert_requested_at"] is not None and row["reverted_at"] is None and status == "done"
    ):
        reverse_kind = "revert"
        moved = await _atomic_move(
            db, bot,
            kind=reverse_kind,
            chat_id=chat_id,
            source=dest,
            dest=source,
            amount=amount,
            reason=f"heal/revert of #{log_id} ({kind})",
            cooldown_sec=60,
            extra_key=f"heal{log_id}",
            dry_run=dry_run,
        )
        async with db.pool.acquire() as conn:
            if moved.ok and moved.status in ("done", "dry_run", "already_done"):
                await conn.execute(
                    """
                    UPDATE nika_transfer_log
                    SET reverted_at = NOW(),
                        revert_transfer_id = $2,
                        status = CASE WHEN status = 'refund_failed' THEN 'refunded' ELSE status END
                    WHERE id = $1
                    """,
                    log_id,
                    moved.log_id,
                )
                if moved.log_id:
                    await conn.execute(
                        "UPDATE nika_transfer_log SET reverts_transfer_id = $2 WHERE id = $1",
                        moved.log_id,
                        log_id,
                    )
                await _resolve_refund(db, log_id)
                return "healed"
            await conn.execute(
                """
                UPDATE nika_transfer_log
                SET status = CASE WHEN status = 'done' THEN status ELSE 'refund_failed' END,
                    error = $2
                WHERE id = $1
                """,
                log_id,
                (moved.error or "heal_failed")[:1000],
            )
        await _raise_refund_stuck(db, row, moved.error or "heal_failed")
        return "heal_failed"
    return "skipped"


async def heal_broken(db, bot, *, dry_run: bool) -> Dict[str, int]:
    stats = {"seen": 0, "healed": 0, "failed": 0, "abandoned": 0}
    try:
        async with db.pool.acquire() as conn:
            rows = await store.fetch_heal_rows(conn)
    except Exception as exc:
        _print(f"heal fetch fail: {type(exc).__name__}: {exc}")
        return stats
    for row in rows:
        stats["seen"] += 1
        try:
            result = await _heal_one(db, bot, row, dry_run)
        except Exception as exc:
            stats["failed"] += 1
            _print(f"heal row {row['id']} fail: {type(exc).__name__}: {exc}")
            continue
        if result == "healed":
            stats["healed"] += 1
        elif result == "pending_abandoned":
            stats["abandoned"] += 1
        elif result == "heal_failed":
            stats["failed"] += 1
    return stats


def _ladder_lines(snapshot: Dict[int, int]) -> str:
    lines = []
    for chat_id, title in SOURCE_LADDER:
        lines.append(f"• {title} ({chat_id}): {int(snapshot.get(chat_id, 0))} кут")
    return "\n".join(lines)


def _payload_dict(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
        except Exception:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


async def _raise_empty_ladder(
    db,
    group_chat_id: int,
    need: int,
    snapshot: Dict[int, int],
    *,
    balance: int = 0,
    moved: int = 0,
) -> None:
    dry = int(balance or 0) <= 0
    title = (
        "НЕТ КУТ: группа под Никой пуста"
        if dry
        else "В играх и кассах пусто — доливать баланс группы не из чего"
    )
    body = (
        f"Группа {group_chat_id}: баланс {int(balance)} кут, не хватает ещё {int(need)}.\n"
        f"Уже долито в этом шаге: {int(moved)}.\n\n"
        f"{_ladder_lines(snapshot)}\n\n"
        "Ника уже обошла игры и кассы и нигде не нашла кут. "
        "Сама эту дыру закрыть не может — нужны кнопка долива, пауза или пополнение касс."
    )
    async with db.pool.acquire() as conn:
        await incidents.raise_incident(
            conn,
            code=incidents.CODE_EMPTY_LADDER,
            fingerprint=incidents.fingerprint_empty_ladder(group_chat_id),
            title=title,
            body=body,
            chat_id=group_chat_id,
            payload={
                "need": int(need),
                "balance": int(balance),
                "moved": int(moved),
                "ladder": {str(k): int(v) for k, v in snapshot.items()},
            },
        )


async def _resolve_empty_ladder(db, group_chat_id: int, note: str = "") -> None:
    try:
        async with db.pool.acquire() as conn:
            await incidents.resolve_fingerprint(
                conn,
                incidents.fingerprint_empty_ladder(group_chat_id),
                note=note or "долив прошёл",
            )
    except Exception as exc:
        _print(f"resolve empty_ladder fail: {type(exc).__name__}: {exc}")


async def _raise_refund_stuck(db, row: Any, error: str) -> None:
    log_id = int(row["id"])
    async with db.pool.acquire() as conn:
        await incidents.raise_incident(
            conn,
            code=incidents.CODE_REFUND_STUCK,
            fingerprint=incidents.fingerprint_refund(log_id),
            title="Застрял возврат кут",
            body=(
                f"Перевод #{log_id}: {int(row['amount'])} кут "
                f"{int(row['dest_chat_id'])} → {int(row['source_chat_id'])} вернуть не удалось.\n"
                f"{error}\n\n"
                "Автоматика уже пробовала откат. Если куты уже потрачены на стороне получателя, "
                "кнопка «Вернуть» не создаст новые — она спишет только то, что ещё лежит."
            ),
            chat_id=int(row["chat_id"]),
            payload={
                "log_id": log_id,
                "amount": int(row["amount"] or 0),
                "source": int(row["source_chat_id"]),
                "dest": int(row["dest_chat_id"]),
                "error": str(error)[:400],
            },
        )


async def _resolve_refund(db, log_id: int) -> None:
    try:
        async with db.pool.acquire() as conn:
            await incidents.resolve_fingerprint(
                conn,
                incidents.fingerprint_refund(int(log_id)),
                note="откат прошёл",
            )
            await incidents.resolve_fingerprint(
                conn,
                incidents.fingerprint_transfer(int(log_id)),
                note="откат прошёл",
            )
    except Exception as exc:
        _print(f"resolve refund fail: {type(exc).__name__}: {exc}")


async def _alert_empty_ladder(db, bot, settings: Dict[str, Any], group_chat_id: int, need: int, snapshot: Dict[int, int]) -> None:
    user_id = await _claim_alert(db, settings)
    if not user_id or bot is None:
        return
    lines = [
        "Ника: в играх и кассах пусто, пополнить баланс группы нечем.",
        f"Группа {group_chat_id}: не хватает ещё {need} кут.",
        "",
        _ladder_lines(snapshot),
        "",
        "Это серьёзно: игроки продолжат играть, а доливать баланс группы не из чего. Смотри вкладку Ника в админке.",
    ]
    try:
        await bot.send_message(int(user_id), "\n".join(lines))
    except Exception as exc:
        _print(f"owner alert fail: {type(exc).__name__}: {exc}")


async def _claim_alert(db, settings: Dict[str, Any]) -> Optional[int]:
    try:
        async with db.pool.acquire() as conn:
            return await store.try_owner_alert(conn, int(settings.get("owner_alert_cooldown_sec") or 21600))
    except Exception as exc:
        _print(f"alert claim fail: {type(exc).__name__}: {exc}")
        return None


async def _topup_group(
    db, bot, *, policy, balance: int, settings: Dict[str, Any], dry_run: bool,
    skip_cooldown: bool = False,
) -> str:
    async with db.pool.acquire() as conn:
        events = await store.ledger_events_24h(conn, policy.chat_id)
        drain = await store.drain_per_hour(conn, policy.chat_id)
        daily = await store.daily_done_sum(conn, policy.chat_id, "topup")
        plan = plan_topup(
            policy,
            balance=balance,
            events_24h=events,
            drain_per_hour=drain,
            daily_topup_used=daily,
        )
        if plan.amount <= 0:
            return plan.skip or "none"
        if skip_cooldown:
            await store.force_touch_group_action(conn, policy.chat_id, "topup")
        else:
            claimed = await store.claim_group_action(conn, policy.chat_id, "topup", plan.cooldown_sec)
            if not claimed:
                return "cooldown"

    ladder_ids = [cid for cid, _ in SOURCE_LADDER if cid != policy.chat_id]
    async with db.pool.acquire() as conn:
        snapshot = await store.fetch_balances(conn, ladder_ids)
    available = tuple((cid, int(snapshot.get(cid, 0))) for cid, _ in SOURCE_LADDER if cid != policy.chat_id)
    takes, leftover = allocate_from_ladder(plan.amount, available)
    if not takes:
        await _raise_empty_ladder(db, policy.chat_id, plan.amount, snapshot, balance=balance)
        await _alert_empty_ladder(db, bot, settings, policy.chat_id, plan.amount, snapshot)
        return "empty_ladder"

    moved_total = 0
    for source, take in takes:
        result = await _atomic_move(
            db, bot,
            kind="topup",
            chat_id=policy.chat_id,
            source=source,
            dest=policy.chat_id,
            amount=take,
            reason=plan.reason if not skip_cooldown else f"ручной долив: {plan.reason}",
            speed_mode=policy.speed_mode,
            activity_tier=plan.tier,
            target_balance=policy.target_balance,
            cooldown_sec=60 if skip_cooldown else plan.cooldown_sec,
            extra_key=f"force{source}" if skip_cooldown else str(source),
            dry_run=dry_run,
        )
        if result.ok and result.status in ("done", "dry_run", "already_done"):
            moved_total += take
        elif result.error.startswith("insufficient"):
            continue

    if leftover > 0 or moved_total < plan.amount:
        async with db.pool.acquire() as conn:
            snapshot = await store.fetch_balances(conn, ladder_ids)
        if all(int(snapshot.get(cid, 0)) <= 0 for cid, _ in SOURCE_LADDER if cid != policy.chat_id):
            await _raise_empty_ladder(
                db, policy.chat_id, plan.amount - moved_total, snapshot,
                balance=balance, moved=moved_total,
            )
            await _alert_empty_ladder(db, bot, settings, policy.chat_id, plan.amount - moved_total, snapshot)
            return "partial_empty"
        if moved_total > 0:
            return "partial"
        return "partial"
    await _resolve_empty_ladder(db, policy.chat_id, "долив закрыл этот шаг")
    return "topup"


async def _sweep_group(
    db, bot, *, policy, balance: int, dry_run: bool, skip_cooldown: bool = False,
    sweep_speed: str = "fast",
) -> str:
    policy = apply_sweep_speed(policy, sweep_speed)
    async with db.pool.acquire() as conn:
        window = await store.sweep_window(conn, policy.chat_id, policy.sweep_delay_sec)
        daily = await store.daily_done_sum(conn, policy.chat_id, "sweep")
        plan = plan_sweep(
            policy,
            balance=balance,
            stable_balance=window["stable_balance"],
            history_covers_delay=True if skip_cooldown else bool(window["covers"]),
            daily_sweep_used=daily,
        )
        if skip_cooldown and plan.amount <= 0:
            # Ручной сбор: если выдержки ещё нет, берём текущий излишек
            # теми же потолками, но без ожидания окна.
            from bot.runtime.nika.policy import sweep_keep
            target = int(max(0, policy.target_balance))
            excess = int(balance) - target
            keep = sweep_keep(policy)
            if excess > keep and target > 0:
                plan = plan_sweep(
                    policy,
                    balance=balance,
                    stable_balance=int(balance),
                    history_covers_delay=True,
                    daily_sweep_used=daily,
                )
        if plan.amount <= 0:
            return plan.skip or "none"
        if skip_cooldown:
            await store.force_touch_group_action(conn, policy.chat_id, "sweep")
        else:
            claimed = await store.claim_group_action(conn, policy.chat_id, "sweep", plan.cooldown_sec)
            if not claimed:
                return "cooldown"

    dest = pick_sweep_dest(policy.chat_id)
    if dest is None or dest == int(policy.chat_id):
        return "self"
    result = await _atomic_move(
        db, bot,
        kind="sweep",
        chat_id=policy.chat_id,
        source=policy.chat_id,
        dest=dest,
        amount=plan.amount,
        reason=plan.reason if not skip_cooldown else f"ручной сбор: {plan.reason}",
        speed_mode=policy.speed_mode,
        activity_tier=plan.tier,
        target_balance=policy.target_balance,
        cooldown_sec=60 if skip_cooldown else plan.cooldown_sec,
        extra_key="force" if skip_cooldown else "",
        dry_run=dry_run,
    )
    return "sweep" if result.ok else (result.error or "sweep_fail")


async def _service_group(
    db, bot, row: Any, settings: Dict[str, Any], dry_run: bool,
    *, skip_cooldown: bool = False, force_kind: str = "",
) -> str:
    policy = policy_from_row(row)
    sweep_speed = str((settings or {}).get("sweep_speed") or "fast")
    policy = apply_sweep_speed(policy, sweep_speed)
    if policy.chat_id in set(store.forbidden_managed_ids()):
        return "forbidden"
    balance = await _chat_balance(db, bot, policy.chat_id)
    try:
        async with db.pool.acquire() as conn:
            await store.insert_sample(conn, policy.chat_id, balance, policy.target_balance)
    except Exception as exc:
        _print(f"sample fail chat={policy.chat_id}: {type(exc).__name__}: {exc}")

    target = int(policy.target_balance)
    want = str(force_kind or "")
    if want == "topup" or (not want and balance < target):
        action = await _topup_group(
            db, bot, policy=policy, balance=balance, settings=settings,
            dry_run=dry_run, skip_cooldown=skip_cooldown,
        )
        if action == "topup":
            await _resolve_empty_ladder(db, policy.chat_id)
        return action
    if want == "sweep" or (not want and balance > target):
        return await _sweep_group(
            db, bot, policy=policy, balance=balance, dry_run=dry_run,
            skip_cooldown=skip_cooldown, sweep_speed=sweep_speed,
        )
    if want:
        return "on_target"
    return "on_target"


async def _execute_operator_command(db, bot, row: Any, settings: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    kind = str(row["kind"] or "")
    payload = _payload_dict(row["payload"])
    chat_id = payload.get("chat_id") or payload.get("chatId")
    transfer_id = payload.get("transfer_id") or payload.get("log_id") or payload.get("transferId")

    if kind == "force_tick":
        return {"action": "force_tick"}

    if kind == "retry_heal":
        heal = await heal_broken(db, bot, dry_run=dry_run)
        return {"action": "retry_heal", "heal": heal}

    if kind == "pause_all":
        await store.disable_system(db)
        return {"action": "pause_all"}

    if kind == "enable_all":
        await store.enable_system(db)
        return {"action": "enable_all"}

    if kind == "pause_group":
        if chat_id is None:
            raise RuntimeError("chat_id required")
        await store.disable_group(db, int(chat_id))
        return {"action": "pause_group", "chat_id": int(chat_id)}

    if kind == "enable_group":
        if chat_id is None:
            raise RuntimeError("chat_id required")
        await store.enable_group(db, int(chat_id))
        return {"action": "enable_group", "chat_id": int(chat_id)}

    if kind == "revert":
        if transfer_id is None:
            raise RuntimeError("transfer_id required")
        requested_by = int(row["requested_by"] or 0)
        ok = await store.request_revert(db, int(transfer_id), requested_by)
        heal = await heal_broken(db, bot, dry_run=dry_run)
        return {"action": "revert", "queued": ok, "heal": heal}

    if kind in ("force_topup", "force_sweep"):
        if chat_id is None:
            raise RuntimeError("chat_id required")
        async with db.pool.acquire() as conn:
            group = await store.fetch_group_row(conn, int(chat_id))
        if group is None:
            raise RuntimeError("group_not_managed")
        action = await _service_group(
            db, bot, group, settings, dry_run,
            skip_cooldown=True,
            force_kind="topup" if kind == "force_topup" else "sweep",
        )
        return {"action": kind, "chat_id": int(chat_id), "result": action}

    raise RuntimeError(f"unknown_command:{kind}")


async def process_operator_commands(db, bot, settings: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"processed": 0, "failed": 0, "force_tick": False, "actions": []}
    try:
        async with db.pool.acquire() as conn:
            rows = await store.claim_commands(conn)
    except Exception as exc:
        _print(f"claim commands fail: {type(exc).__name__}: {exc}")
        return summary

    for row in rows:
        summary["processed"] += 1
        try:
            result = await _execute_operator_command(db, bot, row, settings, dry_run)
            async with db.pool.acquire() as conn:
                await store.finish_command(conn, int(row["id"]), ok=True, result=result)
            if str(row["kind"]) == "force_tick" or result.get("action") == "force_tick":
                summary["force_tick"] = True
            summary["actions"].append(result)
        except Exception as exc:
            summary["failed"] += 1
            _print(f"command #{row['id']} {row['kind']} fail: {type(exc).__name__}: {exc}")
            try:
                async with db.pool.acquire() as conn:
                    await store.finish_command(
                        conn, int(row["id"]), ok=False, error=f"{type(exc).__name__}:{exc}",
                    )
            except Exception as inner:
                _print(f"finish command fail: {type(inner).__name__}: {inner}")
    return summary


async def run_tick(db, bot, *, force: bool = False, _retried: bool = False) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"ok": False, "actions": [], "heal": {}, "commands": {}, "error": "", "tick_interval_sec": 20}
    if not getattr(db, "pool", None):
        summary["error"] = "no_pool"
        return summary

    try:
        async with db.pool.acquire() as conn:
            settings = await store.fetch_settings(conn) or {}
            dry_run = bool(settings.get("dry_run"))
            summary["tick_interval_sec"] = int(settings.get("tick_interval_sec") or 20)
        # Команды с кнопок и самолечение — каждый заход, даже если долив
        # ещё рано или система на паузе. Деньги иначе зависнут.
        summary["commands"] = await process_operator_commands(db, bot, settings, dry_run)
        summary["heal"] = await heal_broken(db, bot, dry_run=dry_run)
        if summary["commands"].get("force_tick"):
            force = True

        claimed = None
        if settings.get("enabled"):
            if force:
                claimed = settings
                try:
                    async with db.pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE nika_settings SET last_tick_at = NOW(), updated_at = NOW() WHERE id = 1"
                        )
                except Exception as exc:
                    _print(f"force tick stamp fail: {type(exc).__name__}: {exc}")
            else:
                async with db.pool.acquire() as conn:
                    claimed = await store.claim_tick(conn)
    except asyncpg.UndefinedTableError:
        if _retried:
            summary["error"] = "schema_missing"
            return summary
        _print("schema missing — поднимаю и повторяю тик")
        await ensure_nika_schema(db)
        return await run_tick(db, bot, force=force, _retried=True)
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}:{exc}"
        _print(f"tick claim fail: {summary['error']}")
        return summary

    if not claimed:
        summary["ok"] = True
        summary["error"] = "skipped" if settings.get("enabled") else "disabled"
        try:
            await store.maybe_sample_universe(db)
        except Exception as exc:
            _print(f"universe sample fail: {type(exc).__name__}: {exc}")
        return summary

    dry_run = bool(claimed.get("dry_run"))
    try:
        async with db.pool.acquire() as conn:
            groups = await store.fetch_enabled_groups(conn)
        for row in groups:
            try:
                action = await _service_group(db, bot, row, claimed, dry_run)
            except Exception as exc:
                action = f"error:{type(exc).__name__}"
                _print(f"group {row['chat_id']} fail: {type(exc).__name__}: {exc}")
            summary["actions"].append({"chat_id": int(row["chat_id"]), "action": action})
        if int(claimed.get("heal_ok_streak") or 0) % 20 == 0:
            async with db.pool.acquire() as conn:
                await store.prune_samples(conn)
                await store.prune_universe(conn)
        async with db.pool.acquire() as conn:
            await store.record_tick_ok(conn)
        summary["ok"] = True
        try:
            await store.maybe_sample_universe(db)
        except Exception as exc:
            _print(f"universe sample fail: {type(exc).__name__}: {exc}")
        return summary
    except asyncpg.UndefinedTableError:
        if _retried:
            summary["error"] = "schema_missing"
            return summary
        await ensure_nika_schema(db)
        return await run_tick(db, bot, force=True, _retried=True)
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}:{exc}"
        _print(f"tick fail: {summary['error']}\n{traceback.format_exc()}")
        try:
            async with db.pool.acquire() as conn:
                await store.record_tick_error(conn, summary["error"])
        except Exception as inner:
            _print(f"record error fail: {type(inner).__name__}: {inner}")
        return summary
