from main import *







emojis = [ "<tg-emoji emoji-id='5472030678633684592'>💸</tg-emoji>" , "<tg-emoji emoji-id='5409048419211682843'>💵</tg-emoji>" , "<tg-emoji emoji-id='5397915559037785261'>🧸</tg-emoji>" , "<tg-emoji emoji-id='5395325195542078574'>🍀</tg-emoji>" , "<tg-emoji emoji-id='5472146462362048818'>💡</tg-emoji>" , "<tg-emoji emoji-id='5458799228719472718'>🌟</tg-emoji>" , "<tg-emoji emoji-id='5445284980978621387'>🚀</tg-emoji>" , "<tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji>" , "<tg-emoji emoji-id='5471952986970267163'>💎</tg-emoji>" , "<tg-emoji emoji-id='5435933711893797296'>🎊</tg-emoji>"  , "<tg-emoji emoji-id='5361837567463399422'>🔮</tg-emoji>" ]

async def create_user_link(user_id: int, first_name: str, username: str = None) -> str:
    """Создает ссылку на профиль пользователя."""
    if username:
        # Если есть username, создаем гиперссылку с именем
        user_hyperlink = f"<a href='https://t.me/{html.escape(username)}'>{html.escape(first_name)}</a>"
    elif first_name:
        # Если username нет, используем имя без ссылки
        user_hyperlink = html.escape(first_name)
    else:
        # Если отсутствуют и имя, и username
        return "У пользователя нет имени."
    return user_hyperlink

async def generate_buttons_marry(page_number, num_pages):
    navigation_buttons123 = []

    if page_number == 1 and num_pages > 1:
        navigation_buttons123.append(
            types.InlineKeyboardButton(text="🔜 Вперед", callback_data=f"next_pagemarry_{page_number + 1}")
        )
    elif page_number == num_pages and num_pages > 1:
        navigation_buttons123.append(
            types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"prev_pagemarry_{page_number - 1}")
        )
    else:
        row_buttons = []
        if page_number > 1:
            row_buttons.append(types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"prev_pagemarry_{page_number - 1}"))
        if page_number < num_pages:
            row_buttons.append(types.InlineKeyboardButton(text="🔜 Вперед", callback_data=f"next_pagemarry_{page_number + 1}"))
        navigation_buttons123.extend(row_buttons)

    return navigation_buttons123

async def generate_buttons_marryxp(page_number, num_pages):
    navigation_buttons = []

    if page_number == 1 and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔜 Вперед", callback_data=f"next_pagemarryxp_{page_number + 1}")
        )
    elif page_number == num_pages and num_pages > 1:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"prev_pagemarryxp_{page_number - 1}")
        )
    else:
        row_buttons = []
        if page_number > 1:
            row_buttons.append(types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"prev_pagemarryxp_{page_number - 1}"))
        if page_number < num_pages:
            row_buttons.append(types.InlineKeyboardButton(text="🔜 Вперед", callback_data=f"next_pagemarryxp_{page_number + 1}"))
        navigation_buttons.extend(row_buttons)

    return navigation_buttons

# Часовой пояс
# =========================================================
# ВКЛ / ВЫКЛ ОТЛАДКИ
# =========================================================
DEBUG_TOP_SYSTEM = False

def top_debug_print(text: str):
    if DEBUG_TOP_SYSTEM:
        try:
            print(text , flush=True)
        except Exception:
            pass

# =========================================================
# БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ЧАСОВОГО ПОЯСА
# =========================================================
def get_bot_timezone():
    try:
        tz = ZoneInfo("Europe/Oslo")
        top_debug_print("✅ [ТОП][TZ] Успешно загружен ZoneInfo('Europe/Oslo')")
        return tz
    except Exception as e:
        top_debug_print(f"❌ [ТОП][TZ] Ошибка ZoneInfo('Europe/Oslo'): {e}")
        top_debug_print("🛟 [ТОП][TZ] Использую fallback UTC+1")

        # Fallback: фиксированный UTC+1
        # Это не учитывает летнее/зимнее время, но код будет работать всегда.
        return timezone(timedelta(hours=1))

BOT_TIMEZONE = get_bot_timezone()

# =========================================================
# ЭМОДЗИ МЕСЯЦЕВ
# =========================================================
MONTH_EMOJI_MAP = {"jan": "<tg-emoji emoji-id='5249107092693870559'>🗓</tg-emoji>" ,
    "feb": "<tg-emoji emoji-id='5249437538887692147'>🗓</tg-emoji>" ,
    "mar": "<tg-emoji emoji-id='5247185597340087202'>🗓</tg-emoji>" ,
    "apr": "<tg-emoji emoji-id='5249434257532676259'>🗓</tg-emoji>" ,
    "may": "<tg-emoji emoji-id='5249393975034407291'>🗓</tg-emoji>" ,
    "jun": "<tg-emoji emoji-id='5247099345806848274'>🗓</tg-emoji>" ,
    "jul": "<tg-emoji emoji-id='5249423580243978202'>🗓</tg-emoji>" ,
    "aug": "<tg-emoji emoji-id='5249033210666448158'>🗓</tg-emoji>" ,
    "sep": "<tg-emoji emoji-id='5247154372927844857'>🗓</tg-emoji>" ,
    "oct": "<tg-emoji emoji-id='5249331363001168909'>🗓</tg-emoji>" ,
    "nov": "<tg-emoji emoji-id='5249233098444399524'>🗓</tg-emoji>" ,
    "dec": "<tg-emoji emoji-id='5249354560119529814'>🗓</tg-emoji>" , }

# =========================================================
# ЭМОДЗИ ДНЕЙ НЕДЕЛИ
# Monday = 0 ... Sunday = 6
# =========================================================
WEEKDAY_EMOJI_MAP = {"sun": "<tg-emoji emoji-id='5247176161296936233'>🗓</tg-emoji>" ,
    "mon": "<tg-emoji emoji-id='5246702099986672703'>🗓</tg-emoji>" ,
    "tue": "<tg-emoji emoji-id='5249111482150450380'>🗓</tg-emoji>" ,
    "wed": "<tg-emoji emoji-id='5249499751488974694'>🗓</tg-emoji>" ,
    "thu": "<tg-emoji emoji-id='5246849949940871272'>🗓</tg-emoji>" ,
    "fri": "<tg-emoji emoji-id='5249031978010830138'>🗓</tg-emoji>" ,
    "sat": "<tg-emoji emoji-id='5249137234774351490'>🗓</tg-emoji>" , }

DEFAULT_TOP_EMOJI = "<tg-emoji emoji-id='5249298854393701472'>🗓</tg-emoji>"

MONTH_NUMBER_TO_KEY = {1: "jan" , 2: "feb" , 3: "mar" , 4: "apr" , 5: "may" , 6: "jun" , 7: "jul" , 8: "aug" ,
    9: "sep" , 10: "oct" , 11: "nov" , 12: "dec" , }

WEEKDAY_NUMBER_TO_KEY = {0: "mon" , 1: "tue" , 2: "wed" , 3: "thu" , 4: "fri" , 5: "sat" , 6: "sun" , }

def get_current_month_key(now: Optional [ datetime ] = None) -> str:
    try:
        if now is None:
            now = datetime.now(BOT_TIMEZONE)

        month_number = now.month
        month_key = MONTH_NUMBER_TO_KEY.get(month_number , "jan")

        top_debug_print(f"📅 [ТОП][МЕСЯЦ] Текущий номер месяца: {month_number}")
        top_debug_print(f"📅 [ТОП][МЕСЯЦ] Определён ключ месяца: {month_key}")

        return month_key
    except Exception as e:
        top_debug_print(f"❌ [ТОП][МЕСЯЦ] Ошибка get_current_month_key: {e}")
        return "jan"

def get_current_weekday_key(now: Optional [ datetime ] = None) -> str:
    try:
        if now is None:
            now = datetime.now(BOT_TIMEZONE)

        weekday_number = now.weekday()
        weekday_key = WEEKDAY_NUMBER_TO_KEY.get(weekday_number , "mon")

        top_debug_print(f"🗓 [ТОП][ДЕНЬ] Текущий номер дня недели: {weekday_number}")
        top_debug_print(f"🗓 [ТОП][ДЕНЬ] Определён ключ дня недели: {weekday_key}")

        return weekday_key
    except Exception as e:
        top_debug_print(f"❌ [ТОП][ДЕНЬ] Ошибка get_current_weekday_key: {e}")
        return "mon"

def get_random_top_calendar_emoji() -> str:
    try:
        now = datetime.now(BOT_TIMEZONE)

        top_debug_print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        top_debug_print(f"🕒 [ТОП] Текущее время: {now.isoformat()}")

        show_mode = random.choice([ "month" , "weekday" ])
        top_debug_print(f"🎲 [ТОП] Случайно выбран режим показа: {show_mode}")

        if show_mode == "month":
            month_key = get_current_month_key(now)
            result_emoji = MONTH_EMOJI_MAP.get(month_key , DEFAULT_TOP_EMOJI)

            top_debug_print(f"📦 [ТОП] Код собирается отправить месяц: {month_key}")
            top_debug_print(f"🏷 [ТОП] HTML эмодзи месяца: {result_emoji}")
            top_debug_print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            return result_emoji

        weekday_key = get_current_weekday_key(now)
        result_emoji = WEEKDAY_EMOJI_MAP.get(weekday_key , DEFAULT_TOP_EMOJI)

        top_debug_print(f"📦 [ТОП] Код собирается отправить день недели: {weekday_key}")
        top_debug_print(f"🏷 [ТОП] HTML эмодзи дня недели: {result_emoji}")
        top_debug_print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return result_emoji

    except Exception as e:
        top_debug_print(f"❌ [ТОП] Ошибка в get_random_top_calendar_emoji: {e}")
        top_debug_print(f"🛟 [ТОП] Будет использован fallback: {DEFAULT_TOP_EMOJI}")
        return DEFAULT_TOP_EMOJI

def _top_save_store(store , store_name: str):
    try:
        if hasattr(store , "save") and callable(store.save):
            store.save()
            top_debug_print(f"💾 [ТОП] {store_name}.save() выполнен")
        else:
            top_debug_print(f"ℹ️ [ТОП] У {store_name} нет метода save()")
    except Exception as e:
        top_debug_print(f"❌ [ТОП] Ошибка {store_name}.save(): {e}")
