from b_Eden.Garden_of_Eden import *
from bot.config.config import _PLATE_MULT_DEFAULT,RISK_MIN_BET,RISK_MAX_BET,_RISK_MULT_DEFAULT,provoda_MIN_BET,provoda_MAX_BET,PAYOUT_MULTIPLIER,WIRES_MIN,WIRES_MAX,WIN_BY_COUNT,WIRE_COLORS
# локи на пользователя (анти-гонка по user_id)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, PreCheckoutQuery, LabeledPrice, InputFile, ForceReply
from aiogram import Bot, Dispatcher, types, F
from main import *
_balance_burn_locks: Dict[int, asyncio.Lock] = LazyGameStore("_balance_burn_locks")
from bot.design.buttons import (
    resolve_gift_menu_icon_override,
    set_gift_menu_emoji_override,
    reset_gift_menu_emoji_override,
    build_gift_menu_control_kb,
    build_gift_menu_ids_callback,
    get_available_gifts_fast,
)




def _hb(*a):
    """Горячий лог баланса печатает только при включённом BALANCE_DEBUG.

    На Windows каждый print с эмодзи через пайп логгера стоит миллисекунды,
    а на команду «баланс» их набегает ~20. Гейтим их флагом, чтобы в проде
    команда отвечала мгновенно.
    """
    if globals().get("BALANCE_DEBUG", False):
        print(*a)


