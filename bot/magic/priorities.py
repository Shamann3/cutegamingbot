# -*- coding: utf-8 -*-
"""
Приоритетные callback_data для Мэджик (игры + магазин).

────────────────────────────────────────────────────────────
ЗАЧЕМ ЭТО НУЖНО
────────────────────────────────────────────────────────────
Кнопки из этого списка идут по «быстрому» каналу:
  • мягче debounce
  • выше лимит кликов
  • выше потолок одновременных handler'ов

Остальные кнопки — по жёсткому антиспаму.

────────────────────────────────────────────────────────────
КАК ДОБАВИТЬ НОВУЮ ИГРУ / МАГАЗИН
────────────────────────────────────────────────────────────
1) Если callback короткий и точный (например "pass"):
      добавь строку в PRIORITY_EXACT

2) Если callback вида "mineclick:12:abc" / "tank_withdraw_1_2":
      добавь префикс в PRIORITY_PREFIXES
      (достаточно начала: "mineclick" или "tank_")

3) Перезапусти бота
   ИЛИ без перезапуска:
      from bot.magic import magic
      magic.add_priority_prefix("mygame_")
      magic.add_priority_exact("my_stub")

Логику самих кнопок менять НЕ нужно.
"""
from __future__ import annotations

from typing import List, Set


# ══════════════════════════════════════════════════════════
# ТОЧНЫЕ callback_data
# ══════════════════════════════════════════════════════════
# Сравниваются целиком (==), без startswith.
# Сюда — короткие stub-кнопки игр/магазина.
PRIORITY_EXACT: Set[str] = {
    # --- универсальные stub'ы в играх ---
    "pass", "noop", "none", "#",
    "win", "lose",
    "spin", "shoot_bot", "shoot_self",
    "money_won", "money_lost",
    "win_amount_callback",

    # --- магазин / инвентарь / крафт (точные) ---
    "page_info", "reset_sorting", "store_close_message",
    "store_craft_close_message",
    "close_message_inventory", "close_inventory",
    "buy341234123412", "cancel341234123412", "cancel3412_purchase",
    "buy_with_coupon", "apply_coupon",
    "cancelsell", "sellitem", "canceldell",
    "store_craft", "craft_cancel",
    "cancel_buy", "cancel_sell", "cancel_house", "cancelhouse_sell",
    "show_car_images", "show_house_images",
    "return_to_my_cars", "return_to_my_house",
    "return_to_buy_menu", "return_to_sell_menu", "return_to_sellhouse_menu",
    "close3412341234123412", "close1",

    # --- создание/режимы групповых игр ---
    "checkers_create", "checkers_mode", "1tmemory_create",
    "induel_create", "tic_tac_create", "inmine_create", "inorel_create",
    "rps_create", "rpschooseknb", "chooseknb",

    # --- результат/заглушки соло-игр ---
    "mouse_withdraw",
    "callbroulletanswermultiplier", "callbroulletanswerhome",
    "minesbetchechtextanswer", "winnerminesanswertext",
    "hsudshjskfpuoaoisd",
    "ball_end_stub", "ball_paid_stub",
    "tank_paid_stub", "tank_msg_stub",
    "plate_end_stub", "plate_paid_stub", "plate_msg_stub",
    "trade_stub",
}


# ══════════════════════════════════════════════════════════
# ПРЕФИКСЫ callback_data
# ══════════════════════════════════════════════════════════
# Срабатывает, если callback_data.startswith(prefix)
# (регистр не важен).
#
# Пример: префикс "mineclick" покроет "mineclick:3:gameid"
PRIORITY_PREFIXES: List[str] = [
    # --- onboarding (bot/funcs/onboarding.py): игры / ставки / старт ---
    # покрывает ob_games, ob_gpick, ob_gstart, ob_game, ob_next, ob_retry, ...
    "ob_",

    # --- достижения профиля ---
    "ach_", "achm_",

    # --- орёл / шахматы / memory / bingo / рулетка / кости ---
    "joinorel", "startorel", "rollorel",
    "inorel_create", "joinorelinline", "startorelinline", "rollorelinline",
    "shajoin", "shastart", "select:", "shamode", "micha:", "shahsurrender",
    "unique_join_game", "unique_start_game",
    "inlineselect", "inlinechange", "michainlain", "shahsurrenderinline",
    "memoryjoin", "memorystart", "memory_open",
    "inlinememoryjoin", "sinlainmemorystart", "oinlinememory_open",
    "joinbingo", "startbingo", "rollbingo", "podrobneebingohui_",
    "joinruletka", "startruletka", "rollruletka",
    "joinroul_", "startroul_", "shootroul_",
    "kostijoin", "kostistart", "kostiroll",

    # --- дуэли / кнб / крестики ---
    "induel",
    "joinknb", "startknb", "chooseknb", "inline_knb", "rps",
    "jointictactoe", "starttictactoe", "surrendertictactoe",
    "inlinemovetictactoe", "tic_tac", "inline_tic",
    "set_board", "make_move",

    # --- mines / gild / bullet / dzrebi / word ---
    "mineclick", "minejoin", "minestart", "mines", "inline_mine",
    "gildclick", "gildjoin", "gildstart",
    "bulletjoin", "bulletstart",
    "joindzrebi", "startdzrebi", "choose_stick",
    "wordcancel_game",

    # --- соло-игры ---
    "tank_", "risk_", "plate_",
    "bomb_", "bombs_", "2412bombsskukota_", "bostop_",
    "ball_", "empty_", "pop_",
    "wcol", "wires_", "provoda",
    "trade_", "Trade",
    "button_",  # mouse
    "fortuna", "roulette", "рулет",
    "callbroullet",

    # --- GC / челлендж-подсказки внутри игр ---
    "gc_info", "gc_status", "gc_reward", "gc_regular", "gc_diff", "gc_in_place",

    # --- tggames (darts/bowling/soccer/...) ---
    "dart", "bowl", "foot", "soccer", "basket", "slot", "kube", "cube",
    "errordarts_", "errorkube_", "errorbowl_", "errorsoccer_",
    "errorbasket_", "errorslot_",

    # --- магазин / инвентарь / крафт / дома / машины / гелик ---
    "shop", "store_", "store", "blackshop", "blackshop_",
    "help_market", "help_store",
    "inv_page_", "filter_", "sorting",
    "craft_", "craftpage_", "inventory", "item_",
    "useitem", "use_item",
    "confirmdell",
    "buy_car_", "sell_car_", "confirm_buy_", "confirm_sell_", "view_car_",
    "buy_house_", "sell_house_", "confirm_house_", "confirmhouse_sell_", "view_house_",
    "buy_gelicopter_", "confirm_gelicopter_",
    "next_page_", "prev_page_", "user_next_page_", "user_prev_page_",
    "next1_page_", "prev1_page_", "user_next1_page_", "user_prev1_page_",
    "view_gelicopter_", "sell_gelicopter_",
    "kow_purchase",
]