@dp.message()
async def top(message: Message):
    from bot.design.buttons import btn_top


    if message.text and message.text.strip().lower() in [ "топ" , "статистика" ]:
        top_debug_print("════════════════════════════════════")
        top_debug_print("📥 [ТОП] Хэндлер top ВООБЩЕ был вызван")
        top_debug_print(f"💬 [ТОП] message.text: {message.text!r}")

        user_id = None

        try:
            if not message.from_user:
                top_debug_print("❌ [ТОП] message.from_user отсутствует")
                return

            user_id = message.from_user.id
            top_debug_print(f"👤 [ТОП] user_id: {user_id}")

            try:
                if user_id not in button_user_top:
                    button_user_top [ user_id ] = {}
                    top_debug_print("🆕 [ТОП] Создан новый button_user_top[user_id]")
                else:
                    top_debug_print("📂 [ТОП] button_user_top[user_id] уже существует")

                button_user_top [ user_id ] [ "keyboard_join" ] = btn_top
                top_debug_print("⌨️ [ТОП] Сохранён btn_top в button_user_top[user_id]['keyboard_join']")
            except Exception as e:
                top_debug_print(f"❌ [ТОП] Ошибка при работе с button_user_top: {e}")

            qsdqdsqdsqd = get_random_top_calendar_emoji()

            top_debug_print(f"🧪 [ТОП] Переменная qsdqdsqdsqd: {qsdqdsqdsqd}")
            top_debug_print(f"🧪 [ТОП] repr(qsdqdsqdsqd): {repr(qsdqdsqdsqd)}")
            top_debug_print("📨 [ТОП] Сейчас будет вызван message.reply(...)")

            sent_messagetop = await message.reply(
                text=qsdqdsqdsqd , reply_markup=btn_top , parse_mode="HTML" , disable_web_page_preview=True)

            top_debug_print(f"✅ [ТОП] Сообщение успешно отправлено. message_id={sent_messagetop.message_id}")

            try:
                user_top [ user_id ] = sent_messagetop.message_id
                top_debug_print(f"🧷 [ТОП] user_top[{user_id}] = {sent_messagetop.message_id}")
            except Exception as e:
                top_debug_print(f"❌ [ТОП] Ошибка при сохранении user_top: {e}")

        except Exception as e:
            top_debug_print(f"❌ [ТОП] Ошибка в основном блоке: {e}")

            try:
                top_debug_print(f"🛟 [ТОП] Пробую отправить fallback: {DEFAULT_TOP_EMOJI}")

                sent_messagetop = await message.reply(
                    text=DEFAULT_TOP_EMOJI , reply_markup=btn_top , parse_mode="HTML" , disable_web_page_preview=True)

                if user_id is None and message.from_user:
                    user_id = message.from_user.id

                if user_id is not None:
                    try:
                        user_top [ user_id ] = sent_messagetop.message_id
                        top_debug_print(f"🧷 [ТОП] user_top[{user_id}] = {sent_messagetop.message_id}")
                    except Exception as e_save:
                        top_debug_print(f"❌ [ТОП] Ошибка сохранения user_top после fallback: {e_save}")

                top_debug_print(f"✅ [ТОП] Fallback успешно отправлен. message_id={sent_messagetop.message_id}")

            except Exception as e2:
                top_debug_print(f"❌ [ТОП] Ошибка fallback-отправки: {e2}")

        _top_save_store(button_user_top , "button_user_top")
        _top_save_store(user_top , "user_top")

        top_debug_print("🏁 [ТОП] Обработка команды завершена")
        top_debug_print("════════════════════════════════════")




    # =========================================================
    # DEBUG ДЛЯ СТАТИСТИКИ
    # =========================================================

    def stata_debug_print(*args):
        try:
            print(*args)
        except Exception:
            pass

    def _stata_save_store(store_obj , store_name: str):
        try:
            saver = globals().get("_top_save_store")
            if callable(saver):
                saver(store_obj , store_name)
        except Exception as e:
            stata_debug_print(f"❌ [СТАТА] Ошибка сохранения {store_name}: {e}")

    # =========================================================
    # WEEK COMMAND HELPERS
    # =========================================================

    def _normalize_week_stats_command_text(text: str) -> str:
        try:
            return " ".join(str(text or "").strip().lower().split())
        except Exception:
            return ""

    def _is_week_stats_command(text: str) -> bool:
        try:
            normalized = _normalize_week_stats_command_text(text)

            allowed_commands = [ "стата недели" , "стата неделя" , "стата недель" , "топ недели" , "топ неделя" ,
                "топ недель" , "статистика недели" , "статистика недель" , "статистика неделя" , ]

            if normalized in allowed_commands:
                return True

            for cmd in sorted(allowed_commands , key=len , reverse=True):
                if normalized.startswith(cmd + " "):
                    tail = normalized [ len(cmd): ].strip()

                    if tail.isdigit():
                        return True

            return False

        except Exception:
            return False

    def _parse_week_stats_limit_from_text(text: str , default_limit: int = 30) -> int:
        try:
            normalized = _normalize_week_stats_command_text(text)

            if not normalized:
                return default_limit

            allowed_commands = [ "стата недели" , "стата неделя" , "стата недель" , "топ недели" , "топ неделя" ,
                "топ недель" , "статистика недели" , "статистика недель" , "статистика неделя" , ]

            for cmd in sorted(allowed_commands , key=len , reverse=True):
                if normalized == cmd:
                    return default_limit

                if normalized.startswith(cmd + " "):
                    tail = normalized [ len(cmd): ].strip()

                    if tail.isdigit():
                        value = int(tail)
                        value = min(max(value , 1) , 100)
                        return value

            return default_limit

        except Exception:
            return default_limit

    # =========================================================
    # ОТКРЫТИЕ СООБЩЕНИЯ СО СТАТИСТИКОЙ ЗА НЕДЕЛЮ
    # =========================================================

    async def open_week_stats_message_improved(message: types.Message , limit: int = 30):
        stata_debug_print("════════════════════════════════════")
        stata_debug_print("📥 [СТАТА][WEEK] open_week_stats_message_improved был вызван")

        user_id = None

        try:
            if not message:
                stata_debug_print("❌ [СТАТА][WEEK] message отсутствует")
                return

            if not message.from_user:
                stata_debug_print("❌ [СТАТА][WEEK] message.from_user отсутствует")
                return

            if not message.chat:
                stata_debug_print("❌ [СТАТА][WEEK] message.chat отсутствует")
                return

            chat_id = message.chat.id
            user_id = message.from_user.id

            stata_debug_print(f"👤 [СТАТА][WEEK] user_id: {user_id}")
            stata_debug_print(f"💬 [СТАТА][WEEK] chat_id: {chat_id}")
            stata_debug_print(f"📊 [СТАТА][WEEK] limit: {limit}")

            day_key = await _resolve_valid_day_key(chat_id , None)
            week_key = await _resolve_valid_week_key(chat_id , None)
            month_key = await _resolve_valid_month_key(chat_id , None)

            stata_debug_print(f"📅 [СТАТА][WEEK] day_key: {day_key}")
            stata_debug_print(f"📅 [СТАТА][WEEK] week_key: {week_key}")
            stata_debug_print(f"📅 [СТАТА][WEEK] month_key: {month_key}")

            text = await _stat_text_week(chat_id , user_id , week_key=week_key , limit=limit)

            kb = await _kb_stats(
                chat_id=chat_id , active="week" , day_key=day_key , week_key=week_key , month_key=month_key)

            stata_debug_print("📨 [СТАТА][WEEK] Сейчас будет вызван message.reply(...)")

            sent_messagestata = await message.reply(
                text=text , reply_markup=kb , parse_mode="HTML" , disable_web_page_preview=True)

            stata_debug_print(
                f"✅ [СТАТА][WEEK] Сообщение статистики успешно отправлено. "
                f"message_id={sent_messagestata.message_id}")

            try:
                user_top [ user_id ] = sent_messagestata.message_id
                stata_debug_print(f"🧷 [СТАТА][WEEK] user_top[{user_id}] = {sent_messagestata.message_id}")
            except Exception as e:
                stata_debug_print(f"❌ [СТАТА][WEEK] Ошибка при сохранении user_top: {e}")

        except Exception as e:
            stata_debug_print(f"❌ [СТАТА][WEEK] Ошибка в основном блоке open_week_stats_message_improved: {e}")

            try:
                fallback_day_key = _build_day_key(_today_date())
                fallback_week_key = _build_week_key(_today_date())

                now_dt = _now_dt()
                fallback_month_key = _build_month_key(now_dt.year , now_dt.month)

                fallback_text = (
                    "<tg-emoji emoji-id='5438529285184847871'>🎁</tg-emoji> <b>Статистика сообщений за неделю</b>\n"
                    "<i>Не удалось сразу открыть недельную статистику. Нажми на нужный раздел ниже.</i>")

                fallback_kb = InlineKeyboardMarkup(
                    inline_keyboard=[ [ InlineKeyboardButton(
                        text="За неделю" , callback_data=f"weekstate123:{fallback_week_key}" , style="default" ,
                        icon_custom_emoji_id="5438529285184847871") ] , [ InlineKeyboardButton(
                        text="За день" , callback_data=f"state123:{fallback_day_key}" , style="default" ,
                        icon_custom_emoji_id="5424987025667293801") , InlineKeyboardButton(
                        text="За месяц" , callback_data=f"monthstate123:{fallback_month_key}" , style="default" ,
                        icon_custom_emoji_id="5436371618169389408") , InlineKeyboardButton(
                        text="За всё время" , callback_data="fullstate123" , style="default" ,
                        icon_custom_emoji_id="5303138782004924588") ] ])

                stata_debug_print("🛟 [СТАТА][WEEK] Пробую отправить fallback-меню статистики")

                sent_messagestata = await message.reply(
                    text=fallback_text , reply_markup=fallback_kb , parse_mode="HTML" , disable_web_page_preview=True)

                if user_id is None and message.from_user:
                    user_id = message.from_user.id

                if user_id is not None:
                    try:
                        user_top [ user_id ] = sent_messagestata.message_id
                        stata_debug_print(f"🧷 [СТАТА][WEEK] user_top[{user_id}] = {sent_messagestata.message_id}")
                    except Exception as e_save:
                        stata_debug_print(f"❌ [СТАТА][WEEK] Ошибка сохранения user_top после fallback: {e_save}")

                stata_debug_print(
                    f"✅ [СТАТА][WEEK] Fallback успешно отправлен. "
                    f"message_id={sent_messagestata.message_id}")

            except Exception as e2:
                stata_debug_print(f"❌ [СТАТА][WEEK] Ошибка fallback-отправки: {e2}")

        _stata_save_store(user_top , "user_top")

        stata_debug_print("🏁 [СТАТА][WEEK] open_week_stats_message_improved завершён")
        stata_debug_print("════════════════════════════════════")

    # ───────── «СТАТА НЕДЕЛИ» - триггер строго через if message.text.lower() ─────────
    if message.text and _is_week_stats_command(message.text):
        print("[WEEKLY_STATS] trigger via message.text.lower()")
        stata_debug_print("════════════════════════════════════")
        stata_debug_print("📥 [СТАТА][WEEK] Хэндлер недельной статистики ВООБЩЕ был вызван")
        stata_debug_print(f"💬 [СТАТА][WEEK] message.text: {message.text!r}")

        chat_id = None
        user_id = None

        try:
            if not message.from_user:
                stata_debug_print("❌ [СТАТА][WEEK] message.from_user отсутствует")
                return

            if not message.chat:
                stata_debug_print("❌ [СТАТА][WEEK] message.chat отсутствует")
                return

            chat_id = message.chat.id
            user_id = message.from_user.id

            stata_debug_print(f"👤 [СТАТА][WEEK] user_id: {user_id}")
            stata_debug_print(f"💬 [СТАТА][WEEK] chat_id: {chat_id}")

            try:
                current_stata = await db.get_current_stata(chat_id)
                stata_debug_print(f"⚙️ [СТАТА][WEEK] current_stata: {current_stata}")
            except Exception as e:
                stata_debug_print(f"❌ [СТАТА][WEEK] Ошибка при получении current_stata: {e}")
                current_stata = 1

            if int(current_stata or 0) == 0:
                try:
                    text_stata_random1 = random.choice(text_stata_random)
                except Exception:
                    text_stata_random1 = "Статистика сейчас выключена"

                await message.reply(
                    f"<b>{text_stata_random1}</b>" , parse_mode="HTML" , disable_web_page_preview=True)
                return

            normalized_text = _normalize_week_stats_command_text(message.text)
            num_rows = _parse_week_stats_limit_from_text(message.text , default_limit=30)

            stata_debug_print(f"🧪 [СТАТА][WEEK] normalized_text: {normalized_text!r}")
            stata_debug_print(f"🧪 [СТАТА][WEEK] num_rows: {num_rows}")

            await open_week_stats_message_improved(message , limit=num_rows)
            print("[WEEKLY_STATS] sent OK")

        except Exception as e:
            stata_debug_print(f"❌ [СТАТА][WEEK] Ошибка в основном блоке: {e}")

            try:
                stata_debug_print("🛟 [СТАТА][WEEK] Пробую отправить аварийный fallback")

                fallback_day_key = _build_day_key(_today_date())
                fallback_week_key = _build_week_key(_today_date())

                now_dt = _now_dt()
                fallback_month_key = _build_month_key(now_dt.year , now_dt.month)

                sent_messagestata = await message.reply(
                    text=("<tg-emoji emoji-id='5438529285184847871'>🎁</tg-emoji> "
                          "<b>Статистика сообщений</b>\n"
                          "<i>Выбери нужный вид статистики кнопками ниже.</i>") , reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[ [ InlineKeyboardButton(
                            text="За неделю" , callback_data=f"weekstate123:{fallback_week_key}" , style="default" ,
                            icon_custom_emoji_id="5438529285184847871") ] , [ InlineKeyboardButton(
                            text="За день" , callback_data=f"state123:{fallback_day_key}" , style="default" ,
                            icon_custom_emoji_id="5424987025667293801") , InlineKeyboardButton(
                            text="За месяц" , callback_data=f"monthstate123:{fallback_month_key}" , style="default" ,
                            icon_custom_emoji_id="5436371618169389408") , InlineKeyboardButton(
                            text="За всё время" , callback_data="fullstate123" , style="default" ,
                            icon_custom_emoji_id="5303138782004924588") ] ]) , parse_mode="HTML" ,
                    disable_web_page_preview=True)

                if user_id is None and message.from_user:
                    user_id = message.from_user.id

                if user_id is not None:
                    try:
                        user_top [ user_id ] = sent_messagestata.message_id
                        stata_debug_print(f"🧷 [СТАТА][WEEK] user_top[{user_id}] = {sent_messagestata.message_id}")
                    except Exception as e_save:
                        stata_debug_print(
                            f"❌ [СТАТА][WEEK] Ошибка сохранения user_top после аварийного fallback: {e_save}")

                stata_debug_print(
                    f"✅ [СТАТА][WEEK] Аварийный fallback успешно отправлен. "
                    f"message_id={sent_messagestata.message_id}")

            except Exception as e2:
                stata_debug_print(f"❌ [СТАТА][WEEK] Ошибка аварийного fallback: {e2}")

        _stata_save_store(user_top , "user_top")

        stata_debug_print("🏁 [СТАТА][WEEK] Обработка команды завершена")
        stata_debug_print("════════════════════════════════════")










    if message.text.lower() in [ "Топ инвайтов" , "топ инвайт" , "топ приглашенных" , "топ приглашённых" ,
        "топ приглашений" , "стата инвайтов" , "стата инвайт" , "стата приглашенных" , "стата приглашённых" ,
        "стата приглашений" , "статистика инвайтов" , "статистика инвайт" , "статистика приглашенных" ,
        "статистика приглашённых" , "статистика приглашений" , "реферальная статистика" , "реферальная стата" ,
        "реферальный топ" , "реф топ" , "реф стата" , "реф статистика" , "статистика рефералов" , "стата рефералов" ,
        "стата реф" ]:
        try:
            # Получаем данные пользователей: ID и количество приглашений
            data = await db.get_user_referrals()

            # Словарь с количеством приглашений
            user_referrals = {item [ 0 ]: item [ 1 ] for item in data if len(item) >= 2 and item [ 1 ] is not None}

            # Сортируем пользователей по количеству приглашений (убывание)
            sorted_users = sorted(user_referrals.items() , key=lambda x: x [ 1 ] , reverse=True)

            # Определяем позицию текущего пользователя в топе
            user_position = next(
                (i + 1 for i , (user , _) in enumerate(sorted_users) if user == message.from_user.id) , None)

            # Формируем текст с позицией пользователя (обрабатываем None корректно)
            try:
                position_text = f"{user_position}" if user_position else "Не в топе"
                win_amount_formatted = "{:,.0f}".format(
                    int(position_text) if position_text.isdigit() else 0).replace("," , ".")
            except Exception as e:
                print(f"Ошибка при форматировании позиции: {e}")
                win_amount_formatted = "Ошибка"

            text = f"<tg-emoji emoji-id='5422386835286423005'>🧩</tg-emoji> <b>Статистика приглашений</b>\n" \
                   f"<tg-emoji emoji-id='5192900470598833151'>🔰</tg-emoji> <b>Ваше место : <i>{win_amount_formatted}</i></b>\n\n"

            # Выводим информацию о топ-10 пользователях
            _names_bulk = await db.get_names_bulk(uid for uid , _ in sorted_users [ :10 ])
            for rank , (user_id , referrals) in enumerate(sorted_users [ :10 ] , start=1):
                referrals_with_dots = locale.format_string("%d" , referrals , grouping=True).replace("," , ".")

                # Получаем имя и username пользователя (один batched-запрос перед циклом)
                first_name , username = _names_bulk.get(user_id , (None , None))
                first_name = first_name or "Неизвестный"

                # Формируем ссылку на пользователя
                name_link = await create_user_link(user_id , first_name , username)

                # Выделяем только топ-3 участников
                if rank <= 3:
                    text += f"<b>{rank}. {name_link} ─ {referrals_with_dots} чел.</b>\n\n"
                else:
                    text += f"{rank}. {name_link} ─ <b>{referrals_with_dots}</b> чел.\n\n"

            # Отправляем сообщение с результатами
            await message.reply(text ,reply_markup=btn_helplol, parse_mode="HTML" , disable_web_page_preview=True)

        except Exception as e:
            print(f"Произошла ошибка при обработке запроса1: {e}")


    elif message.text.lower() in [ "топ ловкоинов" , "Топ ловкоинов" , "Топ лов" , "топ лов" , "стата ловкоинов" ,
                                   "стата лов" , "Стата ловкоинов" , "Стата лов" ]:

        top_10 = await db.get_marriages_top_10_ordered_by_lovecoin()

        user_id = message.from_user.id

        user_marriage_position = None

        # Check if the user is involved in any of the top marriages

        for i , marriage in enumerate(top_10 , start=1):

            user_id1 , user_id2 , xp1 = marriage

            if user_id == user_id1 or user_id == user_id2:
                user_marriage_position = i

                break

        stats_message = "❤️ Топ браков по LoveCoins\n"

        if user_marriage_position is not None:
            stats_message += f"💰 Ваше место в топе: {user_marriage_position}\n"

        for i , marriage in enumerate(top_10 , start=1):

            user_id1 , user_id2 , xp1 = marriage

            if xp1 > 0:
                # Получаем username пользователей

                username1 = await db.get_username_by_user_id(user_id1)

                username2 = await db.get_username_by_user_id(user_id2)

                # Получаем имена пользователей

                first_name1 = db.get_firstname(
                    user_id1)  # Предполагается, что есть метод для получения имени

                first_name2 = db.get_firstname(user_id2)

                # Формируем гиперссылки на профили пользователей

                user_link1 = await create_user_link(user_id1 , first_name1 , username1)

                user_link2 = await create_user_link(user_id2 , first_name2 , username2)

                win_amount_formatted = "{:,.0f}".format(xp1).replace("," , ".")

                stats_message += f"\n{i}. {user_link1} + {user_link2} ─ <b>{win_amount_formatted} </b>LoveCoins \n"

        # Calculate pagination

        marriages_per_page = 10

        num_pages = math.ceil(len(top_10) / marriages_per_page)

        # Generate navigation buttons for the first page

        navigation_buttons = await generate_buttons_marryxp(1 , num_pages)

        await message.answer(

            stats_message ,reply_markup=btn_helplol, disable_web_page_preview=True , parse_mode="HTML"

        )


    elif message.text.lower() in [ "топ опыта" , "топ опыт" , "стата опыта" , "стата опыт" ]:

        try:

            # Получаем данные пользователей из базы данных

            data = await db.get_data_users()

            # Создаем словарь для хранения баланса пользователей по их user_id

            user_id_balance = {}

            # Заполняем словарь user_id_balance

            for item in data:

                if len(item) >= 2:  # Проверяем, что есть достаточно данных

                    user_id = item [ 0 ]

                    balance = await db.get_marriages_top_10_ordered_by_xp()

                    user_id_balance [ user_id ] = balance

            # Сортируем пользователей по балансу

            sorted_users = sorted(user_id_balance.items() , key=lambda x: x [ 1 ] , reverse=True)

            # Находим позицию пользователя в списке топ-пользователей

            user_position = next(

                (i + 1 for i , (user , _) in enumerate(sorted_users) if user == message.from_user.id) , None)

            # Формируем текст статистики

            win_amount_formatted = "{:,.0f}".format(user_position).replace("," , ".")

            text = f"<tg-emoji emoji-id='5318959255385043017'>💰</tg-emoji> Статистика богачей\n<tg-emoji emoji-id='5294026527850132517'>✨</tg-emoji> Ваше место в топе: <b>{win_amount_formatted}</b>\n\n"

            # Выводим информацию о топ-пользователях (первые 10)

            rank = 1

            _names_bulk = await db.get_names_bulk(uid for uid , _ in sorted_users [ :10 ])
            for user_id , balance in sorted_users [ :10 ]:
                balance_with_dots = locale.format_string("%d" , balance , grouping=True).replace(',' , '.')

                # Получаем имя и username пользователя по его user_id (batched)

                first_name , username = _names_bulk.get(user_id , (None , None))

                # Формируем гиперссылку на пользователя

                user_link = await create_user_link(user_id , first_name , username)

                # Добавляем информацию о пользователе в текст статистики

                text += f"{rank}. {user_link} ─ <b>{balance_with_dots}</b> XP\n\n"

                rank += 1

            # Редактируем сообщение с обновленным текстом статистики

            await message.reply(

                text ,reply_markup=btn_helplol, parse_mode="HTML" , disable_web_page_preview=True)


        except Exception as e:

            print(f"Произошла ошибка при обработке запроса2: {e}")

    if message.text.lower() in [ "топ браков34123412" , "стата браков34123412" , "топ брак34123412","браки34123412" ]:
        # Получаем топ-10 браков, отсортированных по длительности
        top_10 = await db.get_marriages_top_10_ordered_by_duration()
        num_marriages = len(top_10)
        user_id = message.from_user.id
        user_marriage_position = None
        for i , marriage in enumerate(top_10 , start=1):
            user_id1 , user_id2 , _ = marriage
            if user_id == user_id1 or user_id == user_id2:
                user_marriage_position = i
                break

        stats_message = "🌹 <b>Статистика браков</b>\n\n"

        # Добавляем позицию пользователя в сообщение, если он в топе
        if user_marriage_position is not None:
            stats_message += f"❤️‍🔥 Ваше место в топе: {user_marriage_position}\n\n"

        # Формирование сообщения о браках
        for i , marriage in enumerate(top_10 , start=1):
            user_id1 , user_id2 , marriage_datetime = marriage
            if isinstance(marriage_datetime , str):
                marriage_time = datetime.strptime(marriage_datetime , "%Y-%m-%d %H:%M:%S")
            else:
                marriage_time = marriage_datetime  # уже datetime, конвертировать не нужно
            marriage_duration = datetime.now() - marriage_time

            # Получаем имена пользователей
            first_name1 = await db.get_firstname_by_user_id(user_id1) or "Неизвестный"
            username1 = await db.get_username_by_user_id(user_id1)
            first_name2 = await db.get_firstname_by_user_id(user_id2) or "Неизвестный"
            username2 = await db.get_username_by_user_id(user_id2)

            # Создаем гиперссылки на пользователей
            user_link1 = await create_user_link(user_id1 , first_name1 , username1)
            user_link2 = await create_user_link(user_id2 , first_name2 , username2)

            formatted_duration = format_marriage_duration(marriage_duration)

            # Формируем строку с пользователями: выделяем только первые три брака
            if i <= 3:
                stats_message += f"<b>{i}. {user_link1} + {user_link2} ─ {formatted_duration}</b>\n\n"
            else:
                stats_message += f"{i}. {user_link1} + {user_link2} ─ {formatted_duration}\n\n"

        # Генерируем кнопки навигации для новой страницы


        # Отправляем сообщение с информацией о браках и кнопками навигации
        sent_marry = await message.answer(
            stats_message ,reply_markup=btn_helplol, disable_web_page_preview=True , parse_mode="HTML")

        user_marry_top [ user_id ] = sent_marry.message_id
    user_marry_top.save()

    if message.text.lower() in [ "топ кут","Топ кутов" , "топ кутов","стата кут","стата кутов","кут стата","топ богачей"]:

        # Получаем данные пользователей из базы
        data = await db.get_data_users()

        # Словарь балансов пользователей
        user_id_balance = {item [ 0 ]: item [ 1 ] for item in data if len(item) >= 2}

        # Сортируем пользователей по балансу (убывание)
        sorted_users = sorted(user_id_balance.items() , key=lambda x: x [ 1 ] , reverse=True)

        # Определяем позицию текущего пользователя в топе
        user_position = next(
            (i + 1 for i , (user , _) in enumerate(sorted_users) if user == message.from_user.id) , None)

        # Формируем текст с позицией пользователя
        position_text = "{:,.0f}".format(user_position or 0).replace("," , ".")
        text = f"<tg-emoji emoji-id='5318959255385043017'>💰</tg-emoji> <b>Статистика богачей\n<tg-emoji emoji-id='5294026527850132517'>✨</tg-emoji> Ваше место в топе : <i>{position_text}</i></b>\n\n"
        # Выводим информацию о топ-10 пользователях
        _names_bulk = await db.get_names_bulk(uid for uid , _ in sorted_users [ :10 ])
        for rank , (user_id , balance) in enumerate(sorted_users [ :10 ] , start=1):
            balance_with_dots = locale.format_string("%d" , balance , grouping=True).replace(',' , '.')

            # Получаем имя и username пользователя (batched)
            first_name , username = _names_bulk.get(user_id , (None , None))

            # Формируем ссылку на пользователя
            name_link = await create_user_link(user_id , first_name , username)

            # Добавляем строку с пользователем в текст статистики
            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {balance_with_dots} кут</b>\n\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{balance_with_dots}</b> кут\n\n"

        # Отправляем сообщение с результатами
        await message.reply(text ,reply_markup=btn_helplol, parse_mode="HTML" , disable_web_page_preview=True)

    if message.text.lower() in [ "топ донатеров" , "стата донатеров" , "стата донатеры" , "кут донатеры" , "донатеры" ]:
        # Получаем пользователей с donate > 0 и их donate
        data = await db.get_donaters()  # Эта функция теперь должна возвращать список кортежей (user_id, donate)

        if not data:
            await message.reply("<b>😢 Донатеров пока нет</b>")
            return

        # Словарь user_id -> donate
        user_id_donate = {user_id: donate for user_id , donate in data if donate > 0}

        # Сортируем по donate в убывающем порядке
        sorted_users = sorted(user_id_donate.items() , key=lambda x: x [ 1 ] , reverse=True)

        # Определяем позицию текущего пользователя
        user_position = next(
            (i + 1 for i , (user_id , _) in enumerate(sorted_users) if user_id == message.from_user.id) , None)
        position_text = "{:,.0f}".format(user_position or 0).replace("," , ".")

        text = f"<tg-emoji emoji-id='5318967016390949076'>🎩</tg-emoji> <b>Статистика донатеров\n<tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji> Ваше место в топе: <i>{position_text}</i></b>\n\n"

        # Топ-10
        _names_bulk = await db.get_names_bulk(uid for uid , _ in sorted_users [ :10 ])
        for rank , (user_id , donate) in enumerate(sorted_users [ :10 ] , start=1):
            donate_text = "{:,.0f}".format(donate).replace("," , ".")
            donate_text2 = "{:,.0f}".format(donate).replace("," , ".")

            first_name , username = _names_bulk.get(user_id , (None , None))
            name_link = await create_user_link(user_id , first_name , username)

            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {donate_text} кут [{donate_text2} ⭐️]</b>\n\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{donate_text}</b> кут [{donate_text2} ⭐️]\n\n"

        await message.reply(text , reply_markup=btn_helplol , parse_mode="HTML" , disable_web_page_preview=True)
    if (message.text or "").lower() in [ "топ групп" , "топ группы" , "стата группы" , "стата групп" , "топ чаты" ,
                                         "топ чат" , "топ балансы групп" , "топ бч" ]:

        user_id = message.from_user.id
        message_id = message.message_id

        randommessagehelp1 = random.choice(randommessagehelp)

        # Получаем данные о группах
        data = await db.get_group_balances()

        if not data:
            await message.answer("Не удалось загрузить данные. Попробуйте позже.")
            return

        # Формируем список данных о группах с учетом суммарного баланса
        group_data = [ {"chat_id": item.get("chat_id") ,
            "balance": (int(item.get("chatbalance") or 0) + int(item.get("dexbalance") or 0)) ,
            "name": (item.get("namechat") or "Без названия") , "username": (item.get("usernamechat") or "")} for item in
            data if item.get("chat_id") is not None and (
                        int(item.get("chatbalance") or 0) + int(item.get("dexbalance") or 0)) > 0 and item.get(
                "chat_id") != -1002135149822 ]

        if not group_data:
            await message.answer("Нет данных для отображения (все балансы нулевые).")
            return

        # Сортируем группы по суммарному балансу в порядке убывания
        sorted_groups = sorted(group_data , key=lambda x: x [ "balance" ] , reverse=True)

        # (опционально) ограничим топ, чтобы не слать слишком много
        sorted_groups = sorted_groups [ :50 ]

        # Текст для вывода топа групп
        text = "💸 Статистика групп по балансу\n\n"

        previous_balance = None
        rank = 0

        for i , group in enumerate(sorted_groups):

            # Форматируем баланс
            balance_with_dots = locale.format_string("%d" , group [ "balance" ] , grouping=True).replace("," , ".")

            # Рейтинг с учетом одинаковых балансов
            if group [ "balance" ] != previous_balance:
                rank = i + 1
            previous_balance = group [ "balance" ]

            emoji = random.choice(emojis)

            # Ник может прийти с @ - почистим
            username_clean = (group [ "username" ].replace("@" , "")).strip()

            # Используем обычные текстовые ссылки
            if username_clean:
                name_link = f"https://t.me/{username_clean} ({group [ 'name' ]})"
            else:
                name_link = group [ "name" ]

            text += f"{emoji} {rank}. {name_link} ─ {balance_with_dots} кут\n\n"

        # Разбиваем текст на блоки по ~2000 символов, но по строкам (чтобы не резать строки)
        messages = [ ]
        chunk = ""

        for line in text.splitlines(True):
            if len(chunk) + len(line) > 2000:
                messages.append(chunk)
                chunk = ""
            chunk += line

        if chunk:
            messages.append(chunk)

        # Отправка сообщений с задержкой, и обработкой ошибки, если юзер не открыл ЛС с ботом
        try:
            for message_part in messages:
                await bot1.send_message(user_id , message_part , parse_mode="HTML" , disable_web_page_preview=True)
                await asyncio.sleep(1)
        except Exception:
            await message.answer("Не могу отправить в ЛС. Открой бота в личке и попробуй снова.")
            return

        # Клавиатура (по твоему принципу)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[ [ InlineKeyboardButton(text="Открыть в лс" , url="https://t.me/CuteGamingBot", style="default" , icon_custom_emoji_id="6028346797368283073") ] ,
                [ InlineKeyboardButton(text="Скрыть" , callback_data="deletehelp0101", style="default" , icon_custom_emoji_id="5226660202035554522") ] ])

        btn_help9 = keyboard

        if message.chat.type != 'private':
            await message.reply(
                "<b><tg-emoji emoji-id='5350421256627838238'>📬</tg-emoji> Результаты отправлены в личные сообщения!</b>" ,
                reply_markup=btn_help9 , parse_mode="HTML" , disable_web_page_preview=True)

    if message.text.lower() in [ "топ ктк" , "топ куткоин" ]:
        try:
            # Получаем данные пользователей из базы данных
            data = await db.get_data_users()

            # Создаем словарь для хранения баланса пользователей по их user_id
            user_id_balance = {item [ 0 ]: await db.get_user_cute_coin_balance(item [ 0 ]) for item in data if len(item) >= 2}

            # Сортируем пользователей по балансу
            sorted_users = sorted(user_id_balance.items() , key=lambda x: x [ 1 ] , reverse=True)

            # Находим позицию пользователя в списке топ-пользователей
            user_position = next(
                (i + 1 for i , (user , _) in enumerate(sorted_users) if user == message.from_user.id) , None)

            # Формируем текст статистики
            text = "🎩 Статистика Элиты\n"

            # Если пользователь найден в топе, добавляем информацию о его месте
            if user_position is not None:
                win_amount_formatted = "{:,.0f}".format(user_position).replace("," , ".")
                text += f"📯 Ваше место в топе: <b>{win_amount_formatted}</b>\n\n"

            # Выводим информацию о топ-пользователях (первые 10)
            _names_bulk = await db.get_names_bulk(uid for uid , _ in sorted_users [ :10 ])
            for rank , (user_id , balance) in enumerate(sorted_users [ :10 ] , start=1):
                balance_with_dots = locale.format_string("%d" , balance , grouping=True).replace(',' , '.')

                # Получаем имя и username пользователя по его user_id (batched)
                first_name , username = _names_bulk.get(user_id , (None , None))

                # Создаем ссылку на пользователя
                name_link = await create_user_link(user_id , first_name , username)

                # Добавляем информацию о пользователе в текст статистики
                text += f"{rank}. {name_link} - <b>{balance_with_dots}</b> ктк\n\n"

            # Отправляем сообщение с обновленным текстом статистики
            await message.reply(text ,reply_markup=btn_helplol, parse_mode="HTML" , disable_web_page_preview=True)

        except Exception as e:
            print(f"Произошла ошибка при обработке запроса4: {e}")

    if message.text.lower() in [ "топ кланов" , "топ клан" ]:
        try:
            # Получаем данные кланов из базы данных
            clans_data = await db.get_clans_data()

            # Фильтруем кланы с нулевым балансом и создаем список кланов с их балансами
            clan_balance_list = [ (emoji , name , coins) for emoji , name , coins in clans_data if coins > 0 ]

            # Сортируем кланы по балансу (coins)
            sorted_clans = sorted(clan_balance_list , key=lambda x: x [ 2 ] , reverse=True)

            # Формируем текст статистики
            text = "🛡 <b>Статистика по клановым очкам рейтинга</b>\n\n"

            # Выводим информацию о топ-кланах (первые 10)
            for rank , (emoji , name , balance) in enumerate(sorted_clans [ :10 ] , 1):
                balance_with_dots = locale.format_string("%d" , balance , grouping=True).replace(',' , '.')
                if rank <= 3:
                    text += f"<b>{rank}. <code>{emoji}</code> {name} ─ {balance_with_dots} ⭐️</b>\n\n"
                else:
                    text += f"{rank}. <code>{emoji}</code> {name} ─ <b>{balance_with_dots} ⭐️</b>\n\n"

            # Редактируем сообщение с обновленным текстом статистики
            await message.reply(text ,reply_markup=btn_helplol, parse_mode="HTML" , disable_web_page_preview=True)



        except TelegramAPIError as e:

            print("Произошла ошибка Telegram API:" , e)

        except TelegramBadRequest as e:

            print("Произошла ошибка Telegram Bad Request:" , e)

        except Exception as e:

            print("Произошла ошибка:" , e)

    # =========================================================
    # ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ ДЛЯ СТАТИСТИКИ
    # =========================================================


    # =========================================================
    # DEBUG ДЛЯ СТАТИСТИКИ
    # =========================================================

    def stata_debug_print(*args):
        try:
            print(*args)
        except Exception:
            pass

    def _stata_save_store(store_obj , store_name: str):
        try:
            saver = globals().get("_top_save_store")
            if callable(saver):
                saver(store_obj , store_name)
        except Exception as e:
            stata_debug_print(f"❌ [СТАТА][ALL] Ошибка сохранения {store_name}: {e}")

    # =========================================================
    # HELPERS ДЛЯ КОМАНДЫ "ВСЯ СТАТА"
    # =========================================================

    def _normalize_all_stats_command_text(text: str) -> str:
        try:
            return " ".join(str(text or "").strip().lower().split())
        except Exception:
            return ""

    def _is_all_stats_command(text: str) -> bool:
        try:
            normalized = _normalize_all_stats_command_text(text)

            allowed_commands = [ "вся стата" , "вся статистика" , "вся стата сообщений" , "вся статистика сообщений" ,
                "полная статистика" , "стата вся" , ]

            return normalized in allowed_commands

        except Exception:
            return False

    # =========================================================
    # ОТКРЫТИЕ СООБЩЕНИЯ СО СТАТИСТИКОЙ ЗА ВСЁ ВРЕМЯ
    # =========================================================

    async def open_all_stats_message_improved(message: types.Message , limit: int = 30):
        stata_debug_print("════════════════════════════════════")
        stata_debug_print("📥 [СТАТА][ALL] open_all_stats_message_improved был вызван")

        user_id = None

        try:
            if not message:
                stata_debug_print("❌ [СТАТА][ALL] message отсутствует")
                return

            if not message.from_user:
                stata_debug_print("❌ [СТАТА][ALL] message.from_user отсутствует")
                return

            if not message.chat:
                stata_debug_print("❌ [СТАТА][ALL] message.chat отсутствует")
                return

            chat_id = message.chat.id
            user_id = message.from_user.id

            stata_debug_print(f"👤 [СТАТА][ALL] user_id: {user_id}")
            stata_debug_print(f"💬 [СТАТА][ALL] chat_id: {chat_id}")
            stata_debug_print(f"📊 [СТАТА][ALL] limit: {limit}")

            day_key = await _resolve_valid_day_key(chat_id , None)
            week_key = await _resolve_valid_week_key(chat_id , None)
            month_key = await _resolve_valid_month_key(chat_id , None)

            stata_debug_print(f"📅 [СТАТА][ALL] day_key: {day_key}")
            stata_debug_print(f"📅 [СТАТА][ALL] week_key: {week_key}")
            stata_debug_print(f"📅 [СТАТА][ALL] month_key: {month_key}")

            text = await _stat_text_all(chat_id , user_id , limit=limit)

            kb = await _kb_stats(
                chat_id=chat_id , active="all" , day_key=day_key , week_key=week_key , month_key=month_key)

            stata_debug_print("📨 [СТАТА][ALL] Сейчас будет вызван message.reply(...)")

            sent_messagestata = await message.reply(
                text=text , reply_markup=kb , parse_mode="HTML" , disable_web_page_preview=True)

            stata_debug_print(
                f"✅ [СТАТА][ALL] Сообщение статистики успешно отправлено. "
                f"message_id={sent_messagestata.message_id}")

            try:
                user_top [ user_id ] = sent_messagestata.message_id
                stata_debug_print(f"🧷 [СТАТА][ALL] user_top[{user_id}] = {sent_messagestata.message_id}")
            except Exception as e:
                stata_debug_print(f"❌ [СТАТА][ALL] Ошибка при сохранении user_top: {e}")

            try:
                asyncio.create_task(db.delete_users_after_24_hours(chat_id))
                stata_debug_print(f"🕒 [СТАТА][ALL] Запущен delete_users_after_24_hours для chat_id={chat_id}")
            except Exception as e:
                stata_debug_print(f"❌ [СТАТА][ALL] Ошибка запуска delete_users_after_24_hours: {e}")

        except Exception as e:
            stata_debug_print(f"❌ [СТАТА][ALL] Ошибка в основном блоке open_all_stats_message_improved: {e}")

            try:
                fallback_day_key = _build_day_key(_today_date())
                fallback_week_key = _build_week_key(_today_date())

                now_dt = _now_dt()
                fallback_month_key = _build_month_key(now_dt.year , now_dt.month)

                fallback_text = (
                    "<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> <b>Статистика сообщений за всё время</b>\n"
                    "<i>Не удалось сразу открыть полную статистику. Нажми на нужный раздел ниже.</i>")

                fallback_kb = InlineKeyboardMarkup(
                    inline_keyboard=[ [ InlineKeyboardButton(
                        text="За всё время" , callback_data="fullstate123" , style="default" ,
                        icon_custom_emoji_id="5303138782004924588") ] , [ InlineKeyboardButton(
                        text="За день" , callback_data=f"state123:{fallback_day_key}" , style="default" ,
                        icon_custom_emoji_id="5424987025667293801") , InlineKeyboardButton(
                        text="За неделю" , callback_data=f"weekstate123:{fallback_week_key}" , style="default" ,
                        icon_custom_emoji_id="5438529285184847871") , InlineKeyboardButton(
                        text="За месяц" , callback_data=f"monthstate123:{fallback_month_key}" , style="default" ,
                        icon_custom_emoji_id="5436371618169389408") ] ])

                stata_debug_print("🛟 [СТАТА][ALL] Пробую отправить fallback-меню статистики")

                sent_messagestata = await message.reply(
                    text=fallback_text , reply_markup=fallback_kb , parse_mode="HTML" , disable_web_page_preview=True)

                if user_id is None and message.from_user:
                    user_id = message.from_user.id

                if user_id is not None:
                    try:
                        user_top [ user_id ] = sent_messagestata.message_id
                        stata_debug_print(f"🧷 [СТАТА][ALL] user_top[{user_id}] = {sent_messagestata.message_id}")
                    except Exception as e_save:
                        stata_debug_print(f"❌ [СТАТА][ALL] Ошибка сохранения user_top после fallback: {e_save}")

                try:
                    if message and message.chat:
                        asyncio.create_task(db.delete_users_after_24_hours(message.chat.id))
                        stata_debug_print(f"🕒 [СТАТА][ALL] delete_users_after_24_hours запущен после fallback")
                except Exception as e_task:
                    stata_debug_print(
                        f"❌ [СТАТА][ALL] Ошибка запуска delete_users_after_24_hours после fallback: {e_task}")

                stata_debug_print(
                    f"✅ [СТАТА][ALL] Fallback успешно отправлен. "
                    f"message_id={sent_messagestata.message_id}")

            except Exception as e2:
                stata_debug_print(f"❌ [СТАТА][ALL] Ошибка fallback-отправки: {e2}")

        _stata_save_store(user_top , "user_top")

        stata_debug_print("🏁 [СТАТА][ALL] open_all_stats_message_improved завершён")
        stata_debug_print("════════════════════════════════════")

    # ───────── «ВСЯ СТАТА» - триггер строго через if message.text.lower() ─────────
    if message.text and _is_all_stats_command(message.text):
        stata_debug_print("════════════════════════════════════")
        stata_debug_print("📥 [СТАТА][ALL] Хэндлер полной статистики ВООБЩЕ был вызван")
        stata_debug_print(f"💬 [СТАТА][ALL] message.text: {message.text!r}")

        chat_id = None
        user_id = None

        try:
            if not message.from_user:
                stata_debug_print("❌ [СТАТА][ALL] message.from_user отсутствует")
                return

            if not message.chat:
                stata_debug_print("❌ [СТАТА][ALL] message.chat отсутствует")
                return

            chat_id = message.chat.id
            user_id = message.from_user.id

            stata_debug_print(f"👤 [СТАТА][ALL] user_id: {user_id}")
            stata_debug_print(f"💬 [СТАТА][ALL] chat_id: {chat_id}")

            try:
                current_stata = await db.get_current_stata(chat_id)
                stata_debug_print(f"⚙️ [СТАТА][ALL] current_stata: {current_stata}")
            except Exception as e:
                stata_debug_print(f"❌ [СТАТА][ALL] Ошибка при получении current_stata: {e}")
                current_stata = 1

            if int(current_stata or 0) == 0:
                try:
                    text_stata_random1 = random.choice(text_stata_random)
                except Exception:
                    text_stata_random1 = "Статистика сейчас выключена"

                await message.reply(
                    f"<b>{text_stata_random1}</b>" , parse_mode="HTML" , disable_web_page_preview=True)
                return

            normalized_text = _normalize_all_stats_command_text(message.text)
            stata_debug_print(f"🧪 [СТАТА][ALL] normalized_text: {normalized_text!r}")

            await open_all_stats_message_improved(message , limit=30)

        except Exception as e:
            stata_debug_print(f"❌ [СТАТА][ALL] Ошибка в основном блоке: {e}")

            try:
                stata_debug_print("🛟 [СТАТА][ALL] Пробую отправить аварийный fallback")

                fallback_day_key = _build_day_key(_today_date())
                fallback_week_key = _build_week_key(_today_date())

                now_dt = _now_dt()
                fallback_month_key = _build_month_key(now_dt.year , now_dt.month)

                sent_messagestata = await message.reply(
                    text=("<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> "
                          "<b>Статистика сообщений</b>\n"
                          "<i>Выбери нужный вид статистики кнопками ниже.</i>") , reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[ [ InlineKeyboardButton(
                            text="За всё время" , callback_data="fullstate123" , style="default" ,
                            icon_custom_emoji_id="5303138782004924588") ] , [ InlineKeyboardButton(
                            text="За день" , callback_data=f"state123:{fallback_day_key}" , style="default" ,
                            icon_custom_emoji_id="5424987025667293801") , InlineKeyboardButton(
                            text="За неделю" , callback_data=f"weekstate123:{fallback_week_key}" , style="default" ,
                            icon_custom_emoji_id="5438529285184847871") , InlineKeyboardButton(
                            text="За месяц" , callback_data=f"monthstate123:{fallback_month_key}" , style="default" ,
                            icon_custom_emoji_id="5436371618169389408") ] ]) , parse_mode="HTML" ,
                    disable_web_page_preview=True)

                if user_id is None and message.from_user:
                    user_id = message.from_user.id

                if user_id is not None:
                    try:
                        user_top [ user_id ] = sent_messagestata.message_id
                        stata_debug_print(f"🧷 [СТАТА][ALL] user_top[{user_id}] = {sent_messagestata.message_id}")
                    except Exception as e_save:
                        stata_debug_print(
                            f"❌ [СТАТА][ALL] Ошибка сохранения user_top после аварийного fallback: {e_save}")

                try:
                    if message and message.chat:
                        asyncio.create_task(db.delete_users_after_24_hours(message.chat.id))
                        stata_debug_print(
                            f"🕒 [СТАТА][ALL] delete_users_after_24_hours запущен после аварийного fallback")
                except Exception as e_task:
                    stata_debug_print(
                        f"❌ [СТАТА][ALL] Ошибка запуска delete_users_after_24_hours после аварийного fallback: {e_task}")

                stata_debug_print(
                    f"✅ [СТАТА][ALL] Аварийный fallback успешно отправлен. "
                    f"message_id={sent_messagestata.message_id}")

            except Exception as e2:
                stata_debug_print(f"❌ [СТАТА][ALL] Ошибка аварийного fallback: {e2}")

        _stata_save_store(user_top , "user_top")

        stata_debug_print("🏁 [СТАТА][ALL] Обработка команды завершена")
        stata_debug_print("════════════════════════════════════")





    # =========================================================
    # DEBUG ДЛЯ СТАТИСТИКИ
    # =========================================================

    def stata_debug_print(*args):
        try:
            print(*args)
        except Exception:
            pass

    def _stata_save_store(store_obj , store_name: str):
        try:
            saver = globals().get("_top_save_store")
            if callable(saver):
                saver(store_obj , store_name)
        except Exception as e:
            stata_debug_print(f"❌ [СТАТА] Ошибка сохранения {store_name}: {e}")

    # =========================================================
    # ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ КОМАНДЫ "СТАТА"
    # =========================================================

    def _normalize_stata_command_text(text: str) -> str:
        try:
            return " ".join(str(text or "").strip().lower().split())
        except Exception:
            return ""

    def _parse_stata_limit_from_text(text: str , default_limit: int = 30) -> int:
        try:
            normalized = _normalize_stata_command_text(text)

            if not normalized:
                return default_limit

            allowed_commands = [ "стата" , "статистика" , "стата сообщений" , "статистика сообщений" , "стата соо" ,
                "статистика соо" , ]

            for cmd in sorted(allowed_commands , key=len , reverse=True):
                if normalized == cmd:
                    return default_limit

                if normalized.startswith(cmd + " "):
                    tail = normalized [ len(cmd): ].strip()

                    if tail.isdigit():
                        value = int(tail)
                        value = min(max(value , 1) , 100)
                        return value

            return default_limit

        except Exception:
            return default_limit

    def _is_stata_command(text: str) -> bool:
        try:
            normalized = _normalize_stata_command_text(text)

            allowed_commands = [ "стата" , "статистика" , "стата сообщений" , "статистика сообщений" , "стата соо" ,
                "статистика соо" , ]

            if normalized in allowed_commands:
                return True

            for cmd in sorted(allowed_commands , key=len , reverse=True):
                if normalized.startswith(cmd + " "):
                    tail = normalized [ len(cmd): ].strip()

                    if tail.isdigit():
                        return True

            return False

        except Exception:
            return False

    # =========================================================
    # ОТКРЫТИЕ СООБЩЕНИЯ СО СТАТИСТИКОЙ
    # =========================================================

    async def open_stats_message_improved(message: types.Message , limit: int = 30):
        stata_debug_print("════════════════════════════════════")
        stata_debug_print("📥 [СТАТА] open_stats_message_improved был вызван")

        user_id = None

        try:
            if not message:
                stata_debug_print("❌ [СТАТА] message отсутствует")
                return

            if not message.from_user:
                stata_debug_print("❌ [СТАТА] message.from_user отсутствует")
                return

            if not message.chat:
                stata_debug_print("❌ [СТАТА] message.chat отсутствует")
                return

            chat_id = message.chat.id
            user_id = message.from_user.id

            stata_debug_print(f"👤 [СТАТА] user_id: {user_id}")
            stata_debug_print(f"💬 [СТАТА] chat_id: {chat_id}")
            stata_debug_print(f"📊 [СТАТА] limit: {limit}")

            day_key = await _resolve_valid_day_key(chat_id , None)
            week_key = await _resolve_valid_week_key(chat_id , None)
            month_key = await _resolve_valid_month_key(chat_id , None)

            stata_debug_print(f"📅 [СТАТА] day_key: {day_key}")
            stata_debug_print(f"📅 [СТАТА] week_key: {week_key}")
            stata_debug_print(f"📅 [СТАТА] month_key: {month_key}")

            text = await _stat_text_day(chat_id , user_id , day_key=day_key , limit=limit)

            kb = await _kb_stats(
                chat_id=chat_id , active="day" , day_key=day_key , week_key=week_key , month_key=month_key)

            stata_debug_print("📨 [СТАТА] Сейчас будет вызван message.reply(...)")

            sent_messagestata = await message.reply(
                text=text , reply_markup=kb , parse_mode="HTML" , disable_web_page_preview=True)

            stata_debug_print(
                f"✅ [СТАТА] Сообщение статистики успешно отправлено. message_id={sent_messagestata.message_id}")

            try:
                user_top [ user_id ] = sent_messagestata.message_id
                stata_debug_print(f"🧷 [СТАТА] user_top[{user_id}] = {sent_messagestata.message_id}")
            except Exception as e:
                stata_debug_print(f"❌ [СТАТА] Ошибка при сохранении user_top: {e}")

        except Exception as e:
            stata_debug_print(f"❌ [СТАТА] Ошибка в основном блоке open_stats_message_improved: {e}")

            try:
                fallback_day_key = _build_day_key(_today_date())
                fallback_week_key = _build_week_key(_today_date())

                now_dt = _now_dt()
                fallback_month_key = _build_month_key(now_dt.year , now_dt.month)

                fallback_text = ("<tg-emoji emoji-id='5424987025667293801'>🐰</tg-emoji> <b>Статистика сообщений</b>\n"
                                 "<i>Не удалось открыть полную статистику сразу. Нажми на нужный раздел ниже.</i>")

                fallback_kb = InlineKeyboardMarkup(
                    inline_keyboard=[ [ InlineKeyboardButton(
                        text="За день" , callback_data=f"state123:{fallback_day_key}" , style="default" ,
                        icon_custom_emoji_id="5424987025667293801") ] , [ InlineKeyboardButton(
                        text="За всё время" , callback_data="fullstate123" , style="default" ,
                        icon_custom_emoji_id="5303138782004924588") , InlineKeyboardButton(
                        text="За неделю" , callback_data=f"weekstate123:{fallback_week_key}" , style="default" ,
                        icon_custom_emoji_id="5438529285184847871") , InlineKeyboardButton(
                        text="За месяц" , callback_data=f"monthstate123:{fallback_month_key}" , style="default" ,
                        icon_custom_emoji_id="5436371618169389408") ] ])

                stata_debug_print("🛟 [СТАТА] Пробую отправить fallback-меню статистики")

                sent_messagestata = await message.reply(
                    text=fallback_text , reply_markup=fallback_kb , parse_mode="HTML" , disable_web_page_preview=True)

                if user_id is None and message.from_user:
                    user_id = message.from_user.id

                if user_id is not None:
                    try:
                        user_top [ user_id ] = sent_messagestata.message_id
                        stata_debug_print(f"🧷 [СТАТА] user_top[{user_id}] = {sent_messagestata.message_id}")
                    except Exception as e_save:
                        stata_debug_print(f"❌ [СТАТА] Ошибка сохранения user_top после fallback: {e_save}")

                stata_debug_print(f"✅ [СТАТА] Fallback успешно отправлен. message_id={sent_messagestata.message_id}")

            except Exception as e2:
                stata_debug_print(f"❌ [СТАТА] Ошибка fallback-отправки: {e2}")

        _stata_save_store(user_top , "user_top")

        stata_debug_print("🏁 [СТАТА] open_stats_message_improved завершён")
        stata_debug_print("════════════════════════════════════")

    # =========================================================
    # ОСНОВНОЙ УЛУЧШЕННЫЙ БЛОК КОМАНДЫ "СТАТА"
    # =========================================================

    if message.text and _is_stata_command(message.text):
        stata_debug_print("════════════════════════════════════")
        stata_debug_print("📥 [СТАТА] Хэндлер статы ВООБЩЕ был вызван")
        stata_debug_print(f"💬 [СТАТА] message.text: {message.text!r}")

        user_id = None

        try:
            if not message.from_user:
                stata_debug_print("❌ [СТАТА] message.from_user отсутствует")
                return

            if not message.chat:
                stata_debug_print("❌ [СТАТА] message.chat отсутствует")
                return

            chat_id = message.chat.id
            user_id = message.from_user.id

            stata_debug_print(f"👤 [СТАТА] user_id: {user_id}")
            stata_debug_print(f"💬 [СТАТА] chat_id: {chat_id}")

            normalized_text = _normalize_stata_command_text(message.text)
            num_rows = _parse_stata_limit_from_text(message.text , default_limit=30)

            stata_debug_print(f"🧪 [СТАТА] normalized_text: {normalized_text!r}")
            stata_debug_print(f"🧪 [СТАТА] num_rows: {num_rows}")

            try:
                current_stata = await db.get_current_stata(chat_id)
                stata_debug_print(f"⚙️ [СТАТА] current_stata: {current_stata}")
            except Exception as e:
                stata_debug_print(f"❌ [СТАТА] Ошибка при получении current_stata: {e}")
                current_stata = 1

            if int(current_stata or 0) == 0:
                try:
                    text_stata_random1 = random.choice(text_stata_random)
                except Exception:
                    text_stata_random1 = "Статистика сейчас выключена"

                stata_debug_print("⛔ [СТАТА] Статистика выключена, отправляю сообщение")

                await message.reply(
                    f"<b>{text_stata_random1}</b>" , parse_mode="HTML" , disable_web_page_preview=True)
                return

            await open_stats_message_improved(message , limit=num_rows)

        except Exception as e:
            stata_debug_print(f"❌ [СТАТА] Ошибка в основном блоке: {e}")

            try:
                stata_debug_print("🛟 [СТАТА] Пробую отправить аварийный fallback")

                fallback_day_key = _build_day_key(_today_date())
                fallback_week_key = _build_week_key(_today_date())

                now_dt = _now_dt()
                fallback_month_key = _build_month_key(now_dt.year , now_dt.month)

                sent_messagestata = await message.reply(
                    text=("<tg-emoji emoji-id='5424987025667293801'>🐰</tg-emoji> "
                          "<b>Статистика сообщений</b>\n"
                          "<i>Выбери нужный вид статистики кнопками ниже.</i>") , reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[ [ InlineKeyboardButton(
                            text="За день" , callback_data=f"state123:{fallback_day_key}" , style="default" ,
                            icon_custom_emoji_id="5424987025667293801") ] , [ InlineKeyboardButton(
                            text="За всё время" , callback_data="fullstate123" , style="default" ,
                            icon_custom_emoji_id="5303138782004924588") , InlineKeyboardButton(
                            text="За неделю" , callback_data=f"weekstate123:{fallback_week_key}" , style="default" ,
                            icon_custom_emoji_id="5438529285184847871") , InlineKeyboardButton(
                            text="За месяц" , callback_data=f"monthstate123:{fallback_month_key}" , style="default" ,
                            icon_custom_emoji_id="5436371618169389408") ] ]) , parse_mode="HTML" ,
                    disable_web_page_preview=True)

                if user_id is None and message.from_user:
                    user_id = message.from_user.id

                if user_id is not None:
                    try:
                        user_top [ user_id ] = sent_messagestata.message_id
                        stata_debug_print(f"🧷 [СТАТА] user_top[{user_id}] = {sent_messagestata.message_id}")
                    except Exception as e_save:
                        stata_debug_print(f"❌ [СТАТА] Ошибка сохранения user_top после аварийного fallback: {e_save}")

                stata_debug_print(
                    f"✅ [СТАТА] Аварийный fallback успешно отправлен. message_id={sent_messagestata.message_id}")

            except Exception as e2:
                stata_debug_print(f"❌ [СТАТА] Ошибка аварийного fallback: {e2}")

        _stata_save_store(user_top , "user_top")

        stata_debug_print("🏁 [СТАТА] Обработка команды завершена")
        stata_debug_print("════════════════════════════════════")