async def handle_balance(message: types.Message, db):
    """
    Вызывается, когда пользователь пишет «баланс» (или аналогичную команду).
    Показывает текущий баланс с учётом движка (sleep/active/burned),
    челленджи, таймер восстановления и т.п.
    """
    # Проверка текста – если вдруг вызвали для другого сообщения, просто выходим
    if not (message.text and message.text.lower() in ["б", "баланс", "💸 баланс", "мой баланс"]):
        return

    owner_id = message.from_user.id
    current_chat_id = message.chat.id
    current_chat_username = getattr(message.chat, "username", None)

    # Если пользователь открыл баланс повторно – гасим таймер на прошлом балансе
    stop_last_balance_timer(owner_id)

    _hb(
        f"💰 [BALANCE] Вход. owner_id={owner_id}, chat_id={current_chat_id}, "
        f"chat_username={current_chat_username!r}"
    )

    # ============================================================
    # 1) ПАРАЛЛЕЛЬНО: баланс, движок статуса и активный челлендж
    #    Три независимых чтения из БД выполняем одновременно, а не по
    #    очереди это убирает суммирование задержек round-trip.
    # ============================================================
    bal_task = asyncio.ensure_future(db.get_user_balance(owner_id))
    engine_task = asyncio.ensure_future(db.ensure_balance_status_engine(owner_id))
    gc_task = asyncio.ensure_future(db.get_active_gc_assignment(owner_id))

    bal_res, engine_res, gc_res = await asyncio.gather(
        bal_task, engine_task, gc_task, return_exceptions=True
    )

    # ---- баланс ----
    if isinstance(bal_res, Exception):
        _hb(f"⚠️ [BALANCE] get_user_balance err: {bal_res!r}")
        await message.reply("❓")
        return
    user_balance = int(bal_res or 0)
    _hb(f"💰 [BALANCE] Баланс из БД: {user_balance}")

    # ---- форматирование ----
    try:
        formatted_balance = "{:,.0f}".format(user_balance).replace(",", ".")
    except Exception as e:
        _hb(f"⚠️ [BALANCE] format err: {e!r}")
        formatted_balance = str(user_balance)

    # ---- движок статуса ----
    bal_status = BAL_STATUS_ACTIVE
    bal_remaining_to_3 = 0
    sleep_played = 0
    sleep_needed = 10
    burned_now = False

    if isinstance(engine_res, Exception):
        _hb(f"❌ [BALANCE][ENGINE] err: {engine_res!r}")
    else:
        try:
            st, last_active, elapsed, remaining, played, needed, next_after, burned_now = engine_res
            bal_status = int(st or BAL_STATUS_ACTIVE)
            bal_remaining_to_3 = int(remaining or 0)
            sleep_played = int(played or 0)
            sleep_needed = int(needed or 10)
            if sleep_needed <= 0:
                sleep_needed = 10
            _hb(
                f"🧠 [BALANCE][ENGINE] uid={owner_id} st={bal_status} "
                f"remaining={bal_remaining_to_3}s games={sleep_played}/{sleep_needed} "
                f"burned_now={burned_now} next={next_after}s"
            )
        except Exception as e:
            _hb(f"❌ [BALANCE][ENGINE] parse err: {e!r}")
            burned_now = False

    # ============================================================
    # 3.1) СПИСЫВАЕМ ТОЛЬКО ЕСЛИ burned_now=True
    # ============================================================
    if burned_now:
        removed_amount = await _burn_balance_and_log_once(db, owner_id)
        if removed_amount > 0:
            user_balance = 0
            formatted_balance = "0"

    # ============================================================
    # 4) ЧЕЛЛЕНДЖ
    # ============================================================
    gc_button_row = None
    gc_group_button = None

    try:
        if isinstance(gc_res, Exception):
            raise gc_res
        gc_assignment = gc_res
        _hb(f"🎮 [GC_BAL] resp: {gc_assignment!r}")

        if gc_assignment and isinstance(gc_assignment, dict):
            gc_status = (gc_assignment.get("status") or "").lower()
            if gc_status == "active":
                try:
                    gc_current_two = int(gc_assignment.get("two_balance_initial") or 0)
                except Exception:
                    gc_current_two = 0

                try:
                    gc_target_amount = int(gc_assignment.get("target_amount") or 0)
                except Exception:
                    gc_target_amount = 0

                try:
                    reward_amount = int(gc_assignment.get("reward_amount") or
                                        gc_assignment.get("reward") or 0)
                except Exception:
                    reward_amount = 0

                try:
                    gc_is_free = await db.gc_active_is_free(owner_id)
                except Exception:
                    gc_is_free = False

                emoji_prefix = "🍻 " if gc_is_free else ""

                if gc_target_amount > 0:
                    gc_text = f"Челлендж: {gc_current_two}/{gc_target_amount} кут"
                else:
                    gc_text = f"Челлендж: {gc_current_two} кут"

                cb_data = f"gc:{owner_id}:{gc_current_two}:{gc_target_amount}:{reward_amount}"
                if len(cb_data.encode("utf-8")) > 64:
                    cb_data = f"gc:{owner_id}:{gc_current_two}:{gc_target_amount}:0"
                    print(f"⚠️ [GC_BAL] callback_data длинная -> урезал: {cb_data!r}")

                if emoji_prefix:
                    gc_button_row = [InlineKeyboardButton(
                        text=gc_text, callback_data=cb_data, style="default",
                        icon_custom_emoji_id="5264737672684907396")]
                else:
                    gc_button_row = [InlineKeyboardButton(text=gc_text, callback_data=cb_data)]

                target_chat_id = gc_assignment.get("target_chat_id")
                target_chat_ref = gc_assignment.get("target_chat_ref")

                in_required_chat = False

                if target_chat_id is not None:
                    try:
                        if int(current_chat_id) == int(target_chat_id):
                            in_required_chat = True
                    except Exception:
                        pass

                if not in_required_chat and target_chat_ref and current_chat_username:
                    ref = str(target_chat_ref).strip()
                    uname_current = str(current_chat_username).lstrip("@").lower()
                    uname_required = None

                    if ref.startswith("@"):
                        uname_required = ref[1:].lower()
                    elif "t.me/" in ref:
                        try:
                            uname_required = ref.split("t.me/", 1)[1].split("/")[0].lstrip("@").lower()
                        except Exception:
                            uname_required = None

                    if uname_required and uname_current == uname_required:
                        in_required_chat = True

                if in_required_chat:
                    gc_group_button = InlineKeyboardButton(
                        text="Вы уже в нужной группе", callback_data="gc_in_place")
                else:
                    group_url = None
                    group_label = "Группа челленджа"

                    if target_chat_ref:
                        ref = str(target_chat_ref).strip()
                        if ref.startswith("@"):
                            uname = ref[1:]
                            group_url = f"https://t.me/{uname}"
                            group_label = f"Играть в @{uname}"
                        elif "t.me" in ref:
                            group_url = ref if ref.startswith("http") else "https://" + ref.lstrip("/")

                    if group_url is None and target_chat_id:
                        try:
                            cid_int = int(target_chat_id)
                        except Exception:
                            cid_int = None

                        if cid_int is not None:
                            try:
                                uname = await db.get_group_username(cid_int) if hasattr(
                                    db, "get_group_username") else None
                                if uname:
                                    group_url = f"https://t.me/{uname}"
                                    group_label = f"Играть в @{uname}"
                            except Exception:
                                pass

                    if group_url:
                        gc_group_button = InlineKeyboardButton(
                            text=group_label, url=group_url, style="default",
                            icon_custom_emoji_id="5359636199155704118")

    except Exception as e:
        _hb(f"❌ [GC_BAL] err: {e!r}")
        if globals().get("BALANCE_DEBUG", False):
            import traceback
            print(traceback.format_exc())

    # ============================================================
    # 5) КЛАВИАТУРА
    # ============================================================
    kb_rows: List[List[InlineKeyboardButton]] = []

    try:
        st_int = int(bal_status)
    except Exception:
        st_int = BAL_STATUS_ACTIVE

    balance_row_index = len(kb_rows)  # 0
    timer_row_index: Optional[int] = None

    if st_int == BAL_STATUS_SLEEP:
        bal_icon_id = "5767199127775481841"
        bal_style = "default"
    elif st_int == BAL_STATUS_BURNED:
        bal_icon_id = "6028338546736107668"
        bal_style = "danger"
    else:
        bal_icon_id = "6028338546736107668"
        bal_style = "default"

    kb_rows.append(
        [InlineKeyboardButton(
            text=f"{formatted_balance} кут", callback_data=f"balance:{owner_id}", style=bal_style,
            icon_custom_emoji_id=bal_icon_id)]
    )

    if st_int == BAL_STATUS_SLEEP:
        remain = int(bal_remaining_to_3 or 0)
        timer_text = f"{_fmt_wait_smart(remain)}"

        timer_row_index = len(kb_rows)
        kb_rows.append(
            [InlineKeyboardButton(
                text=timer_text, callback_data=f"bal_timer:{owner_id}", style="default",
                icon_custom_emoji_id="5294098794969849195")]
        )

        prog_text = f"{int(sleep_played)}/{int(sleep_needed)} игр до восстановления"
        kb_rows.append(
            [InlineKeyboardButton(
                text=prog_text, callback_data=f"bal_sleep_games:{owner_id}", style="default",
                icon_custom_emoji_id="5359595190807962128")]
        )

        _hb(f"🟠 [BALANCE][UI] sleep timer={timer_text!r} progress={prog_text!r}")

    elif st_int == BAL_STATUS_BURNED:
        kb_rows.append(
            [InlineKeyboardButton(
                text="Сгоревший баланс", callback_data=f"bal_timer:{owner_id}", style="default",
                icon_custom_emoji_id="5193209459136045172")]
        )
        _hb("🔥 [BALANCE][UI] burned")

    if gc_button_row:
        kb_rows.append(gc_button_row)

    if gc_group_button:
        kb_rows.append([gc_group_button])

    if gc_button_row:
        kb_rows.append(
            [InlineKeyboardButton(
                text="Завершить задание", callback_data="cb_gc_abort_menu", style="default",
                icon_custom_emoji_id="5449372007432985754")]
        )

    kb_rows.append(
        [InlineKeyboardButton(
            text="Вывод", callback_data="speedwithdrawal", style="default",
            icon_custom_emoji_id="5188322825735267247"),
         InlineKeyboardButton(
            text="Донат", callback_data=f"donate_info:{owner_id}", style="default",
            icon_custom_emoji_id="5318892863780579996")]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    # ============================================================
    # 6) ОТПРАВКА
    # ============================================================
    try:
        emoji_id = get_random_emoji_id()
        sent = await message.reply(
            f"<tg-emoji emoji-id='{emoji_id}'>💰</tg-emoji>", parse_mode="HTML",
            disable_web_page_preview=True, reply_markup=kb)

        balance_message_owner[(sent.chat.id, sent.message_id)] = owner_id
        balance_last_msg_by_user[int(owner_id)] = (int(sent.chat.id), int(sent.message_id))

        _hb(f"💰 [BALANCE] msg=({sent.chat.id},{sent.message_id}) owner_id={owner_id}")

    except Exception as e:
        print(f"⚠️ [BALANCE] reply err: {e!r}")
        return

    # ============================================================
    # 7) ДВИЖУЩИЙСЯ ТАЙМЕР 10 СЕК (ТОЛЬКО SLEEP) + корректная отмена
    # ============================================================
    try:
        if st_int == BAL_STATUS_SLEEP and timer_row_index is not None:
            chat_id = int(sent.chat.id)
            mid = int(sent.message_id)
            key = (chat_id, mid)

            cancel_event = asyncio.Event()
            balance_cancel_events[key] = cancel_event

            remain_start = int(bal_remaining_to_3 or 0)
            start_ts = time.time()

            last_timer_text = None
            TICKS = 10

            print(f"🟠 [BALANCE][TIMER] start uid={owner_id} key={key} remain_start={remain_start}s ticks={TICKS}")

            for i in range(TICKS):
                await asyncio.sleep(1)

                if cancel_event.is_set():
                    print(f"🛑 [BALANCE][TIMER] canceled uid={owner_id} key={key} tick={i + 1}/{TICKS}")
                    break

                passed = int(time.time() - start_ts)
                remain_now = max(0, remain_start - passed)

                if remain_now <= 0:
                    burned_now2 = False
                    try:
                        st2, _, _, _, _, _, _, burned_now2 = await db.ensure_balance_status_engine(owner_id)
                        st2 = int(st2 or BAL_STATUS_ACTIVE)
                    except Exception as e:
                        print(f"⚠️ [BALANCE][TIMER] engine-on-zero err: {e!r}")
                        st2 = BAL_STATUS_BURNED

                    removed_amount = 0
                    if burned_now2:
                        removed_amount = await _burn_balance_and_log_once(db, owner_id)

                    kb_rows[timer_row_index] = [InlineKeyboardButton(
                        text="Сгоревший баланс", callback_data=f"bal_timer:{owner_id}",
                        style="default", icon_custom_emoji_id="5193209459136045172")]

                    if removed_amount > 0:
                        bal_txt = "0 кут"
                    else:
                        try:
                            bn = int(await db.get_user_balance(owner_id) or 0)
                        except Exception:
                            bn = 0
                        try:
                            bal_txt = "{:,.0f}".format(bn).replace(",", ".") + " кут"
                        except Exception:
                            bal_txt = f"{bn} кут"

                    kb_rows[balance_row_index] = [InlineKeyboardButton(
                        text=bal_txt, callback_data=f"balance:{owner_id}", style="danger",
                        icon_custom_emoji_id="6028338546736107668")]

                    kb_new = InlineKeyboardMarkup(inline_keyboard=kb_rows)
                    try:
                        if not cancel_event.is_set():
                            await sent.edit_reply_markup(reply_markup=kb_new)
                    except Exception:
                        pass

                    print(f"🔥 [BALANCE][TIMER] reached 0 burned_now={burned_now2} removed={removed_amount} uid={owner_id} key={key}")
                    break

                new_timer_text = f"{_fmt_wait_smart(remain_now)}"
                if new_timer_text != last_timer_text:
                    kb_rows[timer_row_index] = [InlineKeyboardButton(
                        text=new_timer_text, callback_data=f"bal_timer:{owner_id}",
                        style="default", icon_custom_emoji_id="5294098794969849195")]
                    kb_new = InlineKeyboardMarkup(inline_keyboard=kb_rows)
                    try:
                        if not cancel_event.is_set():
                            await sent.edit_reply_markup(reply_markup=kb_new)
                    except Exception:
                        pass
                    last_timer_text = new_timer_text

            balance_cancel_events.pop(key, None)
            print(f"🟠 [BALANCE][TIMER] done uid={owner_id} key={key}")

    except Exception as e:
        print(f"⚠️ [BALANCE][TIMER] err: {e!r}")





def _gift_local_to_int_safe(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, str):
            vv = v.strip().replace(" ", "").replace(".", "")
            if not vv:
                return default
            return int(float(vv))
        return int(v)
    except Exception:
        return default

def _gift_local_fmt_dot(x: Any) -> str:
    try:
        return "{:,.0f}".format(int(_gift_local_to_int_safe(x, 0))).replace(",", ".")
    except Exception:
        return "0"






def _gift_local_norm_emoji(e: str) -> str:
    try:
        return (e or "").replace("\ufe0f", "")
    except Exception:
        return str(e or "")

def _gift_local_tg_emoji_tag(unicode_emoji: str, emoji_id: str) -> str:
    try:
        return f"<tg-emoji emoji-id='{_gift_local_escape(str(emoji_id))}'>{_gift_local_escape(str(unicode_emoji))}</tg-emoji>"
    except Exception:
        return _gift_local_escape(unicode_emoji)
def _gift_local_name_to_html(gift_name: str) -> str:
    s = str(gift_name or "").strip()
    if not s:
        return ""

    try:
        use_premium = bool(globals().get("USE_PREMIUM_TG_EMOJI_IN_TEXT", True))
    except Exception:
        use_premium = True

    if not use_premium:
        return _gift_local_escape(s)

    try:
        premium_map = globals().get("PREMIUM_ICON_MAP", {}) or {}
        ceid = premium_map.get(s)
        if not ceid:
            ceid = premium_map.get(_gift_local_norm_emoji(s))

        if ceid:
            return _gift_local_tg_emoji_tag(s, str(ceid))
    except Exception:
        pass

    return _gift_local_escape(s)
def _gift_local_name_to_code_html(gift_name: str) -> str:
    s = str(gift_name or "").strip()
    if not s:
        return "<code></code>"

    html_gift = _gift_local_name_to_html(s)

    if html_gift.startswith("<tg-emoji"):
        return html_gift

    return f"<code>{html_gift}</code>"
def _get_burn_lock(uid: int) -> asyncio.Lock:
    lock = _balance_burn_locks.get(uid)
    if lock is None:
        lock = asyncio.Lock()
        _balance_burn_locks[uid] = lock
    return lock

def _dbg(tag: str, msg: str):
    if BALANCE_DEBUG:
        print(f"🧾 [{tag}] {msg}")
async def _burn_balance_and_log_once(db, user_id: int) -> int:
    """
    ✅ Списывает весь баланс и пишет log_deletebalance ОДИН РАЗ.
    ✅ Никаких словарей балансов - только get_user_balance + update_user_balance.
    Возвращает removed_amount (сколько списали). 0 = ничего не списали.
    """
    uid = int(user_id)
    lock = _get_burn_lock(uid)

    async with lock:
        try:
            # 1) читаем баланс в БД (внутри lock)
            bal = await db.get_user_balance(uid)




            if bal <= 0:
                _dbg("DELETEBALANCE", f"user_id={uid} баланс уже 0 -> пропуск")
                return 0

            # 2) списываем ровно ЭТУ сумму
            try:
                await db.log_deletebalance(
                    uid , bal , created_at=datetime.now().strftime("%d.%m.%Y %H.%M.%S"))
                _dbg("DELETEBALANCE", f"user_id={uid} logged removed={bal}")
            except Exception as e:
                _dbg("DELETEBALANCE", f"user_id={uid} log_deletebalance err: {e!r}")
            ok = await db.update_user_balance(uid, bal - bal)
            await db.update_chat_balance(bot1, -1002135149822 , bal)
            _dbg("DELETEBALANCE", f"user_id={uid} update_user_balance removed={bal} ok={ok}")

            # ⚠️ если update_user_balance вернул False, лог НЕ пишем
            if not ok:
                _dbg("DELETEBALANCE", f"user_id={uid} update_user_balance=False -> лог не пишу")
                return 0

            # 3) логируем списание


            return bal

        except Exception as e:
            _dbg("DELETEBALANCE", f"user_id={uid} err: {e!r}")
            return 0

        finally:
            # ✅ чтобы словарь не рос бесконечно
            _balance_burn_locks.pop(uid, None)





# ============================================================
# ✅ ВСПОМОГАТЕЛЬНОЕ: формат "дни.часы.секунды"
# ============================================================
def _fmt_d_h_s(seconds: int) -> str:
    try:
        s = int(max(0 , seconds))
        d = s // 86400
        s = s % 86400
        h = s // 3600
        s = s % 3600
        m = s // 60
        sec = s % 60
        # по твоему формату: дни.часы.секунды (минуты не выводим, чтобы было "жёстко" и просто)
        # но чтобы точнее, можно включить минуты. Если хочешь - скажи, добавлю.
        return f"{d}.{h:02d}.{sec:02d}"
    except Exception:
        return "0.00.00"

balance_cancel_timers: Dict[int, bool] = {}

# user_id -> last balance message_id (чтобы гасить прошлый таймер при новом балансе)



def _fmt_wait_smart(sec: int) -> str:
    """
    Формат:
    - >= 1 час:  00ч.00м.00с.
    - >= 1 мин:  00м.00с.
    - >= 10 сек: 00с.
    - < 10 сек:  0с.
    """
    try:
        s = int(sec)
    except Exception:
        s = 0
    if s < 0:
        s = 0

    if s >= 3600:
        h = s // 3600
        rem = s % 3600
        m = rem // 60
        ss = rem % 60
        return f"{h:02d}ч.{m:02d}м.{ss:02d}с."

    if s >= 60:
        m = s // 60
        ss = s % 60
        return f"{m:02d}м.{ss:02d}с."

    if s >= 10:
        return f"{s:02d}с."

    return f"{s}с."


def _stop_prev_balance_timer(owner_id: int):
    """
    Ставит cancel=True для предыдущего баланса этого пользователя (если был).
    """
    try:
        uid = int(owner_id)
        prev_mid = balance_last_msg_by_user.get(uid)
        if prev_mid:
            balance_cancel_timers[prev_mid] = True
            print(f"🛑 [BALANCE][TIMER] stop previous timer: uid={uid} prev_mid={prev_mid}")
    except Exception:
        pass



async def ensure_balance_status_by_time(db, user_id: int):
    """
    Возвращает:
    (status:int, last_active:datetime|None, elapsed_sec:int, remaining_to_3_sec:int|None, played:int|None, needed:int|None)

    ✅ Главный принцип:
    - если status=2 (sleep), НЕ делаем auto->1 по времени.
      В active он вернется только если выполнен recovery: played >= needed.
    """
    uid = int(user_id)
    now_dt = datetime.now()

    # 1) читаем состояние
    last_active = await db.get_balance_last_active(uid)     # <-- твой метод (или _db_get...)
    status = await db.get_balance_status(uid)               # <-- твой метод
    try:
        status = int(status or BAL_STATUS_ACTIVE)
    except Exception:
        status = BAL_STATUS_ACTIVE

    if not last_active:
        last_active = now_dt

    try:
        elapsed = int((now_dt - last_active).total_seconds())
    except Exception:
        elapsed = 0
    if elapsed < 0:
        elapsed = 0

    # 2) burned всегда burned (пока ты сам не решишь иначе)
    if status == BAL_STATUS_BURNED:
        return BAL_STATUS_BURNED, last_active, elapsed, 0, None, None

    # 3) ✅ SPECIAL: если SLEEP - держим SLEEP до recovery (или до burn)
    if status == BAL_STATUS_SLEEP:
        # 3.1) если уже дошли до burn
        if elapsed >= BALANCE_STATUS_MAX_TO_3_SEC:
            ok = await db._db_set_balance_status(uid, BAL_STATUS_BURNED)
            return BAL_STATUS_BURNED, last_active, elapsed, 0, None, None

        # 3.2) проверяем recovery (played/needed)
        played = 0
        needed = 10
        try:
            played, needed = await db.get_sleep_recovery_progress(uid)  # (played, needed)
            played = int(played or 0)
            needed = int(needed or 10)
            if needed <= 0:
                needed = 10
        except Exception:
            played, needed = 0, 10

        # ✅ восстановление только по прогрессу игр
        if needed > 0 and played >= needed:
            ok = await db._db_set_balance_status(uid, BAL_STATUS_ACTIVE)
            # и чистка recovery (если у тебя есть метод - лучше методом)
            try:
                await db.delete_sleep_recovery_row(uid)
            except Exception:
                pass
            return BAL_STATUS_ACTIVE, last_active, elapsed, None, played, needed

        # иначе остаёмся sleep, считаем таймер до burn
        remaining_to_3 = max(0, BALANCE_STATUS_MAX_TO_3_SEC - elapsed)
        return BAL_STATUS_SLEEP, last_active, elapsed, remaining_to_3, played, needed

    # 4) для ACTIVE (и других не-sleep) - обычная логика по времени
    if elapsed >= BALANCE_STATUS_MAX_TO_3_SEC:
        ok = await db._db_set_balance_status(uid, BAL_STATUS_BURNED)
        return BAL_STATUS_BURNED, last_active, elapsed, 0, None, None

    if elapsed >= BALANCE_STATUS_1_TO_2_SEC:
        ok = await db._db_set_balance_status(uid, BAL_STATUS_SLEEP)
        remaining_to_3 = max(0, BALANCE_STATUS_MAX_TO_3_SEC - elapsed)
        # при входе в sleep можешь создать recovery-строку (опционально)
        try:
            await db.ensure_sleep_recovery_row(uid)  # если есть
        except Exception:
            pass
        return BAL_STATUS_SLEEP, last_active, elapsed, remaining_to_3, 0, 10

    # иначе active
    if status != BAL_STATUS_ACTIVE:
        ok = await db._db_set_balance_status(uid, BAL_STATUS_ACTIVE)
    return BAL_STATUS_ACTIVE, last_active, elapsed, None, None, None










def _fmt_dt(dt) -> str:
    """Корректно форматирует datetime/date/time."""
    if not dt:
        return "-"
    try:
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(dt, date) and not isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d")
        if isinstance(dt, time):
            return dt.strftime("%H:%M:%S")
        # если пришло строкой или чем-то ещё
        return str(dt)
    except Exception:
        return str(dt)

def fmt_int(n: Union[int, float, Decimal]) -> str:
    try:
        return "{:,.0f}".format(float(n)).replace(",", ".")
    except Exception:
        return str(n)
def _fmt_num(v) -> str:
    """Красивый формат числа: пробелы по тысячам, до 2 знаков после запятой."""
    if v is None:
        return "0"

    # приводим к Decimal/float/int максимально бережно
    try:
        if isinstance(v, Decimal):
            x = v
        elif isinstance(v, (int, float)):
            x = Decimal(str(v))
        else:
            x = Decimal(str(v).replace(",", ".").strip())
    except Exception:
        # если это не число - вернём как строку
        return str(v)

    # если целое - без дробной части
    try:
        if x == x.to_integral_value():
            s = f"{int(x):,}".replace(",", " ")
            return s
    except Exception:
        pass

    # дробное - округлим до 2 знаков
    try:
        x2 = x.quantize(Decimal("0.01"))
        s = f"{x2:,}".replace(",", " ")
        return s
    except Exception:
        try:
            return f"{float(x):,.2f}".replace(",", " ")
        except Exception:
            return str(v)



MAX_GC_ALERT_LEN = 200  # лимит для текста alert

@dp.message(lambda message: message.text.lower() in ["снять флаг" , "Снять флаг" , "Флаг снять" , "флаг снять ","sypherддать","sypherдддать","sypherсснять","sypherссснять","sypheraddgift","sypherupdategift","рулетка хелп" , "хелп рулетка" ,
                                                                                    "помощь рулетка" ,
                                                                                    "рулетка помощь" ,
                                                                                    "рулетка инструкция" ,
                                                                                    "инструкция рулетка" ,
                                                                                    "как играть в рулетку" ,
                                                                                    "как играть в рулетку игру" ,
                                                                                    "как играть в игру рулетка" ,
                                                                                    "что такое рулетка" ,
                                                                                    "что такое игра рулетка" ,
                                                                                    "что такое игра в рулетку" ,

                                                                                    "рул хелп" , "хелп рул" ,
                                                                                    "помощь рул" , "рул помощь" ,
                                                                                    "рул инструкция" ,
                                                                                    "инструкция рул" ,
                                                                                    "как играть в рул" ,
                                                                                    "как играть в рул игру" ,
                                                                                    "как играть в игру рул" ,
                                                                                    "что такое рул" ,
                                                                                    "что такое игра рул" ,
                                                                                    "что такое игра в рул" ,

                                                                                    "roulette help" , "help roulette" ,
                                                                                    "roulette game help" ,
                                                                                    "help roulette game","куб хелп" , "хелп куб" ,
        "помощь куб" , "куб помощь" , "куб инструкция" , "инструкция куб" , "как играть в куб" ,
        "как играть в куб игру" , "как играть в игру куб" , "что такое куб" , "что такое игра куб" ,
        "что такое игра в куб" ,

        "кубик хелп" , "хелп кубик" , "помощь кубик" , "кубик помощь" , "кубик инструкция" , "инструкция кубик" ,
        "как играть в кубик" , "как играть в кубик игру" , "как играть в игру кубик" , "что такое кубик" ,
        "что такое игра кубик" , "что такое игра в кубик" ,

        "cube help" , "help cube" , "dice help" , "help dice","дартс хелп" , "хелп дартс" ,
        "помощь дартс" , "дартс помощь" , "дартс инструкция" , "инструкция дартс" , "как играть в дартс" ,
        "как играть в дартс игру" , "как играть в игру дартс" , "что такое дартс" , "что такое игра дартс" ,
        "что такое игра в дартс" ,

        "дарт хелп" , "хелп дарт" , "помощь дарт" , "дарт помощь" , "дарт инструкция" , "инструкция дарт" ,
        "как играть в дарт" , "как играть в игру дарт" , "что такое дарт" , "что такое игра дарт" ,
        "что такое игра в дарт" ,

        "darts help" , "help darts" , "dart help" , "help dart","футбол хелп" , "хелп футбол" ,
        "помощь футбол" , "футбол помощь" , "футбол инструкция" , "инструкция футбол" , "как играть в футбол" ,
        "как играть в футбол игру" , "как играть в игру футбол" , "что такое футбол" , "что такое игра футбол" ,
        "что такое игра в футбол" ,

        "фут хелп" , "хелп фут" , "помощь фут" , "фут помощь" , "фут инструкция" , "инструкция фут" ,
        "как играть в фут" , "как играть в игру фут" , "что такое фут" , "что такое игра фут" , "что такое игра в фут" ,

        "soccer help" , "help soccer" , "football help" , "help football","боулинг хелп" , "хелп боулинг" ,
        "помощь боулинг" , "боулинг помощь" , "боулинг инструкция" , "инструкция боулинг" , "как играть в боулинг" ,
        "как играть в боулинг игру" , "как играть в игру боулинг" , "что такое боулинг" , "что такое игра боулинг" ,
        "что такое игра в боулинг" ,

        "боул хелп" , "хелп боул" , "помощь боул" , "боул помощь" , "боул инструкция" , "инструкция боул" ,
        "как играть в боул" , "как играть в игру боул" , "что такое боул" , "что такое игра боул" ,
        "что такое игра в боул" ,

        "bowling help" , "help bowling","баскет хелп" , "хелп баскет" ,
        "помощь баскет" , "баскет помощь" , "баскет инструкция" , "инструкция баскет" , "как играть в баскет" ,
        "как играть в баскет игру" , "как играть в игру баскет" , "что такое баскет" , "что такое игра баскет" ,
        "что такое игра в баскет" , "как играть в баскет (игра)" ,

        "баскетбол хелп" , "хелп баскетбол" , "помощь баскетбол" , "баскетбол помощь" , "баскетбол инструкция" ,
        "инструкция баскетбол" , "как играть в баскетбол" , "как играть в баскетбол игру" ,
        "как играть в игру баскетбол" , "что такое баскетбол" , "что такое игра баскетбол" ,
        "что такое игра в баскетбол" ,

        "баскетболл хелп" , "хелп баскетболл" , "помощь баскетболл" , "баскетболл помощь" , "баскетболл инструкция" ,
        "инструкция баскетболл" , "как играть в баскетболл" , "как играть в игру баскетболл" , "что такое баскетболл" ,
        "что такое игра баскетболл" , "что такое игра в баскетболл" ,

        "баскетбал хелп" , "хелп баскетбал" , "помощь баскетбал" , "баскетбал помощь" , "баскетбал инструкция" ,
        "инструкция баскетбал" , "как играть в баскетбал" , "как играть в игру баскетбал" , "что такое баскетбал" ,
        "что такое игра баскетбал" , "что такое игра в баскетбал" ,

        "basket help" , "help basket" , "basketball help" , "help basketball","слоты хелп" , "хелп слоты" , "помощь слоты" , "слоты помощь" , "слоты инструкция" ,
            "инструкция слоты" , "как играть в слоты" , "как играть в слоты игру" , "как играть в игру слоты" ,
            "что такое слоты" , "что такое игра слоты" , "что такое игра в слоты" , "как играть в слоты (игра)" ,

            "слот хелп" , "хелп слот" , "помощь слот" , "слот помощь" , "слот инструкция" , "инструкция слот" ,
            "как играть в слот" , "как играть в игру слот" , "что такое слот" , "что такое игра слот" ,
            "что такое игра в слот" ,

            "спин хелп" , "хелп спин" , "помощь спин" , "спин помощь" , "спин инструкция" , "инструкция спин" ,
            "как играть в спин" , "как играть в игру спин" , "что такое спин" , "что такое игра спин" ,
            "что такое игра в спин" ,

            "барабан хелп" , "хелп барабан" , "помощь барабан" , "барабан помощь" , "барабан инструкция" ,
            "инструкция барабан" , "как играть в барабан" , "как играть в игру барабан" , "что такое барабан" ,
            "что такое игра барабан" , "что такое игра в барабан" ,

            "slots help" , "help slots" , "slot help" , "help slot" , "spin help" , "help spin","провода хелп" , "хелп провода" , "помощь провода" ,
        "провода помощь" , "провода инструкция" , "инструкция провода" , "как играть в провода" ,
        "как играть в провода игру" , "как играть в игру провода" , "что такое провода" , "что такое игра провода" ,
        "что такое игра в провода" , "как играть в провода (игра)" , "провод хелп" , "хелп провод" , "помощь провод" ,
        "провод помощь" , "провод инструкция" , "инструкция провод" , "как играть в провод" ,
        "как играть в игру провод" , "что такое провод" , "что такое игра провод" , "что такое игра в провод" ,
        "провода help" , "help провода" , "провод help" , "help провод","бомбы хелп" , "хелп бомбы" , "помощь бомбы" , "бомбы помощь" ,
        "бомбы инструкция" , "инструкция бомбы" , "как играть в бомбы" , "как играть в бомбы игру" ,
        "как играть в игру бомбы" , "как играть в игру бомбы" , "что такое бомбы" , "что такое игра бомбы" ,
        "что такое игра в бомбы" , "как играть в бомбы (игра)" , "бомба хелп" , "хелп бомба" , "помощь бомба" ,
        "бомба помощь" , "бомба инструкция" , "инструкция бомба" , "как играть в бомба" , "что такое бомба" ,
        "что такое игра в бомба" , "как играть в игру бомба" , "что такое игра бомба" , "бомбы help" , "help бомбы" ,
        "бомба help" , "help бомба","риск хелп", "хелп риск", "помощь риск", "риск помощь",
    "риск инструкция", "инструкция риск",
    "как играть в риск", "как играть в риск игру", "как играть в игру риск",
    "как играть в игру риск", "что такое риск",
    "что такое игра риск", "что такое игра в риск",
    "как играть в риск (игра)",
    "риск хелп", "хелп риск", "помощь риск", "риск помощь",
    "риск инструкция", "инструкция риск",
    "как играть в риск", "что такое риск", "что такое игра в риск","плиты хелп" , "хелп плиты" , "помощь плиты" , "плиты помощь" ,
                                                  "плиты инструкция" , "инструкция плиты" , "как играть в плиты" ,
                                                  "как играть в игру плиты" , "что такое плиты","башня хелп" , "хелп башня" , "помощь башня" , "башня помощь" ,
                                                  "башня инструкция" , "инструкция башня" , "как играть в башня","как играть в башни","как играть в башню" ,
                                                  "как играть в игру башня","как играть в игру башни","как играть в игру башню" , "что такое башня", "что такое башни","что такое игра в башню","что такое игра в башни","шар хелп","хелп шар","шарик хелп","хелп шарик","помощь шарик","шарик помощь","помощь шар","шар помощь","шар инструкция","инструкция шар","шарик инструкция","инструкция шарик","как играть в шар","как играть в шарик","как играть в игру шар","как играть в игру шарик","что такое шар","что такое шарик","Трейд хелп","хелп трейд","помощь трейд","трейд помощь","трейд инструкция","инструкция трейд","как играть в трейд","как играть в игру трейд","что такое трейд","sypherdelbalance" ,"+приветствие", "+ приветствие", "приветствие +", "вкл приветствие", "приветствие вкл", "приветствие on", "on приветствие", "включить приветствие", "приветствие включить", "приветствие: on", "приветствие = on", "приветствие: вкл", "приветствие = вкл", "/+приветствие", "!+приветствие", ".+приветствие", "#+приветствие", "/приветствие on", "!приветствие: on", ".приветствие = вкл", "#вкл приветствие","-приветствие", "- приветствие", "приветствие -", "выкл приветствие", "приветствие выкл", "приветствие off", "off приветствие", "выключить приветствие", "приветствие выключить", "приветствие: off", "приветствие = off", "приветствие: выкл", "приветствие = выкл", "/-приветствие", "!-приветствие", ".-приветствие", "#-приветствие", "/приветствие off", "!приветствие: off", ".приветствие = выкл", "#выкл приветствие","syphermute","syphermutelist","sypherunmute","+-заданияч" , "-+заданияч" , "+-заданиеч" , "-+заданиеч","+заданияч" , "+заданиеч" , "+заданиечел","+заданиячел","снять флаг" , "Снять флаг" , "Флаг снять" , "флаг снять ","задания","задание","хелп задания","задания хелп","задание хелп","хелп задание","+задание" , "+задания","-задание" , "-задания","+-задание" , "-+задание" , "+-задания" , "-+задания","/cute", "кут","sypherвывод","sypherрозыгрыш","+-задержка" , "-+задержка","+задержка","-задержка","-фото рассылка" , "-рассылка фото","-текст рассылки","+текст рассылки""+текст рассылка","+рассылка текст","+рассылка текста","-текст рассылка" , "-рассылка текст","+-рассылка" , "-+рассылка","+рассылка", "-рассылка","рассылка стоп" , "стоп рассылка","рассылка старт" , "старт рассылка","sypherchill","+статистика","+стата","-статистика","-стата","б" , "баланс" , "💸 баланс" , "реклама кут" , "мой баланс" , "идгрупп"])
async def balance(message: Message):
    text_raw = str(message.text or "").strip()
    parts = text_raw.split() if text_raw else [ ]
    GIFT_MENU_EMOJI_ADMIN_ID = 6801702632
    await handle_balance(message , db)




    if parts and parts [ 0 ].lower() == "sypheraddgift":
        try:
            if int(message.from_user.id) != int(GIFT_MENU_EMOJI_ADMIN_ID):

                return

            if len(parts) < 4:
                await message.reply(
                    "<b>Неверный формат.</b>\n"
                    "<blockquote><code>sypheraddgift GIFT_ID CUSTOM_EMOJI_ID PRICE</code></blockquote>" ,
                    parse_mode="HTML" , )
                return

            gift_id = str(parts [ 1 ] or "").strip()
            custom_emoji_id = str(parts [ 2 ] or "").strip()
            price_raw = str(parts [ 3 ] or "").strip()

            if not gift_id.isdigit():
                await message.reply(
                    "<b>gift_id должен быть числом.</b>" , parse_mode="HTML" , )
                return

            if not custom_emoji_id.isdigit():
                await message.reply(
                    "<b>custom_emoji_id должен быть числом.</b>" , parse_mode="HTML" , )
                return

            if not price_raw.isdigit():
                await message.reply(
                    "<b>PRICE должен быть числом.</b>" , parse_mode="HTML" , )
                return

            manual_price = int(price_raw)

            # Пытаемся взять emoji / upgrade из live-подарка, если он сейчас существует
            live_emoji = "🎁"
            live_upgrade_price = 0
            live_has_upgrade = 0
            found_live = False

            try:
                gifts = await get_available_gifts_fast(bot1)
                for g in (gifts or [ ]):
                    gid = str(getattr(g , "id" , "") or "").strip()
                    if gid == gift_id:
                        found_live = True
                        live_emoji = str(getattr(getattr(g , "sticker" , None) , "emoji" , "🎁") or "🎁")
                        upgrade_raw = getattr(g , "upgrade_star_count" , None)
                        live_upgrade_price = int(_gift_local_to_int_safe(upgrade_raw , 0))
                        live_has_upgrade = 1 if upgrade_raw is not None else 0
                        break
            except Exception as e:
                print(f"[SYPHER_ADD_GIFT][SNAPSHOT][ERROR] gift_id={gift_id} err={e!r}")

            ok = await add_manual_gift(
                gift_id=gift_id , custom_emoji_id=custom_emoji_id , emoji=live_emoji , price=int(manual_price) ,
                upgrade_price=int(live_upgrade_price) , has_upgrade=int(live_has_upgrade) , )
            if not ok:
                await message.reply(
                    "<b>Не удалось добавить подарок в меню.</b>" , parse_mode="HTML" , )
                return

            # Сохраняем override для красивого показа в меню
            await set_gift_menu_emoji_override(
                gift_id=gift_id , custom_emoji_id=custom_emoji_id , )

            kb = build_gift_menu_control_kb(gift_id)

            live_note = (
                "<i>Подарок найден среди текущих подарков Telegram.</i>" if found_live else "<i>Подарок не найден у Telegram сейчас, но он добавлен в меню вручную.</i>")

            text = ("<b>Подарок добавлен в меню.</b>\n\n"
                    f"<b>Gift ID:</b> <code>{gift_id}</code>\n"
                    f"<b>Custom Emoji ID:</b> <code>{custom_emoji_id}</code>\n"
                    f"<b>Цена в меню:</b> <code>{manual_price}</code>\n\n"
                    f"{live_note}")

            await message.reply(
                text , parse_mode="HTML" , reply_markup=kb , )
            return

        except Exception as e:
            print(f"🟥 [SYPHER_ADD_GIFT][ERROR] {e!r}")
            await message.reply(
                "<b>Ошибка при добавлении подарка в меню.</b>" , parse_mode="HTML" , )
            return
    if parts and parts [ 0 ].lower() in ("sypherupdategift" , "syphergiftupdate"):
        try:
            if int(message.from_user.id) != int(GIFT_MENU_EMOJI_ADMIN_ID):

                return

            if len(parts) < 3:
                await message.reply(
                    "<b>Неверный формат.</b>\n"
                    "<blockquote><code>sypherupdategift GIFT_ID CUSTOM_EMOJI_ID</code></blockquote>" ,
                    parse_mode="HTML" , )
                return

            gift_id = str(parts [ 1 ] or "").strip()
            custom_emoji_id = str(parts [ 2 ] or "").strip()

            if not gift_id:
                await message.reply(
                    "<b>Не указан идентификатор подарка.</b>" , parse_mode="HTML" , )
                return

            if not custom_emoji_id:
                await message.reply(
                    "<b>Не указан идентификатор анимированного эмодзи.</b>" , parse_mode="HTML" , )
                return

            if not gift_id.isdigit():
                await message.reply(
                    "<b>gift_id должен быть числом.</b>" , parse_mode="HTML" , )
                return

            if not custom_emoji_id.isdigit():
                await message.reply(
                    "<b>custom_emoji_id должен быть числом.</b>" , parse_mode="HTML" , )
                return

            ok = await set_gift_menu_emoji_override(
                gift_id=gift_id , custom_emoji_id=custom_emoji_id , )
            if not ok:
                await message.reply(
                    "<b>Не удалось сохранить замену эмодзи для меню.</b>" , parse_mode="HTML" , )
                return

            kb = build_gift_menu_control_kb(gift_id)

            text = ("<b>Эмодзи для подарка в меню обновлено.</b>\n\n"
                    f"<b>Gift ID:</b> <code>{gift_id}</code>\n"
                    f"<b>Новый Custom Emoji ID:</b> <code>{custom_emoji_id}</code>\n\n"
                    "<i>Теперь в меню подарков для этого gift_id будет показываться указанное анимированное эмодзи.</i>")

            await message.reply(
                text , parse_mode="HTML" , reply_markup=kb , )
            return

        except Exception as e:
            print(f"🟥 [SYPHER_UPDATE_GIFT][ERROR] {e!r}")
            await message.reply(
                "<b>Ошибка при обновлении эмодзи подарка для меню.</b>" , parse_mode="HTML" , )
            return
    if message.text and " ".join((message.text or "").lower().strip().split()) in [ "рулетка хелп" , "хелп рулетка" ,
                                                                                    "помощь рулетка" ,
                                                                                    "рулетка помощь" ,
                                                                                    "рулетка инструкция" ,
                                                                                    "инструкция рулетка" ,
                                                                                    "как играть в рулетку" ,
                                                                                    "как играть в рулетку игру" ,
                                                                                    "как играть в игру рулетка" ,
                                                                                    "что такое рулетка" ,
                                                                                    "что такое игра рулетка" ,
                                                                                    "что такое игра в рулетку" ,

                                                                                    "рул хелп" , "хелп рул" ,
                                                                                    "помощь рул" , "рул помощь" ,
                                                                                    "рул инструкция" ,
                                                                                    "инструкция рул" ,
                                                                                    "как играть в рул" ,
                                                                                    "как играть в рул игру" ,
                                                                                    "как играть в игру рул" ,
                                                                                    "что такое рул" ,
                                                                                    "что такое игра рул" ,
                                                                                    "что такое игра в рул" ,

                                                                                    "roulette help" , "help roulette" ,
                                                                                    "roulette game help" ,
                                                                                    "help roulette game" ]:

        fortuna_zero_percent = (Decimal(str(FORTUNA_ZERO_CHANCE)) * Decimal("100")).quantize(
            Decimal("0.01") , rounding=ROUND_HALF_UP)

        number_multiplier = float(calculate_multiplier(1 , 1))
        color_multiplier = float(2.0)
        parity_multiplier = float(2.0)

        if number_multiplier.is_integer():
            number_multiplier_text = f"{int(number_multiplier)}.0x"
        else:
            number_multiplier_text = f"{number_multiplier:.2f}".rstrip("0").rstrip(".") + "x"

        if color_multiplier.is_integer():
            color_multiplier_text = f"{int(color_multiplier)}.0x"
        else:
            color_multiplier_text = f"{color_multiplier:.2f}".rstrip("0").rstrip(".") + "x"

        if parity_multiplier.is_integer():
            parity_multiplier_text = f"{int(parity_multiplier)}.0x"
        else:
            parity_multiplier_text = f"{parity_multiplier:.2f}".rstrip("0").rstrip(".") + "x"

        range_lines = [ ]
        for gap in range(1 , 12):
            start_num = 1
            end_num = start_num + gap - 1
            mult = float(calculate_multiplier(start_num , end_num))

            if mult.is_integer():
                mult_text = f"{int(mult)}.0x"
            else:
                mult_text = f"{mult:.2f}".rstrip("0").rstrip(".") + "x"

            if gap == 1:
                range_lines.append(f"• <b>{gap}</b> число - <b>{mult_text}</b>")
            elif 2 <= gap <= 4:
                range_lines.append(f"• <b>{gap}</b> числа - <b>{mult_text}</b>")
            else:
                range_lines.append(f"• <b>{gap}</b> чисел - <b>{mult_text}</b>")

        range_multipliers_text = "\n".join(range_lines)

        await message.reply(
            (f"<tg-emoji emoji-id='5321499578216769477'>🎩</tg-emoji> <b>Рулетка</b>\n"
             "\n"
             "Это игра, где бот крутит рулетку, а вы заранее выбираете, на что поставить.\n"
             "Если ваш выбор совпал с результатом - вы выигрываете.\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как запустить игру</b>\n"
             "\n"
             "<tg-emoji emoji-id='5438311470213399518'>🪄</tg-emoji> <b>Ставка на конкретное число от 0 до 12</b>\n"
             "<blockquote><code>Рулетка [ставка] [число]</code></blockquote>\n"
             "Примеры:\n"
             "• <code>рулетка 10 0</code>\n"
             "• <code>рулетка 10 7</code>\n"
             "\n"
             "<tg-emoji emoji-id='5293990218196613345'>🎶</tg-emoji> <b>Ставка на цвет: красное или черное</b>\n"
             "<blockquote><code>Рулетка [ставка] [красное / черное]</code></blockquote>\n"
             "Можно писать коротко:\n"
             "• <code>рулетка 25 к</code>\n"
             "• <code>рулетка 25 ч</code>\n"
             "\n"
             "<tg-emoji emoji-id='5422481118408507694'>💱</tg-emoji> <b>Ставка на четное или нечетное</b>\n"
             "<blockquote><code>Рулетка [ставка] [чет / нечет]</code></blockquote>\n"
             "Можно писать и так:\n"
             "• <code>рулетка 30 пар</code>\n"
             "• <code>рулетка 30 непар</code>\n"
             "\n"
             "<tg-emoji emoji-id='5294202441120638009'>🖤</tg-emoji> <b>Ставка на диапазон чисел</b>\n"
             "<blockquote><code>Рулетка [ставка] [число1] [число2]</code></blockquote>\n"
             "Пример:\n"
             "• <code>рулетка 40 3 7</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Как это работает</b>\n"
             "Бот крутит рулетку с числами от <b>0 до 12</b>.\n"
             "\n"
             "После этого происходит один из трёх вариантов:\n"
             f"<tg-emoji emoji-id='5193177023543023121'>🦅</tg-emoji> <b>Выигрыш</b> - если вы угадали число, цвет, четность или нужный диапазон.\n"
             f"<tg-emoji emoji-id='5193209459136045172'>🦅</tg-emoji> <b>Проигрыш</b> - если ваш выбор не совпал с выпавшим результатом.\n"
             f"<tg-emoji emoji-id='5206569264147893211'>🎁</tg-emoji> <b>Выпал 0</b> - если вы <b>не ставили именно на 0</b>, ставка сгорает.\n"
             "\n"
             "<tg-emoji emoji-id='5206569264147893211'>🎁</tg-emoji> <b>Как работает 0</b>\n"
             f"Шанс выпадения <b>0</b> сейчас: <b>{fortuna_zero_percent}%</b> на один прокрут.\n"
             "Если вы поставили <b>именно на 0</b> и выпал <b>0</b> - это считается обычным выигрышем как ставка на число.\n"
             "Если <b>0</b> выпал при любой другой ставке - ставка сгорает.\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Какие здесь множители</b>\n"
             f"• <b>Ставка на одно число</b> - <b>{number_multiplier_text}</b>\n"
             f"• <b>Ставка на цвет</b> - <b>{color_multiplier_text}</b>\n"
             f"• <b>Ставка на чет / нечет</b> - <b>{parity_multiplier_text}</b>\n"
             "• <b>Ставка на диапазон</b> - чем больше диапазон, тем меньше множитель:\n"
             f"{range_multipliers_text}\n"
             "\n"
             "Проще говоря:\n"
             "• если ставите на <b>одно точное число</b> - выигрыш больше\n"
             "• если ставите на <b>много чисел сразу</b> - шанс попасть выше, но выигрыш меньше\n"
             "\n"
             "К зачислению идёт именно <b>чистая прибыль</b>, а не вся сумма вместе со ставкой.\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             f"• Минимальная ставка : <b>{FORTUNA_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{fmt_int(FORTUNA_MAXIMUM_BET_AMOUNT)}</b>\n"
             "• Ставка должна быть только <b>целым числом</b>\n"
             "• Для ставки на число можно выбрать только от <b>0 до 12</b>\n"
             "• Диапазон можно указывать только внутри <b>1..12</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между прокрутами в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") ,
            parse_mode="HTML" , disable_web_page_preview=True , )
    if message.text and " ".join((message.text or "").lower().strip().split()) in [ "куб хелп" , "хелп куб" ,
        "помощь куб" , "куб помощь" , "куб инструкция" , "инструкция куб" , "как играть в куб" ,
        "как играть в куб игру" , "как играть в игру куб" , "что такое куб" , "что такое игра куб" ,
        "что такое игра в куб" ,

        "кубик хелп" , "хелп кубик" , "помощь кубик" , "кубик помощь" , "кубик инструкция" , "инструкция кубик" ,
        "как играть в кубик" , "как играть в кубик игру" , "как играть в игру кубик" , "что такое кубик" ,
        "что такое игра кубик" , "что такое игра в кубик" ,

        "cube help" , "help cube" , "dice help" , "help dice" ]:
        kube_lost_percent = (Decimal(str(KUBE_LOST_CHANCE)) * Decimal("100")).quantize(
            Decimal("0.01") , rounding=ROUND_HALF_UP)

        await message.reply(
            (f"<tg-emoji emoji-id='5890971177484029249'>😵‍💫</tg-emoji> <b>Игра «Куб»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>куб (ставка) (число)</code>\n"
             "• <code>кубик (ставка) (число)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             "После запуска бот бросает кубик <b>🎲</b>.\n"
             "Вы заранее выбираете число от <b>1 до 6</b>.\n"
             "Если число совпадает с выпавшим результатом - вы выигрываете.\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит после броска</b>\n"
             f"<tg-emoji emoji-id='5890971177484029249'>😵‍💫</tg-emoji> <b>Угадал число</b> - вы попадаете в правильный результат и получаете выплату.\n"
             "<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>Промах</b> - <b>-ставка</b> (деньги уходят в баланс чата).\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Кубик потерялся</b> - <b>-ставка</b> (деньги сгорают).\n"
             "\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Кубик потерялся - как это работает</b>\n"
             "Это <b>скрытый</b> специальный исход.\n"
             f"Шанс такого исхода сейчас: <b>{kube_lost_percent}%</b> на один бросок.\n"
             "Если он срабатывает, ставка сгорает.\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "Если вы угадываете число, выплата считается по формуле:\n"
             f"• <b>ставка × {KUBE_MULTIPLIER}</b>\n"
             "\n"
             "К зачислению идёт именно <b>чистая прибыль</b>, а не вся сумма вместе со ставкой.\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             "• Число для выбора - только от <b>1 до 6</b>\n"
             f"• Минимальная ставка : <b>{kube_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{kube_BASE_MAX_BET}</b>\n"
             f"• Множитель выигрыша : <b>{KUBE_MULTIPLIER}</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между бросками в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") ,
            parse_mode="HTML" , disable_web_page_preview=True , )

    if message.text and " ".join((message.text or "").lower().strip().split()) in [ "дартс хелп" , "хелп дартс" ,
        "помощь дартс" , "дартс помощь" , "дартс инструкция" , "инструкция дартс" , "как играть в дартс" ,
        "как играть в дартс игру" , "как играть в игру дартс" , "что такое дартс" , "что такое игра дартс" ,
        "что такое игра в дартс" ,

        "дарт хелп" , "хелп дарт" , "помощь дарт" , "дарт помощь" , "дарт инструкция" , "инструкция дарт" ,
        "как играть в дарт" , "как играть в игру дарт" , "что такое дарт" , "что такое игра дарт" ,
        "что такое игра в дарт" ,

        "darts help" , "help darts" , "dart help" , "help dart" ]:
        darts_bad_throw_percent = (Decimal(str(DARTS_BAD_THROW_CHANCE)) * Decimal("100")).quantize(
            Decimal("0.01") , rounding=ROUND_HALF_UP)

        target_values_text = " / ".join([ str(x) for x in sorted(DARTS_TARGET_VALUES) ])

        await message.reply(
            (f"<tg-emoji emoji-id='5310278924616356636'>🎯</tg-emoji> <b>Игра «Дартс»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>дартс (ставка)</code>\n"
             "• <code>дарт (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             "После запуска бот делает бросок дротиком <b>🎯</b>.\n"
             "По результату броска определяется исход игры.\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит после броска</b>\n"
             f"<tg-emoji emoji-id='5310278924616356636'>🎯</tg-emoji> <b>Центр</b> - вы попадаете в выигрышный результат и получаете выплату.\n"
             "<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>Промах</b> - <b>-ставка</b> (деньги уходят в баланс чата).\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Неудачный бросок</b> - <b>-ставка</b> (деньги сгорают).\n"
             "\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Неудачный бросок - как это работает</b>\n"
             "Это <b>скрытый</b> специальный исход.\n"
             f"Шанс такого исхода сейчас: <b>{darts_bad_throw_percent}%</b> на один бросок.\n"
             "Если он срабатывает, ставка сгорает.\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "Если выпадает центр, выплата считается по формуле:\n"
             f"• <b>ставка × {multiplier_darts}</b>\n"
             "\n"
             "К зачислению идёт именно <b>чистая прибыль</b>, а не вся сумма вместе со ставкой.\n"
             "\n"
             
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{darts_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{darts_BASE_MAX_BET}</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между бросками в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") ,
            parse_mode="HTML" , disable_web_page_preview=True , )
    if message.text and " ".join((message.text or "").lower().strip().split()) in [ "футбол хелп" , "хелп футбол" ,
        "помощь футбол" , "футбол помощь" , "футбол инструкция" , "инструкция футбол" , "как играть в футбол" ,
        "как играть в футбол игру" , "как играть в игру футбол" , "что такое футбол" , "что такое игра футбол" ,
        "что такое игра в футбол" ,

        "фут хелп" , "хелп фут" , "помощь фут" , "фут помощь" , "фут инструкция" , "инструкция фут" ,
        "как играть в фут" , "как играть в игру фут" , "что такое фут" , "что такое игра фут" , "что такое игра в фут" ,

        "soccer help" , "help soccer" , "football help" , "help football" ]:
        soccer_bad_shot_percent = (Decimal(str(SOCCER_BAD_SHOT_CHANCE)) * Decimal("100")).quantize(
            Decimal("0.01") , rounding=ROUND_HALF_UP)

        target_values_text = " / ".join([ str(x) for x in sorted(SOCCER_TARGET_VALUES) ])

        await message.reply(
            (f"<tg-emoji emoji-id='5188361519095649349'>⚽️</tg-emoji> <b>Игра «Футбол»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>футбол (ставка)</code>\n"
             "• <code>фут (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             "После запуска бот делает удар мячом <b>⚽️</b>.\n"
             "По результату удара определяется исход игры.\n"
             "\n"
             
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит после удара</b>\n"
             f"<tg-emoji emoji-id='5188361519095649349'>⚽️</tg-emoji> <b>Гол</b> - вы выбиваете выигрышный результат и получаете выплату.\n"
             "<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>Мимо ворот</b> - <b>-ставка</b> (деньги уходят в баланс чата).\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Неудачный удар</b> - <b>-ставка</b> (деньги сгорают).\n"
             "\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Неудачный удар - как это работает</b>\n"
             "Это <b>скрытый</b> специальный исход.\n"
             f"Шанс такого исхода сейчас: <b>{soccer_bad_shot_percent}%</b> на один удар.\n"
             "Если он срабатывает, ставка сгорает.\n"
             "\n"
             
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "Если выпадает гол, выплата считается по формуле:\n"
             f"• <b>ставка × {multiplier_soccer}</b>\n"
             "\n"
             "К зачислению идёт именно <b>чистая прибыль</b>, а не вся сумма вместе со ставкой.\n"
             "\n"
             
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{soccer_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{soccer_BASE_MAX_BET}</b>\n"

             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между ударами в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") ,
            parse_mode="HTML" , disable_web_page_preview=True , )

    if message.text and " ".join((message.text or "").lower().strip().split()) in [ "боулинг хелп" , "хелп боулинг" ,
        "помощь боулинг" , "боулинг помощь" , "боулинг инструкция" , "инструкция боулинг" , "как играть в боулинг" ,
        "как играть в боулинг игру" , "как играть в игру боулинг" , "что такое боулинг" , "что такое игра боулинг" ,
        "что такое игра в боулинг" ,

        "боул хелп" , "хелп боул" , "помощь боул" , "боул помощь" , "боул инструкция" , "инструкция боул" ,
        "как играть в боул" , "как играть в игру боул" , "что такое боул" , "что такое игра боул" ,
        "что такое игра в боул" ,

        "bowling help" , "help bowling" ]:
        bowling_bad_hit_percent = (Decimal(str(BOWLING_BAD_HIT_CHANCE)) * Decimal("100")).quantize(
            Decimal("0.01") , rounding=ROUND_HALF_UP)

        target_values_text = " / ".join([ str(x) for x in sorted(BOWLING_TARGET_VALUES) ])

        await message.reply(
            (f"<tg-emoji emoji-id='5370853837689070338'>🎳</tg-emoji> <b>Игра «Боулинг»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>боулинг (ставка)</code>\n"
             "• <code>боул (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             "После запуска бот делает бросок шаром <b>🎳</b>.\n"
             "По результату броска определяется исход игры.\n"
             "\n"
             
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит после броска</b>\n"
             f"<tg-emoji emoji-id='5370853837689070338'>🎳</tg-emoji> <b>Страйк</b> - вы выбиваете выигрышный результат и получаете выплату.\n"
             "<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>Промах</b> - <b>-ставка</b> (деньги уходят в баланс чата).\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Неудачный удар</b> - <b>-ставка</b> (деньги сгорают).\n"
             "\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Неудачный удар - как это работает</b>\n"
             "Это <b>скрытый</b> специальный исход.\n"
             f"Шанс такого исхода сейчас: <b>{bowling_bad_hit_percent}%</b> на один бросок.\n"
             "Если он срабатывает, ставка сгорает\n"
             "\n"
             
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "Если выпадает страйк, выплата считается по формуле:\n"
             f"• <b>ставка × {multiplier_bowling}</b>\n"
             "\n"
             "К зачислению идёт именно <b>чистая прибыль</b>, а не вся сумма вместе со ставкой.\n"
             "\n"
             
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{bowling_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{bowling_BASE_MAX_BET}</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между бросками в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") ,
            parse_mode="HTML" , disable_web_page_preview=True , )



    if message.text and " ".join((message.text or "").lower().strip().split()) in [ "баскет хелп" , "хелп баскет" ,
        "помощь баскет" , "баскет помощь" , "баскет инструкция" , "инструкция баскет" , "как играть в баскет" ,
        "как играть в баскет игру" , "как играть в игру баскет" , "что такое баскет" , "что такое игра баскет" ,
        "что такое игра в баскет" , "как играть в баскет (игра)" ,

        "баскетбол хелп" , "хелп баскетбол" , "помощь баскетбол" , "баскетбол помощь" , "баскетбол инструкция" ,
        "инструкция баскетбол" , "как играть в баскетбол" , "как играть в баскетбол игру" ,
        "как играть в игру баскетбол" , "что такое баскетбол" , "что такое игра баскетбол" ,
        "что такое игра в баскетбол" ,

        "баскетболл хелп" , "хелп баскетболл" , "помощь баскетболл" , "баскетболл помощь" , "баскетболл инструкция" ,
        "инструкция баскетболл" , "как играть в баскетболл" , "как играть в игру баскетболл" , "что такое баскетболл" ,
        "что такое игра баскетболл" , "что такое игра в баскетболл" ,

        "баскетбал хелп" , "хелп баскетбал" , "помощь баскетбал" , "баскетбал помощь" , "баскетбал инструкция" ,
        "инструкция баскетбал" , "как играть в баскетбал" , "как играть в игру баскетбал" , "что такое баскетбал" ,
        "что такое игра баскетбал" , "что такое игра в баскетбал" ,

        "basket help" , "help basket" , "basketball help" , "help basketball" ]:
        basket_flat_percent = (Decimal(str(BASKET_FLAT_CHANCE)) * Decimal("100")).quantize(
            Decimal("0.01") , rounding=ROUND_HALF_UP)

        target_values_text = " / ".join([ str(x) for x in sorted(TARGET_VALUES) ])

        await message.reply(
            (f"<tg-emoji emoji-id='5384088040677319401'>🏀</tg-emoji> <b>Игра «Баскетбол»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>баскет (ставка)</code>\n"
             "• <code>баскетбол (ставка)</code>\n"
             "• <code>баскетболл (ставка)</code>\n"
             "• <code>баскетбал (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             "После запуска бот делает бросок мячом <b>🏀</b>.\n"
             "Дальше по результату броска определяется исход игры.\n"
             "\n"
             
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит после броска</b>\n"
             "<tg-emoji emoji-id='5384088040677319401'>🏀</tg-emoji> <b>Попадание</b> - вы забрасываете мяч и получаете выплату по множителю.\n"
             "<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>Промах</b> - <b>-ставка</b> (деньги уходят в баланс чата).\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Мяч сдулся</b> - <b>-ставка</b> (деньги сгорают).\n"
             "\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Мяч сдулся - как это работает</b>\n"
             "Это <b>скрытый</b> специальный исход.\n"
             f"Шанс такого исхода сейчас: <b>{basket_flat_percent}%</b> на один бросок.\n"
             "Если этот исход срабатывает, игра считается не обычным промахом,\n"
             "а отдельным неудачным событием, при котором ставка уходит <b>домой</b>.\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "Если вы попадаете в кольцо, выплата считается по множителю игры.\n"
             "Формула выплаты:\n"
             f"• <b>ставка × {multiplier_basket}</b>\n"
             "\n"
             "К зачислению идёт именно <b>чистая прибыль</b>, а не вся сумма вместе со ставкой.\n"
             "\n"
             
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{basket_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{basket_BASE_MAX_BET}</b>\n"
             f"• Победные значения броска : <b>{target_values_text}</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между бросками в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") ,
            parse_mode="HTML" , disable_web_page_preview=True , )



    if message.text:
        text_low = " ".join((message.text or "").lower().strip().split())

        slots_help_phrases = [ "слоты хелп" , "хелп слоты" , "помощь слоты" , "слоты помощь" , "слоты инструкция" ,
            "инструкция слоты" , "как играть в слоты" , "как играть в слоты игру" , "как играть в игру слоты" ,
            "что такое слоты" , "что такое игра слоты" , "что такое игра в слоты" , "как играть в слоты (игра)" ,

            "слот хелп" , "хелп слот" , "помощь слот" , "слот помощь" , "слот инструкция" , "инструкция слот" ,
            "как играть в слот" , "как играть в игру слот" , "что такое слот" , "что такое игра слот" ,
            "что такое игра в слот" ,

            "спин хелп" , "хелп спин" , "помощь спин" , "спин помощь" , "спин инструкция" , "инструкция спин" ,
            "как играть в спин" , "как играть в игру спин" , "что такое спин" , "что такое игра спин" ,
            "что такое игра в спин" ,

            "барабан хелп" , "хелп барабан" , "помощь барабан" , "барабан помощь" , "барабан инструкция" ,
            "инструкция барабан" , "как играть в барабан" , "как играть в игру барабан" , "что такое барабан" ,
            "что такое игра барабан" , "что такое игра в барабан" ,

            "slots help" , "help slots" , "slot help" , "help slot" , "spin help" , "help spin" ]

        if text_low in slots_help_phrases:
            slots_jam_percent = (Decimal(str(SLOTS_JAM_CHANCE)) * Decimal("100")).quantize(
                Decimal("0.01") , rounding=ROUND_HALF_UP)

            slots_multiplier_lines = [
                f"• <b>семь / семь / семь</b> - <b>{SLOTS_MULTIPLIERS.get(('семь' , 'семь' , 'семь') , Decimal('0'))}x</b>" ,
                f"• <b>лимон / лимон / лимон</b> - <b>{SLOTS_MULTIPLIERS.get(('лимон' , 'лимон' , 'лимон') , Decimal('0'))}x</b>" ,
                f"• <b>виноград / виноград / виноград</b> - <b>{SLOTS_MULTIPLIERS.get(('виноград' , 'виноград' , 'виноград') , Decimal('0'))}x</b>" ,
                f"• <b>BAR / BAR / BAR</b> - <b>{SLOTS_MULTIPLIERS.get(('BAR' , 'BAR' , 'BAR') , Decimal('0'))}x</b>" ,
                f"• <b>семь / семь / любой</b> - до <b>{SLOTS_MULTIPLIERS.get(('семь' , 'семь' , 'BAR') , Decimal('0'))}x</b>" ,
                f"• <b>лимон / лимон / любой</b> - до <b>{SLOTS_MULTIPLIERS.get(('лимон' , 'лимон' , 'семь') , Decimal('0'))}x</b>" ,
                f"• <b>виноград / виноград / любой</b> - до <b>{SLOTS_MULTIPLIERS.get(('виноград' , 'виноград' , 'BAR') , Decimal('0'))}x</b>" ,
                f"• <b>BAR / BAR / любой</b> - до <b>{SLOTS_MULTIPLIERS.get(('BAR' , 'BAR' , 'семь') , Decimal('0'))}x</b>" , ]

            slots_multiplier_text = "\n".join(slots_multiplier_lines)

            help_text = f"""
<tg-emoji emoji-id='5202148759252786291'>🎰</tg-emoji> <b>Игра «Слоты»</b>

<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>
Напишите в чат сообщение:
• <code>слоты (ставка)</code>
• <code>слот (ставка)</code>
• <code>спин (ставка)</code>
• <code>барабан (ставка)</code>

<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>
После запуска бот крутит слот-машину <b>🎰</b>.
На экране выпадает комбинация из <b>3 символов</b>.
По этой комбинации определяется итог спина.

В этой игре есть <b>3 исхода</b>:

<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит после спина</b>
<tg-emoji emoji-id='5202148759252786291'>🎰</tg-emoji> <b>Выигрыш</b> - выпадает выигрышная комбинация, и вы получаете выплату по множителю.
<tg-emoji emoji-id='4956499161319998529'>🔥</tg-emoji> <b>Проигрыш</b> - <b>-ставка</b> (деньги уходят в баланс чата).
<tg-emoji emoji-id='5341715473882955310'>⚙️</tg-emoji> <b>Автомат заклинил</b> - <b>-ставка</b> (деньги сгорают).

<tg-emoji emoji-id='5341715473882955310'>⚙️</tg-emoji> <b>Автомат заклинил - как это работает</b>
Это <b>скрытый специальный исход</b>, который проверяется отдельно от обычной комбинации слотов.
Шанс такого исхода сейчас: <b>{slots_jam_percent}%</b> на один спин.
Если срабатывает этот исход, слот считается проигранным - ставка сгорает.

<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрышные комбинации</b>
Некоторые из основных комбинаций:
{slots_multiplier_text}

Если выпала выигрышная комбинация, выплата считается по её множителю.
Чем сильнее комбинация - тем выше итоговая выплата.

<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Как считается выигрыш</b>
Сначала считается общая сумма по формуле:
• <b>ставка × множитель комбинации</b>

После этого к зачислению идёт именно <b>чистая прибыль</b>:
• <b>итоговая выплата - ставка</b>

То есть выплата зависит от самой комбинации, которая выпала на барабанах.

<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Символы слота</b>
В игре используются следующие символы:
• <b>BAR</b>
• <b>виноград</b>
• <b>лимон</b>
• <b>семь</b>

Разные сочетания этих символов дают разные множители.

<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>
• Играть можно только в <b>публичных группах</b>
• Ставка - только <b>целым числом</b>
• Минимальная ставка : <b>{slots_MIN_BET}</b>
• Максимальная ставка : <b>{slots_BASE_MAX_BET}</b>
• Если группе не хватает баланса на полную выплату, выигрыш может быть ограничен балансом группы

<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>
• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются
• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты
• В игре есть кулдаун между спинами в чате
• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars
    """.strip()

            await message.reply(
                help_text , parse_mode="HTML" , disable_web_page_preview=True , )
            return

    if message.text and message.text.lower() in [ "провода хелп" , "хелп провода" , "помощь провода" ,
        "провода помощь" , "провода инструкция" , "инструкция провода" , "как играть в провода" ,
        "как играть в провода игру" , "как играть в игру провода" , "что такое провода" , "что такое игра провода" ,
        "что такое игра в провода" , "как играть в провода (игра)" , "провод хелп" , "хелп провод" , "помощь провод" ,
        "провод помощь" , "провод инструкция" , "инструкция провод" , "как играть в провод" ,
        "как играть в игру провод" , "что такое провод" , "что такое игра провод" , "что такое игра в провод" ,
        "провода help" , "help провода" , "провод help" , "help провод" ]:
        wins_3 = WIN_BY_COUNT.get(3 , 1)
        wins_4 = WIN_BY_COUNT.get(4 , 1)
        wins_5 = WIN_BY_COUNT.get(5 , 2)

        color_titles = " , ".join([ str(x.get("title" , "")) for x in WIRE_COLORS ])

        await message.reply(
            (f"<tg-emoji emoji-id='5782990399672946716'>🎗</tg-emoji> <b>Игра «Провода»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>провода (ставка)</code>\n"
             "• <code>провод (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             "После запуска появляется ряд проводов.\n"
             f"Их количество всегда рандомное - от <b>{WIRES_MIN}</b> до <b>{WIRES_MAX}</b>.\n"
             "Снаружи все провода выглядят как обычный выбор, но внутри у каждого уже есть свой исход.\n"
             "\n"
             "Ваша задача - выбрать один провод и перерезать его.\n"
             "В зависимости от выбранного провода вы можете:\n"
             
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит при нажатии</b>\n"
             "<tg-emoji emoji-id='5782990399672946716'>⚡️</tg-emoji> <b>Победа</b> - вы угадываете правильный провод и получаете выплату.\n"
             "<tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Проигрыш</b> - <b>-ставка</b> (деньги уходят в баланс чата).\n"
             "<tg-emoji emoji-id='4958479549265347295'>⚡️</tg-emoji> <b>Замыкание</b> - <b>-ставка</b> (деньги <b>сгорают</b> и не попадают в баланс чата игры).\n"
             "\n"
             "<tg-emoji emoji-id='4958479549265347295'>⚡️</tg-emoji> <b>Замыкание - как это работает</b>\n"
             "Это <b>скрытый</b> специальный исход.\n"
             "На каждом запуске среди проводов всегда есть <b>один</b> провод с замыканием.\n"
             "Где именно он находится - заранее увидеть нельзя.\n"
             "\n"
             "<tg-emoji emoji-id='5782990399672946716'>🎗</tg-emoji> <b>Победные провода</b>\n"
             "Количество правильных проводов зависит от общего числа проводов в игре:\n"
             f"• При <b>3</b> проводах - <b>{wins_3}</b> победный\n"
             f"• При <b>4</b> проводах - <b>{wins_4}</b> победный\n"
             f"• При <b>5</b> проводах - <b>{wins_5}</b> победных\n"
             "\n"
             "Все остальные провода, кроме победных и одного провода с замыканием, будут проигрышными.\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "Если вы выбираете правильный провод, выплата считается по множителю игры.\n"
             "Формула выплаты:\n"
             f"• <b>ставка × {PAYOUT_MULTIPLIER}</b>\n"
             "\n"
             "К зачислению идёт именно <b>чистая прибыль</b>, а не вся сумма вместе со ставкой.\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Цвета проводов</b>\n"
             "В игре могут использоваться разные цвета:\n"
             f"• <b>{color_titles}</b>\n"
             "\n"
             "Цвет сам по себе не гарантирует победу или проигрыш.\n"
             "На каждом новом запуске правильные и опасные провода распределяются заново.\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{provoda_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{provoda_MAX_BET}</b>\n"
             f"• Количество проводов за игру : от <b>{WIRES_MIN}</b> до <b>{WIRES_MAX}</b>\n"
             "• Замыкание на поле всегда : <b>1</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между прокрутами в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") , parse_mode="HTML" ,
            disable_web_page_preview=True , )
    if message.text and message.text.lower() in [ "бомбы хелп" , "хелп бомбы" , "помощь бомбы" , "бомбы помощь" ,
        "бомбы инструкция" , "инструкция бомбы" , "как играть в бомбы" , "как играть в бомбы игру" ,
        "как играть в игру бомбы" , "как играть в игру бомбы" , "что такое бомбы" , "что такое игра бомбы" ,
        "что такое игра в бомбы" , "как играть в бомбы (игра)" , "бомба хелп" , "хелп бомба" , "помощь бомба" ,
        "бомба помощь" , "бомба инструкция" , "инструкция бомба" , "как играть в бомба" , "что такое бомба" ,
        "что такое игра в бомба" , "как играть в игру бомба" , "что такое игра бомба" , "бомбы help" , "help бомбы" ,
        "бомба help" , "help бомба" ]:
        await message.reply(
            (f"<tg-emoji emoji-id='5469654973308476699'>💣</tg-emoji> <b>Игра «Бомбы»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>бомбы (ставка)</code>\n"
             "• <code>бомба (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             f"После запуска появится поле из <b>{GRID_SIZE} клеток</b> "
             f"(<b>{ROW_LEN} × {ROW_LEN}</b>).\n"
             "Все клетки сначала выглядят одинаково, и заранее нельзя понять, "
             "что скрывается внутри каждой из них.\n"
             "\n"
             "Ваша задача - открывать клетки, копить потенциальный выигрыш "
             "и вовремя остановиться.\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит при нажатии</b>\n"
             f"• <tg-emoji emoji-id='5294026527850132517'>🚀</tg-emoji> <b>Удача</b> - безопасная клетка , "
             "вы продолжаете игру и увеличиваете потенциальный выигрыш.\n"
             f"• <tg-emoji emoji-id='5429444544590541909'>💥</tg-emoji> <b>Бомба</b> - <b>-ставка</b> "
             "(деньги уходят в баланс чата).\n"
             f"• <tg-emoji emoji-id='5469785308386041323'>💥</tg-emoji> <b>Ядерка</b> - <b>-ставка</b> "
             "(деньги сгорают).\n"
             "\n"
             "<tg-emoji emoji-id='5469913852462242978'>🧨</tg-emoji> <b>Ядерка - и как это работает</b>\n"
             "Это <b>скрытый</b> исход, который находится среди обычных клеток.\n"
             f"На одном поле бывает от <b>{NUKE_MIN}</b> до <b>{NUKE_MAX}</b> таких клеток.\n"
             "Где именно они находятся - всегда <b>рандом</b>. Увидеть заранее невозможно.\n"
             "\n"
             "<tg-emoji emoji-id='5469654973308476699'>💣</tg-emoji> <b>Бомбы на поле</b>\n"
             f"На поле всегда находится <b>{BOMB_COUNT}</b> обычных бомб.\n"
             "Если открыть такую клетку - игра сразу заканчивается проигрышем.\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "За каждую безопасную клетку ваш потенциальный выигрыш увеличивается.\n\n"

            f"• За удачную клетку добавляется:\n"
            f"  <b>×{FIXED_GAIN_PER_CLICK} от ставки</b>\n"
            "\n") + ("Вы можете:\n"
                     "• продолжать открывать клетки и увеличивать выигрыш\n"
                     "• или нажать кнопку <b>«Остановить игру»</b> и забрать накопленное\n"
                     "\n"
                     "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
                     "• Играть можно только в <b>публичных группах</b>\n"
                     "• Ставка - только <b>целым числом</b>\n"
                     f"• Минимальная ставка : <b>{bomb_MIN_BET}</b>\n"
                     f"• Максимальная ставка : <b>{bomb_MAX_BET}</b>\n"
                     f"• На поле всего <b>{GRID_SIZE}</b> клеток\n"
                     f"• Обычных бомб : <b>{BOMB_COUNT}</b>\n"
                     f"• Ядерок : от <b>{NUKE_MIN}</b> до <b>{NUKE_MAX}</b>\n"
                     "\n"
                     "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
                     "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
                     "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
                     "• В игре есть кулдаун между прокрутами в чате\n"
                     "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") ,
            parse_mode="HTML" , disable_web_page_preview=True , )

    if message.text and message.text.lower() in [ "риск хелп", "хелп риск", "помощь риск", "риск помощь",
    "риск инструкция", "инструкция риск",
    "как играть в риск", "как играть в риск игру", "как играть в игру риск",
    "как играть в игру риск", "что такое риск",
    "что такое игра риск", "что такое игра в риск",
    "как играть в риск (игра)",
    "риск хелп", "хелп риск", "помощь риск", "риск помощь",
    "риск инструкция", "инструкция риск",
    "как играть в риск", "что такое риск", "что такое игра в риск" ]:
        await message.reply(
            (f"<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Игра «Риск»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>риск (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             "После запуска появится поле в текущем ряду.\n"
             "В каждом ряду вас ждёт один из исходов:\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит при нажатии</b>\n"
             f"• <tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Удача</b> - вы проходите ряд и копите выигрыш.\n"
             f"• <tg-emoji emoji-id='5318762039076746215'>💥</tg-emoji> <b>Провал</b> - <b>-ставка</b> (деньги уходят в баланс чата).\n"
             f"• <tg-emoji emoji-id='5370842086658546991'>🧱</tg-emoji> <b>Рискнуть не удалось</b> - <b>-ставка</b> (деньги сгорают).\n"
             "\n"
             "<tg-emoji emoji-id='5370842086658546991'>🧱</tg-emoji> <b>Рискнуть не удалось - как это работает</b>\n"
             "Это <b>скрытый</b> исход, который может попасться в любом ряду.\n"
             "Увидеть заранее невозможно.\n"
             "Если он выпал - ставка списывается\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "За каждый успешный ряд к вашему потенциальному выигрышу добавляется:\n"
             f"• <b>ставка ×{_RISK_MULT_DEFAULT}</b>\n"
             "\n"
             "То есть при первом успехе обычно воспринимается как <b>«2х»</b>:\n"
             "• было: <b>ставка</b>\n"
             f"• стало: <b>ставка + (ставка ×{_RISK_MULT_DEFAULT})</b>\n"
             "\n"
             "Вы можете:\n"
             "• продолжать идти дальше и увеличивать выигрыш\n"
             "• или нажать кнопку <b>«Закончить игру»</b> и забрать накопленное\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{RISK_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{RISK_MAX_BET}</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между прокрутами в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") , parse_mode="HTML" , disable_web_page_preview=True)

    if message.text and message.text.lower() in [ "плиты хелп" , "хелп плиты" , "помощь плиты" , "плиты помощь" ,
                                                  "плиты инструкция" , "инструкция плиты" , "как играть в плиты" ,
                                                  "как играть в плиты игру" , "как играть в игру плиты" ,
                                                  "как играть в игру плиты" , "что такое плиты" ,
                                                  "что такое игра плиты" , "что такое игра в плиты" ,
                                                  "как играть в плиты (игра)" , "плита хелп" , "хелп плита" ,
                                                  "помощь плита" , "плита помощь" , "плита инструкция" ,
                                                  "инструкция плита" , "как играть в плита" , "как играть в плиту" ,
                                                  "что такое плита" , "что такое игра в плиту" ]:
        await message.reply(
            (f"<tg-emoji emoji-id='5370842086658546991'>🧱</tg-emoji> <b>Игра «Плиты»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>плиты (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             "После запуска появится поле из <b>2 клеток</b> в текущем ряду.\n"
             "В каждом ряду есть <b>безопасная</b> клетка и <b>взрывная</b>.\n"
             "Ваша задача - проходить ряды <b>вперёд</b> и не ошибиться.\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит при нажатии</b>\n"
             f"• <tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Удача</b> - вы проходите ряд и копите выигрыш.\n"
             f"• <tg-emoji emoji-id='5318762039076746215'>💥</tg-emoji> <b>Провал</b> - <b>-ставка</b> (деньги уходят в баланс чата).\n"
             f"• <tg-emoji emoji-id='5370842086658546991'>🧱</tg-emoji> <b>Тропа разрушилась</b> - <b>-ставка</b> (деньги сгорают).\n"
             "\n"
             "<tg-emoji emoji-id='5370842086658546991'>🧱</tg-emoji> <b>Тропа разрушилась - как это работает</b>\n"
             f"Это <b>скрытый</b> исход, который может попасться в некоторых рядах.\n"
             f"На <b>10 рядов</b> бывает от <b>{PLATE_COLLAPSE_MIN}</b> до <b>{PLATE_COLLAPSE_MAX}</b> таких рядов.\n"
             "Где именно - всегда <b>рандом</b>. Увидеть заранее невозможно.\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "За каждый пройденный ряд к вашему потенциальному выигрышу добавляется:\n"
             f"• <b>ставка ×{_PLATE_MULT_DEFAULT}</b>\n"
             "\n"
             "Вы можете:\n"
             "• продолжать идти дальше и увеличивать выигрыш\n"
             "• или нажать кнопку <b>«Закончить игру»</b> и забрать накопленное\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{PLATE_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{PLATE_MAX_BET}</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между прокрутами в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") , parse_mode="HTML" ,
            disable_web_page_preview=True , )
    if message.text and message.text.lower() in [ "башня хелп" , "хелп башня" , "помощь башня" , "башня помощь" ,
        "башня инструкция" , "инструкция башня" , "как играть в башня" , "как играть в башни" , "как играть в башню" ,
        "как играть в игру башня" , "как играть в игру башни" , "как играть в игру башню" , "что такое башня" ,
        "что такое башни" , "что такое игра в башню" , "что такое игра в башни" ]:
        await message.reply(
            (f"<tg-emoji emoji-id='5291960442422325139'>🏰</tg-emoji> <b>Игра «Башня»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>башня (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Суть игры</b>\n"
             "После запуска появится поле из <b>5 клеток</b> в текущем ряду.\n"
             "В каждом ряду есть <b>безопасные</b> клетки и <b>взрывные</b>.\n"
             "Ваша задача - проходить ряды <b>вниз</b>, не подорвавшись.\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Что происходит при нажатии</b>\n"
             f"• <tg-emoji emoji-id='5204467307153234577'>🍀</tg-emoji> <b>Удача</b> - вы проходите ряд и копите выигрыш.\n"
             f"• <tg-emoji emoji-id='5195369389599265575'>♨️</tg-emoji> <b>Взрыв</b> - <b>-ставка</b> (деньги уходят в баланс чата).\n"
             f"• <tg-emoji emoji-id='5411089297476441876'>🐻</tg-emoji> <b>Башня разрушилась</b> - <b>-ставка</b> (деньги сгорают).\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             "За каждый пройденный ряд к вашему потенциальному выигрышу добавляется :\n"
             f"• <b>ставка ×{TANK_MULTIPLIER_CFG}</b>\n"
             "\n"
             "Вы можете:\n"
             "• продолжать идти дальше и увеличивать выигрыш\n"
             "• или нажать кнопку <b>«Закончить игру»</b> и забрать накопленное\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{Tank_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{Tank_MAX_BET}</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между прокрутами в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") , parse_mode="HTML" , disable_web_page_preview=True , )



    if message.text and message.text.lower() in [ "шар хелп" , "хелп шар" , "шарик хелп" , "хелп шарик" ,
        "помощь шарик" , "шарик помощь" , "помощь шар" , "шар помощь" , "шар инструкция" , "инструкция шар" ,
        "шарик инструкция" , "инструкция шарик" , "как играть в шар" , "как играть в шарик" , "как играть в игру шар" ,
        "как играть в игру шарик" , "что такое шар" , "что такое шарик" ]:
        await message.reply(
            ("<tg-emoji emoji-id='5363877049863786071'>🎱</tg-emoji> <b>Игра «Шарик»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение:\n"
             "• <code>шар (ставка)</code>\n"
             "• <code>шарик (ставка)</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Какой смысл</b>\n"
             "После запуска появятся <b>3 кнопки</b>.\n"
             "Нажмите одну из них - исход выпадет сразу.\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Исходы прозрачны</b>\n"
             f"• <tg-emoji emoji-id='5294026527850132517'>💸</tg-emoji> <b>Победа</b>\n"
             f"• <tg-emoji emoji-id='5422538735394766352'>🔥</tg-emoji> <b>Проигрыш</b>\n"
             f"• <tg-emoji emoji-id='4958799300990600199'>🍄</tg-emoji> <b>Шар исчез</b> (ставка сгорает)\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             f"Если вы нажали победную кнопку - выплата <b>x2.0</b> от ставки\n"
             "(то есть чистая прибыль = <b>+ставка</b>).\n"
             "Если нажали проигрышную - <b>-ставка</b>.\n"
             "Если шар исчез - <b>-ставка</b> (деньги не идут в баланс чата).\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{Balls_MIN_BET}</b>\n"
             f"• Максимальная ставка : <b>{Balls_MAX_BET}</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между прокрутами в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") , parse_mode="HTML" , disable_web_page_preview=True , )

    if message.text and message.text.lower() in [ "Трейд хелп","хелп трейд","помощь трейд","трейд помощь","трейд инструкция","инструкция трейд","как играть в трейд","как играть в игру трейд","что такое трейд"]:
        await message.reply(
            ("<tg-emoji emoji-id='5296306038792808890'>📈</tg-emoji> <b>Игра «Трейд»</b>\n"
             "\n"
             "<tg-emoji emoji-id='5787344001862471785'>✍️</tg-emoji> <b>Как играть</b>\n"
             "Напишите в чат сообщение :\n"
             "• <code>трейд вверх (ставка)</code>\n"
             "• <code>трейд вниз (ставка)</code>\n"
             "Можно и наоборот:\n"
             "• <code>трейд (ставка) вверх</code>\n"
             "• <code>трейд (ставка) вниз</code>\n"
             "\n"
             "<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b>Исходы и шансы</b>\n"
             f"• <tg-emoji emoji-id='5429651785352501917'>↗️</tg-emoji> <b>Вверх</b> - {Trade_P_OUTCOME_UP}%\n"
             f"• <tg-emoji emoji-id='5429518319243775957'>📉</tg-emoji> <b>Вниз</b> - {Trade_P_OUTCOME_DOWN}%\n"
             f"• <tg-emoji emoji-id='5411089297476441876'>🐻</tg-emoji> <b>Сделка сорвалась</b> - {Trade_P_OUTCOME_BROKEN}% (ставка сгорает)\n"
             "\n"
             "<tg-emoji emoji-id='5433758796289685818'>💰</tg-emoji> <b>Выигрыш</b>\n"
             f"Если вы угадали направление, выплата <b>x{Trade_FIXED_WIN_TOTAL_MULTIPLIER}</b> от ставки\n"
             "(то есть чистая прибыль = <b>+ставка</b>).\n"
             "Если не угадали - <b>-ставка</b>.\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Важно</b>\n"
             "• Играть можно только в <b>публичных группах</b>\n"
             "• Ставка - только <b>целым числом</b>\n"
             f"• Минимальная ставка : <b>{min_amount_trade}</b>\n"
             f"• Максмимальная ставка : <b>{max_amount_trade}</b>\n"
             "\n"
             "<tg-emoji emoji-id='6028338546736107668'>⭐️</tg-emoji> <b>Дополнительно</b>\n"
             "• Если у вас активен <b>FREE-челлендж</b>, реальные куты не списываются и не выплачиваются\n"
             "• Если у вас обычное задание, игра учитывает и челлендж, и реальные куты\n"
             "• В игре есть кулдаун между прокрутами в чате\n"
             "• Если у пользователя не хватает кут для ставки, бот предложит покупку через Telegram Stars") , parse_mode="HTML" , disable_web_page_preview=True , )

    def _dbal_safe_int(value , default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _dbal_safe_str(value , default: str = "-") -> str:
        try:
            if value is None:
                return default
            s = str(value).strip()
            return s if s else default
        except Exception:
            return default

    def _dbal_normalize_obj(value) -> dict:
        """
        Приводит значение к dict.
        Поддерживает:
        - dict
        - JSON-строку
        - mapping/Record-подобные объекты
        - всё остальное -> {}
        """
        if value is None:
            return {}

        if isinstance(value , dict):
            return value

        if isinstance(value , str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
                if isinstance(parsed , dict):
                    return parsed
                return {}
            except Exception:
                return {}

        try:
            if hasattr(value , "items"):
                return dict(value)
        except Exception:
            pass

        return {}

    def _dbal_pretty_name(user_data: dict) -> str:
        user_data = _dbal_normalize_obj(user_data)

        first_name = _dbal_safe_str(user_data.get("first_name") , default="")
        username = _dbal_safe_str(user_data.get("username") , default="")
        user_id = _dbal_safe_str(user_data.get("user_id"))

        if username not in ("" , "-"):
            if not str(username).startswith("@"):
                username = f"@{username}"
            return f"{username} · <code>{user_id}</code>"

        if first_name not in ("" , "-"):
            return f"{first_name} · <code>{user_id}</code>"

        return f"<code>{user_id}</code>"

    def _dbal_fmt_dt_for_display(value) -> str:
        """
        Нормализует дату под красивый формат:
        dd.mm.yyyy hh.mm.ss
        """
        if value is None:
            return "-"

        if isinstance(value , datetime):
            return value.strftime("%d.%m.%Y %H.%M.%S")

        s = str(value).strip()
        if not s:
            return "-"

        # если уже форматируется где-то снаружи - просто возвращаем
        # но пытаемся привести ISO / postgres-like форматы
        for fmt in (
                "%Y-%m-%d %H:%M:%S" , "%Y-%m-%d %H:%M:%S.%f" , "%d.%m.%Y %H:%M:%S" , "%d.%m.%Y %H.%M.%S" , "%Y-%m-%d" ,
                "%H:%M:%S" ,):
            try:
                dt = datetime.strptime(s , fmt)
                if fmt == "%H:%M:%S":
                    return dt.strftime("%H.%M.%S")
                if fmt == "%Y-%m-%d":
                    return dt.strftime("%d.%m.%Y")
                return dt.strftime("%d.%m.%Y %H.%M.%S")
            except Exception:
                pass

        return s

    def _dbal_sep(char: str = "─" , width: int = 22) -> str:
        return char * width

    def _dbal_fmt_user_total_block(title: str , user_data) -> str:
        user_data = _dbal_normalize_obj(user_data)
        if not user_data:
            return f"<b>{title}</b>\n-"

        return (f"<b>{title}</b>\n"
                f"👤 Пользователь: {_dbal_pretty_name(user_data)}\n"
                f"• Операций: <b>{_dbal_safe_int(user_data.get('cnt'))}</b>\n"
                f"• Удалено суммарно: <b>{_fmt_num(user_data.get('sum_balance'))}</b>\n"
                f"• Минимум за операцию: <b>{_fmt_num(user_data.get('min_balance'))}</b>\n"
                f"• Максимум за операцию: <b>{_fmt_num(user_data.get('max_balance'))}</b>\n"
                f"• Период: <code>{_dbal_fmt_dt_for_display(user_data.get('first_dt'))}</code> → "
                f"<code>{_dbal_fmt_dt_for_display(user_data.get('last_dt'))}</code>")

    def _dbal_fmt_single_op_block(title: str , op_data) -> str:
        op_data = _dbal_normalize_obj(op_data)
        if not op_data:
            return f"<b>{title}</b>\n-"

        return (f"<b>{title}</b>\n"
                f"👤 Пользователь: {_dbal_pretty_name(op_data)}\n"
                f"• Удалено за операцию: <b>{_fmt_num(op_data.get('balance'))}</b>\n"
                f"• Время: <code>{_dbal_fmt_dt_for_display(op_data.get('data'))}</code>")

    def _dbal_build_top_users_block(top_users: list) -> str:
        if not top_users:
            return "-"

        lines = [ ]
        medals = {1: "🥇" , 2: "🥈" , 3: "🥉" , }

        for i , user_data in enumerate(top_users , start=1):
            user_data = _dbal_normalize_obj(user_data)
            medal = medals.get(i , f"{i}.")

            lines.append(
                f"{medal} {_dbal_pretty_name(user_data)}\n"
                f"   • Сумма: <b>{_fmt_num(user_data.get('sum_balance'))}</b>\n"
                f"   • Операций: <b>{_dbal_safe_int(user_data.get('cnt'))}</b>\n"
                f"   • Макс. за раз: <b>{_fmt_num(user_data.get('max_balance'))}</b>\n"
                f"   • Период: <code>{_dbal_fmt_dt_for_display(user_data.get('first_dt'))}</code> → "
                f"<code>{_dbal_fmt_dt_for_display(user_data.get('last_dt'))}</code>")

        return f"\n\n".join(lines)

    def _dbal_build_daily_block(daily_rows: list) -> str:
        if not daily_rows:
            return "Нет данных для статистики по дням."

        lines = [ ]

        for row in daily_rows:
            row = _dbal_normalize_obj(row)
            day_text = _dbal_fmt_dt_for_display(row.get("day"))

            lines.append(
                f"📅 <b>{day_text}</b>\n"
                f"• Операций: <b>{_dbal_safe_int(row.get('cnt'))}</b>\n"
                f"• Сумма: <b>{_fmt_num(row.get('sum_balance'))}</b>\n"
                f"• Среднее: <b>{_fmt_num(row.get('avg_balance'))}</b>\n"
                f"• Минимум: <b>{_fmt_num(row.get('min_balance'))}</b>\n"
                f"• Максимум: <b>{_fmt_num(row.get('max_balance'))}</b>")

        return "\n\n".join(lines)

    def _dbal_build_hourly_block(hourly_rows: list , note: str = "") -> str:
        if not hourly_rows:
            if note:
                return f"ℹ️ <i>{note}</i>\n\nНет данных для статистики по часам."
            return "Нет данных для статистики по часам."

        lines = [ ]

        if note:
            lines.append(f"ℹ️ <i>{note}</i>")

        for row in hourly_rows:
            row = _dbal_normalize_obj(row)

            hour = _dbal_safe_int(row.get("hour"))
            hour_text = f"{hour:02d}:00"

            lines.append(
                f"🕒 <b>{hour_text}</b>\n"
                f"• Операций: <b>{_dbal_safe_int(row.get('cnt'))}</b>\n"
                f"• Сумма: <b>{_fmt_num(row.get('sum_balance'))}</b>\n"
                f"• Среднее: <b>{_fmt_num(row.get('avg_balance'))}</b>\n"
                f"• Минимум: <b>{_fmt_num(row.get('min_balance'))}</b>\n"
                f"• Максимум: <b>{_fmt_num(row.get('max_balance'))}</b>")

        return "\n\n".join(lines)

    def build_deletebalance_report_text(report: dict) -> str:
        report = report or {}

        meta = _dbal_normalize_obj(report.get("meta"))
        totals = _dbal_normalize_obj(report.get("totals"))
        extremes = _dbal_normalize_obj(report.get("extremes"))

        top_users = report.get("top_users") or [ ]
        daily = report.get("daily") or [ ]
        hourly = report.get("hourly") or [ ]

        ops_count = _dbal_safe_int(totals.get("ops_count"))
        users_count = _dbal_safe_int(totals.get("users_count"))

        sum_balance = _fmt_num(totals.get("sum_balance"))
        avg_balance = _fmt_num(totals.get("avg_balance"))
        min_balance = _fmt_num(totals.get("min_balance"))
        max_balance = _fmt_num(totals.get("max_balance"))

        first_dt = _dbal_fmt_dt_for_display(totals.get("first_dt"))
        last_dt = _dbal_fmt_dt_for_display(totals.get("last_dt"))

        max_total_user = _dbal_normalize_obj(extremes.get("max_total_user"))
        min_total_user = _dbal_normalize_obj(extremes.get("min_total_user"))
        max_single_op = _dbal_normalize_obj(extremes.get("max_single_op"))
        min_single_op = _dbal_normalize_obj(extremes.get("min_single_op"))

        extremes_block = (f"{_dbal_fmt_user_total_block('🔺 Больше всего удалено суммарно' , max_total_user)}\n\n"
                          f"{_dbal_fmt_user_total_block('🔻 Меньше всего удалено суммарно' , min_total_user)}\n\n"
                          f"{_dbal_fmt_single_op_block('💥 Самое большое удаление за одну операцию' , max_single_op)}\n\n"
                          f"{_dbal_fmt_single_op_block('🫧 Самое маленькое удаление за одну операцию' , min_single_op)}")

        top_block = _dbal_build_top_users_block(top_users)

        series_type = _dbal_safe_str(meta.get("series_type") , default="none").lower()
        note = _dbal_safe_str(meta.get("note") , default="")

        if daily:
            series_title = "🗓 <b>Динамика по дням</b>"
            series_block = _dbal_build_daily_block(daily)
        elif hourly:
            series_title = "🕒 <b>Динамика по часам суток</b>"
            series_block = _dbal_build_hourly_block(hourly , note=note)
        else:
            if series_type == "hourly":
                series_title = "🕒 <b>Динамика по часам суток</b>"
                series_block = _dbal_build_hourly_block([ ] , note=note)
            else:
                series_title = "🗓 <b>Динамика</b>"
                series_block = "Нет данных для динамики."

        sep = _dbal_sep()

        text = (f"📊 <b>DeleteBalance - отчёт по удалению баланса</b>\n"
                f"<code>{sep}</code>\n\n"

                f"🧾 <b>Общие итоги</b>\n"
                f"• Всего операций: <b>{ops_count}</b>\n"
                f"• Уникальных пользователей: <b>{users_count}</b>\n"
                f"• Удалено суммарно: <b>{sum_balance}</b>\n"
                f"• Среднее за операцию: <b>{avg_balance}</b>\n"
                f"• Минимум за операцию: <b>{min_balance}</b>\n"
                f"• Максимум за операцию: <b>{max_balance}</b>\n"
                f"• Период: <code>{first_dt}</code> → <code>{last_dt}</code>\n\n"

                f"<code>{sep}</code>\n\n"

                f"🏆 <b>Экстремумы</b>\n"
                f"{extremes_block}\n\n"

                f"<code>{sep}</code>\n\n"

                f"👥 <b>Топ пользователей по удалению</b>\n"
                f"{top_block}\n\n"

                f"<code>{sep}</code>\n\n"

                f"{series_title}\n"
                f"{series_block}")

        return text

    def split_text_into_chunks(text: str , limit: int = 4000) -> list [ str ]:
        """
        Безопасно делит длинный текст на части для Telegram.
        Старается резать по строкам.
        """
        if not text:
            return [ "-" ]

        if len(text) <= limit:
            return [ text ]

        chunks = [ ]
        current_lines = [ ]
        current_len = 0

        for line in text.split("\n"):
            add_len = len(line) + 1

            if current_lines and (current_len + add_len > limit):
                chunks.append("\n".join(current_lines))
                current_lines = [ line ]
                current_len = add_len
            else:
                current_lines.append(line)
                current_len += add_len

        if current_lines:
            chunks.append("\n".join(current_lines))

        return chunks

    # =========================================================
    # HANDLER
    # =========================================================

    if message.text and " ".join((message.text or "").lower().strip().split()) in [ "sypherdelbalance" ]:
        user_id = message.from_user.id

        if int(user_id) != 6801702632:
            return

        report = await db.get_deletebalance_report(top_limit=10 , days_limit=14)

        if report is None:
            await message.answer(
                "❌ <b>Не удалось получить статистику deletebalance.</b>\n"
                "Причина: ошибка чтения базы данных." , parse_mode="HTML")
            return

        try:
            text = build_deletebalance_report_text(report)
        except Exception as e:
            print(f"[DELETEBALANCE][FORMAT][ERROR] {e!r}")
            await message.answer(
                "❌ <b>Не удалось сформировать отчёт deletebalance.</b>" , parse_mode="HTML")
            return

        try:
            parts = split_text_into_chunks(text , limit=4000)
            for part in parts:
                await message.answer(part , parse_mode="HTML")
        except Exception as e:
            print(f"[DELETEBALANCE][SEND][ERROR] {e!r}")
            await message.answer(
                "❌ <b>Не удалось отправить отчёт deletebalance.</b>" , parse_mode="HTML")
    if message.text.lower() in [ "идгрупп" ]:
        chat_id = message.chat.id
        await message.reply(f"🆔 <code>{chat_id}</code>", parse_mode="HTML")

    # ============================================================
    # ЛОГИКА: распознавание команд + переключение chathi
    # (без ensure_chat_row / ensure_chathi_value - только get_chathi/set_chathi)
    # ============================================================

    CHATHI_OFF = 0
    CHATHI_ON = 1

    # -----------------------------
    # ВЫКЛЮЧИТЬ приветствие
    # -----------------------------
    if message.text and message.text.lower() in [ "-приветствие" , "-привет" , "-welcome" , "-hello" , "-hi" ,
        "выкл приветствие" , "приветствие выкл" , "приветствие off" , "off приветствие" , "выключить приветствие" ,
        "приветствие выключить" , ]:
        chat_id = int(message.chat.id)
        user_id = int(message.from_user.id)

        # ✅ только создатель группы
        try:
            creator_id = int(await db.get_group_creator(chat_id))
        except Exception as e:
            print(f"🔴 [CHATHI] chat_id={chat_id} ошибка get_group_creator: {e!r}")
            await message.reply("❗ <b>Не удалось определить создателя группы</b>" , parse_mode="HTML")
        else:
            if user_id == creator_id:
                # читаем текущее состояние
                try:
                    current = await db.get_chathi(chat_id)  # SELECT chathi FROM chat WHERE chat_id=...
                except Exception as e:
                    print(f"🔴 [CHATHI] chat_id={chat_id} ошибка get_chathi: {e!r}")
                    await message.reply("❗ <b>Ошибка базы при чтении настройки</b>" , parse_mode="HTML")
                else:
                    if current is None:
                        await message.reply(
                            "❗ <b>Чат не найден в базе (нет строки в таблице chat). "
                            "Сначала нужно добавить chat_id в таблицу.</b>" , parse_mode="HTML")
                    else:
                        try:
                            current_int = int(current)
                        except Exception:
                            await message.reply(
                                "❗ <b>Состояние приветствия повреждено (не число)</b>" , parse_mode="HTML")
                        else:
                            if current_int == CHATHI_OFF:
                                await message.reply(
                                    "⛵️ <b>Приветствие уже отключено. Нечего менять..</b>" , parse_mode="HTML")
                            elif current_int == CHATHI_ON:
                                # меняем на 0
                                try:
                                    ok = await db.set_chathi(
                                        chat_id , CHATHI_OFF)  # UPDATE chat SET chathi=0 WHERE chat_id=...
                                except Exception as e:
                                    print(f"🔴 [CHATHI] chat_id={chat_id} ошибка set_chathi: {e!r}")
                                    await message.reply(
                                        "❗ <b>Ошибка базы при обновлении настройки</b>" , parse_mode="HTML")
                                else:
                                    if ok:
                                        await message.reply(
                                            "⛵️ <b>Приветствие успешно отключено!</b>" , parse_mode="HTML")
                                    else:
                                        await message.reply(
                                            "❗ <b>Не удалось обновить настройку (строка чата не обновлена). "
                                            "Проверь, что chat_id существует в таблице chat.</b>" , parse_mode="HTML")
                            else:
                                await message.reply(
                                    "❗ <b>Не удалось определить состояние приветствия</b>" , parse_mode="HTML")
            else:
                await message.reply(
                    "<b>🏜 Эту функцию может использовать только создатель группы</b>" , parse_mode="HTML")

    # -----------------------------
    # ВКЛЮЧИТЬ приветствие
    # -----------------------------
    if message.text and message.text.lower() in [ "+приветствие" , "+привет" , "+welcome" , "+hello" , "+hi" ,
        "вкл приветствие" , "приветствие вкл" , "приветствие on" , "on приветствие" , "включить приветствие" ,
        "приветствие включить" , ]:
        chat_id = int(message.chat.id)
        user_id = int(message.from_user.id)

        # ✅ только создатель группы
        try:
            creator_id = int(await db.get_group_creator(chat_id))
        except Exception as e:
            print(f"🔴 [CHATHI] chat_id={chat_id} ошибка get_group_creator: {e!r}")
            await message.reply("❗ <b>Не удалось определить создателя группы</b>" , parse_mode="HTML")
        else:
            if user_id == creator_id:
                # читаем текущее состояние
                try:
                    current = await db.get_chathi(chat_id)
                except Exception as e:
                    print(f"🔴 [CHATHI] chat_id={chat_id} ошибка get_chathi: {e!r}")
                    await message.reply("❗ <b>Ошибка базы при чтении настройки</b>" , parse_mode="HTML")
                else:
                    if current is None:
                        await message.reply(
                            "❗ <b>Чат не найден в базе (нет строки в таблице chat). "
                            "Сначала нужно добавить chat_id в таблицу.</b>" , parse_mode="HTML")
                    else:
                        try:
                            current_int = int(current)
                        except Exception:
                            await message.reply(
                                "❗ <b>Состояние приветствия повреждено (не число)</b>" , parse_mode="HTML")
                        else:
                            if current_int == CHATHI_ON:
                                await message.reply(
                                    "✅ <b>Приветствие уже включено. Всё работает!</b>" , parse_mode="HTML")
                            elif current_int == CHATHI_OFF:
                                # меняем на 1
                                try:
                                    ok = await db.set_chathi(chat_id , CHATHI_ON)
                                except Exception as e:
                                    print(f"🔴 [CHATHI] chat_id={chat_id} ошибка set_chathi: {e!r}")
                                    await message.reply(
                                        "❗ <b>Ошибка базы при обновлении настройки</b>" , parse_mode="HTML")
                                else:
                                    if ok:
                                        await message.reply("✅ <b>Приветствие теперь включено!</b>" , parse_mode="HTML")
                                    else:
                                        await message.reply(
                                            "❗ <b>Не удалось обновить настройку (строка чата не обновлена). "
                                            "Проверь, что chat_id существует в таблице chat.</b>" , parse_mode="HTML")
                            else:
                                await message.reply(
                                    "❗ <b>Не удалось определить состояние приветствия</b>" , parse_mode="HTML")
            else:
                await message.reply(
                    "<b>🏜 Эту функцию может использовать только создатель группы</b>" , parse_mode="HTML")









    if message.text.lower() in [ "-статистика" , "-стата" ]:
        chat_id = message.chat.id
        user_id = message.from_user.id
        current = await db.get_current_stata(chat_id)
        creator_id = await db.get_group_creator(chat_id)
        if user_id == creator_id:
            if current == 0:
                await message.reply("⛵️ <b>Статистика уже отключена. Нечего менять..</b>" , parse_mode="HTML")
            elif current == 1:
                await db.check_and_update_stata(chat_id)
                await message.reply("⛵️ <b>Статистика успешно отключена!</b>" , parse_mode="HTML")
            else:
                await message.reply("❗ <b>Не удалось определить состояние статистики</b>" , parse_mode="HTML")
        else:
            await message.reply("<b>🏜 Эту функцию может использовать только создатель группы</b>",parse_mode="HTML")
    if message.text.lower() in [ "+статистика" , "+стата" ]:
        chat_id = message.chat.id
        user_id = message.from_user.id
        current = await db.get_current_stata(chat_id)
        creator_id = await db.get_group_creator(chat_id)
        if user_id == creator_id:
            if current == 1:
                await message.reply("✅ <b>Статистика уже включена. Всё работает! 📊</b>" , parse_mode="HTML")
            elif current == 0:
                await db.check_and_set_stata_to_one(chat_id)
                await message.reply("✅ <b>Статистика теперь включена!</b>" , parse_mode="HTML")
            else:
                await message.reply("❗ <b>Не удалось определить состояние статистики</b>" , parse_mode="HTML")
        else:
            await message.reply("<b>🏜 Эту функцию может использовать только создатель группы</b>",parse_mode="HTML")

    text = message.text.lower()
    user_id = message.from_user.id
    # === Удаление задержки ===
    if text == "-задержка":
        chat_id = message.chat.id
        creator_id = await db.get_group_creator(chat_id)
        if user_id != creator_id:
            await message.reply("<b>🏜 Эту функцию может использовать только создатель группы</b>" , parse_mode="HTML")
            return

        if chat_id in delaysssssssssgamesonee:
            del delaysssssssssgamesonee [ chat_id ]
            await message.reply("⏱ <b>Задержка успешно отключена!</b>" , parse_mode="HTML")
        else:
            await message.reply("⏱ <b>Задержка уже отключена. Нечего удалять.</b>" , parse_mode="HTML")

    # === Добавление задержки ===
    if text.startswith("+задержка"):
        chat_id = message.chat.id
        creator_id = await db.get_group_creator(chat_id)
        if user_id != creator_id:
            await message.reply("<b>🏜 Эту функцию может использовать только создатель группы</b>" , parse_mode="HTML")
            return

        match = re.match(r"\+задержка\s+(\d+)" , text)
        if match:
            seconds = int(match.group(1))
            delaysssssssssgamesonee [ chat_id ] = seconds
            await message.reply(f"⏱ <b>Задержка в {seconds} секунд(ы) успешно установлена!</b>" , parse_mode="HTML")
        else:
            pass

    if text in [ "+-задержка" , "-+задержка" ]:
        if not delaysssssssssgamesonee:
            await message.reply("ℹ️ <b>Задержки в чатах не установлены.</b>" , parse_mode="HTML")
            return

        response_lines = [ "📋 <b>Текущие задержки по чатам:</b>" ]
        for chat_id , delay in delaysssssssssgamesonee.items():
            response_lines.append(f"• Чат ID <code>{chat_id}</code>: {delay} сек")

        response_text = "\n".join(response_lines)
        await message.reply(response_text , parse_mode="HTML")

    if message.text and message.text.lower() in [ "задания" , "задание" , "хелп задания" , "задания хелп" ,
        "задание хелп" , "хелп задание" ]:
        if message.chat.type == 'private':
            # 💬 Если пользователь пишет в ЛС
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [ InlineKeyboardButton(text="Посмотреть задания" , callback_data="questions_stars") ] ])
            await message.answer("🍹" , parse_mode="HTML" , reply_markup=kb)
        else:
            # 👥 Если пишет в группе - кнопка "Открыть в лс"
            me = await bot1.get_me()
            deep_link = f"https://t.me/{me.username}?start=tasks"  # deep link
            kb = InlineKeyboardMarkup(
                inline_keyboard=[ [ InlineKeyboardButton(text="Открыть в лс" , url=deep_link) ] ])
            await message.answer("🍹 <b>Напишите это в личных сообщениях с ботом 👇</b>" , parse_mode="HTML", reply_markup=kb)

    if message.text.lower() in [ "рассылка стоп" , "стоп рассылка" ]:
        user_id = message.from_user.id
        if user_id in allowed_users:
            broadcast_state [ "should_broadcast" ] = False
            await message.reply("<b>🚫 Рассылка отключена.</b>",parse_mode="HTML")
            print("✋ Рассылка отключена этим пользователем:" , user_id)

        # ✅ Старт рассылка
    if message.text.lower() in [ "рассылка старт" , "старт рассылка" ]:
        user_id = message.from_user.id
        if user_id in allowed_users:
            broadcast_state [ "should_broadcast" ] = True
            await message.reply("<b>✅ Рассылка включена. Будет выполнена при следующем запуске.</b>", parse_mode="HTML")
            print("✅ Рассылка включена этим пользователем:" , user_id)
            broadcast_state.save()

    text = message.text.strip()
    text_lower = text.lower()
    if text_lower in [ "-фото рассылка" , "-рассылка фото" ]:
        user_id = message.from_user.id
        if user_id not in allowed_users:
            print(f"Пользователь {user_id} не разрешён для удаления фото.")
            return

        if "photo" not in fotorassilka:
            await message.reply("⚠ <b>Фото для рассылки не установлено.</b>" , parse_mode="HTML")
            print("Фото не найдено при попытке удаления.")
            return

        del fotorassilka [ "photo" ]
        await message.reply("✅ <b>Фото для рассылки удалено.</b>" , parse_mode="HTML")
        print("Фото для рассылки удалено.")
        return
    # Проверка прав в начале каждого блока
    # Добавление группы
    #if "groups" not in groupsrassilka or not isinstance(groupsrassilka [ "groups" ] , list):
       # groupsrassilka [ "groups" ] = [ ]

        # Добавление группы
    if text_lower.startswith("+текст рассылка") or text_lower.startswith("+рассылка текст") or text_lower.startswith(
        "+рассылка текста")or text_lower.startswith(
        "+текст рассылки"):

        user_id = message.from_user.id

        if user_id not in allowed_users:
            print(f"⛔ Пользователь {user_id} не разрешён для изменения текста рассылки.")
            return

        parts = text.split(maxsplit=2)
        if len(parts) < 3 or not parts [ 2 ].strip():
            await message.reply("❌ <b>Укажите текст для рассылки после команды.</b>" , parse_mode="HTML")
            return

        textrassilka [ "text" ] = parts [ 2 ].strip()
        await message.reply("✅ <b>Текст успешно добавлен для рассылки.</b>" , parse_mode="HTML")
        print(f"✅ Текст рассылки обновлён: {textrassilka [ 'text' ]}")
        textrassilka.save()
        return

    if text_lower in [ "-текст рассылка" , "-рассылка текст","-текст рассылки" ]:
        user_id = message.from_user.id

        if user_id not in allowed_users:
            print(f"⛔ Пользователь {user_id} не разрешён для удаления текста рассылки.")
            return

        textrassilka.clear()
        await message.reply(
            "✅ <b>Текст рассылки удалён. Теперь будет отправляться только картинка.</b>" , parse_mode="HTML")
        print("🗑 Текст рассылки был очищен.")
        textrassilka.save()
        print( textrassilka )
        return
    if text_lower.startswith("+рассылка "):
        user_id = message.from_user.id
        if user_id not in allowed_users:
            print(f"Пользователь {user_id} не разрешён для добавления групп.")
            return

        group = text [ 9: ].strip()
        if not group:
            await message.reply("❌ <b>Укажите ссылку или юзернейм группы после '+рассылка'</b>" , parse_mode="HTML")
            print("Ошибка: пустая группа при добавлении.")
            return

        if group in groupsrassilka:
            await message.reply(f"⚠ <b>Группа {group} уже есть в списке рассылки.</b>" , parse_mode="HTML")
            print(f"Группа {group} уже в списке рассылки.")
            return

        groupsrassilka [ group ] = True
        await message.reply(f"✅ <b>Группа {group} добавлена в список рассылки.</b>" , parse_mode="HTML")
        print(f"Группа {group} успешно добавлена. Текущий список: {list(groupsrassilka.keys())}")
        groupsrassilka.save()
        return

    if text_lower.startswith("-рассылка "):
        user_id = message.from_user.id
        if user_id not in allowed_users:
            print(f"Пользователь {user_id} не разрешён для удаления групп.")
            return

        group = text [ 9: ].strip()

        if group not in groupsrassilka:
            await message.reply(f"⚠ <b>Группа {group} не найдена в списке рассылки.</b>" , parse_mode="HTML")
            print(f"Группа {group} не найдена при попытке удаления.")
            return

        del groupsrassilka [ group ]
        await message.reply(f"✅ <b>Группа {group} удалена из списка рассылки.</b>" , parse_mode="HTML")
        print(f"Группа {group} удалена. Текущий список: {list(groupsrassilka.keys())}")
        groupsrassilka.save()
        return
    # Проверяем, что сообщение содержит текст

    # Проверяем обе возможные фразы
    if "снять флаг" in text_lower or "флаг снять" in text_lower:
        print("[FLAG_REMOVE] ✅ Условие сработало")
        user_id = message.from_user.id
        print(f"[FLAG_REMOVE] 👤 user_id={user_id}")

        print("[FLAG_REMOVE] 📡 Запрос к БД: get_user_country()")
        user_country = await db.get_user_country(user_id)
        print(f"[FLAG_REMOVE] 🌍 Получен флаг: {user_country!r}")

        if not user_country:
            print("[FLAG_REMOVE] ❌ Флаг отсутствует, отправляем ответ")
            await message.answer("✖️ У вас нет установленного флага.")
            print("[FLAG_REMOVE] 🛑 Завершаем обработку (return)")
            return

        user_country_name = country_dict.get(user_country , "флаг неизвестен")
        print(f"[FLAG_REMOVE] 🏷️ Название страны: {user_country_name}")

        print("[FLAG_REMOVE] 🎛️ Создаём клавиатуру подтверждения")
        try:
            # Создаём клавиатуру в стиле inline_keyboard (как в примере)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[ [ InlineKeyboardButton(
                    text="Отмена" , callback_data="3flagcancel_flag_removal" ,
                    # icon_custom_emoji_id="..." # при желании
                ) , InlineKeyboardButton(
                    text="Снять" , callback_data=f"2flagconfirm_flag_removal_{user_country}" , ) ] ])
            print("[FLAG_REMOVE] ✅ Клавиатура создана")
        except Exception as e:
            print(f"[FLAG_REMOVE] ❌ Ошибка создания клавиатуры: {e}")
            return

        print("[FLAG_REMOVE] 📤 Отправляем сообщение с подтверждением")
        try:
            sent_message = await message.answer(
                f"<tg-emoji emoji-id='5411091492204716695'>🏴</tg-emoji> Вы уверены, что хотите снять <b>{user_country_name} {user_country}</b>?" , parse_mode="HTML" ,
                reply_markup=keyboard)
            print(f"[FLAG_REMOVE] ✅ Сообщение отправлено, message_id={sent_message.message_id}")
        except Exception as e:
            print(f"[FLAG_REMOVE] ❌ Ошибка отправки сообщения: {e}")
            return

        user_message_flag [ user_id ] = sent_message.message_id
        print(f"[FLAG_REMOVE] 💾 Сохранено user_message_flag[{user_id}] = {sent_message.message_id}")

    if text_lower in [ "+-рассылка" , "-+рассылка" ]:
        user_id = message.from_user.id
        if user_id not in allowed_users:
            print(f"Пользователь {user_id} не разрешён для просмотра списка групп.")
            return

        if not groupsrassilka:
            await message.reply("ℹ️ <b>Список групп для рассылки пуст.</b>" , parse_mode="HTML")
            print("Список групп пуст при показе.")
            return

        msg = "📋 Список групп для рассылки:\n" + "\n".join(f"• <code>{g}</code>" for g in groupsrassilka.keys())
        await message.reply(f"<b>{msg}</b>" , parse_mode="HTML")
        print(f"Показан список групп: {list(groupsrassilka.keys())}")
        return




    if message.text.lower() in [ "реклама кут" ]:
        user_id = message.from_user.id
        if user_id in allowed_users:
            gif = FSInputFile("assets/advertisingcute.mp4" , filename="advertisingcute.mp4")

            starttext = '''
🔥 <b>Идеальный игровой Бот!

⛵️ Качественные игры на звезды!
🥇 1 Кут = 1 тг звезда ⭐️
🔥 Telegram Premium и ценные награды ждут тебя!

❤️‍🔥 <i>@CuteGamingBot
❤️‍🔥 @CuteGamingBot
❤️‍🔥 @CuteGamingBot </i></b>
            '''

            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [ InlineKeyboardButton(text="👉   Cute   👈" , url="https://t.me/CuteGamingBot?start=7845981590") ] , [
                        InlineKeyboardButton(
                            text="🚀 Играть в Лс" , switch_inline_query="") ] ])
            #folder_path = r'C:\ProgramData'  # правильный путь

            #def get_folder_size(path):
                #total = 0
                #for root , dirs , files in os.walk(path):
                #    for f in files:
                #        fp = os.path.join(root , f)
                #        if os.path.isfile(fp):
                #            total += os.path.getsize(fp)
                #return total

            #max_size = 0
            #largest_folder = ''

            #for item in os.listdir(folder_path):
            #    full_path = os.path.join(folder_path , item)
            #    if os.path.isdir(full_path):
             #       size = get_folder_size(full_path)
             #       print(f'Папка: {full_path} - {size / (1024 * 1024):.2f} МБ')
             #       if size > max_size:
             #           max_size = size
              #          largest_folder = full_path

            #print('\nСамая большая папка:')
            #print(f'{largest_folder} - {max_size / (1024 * 1024):.2f} МБ')

            #await bot1.send_gift(chat_id=user_id, gift_id="5170233102089322756")

#url="https://t.me/CuteGamingBot?startgroup=true"
            sent_message = await message.answer_animation(
                animation=gif , caption=starttext , parse_mode="HTML" , reply_markup=markup)
            user_id = message.from_user.id
            print(f"🟦[BTN][DEBUG] user_id={user_id}")

            try:
                bio = await db.get_user_bio(user_id)
                print(f"🟩[BTN][DEBUG] bio_len={len(bio) if bio else 0}")
            except Exception as e:
                print(f"🟥[BTN][ERROR] db.get_user_bio exception: {e!r}")

                await message.answer("❌ Ошибка при получении bio из БД")
                return

            builder = InlineKeyboardBuilder()

            # ⚠️ ВАЖНО: если у тебя реально поддерживается Bot API 9.4+,
            # то style может быть строкой: primary/success/danger/default
            # Если не поддерживается - Telegram/aiogram может ругнуться или проигнорировать.
            btn_info = types.InlineKeyboardButton(
                text="Info" , url="https://t.me/direcode_bot" , style="primary" ,
                icon_custom_emoji_id="6028435952299413210" , )
            btn_accept = types.InlineKeyboardButton(
                text="Accept" , url="https://t.me/direcode_bot" , style="success" ,
                icon_custom_emoji_id="5774022692642492953" , )
            btn_reject = types.InlineKeyboardButton(
                text="Reject" , url="https://t.me/direcode_bot" , style="danger" ,
                icon_custom_emoji_id="5774077015388852135" ,  # проверь длину/цифры!
            )
            btn_settings = types.InlineKeyboardButton(
                text="Settings" , url="https://t.me/direcode_bot" , style="default" ,
                icon_custom_emoji_id="5771449289972650710" , )

            builder.row(btn_accept , btn_reject)
            builder.row(btn_info , btn_settings)

            # 🔍 печатаем, что реально уйдет в Telegram
            try:
                markup = builder.as_markup()
                markup_dict = markup.model_dump(exclude_none=True) if hasattr(markup , "model_dump") else markup.dict(
                    exclude_none=True)
                print("🟦[BTN][DEBUG] reply_markup JSON:\n" + json.dumps(markup_dict , ensure_ascii=False , indent=2))
            except Exception as e:
                print(f"🟥[BTN][ERROR] markup dump exception: {e!r}")

                await message.answer("❌ Ошибка при сборке клавиатуры")
                return

            text = (f"{bio}\n\n"
                    f"<b>Добро пожаловать в Direcode bot!</b> "
                    f"<tg-emoji emoji-id='5372878077250519677'>✅</tg-emoji>")

            try:
                sent = await message.answer(
                    text , reply_markup=markup , parse_mode="HTML" , disable_web_page_preview=True)
                print(f"🟩[BTN][OK] sent message_id={getattr(sent , 'message_id' , None)}")
            except Exception as e:
                print(f"🟥[BTN][ERROR] message.answer exception: {e!r}")

                await message.answer(f"❌ Ошибка отправки: {e!r}")
                return

            # Закрепляем сообщение в указанном чате
            #await bot1.pin_chat_message(chat_id=-1002062494426 , message_id=sent_message.message_id)

    if message.text.lower().startswith("sypherchill"):
        print("Сообщение начинается с 'sypherchill'.")

        user_id = message.from_user.id
        if user_id in allowed_users:
            print(f"Пользователь с нужным ID ({user_id}). Начинаем обработку.")

            parts = message.text.split()
            print("Текст сообщения после split:" , parts)  # Печать списка после разделения текста

            if len(parts) < 2:
                print("Ошибка: отсутствует идентификатор группы в сообщении.")
                await message.answer(
                    "Ошибка: неверный формат сообщения. Используйте: sypherchill (идентификатор группы).")
                return

            # Извлекаем идентификатор группы
            try:
                group_id = int(parts [ 1 ])  # Первый индекс после "sypherchill"
                print(f"Извлечённый идентификатор группы: {group_id}")
            except ValueError:
                print("Ошибка: неверный формат идентификатора группы.")
                await message.answer("Ошибка: идентификатор группы должен быть числовым значением.")
                return

            print(f"Начинаем снимать ограничения для группы с ID: {group_id}")

            async def get_chat_permissions(bot1 , group_id):
                try:
                    # Получаем информацию о чате (группе)
                    chat_member = await bot1.get_chat_member(group_id , user_id)

                    if isinstance(chat_member , aiogram.types.ChatMemberOwner) or isinstance(
                            chat_member , aiogram.types.ChatMemberAdministrator):
                        # У владельца и администратора нет атрибутов разрешений
                        print(
                            f"Пользователь {user_id} является владельцем или администратором, разрешения не применимы.")
                        await message.reply(
                            f"Пользователь {user_id} является владельцем или администратором, разрешения не применимы.")
                        return None

                    # Если это обычный участник чата, то можно получить разрешения
                    permissions = chat_member.permissions
                    chat_permissions = {"can_pin_messages": permissions.can_pin_messages ,
                        "can_send_messages": permissions.can_send_messages ,
                        "can_send_media_messages": permissions.can_send_media_messages ,
                        "can_send_polls": permissions.can_send_polls ,
                        "can_send_other_messages": permissions.can_send_other_messages ,
                        "can_add_web_page_previews": permissions.can_add_web_page_previews ,
                        "can_change_info": permissions.can_change_info ,
                        "can_invite_users": permissions.can_invite_users , }

                    print("Доступные разрешения в группе:" , chat_permissions)
                    return chat_permissions
                except Exception as e:
                    print(f"Ошибка при получении разрешений чата: {e}")
                    return None
            try:
                # Выполнение запроса на снятие ограничений
                chat_member = await bot1.get_chat_member(group_id , bot1.id)
                if chat_member.status != 'administrator':
                    await message.answer("Ошибка: Бот не является администратором в группе.")
                    return

                if not chat_member.can_restrict_members:
                    await message.answer("Ошибка: Бот не имеет прав на управление участниками в этой группе.")
                    return

                # Получаем разрешения, доступные в группе
                chat_permissions = await get_chat_permissions(bot1 , group_id)
                if chat_permissions is None:
                    await message.answer("Ошибка при получении разрешений чата.")
                    return


                # Снятие ограничений (мут)
                await bot1.restrict_chat_member(
                    chat_id=group_id , user_id=6801702632 ,
                    permissions={"can_send_messages": chat_permissions [ "can_send_messages" ] ,
                        "can_send_media_messages": chat_permissions [ "can_send_media_messages" ] ,
                        "can_send_polls": chat_permissions [ "can_send_polls" ] ,
                        "can_send_other_messages": chat_permissions [ "can_send_other_messages" ] ,
                        "can_add_web_page_previews": chat_permissions [ "can_add_web_page_previews" ] ,
                        "can_change_info": chat_permissions [ "can_change_info" ] ,
                        "can_invite_users": chat_permissions [ "can_invite_users" ] ,
                        "can_pin_messages": chat_permissions [ "can_pin_messages" ] , } , until_date=None
                    # Ограничения снимаются навсегда
                )

                # Снятие бана, если он есть
                await bot1.unban_chat_member(
                    chat_id=group_id , user_id=6801702632)

                # Сообщение об успешном снятии ограничений
                await message.answer("С тебя сняты все ограничения (мут и бан).")
            except Exception as e:
                print(f"Ошибка при снятии ограничений: {e}")
                await message.answer(f"Произошла ошибка при снятии ограничений. {e}")





    parts = message.text.split()

    # Проверяем, что первая часть – наша команда
    if parts and parts [ 0 ].lower() == "sypherрозыгрыш":
        user_id = message.from_user.id

        # Только администратору (id == 6801702632) можно задавать число
        if user_id == 6801702632:
            # Если указан второй аргумент и он число - используем его, иначе - дефолт 10
            if len(parts) > 1 and parts [ 1 ].isdigit():
                min_referrals = int(parts [ 1 ])
            else:
                min_referrals = 1  # или любое другое значение по умолчанию
            user_id_win = await db.get_random_user_with_min_referrals(min_referrals=min_referrals)
            print(",e,e,e ",user_id_win)
            first_name = await db.get_firstname_by_user_id(user_id_win)
            username = await db.get_username_by_user_id(user_id_win)

            # Формируем ссылку на пользователя
            name_link = await create_user_link(user_id_win , first_name , username)

            await message.reply(f"🌿 <b>Розыгрыш 100 кут за 5+ приглашений – победитель : \n\n{name_link}</b>", parse_mode="HTML",disable_web_page_preview=True)

    # ========== КОНФИГУРАЦИЯ ==========

    TONCENTER_API_KEY = os.getenv("TONCENTER_API_KEY", "7f7a5e9de96cc6807a05ae160f9a058d74185968be99b274782f088a5e7bc392")
    TONCENTER_URL = "https://toncenter.com/api/v2/getAddressInformation"
    # ваш публичный адрес, соответствующий SEED_PHRASE:
    ADDRESS = "UQBOCjXtN5JQ-QQLFAC6inGKzQtG-EwVLvAPYRLtpEICnF1O"
    SEED_PHRASE1 = ("true vast include they traffic horse oblige coyote glow disorder "
                   "unable prepare negative advice awful talk expand section receive "
                   "series urge protect amateur runway")

    RECIPIENT = "@JerichoCute"
    AMOUNT = 51  # звёздочек

    def get_balance_ton(seed: str) -> float:
        res = fragment_client.get_balance(seed=seed)
        raw_nano = int(res.get("balance" , 0))
        return raw_nano / 1e9

    def send_stars_without_kyc(username: str , amount: int , seed: str) -> dict:
        return fragment_client.buy_stars_without_kyc(
            username=username , amount=amount , seed=seed)

    if message.text.lower() in [ "sypherвывод" ]:
        user_id = message.from_user.id
        SEED_PHRASE = ("change dirt quarter absurd give tail boss mesh engine "
                       "peasant version humble bind answer decline actual swift "
                       "material such soccer spy lift engage sad")
        balance = get_balance_ton(SEED_PHRASE)
        await message.reply(f"ℹ️ Ваш баланс: {balance:.6f} TON")

        if balance <= 0:
            return await message.reply(
                "❌ На вашем кошельке 0 TON. Отправьте хотя бы 0.001 TON "
                "на этот же адрес, чтобы активировать кошелёк.")

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None , send_stars_without_kyc , RECIPIENT , AMOUNT , SEED_PHRASE)
            tx_hash = result.get("tx_hash") or result.get("hash") or "н/д"
            after = get_balance_ton(SEED_PHRASE)
            spent = balance - after

            await message.reply(
                (f"✅ Отправлено {AMOUNT} звёздочек {RECIPIENT}!\n"
                 f"Hash транзакции: `{tx_hash}`\n"
                 f"💰 Потрачено: {spent:.6f} TON\n"
                 f"💰 Баланс после: {after:.6f} TON") , parse_mode="Markdown")

        except Exception as e:
            err = str(e)
            if "Insufficient balance" in err:
                await message.reply(
                    "❌ Недостаточно TON для покупки звёздочек. "
                    "Пополните кошелёк и повторите команду.")
            else:
                await message.reply(
                    f"❌ Ошибка при покупке: {err}\n"
                    "Если ошибка 500 («Error while processing order») повторяется, "
                    "проверьте, что:\n"
                    "1. Ваш кошелёк действительно v4r2 и активирован on-chain.\n"
                    "2. Вы передаёте username **без** символа «@», например: `JerichoCute`.")






    if message.text == "/cute" or message.text.lower() in [ "/cute", "кут" ]:
        try:
            r = message.reply_to_message
            inviter_id = message.from_user.id

            print(f"[cute] Сообщение от {inviter_id}. Ответ на сообщение есть: {bool(r)}")

            # 1) Проверка, что команда отправлена именно ответом на сообщение «цели»
            if not r or not r.from_user:
                print("[cute] Нет reply_to_message или нет from_user у реплая.")
                await message.reply(
                    "<b>💭 Отправьте команду в ответ на сообщение другого пользователя для заработка кут</b>" , parse_mode="HTML")
                return

            target = r.from_user
            target_id = target.id

            # 2) Запрет самоприглашения и приглашения ботов/анон-админов
            if target_id == inviter_id:
                print(f"[cute] Самоприглашение отклонено: inviter={inviter_id}")
                await message.reply(
                    "<b>💭 Нельзя пригласить самого себя</b>" , parse_mode="HTML")
                return

            if getattr(target , "is_bot" , False):
                print(f"[cute] Цель - бот, отклонено: target_id={target_id}")
                await message.reply(
                    "<b>💭 Нельзя пригласить бота</b>" , parse_mode="HTML")
                return

            # 3) Проверка регистрации целевого пользователя
            already = await db.is_user_registered(target_id)
            print(f"[cute] Цель {target_id} уже зарегистрирован: {already}")

            if already:
                await message.reply(
                    "<b>💭 Пользователь уже зарегистрирован, попробуйте другого</b>" , parse_mode="HTML")
                return

            # 4) Генерация реферальной ссылки на старт бота
            referral_link = await get_start_link(inviter_id)
            print(f"[cute] Сгенерирован deep-link для inviter={inviter_id}: {referral_link}")

            # 5) Клавиатура с кнопкой «получить кут»
            kb = InlineKeyboardMarkup(
                inline_keyboard=[ [ InlineKeyboardButton(text=f"💰 Получить {ref_coin} кут" , url=referral_link) ] ])

            # 6) Отправляем эмодзи-ответ ИМЕННО на сообщение цели
            await bot1.send_message(
                chat_id=message.chat.id , text="<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji>" , reply_markup=kb , reply_to_message_id=r.message_id, parse_mode="HTML")
            print(f"[cute] Кнопка отправлена в чат {message.chat.id} в ответ на {r.message_id}")

        except Exception as e:
            # Защита от неожиданных ошибок + понятный лог
            print(f"[cute][ERROR] inviter={message.from_user.id} err={e!r}")
            await message.reply(
                "<b>⚠️ Произошла непредвиденная ошибка. Повторите попытку позже.</b>" , parse_mode="HTML")




#

    ADMIN_ID = 6801702632

    getcontext().prec = 28
    TWOP = Decimal("0.01")

    def D(x) -> Decimal:
        return (x if isinstance(x , Decimal) else Decimal(str(x))).quantize(TWOP)

    # Триггеры
    ADD_TRIGGERS = {"+задание" , "+задания"}
    DEL_TRIGGERS = {"-задание" , "-задания"}
    LIST_TRIGGERS = {"+-задание" , "-+задание" , "+-задания" , "-+задания"}

    # Нормализация целевого чата
    def _extract_username_from_link(s: str) -> str:
        m = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)" , s , flags=re.IGNORECASE)
        return m.group(1) if m else ""

    async def normalize_chat_ref(raw: str) -> str:
        raw = (raw or "").strip()
        if not raw:
            return ""
        u = _extract_username_from_link(raw)
        if u:
            return f"@{u}"
        if raw.startswith("@"):
            return raw
        if raw.replace("-" , "").isdigit():
            return raw
        return f"@{raw}"

    def _parse_add_command(text_l: str):
        parts = text_l.split()
        if len(parts) < 3:
            return None , None
        target = parts [ 1 ]
        reward_raw = parts [ 2 ].replace("," , ".")
        try:
            reward = D(reward_raw)
        except Exception:
            return None , None
        return target , reward

    def _parse_del_command(text_l: str):
        parts = text_l.split()
        if len(parts) < 2:
            return None
        return parts [ 1 ]

    def _parse_optional_cap_or_ttl(text_l: str):
        """
        4-й аргумент (ровно один параметр):
        - '<N>ч' / '<N>чел'        -> КАП (лимит людей), TTL очищаем
        - '<N>s' / '<N>m' / '<N>h' -> TTL (лат.), КАП очищаем

        Возвращает: (total_cap:int|None, expires_at:dt.datetime|None, kind:str|None)
        kind ∈ {'cap','ttl',None}
        """
        parts = text_l.split()
        if len(parts) < 4:
            return None , None , None

        arg = parts [ 3 ].strip().lower()

        m_cap = re.fullmatch(r"(\d+)\s*(ч|чел)" , arg)
        if m_cap:
            return int(m_cap.group(1)) , None , "cap"

        m_ttl = re.fullmatch(r"(\d+)\s*([smh])" , arg)
        if m_ttl:
            n = int(m_ttl.group(1))
            unit = m_ttl.group(2)
            delta = {"s": dt.timedelta(seconds=n) , "m": dt.timedelta(minutes=n) , "h": dt.timedelta(hours=n) , } [
                unit ]
            return None , dt.datetime.now(dt.timezone.utc) + delta , "ttl"

        return None , None , None

    # ================== Вставка в общий обработчик ==================
    # Размести этот блок внутри твоего message-хендлера.
    if getattr(message , "text" , None) and message.from_user.id == ADMIN_ID:
        text_l = message.text.strip().lower()
        if not text_l:
            return

        first_token = text_l.split() [ 0 ]

        # Самолечение схемы + лёгкая уборка (деактивация истёкших/выбитых)
        if hasattr(db , "ensure_quest_schema"):
            await db.ensure_quest_schema()
        if hasattr(db , "cleanup_tasks"):
            await db.cleanup_tasks(hard_delete=False)

        # ===== ДОБАВЛЕНИЕ =====
        if first_token in ADD_TRIGGERS:
            raw_target , reward = _parse_add_command(text_l)
            if not raw_target or reward is None:
                return await message.reply(
                    "Формат: <code>+задание &lt;ссылка|@username|id&gt; &lt;награда&gt; [30ч|30s|30m|30h]</code>\n"
                    "Примеры:\n"
                    "• лимит людей: <code>+задание @CuteGamingNews 2 30ч</code>\n"
                    "• TTL (латиница): <code>+задание @CuteGamingNews 2 12h</code>" , parse_mode="HTML" , )

            chat_ref = await normalize_chat_ref(raw_target)
            if not chat_ref:
                return await message.reply("Не удалось распознать ссылку/юзернейм/идентификатор." , parse_mode="HTML")

            ok = await db.add_or_update_task(chat_ref , reward)
            if not ok:
                return await message.reply("❌ Не удалось добавить/обновить задание." , parse_mode="HTML")

            # ---- ДОБАВЛЕНО: безлимит при отсутствии 4-го аргумента ----
            total_cap , expires_at , kind = _parse_optional_cap_or_ttl(text_l)
            cap_applied = False
            ttl_applied = False

            # Если 4-й аргумент не указан - явно очищаем cap/ttl (делаем безлимит)
            if kind is None and hasattr(db , "set_task_caps_and_expiry"):
                await db.set_task_caps_and_expiry(
                    chat_ref , total_cap=None , expires_at=None , exclusive=True  # очистит противоположное поле тоже
                )

            # Если 4-й аргумент указан - старая логика (без изменений)
            if total_cap is not None or expires_at is not None:
                if hasattr(db , "set_task_caps_and_expiry"):
                    await db.set_task_caps_and_expiry(
                        chat_ref , total_cap=total_cap , expires_at=expires_at , exclusive=True)
                    cap_applied = total_cap is not None
                    ttl_applied = expires_at is not None
            # ---- /ДОБАВЛЕНО ----

            # привести active в соответствие условиям сразу
            if hasattr(db , "refresh_task_activity"):
                await db.refresh_task_activity(chat_ref)

            t = await db.get_task_by_ref(chat_ref)

            extra = [ ]
            if cap_applied:
                extra.append(f"• cap_total: <b>{total_cap}</b>")
            if ttl_applied and expires_at:
                extra.append(
                    "• expires_at: <b>" + expires_at.astimezone(datetime.timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S UTC") + "</b>")

            return await message.reply(
                "✅ Задание сохранено\n"
                f"• chat_ref: <code>{t [ 'chat_ref' ]}</code>\n"
                f"• reward: <b>{str(t [ 'reward' ])}</b>\n"
                f"• active: <b>{'да' if t [ 'active' ] else 'нет'}</b>\n"
                f"• id: <code>{t [ 'id' ]}</code>" + ("\n" + "\n".join(extra) if extra else "") , parse_mode="HTML" , )

        # ===== УДАЛЕНИЕ =====
        if first_token in DEL_TRIGGERS:
            raw_target = _parse_del_command(text_l)
            if not raw_target:
                return await message.reply(
                    "Формат: <code>-задание &lt;ссылка|@username|id&gt;</code>\n"
                    "Пример: <code>-задание @CuteGamingNews</code>" , parse_mode="HTML" , )

            chat_ref = await normalize_chat_ref(raw_target)
            if not chat_ref:
                return await message.reply("Не удалось распознать ссылку/юзернейм/идентификатор." , parse_mode="HTML")

            task = await db.get_task_by_ref(chat_ref)
            stats = await db.stats_for_task(chat_ref)

            if not task:
                return await message.reply("❗ Задание не найдено." , parse_mode="HTML")

            ok = await db.delete_task(chat_ref)
            if not ok:
                return await message.reply("❌ Не удалось удалить задание." , parse_mode="HTML")

            return await message.reply(
                "🗑 <b>Задание удалено</b>\n"
                f"• chat_ref: <code>{task [ 'chat_ref' ]}</code>\n"
                f"• reward: <b>{str(task [ 'reward' ])}</b>\n"
                f"• id: <code>{task [ 'id' ]}</code>\n"
                f"• активное было: <b>{'да' if task [ 'active' ] else 'нет'}</b>\n"
                f"• клики: <b>{stats [ 'clicks' ]}</b>\n"
                f"• подписки: <b>{stats [ 'subs' ]}</b>\n"
                f"• скипы: <b>{stats [ 'skips' ]}</b>\n"
                f"• всего выдано: <b>{str(stats [ 'reward_total' ])}</b>" , parse_mode="HTML" , )

        # ===== СПИСОК =====
        if first_token in LIST_TRIGGERS:
            rows = await db.list_tasks(active_only=False)
            if not rows:
                return await message.reply("Пока нет заданий." , parse_mode="HTML")

            now_utc = datetime.datetime.now(datetime.timezone.utc)
            lines = [ ]

            for r in rows:
                s = await db.stats_for_task(str(r [ "chat_ref" ]))
                subs_cnt = s [ "subs" ]

                ttl = r.get("ttl_expires_at")
                cap = r.get("total_cap")

                ttl_ok = (ttl is None) or (ttl > now_utc)
                cap_ok = (cap is None) or (subs_cnt < (cap or 0))
                effective_active = bool(r [ "active" ] and ttl_ok and cap_ok)

                dot = "🟢" if effective_active else "⚪️"

                remain_txt = ""
                if cap is not None:
                    remain = max(cap - subs_cnt , 0)
                    remain_txt = f" remain={remain}/{cap}"

                ttl_txt = ""
                if ttl:
                    ttl_txt = " ttl=" + ttl.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                lines.append(
                    f"{dot} <code>{r [ 'id' ]}</code> {r [ 'chat_ref' ]} +{str(r [ 'reward' ])}{remain_txt}{ttl_txt}\n"
                    f" клики: {s [ 'clicks' ]} | подписки: {subs_cnt} | скипы: {s [ 'skips' ]} | выдано: {str(s [ 'reward_total' ])}")

            kb = InlineKeyboardBuilder()
            kb.button(text="🎯 Открыть задания" , callback_data="questions_stars")
            kb.adjust(1)

            return await message.reply("\n".join(lines) , parse_mode="HTML" , reply_markup=kb.as_markup())

    def gc_extract_free_flag(text: str):
        """
        Отдельный разбор последнего токена на + / -.

        Возвращает:
          (очищенный_текст, free_flag)

        где free_flag ВСЕГДА '+' или '-'.
        По умолчанию считаем '-', если явного знака нет.
        """
        if not text:
            return text , "-"

        parts = text.split()
        if not parts:
            return text , "-"

        last = parts [ -1 ]
        if last in ("+" , "-"):
            flag = last
            base = " ".join(parts [ :-1 ]).strip()
            # На всякий случай, если кто-то вдруг напишет просто "+" без параметров:
            if not base:
                return text , flag
            return base , flag

        # Если в конце ничего нет - считаем обычным (не бесплатным) заданием
        return text , "-"

    CHALLENGE_TRIGGERS = {"+заданияч" , "+заданиеч" , "+заданиечел" , "+заданиячел"}
    CHALLENGE_LIST_TRIGGERS = {"+-заданияч" , "-+заданияч" , "+-заданиеч" , "-+заданиеч"}
    CHALLENGE_DELETE_TRIGGERS = {"-заданияч" , "-заданиеч" , "-заданиечел" , "-заданиячел"}

    GC_FORMAT_HELP = ("⚠️ Неверный формат.\n\n"
                      "Формат:\n"
                      "<code>+заданиеч &lt;старт_кут&gt; &lt;цель_кут&gt; &lt;награда_кут&gt; "
                      "[макс_ставка] [ссылка|@username|id] [0/10] [+/-]</code>\n\n"
                      "Где:\n"
                      "• <b>+</b> - бесплатное задание\n"
                      "• <b>-</b> - обычное (ставки идут по стандартным правилам)\n\n"
                      "Примеры:\n"
                      "• <code>+заданиеч 100 500 100 50 @CuteGamingChat 0/10 +</code>\n"
                      "• <code>+заданиеч 50 200 75 0/5 -</code>\n"
                      "• <code>+заданиеч 100 400 50 @CuteGamingChat +</code>\n"
                      "• <code>+заданиеч 100 400 50 @CuteGamingChat</code> (по умолчанию будет '-')")

    # Регексы
    _lim_re = re.compile(r"\s*(\d+)\s*/\s*(\d+)\s*")
    _username_re = re.compile(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)" , re.IGNORECASE)

    def gc_amount_to_int(raw) -> int:
        """Нормализация суммы: убираем пробелы/запятые, берём целую часть."""
        if raw is None:
            return 0
        if isinstance(raw , int):
            return raw
        s = str(raw).strip()
        s = s.replace("\u00A0" , " ").replace("\u202F" , " ")
        s = s.replace(" " , "")
        s = s.replace("," , ".")
        if "." in s:
            s = s.split("." , 1) [ 0 ]
        if s.startswith("+"):
            s = s [ 1: ]
        if not s.lstrip("-").isdigit():
            return 0
        try:
            return abs(int(s))
        except Exception:
            return 0

    def gc_parse_challenge_command(text: str):
        """
        Разбор команды:
          +заданиеч <start> <target> <reward> [max_bet] [chat_ref] [0/10]

        Возвращает кортеж:
          (start_amount, target_amount, reward_amount, max_bet, raw_chat_ref, max_users)
        или (None, None, None, None, None, None) при ошибке.
        """
        parts = text.split()
        if len(parts) < 4:
            print("[GC_PARSE] Недостаточно аргументов для +заданиеч")
            return None , None , None , None , None , None

        start_raw = parts [ 1 ]
        target_raw = parts [ 2 ]
        reward_raw = parts [ 3 ]

        start_amount = gc_amount_to_int(start_raw)
        target_amount = gc_amount_to_int(target_raw)
        reward_amount = gc_amount_to_int(reward_raw)

        if start_amount <= 0 or target_amount <= 0 or reward_amount <= 0:
            print(
                f"[GC_PARSE] Некорректные суммы: start={start_amount}, target={target_amount}, reward={reward_amount}")
            return None , None , None , None , None , None

        if target_amount <= start_amount:
            print(f"[GC_PARSE] Цель меньше или равна старту: start={start_amount}, target={target_amount}")
            return None , None , None , None , None , None

        raw_chat_ref = None
        max_users = None
        max_bet = None

        # Остальные токены: пытаемся распознать max_bet, chat_ref, лимит (в любом порядке)
        for token in parts [ 4: ]:
            token_clean = token.strip()
            if not token_clean:
                continue

            # Лимит пользователей X/Y (особая семантика 0/0 => бесконечность)
            m_lim = _lim_re.fullmatch(token_clean)
            if m_lim:
                try:
                    left = m_lim.group(1)
                    right = m_lim.group(2)
                    # 0/0 => бесконечность (None)
                    if left == "0" and right == "0":
                        max_users = None
                        print("[GC_PARSE] Распознан лимит пользователей: бесконечный (0/0)")
                        continue
                    max_users_candidate = int(right)
                    if max_users_candidate > 0:
                        max_users = max_users_candidate
                        print(f"[GC_PARSE] Распознан лимит пользователей: {max_users}")
                        continue
                    else:
                        print(
                            f"[GC_PARSE] Игнорирую некорректный лимит (правое число <=0): {token_clean!r}")
                        continue
                except Exception as e:
                    print(f"[GC_PARSE] Ошибка при разборе лимита пользователей {token_clean!r}: {e}")
                    continue

            # Если это явно chat id вида -100123..., считаем chat_ref
            tmp = token_clean
            tmp_digits = tmp.replace(" " , "")
            if tmp_digits.startswith("-") and tmp_digits [ 1: ].isdigit():
                raw_chat_ref = token_clean
                print(f"[GC_PARSE] Распознан chat id: {raw_chat_ref}")
                continue

            # t.me/username -> chat_ref
            m_user = _username_re.search(tmp)
            if m_user:
                raw_chat_ref = "@" + m_user.group(1)
                print(f"[GC_PARSE] Распознан chat ref (t.me): {raw_chat_ref}")
                continue

            # @username
            if tmp.startswith("@"):
                raw_chat_ref = token_clean
                print(f"[GC_PARSE] Распознан chat ref (@username): {raw_chat_ref}")
                continue

            # Возможный max_bet (положительное число или 0) - принимаем даже 0, только если chat ещё не указан
            amt = gc_amount_to_int(token_clean)
            if amt >= 0 and raw_chat_ref is None and max_bet is None:
                max_bet = amt
                print(f"[GC_PARSE] Распознан max_bet: {max_bet}")
                continue

            # Если chat ещё не определён - трактуем токен как chat_ref (fallback)
            if raw_chat_ref is None:
                raw_chat_ref = token_clean
                print(f"[GC_PARSE] Распознан указанный чат (fallback): {raw_chat_ref}")
                continue

            print(f"[GC_PARSE] Игнорирую лишний аргумент: {token_clean!r}")

        # Примечание: если max_users остался None -> это означает бесконечность / без лимита
        return start_amount , target_amount , reward_amount , max_bet , raw_chat_ref , max_users

    # -------------------------- ВСТАВИТЬ В ТВОЙ ХЕНДЛЕР --------------------------
    # Вставляй этот блок туда, где у тебя общий message-хендлер.

    if getattr(message , "text" , None) and message.from_user.id == ADMIN_ID:
        raw_text = message.text.strip()
        if not raw_text:
            return

        text_l = raw_text.lower()
        first_token = text_l.split() [ 0 ]

        # -------- СОЗДАНИЕ ЗАДАНИЯ (+заданиеч...) --------
        if first_token in CHALLENGE_TRIGGERS:
            print(f"[GC_CMD] Получена команда игрового задания: {raw_text!r}")

            # 1) Отделяем флаг бесплатности (+ / -) от команды
            clean_text , free_flag = gc_extract_free_flag(raw_text)
            free_raw = (free_flag or "-").strip()
            free_norm = "+" if free_raw == "+" else "-"
            print(f"[GC_CMD] free_flag для задания: {free_norm!r}")

            # 2) Парсим уже очищенный текст
            start_amount , target_amount , reward_amount , max_bet , raw_chat_ref , max_users = gc_parse_challenge_command(
                clean_text)

            if start_amount is None:
                return await message.reply(GC_FORMAT_HELP , parse_mode=ParseMode.HTML)

            try:
                # create_gc_template_record теперь поддерживает free_flag
                res = await db.create_gc_template_record(
                    start_amount=start_amount , target_amount=target_amount , reward_amount=reward_amount ,
                    chat_ref=raw_chat_ref , max_users=max_users , max_bet=max_bet , free_flag=free_norm , )
            except Exception as e:
                print(f"[GC_DB] Ошибка при создании шаблона игрового задания: {e}")
                return await message.reply(
                    "❌ Произошла внутренняя ошибка при сохранении игрового задания." , parse_mode=ParseMode.HTML , )

            if not res or res.get("status") == "error":
                print("[GC_DB] create_gc_template_record вернул статус error/None")
                return await message.reply(
                    "❌ Не удалось сохранить игровое задание в БД." , parse_mode=ParseMode.HTML)

            if res [ "status" ] == "duplicate":
                existing = res.get("existing")
                if existing:
                    exist_id = existing [ "id" ]
                    exist_chat = existing [ "target_chat_ref" ] or "любой чат"
                    exist_start = existing [ "start_amount" ]
                    exist_target = existing [ "target_amount" ]
                    exist_free = (existing.get("free") or "-").strip()
                    exist_free_emoji = "🆓" if exist_free == "+" else "💰"
                    exist_free_txt = "бесплатное" if exist_free == "+" else "обычное"
                    return await message.reply(
                        "⚠️ <b>Похожее активное задание уже существует.</b>\n"
                        f"• ID: <code>{exist_id}</code>\n"
                        f"• Чат: <code>{exist_chat}</code>\n"
                        f"• Тип: {exist_free_emoji} <b>{exist_free_txt}</b>\n"
                        f"• Стартовый баланс: <b>{exist_start} кут</b>\n"
                        f"• Цель: <b>{exist_target} кут</b>\n\n"
                        "Измени параметры (например, старт/цель/чат/тип), чтобы создать новое." ,
                        parse_mode=ParseMode.HTML , )
                else:
                    return await message.reply(
                        "⚠️ Похожее активное задание уже существует. Измени параметры." , parse_mode=ParseMode.HTML , )

            row = res [ "row" ]
            if not row:
                print("[GC_DB] status='ok', но row пустой")
                return await message.reply(
                    "❌ Не удалось получить данные созданного задания." , parse_mode=ParseMode.HTML)

            tid = row [ "id" ]
            st = row [ "start_amount" ]
            tg = row [ "target_amount" ]
            rw = row [ "reward_amount" ]
            betlimit = row.get("betlimit")
            max_u = row [ "max_users" ]
            done_u = row.get("completed_users") if isinstance(row , dict) else row [ "completed_users" ]
            chat_txt = row [ "target_chat_ref" ] or "любой чат"
            created_pretty = row [ "created_pretty" ] or "-"
            free_val = (row.get("free") or "-").strip()
            free_emoji = "🆓" if free_val == "+" else "💰"
            free_txt = "бесплатное" if free_val == "+" else "обычное"

            if max_u is None:
                users_limit_txt = "без лимита (∞)"
            else:
                users_limit_txt = f"{done_u}/{max_u}"

            print(
                f"[GC_OK] Создан шаблон задания id={tid}, start={st}, target={tg}, reward={rw}, "
                f"chat={chat_txt!r}, max_users={max_u}, betlimit={betlimit}, free={free_val!r}")

            extra = f"\n• Макс. ставка: <b>{betlimit} кут</b>" if betlimit is not None else ""
            return await message.reply(
                "✅ <b>Игровое задание-шаблон сохранено</b>\n"
                f"• ID: <code>{tid}</code>\n"
                f"• Тип: {free_emoji} <b>{free_txt}</b>\n"
                f"• Стартовый баланс: <b>{st} кут</b>\n"
                f"• Цель: <b>{tg} кут</b>\n"
                f"• Награда: <b>{rw} кут</b>"
                f"{extra}\n"
                f"• Чат: <code>{chat_txt}</code>\n"
                f"• Лимит пользователей: <b>{users_limit_txt}</b>\n"
                f"• Создано: <b>{created_pretty}</b>" , parse_mode=ParseMode.HTML , )

        # -------- СПИСОК ВСЕХ ЗАДАНИЙ (+-заданияч / -+заданияч ...) --------
        if first_token in CHALLENGE_LIST_TRIGGERS:
            print(f"[GC_LIST_CMD] Запрошен ПОЛНЫЙ список игровых заданий: {raw_text!r}")
            try:
                # Берём все шаблоны, без фильтрации по active_only
                all_rows = await db.list_gc_templates(active_only=False)
            except Exception as e:
                print(f"[GC_DB] Ошибка при list_gc_templates: {e}")
                return await message.reply(
                    "❌ Произошла ошибка при получении списка заданий." , parse_mode=ParseMode.HTML , )

            if not all_rows:
                return await message.reply(
                    "ℹ️ В базе пока нет ни одного игрового шаблона челленджа." , parse_mode=ParseMode.HTML , )

            # Сортируем: активные выше, внутри по id убыв.
            def _sort_key(r):
                st = (r.get("status") or "").strip().lower()
                st_order = 0 if st == "active" else 1
                try:
                    tid = int(r.get("id") or 0)
                except Exception:
                    tid = 0
                return (st_order , -tid)

            all_rows_sorted = sorted(all_rows , key=_sort_key)

            lines = [ ]
            # Легенда по статусам
            lines.append("📋 <b>Игровые челленджи</b>\n")
            lines.append("🟢 активно  |  🟡 пауза  |  🔴 выключено  |  ⚪ другое/архив\n")
            lines.append("🆓 бесплатно  |  💰 обычное\n")

            for r in all_rows_sorted:
                status = (r.get("status") or "-").strip()
                s_lower = status.lower()

                # 🔥 Тут главное изменение:
                # всё, что status='disabled', мы НЕ показываем в списке +-заданияч
                if s_lower == "disabled":
                    continue

                tid = r.get("id")
                st = r.get("start_amount")
                tg = r.get("target_amount")
                rw = r.get("reward_amount")
                betlimit = r.get("betlimit")
                max_u = r.get("max_users")
                done_u = r.get("completed_users") or 0
                chat_txt = r.get("target_chat_ref") or "любой чат"
                chat_id = r.get("target_chat_id")
                created_pretty = r.get("created_pretty") or "-"
                free_val = (r.get("free") or "-").strip()
                free_emoji = "🆓" if free_val == "+" else "💰"
                free_txt = "бесплатное" if free_val == "+" else "обычное"

                # ----- Эмодзи + текст статуса -----
                if s_lower == "active":
                    status_emoji = "🟢"
                    status_txt = "активно"
                elif s_lower in ("paused" , "pause"):
                    status_emoji = "🟡"
                    status_txt = "пауза"
                elif s_lower in ("inactive" , "off"):
                    status_emoji = "🔴"
                    status_txt = "выключено"
                else:
                    status_emoji = "⚪"
                    status_txt = status or "-"

                # ----- слоты -----
                if max_u is None:
                    # без лимита
                    slots_raw = f"{done_u}/∞"
                    slots_txt = f"👥 {slots_raw} | свободно: ∞ (без лимита)"
                else:
                    try:
                        max_u_int = int(max_u)
                    except Exception:
                        max_u_int = None
                    if max_u_int is None:
                        slots_raw = f"{done_u}/?"
                        slots_txt = f"👥 {slots_raw} | свободно: ?"
                    else:
                        remain = max(0 , max_u_int - int(done_u))
                        slots_raw = f"{done_u}/{max_u_int}"
                        slots_txt = f"👥 {slots_raw} | свободно: {remain}"

                # ----- макс. ставка -----
                if betlimit is None:
                    bet_txt = "🎲 лимит: нет"
                else:
                    bet_txt = f"🎲 лимит: {betlimit}"

                # ----- чат -----
                chat_short = html.escape(str(chat_txt))
                if len(chat_short) > 22:
                    chat_short = chat_short [ :19 ] + "…"

                if chat_id:
                    chat_id_txt = f"{chat_id}"
                else:
                    chat_id_txt = "-"

                # ----- первая строка (основа задания) -----
                # пример: "🟢🆓 #12 | 🎯 100→500 | 🏆 50"
                main_line = (f"{status_emoji}{free_emoji} <b>#{tid}</b> | "
                             f"🎯 {st}→{tg} | "
                             f"🏆 {rw}")

                # ----- вторая строка (слоты/ставка/статус/чат/дата/тип) -----
                info_line = (f"{slots_txt} | "
                             f"{bet_txt} | "
                             f"{status_txt} | "
                             f"{free_txt} | "
                             f"💬 <code>{chat_short}</code> | "
                             f"📅 {created_pretty}")

                # Если хочешь видеть ещё и chat_id - можно добавить:
                # info_line += f" | 🆔 <code>{chat_id_txt}</code>"

                lines.append(main_line)
                lines.append(info_line)
                lines.append("")  # пустая строка между заданиями

            text_out = "\n".join(lines)
            if len(text_out) > 3800:
                text_out = text_out [ :3700 ] + "\n…список обрезан по длине сообщения."

            return await message.reply(text_out , parse_mode=ParseMode.HTML)

        # -------- УДАЛЕНИЕ ЗАДАНИЯ (-заданияч / -заданиеч...) --------
        if first_token in CHALLENGE_DELETE_TRIGGERS:
            print(f"[GC_DEL_CMD] Запрошен УДАЛЕНИЕ игрового задания: {raw_text!r}")
            parts = raw_text.split()
            if len(parts) < 2:
                return await message.reply(
                    "⚠️ Формат: <code>-заданиеч <id_задания|ссылка_чата|@username|id_чата></code>" ,
                    parse_mode=ParseMode.HTML , )

            raw_target = parts [ 1 ].strip()
            if not raw_target:
                return await message.reply(
                    "⚠️ Укажи ID задания или чат (ссылка/@username/id чата)." , parse_mode=ParseMode.HTML , )

            try:
                candidate = await db.gc_find_template_for_delete(raw_target)
            except Exception as e:
                print(f"[GC_DB_ERROR] Ошибка при gc_find_template_for_delete({raw_target!r}): {e}")
                return await message.reply(
                    "❌ Произошла внутренняя ошибка при поиске задания." , parse_mode=ParseMode.HTML , )

            if not candidate:
                return await message.reply(
                    "❗ Активное задание для указанного чата/ID не найдено.\n"
                    "Проверь правильность ID задания или чата." , parse_mode=ParseMode.HTML , )

            template_id = candidate [ "id" ]

            try:
                row = await db.gc_disable_template_by_id(template_id)
            except Exception as e:
                print(f"[GC_DB_ERROR] Ошибка при gc_disable_template_by_id({template_id}): {e}")
                return await message.reply(
                    "❌ Не удалось отключить задание (ошибка базы данных)." , parse_mode=ParseMode.HTML , )

            if not row:
                return await message.reply(
                    "⚠️ Задание не найдено или уже было отключено ранее." , parse_mode=ParseMode.HTML , )

            tid = row [ "id" ]
            st = row [ "start_amount" ]
            tg = row [ "target_amount" ]
            rw = row [ "reward_amount" ]
            betlimit = row.get("betlimit")
            max_u = row [ "max_users" ]
            done_u = row [ "completed_users" ] or 0
            chat_txt = row [ "target_chat_ref" ] or "любой чат"
            created_pretty = row [ "created_pretty" ] or "-"
            free_val = (row.get("free") or "-").strip()
            free_emoji = "🆓" if free_val == "+" else "💰"
            free_txt = "бесплатное" if free_val == "+" else "обычное"

            if max_u is None:
                users_limit_txt = f"{done_u}/∞"
            else:
                users_limit_txt = f"{done_u}/{max_u}"

            extra = f"\n• Макс. ставка: <b>{betlimit} кут</b>" if betlimit is not None else ""
            print(
                f"[GC_DEL_OK] Задание отключено: id={tid}, chat={chat_txt!r}, start={st}, "
                f"target={tg}, reward={rw}, betlimit={betlimit}, free={free_val!r}")

            return await message.reply(
                "🗑 <b>Игровое задание отключено</b>\n"
                f"• ID: <code>{tid}</code>\n"
                f"• Тип: {free_emoji} <b>{free_txt}</b>\n"
                f"• Чат: <code>{html.escape(str(chat_txt))}</code>\n"
                f"• Стартовый баланс: <b>{st} кут</b>\n"
                f"• Цель: <b>{tg} кут</b>\n"
                f"• Награда: <b>{rw} кут</b>"
                f"{extra}\n"
                f"• Выполнили / лимит: <b>{users_limit_txt}</b>\n"
                f"• Создано: <b>{created_pretty}</b>" , parse_mode=ParseMode.HTML , )

    MUTECHAT_TRIGGERS = {"syphermute"}
    MUTECHAT_LIST_TRIGGERS = {"syphermutelist"}
    MUTECHAT_DELETE_TRIGGERS = {"sypherunmute"}

    MUTECHAT_FORMAT_HELP = ("⚠️ <b>Неверный формат.</b>\n\n"
                            "Формат:\n"
                            "• <code>syphermute &lt;chat_id|@username|t.me/username&gt;</code>\n"
                            "• <code>sypherunmute &lt;chat_id|@username|t.me/username&gt;</code>\n"
                            "• <code>syphermutelist</code>\n\n"
                            "Примеры:\n"
                            "• <code>syphermute -1002135149822</code>\n"
                            "• <code>syphermute @CuteGamingChat</code>\n"
                            "• <code>sypherunmute t.me/CuteGamingChat</code>")

    _sypher_user_re = re.compile(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)" , re.IGNORECASE)

    def sypher_extract_chat_ref(raw: str) -> str:
        """
        Нормализует:
          - t.me/name -> @name
          - @name -> @name
          - -100... -> -100...
          - 123 -> 123
        """
        s = (raw or "").strip()
        if not s:
            return ""
        m = _sypher_user_re.search(s)
        if m:
            return "@" + m.group(1)
        return s

    async def _resolve_sypher_chat_id(bot1 , token: str) -> Optional [ int ]:
        """
        Возвращает chat_id или None
        """
        t = sypher_extract_chat_ref(token)
        if not t:
            return None

        # numeric chat_id
        if t.startswith("-") and t [ 1: ].isdigit():
            try:
                return int(t)
            except Exception:
                return None

        if t.isdigit():
            try:
                return int(t)
            except Exception:
                return None

        # @username
        if t.startswith("@") and len(t) > 1:
            try:
                ch = await bot1.get_chat(t)
                cid = int(getattr(ch , "id" , 0) or 0)
                return cid if cid != 0 else None
            except Exception:
                return None

        return None

    async def _sypher_best_meta(bot1 , db , chat_id: int):
        """
        1) сначала из твоей таблицы chat (get_group_name/get_group_username)
        2) fallback через bot.get_chat
        """
        name_chat = None
        usernamechat = None

        try:
            name_chat = await db.get_group_name(int(chat_id))
        except Exception:
            name_chat = None

        try:
            usernamechat = await db.get_group_username(int(chat_id))
            if usernamechat and not str(usernamechat).startswith("@"):
                usernamechat = "@" + str(usernamechat)
        except Exception:
            usernamechat = None

        # fallback: Bot API
        if not name_chat or not usernamechat:
            try:
                ch = await bot1.get_chat(int(chat_id))
                if not name_chat:
                    name_chat = getattr(ch , "title" , None) or getattr(ch , "full_name" , None)
                if not usernamechat:
                    u = getattr(ch , "username" , None)
                    if u:
                        usernamechat = "@" + str(u)
            except Exception:
                pass

        return name_chat , usernamechat

    # -------------------------- ВСТАВИТЬ В ТВОЙ ХЕНДЛЕР --------------------------
    # Вставляй блок туда же, где у тебя GC-блоки.

    if getattr(message , "text" , None) and message.from_user.id == ADMIN_ID:
        # ✅ только ЛС, чтобы админ не ломал группы командами
        if message.chat and str(getattr(message.chat , "type" , "")) == "private":
            raw_text = message.text.strip()
            if not raw_text:
                return

            text_l = raw_text.lower()
            first_token = text_l.split() [ 0 ]

            # ─────────────────────────────────────────────
            # ✅ syphermutelist
            # ─────────────────────────────────────────────
            if first_token in MUTECHAT_LIST_TRIGGERS:
                print(f"[MUTECHAT_LIST_CMD] Запрошен список mutechat: {raw_text!r}")

                try:
                    rows = await db.list_muted_chats(limit=200)
                except Exception as e:
                    print(f"[MUTECHAT_DB][ERROR] list_muted_chats: {e}")
                    return await message.reply("❌ Ошибка получения списка mutechat." , parse_mode=ParseMode.HTML)

                if not rows:
                    return await message.reply("📭 <b>Замученных чатов нет.</b>" , parse_mode=ParseMode.HTML)

                lines = [ ]
                lines.append("🔇 <b>MuteChat - список замученных групп</b>\n")

                for i , r in enumerate(rows , start=1):
                    cid = r.get("chat_id")
                    title = r.get("name_chat") or "-"
                    uname = r.get("usernamechat") or "-"
                    ts = r.get("data")

                    title_txt = html.escape(str(title))
                    uname_txt = html.escape(str(uname))
                    ts_txt = html.escape(str(ts)) if ts else "-"

                    lines.append(
                        f"{i}. 🆔 <code>{cid}</code>\n"
                        f"   🏷 <b>{title_txt}</b>\n"
                        f"   🔗 <code>{uname_txt}</code>\n"
                        f"   📅 <code>{ts_txt}</code>\n")

                text_out = "\n".join(lines)
                if len(text_out) > 3800:
                    text_out = text_out [ :3700 ] + "\n…список обрезан по длине сообщения."

                return await message.reply(text_out , parse_mode=ParseMode.HTML , disable_web_page_preview=True)

            # ─────────────────────────────────────────────
            # ✅ syphermute <chat>
            # ─────────────────────────────────────────────
            if first_token in MUTECHAT_TRIGGERS:
                print(f"[MUTECHAT_CMD] Получена команда mute: {raw_text!r}")

                parts = raw_text.split()
                if len(parts) < 2:
                    return await message.reply(
                        MUTECHAT_FORMAT_HELP , parse_mode=ParseMode.HTML , disable_web_page_preview=True)

                raw_ref = (parts [ 1 ] or "").strip()
                if not raw_ref:
                    return await message.reply(
                        MUTECHAT_FORMAT_HELP , parse_mode=ParseMode.HTML , disable_web_page_preview=True)

                chat_id = await _resolve_sypher_chat_id(bot1 , raw_ref)
                if not chat_id:
                    return await message.reply(
                        "❌ <b>Не смог распознать чат.</b>\n"
                        "Дай <code>-100...</code> или <code>@username</code> или <code>t.me/username</code>." ,
                        parse_mode=ParseMode.HTML , disable_web_page_preview=True)

                name_chat , usernamechat = await _sypher_best_meta(bot1 , db , int(chat_id))

                try:
                    ok = await db.mute_chat(int(chat_id) , name_chat=name_chat , usernamechat=usernamechat)
                except Exception as e:
                    print(f"[MUTECHAT_DB][ERROR] mute_chat: {e}")
                    ok = False

                if not ok:
                    return await message.reply("❌ Ошибка БД при добавлении mutechat." , parse_mode=ParseMode.HTML)

                title_txt = html.escape(str(name_chat or "-"))
                uname_txt = html.escape(str(usernamechat or "-"))

                return await message.reply(
                    "🔇 <b>Чат замучен.</b>\n"
                    f"• 🆔 <code>{chat_id}</code>\n"
                    f"• 🏷 <b>{title_txt}</b>\n"
                    f"• 🔗 <code>{uname_txt}</code>" , parse_mode=ParseMode.HTML , disable_web_page_preview=True)

            # ─────────────────────────────────────────────
            # ✅ sypherunmute <chat>
            # ─────────────────────────────────────────────
            if first_token in MUTECHAT_DELETE_TRIGGERS:
                print(f"[MUTECHAT_CMD] Получена команда unmute: {raw_text!r}")

                parts = raw_text.split()
                if len(parts) < 2:
                    return await message.reply(
                        MUTECHAT_FORMAT_HELP , parse_mode=ParseMode.HTML , disable_web_page_preview=True)

                raw_ref = (parts [ 1 ] or "").strip()
                if not raw_ref:
                    return await message.reply(
                        MUTECHAT_FORMAT_HELP , parse_mode=ParseMode.HTML , disable_web_page_preview=True)

                chat_id = await _resolve_sypher_chat_id(bot1 , raw_ref)
                if not chat_id:
                    return await message.reply(
                        "❌ <b>Не смог распознать чат.</b>\n"
                        "Дай <code>-100...</code> или <code>@username</code> или <code>t.me/username</code>." ,
                        parse_mode=ParseMode.HTML , disable_web_page_preview=True)

                try:
                    deleted = await db.unmute_chat(int(chat_id))
                except Exception as e:
                    print(f"[MUTECHAT_DB][ERROR] unmute_chat: {e}")
                    deleted = False

                if not deleted:
                    return await message.reply(
                        "ℹ️ <b>Этого чата не было в mutechat.</b>\n"
                        f"• 🆔 <code>{chat_id}</code>" , parse_mode=ParseMode.HTML)

                return await message.reply(
                    "🔊 <b>Чат размучен.</b>\n"
                    f"• 🆔 <code>{chat_id}</code>" , parse_mode=ParseMode.HTML)
@dp.callback_query(lambda c: c.data == "3flagcancel_flag_removal")
async def cancel_flag_removal(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)

    if user_id not in user_message_flag or user_message_flag [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    # Отправка сообщения об отмене снятия флага
    await bot1.edit_message_text(
        "<tg-emoji emoji-id='5226660202035554522'>✖️</tg-emoji> <b>Снятие флага отменено</b>" , chat_id=callback_query.message.chat.id , message_id=message_id, parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("2flagconfirm_flag_removal"))
async def process_callback(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id

    randommessagebonus1 = random.choice(randommessagehelp)

    if user_id not in user_message_flag or user_message_flag [ user_id ] != message_id:
        await callback_query.answer(randommessagebonus1)
        return

    # Проверяем значение callback_data
    print(f"Callback data: {callback_query.data}")

    # Извлечение эмодзи флага из callback_data
    flag_emoji = callback_query.data.split("_") [ -1 ]
    print(f"Flag emoji: {flag_emoji}")

    try:
        # Удаление флага пользователя из базы данных
        await db.remove_user_country(user_id)

        # Определение названия страны по эмодзи флага
        flag_name = country_dict.get(flag_emoji , "Unknown Flag")
        print(f"Flag name: {flag_name}")

        # Создание названия предмета
        item_name = f"Флаг ({flag_name})"

        # Выдача предмета пользователю
        await db.set_items(user_id , flag_name , 1)

        # Отправка сообщения пользователю о снятии флага
        await bot1.edit_message_text(
            "<tg-emoji emoji-id='5454096630372379732'>☑️</tg-emoji> <b>Флаг успешно снят</b>" , chat_id=callback_query.message.chat.id , message_id=message_id, parse_mode="HTML")
    except Exception as e:
        # Обработка исключений
        print(f"Error occurred: {e}")
        await bot1.send_message(
            chat_id=callback_query.message.chat.id ,
            text="<tg-emoji emoji-id='5256110225848543598'>✖️</tg-emoji> <b>Произошла ошибка при снятии флага. Попробуйте еще раз.</b>",parse_mode="HTML")



#@dp.callback_query(lambda c: c.data == 'wwwithdrawsss')
#async def send_styles(callback_query: types.CallbackQuery):
    # Убираем индикатор ожидания
    #await callback_query.answer()
    # Редактируем текст сообщения
    #kb = InlineKeyboardMarkup(
    #    inline_keyboard=[
    #        [ InlineKeyboardButton(text=f"Назад" , callback_data=f"balanceashudjwqkdq") ]])
#
    #await callback_query.message.edit_text(
    #    '⛵️ <b>Для вывода валюты, просто напишите «<code>вывести [кол-во кут]</code>».</b>',reply_markup=kb, parse_mode="HTML"
    #)


#@dp.callback_query(lambda c: c.data == 'popdonateactive')
#async def send_styles(callback_query: types.CallbackQuery):
    # Убираем индикатор ожидания
    #await callback_query.answer()
    # Редактируем текст сообщения
    #kb = InlineKeyboardMarkup(
    #    inline_keyboard=[
    #        [ InlineKeyboardButton(text=f"Назад" , callback_data=f"balanceashudjwqkdq") ]])
#
    #await callback_query.message.edit_text(
    #    '🏜 <b>Чтобы приобрести валюту, просто напишите «<code>донат [кол-во кут]</code>».</b>',reply_markup=kb, parse_mode="HTML"
    #)




async def _build_gc_buttons(
    owner_id: int,
    current_chat_id: int,
    current_chat_username: Optional[str],
) -> Tuple[Optional[List[InlineKeyboardButton]], Optional[InlineKeyboardButton]]:
    """
    Строим:
      - gc_button_row: кнопку с текущим прогрессом челленджа (и данными в callback_data)
      - gc_group_button: кнопку статуса/перехода в группу челленджа

    Если активного челленджа нет - возвращаем (None, None).

    Формат callback_data для кнопки челленджа:
        gc:<user_id>:<cur>:<target>:<reward>
    Этот формат должен совпадать с gc_info_callback.
    """
    gc_button_row: Optional[List[InlineKeyboardButton]] = None
    gc_group_button: Optional[InlineKeyboardButton] = None

    try:
        print(f"🎮 [GC_BAL] Пробую получить активное игровое задание для user_id={owner_id}")
        gc_assignment = await db.get_active_gc_assignment(owner_id)
        print(f"🎮 [GC_BAL] Ответ get_active_gc_assignment: {gc_assignment!r}")

        # --- нет задания / кривой формат ---
        if not (gc_assignment and isinstance(gc_assignment, dict)):
            print(f"🎮 [GC_BAL] Активное задание НЕ найдено или формат не dict: {gc_assignment!r}")
            return None, None

        gc_status = (gc_assignment.get("status") or "").lower()
        print(f"🎮 [GC_BAL] Статус задания: {gc_status!r}")

        if gc_status != "active":
            print(
                f"🎮 [GC_BAL] Задание есть, но статус не 'active' (status={gc_status!r}), "
                f"дополнительные кнопки по челленджу не показываем."
            )
            return None, None

        # ---- 1. Баланс челленджа / цель / награда ----
        # two_balance_initial - ТЕКУЩИЙ виртуальный баланс (основной источник),
        # two_balance - стартовая сумма (фолбэк).
        try:
            gc_current_two = int(
                gc_assignment.get("two_balance_initial")
                or gc_assignment.get("two_balance")
                or 0
            )
        except Exception as e:
            print(f"⚠️ [GC_BAL] Ошибка приведения current_two: {e}")
            gc_current_two = 0

        try:
            gc_target_amount = int(gc_assignment.get("target_amount") or 0)
        except Exception as e:
            print(f"⚠️ [GC_BAL] Ошибка приведения target_amount: {e}")
            gc_target_amount = 0

        try:
            reward_amount = int(
                gc_assignment.get("reward_amount")
                or gc_assignment.get("reward")
                or 0
            )
        except Exception as e:
            print(f"⚠️ [GC_BAL] Ошибка приведения reward_amount: {e}")
            reward_amount = 0

        try:
            gc_is_free = await db.gc_active_is_free(owner_id)
        except Exception:
            gc_is_free = False  # подстраховка

        emoji_prefix = "🍻 " if gc_is_free else ""

        if gc_target_amount > 0:
            gc_text = f"{emoji_prefix}Челлендж: {gc_current_two}/{gc_target_amount} кут"
        else:
            gc_text = f"{emoji_prefix}Челлендж: {gc_current_two} кут"

        # ---- 1.1. callback_data в формате, который понимает gc_info_callback ----
        cb_data = f"gc:{owner_id}:{gc_current_two}:{gc_target_amount}:{reward_amount}"

        # Лимит Telegram: 64 байта на callback_data - перестрахуемся
        if len(cb_data.encode("utf-8")) > 64:
            # режем награду до 0, чтобы укоротить строку
            cb_data = f"gc:{owner_id}:{gc_current_two}:{gc_target_amount}:0"
            print(f"⚠️ [GC_BAL] callback_data была длинной, урезали до: {cb_data!r}")

        print(
            "🎮 [GC_BAL] Активный челлендж найден:"
            f" text='{gc_text}', current_two={gc_current_two},"
            f" target={gc_target_amount}, reward={reward_amount}, callback={cb_data!r}"
        )

        gc_button_row = [
            InlineKeyboardButton(
                text=gc_text,
                callback_data=cb_data,
            )
        ]

        # ---- 2. Привязка к группе ----
        target_chat_id = gc_assignment.get("target_chat_id")
        target_chat_ref = gc_assignment.get("target_chat_ref")
        print(
            f"🎯 [GC_GROUP] target_chat_id={target_chat_id!r}, "
            f"target_chat_ref={target_chat_ref!r}"
        )

        in_required_chat = False

        # 2.1. Проверяем по chat_id
        if target_chat_id is not None:
            try:
                tpl_chat_id_int = int(target_chat_id)
                print(
                    f"🎯 [GC_GROUP] Сравниваю chat_id: current={current_chat_id}, "
                    f"required={tpl_chat_id_int}"
                )
                if int(current_chat_id) == tpl_chat_id_int:
                    in_required_chat = True
                    print("🎯 [GC_GROUP] Пользователь УЖЕ в нужной группе (по chat_id).")
                else:
                    print("🎯 [GC_GROUP] chat_id не совпадает, это другая группа.")
            except Exception as e:
                print(
                    f"⚠️ [GC_GROUP] Не удалось привести target_chat_id="
                    f"{target_chat_id!r} к int: {e}"
                )

        # 2.2. Если по id не поняли, проверяем по username
        if not in_required_chat and target_chat_ref and current_chat_username:
            ref = str(target_chat_ref).strip()
            uname_current = str(current_chat_username).lstrip("@").lower()
            uname_required = None

            if ref.startswith("@"):
                uname_required = ref[1:].lower()
            elif "t.me/" in ref:
                try:
                    uname_required = (
                        ref.split("t.me/", 1)[1]
                        .split("/")[0]
                        .lstrip("@")
                        .lower()
                    )
                except Exception:
                    uname_required = None

            print(
                f"🎯 [GC_GROUP] Сравнение по username: current={uname_current!r}, "
                f"required={uname_required!r}"
            )
            if uname_required and uname_current == uname_required:
                in_required_chat = True
                print("🎯 [GC_GROUP] Пользователь УЖЕ в нужной группе (по username).")

        # ---- 3. Строим кнопку статуса/перехода ----
        if in_required_chat:
            gc_group_button = InlineKeyboardButton(
                text="Вы уже в нужной группе",
                callback_data="gc_in_place",  # noop
            )
            print("🎯 [GC_GROUP] Добавляю кнопку 'Вы уже в нужной группе' без URL.")
        else:
            group_url = None
            group_label = "🎯 Группа челленджа"

            # 3.1. сначала target_chat_ref
            if target_chat_ref:
                ref = str(target_chat_ref).strip()
                print(f"🎯 [GC_GROUP] Обрабатываю target_chat_ref={ref!r}")

                if ref.startswith("@"):
                    uname = ref[1:]
                    group_url = f"https://t.me/{uname}"
                    group_label = f"🎯 Играть в @{uname}"
                    print(f"🎯 [GC_GROUP] Построен URL по @username: {group_url}")
                elif "t.me" in ref:
                    if ref.startswith("http://") or ref.startswith("https://"):
                        group_url = ref
                    else:
                        group_url = "https://" + ref.lstrip("/")
                    print(f"🎯 [GC_GROUP] Построен URL по t.me-ссылке: {group_url}")

            # 3.2. если нет URL, пытаемся взять username по chat_id
            if group_url is None and target_chat_id:
                try:
                    cid_int = int(target_chat_id)
                except Exception as e:
                    print(
                        f"⚠️ [GC_GROUP] Не удалось привести target_chat_id="
                        f"{target_chat_id!r} к int: {e}"
                    )
                    cid_int = None

                if cid_int is not None:
                    print(
                        f"🎯 [GC_GROUP] Пробую найти username/ссылку по chat_id={cid_int}"
                    )
                    try:
                        uname = None
                        if hasattr(db, "get_group_username"):
                            uname = await db.get_group_username(cid_int)
                            print(
                                f"🎯 [GC_GROUP] get_group_username({cid_int}) -> {uname!r}"
                            )

                        if uname:
                            group_url = f"https://t.me/{uname}"
                            group_label = f"🎯 Играть в @{uname}"
                            print(
                                f"🎯 [GC_GROUP] Построен URL по usernamechat: {group_url}"
                            )
                        else:
                            print(
                                "🎯 [GC_GROUP] username для чата не найден, "
                                "URL построить не удалось"
                            )
                    except Exception as e:
                        import traceback
                        print(
                            f"❌ [GC_GROUP] Ошибка при получении данных о группе "
                            f"по chat_id={cid_int}: {e}"
                        )
                        print(traceback.format_exc())

            if group_url:
                gc_group_button = InlineKeyboardButton(
                    text=group_label,
                    url=group_url,
                )
                print(
                    f"🎯 [GC_GROUP] Итоговая кнопка перехода в группу: "
                    f"text={group_label!r}, url={group_url!r}"
                )
            else:
                print(
                    "🎯 [GC_GROUP] Группу для челленджа определить не удалось "
                    "(нет username/t.me/ссылки) - кнопку не добавляем."
                )

    except Exception as e:
        import traceback
        print(f"❌ [GC_BAL] Ошибка при построении кнопок по челленджу: {e}")
        print(traceback.format_exc())

    return gc_button_row, gc_group_button





















@dp.callback_query(lambda c: c.data.startswith('balance312512512651action'))
async def send_styles(callback_query: types.CallbackQuery):

    await callback_query.answer("""
💰 Текущий баланс

1 кут = 1 Telegram Stars [ При выводе ]
""",show_alert=True)





def _dbg_gc_simple(*args):
    # Лёгкий дебаг по префиксу, чтобы в логах быстро найти
    print("[GC_SIMPLE_ABORT]", *args)


def _get_balance_owner(message: types.Message) -> Optional[int]:
    """
    Определяем владельца сообщения с балансом / челленджем.
    Ожидаем, что где-то при отправке баланса ты делаешь:
       balance_message_owner[(chat_id, message_id)] = owner_id
    """
    try:
        return balance_message_owner.get((message.chat.id, message.message_id))
    except Exception:
        return None


async def _safe_edit_gc_msg(
    message: types.Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
):
    """
    Безопасное редактирование текста + клавиатуры.
    """
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except (TelegramBadRequest, TelegramAPIError) as e:
        if "message is not modified" in str(e).lower():
            return
        _dbg_gc_simple("Ошибка edit_text:", e)
    except Exception as e:
        _dbg_gc_simple("Неожиданная ошибка edit_text:", e)


# =========================================================
#   ШАГ 1. ОТКРЫТЬ МЕНЮ ЗАВЕРШЕНИЯ ЧЕЛЛЕНДЖА
#   callback_data: cb_gc_abort_menu
# =========================================================

@dp.callback_query(lambda c: c.data == "cb_gc_abort_menu")
async def cb_gc_abort_menu_handler(callback_query: types.CallbackQuery):
    """
    Пользователь нажал кнопку «Завершить челлендж» в блоке баланса.

    Что делаем:
    1. Проверяем, что сообщение принадлежит тому же пользователю.
    2. Проверяем, что у него есть активный челлендж.
    3. Меняем сообщение на:
         💰
         [🌴 Завершить челлендж] (cb_gc_abort_finish)
         [🏕 Назад]             (balance:<owner_id>)
    """
    user_id = callback_query.from_user.id
    msg = callback_query.message
    stop_timer_from_callback(callback_query.message)
    if not msg:
        _dbg_gc_simple("cb_gc_abort_menu: нет message в callback_query")
        return

    chat_id = msg.chat.id
    msg_id = msg.message_id
    _dbg_gc_simple(f"abort_menu: clicker={user_id}, chat_id={chat_id}, msg_id={msg_id}")

    # Гасим "часики" у кнопки
    try:
        await callback_query.answer()
    except Exception:
        pass

    # 1. Определяем владельца баланса по словарю balance_message_owner
    owner_id = _get_balance_owner(msg)
    if owner_id is None:
        # Если по какой-то причине не нашли, логируем и считаем владельцем самого кликера,
        # чтобы не ломать UX (но это аномальный случай, лучше по логам отловить).
        _dbg_gc_simple("cb_gc_abort_menu: owner_id не найден, считаем owner=clicker", user_id)
        owner_id = user_id

    # 2. Разрешаем клик только владельцу
    if user_id != owner_id:
        _dbg_gc_simple(
            f"cb_gc_abort_menu: чужой клик, owner={owner_id}, clicker={user_id}"
        )
        try:
            await callback_query.answer(
                "Это не твой челлендж. Открой свой баланс командой «баланс».",
                show_alert=True,
            )
        except Exception:
            pass
        return

    # 3. Проверяем, что вообще есть активный челлендж
    try:
        assignment = await db.get_active_gc_assignment(owner_id)
        _dbg_gc_simple("cb_gc_abort_menu: assignment из БД ->", assignment)
    except Exception as e:
        _dbg_gc_simple("cb_gc_abort_menu: ошибка get_active_gc_assignment:", e)
        assignment = None

    if not assignment:
        try:
            await callback_query.answer(
                "Сейчас у тебя нет активного игрового челленджа.",
                show_alert=True,
            )
        except Exception:
            pass
        return

    # 4. Собираем клавиатуру (Завершить / Назад)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Завершить челлендж",
                    callback_data="cb_gc_abort_finish", style="default" ,
                    icon_custom_emoji_id="5449372007432985754",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"balance:{owner_id}", style="default" ,
                    icon_custom_emoji_id="5359636199155704118",
                )
            ],
        ]
    )

    # 5. Меняем текст сообщения на «💰»
    await _safe_edit_gc_msg(msg, "<tg-emoji emoji-id='6023728560768818964'>💰</tg-emoji>", reply_markup=kb)
    _dbg_gc_simple("cb_gc_abort_menu: сообщение заменено на 💰 (меню завершения)")


# =========================================================
#   ШАГ 2. ФАКТИЧЕСКОЕ ЗАВЕРШЕНИЕ
#   callback_data: cb_gc_abort_finish
# =========================================================

@dp.callback_query(lambda c: c.data == "cb_gc_abort_finish")
async def cb_gc_abort_finish_handler(callback_query: types.CallbackQuery):
    """
    Пользователь нажал «🌴 Завершить челлендж» в меню.

    Что делаем:
    1. Проверяем, что это владелец.
    2. Вызываем db.cancel_gc_assignment(user_id).
    3. При успехе:
          💰
          [🏕 Вернуться назад] -> balance:<owner_id>
    """
    user_id = callback_query.from_user.id
    msg = callback_query.message

    if not msg:
        _dbg_gc_simple("cb_gc_abort_finish: нет message в callback_query")
        return

    chat_id = msg.chat.id
    msg_id = msg.message_id
    _dbg_gc_simple(f"abort_finish: clicker={user_id}, chat_id={chat_id}, msg_id={msg_id}")

    try:
        await callback_query.answer()
    except Exception:
        pass

    # 1. Определяем владельца по balance_message_owner
    owner_id = _get_balance_owner(msg)
    if owner_id is None:
        _dbg_gc_simple("cb_gc_abort_finish: owner_id не найден, считаем owner=clicker", user_id)
        owner_id = user_id

    # 2. Разрешаем клик только владельцу
    if user_id != owner_id:
        _dbg_gc_simple(
            f"cb_gc_abort_finish: чужой клик, owner={owner_id}, clicker={user_id}"
        )
        try:
            await callback_query.answer(
                "Ты не можешь завершать чужой челлендж.",
                show_alert=True,
            )
        except Exception:
            pass
        return

    # 3. Завершаем челлендж в БД
    ok = False
    try:
        _dbg_gc_simple("cb_gc_abort_finish: вызываем db.cancel_gc_assignment(owner_id)")
        ok = await db.cancel_gc_assignment(owner_id)
        _dbg_gc_simple("cb_gc_abort_finish: cancel_gc_assignment ->", ok)
    except Exception as e:
        _dbg_gc_simple("cb_gc_abort_finish: ошибка cancel_gc_assignment:", e)
        ok = False

    if not ok:
        try:
            await callback_query.answer(
                "Не удалось завершить челлендж. Попробуй ещё раз позже.",
                show_alert=True,
            )
        except Exception:
            pass
        return

    # 4. Успешно завершили: показываем 💰 + кнопку «Вернуться назад»
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏕 Вернуться назад",
                    callback_data=f"balance:{owner_id}",
                )
            ]
        ]
    )
    emoji_id = get_random_emoji_id()
    await _safe_edit_gc_msg(msg, f"<tg-emoji emoji-id='{emoji_id}'>💰</tg-emoji>", reply_markup=kb, parse_mode="HTML")

    try:
        await callback_query.answer(
            "Челлендж завершён. Можешь вернуться к балансу или выбрать новое задание.",
            show_alert=False,
        )
    except Exception:
        pass

    _dbg_gc_simple("cb_gc_abort_finish: челлендж завершён, показана кнопка вернуться назад")


