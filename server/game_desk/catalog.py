# -*- coding: utf-8 -*-
"""Каталог игр и дефолты. Админка и бот читают один и тот же смысл."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

PVP_MAX = 500_000


def _theme(accent: str, accent2: str, ink: str, wash: str, motif: str) -> Dict[str, str]:
    return {
        "accent": accent,
        "accent2": accent2,
        "ink": ink,
        "wash": wash,
        "motif": motif,
    }


def _field(key: str, label: str, kind: str, hint: str, lo: float, hi: float, group: str, step: Optional[float] = None) -> Dict[str, Any]:
    item = {
        "key": key,
        "label": label,
        "kind": kind,
        "min": lo,
        "max": hi,
        "hint": hint,
        "group": group,
    }
    if step is not None:
        item["step"] = step
    return item


def _chance(key: str, label: str, hint: str, lo: float = 0.0, hi: float = 0.6, group: str = "odds") -> Dict[str, Any]:
    return _field(key, label, "chance", hint, lo, hi, group, 0.01)


def _mult(key: str, label: str, hint: str, lo: float = 0.05, hi: float = 12.0, group: str = "payout") -> Dict[str, Any]:
    return _field(key, label, "multiplier", hint, lo, hi, group, 0.05)


def _int(key: str, label: str, hint: str, lo: int, hi: int, group: str = "table") -> Dict[str, Any]:
    return _field(key, label, "int", hint, lo, hi, group, 1)


def _sec(key: str, label: str, hint: str, lo: float, hi: float, group: str = "tempo") -> Dict[str, Any]:
    return _field(key, label, "seconds", hint, lo, hi, group, 0.05)


def _game(
    key: str,
    title: str,
    kind: str,
    emoji: str,
    hint: str,
    *,
    min_bet: int,
    max_bet: int,
    commission: float,
    params: Optional[Dict[str, Any]] = None,
    fields: Optional[List[Dict[str, Any]]] = None,
    command: str = "",
    theme: Optional[Dict[str, str]] = None,
    mood: str = "",
) -> Dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "kind": kind,
        "emoji": emoji,
        "hint": hint,
        "mood": mood,
        "command": command,
        "theme": dict(theme or _theme("#8a827c", "#d8cfc6", "#141416", "rgba(255,255,255,.06)", "plain")),
        "defaults": {
            "enabled": True,
            "maintenance": False,
            "minBet": int(min_bet),
            "maxBet": int(max_bet),
            "commissionMult": float(commission),
            "params": dict(params or {}),
        },
        "fields": list(fields or []),
    }


GAMES: List[Dict[str, Any]] = [
    _game(
        "scah", "Шашки", "pvp", "♟",
        "Партия на ставке. Двое ходят по очереди.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="шашки",
        mood="Тёмное дерево и светлые клетки.",
        theme=_theme("#c4a574", "#3b2a1c", "#1a120c", "rgba(196,165,116,.16)", "board"),
        params={"turnRest": 2.2},
        fields=[_sec("turnRest", "Пауза между ходами", "Сколько секунд игрок ждёт, прежде чем может сходить снова.", 0.4, 8.0)],
    ),
    _game(
        "memory", "Мемори", "pvp", "🪵",
        "Найди пару. Кто собрал больше — забирает банк.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="мемори",
        mood="Тёплый лес и карточки из дерева.",
        theme=_theme("#d7a15a", "#5a3a22", "#1c120a", "rgba(215,161,90,.16)", "wood"),
        params={"hideDelay": 1.50, "clickCooldown": 0.28},
        fields=[
            _sec("hideDelay", "Скрытие неверной пары", "Как долго открытые карточки остаются на экране, если пара не сошлась.", 0.4, 4.0),
            _sec("clickCooldown", "Пауза между нажатиями", "Защита от спама по полю.", 0.08, 1.5),
        ],
    ),
    _game(
        "bingo", "Бинго", "pvp", "🍪",
        "Карточки и бочонок. Банк победителю.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="бинго",
        mood="Тёплое печенье и барабан с бочонками.",
        theme=_theme("#e8a05a", "#8a3d1c", "#1c1008", "rgba(232,160,90,.16)", "cookie"),
        params={"maxPlayers": 10},
        fields=[_int("maxPlayers", "Игроков максимум", "Сколько человек может сесть за один стол.", 2, 20)],
    ),
    _game(
        "fortuna_lobby", "Фортуна", "pvp", "🎡",
        "Лобби: несколько игроков, один спин, один забирает банк.",
        min_bet=0, max_bet=PVP_MAX, commission=1.2, command="фортуна",
        mood="Ярмарочное колесо, ночь и золото.",
        theme=_theme("#f0c14b", "#7a1f6b", "#160814", "rgba(240,193,75,.16)", "wheel"),
        params={"maxPlayers": 5},
        fields=[_int("maxPlayers", "Игроков максимум", "Сколько человек крутит одно колесо.", 2, 12)],
    ),
    _game(
        "kosti", "Кости", "pvp", "🎲",
        "Игроки собирают банк и бросают кости. Больше очков — банк.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="кости",
        mood="Зелёное сукно и кости из слоновой кости.",
        theme=_theme("#3d8b5a", "#f3efe6", "#0c1610", "rgba(61,139,90,.16)", "felt"),
        params={"maxPlayers": 12},
        fields=[_int("maxPlayers", "Игроков максимум", "Сколько человек бросает в одном круге.", 2, 24)],
    ),
    _game(
        "duel", "Дуэль", "pvp", "🔫",
        "Двое стреляют. Победитель забирает банк.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="дуэль",
        mood="Порох, латунь и холодный вечер.",
        theme=_theme("#c9a36a", "#3a2c22", "#120e0a", "rgba(201,163,106,.16)", "duel"),
    ),
    _game(
        "orel", "Орёл или решка", "pvp", "🦅",
        "Двое. Орёл или решка. Монета решает банк.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="орел",
        mood="Золотая монета и орёл на реверсе.",
        theme=_theme("#e6c35c", "#7a4e14", "#161008", "rgba(230,195,92,.16)", "coin"),
    ),
    _game(
        "knb", "Камень-ножницы-бумага", "pvp", "✂️",
        "Классическая дуэль на куты.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="кнб",
        mood="Бумага, сталь и камень.",
        theme=_theme("#8aa0b8", "#2a3340", "#0e1218", "rgba(138,160,184,.16)", "steel"),
    ),
    _game(
        "mines", "Мины", "pvp", "🧨",
        "Поле 5×5. Кто наступит на мину — проиграет банк.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="мины",
        mood="Красная черта и чёрный порох.",
        theme=_theme("#e24b4b", "#2a0c0c", "#140808", "rgba(226,75,75,.16)", "hazard"),
    ),
    _game(
        "tic_tac_toe", "Крестики-нолики", "pvp", "☑️",
        "Трое в ряд. Банк победителю.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="крестики",
        mood="Чистая сетка и два знака.",
        theme=_theme("#5aa0e6", "#dce8f6", "#0c141c", "rgba(90,160,230,.16)", "grid"),
        params={"turnRest": 1.2},
        fields=[_sec("turnRest", "Пауза между ходами", "Сколько секунд игрок ждёт до следующего хода.", 0.3, 6.0)],
    ),
    _game(
        "tank", "Башня", "pve", "🍀",
        "Этаж за этажом. Успейте забрать до обвала.",
        min_bet=2, max_bet=1000, commission=1.0, command="башня",
        mood="Клевер, этажи и зелёная удача.",
        theme=_theme("#5cb86a", "#1c3a20", "#0c1610", "rgba(92,184,106,.16)", "clover"),
        params={"stepMultiplier": 0.70, "sessionMinutes": 20, "clickCooldown": 0.35},
        fields=[
            _mult("stepMultiplier", "Множитель этажа", "Насколько растёт выигрыш за каждый взятый этаж."),
            _int("sessionMinutes", "Минут на партию", "После этого башня закрывается сама.", 5, 60),
            _sec("clickCooldown", "Пауза между шагами", "Защита от слишком быстрых нажатий.", 0.1, 2.0),
        ],
    ),
    _game(
        "risk", "Риск", "pve", "🌴",
        "Каждый шаг умножает выигрыш. Заберите вовремя.",
        min_bet=5, max_bet=1000, commission=1.0, command="риск",
        mood="Пальмы, песок и огонь.",
        theme=_theme("#4caf7a", "#c45a2a", "#10180e", "rgba(76,175,122,.16)", "jungle"),
        params={"stepMultiplier": 1.0, "homeChance": 0.15, "sessionMinutes": 20, "clickCooldown": 0.40},
        fields=[
            _mult("stepMultiplier", "Множитель шага", "Насколько растёт выигрыш за каждый удачный шаг."),
            _chance("homeChance", "Шаг домой", "Скрытый исход: ставка сгорает, как будто игрок «ушёл домой»."),
            _int("sessionMinutes", "Минут на партию", "После этого поле закрывается само.", 5, 60),
            _sec("clickCooldown", "Пауза между шагами", "Защита от слишком быстрых нажатий.", 0.1, 2.0),
        ],
    ),
    _game(
        "plate", "Плиты", "pve", "💫",
        "Шаг по плитам. Провалились — ставка сгорает.",
        min_bet=2, max_bet=1000, commission=1.0, command="плиты",
        mood="Роза, космос и хрупкий камень.",
        theme=_theme("#e07aa8", "#6a2a7a", "#140c16", "rgba(224,122,168,.16)", "rose"),
        params={"stepMultiplier": 0.8, "collapseMin": 1, "collapseMax": 3, "sessionMinutes": 20, "clickCooldown": 0.35},
        fields=[
            _mult("stepMultiplier", "Множитель шага", "Насколько растёт выигрыш за каждый верный шаг."),
            _int("collapseMin", "Обвалов минимум", "Сколько рядов из десяти могут обрушиться. Нижняя граница.", 1, 8),
            _int("collapseMax", "Обвалов максимум", "Сколько рядов из десяти могут обрушиться. Верхняя граница.", 1, 10),
            _int("sessionMinutes", "Минут на партию", "После этого плиты закрываются сами.", 5, 60),
            _sec("clickCooldown", "Пауза между шагами", "Защита от слишком быстрых нажатий.", 0.1, 2.0),
        ],
    ),
    _game(
        "bombs", "Бомбы", "pve", "💣",
        "Открываете клетки. Бомба — всё сгорает. Справедливый множитель минус перевес казны.",
        min_bet=3, max_bet=1000, commission=1.0, command="бомбы",
        mood="Искра, порох и оранжевая вспышка.",
        theme=_theme("#f08a2a", "#2a1208", "#140c08", "rgba(240,138,42,.16)", "blast"),
        params={
            "houseEdge": 0.08,
            "bombCount": 8,
            "nukeMin": 4,
            "nukeMax": 8,
            "sessionMinutes": 20,
            "clickCooldown": 0.50,
        },
        fields=[
            _chance("houseEdge", "Перевес казны", "Сколько казна оставляет себе от справедливого множителя за клетку.", 0.0, 0.4),
            _int("bombCount", "Бомб на поле", "Сколько бомб лежит на поле 5×5.", 4, 16),
            _int("nukeMin", "Особых клеток от", "Нижняя граница числа особых клеток на поле.", 0, 10),
            _int("nukeMax", "Особых клеток до", "Верхняя граница числа особых клеток на поле.", 0, 12),
            _int("sessionMinutes", "Минут на партию", "После этого поле закрывается само.", 5, 60),
            _sec("clickCooldown", "Пауза между нажатиями", "Защита от слишком быстрых нажатий.", 0.1, 2.0),
        ],
    ),
    _game(
        "trade", "Трейд", "pve", "📈",
        "Вверх, вниз или сделка срывается. Верное направление платит.",
        min_bet=1, max_bet=1000, commission=1.0, command="трейд",
        mood="Терминал: зелёный рост и красное падение.",
        theme=_theme("#32d74b", "#ff453a", "#0a1210", "rgba(50,215,75,.14)", "terminal"),
        params={"pUp": 0.425, "pDown": 0.425, "pBroken": 0.15, "winMultiplier": 1.0},
        fields=[
            _chance("pUp", "Шанс вверх", "Вероятность роста графика.", 0.05, 0.8),
            _chance("pDown", "Шанс вниз", "Вероятность падения графика.", 0.05, 0.8),
            _chance("pBroken", "Сделка сорвалась", "Ставка сгорает независимо от выбора.", 0.0, 0.6),
            _mult("winMultiplier", "Множитель прибыли", "Сколько ставок игрок получает сверху при верном направлении. 1 — как сейчас: +ставка."),
        ],
    ),
    _game(
        "balls", "Шарик", "pve", "🎱",
        "Три стакана. Шарик, пусто и лопнул. Угадали шарик — выигрыш.",
        min_bet=2, max_bet=1000, commission=1.0, command="шарик",
        mood="Зелёное сукно и чёрный шар.",
        theme=_theme("#2f6b3a", "#111111", "#0a120c", "rgba(47,107,58,.16)", "billiard"),
        params={"winMultiplier": 1.0},
        fields=[_mult("winMultiplier", "Множитель прибыли", "Сколько ставок игрок получает сверху, если угадал шарик. 1 — как сейчас: +ставка.")],
    ),
    _game(
        "provoda", "Провода", "pve", "🎗",
        "Верный провод — выигрыш. Ошибка — ставка сгорает. Один провод всегда замыкание.",
        min_bet=2, max_bet=1000, commission=1.0, command="провода",
        mood="Неон и жилы под напряжением.",
        theme=_theme("#5ad0ff", "#ff4d6d", "#0a1018", "rgba(90,208,255,.14)", "neon"),
        params={"payout": 2.0, "wiresMin": 3, "wiresMax": 5, "winWires3": 1, "winWires4": 1, "winWires5": 2},
        fields=[
            _mult("payout", "Множитель выигрыша", "Во сколько раз умножается ставка при верном проводе. 2 — игрок получает две ставки, чистыми одна."),
            _int("wiresMin", "Проводов минимум", "Нижняя граница числа проводов в раунде.", 2, 7),
            _int("wiresMax", "Проводов максимум", "Верхняя граница числа проводов в раунде.", 3, 8),
            _int("winWires3", "Верных при 3 проводах", "Сколько победных жил, если выпало три провода.", 1, 2),
            _int("winWires4", "Верных при 4 проводах", "Сколько победных жил, если выпало четыре провода.", 1, 3),
            _int("winWires5", "Верных при 5 проводах", "Сколько победных жил, если выпало пять проводов.", 1, 3),
        ],
    ),
    _game(
        "slots", "Слоты", "pve", "🎰",
        "Три барабана. Иногда автомат заклинивает. Выплата по комбинации.",
        min_bet=2, max_bet=1000, commission=1.0, command="слоты",
        mood="Неон казино и три барабана.",
        theme=_theme("#ff4d8d", "#7c2cff", "#120814", "rgba(255,77,141,.16)", "neon"),
        params={
            "jamChance": 0.08,
            "tripleSeven": 2.5,
            "tripleLemon": 2.2,
            "tripleGrape": 1.9,
            "tripleBar": 1.7,
            "pairSeven": 1.5,
            "pairLemon": 1.4,
            "pairGrape": 1.3,
            "pairBar": 1.2,
        },
        fields=[
            _chance("jamChance", "Заклинивание", "Как часто автомат заклинивает вместо обычного проигрыша."),
            _mult("tripleSeven", "Три семёрки", "Выплата за 7️⃣7️⃣7️⃣."),
            _mult("tripleLemon", "Три лимона", "Выплата за три лимона."),
            _mult("tripleGrape", "Три винограда", "Выплата за три винограда."),
            _mult("tripleBar", "Три BAR", "Выплата за три BAR."),
            _mult("pairSeven", "Две семёрки", "Выплата, когда две семёрки и третий другой."),
            _mult("pairLemon", "Два лимона", "Выплата, когда два лимона и третий другой."),
            _mult("pairGrape", "Два винограда", "Выплата, когда два винограда и третий другой."),
            _mult("pairBar", "Два BAR", "Выплата, когда два BAR и третий другой."),
        ],
    ),
    _game(
        "basket", "Баскетбол", "pve", "🏀",
        "В кольцо — выигрыш. Мимо — ставка сгорает. Иногда мяч сдувается.",
        min_bet=2, max_bet=1000, commission=1.0, command="баскет",
        mood="Паркет и оранжевый мяч.",
        theme=_theme("#e67a2e", "#3a2214", "#140e0a", "rgba(230,122,46,.16)", "court"),
        params={"flatChance": 0.15},
        fields=[_chance("flatChance", "Мяч сдулся", "Скрытый промах сверх обычного броска.")],
    ),
    _game(
        "soccer", "Футбол", "pve", "⚽️",
        "Гол — выигрыш. Мимо — ставка сгорает. Иногда удар срывается.",
        min_bet=2, max_bet=1000, commission=1.0, command="футбол",
        mood="Газон и белый мяч.",
        theme=_theme("#4caf50", "#dce8d8", "#0c160e", "rgba(76,175,80,.16)", "grass"),
        params={"badShotChance": 0.08},
        fields=[_chance("badShotChance", "Неудачный удар", "Скрытый промах сверх обычного исхода. Сейчас в боте 8%.")],
    ),
    _game(
        "bowling", "Боулинг", "pve", "🎳",
        "Страйк — выигрыш. Иногда шар уходит в жёлоб.",
        min_bet=2, max_bet=1000, commission=1.0, command="боулинг",
        mood="Деревянная дорожка и кегли.",
        theme=_theme("#d4a574", "#2a1810", "#120e0a", "rgba(212,165,116,.16)", "alley"),
        params={"badHitChance": 0.08},
        fields=[_chance("badHitChance", "Неудачный удар", "Скрытый промах сверх обычного броска. Сейчас в боте 8%.")],
    ),
    _game(
        "darts", "Дартс", "pve", "🎯",
        "Центр мишени — выигрыш. Иногда бросок срывается.",
        min_bet=2, max_bet=1000, commission=1.0, command="дартс",
        mood="Красно-чёрная мишень.",
        theme=_theme("#d12b2b", "#111111", "#140808", "rgba(209,43,43,.16)", "target"),
        params={"badThrowChance": 0.15},
        fields=[_chance("badThrowChance", "Неудачный бросок", "Скрытый промах сверх обычного исхода.")],
    ),
    _game(
        "kube", "Куб", "pve", "🎲",
        "Угадали число на кубике — множитель к ставке. Иногда кубик теряется.",
        min_bet=2, max_bet=1000, commission=1.1, command="куб",
        mood="Белая кость и красные точки.",
        theme=_theme("#f4f0ec", "#c62828", "#141210", "rgba(244,240,236,.12)", "dice"),
        params={"multiplier": 3.0, "lostChance": 0.15},
        fields=[
            _mult("multiplier", "Множитель выигрыша", "Во сколько раз умножается ставка при угаданном числе."),
            _chance("lostChance", "Кубик потерялся", "Скрытый проигрыш сверх обычного промаха."),
        ],
    ),
    _game(
        "fortuna_solo", "Рулетка", "pve", "🎩",
        "Цвет, число, чёт, диапазон. Ноль забирает банк.",
        min_bet=3, max_bet=5000, commission=1.0, command="рулетка",
        mood="Сукно, золото и ноль.",
        theme=_theme("#1f6b3a", "#d4af37", "#08140c", "rgba(212,175,55,.16)", "roulette"),
        params={
            "zeroChance": 0.15,
            "numberMult": 11.0,
            "colorMult": 2.0,
            "parityMult": 2.0,
            "singleNumberWinChance": 0.005,
            "range1": 11.0,
            "range2": 6.0,
            "range3": 4.0,
            "range4": 3.0,
            "range5": 2.4,
            "range6": 2.0,
            "range7": 1.7,
            "range8": 1.45,
            "range9": 1.25,
            "range10": 1.10,
            "range11": 1.02,
        },
        fields=[
            _chance("zeroChance", "Шанс нуля", "Как часто выпадает ноль и забирает ставку."),
            _chance("singleNumberWinChance", "Шанс числа", "Как часто выигрывает ставка на одно число. Сейчас очень редко.", 0.001, 0.08),
            _mult("numberMult", "Множитель числа", "Выплата за угаданное число от 0 до 12.", 1.0, 20.0),
            _mult("colorMult", "Множитель цвета", "Выплата за красное или чёрное."),
            _mult("parityMult", "Множитель чёт/нечет", "Выплата за чётное или нечётное."),
            _mult("range1", "Диапазон 1 число", "Выплата, если игрок поставил на одно число диапазоном."),
            _mult("range2", "Диапазон 2 числа", "Выплата за два числа подряд."),
            _mult("range3", "Диапазон 3 числа", "Выплата за три числа подряд."),
            _mult("range4", "Диапазон 4 числа", "Выплата за четыре числа подряд."),
            _mult("range5", "Диапазон 5 чисел", "Выплата за пять чисел подряд."),
            _mult("range6", "Диапазон 6 чисел", "Выплата за шесть чисел подряд."),
            _mult("range7", "Диапазон 7 чисел", "Выплата за семь чисел подряд."),
            _mult("range8", "Диапазон 8 чисел", "Выплата за восемь чисел подряд."),
            _mult("range9", "Диапазон 9 чисел", "Выплата за девять чисел подряд."),
            _mult("range10", "Диапазон 10 чисел", "Выплата за десять чисел подряд."),
            _mult("range11", "Диапазон 11 чисел", "Выплата за одиннадцать чисел подряд."),
        ],
    ),
    _game(
        "words", "Слова", "pvp", "🔤",
        "По умолчанию без комиссии — так просили.",
        min_bet=0, max_bet=PVP_MAX, commission=0.0, command="слова",
        mood="Бумага и чернила.",
        theme=_theme("#d8cfc0", "#4a4036", "#161410", "rgba(216,207,192,.12)", "paper"),
    ),
    _game(
        "bullet", "Пуля", "pvp", "💥",
        "Быстрая дуэль на ставку.",
        min_bet=0, max_bet=PVP_MAX, commission=1.0, command="пуля",
        mood="Латунная гильза.",
        theme=_theme("#c9a36a", "#2a2018", "#100c08", "rgba(201,163,106,.16)", "brass"),
    ),
]

ALIASES = {
    "fortuna": "fortuna_solo",
    "рулетка": "fortuna_solo",
    "duel": "duel",
    "due": "duel",
}

DEFAULT_COMMISSION = {
    "enabled": True,
    "minPot": 10,
    "rateByLevel": {"0": 0.20, "1": 0.18, "2": 0.15, "3": 0.13, "4": 0.10, "5": 0.05},
}

GAME_BY_KEY = {g["key"]: g for g in GAMES}

GROUP_LABELS = {
    "odds": "Шансы",
    "payout": "Выплата",
    "table": "Стол",
    "tempo": "Темп",
}


def resolve_key(raw: str) -> str:
    key = str(raw or "").strip()
    return ALIASES.get(key, key)


def game_meta(key: str) -> Optional[Dict[str, Any]]:
    return GAME_BY_KEY.get(resolve_key(key))


def default_game_state(key: str) -> Dict[str, Any]:
    meta = game_meta(key)
    if not meta:
        return {
            "enabled": True,
            "maintenance": False,
            "minBet": 1,
            "maxBet": PVP_MAX,
            "commissionMult": 1.0,
            "params": {},
        }
    return {
        "enabled": True,
        "maintenance": False,
        "minBet": int(meta["defaults"]["minBet"]),
        "maxBet": int(meta["defaults"]["maxBet"]),
        "commissionMult": float(meta["defaults"]["commissionMult"]),
        "params": dict(meta["defaults"]["params"]),
    }


def default_payload() -> Dict[str, Any]:
    return {
        "commission": {
            "enabled": bool(DEFAULT_COMMISSION["enabled"]),
            "minPot": int(DEFAULT_COMMISSION["minPot"]),
            "rateByLevel": {str(k): float(v) for k, v in DEFAULT_COMMISSION["rateByLevel"].items()},
        },
        "games": {g["key"]: default_game_state(g["key"]) for g in GAMES},
    }


def catalog_public() -> List[Dict[str, Any]]:
    out = []
    for g in GAMES:
        item = dict(g)
        item["defaults"] = default_game_state(g["key"])
        item["groups"] = dict(GROUP_LABELS)
        out.append(item)
    return out