@dp.callback_query(lambda c: c.data.startswith('donaters34123412'))
async def callbiahsdofhasodfhoasack_top(call: types.CallbackQuery):
    user_id = call.from_user.id
    message_id = call.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_top or user_top [ user_id ] != message_id:
        await call.answer(randommessagehelp1)
        return
    await call.answer()  # Чтобы убрать "часики"

    data = await db.get_donaters()  # Должен возвращать список кортежей (user_id, donate)

    if not data:
        await call.message.edit_text("<b>😢 Донатеров пока нет</b>", reply_markup=btn_backtop123, parse_mode="HTML")
        return

    # Словарь user_id -> donate
    user_id_donate = {user_id: donate for user_id, donate in data if donate > 0}

    # Сортируем по donate в убывающем порядке
    sorted_users = sorted(user_id_donate.items(), key=lambda x: x[1], reverse=True)

    # Определяем позицию текущего пользователя
    user_position = next(
        (i + 1 for i, (user_id, _) in enumerate(sorted_users) if user_id == call.from_user.id), None)
    position_text = "{:,.0f}".format(user_position or 0).replace(",", ".")

    text = f"<tg-emoji emoji-id='5318967016390949076'>🎩</tg-emoji> <b>Статистика донатеров\n<tg-emoji emoji-id='5472164874886846699'>✨</tg-emoji> Ваше место в топе: <i>{position_text}</i></b>\n\n"

    # Топ-10
    _names_bulk = await db.get_names_bulk(uid for uid, _ in sorted_users[:10])
    for rank, (user_id, donate) in enumerate(sorted_users[:10], start=1):
        donate_text = "{:,.0f}".format(donate).replace(",", ".")
        donate_text2 = "{:,.0f}".format(donate).replace(",", ".")

        first_name, username = _names_bulk.get(user_id, (None, None))
        name_link = await create_user_link(user_id, first_name, username)

        if rank <= 3:
            text += f"<b>{rank}. {name_link} ─ {donate_text} кут [{donate_text2} ⭐️]</b>\n\n"
        else:
            text += f"{rank}. {name_link} ─ <b>{donate_text}</b> кут [{donate_text2} ⭐️]\n\n"

    await call.message.edit_text(
        text, reply_markup=btn_backtop123,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
@dp.callback_query(lambda c: c.data.startswith('userwinamountstop'))
async def callasfasfawqfqwback_top(call: types.CallbackQuery):


    user_id = call.from_user.id
    message_id = call.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_top or user_top [ user_id ] != message_id:
        await call.answer(randommessagehelp1)
        return
    await call.answer()

    try:
        # Получаем данные пользователей: ID и количество приглашений
        data = await db.get_user_winamount_all()

        # Словарь с количеством приглашений
        user_referrals = {item [ 0 ]: item [ 1 ] for item in data if len(item) == 2 and item [ 1 ] is not None}

        # Сортируем пользователей по количеству приглашений (убывание)
        sorted_users = sorted(user_referrals.items() , key=lambda x: x [ 1 ] , reverse=True)

        # Определяем позицию текущего пользователя в топе
        user_position = next(
            (i + 1 for i , (user , _) in enumerate(sorted_users) if user == user_id) , None)

        # Формируем текст с позицией пользователя (обрабатываем None корректно)
        position_text = f"{user_position}" if user_position else "Не в топе"
        win_amount_formatted = "{:,.0f}".format(
            int(position_text) if position_text.isdigit() else 0).replace("," , ".")

        text = f"<tg-emoji emoji-id='5848259999763011021'>⭐️</tg-emoji> <b>Статистика счастливчиков</b>\n" \
               f"<tg-emoji emoji-id='5413628907343588244'>🐰</tg-emoji> <b>Ваше место : <i>{win_amount_formatted}</i></b>\n\n"

        # Выводим информацию о топ-10 пользователях
        _names_bulk = await db.get_names_bulk(uid for uid , _ in sorted_users [ :10 ])
        for rank , (user_id , referrals) in enumerate(sorted_users [ :10 ] , start=1):
            referrals_with_dots = locale.format_string("%d" , referrals , grouping=True).replace("," , ".")

            # Получаем имя и username пользователя (batched)
            first_name , username = _names_bulk.get(user_id , (None , None))
            first_name = first_name or "Неизвестный"

            # Формируем ссылку на пользователя
            name_link = await create_user_link(user_id , first_name , username)

            # Выделяем только топ-3 участников
            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {referrals_with_dots} кут выиграно</b>\n\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{referrals_with_dots}</b> кут выиграно\n\n"

        # Отправляем сообщение с результатами
        await call.message.edit_text(
            text , parse_mode="HTML" , reply_markup=btn_backtop123 , disable_web_page_preview=True)

    except Exception as e:
        print(f"Произошла ошибка при обработке запроса12: {e}")

@dp.callback_query(lambda c: c.data.startswith('userloosetop'))
async def casdasdqwqdqwallback_top(call: types.CallbackQuery):


    user_id = call.from_user.id
    message_id = call.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_top or user_top [ user_id ] != message_id:
        await call.answer(randommessagehelp1)
        return
    await call.answer()

    try:
        # Получаем данные пользователей: ID и количество приглашений
        data = await db.get_user_loose_all()

        # Словарь с количеством приглашений
        user_referrals = {item [ 0 ]: item [ 1 ] for item in data if len(item) == 2 and item [ 1 ] is not None}

        # Сортируем пользователей по количеству приглашений (убывание)
        sorted_users = sorted(user_referrals.items() , key=lambda x: x [ 1 ] , reverse=True)

        # Определяем позицию текущего пользователя в топе
        user_position = next(
            (i + 1 for i , (user , _) in enumerate(sorted_users) if user == user_id) , None)

        # Формируем текст с позицией пользователя (обрабатываем None корректно)
        position_text = f"{user_position}" if user_position else "Не в топе"
        win_amount_formatted = "{:,.0f}".format(
            int(position_text) if position_text.isdigit() else 0).replace("," , ".")

        text = f"<tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> <b>Статистика проигравших</b>\n" \
               f"<tg-emoji emoji-id='5397772549511717747'>🦞</tg-emoji> <b>Ваше место : <i>{win_amount_formatted}</i></b>\n\n"

        # Выводим информацию о топ-10 пользователях
        _names_bulk = await db.get_names_bulk(uid for uid , _ in sorted_users [ :10 ])
        for rank , (user_id , referrals) in enumerate(sorted_users [ :10 ] , start=1):
            referrals_with_dots = locale.format_string("%d" , referrals , grouping=True).replace("," , ".")

            # Получаем имя и username пользователя (batched)
            first_name , username = _names_bulk.get(user_id , (None , None))
            first_name = first_name or "Неизвестный"

            # Формируем ссылку на пользователя
            name_link = await create_user_link(user_id , first_name , username)

            # Выделяем только топ-3 участников
            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {referrals_with_dots} проигрышей</b>\n\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{referrals_with_dots}</b> проигрышей\n\n"

        # Отправляем сообщение с результатами
        await call.message.edit_text(
            text , parse_mode="HTML" , reply_markup=btn_backtop123 , disable_web_page_preview=True)

    except Exception as e:
        print(f"Произошла ошибка при обработке запроса20: {e}")

@dp.callback_query(lambda c: c.data.startswith('userwinstop'))
async def callasdqiqjback_top(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_top or user_top [ user_id ] != message_id:
        await call.answer(randommessagehelp1)
        return
    await call.answer()

    try:
        # Получаем данные пользователей: ID и количество приглашений
        data = await db.get_user_wins_all()

        # Словарь с количеством приглашений
        user_referrals = {item [ 0 ]: item [ 1 ] for item in data if len(item) == 2 and item [ 1 ] is not None}

        # Сортируем пользователей по количеству приглашений (убывание)
        sorted_users = sorted(user_referrals.items() , key=lambda x: x [ 1 ] , reverse=True)

        # Определяем позицию текущего пользователя в топе
        user_position = next(
            (i + 1 for i , (user , _) in enumerate(sorted_users) if user == user_id) , None)

        # Формируем текст с позицией пользователя (обрабатываем None корректно)
        position_text = f"{user_position}" if user_position else "Не в топе"
        win_amount_formatted = "{:,.0f}".format(
            int(position_text) if position_text.isdigit() else 0).replace("," , ".")

        text = f"<tg-emoji emoji-id='5262924479226473498'>🏆</tg-emoji> <b>Статистика победителей</b>\n" \
               f"<tg-emoji emoji-id='5897658922600240288'>⭐️</tg-emoji> <b>Ваше место : <i>{win_amount_formatted}</i></b>\n\n"

        # Выводим информацию о топ-10 пользователях
        _names_bulk = await db.get_names_bulk(uid for uid , _ in sorted_users [ :10 ])
        for rank , (user_id , referrals) in enumerate(sorted_users [ :10 ] , start=1):
            referrals_with_dots = locale.format_string("%d" , referrals , grouping=True).replace("," , ".")

            # Получаем имя и username пользователя (batched)
            first_name , username = _names_bulk.get(user_id , (None , None))
            first_name = first_name or "Неизвестный"

            # Формируем ссылку на пользователя
            name_link = await create_user_link(user_id , first_name , username)

            # Выделяем только топ-3 участников
            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {referrals_with_dots} побед</b>\n\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{referrals_with_dots}</b> побед\n\n"

        # Отправляем сообщение с результатами
        await call.message.edit_text(
            text , parse_mode="HTML" , reply_markup=btn_backtop123 , disable_web_page_preview=True)

    except Exception as e:
        print(f"Произошла ошибка при обработке запроса13: {e}")


@dp.callback_query(lambda c: c.data.startswith('cutessss'))
async def callbrgtrgegrewrack_top(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id

        randommessagehelp1 = random.choice(randommessagehelp)

        if user_id not in user_top or user_top[user_id] != message_id:
            await call.answer(randommessagehelp1)
            return
        await call.answer()

        # Получаем данные пользователей из базы данных
        data = await db.get_data_users()

        # Создаем словарь для хранения баланса пользователей по их user_id
        user_id_balance = {item[0]: item[1] for item in data if len(item) >= 2}

        # Сортируем пользователей по балансу
        sorted_users = sorted(user_id_balance.items(), key=lambda x: x[1], reverse=True)

        # Находим позицию пользователя в списке топ-пользователей
        user_position = next((i + 1 for i, (user, _) in enumerate(sorted_users) if user == user_id), None)

        # Формируем текст статистики
        win_amount_formatted = "{:,.0f}".format(user_position).replace(",", ".") if user_position else "н/a"
        text = f"<tg-emoji emoji-id='5318959255385043017'>💰</tg-emoji> <b>Статистика богачей\n<tg-emoji emoji-id='5294026527850132517'>✨</tg-emoji> Ваше место в топе : <i>{win_amount_formatted}</i></b>\n\n"

        # Выводим информацию о топ-пользователях (первые 10)
        _names_bulk = await db.get_names_bulk(uid for uid, _ in sorted_users[:10])
        for rank, (user_id, balance) in enumerate(sorted_users[:10], start=1):
            balance_with_dots = locale.format_string("%d", balance, grouping=True).replace(',', '.')

            # Получаем имя и username пользователя по его user_id (batched)
            first_name, username = _names_bulk.get(user_id, (None, None))

            # Формируем ссылку на пользователя
            name_link = await create_user_link(user_id, first_name, username)

            # Добавляем информацию о пользователе в текст статистики
            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {balance_with_dots} кут</b>\n\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{balance_with_dots}</b> кут\n\n"

        # Редактируем сообщение с обновленным текстом статистики
        await call.message.edit_text(
            text, reply_markup=btn_backtop123, parse_mode="HTML", disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Произошла ошибка при обработке запроса14: {e}")



@dp.callback_query(lambda c: c.data.startswith('balancegrouptop'))
async def calsadqwdqwqdqwcqlback_top(call: types.CallbackQuery):
    user_id = call.from_user.id
    message_id = call.message.message_id

    # Проверка на актуальность запроса
    if user_id not in user_top or user_top[user_id] != message_id:
        await call.answer(random.choice(randommessagehelp))
        return

    # Получение данных из БД
    data = await db.get_group_balances()
    if not data:
        await call.answer("⚠️ Не удалось загрузить данные. Пожалуйста, попробуйте позже.")
        return
    await call.answer()

    # Подготовка и фильтрация данных
    group_data = [
        {
            "chat_id": row["chat_id"],
            "balance": row["chatbalance"] + row["dexbalance"],
            "name": row["namechat"],
            "username": row["usernamechat"]
        }
        for row in data
        if "chat_id" in row and row["chatbalance"] + row["dexbalance"] > 0 and row["chat_id"] != -1002135149822
    ]

    if not group_data:
        await call.message.edit_text("😢 Нет данных по группам с положительным балансом.")
        return

    # Сортировка по балансу
    sorted_groups = sorted(group_data, key=lambda x: x["balance"], reverse=True)[:50]

    # Формирование текста
    text = "<tg-emoji emoji-id='5262924479226473498'>🏆</tg-emoji> <b>Топ групп по балансу</b>\n\n"
    previous_balance = None
    rank = 0

    for i, group in enumerate(sorted_groups):
        balance = group["balance"]
        formatted_balance = locale.format_string("%d", balance, grouping=True).replace(",", ".")

        if balance != previous_balance:
            rank = i + 1
            previous_balance = balance

        emoji = random.choice(emojis)

        username = group["username"]
        name = group["name"]
        if username and username.startswith("http"):
            name_link = f"<a href='{username}'>{name}</a>"
        elif username:
            name_link = f"<a href='https://t.me/{username}'>{name}</a>"
        else:
            name_link = name

        if rank <= 3:
            text += f"{emoji} <b>{rank}. {name_link} ─ {formatted_balance} кут</b>\n\n"
        else:
            text += f"{emoji} {rank}. {name_link} ─ <b>{formatted_balance}</b> кут\n\n"

    # Вывод результата
    await call.message.edit_text(
        text,
        reply_markup=btn_backtop123,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.callback_query(lambda c: c.data.startswith('ktktop'))
async def callbaasdqsdqwcqck_top(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id


        randommessagehelp1 = random.choice(randommessagehelp)

        if user_id not in user_top or user_top[user_id] != message_id:
            await call.answer(randommessagehelp1)
            return
        await call.answer()

        # Получаем данные пользователей из базы данных
        data = await db.get_data_users()

        # Создаем словарь для хранения баланса пользователей по их user_id
        user_id_balance = {
            item[0]: await db.get_user_cute_coin_balance(item[0])
            for item in data if len(item) >= 2
        }

        # Сортируем пользователей по балансу
        sorted_users = sorted(user_id_balance.items(), key=lambda x: x[1], reverse=True)

        # Находим позицию пользователя в списке топ-пользователей
        user_position = next((i + 1 for i, (user, _) in enumerate(sorted_users) if user == user_id), None)

        # Формируем текст статистики
        text = "🎩 Статистика Элиты\n"
        if user_position is not None:
            win_amount_formatted = "{:,.0f}".format(user_position).replace(",", ".")
            text += f"📯 Ваше место в топе: <b>{win_amount_formatted}</b>\n\n"

        # Выводим информацию о топ-пользователях (первые 10)
        _names_bulk = await db.get_names_bulk(uid for uid, _ in sorted_users[:10])
        for rank, (user_id, balance) in enumerate(sorted_users[:10], start=1):
            balance_with_dots = locale.format_string("%d", balance, grouping=True).replace(',', '.')

            # Получаем имя и username пользователя по его user_id (batched)
            first_name, username = _names_bulk.get(user_id, (None, None))

            # Формируем ссылку на пользователя
            name_link = await create_user_link(user_id, first_name, username)

            # Добавляем информацию о пользователе в текст статистики
            text += f"{rank}. {name_link} ─ <b>{balance_with_dots}</b> ктк\n\n"

        # Редактируем сообщение с обновленным текстом статистики
        await call.message.edit_text(
            text, reply_markup=btn_backtop123, parse_mode="HTML", disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Произошла ошибка при обработке запроса15: {e}")


@dp.callback_query(lambda c: c.data.startswith('kutenin123'))
async def callasqsvevqwqqeback_top(call: types.CallbackQuery):

    try:

        user_id = call.from_user.id
        message_id = call.message.message_id




        randommessagehelp1 = random.choice(randommessagehelp)

        if user_id not in user_top or user_top [ user_id ] != message_id:
            await call.answer(randommessagehelp1)
            return
        await call.answer()
        # Получаем данные пользователей из базы данных
            # Получаем данные кланов из базы данных
        clans_data = await db.get_clans_data()

        # Фильтруем кланы с нулевым балансом и создаем список кланов с их балансами
        clan_balance_list = [ (emoji , name , coins) for emoji , name , coins in clans_data if coins > 0 ]

        # Сортируем кланы по балансу (coins)
        sorted_clans = sorted(clan_balance_list , key=lambda x: x [ 2 ] , reverse=True)

        # Формируем текст статистики
        text = "🛡 <b>Статистика по клановым очкам рейтинга</b>\n\n"

        # Выводим информацию о топ-кланах (первые 10)
        for rank , (emoji , name , balance) in enumerate(sorted_clans [ :10 ] , 1):
            balance_with_dots = locale.format_string("%d" , balance , grouping=True).replace(',' , '.')
            if rank <= 3:
                text += f"<b>{rank}. <code>{emoji}</code> {name} ─ {balance_with_dots} ⭐️</b>\n\n"
            else:
                text += f"{rank}. <code>{emoji}</code> {name} ─ <b>{balance_with_dots} ⭐️</b>\n\n"



            # Редактируем сообщение с обновленным текстом статистики

        await call.message.edit_text(text, reply_markup=btn_backtop123, parse_mode="HTML", disable_web_page_preview=True)


    except TelegramAPIError as e:

        print("Произошла ошибка Telegram API:" , e)

    except TelegramBadRequest as e:

        print("Произошла ошибка Telegram Bad Request:" , e)

    except Exception as e:

        print("Произошла ошибка:" , e)


from datetime import datetime, timedelta, date
from typing import Optional, Tuple, List
from html import escape

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError


# =========================================================
# НАСТРОЙКИ НАВИГАЦИИ
# =========================================================

STATS_DAY_LOOKBACK_DAYS = 7       # сегодня + 7 дней назад
STATS_WEEK_LOOKBACK_WEEKS = 3     # текущая неделя + 3 недели назад


# =========================================================
# МЕСЯЦЫ
# =========================================================

RUS_MONTHS = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}

RUS_MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def _fmt_int(n: int) -> str:
    return "{:,.0f}".format(int(n)).replace(",", ".")


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _now_dt() -> datetime:
    return datetime.now()


def _today_date() -> date:
    return _now_dt().date()


def _month_label(year: int, month: int) -> str:
    return f"{RUS_MONTHS.get(month, str(month)).capitalize()} {year}"


def _month_range_label(year: int, month: int) -> str:
    return f"{RUS_MONTHS_GENITIVE.get(month, str(month)).capitalize()} {year}"


def _build_month_key(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def _parse_month_key(month_key: str) -> Tuple[int, int]:
    try:
        parts = str(month_key).strip().split("-")
        year = int(parts[0])
        month = int(parts[1])
        if month < 1 or month > 12:
            raise ValueError("Неверный месяц")
        return year, month
    except Exception:
        now = _now_dt()
        return now.year, now.month


def _build_day_key(day_value: date) -> str:
    return day_value.strftime("%Y-%m-%d")


def _parse_day_key(day_key: Optional[str]) -> date:
    try:
        return datetime.strptime(str(day_key).strip(), "%Y-%m-%d").date()
    except Exception:
        return _today_date()


def _day_label(day_value: date) -> str:
    return day_value.strftime("%d.%m.%Y")


def _week_start(day_value: date) -> date:
    return day_value - timedelta(days=day_value.weekday())


def _week_end(day_value: date) -> date:
    return _week_start(day_value) + timedelta(days=6)


def _build_week_key(day_value: date) -> str:
    return _build_day_key(_week_start(day_value))


def _parse_week_key(week_key: Optional[str]) -> date:
    try:
        parsed = datetime.strptime(str(week_key).strip(), "%Y-%m-%d").date()
        return _week_start(parsed)
    except Exception:
        return _week_start(_today_date())


def _week_label_from_start(week_start_date: date) -> str:
    week_end_date = week_start_date + timedelta(days=6)
    return f"{week_start_date.strftime('%d.%m.%Y')} - {week_end_date.strftime('%d.%m.%Y')}"


def _extract_record_value(obj, preferred_key: Optional[str] = None, default=None):
    try:
        if obj is None:
            return default

        if preferred_key and hasattr(obj, "keys"):
            try:
                if preferred_key in obj.keys():
                    return obj[preferred_key]
            except Exception:
                pass

        if isinstance(obj, dict):
            if preferred_key and preferred_key in obj:
                return obj.get(preferred_key)
            if obj:
                return next(iter(obj.values()))
            return default

        if isinstance(obj, (tuple, list)):
            if len(obj) > 0:
                return obj[0]
            return default

        return obj
    except Exception:
        return default


def _extract_top_row(row) -> Tuple[int, int]:
    try:
        if row is None:
            return 0, 0

        if hasattr(row, "keys"):
            keys = list(row.keys())

            uid = None
            cnt = None

            if "user_id" in keys:
                uid = row["user_id"]
            elif len(keys) >= 1:
                uid = row[keys[0]]

            if "total_messages" in keys:
                cnt = row["total_messages"]
            elif "cnt" in keys:
                cnt = row["cnt"]
            elif "count" in keys:
                cnt = row["count"]
            elif len(keys) >= 2:
                cnt = row[keys[1]]

            return _safe_int(uid), _safe_int(cnt)

        if isinstance(row, dict):
            return _safe_int(row.get("user_id")), _safe_int(
                row.get("total_messages", row.get("cnt", row.get("count", 0)))
            )

        if isinstance(row, (tuple, list)):
            uid = row[0] if len(row) > 0 else 0
            cnt = row[1] if len(row) > 1 else 0
            return _safe_int(uid), _safe_int(cnt)

        return 0, 0

    except Exception:
        return 0, 0


async def _db_get_scalar(method, *args, default=None, preferred_key: Optional[str] = None):
    try:
        result = await method(*args)
        value = _extract_record_value(result, preferred_key=preferred_key, default=default)
        if value is None:
            return default
        return value
    except Exception as e:
        print(f"❌ Ошибка в _db_get_scalar для {getattr(method, '__name__', 'unknown')}: {e}")
        return default


async def _safe_get_first_name(user_id: int) -> str:
    try:
        value = await _db_get_scalar(
            db.get_firstname_by_user_id,
            user_id,
            default="",
            preferred_key="first_name"
        )
        return str(value or "").strip()
    except Exception as e:
        print(f"❌ Ошибка при получении first_name user_id={user_id}: {e}")
        return ""


async def _safe_get_username(user_id: int) -> str:
    try:
        value = await _db_get_scalar(
            db.get_username_by_user_id,
            user_id,
            default="",
            preferred_key="username"
        )
        value = str(value or "").strip()

        if value.startswith("@"):
            value = value[1:]

        return value
    except Exception as e:
        print(f"❌ Ошибка при получении username user_id={user_id}: {e}")
        return ""


async def _safe_create_user_link(user_id: int) -> str:
    try:
        first_name = await _safe_get_first_name(user_id)
        username = await _safe_get_username(user_id)

        display_name = first_name if first_name else (username if username else f"id {user_id}")
        display_name = escape(display_name)

        if username:
            return f"<a href='https://t.me/{escape(username)}'>{display_name}</a>"

        return f"<a href='tg://user?id={int(user_id)}'>{display_name}</a>"

    except Exception as e:
        print(f"❌ Ошибка при создании ссылки на пользователя {user_id}: {e}")
        return f"<code>{int(user_id)}</code>"


async def _safe_member_count(chat_id: int) -> int:
    try:
        return _safe_int(await db.get_user_by_chat_id_count(chat_id), 0)
    except Exception as e:
        print(f"❌ Ошибка при получении количества участников chat_id={chat_id}: {e}")
        return 0


async def _safe_edit_stats_message(
    call: types.CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup
):
    try:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        print("✅ [STATS EDIT] Сообщение статистики успешно обновлено")
    except TelegramBadRequest as e:
        err_text = str(e).lower()

        if "message is not modified" in err_text:
            print("ℹ️ [STATS EDIT] Сообщение не изменилось, пробую обновить только клавиатуру")
            try:
                await call.message.edit_reply_markup(reply_markup=reply_markup)
            except Exception as inner_e:
                print(f"❌ [STATS EDIT] Не удалось обновить reply_markup: {inner_e}")
            return

        print(f"❌ [STATS EDIT] TelegramBadRequest: {e}")
        try:
            await call.answer("⚠️ Не удалось обновить статистику", show_alert=False)
        except Exception:
            pass

    except TelegramAPIError as e:
        print(f"❌ [STATS EDIT] TelegramAPIError: {e}")
        try:
            await call.answer("⚠️ Ошибка Telegram API", show_alert=False)
        except Exception:
            pass

    except Exception as e:
        print(f"❌ [STATS EDIT] Неизвестная ошибка: {e}")
        try:
            await call.answer("⚠️ Не удалось обновить статистику", show_alert=False)
        except Exception:
            pass


# =========================================================
# НАСТРОЙКИ НАВИГАЦИИ
# =========================================================

STATS_DAY_LOOKBACK_DAYS = 7
STATS_WEEK_LOOKBACK_WEEKS = 3


# =========================================================
# МЕСЯЦЫ
# =========================================================

RUS_MONTHS = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}

RUS_MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def _fmt_int(n: int) -> str:
    return "{:,.0f}".format(int(n)).replace(",", ".")


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _now_dt() -> datetime:
    return datetime.now()


def _today_date() -> date:
    return _now_dt().date()


def _month_label(year: int, month: int) -> str:
    return f"{RUS_MONTHS.get(month, str(month)).capitalize()} {year}"


def _month_range_label(year: int, month: int) -> str:
    return f"{RUS_MONTHS_GENITIVE.get(month, str(month)).capitalize()} {year}"


def _build_month_key(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def _parse_month_key(month_key: str) -> Tuple[int, int]:
    try:
        parts = str(month_key).strip().split("-")
        year = int(parts[0])
        month = int(parts[1])

        if month < 1 or month > 12:
            raise ValueError("Неверный месяц")

        return year, month

    except Exception:
        now = _now_dt()
        return now.year, now.month


def _build_day_key(day_value: date) -> str:
    return day_value.strftime("%Y-%m-%d")


def _parse_day_key(day_key: Optional[str]) -> date:
    try:
        return datetime.strptime(str(day_key).strip(), "%Y-%m-%d").date()
    except Exception:
        return _today_date()


def _day_label(day_value: date) -> str:
    return day_value.strftime("%d.%m.%Y")


def _week_start(day_value: date) -> date:
    return day_value - timedelta(days=day_value.weekday())


def _week_end(day_value: date) -> date:
    return _week_start(day_value) + timedelta(days=6)


def _build_week_key(day_value: date) -> str:
    return _build_day_key(_week_start(day_value))


def _parse_week_key(week_key: Optional[str]) -> date:
    try:
        parsed = datetime.strptime(str(week_key).strip(), "%Y-%m-%d").date()
        return _week_start(parsed)
    except Exception:
        return _week_start(_today_date())


def _week_label_from_start(week_start_date: date) -> str:
    week_end_date = week_start_date + timedelta(days=6)
    return f"{week_start_date.strftime('%d.%m.%Y')} - {week_end_date.strftime('%d.%m.%Y')}"


def _extract_record_value(obj, preferred_key: Optional[str] = None, default=None):
    try:
        if obj is None:
            return default

        if preferred_key and hasattr(obj, "keys"):
            try:
                if preferred_key in obj.keys():
                    return obj[preferred_key]
            except Exception:
                pass

        if isinstance(obj, dict):
            if preferred_key and preferred_key in obj:
                return obj.get(preferred_key)

            if obj:
                return next(iter(obj.values()))

            return default

        if isinstance(obj, (tuple, list)):
            if len(obj) > 0:
                return obj[0]

            return default

        return obj

    except Exception:
        return default


def _extract_top_row(row) -> Tuple[int, int]:
    try:
        if row is None:
            return 0, 0

        if hasattr(row, "keys"):
            keys = list(row.keys())

            uid = None
            cnt = None

            if "user_id" in keys:
                uid = row["user_id"]
            elif len(keys) >= 1:
                uid = row[keys[0]]

            if "total_messages" in keys:
                cnt = row["total_messages"]
            elif len(keys) >= 2:
                cnt = row[keys[1]]

            return _safe_int(uid), _safe_int(cnt)

        if isinstance(row, dict):
            return _safe_int(row.get("user_id")), _safe_int(row.get("total_messages"))

        if isinstance(row, (tuple, list)):
            uid = row[0] if len(row) > 0 else 0
            cnt = row[1] if len(row) > 1 else 0
            return _safe_int(uid), _safe_int(cnt)

        return 0, 0

    except Exception:
        return 0, 0


async def _db_get_scalar(method, *args, default=None, preferred_key: Optional[str] = None):
    try:
        result = await method(*args)
        value = _extract_record_value(result, preferred_key=preferred_key, default=default)

        if value is None:
            return default

        return value

    except Exception as e:
        print(f"Ошибка в _db_get_scalar для {getattr(method, '__name__', 'unknown')}: {e}")
        return default


async def _safe_get_first_name(user_id: int) -> str:
    try:
        value = await _db_get_scalar(
            db.get_firstname_by_user_id,
            user_id,
            default="",
            preferred_key="first_name"
        )
        return str(value or "").strip()

    except Exception as e:
        print(f"Ошибка при получении first_name user_id={user_id}: {e}")
        return ""


async def _safe_get_username(user_id: int) -> str:
    try:
        value = await _db_get_scalar(
            db.get_username_by_user_id,
            user_id,
            default="",
            preferred_key="username"
        )
        value = str(value or "").strip()

        if value.startswith("@"):
            value = value[1:]

        return value

    except Exception as e:
        print(f"Ошибка при получении username user_id={user_id}: {e}")
        return ""


async def _safe_create_user_link(user_id: int) -> str:
    try:
        first_name = await _safe_get_first_name(user_id)
        username = await _safe_get_username(user_id)

        display_name = first_name if first_name else (username if username else f"id {user_id}")
        display_name = escape(display_name)

        if username:
            return f"<a href='https://t.me/{escape(username)}'>{display_name}</a>"

        return f"<a href='tg://user?id={int(user_id)}'>{display_name}</a>"

    except Exception as e:
        print(f"Ошибка при создании ссылки на пользователя {user_id}: {e}")
        return f"<code>{int(user_id)}</code>"


async def _safe_member_count(chat_id: int) -> int:
    try:
        return _safe_int(await db.get_user_by_chat_id_count(chat_id), 0)
    except Exception:
        return 0


def _link_from_names_bulk(user_id: int, names_bulk: dict) -> str:
    """Как _safe_create_user_link, но по уже загруженным именам (без похода в БД на каждого юзера)."""
    first_name, username = names_bulk.get(user_id, (None, None))
    display_name = first_name if first_name else (username if username else f"id {user_id}")
    display_name = escape(display_name)

    if username:
        return f"<a href='https://t.me/{escape(username)}'>{display_name}</a>"

    return f"<a href='tg://user?id={int(user_id)}'>{display_name}</a>"


async def _safe_edit_stats_message(
    call: types.CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup
):
    try:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

    except TelegramBadRequest as e:
        err_text = str(e).lower()

        if "message is not modified" in err_text:
            try:
                await call.message.edit_reply_markup(reply_markup=reply_markup)
            except Exception:
                pass
            return

        print("Произошла ошибка Telegram Bad Request:", e)

        try:
            await call.answer("⚠️ Не удалось обновить статистику", show_alert=False)
        except Exception:
            pass

    except TelegramAPIError as e:
        print("Произошла ошибка Telegram API:", e)

        try:
            await call.answer("⚠️ Ошибка Telegram API", show_alert=False)
        except Exception:
            pass

    except Exception as e:
        print("Произошла ошибка:", e)

        try:
            await call.answer("⚠️ Не удалось обновить статистику", show_alert=False)
        except Exception:
            pass


# =========================================================
# НАВИГАЦИЯ
# =========================================================

async def _get_available_month_keys(chat_id: int):
    raw = await db.get_available_months(chat_id, limit=120)

    result = []

    for item in raw:
        try:
            if isinstance(item, (tuple, list)):
                y = _safe_int(item[0])
                m = _safe_int(item[1])
            elif hasattr(item, "keys"):
                y = _safe_int(item["year"])
                m = _safe_int(item["month"])
            elif isinstance(item, dict):
                y = _safe_int(item.get("year"))
                m = _safe_int(item.get("month"))
            else:
                continue

            if 1 <= m <= 12:
                result.append(_build_month_key(y, m))
        except Exception:
            continue

    result = sorted(set(result))
    return result


async def _get_available_day_keys(chat_id: int) -> List[str]:
    today = _today_date()
    result = []

    for offset in range(STATS_DAY_LOOKBACK_DAYS, -1, -1):
        d = today - timedelta(days=offset)
        result.append(_build_day_key(d))

    result = sorted(set(result))
    return result


async def _get_available_week_keys(chat_id: int) -> List[str]:
    current_week = _week_start(_today_date())
    result = []

    for offset in range(STATS_WEEK_LOOKBACK_WEEKS, -1, -1):
        d = current_week - timedelta(days=7 * offset)
        result.append(_build_week_key(d))

    result = sorted(set(result))
    return result


async def _resolve_valid_day_key(chat_id: int, requested_day_key: Optional[str] = None) -> str:
    day_keys = await _get_available_day_keys(chat_id)

    if not day_keys:
        return _build_day_key(_today_date())

    if requested_day_key and requested_day_key in day_keys:
        return requested_day_key

    return day_keys[-1]


async def _resolve_valid_week_key(chat_id: int, requested_week_key: Optional[str] = None) -> str:
    week_keys = await _get_available_week_keys(chat_id)

    if not week_keys:
        return _build_week_key(_today_date())

    if requested_week_key and requested_week_key in week_keys:
        return requested_week_key

    return week_keys[-1]


async def _resolve_valid_month_key(chat_id: int, requested_month_key: Optional[str] = None) -> str:
    month_keys = await _get_available_month_keys(chat_id)

    if not month_keys:
        now = _now_dt()
        return _build_month_key(now.year, now.month)

    if requested_month_key and requested_month_key in month_keys:
        return requested_month_key

    return month_keys[-1]


async def _get_day_nav_info(chat_id: int, day_key: Optional[str]):
    day_keys = await _get_available_day_keys(chat_id)
    resolved_key = await _resolve_valid_day_key(chat_id, day_key)

    prev_key = None
    next_key = None
    has_data = resolved_key in day_keys

    if has_data:
        idx = day_keys.index(resolved_key)

        if idx > 0:
            prev_key = day_keys[idx - 1]

        if idx < len(day_keys) - 1:
            next_key = day_keys[idx + 1]

    return {
        "resolved_key": resolved_key,
        "day_keys": day_keys,
        "prev_key": prev_key,
        "next_key": next_key,
        "has_data": has_data,
    }


async def _get_week_nav_info(chat_id: int, week_key: Optional[str]):
    week_keys = await _get_available_week_keys(chat_id)
    resolved_key = await _resolve_valid_week_key(chat_id, week_key)

    prev_key = None
    next_key = None
    has_data = resolved_key in week_keys

    if has_data:
        idx = week_keys.index(resolved_key)

        if idx > 0:
            prev_key = week_keys[idx - 1]

        if idx < len(week_keys) - 1:
            next_key = week_keys[idx + 1]

    return {
        "resolved_key": resolved_key,
        "week_keys": week_keys,
        "prev_key": prev_key,
        "next_key": next_key,
        "has_data": has_data,
    }


async def _get_month_nav_info(chat_id: int, month_key: Optional[str]):
    month_keys = await _get_available_month_keys(chat_id)
    resolved_key = await _resolve_valid_month_key(chat_id, month_key)

    prev_key = None
    next_key = None
    has_data = resolved_key in month_keys

    if has_data:
        idx = month_keys.index(resolved_key)

        if idx > 0:
            prev_key = month_keys[idx - 1]

        if idx < len(month_keys) - 1:
            next_key = month_keys[idx + 1]

    return {
        "resolved_key": resolved_key,
        "month_keys": month_keys,
        "prev_key": prev_key,
        "next_key": next_key,
        "has_data": has_data,
    }


# =========================================================
# КЛАВИАТУРА
# =========================================================

async def _kb_stats(
    chat_id: int,
    active: str = "day",
    day_key: Optional[str] = None,
    week_key: Optional[str] = None,
    month_key: Optional[str] = None
) -> InlineKeyboardMarkup:
    if active == "day":
        day_key = await _resolve_valid_day_key(chat_id, day_key)

    if active == "week":
        week_key = await _resolve_valid_week_key(chat_id, week_key)

    if active == "month":
        month_key = await _resolve_valid_month_key(chat_id, month_key)

    t_day = "✔️ За день" if active == "day" else "За день"
    t_week = "✔️ За неделю" if active == "week" else "За неделю"
    t_month = "✔️ За месяц" if active == "month" else "За месяц"
    t_all = "✔️ За всё время" if active == "all" else "За всё время"

    btn_day = InlineKeyboardButton(
        text=t_day,
        callback_data=f"state123:{day_key or ''}",
        style="default",
        icon_custom_emoji_id="5424987025667293801"
    )
    btn_week = InlineKeyboardButton(
        text=t_week,
        callback_data=f"weekstate123:{week_key or ''}",
        style="default",
        icon_custom_emoji_id="5438529285184847871"
    )
    btn_month = InlineKeyboardButton(
        text=t_month,
        callback_data=f"monthstate123:{month_key or ''}",
        style="default",
        icon_custom_emoji_id="5436371618169389408"
    )
    btn_all = InlineKeyboardButton(
        text=t_all,
        callback_data="fullstate123",
        style="default",
        icon_custom_emoji_id="5303138782004924588"
    )
    btn_back = InlineKeyboardButton(
        text="Назад",
        callback_data="backtop",
        style="default",
        icon_custom_emoji_id="5255703720078879038"
    )

    rows = [
        [btn_day],
        [btn_all, btn_week, btn_month],
    ]

    if active == "day":
        nav = await _get_day_nav_info(chat_id, day_key)
        resolved_key = nav["resolved_key"]
        prev_key = nav["prev_key"]
        next_key = nav["next_key"]

        target_day = _parse_day_key(resolved_key)

        nav_row = []

        if prev_key:
            nav_row.append(
                InlineKeyboardButton(
                    text=" ",
                    callback_data=f"daynav123:{prev_key}",
                    style="default",
                    icon_custom_emoji_id="5805509901048356965"
                )
            )

        nav_row.append(
            InlineKeyboardButton(
                text=_day_label(target_day),
                callback_data="daynoop123",
                style="default",
                icon_custom_emoji_id="5274055917766202507"
            )
        )

        if next_key:
            nav_row.append(
                InlineKeyboardButton(
                    text=" ",
                    callback_data=f"daynav123:{next_key}",
                    style="default",
                    icon_custom_emoji_id="5807453545548487345"
                )
            )

        if prev_key or next_key:
            rows.append(nav_row)

    elif active == "week":
        nav = await _get_week_nav_info(chat_id, week_key)
        resolved_key = nav["resolved_key"]
        prev_key = nav["prev_key"]
        next_key = nav["next_key"]

        week_start_date = _parse_week_key(resolved_key)

        nav_row = []

        if prev_key:
            nav_row.append(
                InlineKeyboardButton(
                    text=" ",
                    callback_data=f"weeknav123:{prev_key}",
                    style="default",
                    icon_custom_emoji_id="5805509901048356965"
                )
            )

        nav_row.append(
            InlineKeyboardButton(
                text=_week_label_from_start(week_start_date),
                callback_data="weeknoop123",
                style="default",
                icon_custom_emoji_id="5274055917766202507"
            )
        )

        if next_key:
            nav_row.append(
                InlineKeyboardButton(
                    text=" ",
                    callback_data=f"weeknav123:{next_key}",
                    style="default",
                    icon_custom_emoji_id="5807453545548487345"
                )
            )

        if prev_key or next_key:
            rows.append(nav_row)

    elif active == "month":
        nav = await _get_month_nav_info(chat_id, month_key)
        resolved_key = nav["resolved_key"]
        prev_key = nav["prev_key"]
        next_key = nav["next_key"]

        year, month = _parse_month_key(resolved_key)

        nav_row = []

        if prev_key:
            nav_row.append(
                InlineKeyboardButton(
                    text=" ",
                    callback_data=f"monthnav123:{prev_key}",
                    style="default",
                    icon_custom_emoji_id="5805509901048356965"
                )
            )

        nav_row.append(
            InlineKeyboardButton(
                text=f"{_month_label(year, month)}",
                callback_data="monthnoop123",
                style="default",
                icon_custom_emoji_id="5274055917766202507"
            )
        )

        if next_key:
            nav_row.append(
                InlineKeyboardButton(
                    text=" ",
                    callback_data=f"monthnav123:{next_key}",
                    style="default",
                    icon_custom_emoji_id="5807453545548487345"
                )
            )

        if prev_key or next_key:
            rows.append(nav_row)

    rows.append([btn_back])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# =========================================================
# ТЕКСТЫ
# =========================================================

async def _stat_text_day(chat_id: int, user_id: int, day_key: Optional[str] = None, limit: int = 30) -> str:
    nav = await _get_day_nav_info(chat_id, day_key)
    resolved_key = nav["resolved_key"]
    target_day = _parse_day_key(resolved_key)
    day_str = target_day.strftime("%Y-%m-%d")

    top_users = await db.get_top_users_by_day(chat_id, day_str, limit=limit)
    total_messages = await db.get_total_messages_by_day(chat_id, day_str)
    user_msg_count = await db.get_user_message_count_by_day(chat_id, user_id, day_str)
    max_messages_user = await db.find_user_with_max_messages_by_day(chat_id, day_str)

    text = (
        f"<tg-emoji emoji-id='5424987025667293801'>🐰</tg-emoji> <b>Статистика сообщений за день</b> <code>[{_day_label(target_day)}]</code>\n"
        f"<tg-emoji emoji-id='5193136281483254509'>🦅</tg-emoji> <b>Вы написали :</b> <i>{_fmt_int(user_msg_count)}</i>\n\n"
    )

    member_count = await _safe_member_count(chat_id)

    top_ids = [_extract_top_row(row)[0] for row in top_users] if top_users else []
    max_uid = max_cnt = None
    if max_messages_user is not None:
        max_uid, max_cnt = _extract_top_row(max_messages_user)
    names_bulk = await db.get_names_bulk(top_ids + ([max_uid] if max_uid is not None else []))

    if max_messages_user is not None and member_count >= 1000:
        max_user_link = _link_from_names_bulk(max_uid, names_bulk)

        text += (
            f"👑 <b><i>{max_user_link}</i> - царь статистики!</b>\n"
            f"🏆 <b>{_fmt_int(max_cnt)}</b> сообщений за день\n\n"
        )

    if top_users:
        for rank, row in enumerate(top_users, start=1):
            uid, cnt = _extract_top_row(row)
            name_link = _link_from_names_bulk(uid, names_bulk)

            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {_fmt_int(cnt)}</b>\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{_fmt_int(cnt)}</b>\n"
    else:
        text += "За выбранный день сообщений пока нет.\n"

    text += f"\n<tg-emoji emoji-id='5364231788392641533'>❤️</tg-emoji> <b>Всего в чате:</b> <i>{_fmt_int(total_messages)}</i> сообщений"
    return text


async def _stat_text_week(chat_id: int, user_id: int, week_key: Optional[str] = None, limit: int = 30) -> str:
    nav = await _get_week_nav_info(chat_id, week_key)
    resolved_key = nav["resolved_key"]
    week_start_date = _parse_week_key(resolved_key)
    week_end_date = week_start_date + timedelta(days=6)

    date_from = week_start_date.strftime("%Y-%m-%d")
    date_to = week_end_date.strftime("%Y-%m-%d")

    top_users = await db.get_top_users_by_period(chat_id, date_from, date_to, limit=limit)
    total_messages = await db.get_total_messages_by_period(chat_id, date_from, date_to)
    user_msg_count = await db.get_user_message_count_by_period(chat_id, user_id, date_from, date_to)
    max_messages_user = await db.find_user_with_max_messages_by_period(chat_id, date_from, date_to)

    period_str = f"{week_start_date.strftime('%d.%m.%Y')} - {week_end_date.strftime('%d.%m.%Y')}"

    text = (
        f"<tg-emoji emoji-id='5438529285184847871'>🎁</tg-emoji> <b>Статистика сообщений за неделю</b> <code>[{period_str}]</code>\n"
        f"<tg-emoji emoji-id='5246815104871201488'>🐒</tg-emoji> <b>Вы написали :</b> <i>{_fmt_int(user_msg_count)}</i>\n\n"
    )

    member_count = await _safe_member_count(chat_id)

    top_ids = [_extract_top_row(row)[0] for row in top_users] if top_users else []
    max_uid = max_cnt = None
    if max_messages_user is not None:
        max_uid, max_cnt = _extract_top_row(max_messages_user)
    names_bulk = await db.get_names_bulk(top_ids + ([max_uid] if max_uid is not None else []))

    if max_messages_user is not None and member_count >= 1000:
        max_link = _link_from_names_bulk(max_uid, names_bulk)

        text += (
            f"👑 <b><i>{max_link}</i> - царь статистики!</b>\n"
            f"🏆 <b>{_fmt_int(max_cnt)}</b> сообщений за неделю\n\n"
        )

    if top_users:
        for rank, row in enumerate(top_users, start=1):
            uid, cnt = _extract_top_row(row)
            name_link = _link_from_names_bulk(uid, names_bulk)

            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {_fmt_int(cnt)}</b>\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{_fmt_int(cnt)}</b>\n"
    else:
        text += "За выбранную неделю сообщений пока нет.\n"

    text += f"\n<tg-emoji emoji-id='5309894469208801769'>🎁</tg-emoji> <b>Всего в чате:</b> <i>{_fmt_int(total_messages)}</i> сообщений"
    return text


async def _stat_text_month(chat_id: int, user_id: int, month_key: Optional[str] = None, limit: int = 30) -> str:
    nav = await _get_month_nav_info(chat_id, month_key)
    resolved_key = nav["resolved_key"]
    month_keys = nav["month_keys"]

    year, month = _parse_month_key(resolved_key)

    if not month_keys:
        return (
            f"<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> <b>Статистика сообщений за месяц</b> <code>[{_month_range_label(year, month)}]</code>\n\n"
            f"<tg-emoji emoji-id='5436371618169389408'>🎁</tg-emoji> В базе пока нет данных по месяцам для этого чата."
        )

    top_users = await db.get_top_users_month(chat_id, year, month, limit=limit)
    total_messages = await db.get_total_messages_month(chat_id, year, month)
    user_msg_count = await db.get_user_message_count_month(chat_id, user_id, year, month)
    max_messages_user = await db.find_user_with_max_messages_month(chat_id, year, month)

    text = (
        f"<tg-emoji emoji-id='5438440765908874600'>🎁</tg-emoji> <b>Статистика сообщений за месяц</b> <code>[{_month_range_label(year, month)}]</code>\n"
        f"<tg-emoji emoji-id='5436371618169389408'>🎁</tg-emoji> <b>Вы написали :</b> <i>{_fmt_int(user_msg_count)}</i>\n\n"
    )

    member_count = await _safe_member_count(chat_id)

    top_ids = [_extract_top_row(row)[0] for row in top_users] if top_users else []
    max_uid = max_cnt = None
    if max_messages_user is not None:
        max_uid, max_cnt = _extract_top_row(max_messages_user)
    names_bulk = await db.get_names_bulk(top_ids + ([max_uid] if max_uid is not None else []))

    if max_messages_user is not None and member_count >= 1000:
        max_link = _link_from_names_bulk(max_uid, names_bulk)

        text += (
            f"👑 <b><i>{max_link}</i> - царь статистики месяца!</b>\n"
            f"🏆 <b>{_fmt_int(max_cnt)}</b> сообщений за месяц\n\n"
        )

    if top_users:
        for rank, row in enumerate(top_users, start=1):
            uid, cnt = _extract_top_row(row)
            name_link = _link_from_names_bulk(uid, names_bulk)

            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {_fmt_int(cnt)}</b>\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{_fmt_int(cnt)}</b>\n"
    else:
        text += "За выбранный месяц сообщений не найдено.\n"

    text += f"\n<tg-emoji emoji-id='5436312493649591162'>🎁</tg-emoji> <b>Всего в чате:</b> <i>{_fmt_int(total_messages)}</i> сообщений"
    return text


async def _stat_text_all(chat_id: int, user_id: int, limit: int = 30) -> str:
    top_users = await db.get_top_users1(chat_id, limit=limit)
    total_messages = await db.get_total_messages(chat_id)
    user_msg_count = await db.get_user_message_count(chat_id, user_id)
    max_messages_user = await db.find_user_with_max_messages_all(chat_id)

    text = (
        f"<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> <b>Статистика сообщений за всё время</b>\n"
        f"<tg-emoji emoji-id='5318872213577834693'>🎒</tg-emoji> <b>Вы написали :</b> <i>{_fmt_int(user_msg_count)}</i>\n\n"
    )

    member_count = await _safe_member_count(chat_id)

    top_ids = [_extract_top_row(row)[0] for row in top_users] if top_users else []
    max_uid = max_cnt = None
    if max_messages_user is not None:
        max_uid, max_cnt = _extract_top_row(max_messages_user)
    names_bulk = await db.get_names_bulk(top_ids + ([max_uid] if max_uid is not None else []))

    if max_messages_user is not None and member_count >= 1000:
        max_link = _link_from_names_bulk(max_uid, names_bulk)

        text += (
            f"👑 <b><i>{max_link}</i> - царь статистики!</b>\n"
            f"🏆 <b>{_fmt_int(max_cnt)}</b> сообщений за всё время\n\n"
        )

    if top_users:
        for rank, row in enumerate(top_users, start=1):
            uid, cnt = _extract_top_row(row)
            name_link = _link_from_names_bulk(uid, names_bulk)

            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {_fmt_int(cnt)}</b>\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{_fmt_int(cnt)}</b>\n"
    else:
        text += "За всё время сообщений пока нет.\n"

    text += f"\n<tg-emoji emoji-id='5247000905156419417'>🧞‍♂️</tg-emoji> <b>Всего в чате:</b> <i>{_fmt_int(total_messages)}</i> сообщений"
    return text


# =========================================================
# GUARD
# =========================================================

async def _guard_can_edit(call: types.CallbackQuery) -> bool:
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    message_id = call.message.message_id

    try:
        current_stata = await db.get_current_stata(chat_id)
    except Exception as e:
        print(f"Ошибка при получении current_stata для chat_id {chat_id}: {e}")
        current_stata = 1

    if current_stata == 0:
        await call.answer("⚠️ Статистика сейчас выключена", show_alert=True)
        return False

    hint = random.choice(randommessagehelp)

    if user_id not in user_top or user_top.get(user_id) != message_id:
        await call.answer(hint)
        return False

    await call.answer()
    return True


# =========================================================
# CALLBACKS
# =========================================================

@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("state123"))
async def cb_stats_today(call: types.CallbackQuery):
    if not await _guard_can_edit(call):
        return

    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        day_key = None
        parts = str(call.data).split(":", 1)
        if len(parts) == 2 and parts[1].strip():
            day_key = parts[1].strip()

        day_key = await _resolve_valid_day_key(chat_id, day_key)

        text = await _stat_text_day(chat_id, user_id, day_key=day_key, limit=30)
        kb = await _kb_stats(chat_id=chat_id, active="day", day_key=day_key)
        await _safe_edit_stats_message(call, text, kb)

    except Exception as e:
        print(f"❌ Произошла ошибка в cb_stats_today: {e}")
        await call.answer("⚠️ Не удалось открыть статистику за день", show_alert=False)


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("daynav123:"))
async def cb_stats_day_nav(call: types.CallbackQuery):
    if not await _guard_can_edit(call):
        return

    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        day_key = None
        parts = str(call.data).split(":", 1)
        if len(parts) == 2 and parts[1].strip():
            day_key = parts[1].strip()

        day_key = await _resolve_valid_day_key(chat_id, day_key)

        text = await _stat_text_day(chat_id, user_id, day_key=day_key, limit=30)
        kb = await _kb_stats(chat_id=chat_id, active="day", day_key=day_key)
        await _safe_edit_stats_message(call, text, kb)

    except Exception as e:
        print(f"❌ Произошла ошибка в cb_stats_day_nav: {e}")
        await call.answer("⚠️ Не удалось переключить день", show_alert=False)


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data == "daynoop123")
async def cb_stats_day_noop(call: types.CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("weekstate123"))
async def cb_stats_week(call: types.CallbackQuery):
    if not await _guard_can_edit(call):
        return

    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        week_key = None
        parts = str(call.data).split(":", 1)
        if len(parts) == 2 and parts[1].strip():
            week_key = parts[1].strip()

        week_key = await _resolve_valid_week_key(chat_id, week_key)

        text = await _stat_text_week(chat_id, user_id, week_key=week_key, limit=30)
        kb = await _kb_stats(chat_id=chat_id, active="week", week_key=week_key)
        await _safe_edit_stats_message(call, text, kb)

    except Exception as e:
        print(f"❌ Произошла ошибка в cb_stats_week: {e}")
        await call.answer("⚠️ Не удалось открыть статистику за неделю", show_alert=False)


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("weeknav123:"))
async def cb_stats_week_nav(call: types.CallbackQuery):
    if not await _guard_can_edit(call):
        return

    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        week_key = None
        parts = str(call.data).split(":", 1)
        if len(parts) == 2 and parts[1].strip():
            week_key = parts[1].strip()

        week_key = await _resolve_valid_week_key(chat_id, week_key)

        text = await _stat_text_week(chat_id, user_id, week_key=week_key, limit=30)
        kb = await _kb_stats(chat_id=chat_id, active="week", week_key=week_key)
        await _safe_edit_stats_message(call, text, kb)

    except Exception as e:
        print(f"❌ Произошла ошибка в cb_stats_week_nav: {e}")
        await call.answer("⚠️ Не удалось переключить неделю", show_alert=False)


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data == "weeknoop123")
async def cb_stats_week_noop(call: types.CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("monthstate123"))
async def cb_stats_month(call: types.CallbackQuery):
    if not await _guard_can_edit(call):
        return

    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        month_key = None
        parts = str(call.data).split(":", 1)
        if len(parts) == 2 and parts[1].strip():
            month_key = parts[1].strip()

        month_key = await _resolve_valid_month_key(chat_id, month_key)

        text = await _stat_text_month(chat_id, user_id, month_key=month_key, limit=30)
        kb = await _kb_stats(chat_id=chat_id, active="month", month_key=month_key)
        await _safe_edit_stats_message(call, text, kb)

    except Exception as e:
        print(f"❌ Произошла ошибка в cb_stats_month: {e}")
        await call.answer("⚠️ Не удалось открыть статистику за месяц", show_alert=False)


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("monthnav123:"))
async def cb_stats_month_nav(call: types.CallbackQuery):
    if not await _guard_can_edit(call):
        return

    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        month_key = None
        parts = str(call.data).split(":", 1)
        if len(parts) == 2 and parts[1].strip():
            month_key = parts[1].strip()

        month_keys = await _get_available_month_keys(chat_id)

        if not month_keys:
            await call.answer("ℹ️ В базе пока нет статистики по месяцам", show_alert=True)
            return

        if month_key not in month_keys:
            await call.answer("⚠️ Для выбранного месяца нет данных", show_alert=False)
            month_key = await _resolve_valid_month_key(chat_id, None)

        text = await _stat_text_month(chat_id, user_id, month_key=month_key, limit=30)
        kb = await _kb_stats(chat_id=chat_id, active="month", month_key=month_key)
        await _safe_edit_stats_message(call, text, kb)

    except Exception as e:
        print(f"❌ Произошла ошибка в cb_stats_month_nav: {e}")
        await call.answer("⚠️ Не удалось переключить месяц", show_alert=False)


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data == "monthnoop123")
async def cb_stats_month_noop(call: types.CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass


@dp.callback_query(lambda c: isinstance(c.data, str) and c.data == "fullstate123")
async def cb_stats_all(call: types.CallbackQuery):
    if not await _guard_can_edit(call):
        return

    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        text = await _stat_text_all(chat_id, user_id, limit=30)
        kb = await _kb_stats(chat_id=chat_id, active="all")
        await _safe_edit_stats_message(call, text, kb)

    except Exception as e:
        print(f"❌ Произошла ошибка в cb_stats_all: {e}")
        await call.answer("⚠️ Не удалось открыть статистику за всё время", show_alert=False)


# =========================================================
# ОТКРЫТИЕ МЕНЮ СТАТИСТИКИ
# =========================================================

async def open_stats_message(message: types.Message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id

        day_key = await _resolve_valid_day_key(chat_id, None)

        text = await _stat_text_day(chat_id, user_id, day_key=day_key, limit=30)
        kb = await _kb_stats(chat_id=chat_id, active="day", day_key=day_key)

        sent = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb,
            disable_web_page_preview=True
        )

        user_top[user_id] = sent.message_id

    except Exception as e:
        print(f"❌ Ошибка при открытии статистики: {e}")
def format_marriage_duration(duration):
    years = duration.days // 365
    months = (duration.days % 365) // 30
    days = duration.days % 30
    hours = duration.seconds // 3600
    minutes = (duration.seconds % 3600) // 60
    seconds = duration.seconds % 60

    if years > 0:
        year_str = "год" if years == 1 else "года" if 2 <= years <= 4 else "лет"
        month_str = "месяц" if months == 1 else "месяца" if 2 <= months <= 4 else "месяцев"
        day_str = "день" if days == 1 else "дня" if 2 <= days <= 4 else "дней"
        return f"{years} {year_str} {months} {month_str} {days} {day_str} {hours} часов {minutes} минут"

    if months > 0:
        month_str = "месяц" if months == 1 else "месяца" if 2 <= months <= 4 else "месяцев"
        day_str = "день" if days == 1 else "дня" if 2 <= days <= 4 else "дней"
        if days == 0 and hours == 0:
            return f"{months} {month_str}"
        return f"{months} {month_str} {days} {day_str} {hours} часов {' ' if minutes == 0 or minutes >= 30 else ''}"

    if days > 0:
        day_str = "день" if days == 1 else "дня" if 2 <= days <= 4 else "дней"
        hour_str = "час" if hours == 1 else "часа" if 2 <= hours <= 4 else "часов"
        if hours == 0:
            if minutes == 0 or minutes >= 30:
                return f"{days} {day_str}"
            return f"{days} {day_str} {hours} {hour_str}"
        return f"{days} {day_str} {hours} {hour_str} {' ' if minutes >= 30 else ''}{minutes} минут"

    if hours > 0:
        hour_str = "час" if hours == 1 else "часа" if 2 <= hours <= 4 else "часов"
        if minutes == 0 or minutes >= 30:
            return f"{hours} {hour_str}"
        minute_str = "минута" if minutes == 1 else "минут" if minutes >= 2 else "минуты"
        return f"{hours} {hour_str} {minutes} {minute_str}"

    if minutes > 0 and minutes < 30:
        minute_str = "минута" if minutes == 1 else "минут" if minutes >= 2 else "минуты"
        second_str = "секунда" if seconds == 1 else "секунд" if seconds >= 2 else "секунды"
        return f"{minutes} {minute_str} {seconds} {second_str}"

    return f"{seconds} секунд"

@dp.callback_query(lambda c: c.data.startswith('topinvite'))
async def caasqscwqscqllback_top(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id


    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_top or user_top[user_id] != message_id:
        await call.answer(randommessagehelp1)
        return
    await call.answer()
    try:
        # Получаем данные пользователей: ID и количество приглашений
        data = await db.get_user_referrals()

        # Словарь с количеством приглашений
        user_referrals = {item[0]: item[1] for item in data if len(item) == 2 and item[1] is not None}

        # Сортируем пользователей по количеству приглашений (убывание)
        sorted_users = sorted(user_referrals.items(), key=lambda x: x[1], reverse=True)

        # Определяем позицию текущего пользователя в топе
        user_position = next(
            (i + 1 for i, (user, _) in enumerate(sorted_users) if user == user_id), None)

        # Формируем текст с позицией пользователя (обрабатываем None корректно)
        position_text = f"{user_position}" if user_position else "Не в топе"
        win_amount_formatted = "{:,.0f}".format(
            int(position_text) if position_text.isdigit() else 0).replace(",", ".")

        text = f"<tg-emoji emoji-id='5422386835286423005'>🧩</tg-emoji> <b>Статистика приглашений</b>\n" \
               f"<tg-emoji emoji-id='5192900470598833151'>🔰</tg-emoji> <b>Ваше место : <i>{win_amount_formatted}</i></b>\n\n"

        # Выводим информацию о топ-10 пользователях
        _names_bulk = await db.get_names_bulk(uid for uid, _ in sorted_users[:10])
        for rank, (user_id, referrals) in enumerate(sorted_users[:10], start=1):
            referrals_with_dots = locale.format_string("%d", referrals, grouping=True).replace(",", ".")

            # Получаем имя и username пользователя (batched)
            first_name, username = _names_bulk.get(user_id, (None, None))
            first_name = first_name or "Неизвестный"

            # Формируем ссылку на пользователя
            name_link = await create_user_link(user_id, first_name, username)

            # Выделяем только топ-3 участников
            if rank <= 3:
                text += f"<b>{rank}. {name_link} ─ {referrals_with_dots} чел.</b>\n\n"
            else:
                text += f"{rank}. {name_link} ─ <b>{referrals_with_dots}</b> чел.\n\n"

        # Отправляем сообщение с результатами
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=btn_backtop123, disable_web_page_preview=True)

    except Exception as e:
        print(f"Произошла ошибка при обработке запроса18: {e}")


@dp.callback_query(lambda c: c.data.startswith('marry1213'))
async def calskqdkqodkqowlback_top(call: types.CallbackQuery):

    top_10 = await db.get_marriages_top_10_ordered_by_duration()
    user_id = call.from_user.id
    message_id = call.message.message_id


    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_top or user_top [ user_id ] != message_id:
        await call.answer(randommessagehelp1)
        return
    await call.answer()

    # Проверяем, находится ли пользователь в числе топ-браков
    user_marriage_position = None
    for i , marriage in enumerate(top_10 , start=1):
        user_id1 , user_id2 , _ = marriage
        if user_id == user_id1 or user_id == user_id2:
            user_marriage_position = i
            break

    stats_message = "🌹 <b>Статистика браков</b>\n\n"

    # Добавляем позицию пользователя в сообщение, если он в топе
    if user_marriage_position is not None:
        stats_message += f"❤️‍🔥 Ваше место в топе: {user_marriage_position}\n\n"

    # Формирование сообщения о браках
    for i , marriage in enumerate(top_10 , start=1):
        user_id1 , user_id2 , marriage_datetime = marriage
        if isinstance(marriage_datetime , str):
            marriage_time = datetime.strptime(marriage_datetime , "%Y-%m-%d %H:%M:%S")
        else:
            marriage_time = marriage_datetime  # уже datetime, конвертировать не нужно
        marriage_duration = datetime.now() - marriage_time

        # Получаем имена пользователей
        first_name1 = await db.get_firstname_by_user_id(user_id1) or "Неизвестный"
        username1 = await db.get_username_by_user_id(user_id1)
        first_name2 = await db.get_firstname_by_user_id(user_id2) or "Неизвестный"
        username2 = await db.get_username_by_user_id(user_id2)

        # Создаем гиперссылки на пользователей
        user_link1 = await create_user_link(user_id1 , first_name1 , username1)
        user_link2 = await create_user_link(user_id2 , first_name2 , username2)

        formatted_duration = format_marriage_duration(marriage_duration)

        # Формируем строку с пользователями: выделяем только первые три брака
        if i <= 3:
            stats_message += f"<b>{i}. {user_link1} + {user_link2} ─ {formatted_duration}</b>\n\n"
        else:
            stats_message += f"{i}. {user_link1} + {user_link2} ─ {formatted_duration}\n\n"

    await call.message.edit_text(
        stats_message , reply_markup=btn_backtop123 , disable_web_page_preview=True , parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith('marrylovecoins'))
async def callcqdqkiwqback_top(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id


    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_top or user_top [ user_id ] != message_id:
        await call.answer(randommessagehelp1)
        return
    await call.answer()
    top_10 = await db.get_marriages_top_10_ordered_by_lovecoin()
    user_marriage_position = None

    # Проверяем, находится ли пользователь в числе топ-браков
    for i , marriage in enumerate(top_10 , start=1):
        user_id1 , user_id2 , xp1 = marriage
        if user_id == user_id1 or user_id == user_id2:
            user_marriage_position = i
            break

    stats_message = "❤️ Топ браков по LoveCoins\n"
    if user_marriage_position is not None:
        stats_message += f"💰 Ваше место в топе: {user_marriage_position}\n"

    # Формирование сообщения о браках
    for i , marriage in enumerate(top_10 , start=1):
        user_id1 , user_id2 , xp1 = marriage
        if xp1 > 0:
            first_name1 = await db.get_firstname_by_user_id(user_id1)
            username1 = await db.get_username_by_user_id(user_id1)
            first_name2 = await db.get_firstname_by_user_id(user_id2)
            username2 = await db.get_username_by_user_id(user_id2)

            # Создаем гиперссылки на пользователей

            win_amount_formatted = "{:,.0f}".format(xp1).replace("," , ".")

            # Создаем гиперссылки для пользователей
            user_link1 = await create_user_link(user_id1 , first_name1 , username1)
            user_link2 = await create_user_link(user_id2 , first_name2 , username2)

            stats_message += f"\n{i}. {user_link1} + {user_link2} ─ <b>{win_amount_formatted}</b> LoveCoins\n"

    # Рассчитываем количество страниц
    marriages_per_page = 10
    num_pages = math.ceil(len(top_10) / marriages_per_page)

    # Генерируем кнопки навигации для первой страницы
    navigation_buttons = await generate_buttons_marryxp(1 , num_pages)

    await call.message.edit_text(
        stats_message , reply_markup=btn_backtop123 ,  # Здесь можно добавить navigation_buttons для навигации
        disable_web_page_preview=True , parse_mode="HTML")
@dp.callback_query(lambda c: c.data.startswith('marryxp'))
async def callqjiqwjdiqjqback_top(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    randommessagehelp1 = random.choice(randommessagehelp)

    if user_id not in user_top or user_top[user_id] != message_id:
        await call.answer(randommessagehelp1)
        return
    await call.answer()

    try:
        # Получаем данные пользователей из базы данных
        data = await db.get_data_users()  # Обратите внимание на асинхронный вызов
        users_with_xp = []

        # Заполняем список пользователей с положительным опытом
        for item in data:
            if len(item) >= 2:  # Проверяем, что есть достаточно данных
                user_id_db, _ = item[0], item[1]
                xpppp = await db.get_marriages_xp(user_id_db)
                if xpppp > 0:
                    users_with_xp.append((user_id_db, xpppp))

        # Сортируем пользователей по опыту
        sorted_users = sorted(users_with_xp, key=lambda x: x[1], reverse=True)

        # Находим позицию пользователя в списке топ-пользователей
        user_position = next((i + 1 for i, (user, _) in enumerate(sorted_users) if user == user_id), None)

        # Формируем текст статистики
        if user_position is not None:
            win_amount_formatted = "{:,.0f}".format(user_position).replace(",", ".")
            text = f"⭐️ Статистика опыта\n✨ Ваше место в топе: <b>{win_amount_formatted}</b>\n\n"
        else:
            text = "⭐️ Статистика опыта\n✨ Вы не находитесь в топе.\n\n"

        # Выводим информацию о топ-пользователях (первые 10)
        rank = 1
        for user_id_db, balance in sorted_users[:10]:
            balance_with_dots = locale.format_string("%d", balance, grouping=True).replace(',', '.')

            # Получаем имя и username пользователя по его user_id
            first_name = await db.get_firstname_by_user_id(user_id_db)  # Обратите внимание на асинхронный вызов
            username = await db.get_username_by_user_id(user_id_db)  # Обратите внимание на асинхронный вызов

            # Формируем имя для отображения
            if first_name:
                name_to_display = html.escape(first_name)
            elif username:
                name_to_display = html.escape(username)
            else:
                name_to_display = f"Пользователь {user_id_db}"

            # Формируем ссылку на username, если он есть
            name_link = f'<a href="tg://user?id={user_id_db}">{name_to_display}</a>'

            # Добавляем информацию о пользователе в текст статистики
            text += f"{rank}. {name_link} ─ <b>{balance_with_dots}</b> XP\n\n"
            rank += 1

        # Редактируем сообщение с обновленным текстом статистики
        await call.message.edit_text(
            text,
            reply_markup=btn_backtop123,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Произошла ошибка при обработке запроса19: {e}")

@dp.callback_query(lambda c: isinstance(c.data, str) and c.data.startswith("backtop"))
async def sasadqqwdqwcallback_top(call: types.CallbackQuery):
    top_debug_print("════════════════════════════════════")
    top_debug_print("📥 [BACKTOP] callback-хэндлер вызван")

    try:
        if not call.from_user:
            top_debug_print("❌ [BACKTOP] call.from_user отсутствует")
            return

        user_id = call.from_user.id
        top_debug_print(f"👤 [BACKTOP] user_id={user_id}")

        if not call.message:
            top_debug_print("❌ [BACKTOP] call.message отсутствует")
            try:
                await call.answer("Ошибка сообщения", show_alert=True)
            except Exception:
                pass
            return

        message_id = call.message.message_id
        top_debug_print(f"🧷 [BACKTOP] message_id={message_id}")
        top_debug_print(f"🏷 [BACKTOP] callback_data={call.data!r}")

        randommessagehelp1 = random.choice(randommessagehelp)
        top_debug_print(f"🎲 [BACKTOP] randommessagehelp1={randommessagehelp1!r}")

        saved_message_id = user_top.get(user_id)
        top_debug_print(f"📂 [BACKTOP] user_top.get({user_id})={saved_message_id}")

        if user_id not in user_top or saved_message_id != message_id:
            top_debug_print("⛔ [BACKTOP] user_id не найден в user_top или message_id не совпал")
            try:
                await call.answer(randommessagehelp1)
            except Exception as e:
                top_debug_print(f"❌ [BACKTOP] Ошибка call.answer(randommessagehelp1): {e}")
            return

        try:
            await call.answer()
            top_debug_print("✅ [BACKTOP] call.answer() выполнен")
        except Exception as e:
            top_debug_print(f"❌ [BACKTOP] Ошибка call.answer(): {e}")

        # =========================================================
        # ВАЖНО: берём правильное эмодзи месяца / дня недели
        # =========================================================
        top_emoji = get_random_top_calendar_emoji()
        top_debug_print(f"🧪 [BACKTOP] top_emoji={top_emoji}")
        top_debug_print(f"🧪 [BACKTOP] repr(top_emoji)={repr(top_emoji)}")

        try:
            await call.message.edit_text(
                text=top_emoji,
                reply_markup=btn_top,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            top_debug_print("✅ [BACKTOP] Сообщение успешно изменено на правильное календарное эмодзи")
        except Exception as e:
            top_debug_print(f"❌ [BACKTOP] Ошибка edit_text: {e}")

            try:
                sent = await call.message.answer(
                    text=top_emoji,
                    reply_markup=btn_top,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                top_debug_print(f"🛟 [BACKTOP] Отправлен fallback message_id={sent.message_id}")

                try:
                    user_top[user_id] = sent.message_id
                    top_debug_print(f"💾 [BACKTOP] user_top[{user_id}] обновлён на {sent.message_id}")
                except Exception as e_save:
                    top_debug_print(f"❌ [BACKTOP] Ошибка сохранения нового message_id в user_top: {e_save}")

            except Exception as e2:
                top_debug_print(f"❌ [BACKTOP] Ошибка fallback answer(): {e2}")

        try:
            if hasattr(user_top, "save") and callable(user_top.save):
                user_top.save()
                top_debug_print("💾 [BACKTOP] user_top.save() выполнен")
            else:
                top_debug_print("ℹ️ [BACKTOP] У user_top нет метода save()")
        except Exception as e:
            top_debug_print(f"❌ [BACKTOP] Ошибка user_top.save(): {e}")

    except Exception as e:
        top_debug_print(f"❌ [BACKTOP] Критическая ошибка: {e}")
        try:
            await call.answer("Ошибка обработчика", show_alert=True)
        except Exception:
            pass

    top_debug_print("🏁 [BACKTOP] Обработка завершена")
    top_debug_print("════════════════════════════════════")



@dp.callback_query(lambda c: c.data.startswith('help_deletestate'))
async def calljiqwjicqjqback_top(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id




        randommessagehelp1 = random.choice(randommessagehelp)

        if user_id not in user_top or user_top [ user_id ] != message_id:
            await call.answer(randommessagehelp1)
            return
        await call.answer("Сообщение удалено")
        await call.message.delete()


    except Exception as e:
        print(f"Произошла ошибка при обработке запроса17: {e}")


# Обработчик callback-запросов для пагинации браков
@dp.callback_query(lambda call: call.data.startswith("next_pagemarry_") or call.data.startswith("prev_pagemarry_"))
async def handle_marry_pagination(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id


    randommessagebonus1 = random.choice(randommessagehelp)
    if user_id not in user_top or user_top [ user_id ] != message_id:
        await call.answer(randommessagebonus1)
        return
    await call.answer()
    try:
        page_number = int(call.data.split("_")[2])  # Извлекаем номер страницы из callback_data
    except IndexError:
        return

    # Получаем топ-10 браков, отсортированных по длительности
    top_10 = await db.get_marriages_top_10_ordered_by_duration()
    num_marriages = len(top_10)
    user_id = call.from_user.id
    user_marriage_position = None

    # Определяем позицию пользователя в топе браков
    for i, marriage in enumerate(top_10, start=1):
        user_id1, user_id2, _ = marriage
        if user_id == user_id1 or user_id == user_id2:
            user_marriage_position = i
            break

    # Настройка пагинации
    marriages_per_page = 10
    num_pages = math.ceil(num_marriages / marriages_per_page)

    # Определяем текущую страницу на основе позиции пользователя
    if user_marriage_position is not None:
        current_page = math.ceil(user_marriage_position / marriages_per_page)
    else:
        current_page = 1

    # Вычисляем начальный и конечный индексы для текущей страницы
    start_index = (page_number - 1) * marriages_per_page
    end_index = min(start_index + marriages_per_page, num_marriages)

    stats_message = "🌹 Топ браков:\n"
    if user_marriage_position is not None:
        stats_message += f"❤️‍🔥 Ваше место в топе: {user_marriage_position}\n"

    # Выводим браки для текущей страницы
    for i in range(start_index, end_index):
        user_id1, user_id2, marriage_datetime = top_10[i]
        marriage_time = datetime.strptime(marriage_datetime, "%Y-%m-%d %H:%M:%S")
        marriage_duration = datetime.now() - marriage_time
        username1 = await db.get_username_by_user_id(user_id1)
        username2 = await db.get_username_by_user_id(user_id2)
        formatted_duration = format_marriage_duration(marriage_duration)
        stats_message += f"\n{i + 1}. {username1 or user_id1} + {username2 or user_id2} ─ {formatted_duration}\n"

    # Генерируем кнопки навигации для новой страницы
    navigation_buttons = await generate_buttons_marry(page_number, num_pages)

    await call.message.edit_text(
        stats_message, disable_web_page_preview=True, parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[navigation_buttons])
    )


@dp.callback_query(lambda call: call.data.startswith("next_pagemarryxp_") or call.data.startswith("prev_pagemarryxp_"))
async def handle_marryxp_pagination(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id


    randommessagebonus1 = random.choice(randommessagehelp)


    if user_id not in user_top or user_top [ user_id ] != message_id:
        await call.answer(randommessagebonus1)
        return
    await call.answer()
    try:
        page_number = int(call.data.split("_")[2])
    except IndexError:
        return

    top_10 = await db.get_marriages_top_10_ordered_by_xp()
    num_marriages = len(top_10)
    user_id = call.from_user.id
    user_marriage_position = None

    # Check if the user is involved in any of the top marriages
    for i, marriage in enumerate(top_10, start=1):
        user_id1, user_id2, xp1 = marriage
        if user_id == user_id1 or user_id == user_id2:
            user_marriage_position = i
            break

    marriages_per_page = 5
    num_pages = math.ceil(num_marriages / marriages_per_page)

    # Determine current page based on user's marriage position
    if user_marriage_position is not None:
        current_page = math.ceil(user_marriage_position / marriages_per_page)
    else:
        current_page = 1

    # Calculate start and end indices for current page
    start_index = (page_number - 1) * marriages_per_page
    end_index = min(start_index + marriages_per_page, num_marriages)

    stats_message = "⭐️ Топ браков по опыту\n"
    if user_marriage_position is not None:
        stats_message += f"✨ Ваше место в топе: {user_marriage_position}\n"

    # Display marriages for the current page
    for i in range(start_index, end_index):
        user_id1, user_id2, xp1 = top_10[i]
        username1 = await db.get_username_by_user_id(user_id1)
        username2 = await db.get_username_by_user_id(user_id2)
        win_amount_formatted = "{:,.0f}".format(xp1).replace("," , ".")
        stats_message += f"\n{i}. {username1 or user_id1} + {username2 or user_id2} ─ <b>{win_amount_formatted}</b> ⭐️\n"

    # Generate navigation buttons for the new page
    navigation_buttons = await generate_buttons_marryxp(page_number, num_pages)

    await call.message.edit_text(
        stats_message, disable_web_page_preview=True, parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[navigation_buttons])
    )