# ============================================================
# 🧠 СИСТЕМА БЕЗОПАСНОГО ТОРМОЖЕНИЯ КЛИКОВ
# ============================================================

BALANCE_SAFE_INTERVAL = 2.0       # минимум секунд между действиями
BALANCE_SAFE_DELAY = 2.2          # реальная задержка (чуть больше)

# user_id -> timestamp последнего ДОПУЩЕННОГО действия
_balance_safe_clock: dict[int, float] = {}

# user_id -> asyncio.Lock
_balance_safe_lock: dict[int, asyncio.Lock] = {}


def _balance_safe_mutex(uid: int) -> asyncio.Lock:
    if uid not in _balance_safe_lock:
        _balance_safe_lock[uid] = asyncio.Lock()
    return _balance_safe_lock[uid]


async def _balance_safe_brake(
    *,
    uid: int,
    callback: types.CallbackQuery
) -> None:
    """
    Гарантирует, что запросы к Telegram
    для одного пользователя идут НЕ ЧАЩЕ 1 раза в 2 секунды
    """
    guard = _balance_safe_mutex(uid)

    async with guard:
        now = time.monotonic()
        last_ok = _balance_safe_clock.get(uid)

        if last_ok is not None:
            elapsed = now - last_ok
            if elapsed < BALANCE_SAFE_INTERVAL:
                wait_for = BALANCE_SAFE_DELAY - elapsed
                if wait_for > 0:
                    await asyncio.sleep(wait_for)

                try:
                    await callback.answer(
                        "⏳ Подожди пару секунд…",
                        show_alert=False
                    )
                except Exception:
                    pass

        _balance_safe_clock[uid] = time.monotonic()


