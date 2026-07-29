import io, os, pathlib, sys, asyncio, types as pytypes
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Шаг 5 проверяет пережитие рестарта через НАСТОЯЩИЙ Redis, а pklcode берёт
# доступы из окружения процесса. Без этого вызова REDIS_PASSWORD не выставлен,
# Redis не подключается, и шаг 5 падал независимо от проверяемой логики.
from bot.config.db_config import bootstrap_database_env
bootstrap_database_env()

import bot.funcs.king_stats as ks
from aiogram.exceptions import TelegramForbiddenError

GROUP_A, GROUP_B, USER = -1002213242513, -1002189875640, 555
DM = USER

class Chat:
    def __init__(self, cid, ctype): self.id, self.type = cid, ctype
class User:
    def __init__(self, uid): self.id = uid
class Msg:
    _next = [100]
    def __init__(self, text, chat, user=USER, mid=None):
        Msg._next[0] += 1
        self.text, self.chat, self.from_user = text, chat, User(user)
        self.message_id = mid or Msg._next[0]
        self.reply_to_message = None; self.caption=None; self.reply_markup=None
        self.bot = None

sent_log = []

class Bot:
    def __init__(self, dm_open=True): self.dm_open = dm_open
    async def get_me(self): return pytypes.SimpleNamespace(username="CuteGamingBot")
    async def send_message(self, chat_id, text, **kw):
        if not self.dm_open and chat_id > 0:
            raise TelegramForbiddenError(method=None, message="bot can't initiate conversation")
        m = Msg(text, Chat(chat_id, "private" if chat_id > 0 else "supergroup"))
        sent_log.append(("send", chat_id, text))
        return m
    async def delete_message(self, chat_id, message_id):
        sent_log.append(("delete", chat_id, message_id))
    async def edit_message_text(self, **kw): pass

class DB:
    def __init__(self): self.settings = {}
    async def ensure_king_stats_schema(self): pass
    async def update_chat_creator_if_owner(self, *a, **k): pass
    async def get_group_creator(self, chat_id): return USER
    async def get_chat_meta_basic(self, chat_id):
        return {"namechat": f"Группа {chat_id}", "chatbalance": 5000, "usernamechat": "none"}
    async def get_chat_king_reward_settings(self, chat_id):
        return self.settings.setdefault(int(chat_id), {
            "chat_id": chat_id, "enabled": False, "min_messages": 0, "period_kind": "day",
            "active_until_ts": None, "start_at_ts": None,
            "place_1": {}, "place_2": {}, "place_3": {}})
    async def set_chat_king_start_at(self, chat_id, ts, **kw):
        s = await self.get_chat_king_reward_settings(chat_id); s["start_at_ts"] = ts; return s

async def reply_capture(message, text, reply_markup=None):
    m = Msg(text, message.chat)
    sent_log.append(("reply", message.chat.id, text))
    return m
ks._reply_barnum = reply_capture

def show(tag):
    print(f"  {tag}")
    for e in sent_log: print("     ", e[0], e[1], "|", str(e[2]).split(chr(10))[0][:60])
    sent_log.clear()

def wipe_king_stores():
    """Тесты должны стартовать с чистого листа: Redis тут настоящий."""
    import bot.db_create.pklcode as P
    rc = P._raw_client()
    if rc is None:
        return
    for pat in (b'pkl:_KING*',):
        for k in list(rc.scan_iter(match=pat)):
            rc.delete(k)
    for st in (ks._KING_MENU_TARGET, ks._KING_MENU_OWNERS,
               ks._KING_DM_LAST_MENU, ks._KING_PENDING_INPUTS,
               ks._KING_MENU_RENDER_STATE):
        s = st._load()
        s.clear(); s.timestamps.clear()


