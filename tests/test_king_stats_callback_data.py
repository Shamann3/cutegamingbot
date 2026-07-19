"""Группа зашита в callback_data: меню не зависит от состояния в памяти."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import bot.funcs.king_stats as ks

GROUP = -1004203778966
ok = True

kb = ks._king_menu_keyboard({"period_kind": "day"}, group_chat_id=GROUP, group_balance=100)
datas = [b.callback_data for r in kb.inline_keyboard for b in r]
assert all(d.startswith(f"kingm:{GROUP}:") for d in datas), "не все кнопки несут группу"
assert max(len(d) for d in datas) <= 64, "callback_data длиннее лимита Telegram"

gid, tail = ks._split_callback_data(f"kingm:{GROUP}:place:1:kut:custom")
parts = [ks._KING_MENU_PREFIX, *tail]
assert (gid, parts[1], parts[2], parts[4]) == (GROUP, 'place', '1', 'custom'), "новый формат"

gid_old, tail_old = ks._split_callback_data("kingm:period:week")
parts_old = [ks._KING_MENU_PREFIX, *tail_old]
assert gid_old is None and parts_old[1] == 'period' and parts_old[2] == 'week', "старый формат"

for st in (ks._KING_MENU_OWNERS, ks._KING_MENU_TARGET, ks._KING_DM_LAST_MENU):
    st._load().clear()
gid2, _ = ks._split_callback_data(f"kingm:{GROUP}:period:week")
assert gid2 == GROUP, "группа должна читаться без всякого состояния"

for kb2 in (ks._king_place_keyboard({}, 1, group_chat_id=GROUP, show_input_cancel=True),
            ks._pending_cancel_keyboard(group_chat_id=GROUP),
            ks._budget_confirm_keyboard(group_chat_id=GROUP)):
    ds = [b.callback_data for r in kb2.inline_keyboard for b in r]
    assert all(d.startswith(f"kingm:{GROUP}:") for d in ds), "вложенные клавиатуры"

print("ВСЕ ПРОВЕРКИ ПРОШЛИ")