# ============================================================
# 💰 CALLBACK БАЛАНСА (SAFE VERSION)
# ============================================================

def _stop_timer_for_message(chat_id: int, mid: int) -> None:
    """
    ✅ Остановить таймер конкретного сообщения.
    Безопасно вызывать много раз.
    """
    key: BalanceTimerKey = (int(chat_id), int(mid))
    ev = balance_cancel_events.get(key)
    if ev and not ev.is_set():
        ev.set()


# ============================================================
# ✅ CALLBACK: обновить баланс по нажатию на кнопку "balance:..."
#    Полностью рабочий и продуманный вариант:
#    - гасит таймер именно этого сообщения
#    - обновляет UI
#    - запускает НОВЫЙ таймер (если SLEEP)
#    - таймер не перезатирает твои edit_* после нажатий, потому что его можно гасить
# ============================================================
@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("balance:"))
async def cb_balance_refresh(c: types.CallbackQuery):

    # -------- 0) owner_id --------
    try:
        owner_id = int((c.data or "").split(":", 1)[1])
    except Exception:
        try:
            await c.answer("❌ Ошибка данных.", show_alert=True)
        except Exception:
            pass
        return

    # -------- защита: нужен message --------
    if not c.message:
        try:
            await c.answer("❌ Нет сообщения для обновления.", show_alert=True)
        except Exception:
            pass
        return

    # 🔒 только владелец
    if int(c.from_user.id) != int(owner_id):
        try:
            await c.answer("⛔ Это чужой баланс. Открой свой командой «баланс».", show_alert=True)
        except Exception:
            pass
        return

    chat_id = int(c.message.chat.id)
    mid = int(c.message.message_id)
    key: BalanceTimerKey = (chat_id, mid)

    # ✅ 1) Гасим анимацию таймера на ЭТОМ сообщении (если шла)
    _stop_timer_for_message(chat_id, mid)

    # ✅ 2) Доп. страховка: если у тебя есть логика гашения по user_id - оставляем
    #    (например, ты гасишь прошлое "баланс-сообщение" юзера)
    try:
        _stop_prev_balance_timer(owner_id)
    except Exception:
        pass

    # -------- 🧠 ГАРАНТИРОВАННАЯ ЗАДЕРЖКА (как у тебя) --------
    try:
        await _balance_safe_brake(uid=owner_id, callback=c)
    except Exception:
        pass

    # ============================================================
    # 1) БАЛАНС ТОЛЬКО ИЗ БД
    # ============================================================
    try:
        bal_raw = await db.get_user_balance(owner_id)
        user_balance = int(bal_raw or 0)
        print(f"💰 [BALANCE_CB] balance from DB={user_balance}")
    except Exception as e:
        print(f"⚠️ [BALANCE_CB] get_user_balance err: {e!r}")
        try:
            await c.answer("❓", show_alert=True)
        except Exception:
            pass
        return

    # ============================================================
    # 2) ФОРМАТ
    # ============================================================
    try:
        formatted_balance = "{:,.0f}".format(user_balance).replace(",", ".")
    except Exception:
        formatted_balance = str(user_balance)

    # ============================================================
    # 3) ENGINE (статус/таймер/игры) + burned_now
    # ============================================================
    bal_status = BAL_STATUS_ACTIVE
    bal_remaining_to_3 = 0
    sleep_played = 0
    sleep_needed = 10
    burned_now = False

    try:
        st, last_active, elapsed, remaining, played, needed, next_after, burned_now = await db.ensure_balance_status_engine(owner_id)

        bal_status = int(st or BAL_STATUS_ACTIVE)
        bal_remaining_to_3 = int(remaining or 0)
        sleep_played = int(played or 0)
        sleep_needed = int(needed or 10)
        if sleep_needed <= 0:
            sleep_needed = 10

        print(
            f"🧠 [BALANCE_CB][ENGINE] uid={owner_id} st={bal_status} remaining={bal_remaining_to_3}s "
            f"games={sleep_played}/{sleep_needed} burned_now={burned_now} next={next_after}s"
        )
    except Exception as e:
        print(f"❌ [BALANCE_CB][ENGINE] err: {e!r}")
        bal_status = BAL_STATUS_ACTIVE
        bal_remaining_to_3 = 0
        sleep_played = 0
        sleep_needed = 10
        burned_now = False

    # ============================================================
    # ✅ 3.1) СПИСЫВАЕМ ТОЛЬКО ЕСЛИ burned_now=True
    # ============================================================
    if burned_now:
        try:
            removed_amount = await _burn_balance_and_log_once(db, owner_id)
        except Exception as e:
            print(f"⚠️ [BALANCE_CB][BURN] burn err: {e!r}")
            removed_amount = 0

        if removed_amount > 0:
            user_balance = 0
            formatted_balance = "0"

    # ============================================================
    # 4) ЧЕЛЛЕНДЖ
    # ============================================================
    try:
        gc_button_row, gc_group_button = await _build_gc_buttons(
            owner_id=owner_id,
            current_chat_id=chat_id,
            current_chat_username=getattr(c.message.chat, "username", None),
        )
    except Exception as e:
        print(f"❌ [BALANCE_CB] _build_gc_buttons err: {e!r}")
        gc_button_row, gc_group_button = None, None

    # ============================================================
    # 5) КЛАВИАТУРА
    # ============================================================
    kb_rows: List[List[InlineKeyboardButton]] = []

    balance_row_index = len(kb_rows)  # будет 0
    timer_row_index: Optional[int] = None

    try:
        st_int = int(bal_status)
    except Exception:
        st_int = BAL_STATUS_ACTIVE

    # кнопка баланса
    if st_int == BAL_STATUS_SLEEP:
        bal_icon_id = "5767199127775481841"
        bal_style = "default"
    elif st_int == BAL_STATUS_BURNED:
        bal_icon_id = "6028338546736107668"
        bal_style = "danger"
    else:
        bal_icon_id = "6028338546736107668"
        bal_style = "default"

    kb_rows.append([InlineKeyboardButton(
        text=f"{formatted_balance} кут",
        callback_data=f"balance:{owner_id}",
        style=bal_style,
        icon_custom_emoji_id=bal_icon_id
    )])

    # статусные строки
    if st_int == BAL_STATUS_SLEEP:
        remain = int(bal_remaining_to_3 or 0)
        timer_text = f"{_fmt_wait_smart(remain)}"

        timer_row_index = len(kb_rows)
        kb_rows.append([InlineKeyboardButton(
            text=timer_text,
            callback_data=f"bal_timer:{owner_id}",
            style="default",
            icon_custom_emoji_id="5294098794969849195"
        )])

        prog_text = f"{int(sleep_played)}/{int(sleep_needed)} игр до восстановления"
        kb_rows.append([InlineKeyboardButton(
            text=prog_text,
            callback_data=f"bal_sleep_games:{owner_id}",
            style="default",
            icon_custom_emoji_id="5359595190807962128"
        )])

    elif st_int == BAL_STATUS_BURNED:
        kb_rows.append([InlineKeyboardButton(
            text="Сгоревший баланс",
            callback_data=f"bal_timer:{owner_id}",
            style="default",
            icon_custom_emoji_id="5193209459136045172"
        )])

    # челлендж
    if gc_button_row:
        kb_rows.append(gc_button_row)

    if gc_group_button:
        kb_rows.append([gc_group_button])

    if gc_button_row:
        kb_rows.append([InlineKeyboardButton(
            text="Завершить задание",
            callback_data="cb_gc_abort_menu",
            style="default",
            icon_custom_emoji_id="5449372007432985754"
        )])

    kb_rows.append([
        InlineKeyboardButton(
            text="Вывод",
            callback_data="speedwithdrawal",
            style="default",
            icon_custom_emoji_id="5188322825735267247"
        ),
        InlineKeyboardButton(
            text="Донат",
            callback_data=f"donate_info:{owner_id}",
            style="default",
            icon_custom_emoji_id="5318892863780579996"
        )
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    # ============================================================
    # 6) ОБНОВЛЕНИЕ СООБЩЕНИЯ (SAFE)
    # ============================================================
    try:
        emoji_id = get_random_emoji_id()
        await c.message.edit_text(
            f"<tg-emoji emoji-id='{emoji_id}'>💰</tg-emoji>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=kb
        )
        balance_message_owner[(chat_id, mid)] = owner_id
        print(f"💰 [BALANCE_CB] refreshed owner_id={owner_id} key={key}")
    except Exception as e:
        print(f"⚠️ [BALANCE_CB] edit_text err: {e!r}")
        try:
            await c.answer("⚠️ Не удалось обновить баланс.", show_alert=True)
        except Exception:
            pass
        return

    # ============================================================
    # 7) ✅ ДВИЖУЩИЙСЯ ТАЙМЕР 10 СЕК (только для SLEEP)
    #    ВАЖНО: запускаем ТОЛЬКО если статус SLEEP.
    #    Отмена через Event: _stop_timer_for_message(chat_id, mid)
    # ============================================================
    try:
        if st_int == BAL_STATUS_SLEEP and timer_row_index is not None:
            # создаём НОВЫЙ event отмены (старый уже set() в начале)
            cancel_event = asyncio.Event()
            balance_cancel_events[key] = cancel_event

            remain_start = int(bal_remaining_to_3 or 0)
            start_ts = time.time()

            last_timer_text = None
            TICKS = 10

            print(f"🟠 [BALANCE_CB][TIMER] start uid={owner_id} key={key} remain_start={remain_start}s ticks={TICKS}")

            for i in range(TICKS):
                await asyncio.sleep(1)

                if cancel_event.is_set():
                    print(f"🛑 [BALANCE_CB][TIMER] canceled uid={owner_id} key={key} tick={i+1}/{TICKS}")
                    break

                passed = int(time.time() - start_ts)
                remain_now = max(0, remain_start - passed)

                # дошли до 0 -> обновляем UI + списание ТОЛЬКО если burned_now=True
                if remain_now <= 0:
                    burned_now2 = False
                    try:
                        st2, _, _, _, _, _, _, burned_now2 = await db.ensure_balance_status_engine(owner_id)
                        st2 = int(st2 or BAL_STATUS_ACTIVE)
                    except Exception as e:
                        print(f"⚠️ [BALANCE_CB][TIMER] engine-on-zero err: {e!r}")
                        st2 = BAL_STATUS_BURNED

                    removed_amount = 0
                    if burned_now2:
                        try:
                            removed_amount = await _burn_balance_and_log_once(db, owner_id)
                        except Exception as e:
                            print(f"⚠️ [BALANCE_CB][TIMER] burn err: {e!r}")
                            removed_amount = 0

                    kb_rows[timer_row_index] = [InlineKeyboardButton(
                        text="Сгоревший баланс",
                        callback_data=f"bal_timer:{owner_id}",
                        style="default",
                        icon_custom_emoji_id="5193209459136045172"
                    )]

                    if removed_amount > 0:
                        bal_txt = "0 кут"
                    else:
                        try:
                            bn = int(await db.get_user_balance(owner_id) or 0)
                        except Exception:
                            bn = 0
                        try:
                            bal_txt = "{:,.0f}".format(bn).replace(",", ".") + " кут"
                        except Exception:
                            bal_txt = f"{bn} кут"

                    kb_rows[balance_row_index] = [InlineKeyboardButton(
                        text=bal_txt,
                        callback_data=f"balance:{owner_id}",
                        style="danger",
                        icon_custom_emoji_id="6028338546736107668"
                    )]

                    kb_new = InlineKeyboardMarkup(inline_keyboard=kb_rows)
                    try:
                        if not cancel_event.is_set():
                            await c.message.edit_reply_markup(reply_markup=kb_new)
                    except Exception:
                        pass

                    print(f"🔥 [BALANCE_CB][TIMER] reached 0 burned_now={burned_now2} removed={removed_amount} uid={owner_id} key={key}")
                    break

                # обычное обновление таймера
                new_timer_text = f"{_fmt_wait_smart(remain_now)}"
                if new_timer_text != last_timer_text:
                    kb_rows[timer_row_index] = [InlineKeyboardButton(
                        text=new_timer_text,
                        callback_data=f"bal_timer:{owner_id}",
                        style="default",
                        icon_custom_emoji_id="5294098794969849195"
                    )]
                    kb_new = InlineKeyboardMarkup(inline_keyboard=kb_rows)
                    try:
                        if not cancel_event.is_set():
                            await c.message.edit_reply_markup(reply_markup=kb_new)
                    except Exception:
                        pass
                    last_timer_text = new_timer_text

            # подчистим event (если он всё ещё наш текущий)
            ev_now = balance_cancel_events.get(key)
            if ev_now is cancel_event:
                balance_cancel_events.pop(key, None)

            print(f"🟠 [BALANCE_CB][TIMER] done uid={owner_id} key={key}")

    except Exception as e:
        print(f"⚠️ [BALANCE_CB][TIMER] err: {e!r}")







@dp.callback_query(lambda c: c.data == "balanceashudjwqkdq")
async def cb_back_legacy(c: types.CallbackQuery):
    await c.answer()
    # Пытаемся найти owner_id по маппингу сообщения
    owner_id = balance_message_owner.get((c.message.chat.id, c.message.message_id))
    if owner_id is None:
        owner_id = c.from_user.id  # запасной вариант

    # Проксируем на обычный обработчик баланса
    c.data = f"balance:{owner_id}"
    await cb_balance_refresh(c)





















#@dp.message()
#async def balance(message: Message):
    #if message.text.lower() in [ "б" , "баланс" , "💸 баланс" ]:
        #user_id = message.from_user.id

        # Получаем все необходимые данные за один запрос
        #user_data = await db.get_user_balance_and_assets(
            #user_id)  # запрос на получение всех данных о пользователе за один раз

        #user_balance , user_cutecoins , user_cutenin , balance2 , balance3 = user_data  # unpacking всех данных  #
        # Форматируем баланс пользователя
        #formatted_balance = "{:,.0f}".format(user_balance).replace("," , ".")

        # Список случайных сообщений
        #asdiajsadasds = random.choice(
            #[ "💸 Как дела?" , "🚀 Какие новости?" , "📈 Уже заработали кут?" , "💰 Кто-то сп***ил мои куты?" ,
                #"🎯 Вы уже играли в личных сообщениях?" , "⚡ У вас так много кут.." , "🔒 Это замок" ,
                #"🛠️ Сегодня будешь фармить куты?" , "📊 Как куты? Уже возвращаются?" ,
                #"💡 Какие стратегии для кутов вам нравятся больше?" , "🎩 Как вы планируете тратить свои куты?" ,
                #"💰 У вас всё с ними в порядке?" , "🕵️‍♂️ Уже накопили куты или ещё в процессе?" ,
                #"🌱 Ваш баланс изменился?" , "🛒 Куты уже готовы к покупкам?" ,
                #"💎 Как куты? Не перепутали ли их с драгоценностями?" , "🤠 Чисто по приколу." ,
                #"🎩 Вы знали что кут был создан одним человеком?" ,
                #"🎩 Используя 'шайн' можно получить какой-то предмет)" , "😎 это я усё украл" ,
                #"🎮 Мне нравится Лера, она играет в мои игры" , "😮 Вот это да, я поражен" ,
                #"📅 Как идёт накопление кутов? Сегодня был успех?" , "💰 Сколько кут вам нужно для счастья?" ,
                #"💼 На что их потратите?" , "🏅 Что делали сегодня?" , "💡 Как день?" , "⚡ Как настроение?" ])

        # Формируем ответное сообщение
        #reply_message = f'💰 <b>Ваш баланс ~ {formatted_balance} кут</b>'
        #if random.randint(1 , 100) > 95:
            #reply_message += f'\n\n<b>{asdiajsadasds}</b>'

        #if user_cutecoins > 0:
            #formatted_cutecoins = "{:,.0f}".format(user_cutecoins).replace("," , ".")
            #reply_message += f'\n💠 Ктк ~ {formatted_cutecoins}'

        #if user_cutenin > 0:
            #formatted_cutenin = "{:,.0f}".format(user_cutenin).replace("," , ".")
            #reply_message += f'\n🧬 Кутенин ~ {formatted_cutenin}'

        # Если есть данные о хранилище
        #if balance2 != 0 or balance3 != 0:
            #reply_message += "\n\n"
            #if balance2 != 0:
                #formatted_balance2 = "{:,.0f}".format(balance2).replace("," , ".")
                #reply_message += f'💰 Хранилище:\n💵 {formatted_balance2} кут'
            #if balance3 != 0:
                #if balance2 != 0:
                    #reply_message += "\n"
                #formatted_balance3 = "{:,.0f}".format(balance3).replace("," , ".")
                #reply_message += f'💎 {formatted_balance3} ктк'

        # Отправляем сообщение
        #await message.reply(reply_message , parse_mode="HTML" , disable_web_page_preview=True)



@dp.callback_query(F.data.startswith("gc:"))
async def gc_info_callback(callback_query: types.CallbackQuery):
    """
    Формат callback_data: gc:<user_id>:<cur>:<target>:<reward>

    Пример: "gc:6801702632:120:200:1000"

    Показываем краткую сводку по челленджу через callback_query.answer(show_alert=True),
    стараясь уложиться в MAX_GC_ALERT_LEN символов.
    """
    data = callback_query.data or ""
    clicker_id = callback_query.from_user.id

    print(f"🎮 [GC_INFO] Входящий callback: {data!r} от user_id={clicker_id}")

    # ---------- 1. Разбор callback_data ----------
    parts = data.split(":")

    if len(parts) < 2:
        # Совсем сломанный формат, даже нет префикса / user_id
        print(f"⚠️ [GC_INFO] Слишком мало частей в callback_data={data!r}: len={len(parts)}")
        await callback_query.answer(
            "⚠️ Не удалось прочитать данные челленджа.",
            show_alert=True,
        )
        return

    prefix = parts[0]

    if prefix != "gc":
        # На всякий случай: фильтр поймал, но префикс не тот
        print(f"⚠️ [GC_INFO] Неизвестный prefix={prefix!r} в callback_data={data!r}")
        await callback_query.answer(
            "⚠️ Формат данных челленджа не распознан.",
            show_alert=True,
        )
        return

    if len(parts) < 5:
        # Ожидаем минимум: gc:<user_id>:<cur>:<target>:<reward>
        print(f"⚠️ [GC_INFO] Недостаточно данных в callback_data={data!r}, parts={parts}")
        await callback_query.answer(
            "⚠️ Недостаточно данных по челленджу.",
            show_alert=True,
        )
        return

    uid_str, cur_str, targ_str, rew_str = parts[1:5]

    # ---------- 2. Проверяем, что это именно владелец челленджа ----------
    real_user_id = callback_query.from_user.id
    if str(real_user_id) != uid_str:
        print(
            f"⚠️ [GC_INFO] user_id={real_user_id} пытается открыть задание uid={uid_str} - запрещаем."
        )
        await callback_query.answer(
            "Это не ваш челлендж.\n"
            "Возьмите свой челлендж в личных сообщениях с ботом.",
            show_alert=True,
        )
        return

    # ---------- 3. Пробуем привести числа ----------
    def _safe_int(v: str, default: int = 0, label: str = "") -> int:
        try:
            return int(v)
        except Exception as e:
            if label:
                print(f"⚠️ [GC_INFO] Ошибка приведения {label}={v!r} к int: {e}")
            return default

    cur = _safe_int(cur_str, 0, "cur")
    targ = _safe_int(targ_str, 0, "target")
    rew = _safe_int(rew_str, 0, "reward")

    # ---------- 4. Строим краткий текст ----------
    # Держим формат максимально компактным, но понятным
    lines = []

    # заголовок
    lines.append("🎮 Ваш челлендж")

    # баланс / цель
    if targ > 0:
        # можно посчитать, сколько осталось
        remaining = max(0, targ - cur)
        try:
            progress_pct = max(0, min(999, int(round((cur / targ) * 100))))
        except Exception:
            progress_pct = None

        if progress_pct is not None:
            lines.append(f"Баланс: {cur}/{targ} кут (осталось {remaining}, {progress_pct}%)")
        else:
            lines.append(f"Баланс: {cur}/{targ} кут")
    else:
        lines.append(f"Баланс: {cur} кут")

    # награда
    if rew > 0:
        lines.append(f"Награда: {rew} кут")

    text = "\n".join(lines)

    # ---------- 5. Контроль длины (жёсткий лимит) ----------
    if len(text) > MAX_GC_ALERT_LEN:
        print(
            f"⚠️ [GC_INFO] Текст ({len(text)} симв.) превышает лимит {MAX_GC_ALERT_LEN}, "
            f"делаем ещё короче."
        )
        # супер-компактная версия
        # например: "Челлендж: 100/200, награда 1000"
        short_parts = []
        if targ > 0:
            short_parts.append(f"{cur}/{targ}")
        else:
            short_parts.append(str(cur))

        if rew > 0:
            short_parts.append(f"+{rew}")

        short_core = ", ".join(short_parts)
        text = f"Челлендж: {short_core}"
        # подстрахуемся ещё раз
        if len(text) > MAX_GC_ALERT_LEN:
            text = text[: MAX_GC_ALERT_LEN - 1] + "…"

    print(f"🎮 [GC_INFO] Итоговый текст alert ({len(text)} симв.): {text!r}")

    # ---------- 6. Отправляем alert ----------
    await callback_query.answer(text, show_alert=True)





# ============================================================
# ✅ CALLBACK: кнопка таймера/сгоревшего баланса (bal_timer:<owner_id>)
# ============================================================
# ============================================================
# ✅ CALLBACK: кнопка таймера/сгоревшего баланса (bal_timer:<owner_id>)
# ============================================================
def _parse_owner_id(cb_data: str, prefix: str) -> int:
    """
    Жёстко парсим owner_id из callback_data вида: f"{prefix}:{owner_id}"
    """
    if not isinstance(cb_data, str) or not cb_data.startswith(prefix):
        raise ValueError("bad callback prefix")
    parts = cb_data.split(":", 1)
    if len(parts) != 2:
        raise ValueError("bad callback format")
    return int(parts[1])


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("bal_timer:"))
async def cb_balance_timer_info(c: types.CallbackQuery):
    # 1) owner_id из callback_data
    try:
        owner_id = _parse_owner_id(c.data, "bal_timer")
    except Exception:
        await c.answer("❌ Ошибка данных кнопки.", show_alert=True)
        return

    # 2) только владелец
    if int(c.from_user.id) != int(owner_id):
        await c.answer("⛔ Это кнопка таймера чужого баланса.", show_alert=True)
        return

    # 3) подтягиваем статус/таймер/прогресс заново через ENGINE
    try:
        # engine возвращает:
        # (status, last_active, elapsed_sec, remaining_to_3_sec, played_games, needed_games, next_after, burned_now)
        st, last_active, elapsed, remaining_to_3, played, needed, next_after, burned_now = await db.ensure_balance_status_engine(owner_id)
        bal_status = int(st or BAL_STATUS_ACTIVE)
    except Exception as e:
        await c.answer(f"❌ Ошибка статуса: {e!r}", show_alert=True)
        return

    # 4) тексты (без HTML - callback answer не рендерит теги)
    if bal_status == BAL_STATUS_ACTIVE:
        msg = (
            "🟢 Кошелёк активен\n\n"
            "✅ Баланс в нормальном режиме.\n"
            "🎮 Активность засчитывается, когда ты играешь на ставку.\n\n"
            "💡 Если долго не играть - кошелёк перейдёт в спящий режим."
        )
        await c.answer(msg, show_alert=True)
        return

    if bal_status == BAL_STATUS_SLEEP:
        remain = int(remaining_to_3 or 0)

        # тут можно поставить твой красивый формат
        # timer_txt = _fmt_d_h_s(remain)
        timer_txt = _fmt_wait_smart(remain)  # если ты уже используешь smart-формат

        played_i = int(played or 0)
        needed_i = int(needed or 10)
        if needed_i <= 0:
            needed_i = 10

        left = max(0, needed_i - played_i)

        msg = (
            "🟠 Кошелёк в спящем режиме\n\n"
            f"⏳ До сгорания: {timer_txt}\n"
            f"🎮 Для восстановления: {played_i}/{needed_i} игр (осталось {left})\n\n"
            "💡 Победа/поражение не важно - главное доигрывать игры на ставку."
        )
        await c.answer(msg, show_alert=True)
        return

    if bal_status == BAL_STATUS_BURNED:
        msg = (
            "🔥 Баланс сгорел\n\n"
            "Кошелёк был слишком долго без экономической активности.\n\n"
            "💡 Если тебе начислили деньги после сгорания - они остаются.\n"
        )
        await c.answer(msg, show_alert=True)
        return

    await c.answer("❓ Неизвестный статус кошелька.", show_alert=True)


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("bal_sleep_games:"))
async def cb_bal_sleep_games(c: types.CallbackQuery):
    try:
        owner_id = _parse_owner_id(c.data, "bal_sleep_games")
    except Exception:
        await c.answer("❌ Ошибка данных кнопки.", show_alert=True)
        return

    if int(c.from_user.id) != int(owner_id):
        await c.answer("⛔ Это кнопка чужого баланса.", show_alert=True)
        return

    # Подтянем актуальный прогресс (чтобы показывать реальные цифры)
    try:
        st, last_active, elapsed, remaining_to_3, played, needed, next_after, burned_now = await db.ensure_balance_status_engine(owner_id)
        bal_status = int(st or BAL_STATUS_ACTIVE)
        played_i = int(played or 0)
        needed_i = int(needed or 10)
        if needed_i <= 0:
            needed_i = 10
    except Exception:
        bal_status = BAL_STATUS_ACTIVE
        played_i = 0
        needed_i = 10

    if bal_status != BAL_STATUS_SLEEP:
        await c.answer("🟢 Сейчас кошелёк не в спящем режиме.", show_alert=True)
        return

    left = max(0, needed_i - played_i)

    await c.answer(
        "🎮 Восстановление кошелька\n\n"
        f"Прогресс : {played_i}/{needed_i}\n"
        f"Осталось сыграть : {left} игру \n\n"
        "Победа/поражение не важно - важен факт сыгранной игры.",
        show_alert=True
    )



