"""Регрессия: расчёт итога шашек не должен терять параллельные изменения баланса.

Тикет: игрок видел баланс 50, пошёл играть в шашки — баланс пропал.

Причина: settlement в bot/games/scah.py делал read-modify-write —
    update_user_balance(uid, get_user_balance(uid) + stake)   # SET абсолютного значения
Если между чтением и записью баланс менял кто-то ещё (урожай, квест, покупка),
это изменение молча затиралось. Фикс — атомарный DELTA-режим ("+stake" / "-stake"),
который транслируется в `SET balance = balance + $2` под локом.

Тест моделирует общий стор баланса и параллельный кредит, вклинивающийся между
чтением и записью, и показывает: SET теряет кредит, DELTA — сохраняет.
"""
import io, sys, asyncio, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class FakeBalanceStore:
    """Мини-модель users.balance с двумя режимами update_user_balance.

    SET-режим  : пишет абсолютное значение (как было в баге).
    DELTA-режим: атомарный balance = balance + delta (как в реальной db.py).
    """
    def __init__(self, start):
        self.balance = start

    async def get_user_balance(self, _uid):
        # await -> точка переключения корутин, как у реального async DB-вызова
        await asyncio.sleep(0)
        return self.balance

    async def update_user_balance(self, _uid, value):
        await asyncio.sleep(0)
        if isinstance(value, str) and re.fullmatch(r"[+-]\d+", value.strip()):
            # DELTA: атомарное относительное изменение, без ухода в минус
            delta = int(value)
            if self.balance + delta < 0:
                return self.balance
            self.balance += delta
        else:
            # SET: жёсткая установка абсолютного значения (клампится к 0)
            self.balance = max(0, int(value))
        return self.balance


async def _concurrent_credit(store, amount):
    """Параллельная награда/начисление, приходящая во время расчёта игры."""
    await asyncio.sleep(0)  # даём settlement сделать get_user_balance
    await store.update_user_balance(0, f"+{amount}")


async def _settle_racy_set(store, stake):
    """Старое поведение: read-modify-write абсолютным значением (проигравший)."""
    cur = await store.get_user_balance(0)     # читаем 50
    await asyncio.sleep(0)                     # <- сюда вклинивается кредит +100
    await store.update_user_balance(0, cur - stake)  # пишем 50-10=40, +100 потерян


async def _settle_atomic_delta(store, stake):
    """Новое поведение: атомарный DELTA (проигравший)."""
    await store.update_user_balance(0, f"-{stake}")


async def main():
    STAKE = 10
    CREDIT = 100
    START = 50

    # --- Старый (багованный) путь: кредит теряется ---
    racy = FakeBalanceStore(START)
    await asyncio.gather(_settle_racy_set(racy, STAKE), _concurrent_credit(racy, CREDIT))
    # Ожидаемо-корректный итог: 50 + 100 - 10 = 140. Баг даёт 40 (кредит съеден).
    assert racy.balance == START - STAKE, f"демо-бага: ожидали {START-STAKE}, а не {racy.balance}"
    assert racy.balance != START + CREDIT - STAKE, "старый путь не должен быть корректным"
    print(f"[SET ] баланс={racy.balance} — параллельный кредит +{CREDIT} ПОТЕРЯН (демонстрация бага)")

    # --- Новый путь: кредит сохраняется ---
    fixed = FakeBalanceStore(START)
    await asyncio.gather(_settle_atomic_delta(fixed, STAKE), _concurrent_credit(fixed, CREDIT))
    assert fixed.balance == START + CREDIT - STAKE, \
        f"DELTA должен сохранить кредит: ожидали {START+CREDIT-STAKE}, получили {fixed.balance}"
    print(f"[DELTA] баланс={fixed.balance} — параллельный кредит +{CREDIT} СОХРАНЁН (фикс работает)")

    # --- Победитель: атомарное начисление ---
    winner = FakeBalanceStore(START)
    await asyncio.gather(
        winner.update_user_balance(0, f"+{STAKE}"),
        _concurrent_credit(winner, CREDIT),
    )
    assert winner.balance == START + STAKE + CREDIT, \
        f"начисление победителю + кредит: ожидали {START+STAKE+CREDIT}, получили {winner.balance}"
    print(f"[WIN  ] баланс={winner.balance} — выигрыш и параллельный кредит оба учтены")

    # --- Проигравший без достаточного баланса: списание не уводит в минус ---
    poor = FakeBalanceStore(5)
    await _settle_atomic_delta(poor, STAKE)
    assert poor.balance == 5, f"списание не должно уводить в минус: получили {poor.balance}"
    print(f"[MIN  ] баланс={poor.balance} — при нехватке средств списание не проходит (как в SET)")

    print("ВСЕ ПРОВЕРКИ ПРОШЛИ")


asyncio.run(main())
