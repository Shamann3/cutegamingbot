"""
Проверка таймера выводов на живой БД.

Главное свойство, которое проверяем: таймер ставится РОВНО ОДИН РАЗ - в момент,
когда вывод исчерпал лимит, - и после истечения не появляется заново сам собой.

Работаем на отдельном синтетическом user_id, который создаём и удаляем целиком,
поэтому на реальные данные тест не влияет.

Запуск:  python tests/test_withdraw_cooldown.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bot" / "db_create"))

from bot.config.db_config import bootstrap_database_env

bootstrap_database_env()

from bot.db_create.db import Database, db, WITHDRAW_DEFAULT_COOLDOWN_SEC

UID = 900000000001  # невозможный telegram id -> с реальными пользователями не пересечётся
LIMIT = 100
BALANCE = 1000

_failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "OK  " if ok else "ПРОВАЛ"
    print(f"[{mark}] {name}" + (f" -> {detail}" if detail else ""))
    if not ok:
        _failures.append(f"{name}: {detail}")


async def cleanup(db: Database) -> None:
    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM withdraw_cooldown WHERE user_id=$1", UID)
        await conn.execute("DELETE FROM withdraw_quota_window WHERE user_id=$1", UID)
        await conn.execute("DELETE FROM withdraw_log WHERE user_id=$1", UID)
        await conn.execute("DELETE FROM withdraw_limits WHERE user_id=$1", UID)
        await conn.execute("DELETE FROM users WHERE user_id=$1", UID)


async def prepare(db: Database) -> None:
    await cleanup(db)
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, balance, canwithdrawal)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE
              SET balance = EXCLUDED.balance,
                  canwithdrawal = EXCLUDED.canwithdrawal
            """,
            UID, BALANCE, LIMIT,
        )


async def cooldown_row(db: Database):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT started_at, until_at, cause FROM withdraw_cooldown WHERE user_id=$1", UID)