# ============================================================
# ✅ CALLBACK: RESET GIFT MENU EMOJI TO BASE
# ============================================================
# ============================================================
# ✅ CALLBACK: RESET GIFT MENU EMOJI TO BASE
# ============================================================
@dp.callback_query(lambda c: c.data and c.data.startswith("giftmenureset:"))
async def gift_menu_reset_emoji_callback(call: types.CallbackQuery):
    try:
        await call.answer()

        raw = str(call.data or "")
        parts = raw.split(":", 1)

        if len(parts) != 2:
            await call.answer("Некорректные данные", show_alert=True)
            return

        gift_id = str(parts[1] or "").strip()
        if not gift_id:
            await call.answer("Gift ID не найден", show_alert=True)
            return

        ok = await reset_gift_menu_emoji_override(gift_id)
        if not ok:
            await call.answer("Не удалось вернуть базовое эмодзи", show_alert=True)
            return

        kb = build_gift_menu_control_kb(gift_id)

        text = (
            "<b>Базовое эмодзи для подарка восстановлено.</b>\n\n"
            f"<b>Gift ID:</b> <code>{gift_id}</code>"
        )

        try:
            await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await call.message.answer(text, parse_mode="HTML", reply_markup=kb)

    except Exception as e:
        print(f"🟥 [GIFT_MENU_RESET][ERROR] {e!r}")
        try:
            await call.answer("Ошибка при возврате базового эмодзи", show_alert=True)
        except Exception:
            pass