async def main():
    wipe_king_stores()
    db, bot = DB(), Bot()
    ok = True

    print("\n=== 1. Команда в ЛС без ожидания ввода ===")
    await ks.handle_king_stats_command(Msg("система царя статистики", Chat(DM, "private")), db, bot)
    hint = any("в той группе" in e[2] for e in sent_log)
    show("ожидаем подсказку «напишите в группе»")
    print("  ->", "OK" if hint else "ПРОВАЛ"); ok &= hint

    print("\n=== 2. Команда в группе A -> меню уходит в ЛС ===")
    await ks.handle_king_stats_command(Msg("система царя статистики", Chat(GROUP_A, "supergroup")), db, bot)
    to_dm = any(e[0]=="send" and e[1]==DM for e in sent_log)
    in_group = any(e[0]=="reply" and e[1]==GROUP_A and "личные" in e[2] for e in sent_log)
    show("ожидаем send в ЛС + ответ в группе")
    print("  ->", "OK" if (to_dm and in_group) else "ПРОВАЛ"); ok &= to_dm and in_group

    dm_msg_a = ks._get_dm_last_menu(USER, GROUP_A)
    bound_a = ks._get_menu_target(DM, dm_msg_a)
    print(f"  меню {dm_msg_a} в ЛС привязано к группе {bound_a}")
    ok &= bound_a == GROUP_A

    print("\n=== 3. Вторая группа B -> отдельное меню, A не тронуто ===")
    await ks.handle_king_stats_command(Msg("система царя статистики", Chat(GROUP_B, "supergroup")), db, bot)
    sent_log.clear()
    dm_msg_b = ks._get_dm_last_menu(USER, GROUP_B)
    print(f"  A -> сообщение {dm_msg_a} -> группа {ks._get_menu_target(DM, dm_msg_a)}")
    print(f"  B -> сообщение {dm_msg_b} -> группа {ks._get_menu_target(DM, dm_msg_b)}")
    both = (ks._get_menu_target(DM, dm_msg_a) == GROUP_A and ks._get_menu_target(DM, dm_msg_b) == GROUP_B)
    print("  ->", "OK" if both else "ПРОВАЛ"); ok &= both

    print("\n=== 4. Ручной ввод даты в ЛС применяется к нужной группе ===")
    ks._set_pending_input(DM, USER, {"type": "start_date_custom", "panel_message_id": dm_msg_a},
                          group_chat_id=GROUP_A)
    m = Msg("16.07.2026", Chat(DM, "private"))
    routed = ks.has_king_stats_pending_input(m)
    print("  роутится в обработчик:", routed); ok &= routed
    await ks.handle_king_stats_command(m, db, bot)
    saved = db.settings[GROUP_A]["start_at_ts"]
    untouched = db.settings.get(GROUP_B, {}).get("start_at_ts")
    sent_log.clear()
    print(f"  группа A start_at_ts = {saved}")
    print(f"  группа B start_at_ts = {untouched} (должно остаться None)")
    good = saved is not None and untouched is None
    print("  ->", "OK" if good else "ПРОВАЛ"); ok &= good

    print("\n=== 5. Переживание рестарта бота (через настоящий Redis) ===")
    import bot.db_create.pklcode as P
    # Как при выключении контейнера: сбрасываем всё в Redis.
    for st in (ks._KING_MENU_TARGET, ks._KING_MENU_OWNERS, ks._KING_DM_LAST_MENU):
        st._load().flush()
    # Как при старте нового процесса: ни одного объекта стора в памяти.
    P.GameStore._instances.clear()
    P.LazyGameStore._loaded_instances.clear()
    for st in (ks._KING_MENU_TARGET, ks._KING_MENU_OWNERS, ks._KING_DM_LAST_MENU):
        st._store = None
    print(f"  сторов в памяти после «рестарта»: {len(P.GameStore._instances)}")
    # Меню 104 после шага 4 удалено штатно (панель заменяется новой), поэтому
    # проверяем нетронутое меню группы B и актуальное меню группы A.
    survived_b = ks._get_menu_target(DM, dm_msg_b)
    owner_b = ks._get_menu_owner(DM, dm_msg_b)
    fresh_a = ks._get_dm_last_menu(USER, GROUP_A)
    survived_a = ks._get_menu_target(DM, fresh_a) if fresh_a else None
    print(f"  меню группы B ({dm_msg_b}) -> группа {survived_b}, владелец {owner_b}")
    print(f"  актуальное меню группы A ({fresh_a}) -> группа {survived_a}")
    good = survived_b == GROUP_B and owner_b == USER and survived_a == GROUP_A
    print("  ->", "OK" if good else "ПРОВАЛ"); ok &= good

    print("\n=== 6. ЛС закрыто -> подсказка запустить бота ===")
    ks._KING_DM_LAST_MENU.clear() if hasattr(ks._KING_DM_LAST_MENU, 'clear') else None
    await ks.handle_king_stats_command(
        Msg("система царя статистики", Chat(GROUP_A, "supergroup")), db, Bot(dm_open=False))
    warn = any("Не могу написать" in e[2] for e in sent_log)
    show("ожидаем предупреждение в группе")
    print("  ->", "OK" if warn else "ПРОВАЛ"); ok &= warn

    print("\n" + ("="*46) + f"\nИТОГ: {'ВСЕ ПРОВЕРКИ ПРОШЛИ' if ok else 'ЕСТЬ ПРОВАЛЫ'}")
    return 0 if ok else 1

sys.exit(asyncio.run(main()))