async def window_row(db: Database):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT window_started_at, used_in_window, daily_limit, remaining, status
            FROM withdraw_quota_window WHERE user_id=$1
            """, UID)


async def expire_cooldown(db: Database) -> None:
    """Сдвигаем конец таймера в прошлое - имитируем 'таймер отбыт'."""
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE withdraw_cooldown SET until_at = NOW() - INTERVAL '2 seconds' WHERE user_id=$1", UID)


# ============================================================
async def scenario_1_arm_once(db: Database) -> None:
    print("\n--- 1. Вывод, исчерпавший лимит, ставит ровно один таймер ---")
    await prepare(db)

    res = await db.add_withdraw_strict(
        user_id=UID, amount=LIMIT, request_id="t1-exhaust", reason="test")
    check("вывод зафиксирован", bool(res.get("ok") and res.get("committed")), str(res.get("status")))
    check("таймер поставлен выводом", bool(res.get("cooldown_set")), f"cooldown_set={res.get('cooldown_set')}")

    row = await cooldown_row(db)
    check("строка таймера существует", row is not None)
    if row:
        check("причина - исчерпание лимита", str(row["cause"]).startswith("daily_limit"), str(row["cause"]))

    left = int(res.get("cooldown_left") or 0)
    check(
        "срок таймера равен настроенному",
        abs(left - WITHDRAW_DEFAULT_COOLDOWN_SEC) <= 5,
        f"осталось {left}s, ожидалось ~{WITHDRAW_DEFAULT_COOLDOWN_SEC}s",
    )


async def scenario_2_renders_do_not_restart(db: Database) -> None:
    print("\n--- 2. Открытие экрана не перезапускает и не продлевает таймер ---")
    row0 = await cooldown_row(db)
    until0 = row0["until_at"] if row0 else None
    started0 = row0["started_at"] if row0 else None

    lefts = []
    for _ in range(5):
        st = await db.refresh_withdraw_quota_if_needed(UID)
        lefts.append(int(st.get("cooldown_left") or 0))
        check_allowed = bool(st.get("allowed"))
        if check_allowed:
            check("экран показывает блокировку", False, f"allowed={check_allowed} state={st}")

    row1 = await cooldown_row(db)
    check("таймер не пересоздан", row1 is not None and row1["until_at"] == until0,
          f"until_at было {until0}, стало {row1['until_at'] if row1 else None}")
    check("начало таймера не сдвинулось", row1 is not None and row1["started_at"] == started0)
    check("остаток не растёт", all(lefts[i] >= lefts[i + 1] for i in range(len(lefts) - 1)), str(lefts))


async def scenario_3_expiry_frees_limit(db: Database) -> None:
    print("\n--- 3. После истечения лимит свободен, новый таймер не появляется ---")
    await expire_cooldown(db)

    st = await db.refresh_withdraw_quota_if_needed(UID)
    check("вывод снова разрешён", bool(st.get("allowed")), str(st))
    check("лимит восстановлен полностью", int(st.get("remaining") or 0) == LIMIT, f"remaining={st.get('remaining')}")
    check("таймер не показывается", int(st.get("cooldown_left") or 0) == 0, f"left={st.get('cooldown_left')}")
    check("строка таймера удалена", (await cooldown_row(db)) is None)

    for i in range(5):
        st = await db.refresh_withdraw_quota_if_needed(UID)
        if not st.get("allowed") or (await cooldown_row(db)) is not None:
            check(f"повторное открытие экрана #{i + 1} не вернуло таймер", False, str(st))
            return
    check("5 повторных открытий экрана таймер не вернули", True)


async def scenario_4_heals_stuck_state(db: Database) -> None:
    print("\n--- 4. Застрявшее состояние (лимит выбран, таймера нет) лечится без нового таймера ---")
    await prepare(db)

    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO withdraw_quota_window(
                user_id, window_started_at, used_in_window, daily_limit, remaining,
                used_percent, status, cooldown_left_sec, cooldown_until, updated_at)
            VALUES ($1, NOW() - INTERVAL '1 hour', $2, $2, 0, 100, 'LIMIT_REACHED', 0, NULL, NOW())
            ON CONFLICT (user_id) DO UPDATE
              SET window_started_at = NOW() - INTERVAL '1 hour',
                  used_in_window = EXCLUDED.used_in_window,
                  daily_limit = EXCLUDED.daily_limit,
                  remaining = 0,
                  status = 'LIMIT_REACHED'
            """, UID, LIMIT)
        await conn.execute(
            """
            INSERT INTO withdraw_log(user_id, amount, reason, created_at, request_id)
            VALUES ($1, $2, 'test-stuck', NOW() - INTERVAL '30 minutes', 't4-stuck')
            """, UID, LIMIT)

    st = await db.refresh_withdraw_quota_if_needed(UID)
    check("окно переведено, вывод разрешён", bool(st.get("allowed")), str(st))
    check("лимит доступен целиком", int(st.get("remaining") or 0) == LIMIT, f"remaining={st.get('remaining')}")
    check("новый таймер НЕ поставлен", (await cooldown_row(db)) is None)


async def scenario_5_guard_refuses(db: Database) -> None:
    print("\n--- 5. Прямая постановка таймера отклоняется, пока лимит не исчерпан ---")
    st = await db.refresh_withdraw_quota_if_needed(UID)
    check("лимит доступен перед проверкой", int(st.get("remaining") or 0) > 0, str(st))

    ok = await db.start_user_withdraw_cooldown(UID, WITHDRAW_DEFAULT_COOLDOWN_SEC, "daily_limit")
    check("метод вернул отказ", ok is False, f"вернул {ok!r}")
    check("строка таймера не создана", (await cooldown_row(db)) is None)