# ============================================================
# ✅ GIFT MENU EMOJI ADMIN
# ============================================================



def _gift_ids_escape(v) -> str:
    try:
        return html.escape(str(v or ""))
    except Exception:
        return ""


def _gift_ids_to_int_safe(v, default: int = 0) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, str):
            vv = v.strip().replace(" ", "").replace(".", "")
            if not vv:
                return default
            return int(float(vv))
        return int(v)
    except Exception:
        return default


def _gift_ids_fmt_dot(v) -> str:
    try:
        return "{:,.0f}".format(int(_gift_ids_to_int_safe(v, 0))).replace(",", ".")
    except Exception:
        return "0"

def _gift_local_escape(text: Any) -> str:
    try:
        return html.escape(str(text or ""))
    except Exception:
        return ""
async def _build_gift_ids_text(bot1) -> str:
    try:
        gifts = await get_available_gifts_fast(bot1)
    except Exception as e:
        print(f"[GIFT_IDS][ERROR] get_available_gifts_fast err={e!r}")
        return "<b>Не удалось получить список доступных подарков.</b>"

    if not gifts:
        return "<b>Список подарков пуст.</b>"

    rows = []
    total = 0

    for gift in gifts:
        try:
            gift_id = str(getattr(gift, "id", "") or "").strip()
            if not gift_id:
                continue

            emoji = str(getattr(getattr(gift, "sticker", None), "emoji", "🎁") or "🎁")
            star_count = _gift_local_to_int_safe(getattr(gift, "star_count", 0), 0)
            upgrade_raw = getattr(gift, "upgrade_star_count", None)
            has_upgrade = upgrade_raw is not None

            price_text = _gift_local_fmt_dot(star_count)
            nft_text = " [ NFT ]" if has_upgrade else ""

            rows.append(
                f"{_gift_local_escape(emoji)} <code>{_gift_local_escape(gift_id)}</code> - <b>{price_text}</b>{_gift_local_escape(nft_text)}"
            )
            total += 1
        except Exception as e:
            print(f"[GIFT_IDS][ROW][ERROR] err={e!r}")

    if not rows:
        return "<b>Не удалось собрать список идентификаторов подарков.</b>"

    text = (
        "<b>Список доступных идентификаторов подарков</b>\n\n"
        + "\n".join(rows)
        + f"\n\n<b>Всего:</b> <code>{total}</code>"
    )

    if len(text) > 3900:
        short_rows = rows[:80]
        text = (
            "<b>Список доступных идентификаторов подарков</b>\n"
            "<i>Показана первая часть списка.</i>\n\n"
            + "\n".join(short_rows)
            + f"\n\n<b>Всего найдено:</b> <code>{total}</code>"
        )

    return text


# ============================================================
# ✅ CALLBACK: SHOW ALL AVAILABLE GIFT IDS
# ============================================================
@dp.callback_query(lambda c: c.data and c.data == build_gift_menu_ids_callback())
async def gift_menu_ids_list_callback(call: types.CallbackQuery):
    try:
        await call.answer()

        text = await _build_gift_ids_text(bot1)

        try:
            await call.message.edit_text(
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await call.answer("⚠️ Уже актуально", show_alert=False)
                return

            await call.message.answer(
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            await call.message.answer(
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

    except Exception as e:
        print(f"🟥 [GIFT_MENU_IDS][ERROR] {e!r}")
        try:
            await call.answer("Ошибка загрузки списка идентификаторов", show_alert=True)
        except Exception:
            pass


# ============================================================
# ✅ CALLBACK: DELETE MANUAL GIFT
# ============================================================
@dp.callback_query(lambda c: c.data and c.data.startswith("giftmenudelete:"))
async def gift_menu_delete_gift_callback(call: types.CallbackQuery):
    try:
        await call.answer()

        raw = str(call.data or "")
        parts = raw.split(":", 1)

        if len(parts) != 2:
            await call.answer("Некорректные данные", show_alert=True)
            return

        gift_id = str(parts[1] or "").strip()
        if not gift_id:
            await call.answer("Gift ID не найден", show_alert=True)
            return

        ok = await remove_manual_gift(gift_id)
        if not ok:
            await call.answer("Не удалось удалить подарок", show_alert=True)
            return

        text = (
            "<b>Подарок удалён из ручного списка меню.</b>\n\n"
            f"<b>Gift ID:</b> <code>{gift_id}</code>"
        )

        try:
            await call.message.edit_text(text, parse_mode="HTML")
        except Exception:
            await call.message.answer(text, parse_mode="HTML")

    except Exception as e:
        print(f"🟥 [GIFT_MENU_DELETE][ERROR] {e!r}")
        try:
            await call.answer("Ошибка при удалении подарка", show_alert=True)
        except Exception:
            pass