async def scenario_6_obsolete_cause_cleared(db: Database) -> None:
    print("\n--- 6. Устаревший таймер 'нет подарков под лимит' снимается сам ---")
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO withdraw_cooldown(user_id, started_at, until_at, cause)
            VALUES ($1, NOW(), NOW() + INTERVAL '3 hours', 'no_available_gifts')
            ON CONFLICT (user_id) DO UPDATE
              SET started_at = EXCLUDED.started_at,
                  until_at = EXCLUDED.until_at,
                  cause = EXCLUDED.cause
            """, UID)

    st = await db.refresh_withdraw_quota_if_needed(UID)
    check("вывод разблокирован", bool(st.get("allowed")), str(st))
    check("устаревшая строка удалена", (await cooldown_row(db)) is None)


async def scenario_7_second_cycle(db: Database) -> None:
    print("\n--- 7. Второй цикл: новый вывод -> ровно один новый таймер ---")
    res = await db.add_withdraw_strict(
        user_id=UID, amount=LIMIT, request_id="t7-exhaust", reason="test")
    check("второй вывод зафиксирован", bool(res.get("ok") and res.get("committed")), str(res.get("status")))

    row = await cooldown_row(db)
    check("таймер поставлен заново", row is not None)
    left = int(res.get("cooldown_left") or 0)
    check("срок полный", abs(left - WITHDRAW_DEFAULT_COOLDOWN_SEC) <= 5, f"осталось {left}s")

    async with db.pool.acquire() as conn:
        cnt = int(await conn.fetchval("SELECT COUNT(*) FROM withdraw_cooldown WHERE user_id=$1", UID) or 0)
    check("таймер в единственном экземпляре", cnt == 1, f"строк {cnt}")

    st = await db.refresh_withdraw_quota_if_needed(UID)
    check("экран блокирует вывод", not st.get("allowed"), str(st))

    res2 = await db.add_withdraw_strict(
        user_id=UID, amount=10, request_id="t7-during-cooldown", reason="test")
    check("вывод во время таймера отклонён", res2.get("error") == "cooldown_active", str(res2))

    row2 = await cooldown_row(db)
    check("отклонённая попытка таймер не продлила", row2 is not None and row2["until_at"] == row["until_at"],
          f"{row['until_at'] if row else None} -> {row2['until_at'] if row2 else None}")


async def scenario_8_partial_withdraw_no_timer(db: Database) -> None:
    print("\n--- 8. Частичный вывод (лимит не исчерпан) таймер не ставит ---")
    await prepare(db)

    res = await db.add_withdraw_strict(
        user_id=UID, amount=LIMIT - 40, request_id="t8-partial", reason="test")
    check("частичный вывод зафиксирован", bool(res.get("ok") and res.get("committed")), str(res.get("status")))
    check("таймер не ставился", not res.get("cooldown_set"), f"cooldown_set={res.get('cooldown_set')}")
    check("строки таймера нет", (await cooldown_row(db)) is None)

    st = await db.refresh_withdraw_quota_if_needed(UID)
    check("остаток верный", int(st.get("remaining") or 0) == 40, f"remaining={st.get('remaining')}")
    check("вывод разрешён", bool(st.get("allowed")), str(st))

    win = await window_row(db)
    check("израсходованное учтено", win is not None and int(win["used_in_window"]) == LIMIT - 40,
          f"used_in_window={win['used_in_window'] if win else None}")


async def scenario_9_parallel_renders(db: Database) -> None:
    print("\n--- 9. Одновременные открытия экрана в момент истечения таймера ---")
    await prepare(db)
    res = await db.add_withdraw_strict(
        user_id=UID, amount=LIMIT, request_id="t9-exhaust", reason="test")
    check("вывод зафиксирован", bool(res.get("ok") and res.get("committed")), str(res.get("status")))
    await expire_cooldown(db)

    states = await asyncio.gather(*[db.refresh_withdraw_quota_if_needed(UID) for _ in range(8)])
    all_allowed = all(bool(s.get("allowed")) for s in states)
    check("все параллельные вызовы разрешили вывод", all_allowed,
          str([(s.get("allowed"), s.get("remaining"), s.get("cooldown_left")) for s in states]))
    check("таймер не возродился ни одним из вызовов", (await cooldown_row(db)) is None)

    async with db.pool.acquire() as conn:
        logs = int(await conn.fetchval("SELECT COUNT(*) FROM withdraw_log WHERE user_id=$1", UID) or 0)
    check("журнал выводов не пострадал", logs == 1, f"записей {logs}")


async def main() -> int:
    await db.connect()
    try:
        await scenario_1_arm_once(db)
        await scenario_2_renders_do_not_restart(db)
        await scenario_3_expiry_frees_limit(db)
        await scenario_4_heals_stuck_state(db)
        await scenario_5_guard_refuses(db)
        await scenario_6_obsolete_cause_cleared(db)
        await scenario_7_second_cycle(db)
        await scenario_8_partial_withdraw_no_timer(db)
        await scenario_9_parallel_renders(db)
    finally:
        try:
            await cleanup(db)
            print("\n[очистка] тестовые данные удалены")
        except Exception as e:
            print(f"\n[очистка] ошибка: {e!r}")
        await db.pool.close()

    print("\n" + "=" * 60)
    if _failures:
        print(f"ПРОВАЛЕНО ПРОВЕРОК: {len(_failures)}")
        for f in _failures:
            print("  -", f)
        return 1
    print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
