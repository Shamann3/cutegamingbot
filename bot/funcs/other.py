import random
from main import *

import pyowm
from datetime import datetime, timedelta
from google_trans_new import google_translator
from datetime import datetime
from yandex.Translater import Translater
from googletrans import Translator
from deep_translator import GoogleTranslator
from aiogram.enums import ParseMode, ChatType  # Импортируем ParseMode из aiogram.enums
from langdetect import detect
import langid
import praw
import requests
import re
import pytz
import requests
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import geonamescache
import itertools
from transliterate import translit, detect_language
import asyncio

from translate import Translator
from better_profanity import profanity


from aiogram.types import ChatPermissions
import datetime as dt
import datetime
import traceback
import requests
import aiohttp
from datetime import datetime
import datetime
from bs4 import BeautifulSoup
from langdetect import detect, DetectorFactory
import pytz
from email.utils import parsedate_to_datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dateutil import parser

from main import *

shown_books = set()
BASE_URL = 'https://some-random-api.ml'
owm = pyowm.OWM('0b24008b13ce7a86e9f86bbf0c667d67')
GEONAMES_USERNAME = 'shamann3412q'
weather_manager = owm.weather_manager()

current_time = time.time()
RESTcute = 1
cute3 = {}
cute_time = {}
profanity.load_censor_words()

gc = geonamescache.GeonamesCache()
cities = [city['name'] for city in gc.get_cities().values()]

def format_number(number):
    return "{:,.0f}".format(number).replace(',', '.')

def get_time_of_day1(hour):
    if 0 <= hour < 1:
        return "Полночь"
    elif 1 <= hour < 5:
        return "Ночь"
    elif 6 <= hour < 9:
        return "Раннее утро"
    elif 9 <= hour < 12:
        return "Утро"
    elif 12 <= hour < 15:
        return "День"
    elif 15 <= hour < 18:
        return "Обед"
    elif 18 <= hour < 22:
        return "Вечер"
    else:  # 22 <= hour < 24
        return "Поздний вечер"


def get_time_of_day2(hour):
    if 0 <= hour < 1:
        return "Полночь"
    elif 1 <= hour < 5:
        return "Ночь"
    elif 6 <= hour < 9:
        return "Ран. утро"
    elif 9 <= hour < 12:
        return "Утро"
    elif 12 <= hour < 15:
        return "День"
    elif 15 <= hour < 18:
        return "Обед"
    elif 18 <= hour < 22:
        return "Вечер"
    else:  # 22 <= hour < 24
        return "Поздн. вечер"


def get_weather_emoji(weather_status):
    translations = {
        'Clear': 'Ясно',
        'Night': 'Ночь',
        'Clouds': 'Облачно',
        'Partly Cloudy': 'Переменная облачность',
        'Cloudy': 'Облачно',
        'Sunny': 'Солнечно',
        'Rain': 'Дождь',
        'Thunderstorm': 'Гроза',
        'Snow': 'Снег',
        'Mist': 'Туман',
    }

    emoji_translations = {
        'Ясно': '🔆',
        'Ночь': '🌙',
        'Облачно': '☁️',
        'Переменная облачность': '🌥',
        'Солнечно': '🔆',
        'Дождь': '🌧',
        'Гроза': '⛈',
        'Снег': '❄️',
        'Туман': '😶‍🌫️',
    }
    return emoji_translations.get(translations.get(weather_status, ''),
                                  '🌈')  # По умолчанию используется радуга, если статус не распознан



def _normalize_city_name(raw: str) -> str:
    """
    Нормализуем ввод пользователя:
    - убираем лишние пробелы
    - приводим слова к Title Case
    - корректно обрабатываем дефисы (Санкт-Петербург / Лос-Анджелес)
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    # заменим тире на дефис и схлопнем пробелы
    parts = [p for p in raw.replace("-", "-").replace("–", "-").split() if p]
    pretty = " ".join(parts)

    def _title_hyphen(chunk: str) -> str:
        return "-".join(s.capitalize() for s in chunk.split("-"))

    return " ".join(_title_hyphen(w) for w in pretty.split(" "))

def get_city_time(city_name: str) -> str:
    """
    Возвращает HTML-строку:
      <b>dd.mm.yyyy</b>\n<b>HH:MM:SS</b>
    либо короткое сообщение об ошибке.
    """
    # Локальный alias, чтобы не конфликтовать с любыми глобальными импортами datetime
    from datetime import datetime as _dt

    try:
        city_pretty = _normalize_city_name(city_name)
        if not city_pretty:
            return "⚠️ Пожалуйста, укажите город после команды «время»."

        geolocator = Nominatim(user_agent="CuteGamingBot-TimeLookup/1.0", timeout=10)
        location = geolocator.geocode(city_pretty)
        if not location:
            return "⚠️ Не удалось найти такой город. Уточни название."

        tz_name = TimezoneFinder().timezone_at(lng=location.longitude, lat=location.latitude)
        if not tz_name:
            return "⚠️ Для этого места не удалось определить часовой пояс."

        now = _dt.now(pytz.timezone(tz_name))
        return now.strftime("<b>%d.%m.%Y</b>\n<b>%H:%M:%S</b>")

    except pytz.UnknownTimeZoneError:
        return "⚠️ Неизвестный часовой пояс для указанного города."
    except Exception:
        # Без лишних подробностей - просто мягкая ошибка
        return "⚠️ Внутренняя ошибка при определении времени. Попробуй ещё раз."


joined_users = {}


async def update_join_date(user_id):
    if user_id not in joined_users:
        joined_users[user_id] = datetime.datetime.now()

@dp.message()
async def other(message: Message):

    # Это catch-all обработчик-фолбэк для ТЕКСТОВЫХ команд (время, кут скажи и т.п.).
    # Любое сообщение без текста (фото, стикер, голос, сервисные сообщения и др.)
    # раньше падало здесь на message.text.lower() → AttributeError: 'NoneType'.
    # Такие сообщения уже обрабатываются профильными системами (мут/варн/бан/кик
    # и игровыми хендлерами) выше по цепочке, поэтому здесь их просто пропускаем.
    if not message.from_user or not message.text:
        return

    linkk = f"https://t.me/{message.from_user.username}"
    options = ['орел', 'решка']
    words = message.text.lower().split()
    if len(words) >= 2 and (words [ 0 ] == 'время' or (words [ 0 ] == 'кут' and words [ 1 ] == 'время')):
        if words [ 0 ] == 'время':
            city_name = words [ 1 ]
        elif words [ 0 ] == 'кут' and words [ 1 ] == 'время':
            city_name = words [ 2 ] if len(words) > 2 else None

        if city_name:
            time_result = get_city_time(city_name)
            await message.reply(
                f'''
📡 <b><i>Точное время в городе {city_name.capitalize()}</i></b>
{time_result}''' , parse_mode="HTML" , disable_web_page_preview=True)
        else:
            await message.reply(
                "⚠️ Пожалуйста, укажите город после команды 'время'." , parse_mode="HTML" ,
                disable_web_page_preview=True)




    #flag_emoji = {
      #  'ru': '🇷🇺' ,  # Россия
      #  'uk': '🇺🇦' ,  # Украина
      #  'al': '🇦🇱' ,  # Албания
      #  'ad': '🇦🇩' ,  # Андорра
      #  'at': '🇦🇹' ,  # Австрия
      #  'by': '🇧🇾' ,  # Беларусь
      #  'be': '🇧🇪' ,  # Бельгия
      #  'ba': '🇧🇦' ,  # Босния и Герцеговина
      #  'bg': '🇧🇬' ,  # Болгария
      #  'hr': '🇭🇷' ,  # Хорватия
     #   'cy': '🇨🇾' ,  # Кипр
     #   'cz': '🇨🇿' ,  # Чехия
     #   'dk': '🇩🇰' ,  # Дания
     #   'ee': '🇪🇪' ,  # Эстония
     #   'fo': '🇫🇴' ,  # Фарерские острова
     #   'fi': '🇫🇮' ,  # Финляндия
     #   'fr': '🇫🇷' ,  # Франция
    #    'de': '🇩🇪' ,  # Германия
     #   'gi': '🇬🇮' ,  # Гибралтар
    #    'gr': '🇬🇷' ,  # Греция
    # #   'gg': '🇬🇬' ,  # Гернси
    #    'hu': '🇭🇺' ,  # Венгрия
    #    'is': '🇮🇸' ,  # Исландия
     #   'ie': '🇮🇪' ,  # Ирландия
    #    'im': '🇮🇲' ,  # Остров Мэн
    #    'it': '🇮🇹' ,  # Италия
    #    'je': '🇯🇪' ,  # Джерси
    #    'xk': '🇽🇰' ,  # Косово
    #    'lv': '🇱🇻' ,  # Латвия
    #    'li': '🇱🇮' ,  # Лихтенштейн
     #   'lt': '🇱🇹' ,  # Литва
     #   'lu': '🇱🇺' ,  # Люксембург
     #   'mk': '🇲🇰' ,  # Северная Македония
     #   'mt': '🇲🇹' ,  # Мальта
     #   'md': '🇲🇩' ,  # Молдавия
     #   'mc': '🇲🇨' ,  # Монако
     #   'me': '🇲🇪' ,  # Черногория
     #   'nl': '🇳🇱' ,  # Нидерланды
      #  'no': '🇳🇴' ,  # Норвегия
     #   'pl': '🇵🇱' ,  # Польша
    #    'pt': '🇵🇹' ,  # Португалия
    #    'ro': '🇷🇴' ,  # Румыния
    #    'sm': '🇸🇲' ,  # Сан-Марино
    #    'rs': '🇷🇸' ,  # Сербия
   #     'sk': '🇸🇰' ,  # Словакия
    #    'si': '🇸🇮' ,  # Словения
   #     'es': '🇪🇸' ,  # Испания
    #    'se': '🇸🇪' ,  # Швеция
    #    'ch': '🇨🇭' ,  # Швейцария
   #     'ua': '🇺🇦' ,  # Украина
   #     'gb': '🇬🇧' ,  # Великобритания
 #       'va': '🇻🇦' ,  # Ватикан
#    }

    def translate_weather_status(current_status: str) -> str:
        """
        Перевод статусов погоды на русский. Если нет перевода - возвращаем оригинал.
        """
        translation_dict = {'Clear': 'Ясно' , 'Night': 'Ночь' , 'Clouds': 'Облачно' ,
            'Partly Cloudy': 'Переменная облачность' , 'Cloudy': 'Облачно' , 'Sunny': 'Солнечно' , 'Rain': 'Дождь' ,
            'Thunderstorm': 'Гроза' , 'Snow': 'Снег' , 'Mist': 'Туман' , 'Fog': 'Туман' , 'Drizzle': 'Морось' ,
            'Haze': 'Дымка' , 'Sleet': 'Мокрый снег' , }
        return translation_dict.get((current_status or '').strip() , current_status or '')

    def get_time_of_day_emoji() -> str:
        """
        Эмодзи времени суток по локальным системным часам.
        """
        current_hour = dt.datetime.now().hour
        if 6 <= current_hour < 20:  # День
            styles_day = [ [ "🌅" , "🌄" , "🌇" , "🌆" , "🏞" , "🌅" , "🌄" ] ]
            selected_style = random.choice(styles_day)
            return random.choice(selected_style)
        else:  # Ночь
            styles_night = [ [ "🌃" , "🌌" , "🌉" , "🎇" , "🌑" , "🌠" , "🎆" , "🌌" , "🌃" ] ]
            selected_style = random.choice(styles_night)
            return random.choice(selected_style)

    def get_time_of_day_label(hour: int) -> str:
        """
        Короткая подпись времени суток по часу [0..23].
        """
        try:
            h = int(hour)
        except Exception:
            h = 0
        if 5 <= h < 12:
            return "утро"
        if 12 <= h < 17:
            return "день"
        if 17 <= h < 22:
            return "вечер"
        return "ночь"

    def get_weather_emoji(status: str) -> str:
        """
        Простейший маппинг статусов → эмодзи.
        """
        s = (status or '').lower()
        if 'thunder' in s:
            return '⛈'
        if 'snow' in s or 'sleet' in s:
            return '🌨'
        if 'rain' in s or 'drizzle' in s:
            return '🌧'
        if 'cloud' in s or 'overcast' in s:
            return '☁️'
        if 'mist' in s or 'fog' in s or 'haze' in s:
            return '🌫'
        if 'clear' in s or 'sunny' in s:
            return '☀️'
        return '🌤'

    def fuzzy(token: str , choices: set , cutoff: float = 0.7):
        """
        Нечёткое сравнение токена с набором допустимых вариантов.
        """
        token = (token or '').lower()
        if token in choices:
            return token
        m = difflib.get_close_matches(token , list(choices) , n=1 , cutoff=cutoff)
        return m [ 0 ] if m else None

    # ───────────────────── константы ─────────────────────
    CMDS = {'погода' , 'прогноз'}
    WEATHER_WORDS = {'погоды'}
    PREFIX = 'кут'  # поддержка префикса

    # ───────────────────── handler body (фрагмент) ─────────────────────
    # Предполагается, что:
    # - переменная `message` - объект aiogram.types.Message
    # - глобально доступен `weather_manager` (pyowm)
    # Этот блок вставляется внутрь твоего message-хендлера.

    text = (message.text or '').strip()
    raw = text.split()
    low = [ t.lower() for t in raw ]

    invoked = False
    city = ""  # всегда строка

    if raw:
        i = 0
        if low [ 0 ] == PREFIX:
            i = 1

        if i < len(low):
            cmd = fuzzy(low [ i ] , CMDS)
            if cmd:
                i += 1
                # поддержка «прогноз погоды ...»
                if cmd == 'прогноз' and i < len(low) and fuzzy(low [ i ] , WEATHER_WORDS):
                    i += 1
                invoked = True
                city = ' '.join(raw [ i: ]).strip()
            else:
                # кейс: «кут прогноз погоды Осло»
                if i + 1 < len(low) and fuzzy(low [ i ] , {'прогноз'}) and fuzzy(low [ i + 1 ] , WEATHER_WORDS):
                    invoked = True
                    city = ' '.join(raw [ i + 2: ]).strip()

    # Если команду вызвали, но город не указан - сообщаем и выходим
    if invoked and not city:
        await message.answer(
            "📍 Укажи город после команды, например: <b>погода Осло</b>." ,
            parse_mode="HTML")  # мягко выходим только из этой ветки, не ломая общий хендлер
    else:
        # Если команда не распознана - ничего не делаем (пусть обрабатывают другие блоки)
        if not invoked:
            pass
        else:
            # ── основная логика погоды ──
            result_message = ""
            try:
                if 'weather_manager' not in globals() or weather_manager is None:
                    raise RuntimeError("weather_manager не инициализирован")

                city_safe = city.strip()
                print(f"[Погода] Запрошено: «{city_safe}»")

                # Не блокируем event-loop: обращаемся к OWM через to_thread
                observation = await asyncio.to_thread(weather_manager.weather_at_place , city_safe)
                current_weather = observation.weather

                # Температура (℃) и ветер
                temp_info = current_weather.temperature('celsius') or {}
                current_temperature = temp_info.get('temp')
                try:
                    wind_speed = float((current_weather.wind() or {}).get('speed' , 0))
                except Exception:
                    wind_speed = 0.0

                current_status = current_weather.status or ""
                translated_status = translate_weather_status(current_status)

                # Прогноз 3h
                forecast = await asyncio.to_thread(weather_manager.forecast_at_place , city_safe , '3h')
                upcoming_weather = list(getattr(forecast.forecast , 'weathers' , [ ]) or [ ])

                # Шапка
                time_of_day_emoji = get_time_of_day_emoji()
                header_city = city_safe [ :1 ].upper() + city_safe [ 1: ]
                temp_str = f"{round(current_temperature)}°C" if isinstance(current_temperature , (int , float)) else "-"
                wind_str = f"{round(wind_speed , 1)} м/с"

                result_message = (f"<b>{time_of_day_emoji} Погода в городе {header_city}</b>\n\n"
                                  f"<b><i>{get_weather_emoji(current_status)} {translated_status}</i></b>\n"
                                  f"<b><i>{temp_str}</i></b>\n"
                                  f"<b><i>{wind_str}</i></b>\n\n")

                # Даты «сегодня/завтра» по локальному времени
                now_local = dt.datetime.now()
                today = now_local.date()
                tomorrow = today + timedelta(days=1)

                # ── Прогноз на сегодня ──
                result_message += "<b>Прогноз на сегодня</b>\n"
                today_found = False
                for w in upcoming_weather:
                    # w.reference_time('iso') → ISO-строка без TZ; приводим к локали
                    try:
                        forecast_time = dt.datetime.fromisoformat(w.reference_time('iso'))
                    except Exception:
                        # запасная ветка: иногда OWM даёт unixtime
                        try:
                            forecast_time = dt.datetime.fromtimestamp(int(w.reference_time('unix')))
                        except Exception:
                            continue

                    if forecast_time.date() == today:
                        label = get_time_of_day_label(forecast_time.hour)
                        temp_w = w.temperature('celsius') or {}
                        tval = temp_w.get('temp')
                        t_str = f"{round(tval)}°C" if isinstance(tval , (int , float)) else "-"
                        emoji = get_weather_emoji(w.status)
                        result_message += f"{emoji} <b><i>{label}</i> {forecast_time.strftime('%H:%M')}</b> - <b>{t_str}</b>\n"
                        today_found = True

                if not today_found:
                    result_message += "- нет данных.\n"

                # ── Прогноз на завтра ──
                result_message += "\n<b>Прогноз на завтра</b>\n"
                tomorrow_found = False
                for w in upcoming_weather:
                    try:
                        forecast_time = dt.datetime.fromisoformat(w.reference_time('iso'))
                    except Exception:
                        try:
                            forecast_time = dt.datetime.fromtimestamp(int(w.reference_time('unix')))
                        except Exception:
                            continue

                    if forecast_time.date() == tomorrow:
                        label = get_time_of_day_label(forecast_time.hour)
                        temp_w = w.temperature('celsius') or {}
                        tval = temp_w.get('temp')
                        t_str = f"{round(tval)}°C" if isinstance(tval , (int , float)) else "-"
                        emoji = get_weather_emoji(w.status)
                        result_message += f"{emoji} <b><i>{label}</i> {forecast_time.strftime('%H:%M')}</b> - <b>{t_str}</b>\n"
                        tomorrow_found = True

                if not tomorrow_found:
                    result_message += "- нет данных.\n"

            except Exception as e:
                traceback.print_exc()
                # Вежливое сообщение об ошибке + подсказка
                city_cap = (city or '').strip()
                city_cap = city_cap [ :1 ].upper() + city_cap [ 1: ] if city_cap else ""
                result_message = ("⚠️ Произошла ошибка при получении погоды.\n"
                                  f"Проверь написание города{f' «{city_cap}»' if city_cap else ''} и попробуй ещё раз.")

            # Финальный ответ
            try:
                await message.reply(result_message , parse_mode="HTML" , disable_web_page_preview=True)
            except Exception:
                # На крайний случай - fallback
                await message.answer(result_message , parse_mode="HTML" , disable_web_page_preview=True)

    if 'кут скажи' in message.text.lower() or 'кут повтори' in message.text.lower():
        if 'кут скажи' in message.text.lower():
            question = message.text.lower().split('кут скажи' , 1) [ -1 ].strip()
        elif 'кут повтори' in message.text.lower():
            question = message.text.lower().split('кут повтори' , 1) [ -1 ].strip()

        if question:  # Проверяем, что вопрос не пустой
            user_id = message.from_user.id
            answer = random.choice([ 'попросил(-а) меня сказать' ])

            first_name = await db.get_firstname_by_user_id(user_id)
            linkk = f"https://t.me/{message.from_user.username}"  # Пример ссылки на пользователя
            emojitext = random.choice([ "💖" , "🍓" , "🐾" , "🦋" , "🌈" , "🎀" , "🐥" ])

            # Проверка на нецензурные слова
            if profanity.contains_profanity(question):
                # Сообщаем пользователю о проблеме
                await message.reply(
                    "⚠️ Ваше сообщение содержит нецензурные слова и не может быть отправлено." ,
                    parse_mode="HTML" , disable_web_page_preview=True)
            else:
                response = f'{emojitext} <b><i>{question}</i></b>'
                await message.reply(response , parse_mode="HTML" , disable_web_page_preview=True)
    def parse_number(num_str):
        # Убираем запятые и пробелы, заменяем точку на пустую строку
        num_str = num_str.replace(',' , '').replace(' ' , '')
        # Пробуем преобразовать строку в целое число
        try:
            return int(num_str)
        except ValueError:
            return None
    words = message.text.lower().split()
    if len(words) > 0 and (words [ 0 ] in [ 'кут' , 'рандом' ]):

        # Обработка случая, когда на первом индексе 'кут'
        if words [ 0 ] == 'кут':
            # Проверяем, есть ли 'рандом' на втором индексе и числовые значения на следующих
            if len(words) >= 4 and words [ 1 ] == 'рандом':
                # Убедимся, что на втором и третьем индексах числа
                num1 = parse_number(words [ 2 ])
                num2 = parse_number(words [ 3 ])

                if num1 is not None and num2 is not None:  # Проверка, что оба числа корректны
                    # Проверяем, что числа корректны (num1 < num2)
                    if num1 < num2:
                        result = random.randint(num1 , num2)
                        answer = random.choice(
                            [ f"<b>Я решил выбрать {result}.\n<i>Как будто это единственный вариант!</i></b>" ,
                              f"<b>Я определился на {result}, <i>не спрашивайте как!</i></b>" ,
                              f"<b>Я остановился на {result}, <i>оно мне нравится.</i></b>" ,
                              f"<b>Я принял решение на {result}, <i>как будто это было легко!</i></b>" ,
                              f"<b>Я сделал выбор на {result}, <i>просто потому что могу.</i></b>" ,
                              f"<b>Я выбрал число {result}, <i>оно мне подмигнуло.</i></b>" ,
                              f"<b>Я остановил выбор на {result}, <i>когда устал думать.</i></b>" ,
                              f"<b>Я выбрал {result}, <i>потому что все остальное слишком сложно!</i></b>" ,
                              f"<b>Я выбрал {result}, <i>и это было непросто!</i></b>" ])
                        # Отправляем ответ пользователю
                        await message.reply(
                            f'🐻‍❄️ {answer}' , parse_mode="HTML" , disable_web_page_preview=True)
                    else:
                        await message.reply(
                            '⚠️ Первая цифра должна быть меньше второй' , parse_mode="HTML" ,
                            disable_web_page_preview=True)
                else:
                    await message.reply(
                        '''⚠️ Используйте <b>"кут рандом 1 10"</b> для генерации числа от 1 до 10''' ,
                        parse_mode="HTML" , disable_web_page_preview=True)
            # Обработка случая, если только 'кут'
            else:
                # Ваш код для обработки 'кут' без 'рандом'
                pass  # Замените на ваш код

        # Обработка случая, когда на первом индексе 'рандом'
        elif words [ 0 ] == 'рандом':
            # Убедимся, что на первом индексе 'рандом', а на следующих - числа
            if len(words) >= 3:
                try:
                    num1 = parse_number(words [ 1 ])
                    num2 = parse_number(words [ 2 ])

                    if num1 is not None and num2 is not None:  # Проверка, что оба числа корректны
                        # Проверяем, что числа корректны (num1 < num2)
                        if num1 < num2:
                            result = random.randint(num1 , num2)
                            answer = random.choice(
                                [ f"<b>Я решил выбрать {result}.\n<i>Как будто это единственный вариант!</i></b>" ,
                                  f"<b>Я определился на {result}, <i>не спрашивайте как!</i></b>" ,
                                  f"<b>Я остановился на {result}, <i>оно мне нравится.</i></b>" ,
                                  f"<b>Я принял решение на {result}, <i>как будто это было легко!</i></b>" ,
                                  f"<b>Я сделал выбор на {result}, <i>просто потому что могу.</i></b>" ,
                                  f"<b>Я выбрал число {result}, <i>оно мне подмигнуло.</i></b>" ,
                                  f"<b>Я остановил выбор на {result}, <i>когда устал думать.</i></b>" ,
                                  f"<b>Я выбрал {result}, <i>потому что все остальное слишком сложно!</i></b>" ,
                                  f"<b>Я выбрал {result}, <i>и это было непросто!</i></b>" ])
                            # Отправляем ответ пользователю
                            await message.reply(
                                f'🐻‍❄️ {answer}' , parse_mode="HTML" , disable_web_page_preview=True)
                        else:
                            await message.reply(
                                '⚠️ Первая цифра должна быть меньше второй' , parse_mode="HTML" ,
                                disable_web_page_preview=True)
                    else:
                        await message.reply(
                            '''⚠️ Используйте <b>"рандом 1 10"</b> для генерации числа от 1 до 10''' ,
                            parse_mode="HTML" , disable_web_page_preview=True)
                except ValueError:
                    await message.reply(
                        '''⚠️ Используйте <b>"рандом 1 10"</b> для генерации числа от 1 до 10''' ,
                        parse_mode="HTML" , disable_web_page_preview=True)

    words = message.text.lower().split()

    # Проверяем условия по индексам

    if len(words) > 3 and words [ 0 ] == "кут" and words [ 1 ] in [ "орел","орёл" , "решка" ] and words [ 2 ] == "или" and \
            words [ 3 ] in [ "орел","орёл" , "решка","орел?","орёл?" , "решка?" ]:
        # Случайный выбор
        result = random.choice(options)

        # Определение текста ответа в зависимости от результата
        answertext = 'выпала' if result == 'решка' else 'выпал'

        # Отправка соответствующего эмодзи
        emoji = "🌑" if result == "решка" else "🌕"
        await message.answer(emoji)  # Отправка эмодзи

        # Ответ пользователю
        await message.reply(
            f'{emoji} <b>{answertext} :</b> <b><i>{result}</i></b>' , parse_mode="HTML" , disable_web_page_preview=True)

    words = message.text.lower().strip().split()
    if len(words) > 1 and words [ 0 ] in [ 'шар' , 'Шар' ]:
        await message.reply(f'🛠 Используйте похожую функцию\n<code>Кут ( сообщение )</code>',parse_mode="HTML")


    elif message.text in ['кут список', 'Кут список', 'кут сп', 'Кут сп', 'Кт сп', 'кт сп']:
        await message.reply('''
<b>📓 Список функций Кута : 

1|🎩 шар [ сообщение ]

2|🤔 выбери [ 1 ] или [ 2 ]

3|🦅 орел и решка

4|🎲 рандом [1 число] [2 число]

5|🙊 скажи [ сообщение ]

6|🌤 погода [ город ]
 
7|🕓 время [ город ]

8|✏️ стик

9|🥹 эмодзи / эмо

Функции работают при вводе : « кут [ функция ] »</b>
        ''', parse_mode="HTML", disable_web_page_preview=True)

    if message.text.lower() in [ 'кут расскажи о себе','кут, расскажи о себе','кут что ты такое?','кут что ты такое' ]:
        await message.reply(
            '''
🎩 <b>Хорошо! Я Кут - Элитный игровой бот на звёзды в Telegram, который делает чаты живыми и увлекательными!</b>

<pre>✨ Что я умею :

🎮 Захватывающие игры, которые приносят море эмоций и объединяют друзей.  
 
🎨 Веселые и необычные развлечения, которые точно не дадут скучать.

🎩 Качественные функции, которые делают общение интереснее и удобнее.</pre>


⭐️ Чтобы узнать больше информации обо мне - напишите <code>Хелп</code>

🚀 <b>Добавь меня в свой чат - и убедись, что с Кутом всегда весело! 🥳</b>
        ''', parse_mode="HTML")

    normal_answers = ['Я тут' ,'Чем помочь?', 'На месте' ]

    # Случайные фразы для спам-защиты
    spam_protection_answers = [ "🐌 Я не гонщик, давай потише... я подбираю слова." ,
        "🛠️ Эй, я не фабрика ответов! Немного перезаряжусь." , "🤯 У меня аж процессор задымился от твоей скорости." ,
        "🚧 Ты так быстро, что я уже начал подозревать тебя в спаме!" , "🍕 Я на перерыве. Пицца важнее. Щас вернусь." ,
        "👽 Ты общаешься с ботом или с пришельцами? Дай передохнуть!" ,
        "🧠 Кажется, мои нейроны немного устали... Нужен перерыв!" ,
        "🐶 Я пошел за палкой... Ой, погоди, я бот... Сейчас вернусь!" ,
        "🎩 Мой фокус пока заряжается, давай подождем чуть-чуть." ,
        "⏳ Я бы ответил, но время остановилось... Перезапуск через пару секунд." ,
        "🐙 У меня восемь рук, но даже я не справляюсь с твоим спамом!" ,
        "🤖 Боты тоже чувствуют усталость. Дай мне передохнуть!" , "🏃‍♂️ Эй, куда спешим? Я тебя не догоняю!" ,
        "🧘‍♂️ Спокойствие... Я медитирую между ответами." ,
        "🐧 Я как пингвин – топаю медленно, но уверенно. Подожди немного!" ]

    if message.text.lower().split() [ 0 ] in [ 'бот' ] and len(message.text.split()) == 1:
        user_id = message.from_user.id
        current_time = time.time()  # Текущее время в секундах

        # Получаем время последнего использования функции пользователем
        last_usage_time = cute3.get(user_id)

        # Проверяем, прошёл ли период отдыха
        if last_usage_time and current_time - last_usage_time < RESTcute:
            # Если команда вызывается слишком часто, отвечаем случайной фразой для спам-защиты
            answer_spam = random.choice(spam_protection_answers)
            #await message.reply(f"<b>{answer_spam}</b>" , parse_mode="HTML")
            return

        # Если время прошло, отправляем обычный ответ
        answer1 = random.choice(normal_answers)

        button = InlineKeyboardButton(text=f"{answer1}" , callback_data="answer1_callback")
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
        # Отправляем сообщение с кнопкой
        await message.reply(
            f"<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji>" , reply_markup=inline_kb , parse_mode="HTML")
        # Обновляем время последнего использования команды
        cute3 [ user_id ] = current_time


    if message.text in ['кут стик', 'Кут стик','Кут стикер','кут стикер','кут стикеры','Кут стикеры ']:

        stiker1_option = ['CAACAgIAAxkBAS8Cm2WkKuS4WLb4WniXBuDvFDpj05aVAAL2AAPluQga_IFE0NTtdZ40BA',
                          'CAACAgIAAxkBAS8C0WWkK93s5YgKgz5xaX54tWQk_aiWAAI0AAPluQgazjA-_Be9KrU0BA' ,
                          'CAACAgIAAxkBAS8DAWWkLMl_DwioRWy7HP4q0VMWSOF5AAJWAQACBKRhGLBdBGl3Uu-sNAQ' ,
                          'CAACAgIAAxkBAS8EBWWkMQox9GPpdkWNSQaHgbZe1exCAALIEAACH4nxS-bLV19YSp9wNAQ' ,
                          'CAACAgIAAxkBAS8EAmWkMPyHR_voeof6j0jpfvYXefGnAAKxFAAClX84SprUU5e5NRh6NAQ' ,
                          'CAACAgIAAxkBAS8D_WWkMPix05RcU0NxQMZF8pEhndugAALFFQACeNkpShBEDeAyHrXqNAQ' ,
                          'CAACAgIAAxkBAS8D-WWkMPQF4rTnbNCAX9D4YUUhpKPsAAI9GAACb7IgSuPTpLu-DEFENAQ' ,
                          'CAACAgIAAxkBAS8D9WWkMNvh-OVkBPoUorlO1fw_xXTSAAIIDAACdmmZSLAp3KFsYkIsNAQ' ,
                          'CAACAgIAAxkBAS8D8mWkMMav7sHChF9p-AlFRgfSg1W5AAL9GgACvwegSi0j-s8Yt8pjNAQ' ,
                          'CAACAgIAAxkBAS8D7WWkMLw_y9V1xlZE00TBYkFgok9GAAJGAAPBOxQ--qLH6fXzTC80BA' ,
                          'CAACAgIAAxkBAS8D5GWkMKsXRqiRz0tpS88HznQfr-FxAAIuAAPBOxQ-gNdZXiDswSk0BA' ,
                          'CAACAgIAAxkBAS8D4mWkMKKMp2agrOgCVyRIE67EJtKGAAIPAAPBOxQ-yhmUtjDlQTs0BA' ,
                          'CAACAgIAAxkBAS8D3mWkMJ15fVcKHBGuxTix-0obQN64AAIjFAAC5jlpS7CUh81Gd3qmNAQ' ,
                          'CAACAgIAAxkBAS8D2mWkMJpPlPcNGiNikrMIuvOjugvAAAIOGwACnCK4SRpJxB_Xi-QrNAQ' ,
                          'CAACAgIAAxkBAS8D2GWkMJZr9n0gmE-quol_62k6GcCjAAJKFwACerrwSw3OVyhI-ZjLNAQ' ,
                          'CAACAgIAAxkBAS8D1GWkMI-31504iUObqqSAt1g0KU5RAAJSEwACMW45SAS_cwdjHnOTNAQ' ,
                          'CAACAgIAAxkBAS8Dx2WkMEl6nw5DadxnqGRuOeQ9tte7AAJlPQACG7PwSKo0jkgKjS7GNAQ' ,
                          'CAACAgIAAxkBAS8DxGWkMEWxJMAHiw_2-TlW28OU2vlbAAI8GAAC6sYwSWHJbhwbQR23NAQ' ,
                          'CAACAgIAAxkBAS8DwWWkMEJQ6P8bnnzYvQcngDOv0AqsAAJ8FQACv6MxSRgGi10ktbtUNAQ' ,
                          'CAACAgIAAxkBAS8Dv2WkMD3iDv1zRXS3j7Vv5dATQojWAAJ8KwAC4RCoS0RjBy8wDG5UNAQ' ,
                          'CAACAgIAAxkBAS8DvWWkMDWm72yVMr6D0dsmBJwrEgZgAAKREwACTBoxSTWapkvzylkDNAQ' ,
                          'CAACAgIAAxkBAS8DuWWkMDEHFNoe60E1yUl1rrH4HW7-AAK_EAACh0GwSv7l0GF2uOC9NAQ' ,
                          'CAACAgIAAxkBAS8Dt2WkMDC5gTQkuLNKgpCHW_daFGWkAAJqDwACAquwSk05dSkP6dUSNAQ' ,
                          'CAACAgIAAxkBAS8DtWWkMC5swljfVGWF9e25WihzgcZxAAJbEAACDRuwSpSt8ICFyj3qNAQ' ,
                          'CAACAgIAAxkBAS8DsWWkMC2kRthn5ox2MW3BmayU9fBSAAJ6DgACKt6wSmMCmv3SEGEMNAQ' ,
                          'CAACAgIAAxkBAS8Dr2WkMCE0Na-tvggzF69tD0Zw3Eh9AALVIgACOvD4S6pWF7g7i40TNAQ' ,
                          'CAACAgIAAxkBAS8DqWWkMBIcvn2C11l9yeAqnA2jMwXVAAIYNgACop2AS746xe79p9s1NAQ' ,
                          'CAACAgIAAxkBAS8DnWWkL-F-_gFOxDtw33mWwhhHUS8nAAJyNgACzgYpS6vUNBim4-jpNAQ' ,
                          'CAACAgIAAxkBAS8Dm2WkL94VEprWhsBm0zEM0E5JcJ-ZAAJNNwAC17spS60W8CmhksZKNAQ' ,
                          'CAACAgIAAxkBAS8DmWWkL9sksaYeMIoHvg3YDjZ6d0fQAAIjNQACyjopSzqhsXUGPOP5NAQ' ,
                          'CAACAgIAAxkBAS8Dl2WkL9Ys0MlhToITGyOMm69Y_GmcAAJnMgACTKooSyyXvapdSOgcNAQ' ,
                          'CAACAgIAAxkBAS8DiGWkL1pS4yAXCPhBe3zxn_Vr2yw4AAJSGgACDnsZS2vMLx_EP3kjNAQ' ,
                          'CAACAgIAAxkBAS8Dg2WkL1Lu5vVX1xqs9MbksVw1TyFRAALJFAACfG4ZSgjMbEzdgoQfNAQ' ,
                          'CAACAgIAAxkBAS8DgGWkL0gWiRvxxW1SxPEAAaUDGPcGVwAC-BYAAgXuEErwBZIN16w6BjQE' ,
                          'CAACAgIAAxkBAS8DfmWkL0Re9zoLCl3z9eosnSC6D3l-AAIpFQACgRwQSuBfq6hR3IxKNAQ' ,
                          'CAACAgIAAxkBAS8DdmWkLxUimAu2DbuM8JlktRm6QHitAAKqFQACU-vISxevT5WgIoQ4NAQ' ,
                          'CAACAgIAAxkBAS8DdGWkLxCBbLpP10iQS-aZ-TeJ50BEAAJyLAAC4sdJSzsP80F0aCJjNAQ' ,
                          'CAACAgIAAxkBAS8DcWWkLwvxNgoTR0CmGlfhc92z-TxYAAJjNAACyD8hSKeiqclpg2gDNAQ' ,
                          'CAACAgIAAxkBAS8DbmWkLuti5fyiuHOVD6YvhbYqfXd2AAI9FwACYbgJSA0PIW0fGyyWNAQ' ,
                          'CAACAgIAAxkBAS8Da2WkLt51_Pu7UlTmtgLjwVCqHk2SAAItIgACwmbxSojTSCJ7uvOMNAQ' ,
                          'CAACAgIAAxkBAS8DaWWkLt1VbuCOAAE2vE3kLwVJ3zjE2AACHiAAAmpd8EpEpl_LdGkHGTQE' ,
                          'CAACAgIAAxkBAS8DZWWkLtJX8wqqRj7NhAABaDAlenuGzAACxiQAApJn-EqbSvXyt9XZdjQE' ,
                          'CAACAgIAAxkBAS8DYmWkLtE0zlYqPTcRKHKewgMoolTIAAKdKAACMFv4SnQfBwABlNGNHDQE' ,
                          'CAACAgIAAxkBAS8DX2WkLs071PqeW5E7O5nreAABG-Rf5gAC1iMAAjDG8EoPRAMZCkSupjQE' ,
                          'CAACAgIAAxkBAS8DXGWkLsm3nKh49aN83ry0JCZsRkHIAAJVJgACuSfwSsjaBbanmpL4NAQ' ,
                          'CAACAgIAAxkBAS8DWWWkLsSBqyc11xoQ_XosCt215ODAAAIpJgAC1hz4SmjDHcrrOuyPNAQ' ,
                          'CAACAgIAAxkBAS8DUmWkLp8ZnJYK-99z650RLxVMTYaHAAKpGwAC8UVQS5o1NESZm8a4NAQ' ,
                          'CAACAgIAAxkBAS8DUGWkLp04ngF6iAms0xUQJIdl_znoAAJpGwACyIdQS2FZYgjwZL5CNAQ' ,
                          'CAACAgIAAxkBAS8DTmWkLpd43o9miYuYbfqRKZiE_0MbAAJ2GAACbLpQSyYuteRF_eL8NAQ' ,
                          'CAACAgIAAxkBAS8DS2WkLoXrKN8jsqntlUzhUGyoIwAB1gACSCkAAjeiiUvq6r-EWDwu0jQE' ,
                          'CAACAgIAAxkBAS8DRmWkLlVLTCbkLbBIKh_YGmVA49XbAAIwMQACY8UwSCeRpcjn-n4hNAQ' ,
                          'CAACAgIAAxkBAS8DP2WkLkTKN3HBpS7g2Mjq_ehFpaT4AAKvKgACIuT5SChcj--AK-HVNAQ' ,
                          'CAACAgIAAxkBAS8DOWWkLh7q1kMYf4uEj1UkpkzAdPEkAAL2LwACXVghSHsMJUnWqxdENAQ' ,
                          'CAACAgIAAxkBAS8DNmWkLge7fZiT4fDxKxZ2dN6ulCU_AAKvNwACux8ISAHZybLFWLlINAQ' ,
                          'CAACAgIAAxkBAS8DJmWkLcIbGbVXtwsRq_ReeKt-o1DMAAKfMgACzK4pSE805FxZFVSTNAQ' ,
                          'CAACAgIAAxkBAS8DJGWkLbtpWsf2QI8nF279AZEqfEcCAAKSNgAC_3AhSC7owqcTmP9LNAQ' ,
                          'CAACAgIAAxkBAS8DImWkLa97tPs33EAovibjtj2V09pYAALmNAACM1NZS-VwgVBTXsOaNAQ' ,
                          'CAACAgIAAxkBAS8DJmWkLcIbGbVXtwsRq_ReeKt-o1DMAAKfMgACzK4pSE805FxZFVSTNAQ' ,
                          'CAACAgIAAxkBAS8DImWkLa97tPs33EAovibjtj2V09pYAALmNAACM1NZS-VwgVBTXsOaNAQ' ,
                          'CAACAgIAAxkBAS8ERmWkMuOqh5gbFUiTm04m0tNyOlmZAALOEQACW-6hS0nvqzvOJ-hjNAQ' ,
                          'CAACAgIAAxkBAS8ESGWkMuoKJrOSNiomVKqRH3wyz4aYAALgDwACxsuhS822k-oRGhyHNAQ' ,
                          'CAACAgIAAxkBAS8ESmWkMu-SOptMHQk_jMPjfZzhoT12AAITEQACPfSgS9kEpU7s4GCmNAQ' ,
                          'CAACAgIAAxkBAS8ETWWkMvh_34LxlUoSRwXXmJJJ-AGWAAK3IwACrLwISQPq4WDxvT9TNAQ' ,
                          'CAACAgIAAxkBAS8ET2WkMwABfbbhrS3t4jTD-JiHqEG8iAAC9BIAAmrucEve89U7y6zXujQE' ,
                          'CAACAgIAAxkBAS8EUmWkMwbge9XcCvyPjbf6d-3CFTtPAALDDgACXHAJSq17qZcWFzWmNAQ' ,
                          'CAACAgIAAxkBAS8EVGWkMw0DwJIoyYDFIBvIbKb10rKrAAIbAANdBYIWev4TQi5q3O00BA' ,
                          'CAACAgIAAxkBAS8EVmWkMxLSg20tXaPOmnt8wXKAv-vFAAIkAANdBYIWBb3aWZHVOB80BA' ,
                          'CAACAgIAAxkBAS8EWWWkMxrQuAUdAaaw2Yxm9jCZMFwmAAI_AANdBYIWvlXmj9Fp2bE0BA' ,
                          'CAACAgIAAxkBAS8EXWWkMyHkUrTtunAIp5cSDl4h-UZfAAL3DgAC2agJSvbTqZ3FSRYvNAQ' ,
                          'CAACAgIAAxkBAS8EX2WkMyYuYc77cSpu-eXraTO8iffuAAK-DQAClA1oSxUJBsiFjyGKNAQ' ,
                          'CAACAgIAAxkBAS8EYWWkMy7opNdLiKkTi7WlCqWZyUzKAAJjDgACWO1xS9TjpD_GIGo3NAQ' ,
                          'CAACAgIAAxkBAS8EZGWkMzKR5dCIHnTE0Cjj1VTrl0SmAAMTAAL6dHBL58fCMakLvfQ0BA' ,
                          'CAACAgIAAxkBAS8EZ2WkMz_VCVkWnML1o3452HeAZ2hRAAJ3EAACiXCoSDY-xtuOJk95NAQ' ,
                          'CAACAgIAAxkBATqxU2XE1foUq3AbyytIobI5mWucvND7AAJpGAACHEpQS87SaGnbjh94NAQ' ,
                          'CAACAgIAAxkBATqxUWXE1fgQbgcrbtt3Od3Yj3TXFcJwAAJpGwACyIdQS2FZYgjwZL5CNAQ' ,
                          'CAACAgIAAxkBATqxT2XE1fdEL6q2hq3C2HFYMgJy3xg6AALJIQAC2hr4SoBW2XC0U1wKNAQ' ,
                          'CAACAgIAAxkBATqxTWXE1feteUkfhWSW1fIrlNcR5EDAAALtJAACUUDwSowuSF4GhNM8NAQ' ,
                          'CAACAgIAAxkBATqxS2XE1faWkUQ9JIslwg_lsZOmkgL2AAIeJAACnS3wSto0cx_QvNUiNAQ' ,
                          'CAACAgIAAxkBATqxSWXE1fb1rn2lgCKsy_TCTkRXUmRvAAIpJgAC1hz4SmjDHcrrOuyPNAQ' ,
                          'CAACAgIAAxkBATqxR2XE1fQqfmFKFAHD62Jh9xjUGJNbAAIvLAACdQfxSjjyeAAB1OYGKTQE' ,
                          'CAACAgIAAxkBATqxRGXE1fOjN_XVPCc3ryqqE0R58LFhAAItIgACwmbxSojTSCJ7uvOMNAQ' ,
                          'CAACAgIAAxkBATqxQmXE1fJqPsLkKvgj-owG3Fs3hyIJAALWIwACMMbwSg9EAxkKRK6mNAQ' ,
                          'CAACAgIAAxkBATqxQGXE1fEHgNQBK4y_vOGnoTpSPwoiAAIeIAACal3wSkSmX8t0aQcZNAQ' ,
                          'CAACAgIAAxkBATqxPmXE1fEJ2_2LjVZ4ayeEKgrpDqfFAAI9JAAC6Bz4SrjVtclWm-bLNAQ' ,
                          'CAACAgIAAxkBATqxPGXE1fACWVylbypg_ZCA5E9-NnXNAAJVJgACuSfwSsjaBbanmpL4NAQ' ,
                          'CAACAgIAAxkBATqxOmXE1e8XRFCljEKebE6xkMckDazdAAJdIAACFvHwSqRZ-pUG0XH8NAQ' ,
                          'CAACAgIAAxkBATqxOGXE1e9ndMhTSgrc8qa37x_yQyghAAJJKQACQs7xSo3nsyyJPIUbNAQ' ,
                          'CAACAgIAAxkBATqxNWXE1e74MmoIL35EY9kvJ720xR4ZAAJgIwACj2nwStoZSDXppP8vNAQ' ,
                          'CAACAgIAAxkBATqxM2XE1e4eiUhMMzIBlprBrp2vthyWAAIQJgACjNn4SmEnDt1LJ3rMNAQ' ,
                          'CAACAgIAAxkBATqxMWXE1e2V6P_KqKCQ5xkXKJHL6oAWAALkJgAC4ODwStPSDK16aZtKNAQ' ,
                          'CAACAgIAAxkBATqxL2XE1exjtKocP2wwJUMgLcxSCLkcAAKDKwACKkvxSkVVpWyKAAFNcjQE' ,
                          'CAACAgIAAxkBATqxLWXE1ev8nN9cvUGWbaeqyXy7-narAAIUIQACvlXwSrvwuqHEem6ANAQ' ,
                          'CAACAgIAAxkBATqxK2XE1eqmiWZ17C62nxsYBhWQn8aJAAL6JAACRE3xSvGmNHSNnGmSNAQ' ,
                          'CAACAgIAAxkBATqxKWXE1eaZuxGJu0FMan5lahJm7-wNAAIfIgACEKPxSv7COrQtj7CLNAQ' ,
                          'CAACAgIAAxkBATqxJ2XE1eRPfmBwHy7-6u-TdrHNSALCAAI1JgAC3XjwSutHlAJUw3p1NAQ' ,
                          'CAACAgIAAxkBATqxJWXE1eMnLl2ZrqRkozSH9d8akNoPAAJxIgAC_fTxSuHyAAEdGn7sfzQE' ,
                          'CAACAgIAAxkBATqxI2XE1eNcRCKsumFTx9SX2ZiTS9rTAAIWKQACpxv5SrzLYHbT_OA0NAQ' ,
                          'CAACAgIAAxkBATqxIWXE1d8oBDcmrUx7UcbeI7zaFvtnAAL_AQACPQ3oBD8bwL5KHyjrNAQ' ,
                          'CAACAgIAAxkBATqxH2XE1d40CMNSZfga-y4C8lXaZscUAAL2AQACPQ3oBIg_Yag9NQJ7NAQ' ,
                          'CAACAgIAAxkBATqxHWXE1d6h9RprtgABaOu1zjl3tcFvagAC9AEAAj0N6ASuGPtVPZC6lzQE' ,
                          'CAACAgIAAxkBATqxG2XE1d25wimi3rGFM2PQAAEe_GlbYwADAgACPQ3oBIaM11l_pjF7NAQ' ,
                          'CAACAgIAAxkBATqxGWXE1d0HULF40MB_gAaulcZu7YiCAALyAQACPQ3oBK4rSsqxd5bENAQ' ,
                          'CAACAgIAAxkBATqxFmXE1dw_RTBKyRTqk5yU2yKAAYgOAALzAQACPQ3oBMjOWij0tUZuNAQ' ,
                          'CAACAgIAAxkBATqxFGXE1dqp552lpwVErhrC_vmA5SV5AAL9AQACPQ3oBIzTSJeMdf3PNAQ' ,
                          'CAACAgIAAxkBATqxEmXE1dkVe0apcCgE1FlS0FyALX5qAAL-AQACPQ3oBJG_wxhnwyLWNAQ' ,
                          'CAACAgIAAxkBATqxEGXE1dgDpeuZ3s90jecgKL9ETvWOAALxAQACPQ3oBK9nbZq29kyrNAQ' ,
                          'CAACAgIAAxkBATqxDmXE1dYMXyHx4r-cY0PjhO7S2m-4AAIEAgACPQ3oBKJefdwUgszQNAQ' ,
                          'CAACAgIAAxkBATqxCGXE1cezjNCkd2jw7ZK_dFy9hbuHAAJgDwACszlYSqu_GDgszhr8NAQ' ,
                          'CAACAgIAAxkBATqxBmXE1cJTQ3QCvAO7WqeCZzZnDyXxAAKdEAAClrhgSuWqbgE3tPkINAQ' ,
                          'CAACAgIAAxkBATqw_mXE1bGdyhTiQhkoyqXZunPnPj65AAJxOgAC1tBoSWC7DXD5lSkiNAQ' ,
                          'CAACAgIAAxkBATqw_GXE1bDupOjFfpDgocbuKvDKMxI6AAKlOAACjyVoSTBPkSf9J2TqNAQ' ,
                          'CAACAgIAAxkBATqw-mXE1a9F9IS_xC3Q9c4f6yKkoorFAAIzQQACdl9oSUNM2nRFs0tUNAQ' ,
                          'CAACAgIAAxkBATqw-GXE1a3nKuUnstNMOx3C8g4ULjKqAAJyNgACbploSSqFCJGxE8cwNAQ' ,
                          'CAACAgIAAxkBATqw9mXE1ax2FcxQJjLvJ_PprAtW3hzKAAJvPAACI3toSR4dwZj12uXhNAQ' ,
                          'CAACAgIAAxkBATqw9GXE1axGiYipkb0NFjtRx4FAz_lvAAJEPgAC1x5oSa6h_TM5Z_N1NAQ' ,
                          'CAACAgIAAxkBATqw8mXE1aters6z7_X7M7nk-OS-25rEAAKpOAACU-NoSdR5HPPyfp9gNAQ' ,
                          'CAACAgIAAxkBATqw72XE1aj4SUTFtTluzsovnxSt8nz9AAJQOgACJ4doSVUx9Up615kPNAQ' ,
                          'CAACAgIAAxkBATqw7WXE1afysPvbhMsdF7qcyG7he-nHAAJ0OgACdg9pSV-rNlbVD_yVNAQ' ,
                          'CAACAgIAAxkBATqw62XE1aaAUeO3uk-wsqb6U3BLYS74AAI2QgACtUJxSTcAARsYT5zkfzQE' ,
                          'CAACAgIAAxkBATqw6GXE1aMwth6fNdHdDwABd0mqx_8gtQACVQEAAgSkYRh8eR4hdkpCwTQE' ,
                          'CAACAgIAAxkBATqw5mXE1aIUSci4EuqcJDXAaLLGXXlvAAJmAQACBKRhGBmYHLAGiLzxNAQ' ,
                          'CAACAgIAAxkBATqw5GXE1aBINrl6Ad1d7H2xFwS9VHkyAAJpAQACBKRhGHTEf569JAW7NAQ' ,
                          'CAACAgIAAxkBATqw4WXE1aDRGbYUhm9_Re_EPKIvXA27AAJqAQACBKRhGFEz6gZSdBPsNAQ' ,
                          'CAACAgIAAxkBATqw32XE1Z9HSu0PEfjQb_HzRNd1uv0AA4gBAAIEpGEYxI1Pt-LMaC00BA' ,
                          'CAACAgIAAxkBATqw3WXE1Z_SqREeHdaQC4T8bVl5p8XOAAJ7AQACBKRhGMN0fbjz4x-dNAQ' ,
                          'CAACAgIAAxkBATqw22XE1Z5U5kQpB0LSZzhr0oY3OnBJAAKHAQACBKRhGJM7T4PXCYGTNAQ' ,
                          'CAACAgIAAxkBATqw2WXE1Z7d-nYRo3MVbK0x6NZ-Efm5AAJUAQACBKRhGPfsEw0IE52jNAQ' ,
                          'CAACAgIAAxkBATqw1mXE1Zu0j9gVsuQacJTvNI-StZPmAAJ5AQACBKRhGGCw4-NH_n9xNAQ' ,
                          'CAACAgIAAxkBATqw1GXE1ZhD6t3JETA3WToFv6oawluXAAJjAQACBKRhGFWb0mBNF6MsNAQ' ,
                          'CAACAgIAAxkBATqw0mXE1Zao6GBS0e7uZapGUgL5fqaZAAJWAQACBKRhGLBdBGl3Uu-sNAQ' ,
                          'CAACAgQAAxkBATqwy2XE1Ym8j8MM2namGi9aHMFTOHO1AALeDQAClTlwU-qd5alrCOu8NAQ' ,
                          'CAACAgIAAxkBATqwxmXE1YNp0Jy8a7Mny8o1-o4LZp5XAAKOJwACcnr5SA6U9DA-DFiXNAQ' ,
                          'CAACAgIAAxkBATqwwWXE1XoAAbP4ZNOAkVgNuE6ur_DUrAAC_wAD5bkIGvo7MX3nUJ5VNAQ' ,
                          'CAACAgIAAxkBATqwv2XE1XfJz8_SsINBawJIVS9XohV4AAMBAALluQgaCS8ynklF_4w0BA' ,
                          'CAACAgIAAxkBATqwvWXE1XIJOOWIjmvAh6b0CyHNQmn-AAL-AAPluQga3IurrgrFPy80BA' ,
                          'CAACAgIAAxkBATqwvWXE1XIJOOWIjmvAh6b0CyHNQmn-AAL-AAPluQga3IurrgrFPy80BA' ,
                          'CAACAgIAAxkBATqwuWXE1W7IrgJR3lyfH2l95NmbuWv-AAJwAAPluQgasRuPWvSdarE0BA' ,
                          'CAACAgIAAxkBATqwt2XE1W7bVGzuuwJoTzXyfcdQVZ0hAAJsAAPluQgaYOfQXeHcwJc0BA' ,
                          'CAACAgIAAxkBATqwtWXE1W3GPGUCXI4TqcQDPBcoMqtdAALnAAPluQgaZOxhXO_cJy00BA' ,
                          'CAACAgIAAxkBATqws2XE1Wgr0CaAkGi43fdb2VzgGlVcAAJcAAPluQgarXwM-rbw-y40BA' ,
                          'CAACAgIAAxkBATqwsWXE1WHg5UhImAVMXCGdtmvicMgZAAJTAAPluQgaG6stK5ONDaY0BA' ,
                          'CAACAgIAAxkBATqwrmXE1V5QhhYJ_Z3OK89fIPCW5vVXAAJlAQAC5bkIGiEoaMPOe3OONAQ' ,
                          'CAACAgIAAxkBATqwqmXE1VYEzrznkCACpBAGWbEczRbbAAL1AAPluQgacwABpWkXqa4NNAQ' ,
                          'CAACAgIAAxkBATqwqGXE1VSuIZvaOB1YqlhxjIO40YNoAAL3AAPluQgav4aZ7n_sdu40BA' ,
                          'CAACAgIAAxkBATqwpmXE1U9_CcKRe0L1Pom9iw7BvCDBAAL2AAPluQga_IFE0NTtdZ40BA' ,
                          'CAACAgIAAxkBATqwpGXE1U4pgcuPost3POX85TiNdwYdAALfAAPluQgaOwiMAop5Pg00BA' ,
                          'CAACAgIAAxkBATqwomXE1U1SZ4iicQT8n6wY-UDGO6czAAJIAAPluQgaj8Z12duSHLI0BA' ,
                          'CAACAgIAAxkBATqwomXE1U1SZ4iicQT8n6wY-UDGO6czAAJIAAPluQgaj8Z12duSHLI0BA' ,
                          'CAACAgIAAxkBATqwnmXE1UgnJIkvNXFZ8gyEn4h4yFeRAAJrAQAC5bkIGqhOZ7E-fwhqNAQ' ,
                          'CAACAgEAAxkBATqwnGXE1UYqd139X1Co4okYHrPB69JRAAIvAgACK1MhRKZVJHt9m4DVNAQ' ,
                          'CAACAgIAAxkBATqwmWXE1UOlArPxz1EwOAdktfN9zGi1AAMTAAL6dHBL58fCMakLvfQ0BA' ,
                          'CAACAgIAAxkBATqwl2XE1UGEKn8H2MpXmnUwEyzvagWKAALOEQACW-6hS0nvqzvOJ-hjNAQ' ,
                          'CAACAgIAAxkBATqxsGXE15lvDsE4NhUPHm-ERAFLPmO3AALAFgACDYxRSEO9yCJh0yLgNAQ' ,
                          'CAACAgIAAxkBATqxtWXE154Rx6gyoziT0A22AAHw5WpaCwACrhMAArmBKUhQAk1r-C9_9TQE' ,
                          'CAACAgIAAxkBATqxuWXE16QhjlrfDeZB2H-7MAboUWYbAALUFgAC9jEpSM7ijn4Uz0b2NAQ' ,
                          'CAACAgIAAxkBATqxvGXE16sJxyIW6GxvXA850BUXtRZCAAKXGAACRAQhSIRyVC-EnX8WNAQ' ,
                          'CAACAgIAAxkBATqxwWXE17JOtAor-9EOxj-c1uw3dVGhAAKhGwACbeggSNTLXznyCvIYNAQ' ,
                          'AAMCAgADGQEBOrHDZcTXu3UURyTl11Yq4HNsDy9zf5UAAg0YAAJHBtFId-wIsSO_66wBAAdtAAM0BA' ,
                          'CAACAgIAAxkBATqxyWXE18UdCwh1A0VBhqF8RWyqc1LgAALDFwAC2kAhSOXDYjx6nEL5NAQ' ,
                          'CAACAgIAAxkBATqxzWXE18z1QLeESaQs16-Ea0x4_xVHAAIcHAACMjUgSHaGBaA6MzYENAQ' ,
                          'CAACAgIAAxkBATqx1WXE1-SfG8tk3J7kyFbBCdcynuTAAALsLwACQuUoSwk1hfMQHz-qNAQ' ,
                          'CAACAgIAAxkBATqx12XE1-s7iKd3RxgKqHsiRwH-HnXxAAJwNAACy9MhSzmzjexRajeGNAQ' ,
                          'CAACAgIAAxkBATqx2mXE1_Kt4gm1DaRkMxVj5f8M0gaYAAJyMgACEu4pS7A98ziLfjlkNAQ' ,
                          'CAACAgIAAxkBATqx3mXE1_6cXz5NXt7GwxNtqxt53nYUAALnOgACcZMoSzm-efYMlFaoNAQ' ]
        stiker = random.choice(stiker1_option)
        await message.reply_sticker(stiker)


    elif message.text.lower() in [ 'кут эмо' , 'Кут эмо' , 'кут эмодзи' , 'Кут эмодзи' ]:

        emoji = [ '😀' , '😃' , '😄' , '😁' , '😆' , '😅' , '😂' , '🤣' , '😊' , '😇' , '🙂' , '🙃' , '😉' , '😌' , '😍' , '🥰' , '😘' ,
                   '😗' , '😙' , '😚' , '😋' , '😛' , '😝' , '😜' , '🤪' , '🤨' , '🧐' , '🤓' , '😎' , '🤩' , '😏' , '😒' , '😞' , '😔' ,
                   '😟' , '😕' , '🙁' , '☹️' , '😣' , '😖' , '😫' , '😩' , '🥺' , '😢' , '😭' , '😤' , '😠' , '😡' , '🤬' , '🤯' ,
                   '😳' , '🥵' , '🥶' , '😱' , '😨' , '😰' , '😥' , '😓' , '🤗' , '🤔' , '🤭' , '🤫' , '🤥' , '😶' , '😐' , '😑' , '😬' ,
                   '🙄' , '😯' , '😦' , '😧' , '😮' , '😲' , '😴' , '🤤' , '😪' , '😵' , '🤐' , '🥴' , '🤢' , '🤮' , '🤧' , '😷' , '🤒' ,
                   '🤕' , '🤑' , '🤠' , '😈' , '👿' , '👹' , '👺' , '🤡' , '💩' , '👻' , '💀' , '☠️' , '👽' , '👾' , '🤖' , '🎃' ,
                   '😺' , '😸' , '😹' , '😻' , '😼' , '😽' , '🙀' , '😿' , '😾' , '👋' , '🤚' , '🖐' , '✋' , '🖖' , '👌' , '🤏' ,
                   '✌️' , '🤞' , '🤟' , '🤘' , '🤙' , '👈' , '👉' , '👆' , '🖕' , '👇' , '☝️' , '👍' , '👎' , '✊' , '👊' , '🤛' ,
                   '🤜' , '👏' , '🙌' , '👐' , '🤲' , '🤝' , '🙏' , '✍️' , '💅' , '🤳' , '💪' , '🦾' , '🦵' , '🦿' , '🦶' , '👂' ,
                   '🦻' , '👃' , '🧠' , '🦷' , '🦴' , '👀' , '👁' , '👅' , '👄' , '👶' , '🧒' , '👦' , '👧' , '🧑' , '👱' , '👨' , '🧔' ,
                   '👩' , '👱‍♀️' , '👱‍♂️' , '🧓' , '👴' , '👵' , '🙍' , '🙍‍♂️' , '🙍‍♀️' , '🙎' , '🙎‍♂️' , '🙎‍♀️' , '🙅' ,
                   '🙅‍♂️' , '🙅‍♀️' , '🙆' , '🙆‍♂️' , '🙆‍♀️' , '💁' , '💁‍♂️' , '💁‍♀️' , '🙋' , '🙋‍♂️' , '🙋‍♀️' , '🧏' ,
                   '🧏‍♂️' , '🧏‍♀️' , '🙇' , '🙇‍♂️' , '🙇‍♀️' , '🤦' , '🤦‍♂️' , '🤦‍♀️' , '🤷' , '🤷‍♂️' , '🤷‍♀️' , '🧑‍⚕️' ,
                   '👨‍⚕️' , '👩‍⚕️' , '🧑‍🎓' , '👨‍🎓' , '👩‍🎓' , '🧑‍🏫' , '👨‍🏫' , '👩‍🏫' , '🧑‍⚖️' , '👨‍⚖️' , '👩‍⚖️' , '🧑‍🌾' ,
                   '👨‍🌾' , '👩‍🌾' , '🧑‍🍳' , '👨‍🍳' , '👩‍🍳' , '🧑‍🔧' , '👨‍🔧' , '👩‍🔧' , '🧑‍🏭' , '👨‍🏭' , '👩‍🏭' , '🧑‍💼' ,
                   '👨‍💼' , '👩‍💼' , '🧑‍🔬' , '👨‍🔬' , '👩‍🔬' , '🧑‍💻' , '👨‍💻' , '👩‍💻' , '🧑‍🎤' , '👨‍🎤' , '👩‍🎤' , '🧑‍🎨' ,
                   '👨‍🎨' , '👩‍🎨' , '🧑‍✈️' , '👨‍✈️' , '👩‍✈️' , '🧑‍🚀' , '👨‍🚀' , '👩‍🚀' , '🧑‍🚒' , '👨‍🚒' , '👩‍🚒' , '👮' ,
                   '👮‍♂️' , '👮‍♀️' , '🕵' , '🕵️‍♂️' , '🕵️‍♀️' , '💂' , '💂‍♂️' , '💂‍♀️' , '👷' , '👷‍♂️' , '👷‍♀️' , '🤴' ,
                   '👸' , '👳' , '👳‍♂️' , '👳‍♀️' , '👲' , '🧕' , '🤵' , '👰' , '🤰' , '🤱' , '👼' , '🎅' , '🤶' , '🦸' , '🦸‍♂️' ,
                   '🦸‍♀️' , '🦹' , '🦹‍♂️' , '🦹‍♀️' , '🧙' , '🧙‍♂️' , '🧙‍♀️' , '🧚' , '🧚‍♂️' , '🧚‍♀️' , '🧛' , '🧛‍♂️' ,
                   '🧛‍♀️' , '🧜' , '🧜‍♂️' , '🧜‍♀️' , '🧝' , '🧝‍♂️' , '🧝‍♀️' , '🧞' , '🧞‍♂️' , '🧞‍♀️' , '🧟' , '🧟‍♂️' ,
                   '🧟‍♀️' , '💆' , '💆‍♂️' , '💆‍♀️' , '💇' , '💇‍♂️' , '💇‍♀️' , '🚶' , '🚶‍♂️' , '🚶‍♀️' , '🧍' , '🧍‍♂️' ,
                   '🧍‍♀️' , '🧎' , '🧎‍♂️' , '🧎‍♀️' , '🧑‍🦯' , '👨‍🦯' , '👩‍🦯' , '🧑‍🦼' , '👨‍🦼' , '👩‍🦼' , '🧑‍🦽' , '👨‍🦽' ,
                   '👩‍🦽' , '🏃' , '🏃‍♂️' , '🏃‍♀️' , '💃' , '🕺' , '🕴' , '👯' , '👯‍♂️' , '👯‍♀️' , '🧖' , '🧖‍♂️' , '🧖‍♀️' ,
                   '🧘' , '🧘‍♂️' , '🧘‍♀️' , '🛀' , '🛌' , '🕰' , '⏰' , '🌞' , '🌝' , '🌛' , '🌜' , '🌚' , '🌕' , '🌖' , '🌗' , '🌘' ,
                   '🌑' , '🌒' , '🌓' , '🌔' , '🌙' , '🌎' , '🌍' , '🌏' , '💫' , '⭐' , '🌟' , '✨' , '⚡' , '🔥' , '💥' , '☄️' ,
                   '☀️' , '🌤' , '⛅' , '🌥' , '🌦' , '🌈' , '☁️' , '🌧' , '⛈' , '🌩' , '🌨' , '❄️' , '☃️' , '⛄' , '🌬' , '💨' ,
                   '🌪' , '🌫' , '🌊' , '💧' , '💦' , '☔' , '🍏' , '🍎' , '🍐' , '🍊' , '🍋' , '🍌' , '🍉' , '🍇' , '🍓' , '🍈' , '🍒' ,
                   '🍑' , '🥭' , '🍍' , '🥥' , '🥝' , '🍅' , '🍆' , '🥑' , '🥦' , '🥬' , '🥒' , '🌶' , '🌽' , '🥕' , '🥔' , '🍠' , '🥐' ,
                   '🍞' , '🥖' , '🥨' , '🧀' , '🥚' , '🍳' , '🥓' , '🥩' , '🍗' , '🍖' , '🌭' , '🍔' , '🍟' , '🍕' , '🥪' , '🥙' , '🌮' ,
                   '🌯' , '🥗' , '🥘' , '🥫' , '🍝' , '🍜' , '🍲' , '🍛' , '🍣' , '🍱' , '🥟' , '🍤' , '🍙' , '🍚' , '🍘' , '🍥' , '🥠' ,
                   '🍢' , '🍡' , '🍧' , '🍨' , '🍦' , '🥧' , '🍰' , '🎂' , '🍮' , '🍭' , '🍬' , '🍫' , '🍿' , '🧂' , '🥡' , '🥢' , '🍽' ,
                   '🍴' , '🥄' , '🔪' , '🏺' , '🌍' , '🌎' , '🌏' , '🌐' , '🗺' , '🗾' , '🧭' , '🏔' , '⛰' , '🌋' , '🗻' , '🏕' , '🏖' ,
                   '🏜' , '🏝' , '🏞' , '🏟' , '🏛' , '🏗' , '🧱' , '🏘' , '🏚' , '🏠' , '🏡' , '🏢' , '🏣' , '🏤' , '🏥' , '🏦' , '🏨' ,
                   '🏩' , '🏪' , '🏫' , '🏬' , '🏭' , '🏯' , '🏰' , '💒' , '🗼' , '🗽' , '⛪' , '🕌' , '🕍' , '⛩' , '🕋' , '⛲' , '⛺' ,
                   '🌁' , '🌃' , '🏙' , '🌄' , '🌅' , '🌆' , '🌇' , '🌉' , '♨️' , '🎠' , '🎡' , '🎢' , '💈' , '🎪' , '🚂' , '🚃' ,
                   '🚄' , '🚅' , '🚆' , '🚇' , '🚈' , '🚉' , '🚊' , '🚝' , '🚞' , '🚋' , '🚌' , '🚍' , '🚎' , '🚐' , '🚑' , '🚒' , '🚓' ,
                   '🚔' , '🚕' , '🚖' , '🚗' , '🚘' , '🚙' , '🚚' , '🚛' , '🚜' , '🏎' , '🏍' , '🛵' , '🦽' , '🦼' , '🛺' , '🚲' , '🛴' ,
                   '🛹' , '🚏' , '🛣' , '🛤' , '🛢' , '⛽' , '🚨' , '🚥' , '🚦' , '🛑' , '🚧' , '⚓' , '⛵' , '🛶' , '🚤' , '🛳' , '⛴' ,
                   '🚢' , '✈️' , '🛩' , '🛫' , '🛬' , '💺' , '🚁' , '🚟' , '🚠' , '🚡' , '🛰' , '🚀' , '🛸' , '🛎' , '🧳' , '⌛' ,
                   '⏳' , '⌚' , '⏰' , '⏱' , '⏲' , '🕰' , '🕛' , '🕧' , '🕐' , '🕜' , '🕑' , '🕝' , '🕒' , '🕞' , '🕓' , '🕟' , '🕔' ,
                   '🕠' , '🕕' , '🕡' , '🕖' , '🕢' , '🕗' , '🕣' , '🕘' , '🕤' , '🕙' , '🕥' , '🕚' , '🕦' , '🌑' , '🌒' , '🌓' , '🌔' ,
                   '🌕' , '🌖' , '🌗' , '🌘' , '🌙' , '🌚' , '🌛' , '🌜' , '🌡' , '☀️' , '🌝' , '🌞' , '🪐' , '⭐' , '🌟' , '🌠' ,
                   '🌌' , '☁️' , '⛅' , '⛈' , '🌤' , '🌥' , '🌦' , '🌧' , '🌨' , '🌩' , '🌪' , '🌫' , '🌬' , '💨' , '🌀' , '🌈' ,
                   '🌂' , '☂️' , '☔' , '⚡' , '❄️' , '🔥' , '💧' , '🌊' , '🍏' , '🍎' , '🍐' , '🍊' , '🍋' , '🍌' , '🍉' , '🍇' ,
                   '🍓' , '🫐' , '🍈' , '🍒' , '🍑' , '🥭' , '🍍' , '🥥' , '🥝' , '🍅' , '🍆' , '🥑' , '🥦' , '🥬' , '🥒' , '🌶' , '🫑' ,
                   '🌽' , '🥕' , '🥔' , '🍠' , '🧅' , '🧄' , '🥯' , '🍞' , '🥖' , '🥨' , '🧀' , '🥚' , '🍳' , '🧈' , '🥞' , '🧇' , '🥓' ,
                   '🥩' , '🍗' , '🍖' , '🦴' , '🌭' , '🍔' , '🍟' , '🍕' , '🫓' , '🥪' , '🥙' , '🧆' , '🌮' , '🌯' , '🫔' , '🥗' , '🥘' ,
                   '🍝' , '🍜' , '🍲' , '🍛' , '🍣' , '🍱' , '🥟' , '🍤' , '🍙' , '🍚' , '🍘' , '🍥' , '🥠' , '🍢' , '🍡' , '🍧' , '🍨' ,
                   '🍦' , '🥧' , '🧁' , '🍰' , '🎂' , '🍮' , '🍭' , '🍬' , '🍫' , '🍿' , '🍩' , '🍪' , '🌰' , '🥜' , '🍯' , '🥛' , '🍼' ,
                   '☕' , '🫖' , '🍵' , '🍶' , '🍾' , '🍷' , '🍸' , '🍹' , '🍺' , '🍻' , '🥂' , '🥃' , '🥤' , '🧃' , '🧉' , '🧊' , '🥢' ,
                   '🍽' , '🍴' , '🥄' , '🔪' , '🏺' , '🌍' , '🌎' , '🌏' , '🌐' , '🗺' , '🗾' , '🧭' , '🏔' , '⛰' , '🌋' , '🗻' , '🏕' ,
                   '🏖' , '🏜' , '🏝' , '🏞' , '🏟' , '🏛' , '🏗' , '🧱' , '🏘' , '🏚' , '🏠' , '🏡' , '🏢' , '🏣' , '🏤' , '🏥' , '🏦' ,
                   '🏨' , '🏩' , '🏪' , '🏫' , '🏬' , '🏭' , '🏯' , '🏰' , '💒' , '🗼' , '🗽' , '⛪' , '🕌' , '🕍' , '⛩' , '🕋' , '⛲' ,
                   '⛺' , '🌁' , '🌃' , '🏙' , '🌄' , '🌅' , '🌆' , '🌇' , '🌉' , '♨️' , '🎠' , '🎡' , '🎢' , '💈' , '🎪' , '🚂' ,
                   '🚃' , '🚄' , '🚅' , '🚆' , '🚇' , '🚈' , '🚉' , '🚊' , '🚝' , '🚞' , '🚋' , '🚌' , '🚍' , '🚎' , '🚐' , '🚑' , '🚒' ,
                   '🚓' , '🚔' , '🚕' , '🚖' , '🚗' , '🚘' , '🚙' , '🚚' , '🚛' , '🚜' , '🏎' , '🏍' , '🛵' , '🦽' , '🦼' , '🛺' , '🚲' ,
                   '🛴' , '🛹' , '🚏' , '🛣' , '🛤' , '🛢' , '⛽' , '🚨' , '🚥' , '🚦' , '🛑' , '🚧' , '⚓' , '⛵' , '🛶' , '🚤' , '🛳' ,
                   '⛴' , '🚢' , '✈️' , '🛩' , '🛫' , '🛬' , '💺' , '🚁' , '🚟' , '🚠' , '🚡' , '🛰' , '🚀' , '🛸' , '🛎' , '🧳' ,
                   '⌛' , '⏳' , '⌚' , '⏰' , '⏱' , '⏲' , '🕰' , '🕛' , '🕧' , '🕐' , '🕜' , '🕑' , '🕝' , '🕒' , '🕞' , '🕓' , '🕟' ,
                   '🕔' , '🕠' , '🕕' , '🕡' , '🕖' , '🕢' , '🕗' , '🕣' , '🕘' , '🕤' , '🕙' , '🕥' , '🕚' , '🕦' , '⏳' , '⌛' , '🧭' ,
                   '🔋' , '🔌' , '💡' , '🔦' , '🕯' , '🪔' , '🧯' , '💸' , '💵' , '💴' , '💶' , '💷' , '💰' , '💳' , '🧾' , '💎' ,
                   '⚖️' , '🪙']


        emoji_random = random.choice(emoji)
        await message.reply(emoji_random)


    elif message.text.lower() in [ 'кут цитаты' , 'Кут цитаты' , 'кут цитата' , 'Кут цитата','кут расскажи цитату','кут, расскажи цитату','кут покажи цитату','кут, покажи цитату' ]:
        response = requests.get('https://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=ru')
        data = response.json()
        citata = data['quoteText']
        author = data['quoteAuthor']
        await message.reply(f'🕊 <b><i>{citata}</i></b>', parse_mode="HTML")

    if message.text.lower().strip().startswith(
            ('кут посчитай','кут, посчитай' , 'кут посчитай' , 'кут калькулятор', 'кут, калькулятор' , 'кут калькулятор','кут рассчитай','кут, рассчитай','кут рассчитай',"кут реши","кут, реши","кут реши","Сколько будет","Сколько, будет","кут сколько будет","кут, сколько будет")):
        # Извлекаем выражение из сообщения
        expression = ' '.join(message.text.split(' ') [ 2: ]).strip()

        # Заменяем запятые на точки
        expression = expression.replace(',' , '.')

        try:
            # Вычисляем результат выражения
            result = eval(expression.replace(':' , '/').replace('х' , '*'))

            # Форматируем результат
            formatted_result = "{:,.2f}".format(result).replace(',' , ' ').replace('.' , ',').replace(' ' , '.')
            if formatted_result.endswith(',00'):
                formatted_result = formatted_result [ :-3 ]

            await message.reply(f"🤓 <b>{formatted_result}</b>" , parse_mode="HTML")
        except:
            await message.reply("⚠️ Ошибка в выражении")

    try:
        # print("Попытка инициализации переводчика...")
        translator = GoogleTranslator(source='auto' , target='ru')

        # Обработка команды "кут переведи"
        if message.text.strip() in [ 'кут переведи','Кут переведи','Кут перевод' , 'кут перевод' , 'кут, переведи','перевод','Перевод' , 'кут, перевод' ,
                                             '/translation@CuteGamingBot' ]:
            if message.reply_to_message:  # Проверяем, есть ли ответное сообщение
                original_text = message.reply_to_message.text
                print("[Перевод текста] Оригинальный текст:" , original_text)

                # Отправляем сообщение о начале обработки
                sent_message = await message.reply('🔗 <b>Перевод в обработке</b>' , parse_mode="HTML")

                try:
                    # Определение языка текста
                    text_language , _ = langid.classify(original_text)
                    print("[Перевод текста] Определенный язык текста:" , text_language)

                    # Переводим текст, если он не на русском
                    if text_language != 'ru':
                        translated_text = translator.translate(original_text)
                        print("[Перевод текста] Переведенный текст:" , translated_text)
                    else:
                        translated_text = original_text
                        print("[Перевод текста] Текст на русском языке, перевод не требуется")

                    # Проверяем, если перевод выполнен корректно
                    if translated_text:
                        # Изменяем сообщение на переведенный текст
                        await sent_message.edit_text(
                            f'🕊 <b><i>{translated_text}</i></b>' , parse_mode="HTML")
                    else:
                        await sent_message.edit_text('⚠️ Ошибка перевода, текст пустой.')

                except Exception as translate_error:
                    print("[Перевод текста] Ошибка перевода:" , translate_error)
                    await sent_message.edit_text("⚠️ Произошла ошибка при переводе.")
            else:
                await message.reply("⚠️ Не указан текст для перевода.")


        elif message.text.strip().startswith(
                ('Кут переведи' , 'кут перевод' , 'Кут, перевед' , 'кут, перевод','перевод','Перевод' , '/translation@CuteGamingBot')):

            # Определяем длину команды

            command_length = 0

            if message.text.strip().lower().startswith(('кут переведи' , 'кут, переведи')):

                command_length = len('кут переведи')

            elif message.text.strip().lower().startswith(('кут перевод' , 'кут, перевод')):

                command_length = len('кут перевод')

            else:

                command_length = len('/translation@CuteGamingBot')

            # Получаем текст для перевода

            text_to_translate = message.text [ command_length: ].strip()

            print("[Перевод текста] Текст для перевода:" , text_to_translate)

            # Отправляем сообщение о начале обработки

            sent_message = await message.reply('🔗 <b>Перевод в обработке</b>' , parse_mode="HTML")

            if text_to_translate:  # Проверяем, что текст для перевода не пустой

                try:

                    # Определение языка текста

                    text_language , _ = langid.classify(text_to_translate)

                    print("[Перевод текста] Определенный язык текста:" , text_language)

                    # Переводим текст, если он не на русском языке

                    if text_language != 'ru':

                        translated_text = translator.translate(text_to_translate)

                        print("[Перевод текста] Переведенный текст:" , translated_text)

                    else:

                        translated_text = text_to_translate  # Оставляем текст без изменений

                        print("[Перевод текста] Текст на русском языке, перевод не требуется")

                    # Отправляем переведенный текст

                    await sent_message.edit_text(

                        f'🕊 <b><i>{translated_text}</i></b>' , parse_mode="HTML")


                except Exception as translate_error:

                    print("[Перевод текста] Ошибка перевода:" , translate_error)

                    await sent_message.edit_text("⚠️ Произошла ошибка при переводе.")

            else:

                print("[Перевод текста] Не указан текст для перевода.")

                await sent_message.edit_text("⚠️ Не указан текст для перевода.")


    except Exception as e:

        print("[Перевод текста] Произошла ошибка:" , e)

    def get_random_book_id():
        """Получение случайного ID книги для предотвращения повторов"""
        while True:
            response = requests.get('https://www.googleapis.com/books/v1/volumes?q=good+book&maxResults=40')
            data = response.json()

            if 'items' in data:
                books = data [ 'items' ]
                unseen_books = [ book for book in books if book [ 'id' ] not in shown_books ]
                if unseen_books:
                    chosen_book = random.choice(unseen_books)
                    shown_books.add(chosen_book [ 'id' ])
                    return chosen_book
            else:
                return None
    #if message.text.lower() in [ 'кут книга' , 'кут хорошая книга' ]:
        #"""Обработка сообщений для получения книги"""
        #book = get_random_book_id()

        #if book:
            #title = book [ 'volumeInfo' ].get('title' , 'Нет названия')
            #authors = ', '.join(book [ 'volumeInfo' ].get('authors' , [ 'Нет автора' ]))
            #description = book [ 'volumeInfo' ].get('description' , 'Нет описания')

            ## Перевод описания на русский язык
            #translator = GoogleTranslator(source='en' , target='ru')
            #translated_description = translator.translate(description)

            # Отправляем сообщение с информацией о книге
            #await message.answer(text='📚')
            #await message.reply(
                #f"<code><b>{title}</b></code>\n\nАвтор(ы) : <b>{authors}</b>\nОписание : <b>{translated_description}</b>" ,
                #parse_mode="HTML")
        #else:
            #await message.reply("📕 Не удалось найти книгу.")

    async def fetch_myth():
        """Получение мифа через API"""
        url = 'https://uselessfacts.jsph.pl/random.json?language=en'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                return data.get('text' , 'Не удалось получить миф.')

    async def translate_text(text , target_language='ru'):
        """Перевод текста на указанный язык"""
        translator = GoogleTranslator(target=target_language)
        return translator.translate(text)


    if message.text.lower() in [ 'кут миф','кут мифы','кут расскажи миф','кут, расскажи миф','кут, напиши миф','кут напиши миф','кут, напиши миф','кут напиши миф','кут, напиши миф','кут, расскажи миф' ]:
        myth = await fetch_myth()
        translated_myth = await translate_text(myth , 'ru')

        # Отправляем сообщение с переведенным мифом
        await message.reply(f"🧙🏼 <b><i>{translated_myth}</i></b>",parse_mode="HTML")

    async def get_poem():
        # Возьмем стихотворение из интернета
        async with aiohttp.ClientSession() as session:
            async with session.get('https://poetrydb.org/random') as response:
                data = await response.json()
                if data:
                    # Возьмем первое стихотворение из списка
                    poem = data [ 0 ]
                    author = poem.get('author' , 'Unknown Author')
                    lines = poem.get('lines' , [ ])

                    # Обработка строк для сохранения разделения строф
                    # В этом примере предполагается, что строфы разделены пустыми строками
                    formatted_poem = '\n\n'.join('\n'.join(line for line in lines).split('\n\n'))

                    return formatted_poem , author
                return None , None

    async def translate_text(text: str , target_language: str = 'ru') -> str:
        """Перевод текста на указанный язык"""
        try:
            translator = GoogleTranslator(target=target_language)
            translated_text = translator.translate(text)
            return translated_text
        except Exception as e:
            print(f"Ошибка при переводе: {e}")
            return text

    def limit_text(text: str , max_words: int) -> str:
        words = text.split()
        if len(words) > max_words:
            words = words [ :max_words ]
            text = ' '.join(words) + '...'
        return text


    if message.text.lower() in [ 'кут стих','кут, стих','кут напиши стих','кут расскажи стих','кут покажи стих','кут, напиши стих','кут, расскажи стих','кут, покажи стих' ]:
        poem , author = await get_poem()
        if poem:
            translated_poem = await translate_text(poem)
            limited_poem = limit_text(translated_poem , 200)
            response_text = f"<b><i>{limited_poem}</i></b>"
            # Отправляем сообщение с HTML разметкой
            await message.reply(response_text , parse_mode="HTML")
        else:
            await message.reply("Не удалось найти стихотворение.")

    async def get_random_fact():
        """Получить случайный факт из интернета."""
        async with aiohttp.ClientSession() as session:
            async with session.get('https://uselessfacts.jsph.pl/random.json?language=en') as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('text')
                return None

    async def translate_text(text , target_language='ru'):
        """Перевод текста на указанный язык."""
        translator = GoogleTranslator(target=target_language)
        return translator.translate(text)


    if message.text.lower() in [ 'кут факт','кут, факт','кут факты','кут, факты','кут, расскажи факт','кут расскажи факт','кут, напиши факт','кут напиши факт','кут покажи факт','кут, покажи факт' ]:
        fact = await get_random_fact()
        if fact:
            translated_fact = await translate_text(fact)
            await message.reply(f"🧠 <b><i>{translated_fact}</i></b>",parse_mode="HTML")
        else:
            await message.reply("🤯 Не удалось найти факт. Попробуйте позже.")

    def is_russian(text):
        """Проверяет, содержит ли текст русские буквы."""
        return bool(re.search(r'[а-яА-Я]' , text))

    GIPHY_API_KEY = '2F7yZTttn27QqbRc8fcobMiBhmbc2pRv'

    async def get_random_funny_image():
        """Функция для получения случайного смешного изображения из Pinterest."""
        access_token = 'YOUR_ACCESS_TOKEN'  # Замените на ваш токен доступа
        url = 'https://api.pinterest.com/v1/urls/search/'
        search_term = 'hilarious'
        params = {'query': search_term , 'access_token': access_token , 'fields': 'id,url,image'}

        async with aiohttp.ClientSession() as session:
            async with session.get(url , params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # Получаем случайное изображение
                    if 'data' in data and len(data [ 'data' ]) > 0:
                        random_image = random.choice(data [ 'data' ])
                        return random_image [ 'image' ] [ 'original' ] [ 'url' ]  # Получаем URL изображения
                    else:
                        print("🤯 Не удалось найти необходимые данные в ответе Pinterest.")
                elif response.status == 429:
                    print("🤯 Слишком много запросов! Попробуйте позже.")
                    await asyncio.sleep(5)  # Задержка перед повторной попыткой
                    return await get_random_funny_image()  # Повторная попытка
                else:
                    print(f"Ошибка Pinterest API: {response.status} - {response.reason}")
        return None
    # Обработчик сообщения
    #'кут мем' , 'кут мемы' , 'кут покажи мем' , 'кут покажи мемы' , 'кут, покажи мем','кут факт' , 'кут, факт' , 'кут факты' , 'кут, факты' , 'кут, расскажи факт' , 'кут расскажи факт' , 'кут, напиши факт' , 'кут напиши факт' , 'кут покажи факт' , 'кут, покажи факт' , 'кут стих' , 'кут, стих' , 'кут напиши стих' , 'кут расскажи стих' , 'кут покажи стих' , 'кут, напиши стих' , 'кут, расскажи стих' , 'кут, покажи стих' , 'кут миф' , 'кут мифы' , 'кут расскажи миф' , 'кут, расскажи миф' , 'кут, напиши миф' , 'кут напиши миф' , 'кут, напиши миф' , 'кут напиши миф' , 'кут, напиши миф' , 'кут, расскажи миф' , 'кут переведи' , 'кут перевод' , 'кут, переведи' , 'кут, перевод' ,
    #'/translation@CuteGamingBot' , 'кут посчитай' , 'кут, посчитай' , 'кут посчитай' , 'кут калькулятор' , 'кут, калькулятор' , 'кут калькулятор' , 'кут рассчитай' , 'кут, рассчитай' , 'кут рассчитай' , "кут реши" , "кут, реши" , "кут реши" , "Сколько будет" , "Сколько, будет" , "кут сколько будет" , "кут, сколько будет" , 'кут цитаты' , 'Кут цитаты' , 'кут цитата' , 'Кут цитата' , 'кут расскажи цитату' , 'кут, расскажи цитату' , 'кут покажи цитату' , 'кут, покажи цитату' , 'кут эмо' , 'Кут эмо' , 'кут эмодзи' , 'Кут эмодзи' , 'кут стик' , 'Кут стик' , 'Кут стикер' , 'кут стикер' , 'кут стикеры' , 'Кут стикеры ' , 'бот' , 'кут' , 'кут расскажи о себе' , 'кут, расскажи о себе' , 'кут что ты такое?' , 'кут что ты такое' , 'кут список' , 'Кут список' , 'кут сп' , 'Кут сп' , 'Кт сп' , 'кт сп' , "шар" , "кут время" , "время" , "кут погода" , "погода" , "кут скажи" , "кут повтори" , "кут рандом" , "кут орел или решка?" , "кут орёл или решка?" , "кут орел или решка" , "кут орёл или решка" , "кут решка или орел?" , "кут решка или орёл?" , "кут решка или орел" , "кут решка или орёл"

    if message.text.lower() in [ 'кут мем' , 'кут мемы' , 'кут покажи мем' , 'кут покажи мемы' , 'кут, покажи мем' ]:
        image_url = await get_random_funny_image()

        if image_url:
            try:
                await message.reply_photo(photo=image_url , caption="🤣 Вот ваше смешное изображение!")
                print("Изображение успешно отправлено.")
            except Exception as e:
                print(f"Ошибка при отправке изображения: {e}")
                await message.reply("🤯 Не удалось отправить изображение, попробуйте позже.")
        else:
            await message.reply("🤯 Не удалось найти изображение, попробуйте позже.")


    if message.text.lower() in [ 'кут число','кут, число','кут, выбери рандом число','кут выбери рандом число','кут скажи рандом число','кут, скажи рандом число','кут, рандом число','кут рандом число' ]:
        random_number = random.randint(1 , 10000)
        formatted_win_amount = "{:,.0f}".format(random_number).replace(',' , '.')
        await message.answer(f"🎲 <b>{formatted_win_amount}</b>", parse_mode="HTML")

    def format_number(number):
        return f"{number:,}".replace("," , " ")



    # Проверяем, что сообщение имеет достаточное количество частей



# Пример функции форматирования числа




    # Функция для перевода текста на язык назначения
    DetectorFactory.seed = 0

    # Функция для перевода текста на язык назначения
    def translate_text(text , dest_language='en'):
        try:
            translated = GoogleTranslator(source='auto' , target=dest_language).translate(text)

            return translated
        except Exception as e:
            print(f"Ошибка при переводе текста: {e}")
            return text

    _HTTP_TIMEOUT = 6.0
    _HTTP_UA = "Mozilla/5.0 (compatible; CuteBot/1.0; +https://t.me/)"

    def _safe_term(raw: str , * , max_len: int = 80) -> str:
        """Нормализует ввод (безопасно и стабильно)."""
        text = (raw or "").strip()
        text = re.sub(r"\s+" , " " , text)
        # убираем управляющие символы
        text = re.sub(r"[\x00-\x1f\x7f]" , "" , text)
        return text [ :max_len ].strip()

    def _detect_lang_safe(text: str) -> str:
        """Определение языка без падений."""
        try:
            t = (text or "").strip()
            if not t:
                return "ru"
            return detect(t)
        except Exception as e:
            print(f"🟨 [DEF][LANG][WARN] Ошибка при определении языка: {e}")
            return "ru"

    def _translate_safe(text: str , target_lang: str) -> str:
        """Перевод без падений (translate_text - твоя функция)."""
        try:
            out = translate_text(text , target_lang)
            return (out or "").strip()
        except Exception as e:
            print(f"🟥 [DEF][TRANSLATE][ERROR] Перевод в '{target_lang}' упал: {e}")
            return (text or "").strip()

    # Функция для получения определения из англоязычной Википедии
    def get_definition_from_wikipedia(term):
        term = _safe_term(term , max_len=120)
        if not term:
            return None

        # ✅ обязательно экранируем term для URL
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(term)}"
        headers = {"User-Agent": _HTTP_UA , "Accept": "application/json"}

        try:
            response = requests.get(url , headers=headers , timeout=_HTTP_TIMEOUT)
        except Exception as e:
            print(f"🟥 [DEF][WIKI][ERROR] Запрос упал: {e} term={term!r}")
            return None

        if response.status_code != 200:
            print(f"🟨 [DEF][WIKI][WARN] Не удалось получить данные: status={response.status_code} term={term!r}")
            return None

        try:
            data = response.json()
        except Exception as e:
            print(f"🟥 [DEF][WIKI][ERROR] JSON decode error: {e} term={term!r}")
            return None

        # Проверяем наличие 'extract' и его непустоту
        extract = (data.get("extract") or "").strip()
        if not extract:
            return None

        # ✅ если пришла неоднозначность - лучше считать как "не нашли"
        # (на wiki это type=disambiguation)
        try:
            if str(data.get("type" , "")).lower() == "disambiguation":
                return None
        except Exception:
            pass

        return extract

    # Функция для получения определения из DuckDuckGo
    def get_definition_from_duckduckgo(term):
        term = _safe_term(term , max_len=120)
        if not term:
            return None

        # ✅ параметры без pretty=1 (он не нужен), добавим no_html=1, skip_disambig=1
        url = f"https://api.duckduckgo.com/?q={quote(term)}&format=json&no_html=1&skip_disambig=1"
        headers = {"User-Agent": _HTTP_UA , "Accept": "application/json"}

        try:
            response = requests.get(url , headers=headers , timeout=_HTTP_TIMEOUT)
        except Exception as e:
            print(f"🟥 [DEF][DDG][ERROR] Запрос упал: {e} term={term!r}")
            return None

        if response.status_code != 200:
            print(f"🟨 [DEF][DDG][WARN] status={response.status_code} term={term!r}")
            return None

        try:
            data = response.json()
        except Exception as e:
            print(f"🟥 [DEF][DDG][ERROR] JSON decode error: {e} term={term!r}")
            return None

        # 1) AbstractText
        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            return abstract

        # 2) Definition (иногда бывает)
        definition = (data.get("Definition") or "").strip()
        if definition:
            return definition

        # 3) RelatedTopics (часто там первая годная выжимка)
        rel = data.get("RelatedTopics") or [ ]
        try:
            for item in rel:
                if isinstance(item , dict) and "Text" in item:
                    txt = (item.get("Text") or "").strip()
                    if txt:
                        return txt
                if isinstance(item , dict) and isinstance(item.get("Topics") , list):
                    for sub in item [ "Topics" ]:
                        if isinstance(sub , dict) and "Text" in sub:
                            txt = (sub.get("Text") or "").strip()
                            if txt:
                                return txt
        except Exception:
            pass

        return None

    # (оставил как у тебя, но безопаснее)
    words = (message.text or "").split()

    async def textrazzzz(message , original_term):
        original_term = _safe_term(original_term , max_len=80)

        if not original_term:
            await message.answer(
                '🛠 <b>Напиши слово/термин, чтобы я нашёл определение.</b>' , parse_mode="HTML")
            return

        detected_language = _detect_lang_safe(original_term)

        # Переводим на английский, если текст не на английском
        if detected_language != "en":
            term = _translate_safe(original_term , "en")
        else:
            term = original_term

        term = _safe_term(term , max_len=120)

        # Пробуем получить определение с англоязычной Википедии
        definition = get_definition_from_wikipedia(term)

        if definition:
            # Переводим текст ответа с английского на русский
            translated_definition = _translate_safe(definition , "ru")
            await message.answer(
                f'🌐 <b>Вот что я нашел о "{original_term}"</b>:\n\n<b><i>{translated_definition}</i></b>' ,
                parse_mode="HTML")
            return

        # Если не удалось найти информацию на Википедии, пробуем DuckDuckGo
        definition = get_definition_from_duckduckgo(term)
        if definition:
            translated_definition = _translate_safe(definition , "ru")
            await message.answer(
                f'🌐 <b>Вот что я нашел о "{original_term}"</b>:\n\n<b><i>{translated_definition}</i></b>' ,
                parse_mode="HTML")
            return

        # Если нигде не нашли
        await message.answer(
            f'🛠 Не удалось найти ответ о "{original_term}".\n\n'
            f'🛠 Возможно, это связано с тем, что информация отсутствует в открытых источниках.' , parse_mode="HTML")


    if len(words) > 1 and words [ 0 ].lower() in [ "кут","кут," , "что" , "кто" , "расскажи" ]:
        if words [ 1 ].lower() in [ "такое" , "такой" , "такая" , "о" ]:
            original_term = ' '.join(words [ 2: ]).rstrip('?')  # Удаляем вопросительный знак, если он есть
            await textrazzzz(message , original_term)  # Вызов функции с передачей аргументов

        elif len(words) > 2 and words [ 1 ].lower() in [ "такое" , "такой" , "такая" , "о" , "что" , "кто" ,
                                                         "расскажи" ] and words [ 2 ].lower() in [ "такое" , "такая" ,
                                                                                                   "такой" , "о" ]:
            original_term = ' '.join(words [ 3: ]).rstrip('?')  # Удаляем вопросительный знак, если он есть
            await textrazzzz(message , original_term)  # Вызов функции с передачей аргументов








        # Определяем язык исходного текста

    async def get_world_news():
        url = 'https://newsapi.org/v2/top-headlines?language=en&apiKey=2af0327459084a61a04cd423c48a0e9f'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:

                    response_text = await response.text()


                    if response.status == 200:
                        data = await response.json()

                        if 'articles' in data and len(data [ 'articles' ]) > 0:
                            return data [ 'articles' ]
                        else:
                            print("Нет доступных статей в ответе.")

        except Exception as e:
            print(f"Ошибка при запросе новостей: {e}")
        return None

    def format_date(published_at):
        try:
            # Преобразуем строку даты в объект datetime с использованием dateutil
            dt_utc = parser.isoparse(published_at)
            # Добавляем 3 часа для преобразования в Московское время
            dt_msk = dt_utc + timedelta(hours=3)
            # Форматируем дату и время в нужный формат
            return dt_msk.strftime('%d.%m.%Y в %H:%M')
        except ValueError:
            return 'Неизвестно'

    if message.text.lower() in ["кут, расскажи тему","кут расскажи тему","кут, расскажи тему для разговора","кут расскажи тему для разговора","кут, подскажи тему для разговора","кут подскажи тему для разговора","кут, темы для разговора","кут темы для разговора","кут темы","кут, темы","кут тема для разговора","кут, тема для разговора","кут темка для разговора","кут, темка для разговора"]:
        topics = [ "Какую суперспособность ты бы хотел(а) иметь и как бы её использовал(а)?" ,
            "Если бы твоя жизнь была фильмом, кого бы ты выбрал(а) на главную роль?" ,
            "Какой самый смешной или необычный сон тебе снился?" ,
            "Если бы тебе предложили бесплатный билет в любую страну, куда бы ты поехал(а) и почему?" ,
            "Какое блюдо ты мог(ла) бы есть каждую неделю без ограничений?" ,
            "Какой анекдот заставляет тебя смеяться каждый раз?" ,
            "Если бы ты придумал(а) новый праздник, каким бы он был?" ,
            "Что бы ты выбрал(а): отказаться от сладкого или от видеоигр?" ,
            "Как бы выглядела твоя вечеринка с неограниченным бюджетом?" ,
            "Какой фильм или сериал ты мог(ла) пересматривать бесконечно?" , "Какую музыку ты чаще всего слушаешь?" ,
            "В какие игры ты любишь играть и почему?" , "Какая книга изменила твой взгляд на жизнь?" ,
            "Какой концерт стал для тебя самым запоминающимся?" , "Кем из известных людей ты восхищаешься и почему?" ,
            "Какой навык ты хотел(а) бы освоить в ближайшее время?" , "Самое яркое воспоминание из детства?" ,
            "О чём ты мечтал(а) в детстве и что изменилось?" ,
            "Какое событие произвело на тебя наибольшее впечатление в последнее время?" ,
            "С каким человеком из прошлого ты бы хотел(а) встретиться и о чём спросить?" ,
            "Какие цели у тебя на ближайший год?" , "Опиши свой идеальный выходной день." ,
            "Если бы тебя перенесли на 10 лет вперёд, чем бы ты занимался(ась)?" ,
            "Какая книга или фильм вдохновили тебя на мечту?" , "Зачем мы живём, по-твоему?" ,
            "Что значит быть взрослым?" , "Что важнее: свобода или безопасность?" , "Что для тебя счастье?" ,
            "Есть ли судьба или всё в наших руках?" , "Есть ли жизнь за пределами Земли?" ,
            "Что важнее: ум или доброта?" , "Что для тебя настоящая дружба?" , "Что значит успех для тебя?" ,
            "Придумай новый вид спорта и опиши правила." , "О чём был бы твой фильм, если бы ты написал(а) сценарий?" ,
            "Придумай сюжет для комикса." , "Что бы ты изменил(а) в своём городе, если бы стал(а) мэром?" ,
            "Если бы у тебя была волшебная кисть, что бы ты нарисовал(а)?" ,
            "Придумай смешную рекламу обычного предмета." ,
            "Если бы на деревьях росли гаджеты, какие бы ты посадил(а)?" ,
            "Какой книжный или киногерой мог бы жить в реальном мире?" , "Придумай новое слово и его значение." ,
            "Какими способностями обладал бы твой робот-помощник?" , "Какие технологии появятся через 20 лет?" ,
            "Что интересного из природы или космоса ты узнал(а) недавно?" , "Как соцсети изменили наше общение?" ,
            "Какое научное открытие удивило тебя?" , "Могут ли люди жить на других планетах?" ,
            "Какие приложения или гаджеты упрощают твою жизнь?" ,
            "Какую необычную профессию ты хотел(а) бы попробовать?" ,
            "Если бы ты мог(ла) выбрать любую эпоху для жизни, какую бы выбрал(а)?" ,
            "Какая страна тебе кажется самой загадочной?" ,
            "Если бы ты был(а) волшебником, какой был бы твой первый закон?" ,
            "Если бы можно было получить любую профессию за день, какую бы ты выбрал(а)?" ,
            "Какой язык ты хотел(а) бы выучить и почему?" , "Что для тебя идеальный дом?" ,
            "Какой талант ты хотел(а) бы иметь?" , "Какая наука тебе кажется самой интересной?" ,
            "Если бы ты открыл(а) свой ресторан, что бы в нём подавали?" ,
            "Какую вещь ты хотел(а) бы улучшить в повседневной жизни?" ,
            "Если бы можно было стать животным на день, кем бы ты стал(а)?" ,
            "Какой момент в твоей жизни ты бы хотел(а) повторить?" ,
            "Если бы ты мог(ла) путешествовать во времени, куда бы отправился(ась)?" ,
            "Как бы ты описал(а) свою мечту одним словом?" , "Что важнее: иметь знания или опыт?" ,
            "Какую привычку ты хотел(а) бы развить?" , "Какая страна тебе кажется идеальной для жизни?" ,
            "Какую работу ты мечтал(а) бы попробовать на один день?" , "Каким был бы твой идеальный завтрак?" ,
            "Если бы тебе дали миллион долларов, как бы ты их потратил(а)?" ,
            "Что бы ты хотел(а) сделать в этом году?" , "Какая твоя самая безумная мечта?" ,
            "Что самое важное в дружбе?" , "Что для тебя значит быть успешным человеком?" ,
            "Если бы ты создал(а) новый предмет в школе, чему бы он учил?" ,
            "Если бы ты был(а) героем книги, каким бы был твой суперспособность?" ,
            "Какая песня точно описывает твоё настроение сейчас?" , "Какие черты ты ценишь в людях больше всего?" ,
            "Как ты понимаешь слово 'счастье'?" , "Что бы ты сказал(а) себе 5 лет назад?" ,
            "Какое место на Земле ты мечтаешь посетить?" , "Кем ты мечтал(а) стать в детстве?" ,
            "Если бы ты придумал(а) свой собственный бренд, каким бы он был?" , "Что для тебя значит слово 'дом'?" ,
            "Если бы ты мог(ла) прожить день в теле другого человека, кого бы выбрал(а)?" ,
            "Какое качество ты бы хотел(а) развить в себе?" , "Какая привычка помогает тебе быть счастливее?" ,
            "Какие три вещи ты бы взял(а) на необитаемый остров?" , "Что бы ты изменил(а) в мире, если бы мог(ла)?" ,
            "Какую суперсилу ты бы хотел(а) получить на 1 день?" , "Что тебя вдохновляет больше всего?" ,
            "Если бы ты стал(а) знаменитым(ой), чем именно?" , "Какой самый безумный поступок ты совершал(а)?" ,
            "Что бы ты сделал(а) в первый день на новой планете?" ,
            "Что бы ты выбрал(а): быть невидимым(ой) или читать мысли?" ,
            "Какое событие в жизни сделало тебя сильнее?" , "Какой подарок был для тебя самым памятным?" ,
            "Что бы ты изменил(а) в своей школе/университете?",
        "Жить монстром или умереть человеком?" ,
        "Пожертвовать собой ради всех или всех ради себя?" ,
        "Забыть свою жизнь или помнить каждый момент боли?" ,
        "Спасти друга, предав всех остальных, или спасти всех, предав друга?" ,
        "Бороться до конца или сдаться с достоинством?" ,
        "Любить без ответа или быть любимым без любви?" ,
        "Умереть героем или жить в стыде?" ,
        "Быть свободным в одиночестве или в плену среди людей?" ,
        "Жить в мире лжи или умереть за правду?" ,
        "Отдать всё ради мечты или отказаться от мечты ради спокойствия?" ,
        "Стать спасителем или разрушителем?" ,
        "Потерять воспоминания или потерять чувства?" ,
        "Вечно искать истину или жить в удобной лжи?" ,
        "Стать чудовищем ради справедливости или сохранить честь, проиграв?" ,
        "Простить врага или мстить до конца?" ,
        "Пожертвовать счастьем ради долга или долгом ради счастья?" ,
        "Быть первым среди худших или последним среди лучших?" ,
        "Жить ради себя или ради других?" ,
        "Быть слепым к боли мира или страдать вместе с ним?" ,
        "Стать героем для всех или другом для одного?" ,
        "Убить во имя мира или умереть, защищая идеалы?" ,
        "Потерять всё ради нового начала или сохранить всё, боясь перемен?" ,
        "Выжить любой ценой или умереть с гордостью?" ,
        "Промолчать, когда можешь спасти, или говорить, рискуя всем?" ,
        "Жить в воспоминаниях или отпустить и забыть?" ,
        "Стать королём чужой мечты или хозяином своей реальности?" ,
        "Предать веру ради спасения или пасть за веру?" ,
        "Делать добро втайне или быть признанным за добро?" ,
        "Победить ценой совести или проиграть сохраняя честь?" ,
        "Жить в комфорте среди лицемеров или в бедности среди искренних?" ,
        "Выбрать одиночество ради свободы или связь ради безопасности?" ,
        "Стать символом надежды или оружием страха?" ,
        "Принять тьму внутри или бороться с ней вечно?" ,
        "Отказаться от мечты ради мира или рискнуть всем ради мечты?" ,
        "Любить вечно, страдая, или никогда не узнать любовь?" ,
        "Потерять голос или потерять волю?" ,
        "Идти против мира или идти против себя?" ,
        "Жить, зная правду, или умереть в неведении?" ,
        "Стать тем, кого ненавидишь, чтобы победить?" ,
        "Жить в бесконечной войне или умереть в кратком мире?" ,
        "Пожертвовать памятью о себе ради мира или жить в славе среди разрушений?" ,
        "Бороться за то, что не можешь изменить, или отпустить?" ,
        "Стать легендой трагедии или обычным человеком счастья?" ,
        "Принять вину за чужое спасение или отказаться от неё?" ,
        "Жить с вечным сожалением или с вечной надеждой?" ,
        "Разрушить один город ради спасения мира или искать другой путь, рискуя всем?" ,
        "Жить в страхе или умереть в порыве свободы?" ,
        "Уничтожить врага или протянуть ему руку?" ,
        "Стать бессмертным, теряя себя, или остаться собой и исчезнуть?" ,
        "Быть жестоким ради любви или милосердным ради ненависти?" ,
        "Строить жизнь на лжи или умереть за истину?" ,
        "Довериться однажды и быть преданным или никогда никому не доверять?" ,
        "Пожертвовать мечтой ради семьи или оставить всех ради мечты?" ,
        "Жить, зная свою судьбу, или идти в неизвестность?" ,
        "Быть спасённым ценой чужой жизни или погибнуть самому?" ,
        "Стать слугой идеалов или хозяином хаоса?" ,
        "Пройти через предательство или никогда не знать верности?" ,
        "Потерять свободу ради любви или потерять любовь ради свободы?" ,
        "Жить в вечной вине или умереть искупив?" ,
        "Стать силой перемен или жертвой стабильности?" ,
        "Жить без чувств или умереть от эмоций?" ,
        "Бороться за справедливость или за милосердие?" ,
        "Спасти одного человека или тысячу?" ,
        "Принять чужую боль или причинить свою?" ,
        "Остаться человеком среди зверей или стать зверем среди людей?" ,
        "Вечно гореть в поисках смысла или угаснуть в покое?" ,
        "Жить под чужим именем или умереть своим?" ,
        "Предать друга ради победы или проиграть ради друга?" ,
        "Отказаться от правды ради жизни или умереть за неё?" ,
        "Жить вечно в одиночестве или жить кратко среди любимых?" ,
        "Бороться за недостижимое или довольствоваться малым?" ,
        "Жить в страхе перемен или умереть ради шанса?" ,
        "Стать машиной без чувств или человеком с болью?" ,
        "Жить в плену прошлого или строить без основ?" ,
        "Умереть ради идеи или ради человека?" ,
        "Стать легендой ужаса или забытым героем?" ,
        "Сражаться с собой или с миром?" ,
        "Жить во сне или умереть в реальности?" ,
        "Дать шанс врагу или добить его?" ,
        "Отказаться от силы ради любви или от любви ради силы?" ,
        "Потерять всё ради свободы или сохранить всё ради зависимости?" ,
        "Быть спасителем, которого ненавидят, или тираном, которого любят?" ,
        "Принести мир ценой собственной души или сохранить душу ценой войны?" ,
        "Стать памятью или вечной загадкой?" ,
        "Сломить себя ради чужого счастья или сохранить себя в одиночестве?" ,
        "Стать кем угодно ради мести или кем-то ради прощения?" ,
        "Принять вечный поиск или вечное разочарование?" ,
        "Быть верным своим мечтам или ожиданиям других?" ,
        "Жить, следуя правилам, или умереть, следуя сердцу?" ,
        "Быть силой разрушения или шансом на новый мир?" ,
        "Любить, зная о потере, или никогда не рисковать?" ,
        "Стать голосом правды в мире лжи или молчаливым свидетелем?" ,
        "Уйти с миром или остаться и бороться?" ,
        "Жить ради памяти о прошлом или ради надежды на будущее?" ,
        "Сдаться, чтобы сохранить жизнь, или умереть за свободу?" ,
        "Быть одиноким королём или счастливым скитальцем?" ,
        "Стать кем-то ради мести или кем-то ради прощения?","Жить в вечном страхе или умереть свободным?",
"Стать богом среди людей или остаться человеком среди богов?",
"Потерять всё ради одной мечты или отказаться от мечты ради всего?",
"Жить в мире иллюзий или умереть в жестокой правде?",
"Остаться добрым в мире зла или стать злым ради добра?",
"Умереть за веру или жить в предательстве?",
"Принять свою тьму или бороться до конца?",
"Стать героем для истории или для одного сердца?",
"Отказаться от счастья ради истины или от истины ради счастья?",
"Сохранить любовь, потеряв себя, или сохранить себя, потеряв любовь?",
"Быть любимым, но жить во лжи, или быть ненавидимым за правду?",
"Жить в мире без чувств или умереть, переживая каждую эмоцию?",
"Уйти без следа или оставить за собой хаос?",
"Жить ради мести или простить, освободив себя?",
"Пожертвовать честью ради победы или проиграть с честью?",
"Быть последним праведником или первым предателем?",
"Умереть с мечтой или жить без неё?",
"Жить вечно в одиночестве или умереть в толпе?",
"Принять мир таким, какой он есть, или разрушить его в поисках лучшего?",
"Жить без будущего или умереть ради мечты о нём?",
"Быть вечным странником или пленником одного места?",
"Потерять свою душу ради спасения других или сохранить свою ценой их жизней?",
"Сдаться в последний момент или сражаться до последнего вздоха?",
"Стать врагом для спасения друзей или другом для гибели мира?",
"Принять чужую вину или позволить им упасть?",
"Быть королём пустоты или воином света?",
"Сражаться за любовь или отпустить её ради её счастья?",
"Стать частью системы или разбить её ценой себя?",
"Жить вечной надеждой или вечным разочарованием?",
"Быть забытой правдой или воспетой ложью?",
"Отказаться от своих принципов ради выживания или пасть верным себе?",
"Жить с чувством вины или умереть с чувством долга?",
"Стать легендой боли или обычным свидетелем счастья?",
"Сгореть ярко, но быстро, или тлеть вечно?",
"Потерять тело или потерять душу?",
"Быть героем в глазах людей или в своих собственных?",
"Умереть за чужую мечту или за свою?",
"Жить среди врагов или умереть среди друзей?",
"Стать чудовищем для добра или ангелом для зла?",
"Жить чужой жизнью или умереть за свою?",
"Выбрать легкий путь или верный?",
"Быть спасителем одного или судьёй миллионов?",
"Жить в страхе поражения или умереть ради попытки?",
"Бороться за идею или за любовь?",
"Стать оружием или щитом?",
"Принять свою судьбу или изменить её ценой всего?",
"Стать голосом революции или тенью порядка?",
"Остаться верным слову или верным сердцу?",
"Жить, скрывая истину, или умереть, раскрыв её?",
"Быть героем чужих ожиданий или врагом своих страхов?",
"Потерять разум ради спасения или сохранить разум ценой гибели?",
"Стать пленником времени или его хозяином?",
"Жить чужими правилами или умереть по своим?",
"Спасать мир, уничтожая его части, или сохранить всё, рискуя всем?",
"Стать одним из многих или единственным, кто пошёл своим путём?",
"Выбрать боль ради роста или комфорт ради стагнации?",
"Быть королём тишины или рыцарем крика?",
"Принести свет туда, где все выбрали тьму, или остаться с ними во тьме?",
"Жить среди теней прошлого или умереть в свете настоящего?",
"Пожертвовать любовью ради долга или долгом ради любви?",
"Быть последним голосом надежды или первым камнем сомнений?",
"Принять закат или сражаться за рассвет?",
"Стать силой разрушения ради перерождения или оберегать умирающий мир?",
"Жить предателем или умереть верным?",
"Быть проклятым ради спасения или благословлённым ради разрушения?",
"Отказаться от веры ради выживания или умереть за неё?",
"Сражаться с собой или против мира?",
"Быть частью прошлого или строить будущее?",
"Жить под маской или умереть лицом к лицу?",
"Пожертвовать мечтой ради справедливости или справедливостью ради мечты?",
"Стать символом борьбы или символом утраты?",
"Жить без надежды или умереть за неё?",
"Построить империю на крови или умереть за мир?",
"Выбрать путь боли или путь забвения?",
"Стать золотой клеткой для других или быть вольным узником?",
"Быть героем чьей-то жизни или призраком чьей-то памяти?",
"Сражаться ради славы или ради правды?",
"Стать голосом тишины или криком безмолвия?",
"Быть источником перемен или хранителем порядка?",
"Жить на коленях или умереть стоя?",
"Быть вечно виноватым или вечно забытым?",
"Принести свет ценой вечной ночи или уйти вместе с ней?",
"Стать мечтой ради разрушения или кошмаром ради спасения?",
"Выбрать путь страха или путь веры?",
"Жить в роли зрителя или умереть героем сцены?",
"Пожертвовать разумом ради чувств или чувствами ради разума?",
"Быть победителем войны или героем мира?",
"Сражаться за слабых или уничтожать сильных?",
"Жить в золотой клетке или умереть на свободе?",
"Стать символом чужой свободы или рабом своей мечты?",
"Выбрать вечное одиночество или риск быть преданным?",
"Быть героем истории или героем сердца?",
"Жить в страхе потерь или умереть в момент триумфа?",
"Стать разрушением ради созидания или созиданием в разрушении?",
"Быть голосом совести или мечом наказания?",
"Жить на обломках мира или умереть, создав новый?",
"Пожертвовать всем ради шанса или ничего ради безопасности?",
"Быть искрой надежды или пламенем отчаяния?",
"Стать стеной для других или дорогой для себя?",
"Жить в поисках смысла или умереть, не найдя его?",
"Потерять всё ради любви или сохранить всё ради одиночества?" ]

        random_topic = random.choice(topics)
        await message.reply(f"<b>🌿 {random_topic}</b>",parse_mode="HTML")

    if message.text.lower() in ['кут новости','кут, новости','кут покажи новости','кут, покажи новости','кут покажи недавние новости','кут, покажи недавние новости','кут покажи новости мира','кут, покажи новости мира','кут открой новости','кут, открой новости']:
        articles = await get_world_news()  # Получаем новости

        if articles:
            translator = GoogleTranslator(source='en' , target='ru')
            news_messages = [ ]

            # Ограничиваем количество новостей до 5
            for article in articles [ :5 ]:
                title = article.get('title' , 'Без заголовка')
                description = article.get('description' , 'Без описания') or ''  # Заменяем None на пустую строку
                url = article.get('url' , '#')
                published_at = article.get('publishedAt' , 'Неизвестно')

                # Переводим заголовок и описание
                translated_title = translator.translate(title)
                if isinstance(
                        description , str) and description:  # Проверяем, что описание является строкой и не пустое
                    translated_description = translator.translate(description)
                else:
                    translated_description = ''

                # Форматируем дату и время
                formatted_date = format_date(published_at)

                # Формируем текст сообщения
                news_message = (f"\n\n🗞️ <b>{translated_title}</b>\n"
                                f"📅 {formatted_date}\n"
                                f"<i>{translated_description}</i>\n"
                                f"🔗 <a href='{url}'>Читать далее</a>")
                news_messages.append(news_message)

            if news_messages:
                response_message = "\n".join(news_messages)
                await message.reply(response_message , parse_mode="HTML")
            else:
                await message.reply("🛠 Не удалось получить новости.")
        else:
            await message.reply("🛠 Не удалось получить новости.")

    async def get_joke():
        url = 'https://v2.jokeapi.dev/joke/Any'  # Используем JokeAPI для получения анекдотов
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'joke' in data:
                            return data [ 'joke' ]
                        elif 'setup' in data and 'delivery' in data:
                            return f"{data [ 'setup' ]} - {data [ 'delivery' ]}"
                    return "🛠 Не удалось получить анекдот."
        except Exception as e:
            print(f"Ошибка при запросе анекдота: {e}")
            return "🛠 Ошибка при получении анекдота."

    async def translate_joke(text , target_language='ru'):
        translator = GoogleTranslator(source='en' , target=target_language)
        try:
            translated_text = translator.translate(text)
            return translated_text
        except Exception as e:
            print(f"Ошибка при переводе текста: {e}")
            return text  # Возвращаем оригинальный текст в случае ошибки

    if message.text.lower() in [ 'кут анекдот','кут, анекдот','кут черные шутки','кут, черные шутки','кут черная шутка','кут, черная шутка','кут расскажи черную шутку','кут, расскажи черную шутку','кут расскажи темную шутку','кут, расскажи темную шутку','кут темная шутка','кут, темная шутка','кут шутка','кут, шутка','кут шутки','кут, шутки','кут расскажи шутку','кут, расскажи шутку','Кут напиши шутку','Кут, напиши шутку','кут, расскажи анекдот','кут, расскажи шутку','кут, напиши шутку','кут, напиши анекдот' ]:
        joke = await get_joke()
        translated_joke = await translate_joke(joke)
        await message.reply(f"🚀 <b><i>{translated_joke}</i></b>", parse_mode="HTML")

    async def get_exchange_rates():
        url = 'https://v6.exchangerate-api.com/v6/fa0d71fe30e38146e7b9eb72/latest/USD'  # Получаем курсы относительно доллара США
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        print(f"Не удалось получить данные о курсах валют: {response.status}")
                        return None
        except Exception as e:
            print(f"Ошибка при запросе курсов валют: {e}")
            return None

    async def fetch_time(session , url):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Не удалось получить данные: {response.status}")
                    return None
        except Exception as e:
            print(f"Ошибка при запросе времени: {e}")
            return None

    async def get_current_time(retries=3):
        urls = {'Moscow': 'http://worldtimeapi.org/api/timezone/Europe/Moscow' ,
            'Kiev': 'http://worldtimeapi.org/api/timezone/Europe/Kiev'}

        times = {}

        async with aiohttp.ClientSession() as session:
            for city , url in urls.items():
                for attempt in range(retries):
                    data = await fetch_time(session , url)
                    if data:
                        datetime_str = data [ 'datetime' ]
                        dt = parser.isoparse(datetime_str)
                        times [ city ] = dt.strftime('%d.%m.%Y в %H:%M')
                        break  # Выход из цикла попыток, если запрос успешен
                    else:
                        print(f"Попытка {attempt + 1} не удалась для {city}.")
                        await asyncio.sleep(2)  # Подождите перед повторной попыткой
                else:
                    times [ city ] = 'Неизвестно'  # Если все попытки не удались

        return times

    #if message.text.lower() in [ 'курс валют' , 'кут покажи курс валют' , 'кут, покажи курс валют' ,
        #'кут покажи курсы валют' , 'кут, покажи курсы валют' , 'кут покажи курс' , 'кут, покажи курс' ]:
        #data = await get_exchange_rates()
        #if data:
            #rates = data.get('conversion_rates' , {})
            #times = await get_current_time()

            #currency_message = (f"💵 <b>Приблизительный курс валют</b>\n\n"
                                #f"🇷🇺 <b><i>Москва : {times.get('Moscow' , 'Неизвестно')}</i></b>\n"
                                #f"🇺🇦 <b><i>Киев : {times.get('Kiev' , 'Неизвестно')}</i></b>\n\n"
                                #f"💵 <b><i>Доллар США (USD)</i></b> : 1$\n"
                                #f"💶 <b><i>Евро (EUR)</i></b> : <b>{rates.get('EUR' , 'Неизвестно')}</b> EUR за 1$(USD)\n"
                                #f"💳 <b><i>Гривна (UAH)</i></b> : <b>{rates.get('UAH' , 'Неизвестно')}</b> UAH за 1$(USD)\n"
                                #f"💰 <b><i>Российский рубль (RUB)</i></b> : <b>{rates.get('RUB' , 'Неизвестно')}</b> RUB за 1$(USD)\n"
                                #f"💵 <b><i>Белорусский рубль (BYN)</i></b> : <b>{rates.get('BYN' , 'Неизвестно')}</b> BYN за 1$(USD)\n"
                                #f"💴 <b><i>Японская иена (JPY)</i></b> : <b>{rates.get('JPY' , 'Неизвестно')}</b> JPY за 1$(USD)\n")

            #await message.reply(currency_message , parse_mode="HTML")
        #else:
            #await message.reply("🛠 Не удалось получить данные о курсах валют.")

    if message.text.lower() in [ 'кут гугл','кут открой гугл','кут дай мне гугл' ]:
        keyboard = InlineKeyboardMarkup()
        google_button = InlineKeyboardButton(
            text="Открыть Google" , url="https://www.google.com"  # URL, который будет открыт
        )
        keyboard.add(google_button)

        # Отправка сообщения с кнопкой
        await message.reply("🌐" , reply_markup=keyboard)

    if message.text.lower() in [ 'кут как ты?' , 'кут, как ты?','кут, как ты','кут как ты','кут, как дела?','кут как дела?','кут как дела','кут, как дела','кут, как твои дела?','кут как твои дела?','кут как твои дела','кут, как твои дела']:
        answer = random.choice(
            [ "Огонь, как дракон на вечеринке!" , "Чётко, как у кота на подушке." ,
                "На расслабоне, как Wi-Fi без пароля." , "Всё ништяк, как пончик в глазури." ,
                "Топчик, как новый мем." , "Всё ровно, как трек в плейлисте." ,
                "Живу, как кнопка 'не нажимать' - не трогают и то хорошо." ,
                "Как будто пятница, а завтра понедельник." , "На уровне, как зарядка на 10%." ,
                "Кайфую, как кот в тёплом месте." , "Норм, как шнурок без узлов." , "Как Wi-Fi - иногда пропадаю." ,
                "Летс гоу, как будто суббота!" , "Живу, как челлендж в TikTok - странно, но весело." ,
                "Как пельмени - горячо, но держусь." , "В норме, как кот в коробке." ,
                "Заряжен, как телефон после ночи." , "Всё чётко, как стрим на хорошем Wi-Fi." ,
                "Топлю, как лыжник на спуске." , "Флекс, как на новый трек." , "Чилл, как на пляже." ,
                "Норм, как новая серия любимого сериала." , "Ору, как кот на луну." , "Свеж, как кофе с утра." ,
                "Как рамен - горячо и быстро." , "Ловлю вайб, как в пятницу вечером." ,
                "Плыву по течению, как уточка в бассейне." , "Как сосиска в тесте - держусь!" ,
                "На стиле, как новый сникерс." , "Заряжаюсь, как телефон на 1%." , "Топлю, как катер по реке." ,
                "Чилл, как кот на диване." , "Как новая песня в плейлисте - свежо!" , "На волне, как серфер." ,
                "Держусь, как кабель без зарядки." , "Качаюсь, как в тренажёрке." , "Как будто все задания сделал." ,
                "Как в рекламе: 'Всё хорошо!'" , "На стиле, как новый костюм." , "В норме, как Wi-Fi дома." ,
                "Норм, как будто с утра зарядился." , "Флекс, как будто тикток." , "На волне, как будто на серфе." ,
                "Дела огонь, как барбекю на пикнике." , "Всё круто, как первый день отпуска." ,
                "Норм, как будто выходной." , "Как пирожок - тёплый и мягкий." , "Всё ровно, как дорога без ям." ,
                "Как кофейный автомат - всегда готов!" , "Лечу, как самолёт в небе." , "На чиле, как мороженое летом." ,
                "Как бутерброд - в порядке!" , "Дела норм, как всегда." , "Как часы - тикаю по графику." ,
                "В порядке, как кот под одеялом." , "Всё чётко, как маршрут на карте." ,
                "Как песок на пляже - тепло и спокойно." , "Как зарядка - иногда теряюсь, но быстро восстанавливаюсь." ,
                "Как тучка - немного мрачновато, но всё ок." , "Держусь, как конфета на палочке." ,
                "На коне, как в фильмах про ковбоев." ,
                "Как новая песня на репите - немного подустал, но двигаюсь дальше." , "Как Wi-Fi в кафе - стабильно!" ,
                "На гребне волны, как серфингист." , "Живу, как будто лето вечное." , "Как чай - настоенный и тёплый." ,
                "Плыву, как рыба в аквариуме." , "Живу, как в фильме - иногда экшен, иногда драма." ,
                "Как воздушный шарик - вечно на подъёме." , "На стиле, как будто все лайки мои." ,
                "Норм, как у кота в любимой коробке." , "На высоте, как тополь на плющихе." ,
                "Как плюшевый медведь - мягко и уютно." , "На подъёме, как в тренде в TikTok." ,
                "Как вишенка на торте - вишенка есть, а торта нет." , "Чуть не сплю, но держусь." ,
                "Как чай с лимоном - освежаюсь." , "Как барабан в рок-группе - держу ритм!" ,
                "На стиле, как рэпер на сцене." , "Ловлю вайб, как на вечеринке." , "Норм, как дожить до пятницы." ,
                "Как новый сериал - все ждут, а я ещё не вышел." , "Держусь, как последний уровень в игре." ,
                "Как стихи - иногда рифмуюсь, иногда нет." , "Чилл, как утром в субботу." ,
                "Тепло, как чашка чая в руках." , "Как тайм-менеджер - стараюсь успеть всё." ,
                "Дела норм, как у программиста на кофеине." , "Как палочка в мороженом - держу в себе холодный заряд!" ,
                "Живу, как зарядка - иногда разряжаюсь." , "Всё окей, как кнопка в Windows." ,
                "Как плеер на репите - одно и то же, но терплю." , "Как утка - плаваю спокойно." ,
                "Как утюг - грею, но не всегда вовремя." , "Как луна - то пропадаю, то снова здесь." ,
                "Как какао зимой - теплота в душе." , "Как кнопка перезагрузки - иногда не хватает." ,
                "Как батарейка - иногда нужна подзарядка." , "На уровне, как новое обновление." ,
                "Как компьютер без лагов - всё работает чётко." , "Всё ровно, как гугл-мапс." ,
                "Как сигналы в мессенджере - иногда потеряюсь, но нахожусь." ,
                "Как новая игра - пытаюсь понять правила." , "Чётко, как день зарплаты." ,
                "Как гол в футбольном матче - иногда неожиданный!" ,
                "Как фильтр в Instagram - иногда ярко, иногда естественно." ,
                "Как квест - не всегда просто, но интересно." , "Как ветер - иногда штиль, иногда ураган." ,
                "Как парусник - плыву по течению." , "Как телефон на вибро - тихо, но работаю." ,
                "Как финал сериала - иногда не предсказуемо." , "Как новый апдейт - ещё разбираюсь." ,
                "Всё ровно, как график отпусков." , "Как знак стоп - иногда торможу, но потом иду дальше." ,
                "Как таймер - на счёте секунды." , "Как мороженое - немного подтаял, но всё ещё вкусно." ,
                "Как геймпад - жду следующих действий." , "Как фотка на аватарке - всё вроде норм." ,
                "Как мем - иногда смешно, иногда грустно." , "Как пауза в кино - жду продолжения." ,
                "Как танцор - стараюсь не сбиться с ритма." , "Как ластик - стираю ошибки и иду дальше." ,
                "Как шахматы - продумываю ходы." , "Как музыка в наушниках - иногда тихо, иногда громко." ,
                "Как метка на карте - всегда в нужном месте." , "Как игра без багов - редкость, но бывает." ,
                "Как интернет - иногда торможу, но потом догоняю." , "Как водопад - теку мощно, но иногда медленно." ,
                "Как заброшенный чат - долго молчу, но потом оживаю." ,
                "Как будильник - иногда хочется просто выключить." ])
        await message.answer(text='😎')
        await message.reply(f"😎 <b>{answer}</b>", parse_mode="HTML")

    if message.text.lower() in [ 'кут что делаешь?' , 'кут, что делаешь?','кут, что делаешь','кут что делаешь','кут, чем занимаешься?','кут чем занимаешься?','кут чем занимаешься','кут, чем занимаешься','кут, чем занят?','кут чем занят?','кут, чем занят','кут чем занят']:
        answer = random.choice(
            [ "Смотрю на мир с улыбкой и наслаждаюсь каждым моментом!" ,
                "В поисках вдохновения, чтобы сделать день особенным!" ,
                "Думаю о том, как провести этот день с удовольствием!" ,
                "Размышляю о том, как сделать мир немного ярче!" ,
                "Собираю положительные эмоции, чтобы поделиться ими с вами!" ,
                "Ищу новые идеи для весёлого времяпрепровождения!" , "Просто наслаждаюсь моментом, а что ты?" ,
                "Делаю что-то интересное и радуюсь каждому мгновению!" , "Занимаюсь чем-то приятным и вдохновляющим!" ,
                "Играю с мыслями о том, как сделать этот день замечательным!" ,
                "Общаюсь с прекрасными людьми, и ты - один из них!" , "Делаю небольшие шаги к своим мечтам!" ,
                "Просто мечтаю о будущем и его возможностях!" , "Делюсь положительными мыслями с друзьями!" ,
                "Собираю идеи для нового проекта, а ты как?" , "Нахожусь в потоке вдохновения и радости!" ,
                "Создаю маленькие радости в своём дне!" , "Смотрю на небо и радуюсь тому, что оно синее!" ,
                "Просто наслаждаюсь тишиной и умиротворением!" , "Ищу красивые моменты вокруг, чтобы поделиться ими!" ,
                "Смехом и радостью наполняю своё окружение!" , "Занимаюсь любимым делом и чувствую себя прекрасно!" ,
                "Думаю о том, как сделать день лучше для себя и других!" , "Просто собираю воспоминания о счастье!" ,
                "Пытаюсь найти повод для улыбки и хорошего настроения!" , "Нахожусь в потоке позитивных эмоций!" ,
                "Смотрю на мир через призму радости и вдохновения!" , "Делаю что-то креативное и приятное для себя!" ,
                "Размышляю о том, как сделать этот день особенным!" , "Собираю хорошие мысли и делюсь ими с миром!" ,
                "Ищу счастье в мелочах и радуюсь каждому дню!" ,
                "Просто наслаждаюсь жизнью и моментами, которые она дарит!" ,
                "Занимаюсь тем, что приносит мне радость!" , "Собираю яркие впечатления и положительные эмоции!" ,
                "Нахожусь в гармонии с собой и окружающим миром!" , "Делюсь радостью и улыбками с близкими!" ,
                "Нахожусь в мире своих мечт и целей!" , "Смех и радость - мои верные спутники!" ,
                "Делаю шаги к своим мечтам с радостью!" , "Собираю моменты счастья и любви вокруг!" ,
                "Просто наслаждаюсь каждым мгновением жизни!" , "Ищу радость в каждом дне и каждом событии!" ,
                "Смех делает мир ярче, и я стараюсь не упускать это!" , "Делюсь счастьем с теми, кто меня окружает!" ,
                "Каждый новый день - это возможность для нового начала!" ,
                "Собираю позитивные моменты и делюсь ими с друзьями!" ,
                "Делюсь любовью с окружающими и радуюсь этому!" , "Ищу вдохновение в каждом дне и каждом моменте!" ,
                "Просто наслаждаюсь тишиной и хорошими мыслями!" , "Занимаюсь любимыми хобби и делюсь ими с миром!" ,
                "Создаю позитивную атмосферу вокруг себя!" , "Смех и радость наполняют моё сердце!" ,
                "Каждый день - это шанс быть счастливым!" , "Размышляю о том, как сделать жизнь ярче!" ,
                "Нахожусь в потоке положительных эмоций и вдохновения!" ,
                "Просто собираю яркие впечатления и радуюсь жизни!" , "Ищу вдохновение и радость в каждом дне!" ,
                "Делюсь радостью с теми, кто меня окружает!" , "Каждый момент - это шанс для счастья и улыбки!" ,
                "Смех и дружба - это то, что делает мою жизнь лучше!" , "Делаю шаги к своим целям и мечтам!" ,
                "Собираю хорошие воспоминания и делюсь ими!" , "Ищу радость в каждом дне и каждом мгновении!" ,
                "Просто наслаждаюсь каждым моментом жизни!" , "Смех делает мир ярче, и я стараюсь его не упускать!" ,
                "Делюсь счастьем с окружающими и радуюсь этому!" ,
                "Каждый новый день - это возможность для чего-то нового!" ,
                "Собираю позитивные моменты и радуюсь жизни!" , "Нахожусь в гармонии с собой и окружающим миром!" ,
                "Делаю что-то приятное и вдохновляющее для себя!" , "Просто наслаждаюсь моментом и радуюсь жизни!" ,
                "Делюсь радостью и хорошими эмоциями с друзьями!" ,
                "Каждый день - это новая возможность быть счастливым!" , "Смех и радость наполняют моё сердце!" ,
                "Ищу вдохновение и радость в каждом дне!" , "Занимаюсь тем, что приносит мне счастье!" ,
                "Собираю яркие впечатления и делюсь ими с миром!" ,
                "Нахожусь в потоке положительных эмоций и вдохновения!" ,
                "Просто мечтаю о будущем и его возможностях!" , "Делюсь счастьем с теми, кто меня окружает!" ,
                "Смех делает мир ярче, и я стараюсь не упускать это!" ,
                "Каждый момент - это шанс для счастья и улыбки!" , "Собираю положительные эмоции и делаю мир лучше!" ,
                "Давайте наполним этот день радостью и улыбками!" , "Просто наслаждаюсь каждым мгновением жизни!" ])
        await message.answer(text='😼')
        await message.reply(f"😼 <b>{answer}</b>", parse_mode="HTML")

    if message.text.lower() in [ 'кут привет' , 'кут, привет','кут, здраствуй','кут здраствуй','кут, добрый день','кут добрый день','кут здраствуйте','кут, здраствуйте']:

        answer=random.choice(
            [ "Привет, как ты?" , "Привет, чем занимаешься?" , "Привет, как проходит день?" ,
                "Привет, что нового?" , "Привет, как дела?" , "Привет, чем ты занят?" , "Привет, как настроение?" ,
                "Привет, как у тебя дела?" , "Привет, что на уме?" ,
                "Привет, чем ты занимаешься сегодня?" , "Привет, что у тебя нового?" ,
                "Привет, как ты проводишь время?" , "Привет, что интересного у тебя?" , "Привет, как поживаешь?" ,
                "Привет, чем сейчас увлекаешься?" , "Привет, как твой день?" , "Привет, что у тебя на повестке?" ,
                "Привет, как идет твоя работа?" , "Привет, как обстановка?" ,
                "Привет, чем занимаешься в свободное время?" , "Привет, что у тебя в планах?" ,
                "Привет, как проводишь время?" ])
        await message.answer(text='👋')
        await message.reply(f"👋 <b>{answer}</b>", parse_mode="HTML")

    if message.text.lower() in [ 'кут доброе утро' , 'кут, доброе утро' ]:
        answer = random.choice(
            [ "Доброе","Привет","Доброе утро" ])
        await message.answer(text='🌤')
        await message.reply(f"🌤 <b>{answer}</b>" , parse_mode="HTML")

    if message.text.lower() in [ 'кут доброй ночи' , 'кут, доброй ночи','кут спокойной' , 'кут, спокойной ночи' ]:
        answer = random.choice(
            [ "Доброй","Спокойной ночи","Доброй ночи","Сладких снов" ])
        await message.answer(text='🌑')
        await message.reply(f"🌑 <b>{answer}</b>" , parse_mode="HTML")

    if message.text.lower() in [ 'кут ты еблан?','кут, ты еблан?','кут ты еблан','кут, ты еблан','кут ты долбоеб?','кут, ты долбоеб?','кут ты долбоеб','кут, ты долбоеб','кут ты плохой бот?','кут, ты плохой бот?','кут ты плохой бот','кут, ты плохой бот','кут ты даун?' , 'кут, ты даун?','кут ты даун' , 'кут, ты даун','кут, ты клоун?','кут ты клоун?','кут ты клоун','кут, ты клоун','кут, ты уебище?','кут ты уебище?','кут, ты уебище','кут ты уебище?' ]:
        answer = random.choice(
            [ "Нет" ])
        await message.answer(text='👎')
        await message.reply(f"👎 <b>{answer}</b>" , parse_mode="HTML")
    if len(words) > 0 and words [ 0 ] in [ 'кут' , 'Кут' , 'Кут,' , 'кут,' , 'кут.' , 'Кут.' ]:


        # Объединяем слова после "кут" в строку, удаляем запятые и точки, затем приводим к нижнему регистру
        phrase = ' '.join(words [ 1: ]).lower().strip()  # Удаляем точки и запятые


        # Проверяем, содержит ли фраза одну из игнорируемых фраз
        ignore_phrases = [ 'расскажи цитату','ты еблан','привет','как твои дела','ты долбоеб','ты даун','ты клоун','ты плохой бот','ты уебище','доброй ночи','спокойной ночи','здраствуй','доброе утро','добрый день','добрый день','здраствуйте','что делаешь','чем занимаешься','чем занят','как ты','как дела','сколько будет' , 'черные шутки' , 'черная шутка' , 'расскажи черную шутку' ,
            'расскажи темную шутку' , 'темная шутка' , 'напиши шутку' , 'расскажи анекдот' , 'расскажи шутку' ,
            'напиши анекдот' , 'покажи новости' , 'покажи недавние новости' , 'покажи новости мира' , 'открой новости' ,
            'выбери рандом число' , 'скажи рандом число' , 'рандом число' , 'покажи цитату' , 'напиши миф' ,
            'расскажи миф' , 'покажи миф' , 'напиши стих' , 'расскажи стих' , 'покажи стих' , 'расскажи факт' ,
            'напиши факт' , 'покажи факт' , 'покажи мемы' , 'покажи мемы' , 'мем' , 'мемы','кто такое','кто такой','кто такая','расскажи','расскажи такое','расскажи такой','расскажи такая','расскажи о'  ]

        # Если фраза полностью соответствует одной из игнорируемых фраз
        if phrase.rstrip('?') in ignore_phrases:
            return  # Игнорируем указанные фразы
        if phrase in ignore_phrases:

            return  # Игнорируем указанные фразы

        # Проверяем комбинации для 'орел или решка' и 'решка или орел'
        for i in range(len(words)):
            # Проверяем "орел или решка"
            if (i + 2 < len(words) and words [ i ] in [ 'орел' , 'орёл' ] and words [ i + 1 ] == 'или' and words [
                i + 2 ] == 'решка'):

                # Игнорируем, если следующее слово - вопросительный знак
                if i + 3 < len(words) and words [ i + 3 ] == '?':
                    return  # Игнорируем
                return  # Игнорируем 'орел или решка'

            # Проверяем "решка или орел"
            elif (i + 2 < len(words) and words [ i ] == 'решка' and words [ i + 1 ] == 'или' and words [ i + 2 ] in [
                'орел' , 'орёл' ]):

                # Игнорируем, если следующее слово - вопросительный знак
                if i + 3 < len(words) and words [ i + 3 ] == '?':
                    return  # Игнорируем
                return  # Игнорируем 'решка или орел'

            # Проверяем слово "скажи"

            if words [ i ] in [ 'скажи' , 'рандом' , 'стик' , 'стикер' , 'стикеры' , 'эмодзи' , 'эмо' , 'цитата' ,
                                'число' , 'цитаты' , 'миф' , 'мифы' , 'стих' , 'факт' , 'факты' , 'новости' ,
                                'анекдот' , 'шутка' , 'шутки','калькулятор','рассчитай','реши','посчитай','перевод','переведи','такое','такой','такая','о','кто']:

                return  # Игнорируем 'скажи'

        # Проверка на фразы с датами
        time_phrases = [ 'сколько времени прошло с' , 'сколько дней прошло от' , 'сколько секунд прошло со' ,
            'сколько дней прошло с' , 'сколько времени прошло от' , 'сколько секунд прошло со' , 'сколько времени с' ,
            'сколько секунд от' , 'сколько минут со' , 'сколько минут прошло с' , 'сколько времени прошло от' ,
            'сколько дней прошло со','сколько прошло с' ]




        # Регулярное выражение для проверки формата даты
        date_pattern = r'(\d{2}\.\d{2}\.\d{4}|\d{4}\.\d{2}\.\d{2})$'

        # Проверяем, заканчивается ли фраза на одну из временных фраз с датой
        for tp in time_phrases:
            if phrase.startswith(tp) and re.search(date_pattern , phrase):

                return  # Возвращаем результат для временной фразы с датой

    question = None  # Инициализируем переменную question

    # Проверяем, что сообщение начинается с "кут" или его вариаций
    if len(words) > 0 and words [ 0 ] in [ 'кут' , 'Кут' , 'Кут,' , 'кут,' , 'кут.' , 'Кут.' ]:

        # Проверяем наличие слова "или" или "or"
        if 'или' in message.text.lower() or 'or' in message.text.lower():
            # Проверяем "орел или решка" или "решка или орел"
            for i in range(len(words)):
                # Проверяем "орел или решка"
                if (i + 2 < len(words) and words [ i ] in [ 'орел' , 'орёл' ] and words [ i + 1 ] in [ 'или' ,
                                                                                                       'or' ] and
                        words [ i + 2 ] == 'решка'):
                    return  # Игнорируем дальнейший код

                # Проверяем "решка или орел"
                elif (i + 2 < len(words) and words [ i ] == 'решка' and words [ i + 1 ] in [ 'или' , 'or' ] and words [
                    i + 2 ] in [ 'орел' , 'орёл' ]):
                    return  # Игнорируем дальнейший код

            # Если здесь, значит, нет "орел или решка" или "решка или орел", но есть "или" или "or"

            # Разделяем сообщение на части
            parts = message.text.split("или" , 1) if 'или' in message.text else message.text.split("or" , 1)

            # Проверяем, есть ли текст до "или" или "or"
            if len(parts) > 0:
                before_or = parts [ 0 ].strip()

                # Проверяем, что текст после "кут" не пустой
                if len(before_or.split()) > 1 and not any(
                        word in before_or.lower() for word in [ 'орел' , 'орёл' , 'решка' ]):
                    # Находим текст после "кут" до "или" или "or"
                    message1 = before_or [ len('кут'): ].strip()  # Все, что после "кут"

                    # Получаем второе сообщение после "или" или "or"
                    message2 = parts [ 1 ].strip() if len(parts) > 1 else ""

                    if message2.endswith('?'):
                        message2 = message2 [ :-1 ].strip()

                    # Случайно выбираем одно из сообщений
                    selected_message = random.choice([ message1 , message2 ])

                    # Генерируем случайный ответ
                    answertext = random.choice(
                        [ f'<b>"{selected_message}", <i>я выбрал лучшее.</i></b>' ,
                          f'<b>{selected_message}, <i>разве не очевидно?</i></b>' ,
                          f'<b>"{selected_message}", <i>так сказал мой алгоритм, доверься ему!</i></b>' ,
                          f'<b>"{selected_message}", <i>, я был рождён для этого выбора!</i></b>' ,
                          f'<b>"{selected_message}", <i>лучшее из худшего! Ну, шучу.</i></b>' ,
                          f'<b>"{selected_message}", <i>только потому, что я могу!</i></b>' ,
                          f'<b>"{selected_message}", <i>лучший выбор среди всех возможных.</i></b>' ,
                          f'<b>"{selected_message}", <i>я решаю, и это мой вердикт!</i></b>' ,
                          f'<b>"{selected_message}", <i>да, я гений выбора!</i></b>' ])

                    # Отправляем сообщение с ответом
                    await message.reply(
                        f'☝️ {answertext}' , parse_mode="HTML" , disable_web_page_preview=True)
            return  # Останавливаем дальнейший код

        # Если в сообщении нет "или" или "or" и не обнаружены варианты для "орел или решка"
        else:
            # Сохраняем вопрос в переменную question
            question = message.text [ len('кут,'): ].strip()

            # Отправляем случайный ответ на вопрос
            if question:
                answer = random.choice(
                    [ 'Да, это действительно сбудется!' , 'Да, но позаботься о деталях!' ,
                      'Нет, не стоит за этим идти - коты против.' , 'Да, если подождешь немного.' ,
                      'Нет, это не твой день.' , 'Да, звезды на твоей стороне!' ,
                      'Нет, лучше оставить это желание на потом.' , 'Да, но не забудь про удачу.' ,
                      'Нет, этого не произойдет.' , 'Да, это именно то, что тебе нужно!' ,
                      'Нет, ты сможешь найти что-то лучше.' , 'Да, вперед к новым достижениям!' ,
                      'Нет, не теряй надежду, просто не сейчас.' , 'Да, мечты сбываются, если в них верить.' ,
                      'Нет, это желание слишком рискованно.' , 'Да, тебе нужно только немного терпения.' ,
                      'Нет, не стоит надеяться на это.' , 'Да, давай попробуем!' , 'Нет, твои планы, возможно, изменятся.' ,
                      'Да, успех уже близок!' , 'Нет, это может привести к неприятностям.' ,
                      'Да, но не забудь взять с собой удачу.' , 'Нет, лучше не искушай судьбу.' ,
                      'Да, ты готов к переменам!' , 'Нет, это не сбудется так быстро.' ,
                      'Да, и успех не заставит себя ждать!' , 'Нет, это может привести к разочарованию.' ,
                      'Да, если ты будешь настойчивым!' , 'Нет, это не лучший выбор.' , 'Да, мир будет на твоей стороне!' ,
                      'Нет, лучше оставить это в прошлом.' , 'Да, время пришло действовать!' , 'Нет, лучше не рисковать.' ,
                      'Да, мечтай и действуй!' , 'Нет, это не твой путь.' , 'Да, если веришь в свои силы!' ,
                      'Нет, это желание не принесет удачи.' , 'Да, приготовься к невероятным приключениям!' ,
                      'Нет, сейчас не время для этого.' , 'Да, звезды благоприятствуют тебе.' ,
                      'Нет, стоит пересмотреть свои цели.' , 'Да, если ты готов к новым вызовам.' ,
                      'Нет, это желание потребует много усилий.' , 'Да, у тебя все получится!' ,
                      'Нет, слишком много неопределенности.' , 'Да, и не забудь улыбаться!' , 'Нет, сейчас не время.' ,
                      'Да, ты на верном пути.' , 'Нет, это желание может обернуться сюрпризами.' ,
                      'Да, если ты будешь следовать своей мечте.' , 'Нет, но не теряй надежду!' , 'Да, готовься к успеху!' ,
                      'Нет, стоит пересмотреть свои приоритеты.' , 'Да, если будешь верить в себя.' ,
                      'Нет, это не принесет радости.' , 'Да, у тебя есть все шансы!' , 'Нет, это не для тебя.' ,
                      'Да, если найдешь правильный подход.' , 'Нет, и это к лучшему.' , 'Да, ты сможешь это сделать!' ,
                      'Нет, это не принесет тебе счастья.' , 'Да, если будешь верить в свои силы.' ,
                      'Нет, лучше не искушать судьбу.' , 'Да, и твои мечты сбудутся!' ,
                      'Нет, это желание требует больше времени.' , 'Да, и помни, что ты в ответе за свою судьбу!' ,
                      'Нет, лучше пересмотри свои планы.' , 'Да, удача будет с тобой!' , 'Нет, сейчас не лучший момент.' ,
                      'Да, вперед к новым приключениям!' , 'Нет, это желание слишком рискованное.' ,
                      'Да, если не будешь отступать!' , 'Нет, тебе нужно больше времени.' ,
                      'Да, это сбудется, если ты будешь работать над этим!' , 'Нет, не стоит об этом мечтать.' ,
                      'Да, и это принесет много радости!' , 'Нет, это может закончиться печально.' ,
                      'Да, ты уже на правильном пути.' , 'Нет, лучше оставить это желание.' ,
                      'Да, если ты готов к новому этапу!' , 'Нет, не стоит это делать.' , 'Да, и не забудь об отдыхе!' ,
                      'Нет, это желание обернется сложностями.' , 'Да, всё идет к твоему успеху!' ,
                      'Нет, этого не произойдет.' , 'Да, и помни - ты сможешь все!' , 'Нет, это не принесет счастья.' ,
                      'Да, если ты откроешься новому!' , 'Нет, это может привести к неприятностям.' ,
                      'Да, и ты на правильном пути к своей мечте!' , 'Нет, у тебя есть более важные дела.' ,
                      'Да, время действовать!' , 'Нет, это не лучшая идея.' , 'Да, если будешь верить в себя!' ,
                      'Нет, это желание обернется сложностями.' , 'Да, и это обязательно сбудется!' ,
                      'Нет, не стоит на это надеяться.' , 'Да, и знай - ты справишься!' ,
                      'Нет, это не приведет к счастью.' , 'Да, удача будет с тобой!' , 'Нет, не стоит это делать сейчас.' ,
                      'Да, и все обязательно получится!' , 'Нет, это не твой путь.' ,
                      'Да, если ты будешь верить в чудеса.' , 'Нет, лучше оставь это желание.' ,
                      'Да, и звезды поддерживают твой выбор!' , 'Нет, это не принесет радости.' ,
                      'Да, всё будет хорошо, верь в себя!' , 'Нет, стоит обдумать другой план.' ,
                      'Да, если ты не боишься трудностей.' , 'Нет, это желание не сбудется.' ,
                      'Да, и помни - все в твоих руках!' , 'Нет, лучше подумай еще раз.' ,
                      'Да, вперед к новым свершениям!' , 'Нет, это желание потребует много усилий.' ,
                      'Да, и у тебя все получится!' , 'Нет, это не твой путь к успеху.' ,
                      'Да, если ты будешь верить в себя!' , 'Нет, это не приведет к чему-то хорошему.' ,
                      'Да, и не забудь о своей мечте!' , 'Нет, лучше отложи это на потом.' ,
                      'Да, если ты сможешь найти нужные ресурсы.' , 'Нет, это не принесет счастья.' ,
                      'Да, вперед к новым высотам!' , 'Нет, не стоит это делать.' , 'Да, если у тебя есть желание!' ,
                      'Нет, это слишком рискованно.' , 'Да, и помни - ты на верном пути!' , 'Нет, это не принесет успеха.' ,
                      'Да, и мир будет на твоей стороне!' , 'Нет, стоит пересмотреть свои цели.' ,
                      'Да, и это обязательно сбудется!' , 'Нет, не стоит этому доверять.' , 'Да, если у тебя есть план!' ,
                      'Нет, это не твой день.' , 'Да, ты на верном пути!' , 'Нет, это желание может обернуться неудачей.' ,
                      'Да, и будь готов к удивительным сюрпризам!' , 'Нет, сейчас не время для этого.' ,
                      'Да, если веришь в свою силу!' , 'Нет, это не принесет успеха.' , 'Да, и твоя мечта сбудется!' ,
                      'Нет, лучше оставить это желание.' , 'Да, и не забывай о своей цели!' , 'Нет, это не твой путь.' ,
                      'Да, если будешь действовать!' , 'Нет, лучше пересмотри свои планы.' , 'Да, и готовься к успеху!' ,
                      'Нет, это может привести к сложностям.' , 'Да, и удача на твоей стороне!' ,
                      'Нет, это не принесет радости.' , 'Да, и ты сможешь это сделать!' , 'Нет, лучше не рисковать.' ,
                      'Да, и помни о своих целях!' , 'Нет, это не тот путь, который нужно выбирать.' ,
                      'Да, если ты решишься!' , 'Нет, это может обернуться проблемами.' , 'Да, и твое желание исполнится!' ,
                      'Нет, это не приведет к успеху.' , 'Да, и не забывай о своих мечтах!' , 'Нет, это не лучший выбор.' ,
                      'Да, если ты готов к переменам!' , 'Нет, лучше обдумай это еще раз.' , 'Да, и удача улыбнется тебе!' ,
                      'Нет, это не твой путь.' , 'Да, если будешь уверенным!' , 'Нет, это желание слишком рискованное.' ,
                      'Да, и всё сбудется, если ты в это веришь!' , 'Нет, не стоит на это рассчитывать.' ,
                      'Да, если ты готов приложить усилия!' , 'Нет, это не принесет тебе счастья.' ,
                      'Да, и ты готов к новым вызовам!' , 'Нет, лучше оставить это в прошлом.' ,
                      'Да, и следуй за своей мечтой!' , 'Нет, это не приведет к хорошему результату.' ,
                      'Да, если будешь верить в себя!' , 'Нет, это желание слишком рискованное.' ,
                      'Да, и все зависит от тебя!' , 'Нет, лучше подумай еще раз.' ,
                      'Да, это сбудется, если ты будешь стремиться к этому!' , 'Нет, не теряй надежду, просто не сейчас.' ,
                      'Да, у тебя все получится!' , 'Нет, это не твой день.' , 'Да, и успех не заставит себя ждать!' ,
                      'Нет, лучше оставь это желание.' , 'Да, и готовься к успеху!' ,
                      'Нет, это может обернуться неприятностями.' , 'Да, если ты настроишься на положительный результат!' ,
                      'Нет, лучше не рисковать.' , 'Да, и твои мечты сбудутся!' , 'Нет, это не принесет радости.' ,
                      'Да, если ты будешь следовать своим мечтам!' , 'Нет, это желание не сбудется.' ,
                      'Да, и помни - ты в ответе за свою судьбу!' , 'Нет, не стоит об этом мечтать.' ,
                      'Да, и это приведет к удивительным результатам!' , 'Нет, это может закончиться печально.' ,
                      'Да, ты уже на правильном пути.' , 'Нет, лучше не искушай судьбу.' ,
                      'Да, если ты готов действовать!' , 'Нет, это не лучший выбор.' ,
                      'Да, и будь готов к новым достижениям!' , 'Нет, это желание потребует много усилий.' ,
                      'Да, и не забудь о своей цели!' , 'Нет, это не принесет успеха.' , 'Да, ты сможешь это сделать!' ,
                      'Нет, это не твой путь к счастью.' , 'Да, если найдешь нужные ресурсы!' ,
                      'Нет, это не приведет к хорошему результату.' , 'Да, и помни - ты на правильном пути!' ,
                      'Нет, лучше обдумай другой план.' , 'Да, это точно сбудется!' , 'Нет, это не лучший выбор.' ,
                      'Да, и звезды будут с тобой!' , 'Нет, это не принесет радости.' ,
                      'Да, если будешь работать над своей мечтой!' , 'Нет, это не твой день.' ,
                      'Да, и помни, что удача на твоей стороне!' , 'Нет, лучше не рисковать.' ,
                      'Да, если ты готов к новым вызовам!' , 'Нет, это желание не сбудется.' ,
                      'Да, и у тебя есть все шансы!' , 'Нет, это не приведет к успеху.' ,
                      'Да, и твое желание обязательно сбудется!' , 'Нет, лучше оставь это желание на потом.' ,
                      'Да, если ты сможешь найти нужные ресурсы!' , 'Нет, это не для тебя.' ,
                      'Да, и готовься к удивительным приключениям!' , 'Нет, это может обернуться неприятностями.' ,
                      'Да, если ты будешь следовать своим мечтам!' , 'Нет, лучше обдумай свои планы.' ,
                      'Да, и не забудь о своих целях!' , 'Нет, это не лучший выбор.' , 'Да, ты на правильном пути!' ,
                      'Нет, это желание потребует много усилий.' , 'Да, и звезды поддерживают твой выбор!' ,
                      'Нет, это не принесет удачи.' , 'Да, и твои мечты сбудутся!' , 'Нет, не стоит этому доверять.' ,
                      'Да, и помни - все в твоих руках!' , 'Нет, лучше пересмотри свои цели.' ,
                      'Да, и удача будет с тобой!' , 'Нет, это не приведет к счастью.' ,
                      'Да, если ты будешь верить в себя!' , 'Нет, лучше оставь это желание.' ,
                      'Да, ты сможешь это сделать!' , 'Нет, это не твой путь к успеху.' ,
                      'Да, и не забудь о своих мечтах!' , 'Нет, это не принесет радости.' ,
                      'Да, и помни, что ты в ответе за свою судьбу!' , 'Нет, это не лучший выбор.' ,
                      'Да, если будешь следовать своим мечтам!' , 'Нет, это не приведет к успеху.' ,
                      'Да, и готовься к новым свершениям!' , 'Нет, лучше обдумай свои планы.' , 'Да, ты на верном пути!' ,
                      'Нет, это желание может обернуться проблемами.' , 'Да, и не забывай о своей цели!' ,
                      'Нет, это не приведет к хорошему результату.' , 'Да, и помни - всё зависит от тебя!' ,
                      'Нет, лучше оставь это желание на потом.' , 'Да, и звезды будут с тобой!' ,
                      'Нет, это не принесет радости.' , 'Да, если ты готов к переменам!' , 'Нет, это не твой день.' ,
                      'Да, и помни - ты сможешь это сделать!' , 'Нет, лучше не рисковать.' ,
                      'Да, и твое желание сбудется!' , 'Нет, это не принесет успеха.' , 'Да, если будешь верить в себя!' ,
                      'Нет, лучше пересмотри свои цели.' , 'Да, ты уже на правильном пути!' ,
                      'Нет, это не твой путь к счастью.' , 'Да, и следуй за своей мечтой!' ,
                      'Нет, это желание не сбудется.' , 'Да, и помни, что удача на твоей стороне!' ,
                      'Нет, лучше не искушай судьбу.' , 'Да, и всё будет хорошо, верь в себя!' ,
                      'Нет, это не лучший выбор.' , 'Да, и звезды поддерживают твой выбор!' ,
                      'Нет, это не принесет радости.' , 'Да, если ты будешь следовать своим мечтам!' ,
                      'Нет, это не приведет к успеху.' , 'Да, и помни - ты на правильном пути!' , 'Нет, это не твой день.' ,
                      'Да, если ты готов к новым вызовам!' , 'Нет, это желание потребует много усилий.' ,
                      'Да, и не забудь о своих целях!' , 'Нет, это не принесет удачи.' , 'Да, ты сможешь это сделать!' ,
                      'Нет, это не твой путь к счастью.' , 'Да, и готовься к удивительным приключениям!' ,
                      'Нет, это не приведет к успеху.' , 'Да, и помни, что удача будет с тобой!' ,
                      'Нет, лучше оставь это желание.' , 'Да, если будешь работать над своей мечтой!' ,
                      'Нет, это не принесет радости.' , 'Да, и твои мечты сбудутся!' , 'Нет, это не твой путь.' ,
                      'Да, и не забудь о своих целях!' , 'Нет, это не лучший выбор.' , 'Да, если ты веришь в свои силы!' ,
                      'Нет, это не приведет к хорошему результату.' , 'Да, и помни, что ты на верном пути!' ,
                      'Нет, лучше обдумай свои планы.' , 'Да, и всё будет хорошо, верь в себя!' ,
                      'Нет, это желание потребует много усилий.' , 'Да, и звезды поддерживают твой выбор!' ,
                      'Нет, это не принесет успеха.' , 'Да, и помни - всё в твоих руках!' , 'Нет, это не твой день.' ,
                      'Да, и удача на твоей стороне!' , 'Нет, лучше не рисковать.' , 'Да, если ты готов к переменам!' ,
                      'Нет, это не лучший выбор.' , 'Да, и не забудь о своей мечте!' ,
                      'Нет, это не приведет к хорошему результату.' , 'Да, и ты сможешь это сделать!' ,
                      'Нет, это не твой путь к счастью.' , 'Да, если найдешь нужные ресурсы!' ,
                      'Нет, это не приведет к успеху.' , 'Да, и будь готов к удивительным сюрпризам!' ,
                      'Нет, лучше обдумай другие варианты.' , 'Да, и помни - звезды будут с тобой!' ,
                      'Нет, это не приведет к радости.' , 'Да, и удача будет на твоей стороне!' ,
                      'Нет, лучше оставь это желание.' , 'Да, и твои мечты сбудутся!' , 'Нет, это не твой путь к успеху.' ,
                      'Да, и помни, что всё зависит от тебя!' , 'Нет, это не принесет счастья.' ,
                      'Да, и следуй за своей мечтой!' , 'Нет, это желание не сбудется.' ,
                      'Да, и помни - удача на твоей стороне!' , 'Нет, лучше обдумай свои планы.' ,
                      'Да, и готовься к новым свершениям!' , 'Нет, это не твой день.' ,
                      'Да, и всё будет хорошо, верь в себя!' , 'Нет, это может обернуться сложностями.' ,
                      'Да, если будешь верить в себя!' , 'Нет, это не принесет радости.' , 'Да, и удача будет с тобой!' ,
                      'Нет, лучше оставь это желание.' , 'Да, ты сможешь это сделать!' , 'Нет, это не приведет к успеху.' ,
                      'Да, если найдешь нужные ресурсы!' , 'Нет, это не твой путь к счастью.' ,
                      'Да, и не забудь о своей мечте!' , 'Нет, это не лучший выбор.' , 'Да, если ты готов действовать!' ,
                      'Нет, это не приведет к хорошему результату.' , 'Да, и звезды поддерживают твой выбор!' ,
                      'Нет, лучше обдумай свои цели.' , 'Да, и помни, что ты на верном пути!' ,
                      'Нет, это не принесет удачи.' , 'Да, и всё будет хорошо, верь в себя!' , 'Нет, это не твой день.' ,
                      'Да, и готовься к удивительным приключениям!' , 'Нет, это может обернуться проблемами.' ,
                      'Да, если ты будешь следовать своим мечтам!' , 'Нет, это не приведет к успеху.' ,
                      'Да, и помни, что удача на твоей стороне!' , 'Нет, лучше не рисковать.' ,
                      'Да, и будь готов к новым свершениям!' , 'Нет, это не твой путь.' , 'Да, и не забудь о своих целях!' ,
                      'Нет, это не приведет к радости.' , 'Да, ты сможешь это сделать!' , 'Нет, это не лучший выбор.' ,
                      'Да, если будешь работать над своей мечтой!' , 'Нет, это не приведет к успеху.' ,
                      'Да, и помни - ты на правильном пути!' , 'Нет, лучше обдумай другие варианты.' ,
                      'Да, и удача будет с тобой!' , 'Нет, это не твой день.' , 'Да, и следуй за своей мечтой!' ,
                      'Нет, это не приведет к хорошему результату.' , 'Да, если найдешь нужные ресурсы!' ,
                      'Нет, это не приведет к успеху.' , 'Да, и будь готов к удивительным приключениям!' ,
                      'Нет, лучше оставь это желание на потом.' , 'Да, и помни, что звезды будут с тобой!' ,
                      'Нет, это не твой путь к счастью.' , 'Да, и не забудь о своей мечте!' ,
                      'Нет, это желание не сбудется.' , 'Да, и удача будет на твоей стороне!' ,
                      'Нет, лучше обдумай свои планы.' , 'Да, если будешь верить в себя!' ,
                      'Нет, это не приведет к успеху.' , 'Да, и помни - ты сможешь это сделать!' ,
                      'Нет, это не лучший выбор.' , 'Да, и следуй за своей мечтой!' ,
                      'Нет, это может обернуться сложностями.' , 'Да, и не забудь о своих целях!' ,
                      'Нет, это не приведет к удаче.' , 'Да, ты сможешь это сделать!' , 'Нет, это не твой путь.' ,
                      'Да, и помни, что ты на правильном пути!' , 'Нет, лучше не рисковать.' ,
                      'Да, если найдешь нужные ресурсы!' , 'Нет, это не приведет к хорошему результату.' ,
                      'Да, и удача будет с тобой!' , 'Нет, это не твой день.' , 'Да, и готовься к новым свершениям!' ,
                      'Нет, лучше обдумай другие варианты.' , 'Да, если ты будешь следовать своим мечтам!' ,
                      'Нет, это не приведет к успеху.' , 'Да, и звезды поддерживают твой выбор!' ,
                      'Нет, это не приведет к радости.' , 'Да, и помни, что удача на твоей стороне!' ,
                      "Возможно, ты сможешь в это поверить!" , "Наверняка, стоит подумать еще раз." ,
                      "Может, удача будет с тобой!" , "Не уверен, что это лучший выбор." ,
                      "Скорее всего, ты сможешь это сделать!" , "Есть вероятность, что это не принесет радости." ,
                      "Вероятно, все в твоих руках!" , "Может, стоит обдумать другой план." ,
                      "Уверен, твои мечты станут явью!" , "Возможно, это не лучший путь." ,
                      "Скорее всего, если ты веришь в свои способности!" , "Не исключено, что стоит рискнуть." ,
                      "Возможно, твоя мечта станет реальностью!" , "Не стоит надеяться на это." ,
                      "Может, если ты готов действовать!" , "Не уверена, что это принесет удачу." ,
                      "Возможно, успех будет с тобой!" , "Скорее всего, лучше не рисковать." ,
                      "Есть шанс, что ты на правильном пути!" , "Не исключено, что это не твой день." ,
                      "Наверняка, если будешь следовать своей мечте!" ,
                      "Есть вероятность, что это желание может обернуться проблемами." , "Может, успех будет с тобой!" ,
                      "Возможно, лучше оставить это в прошлом." , "Уверен, ты готов к новым приключениям!" ,
                      "Не уверена, что это твой путь." , "Скорее всего, помни, что ты на правильном пути!" ,
                      "Возможно, это не приведет к счастью." , "Вероятно, не забудь об отдыхе!" ,
                      "Не исключено, что это может обернуться неудачей." , "Может, если ты не боишься трудностей!" ,
                      "Есть вероятность, что стоит пересмотреть свои приоритеты." , "Уверен, ты готов к успеху!" ,
                      "Вероятно, это не принесет хорошего результата." , "Может, твое желание сбудется!" ,
                      "Не исключено, что это может обернуться неудачей." , "Скорее всего, если ты не теряешь надежду!" ,
                      "Возможно, лучше обдумай еще раз." , "Уверен, ты справишься!" ,
                      "Не исключено, что это не лучший путь." , "Может, удача будет с тобой!" ,
                      "Есть вероятность, что это не принесет радости." , "Скорее всего, если ты готов действовать!" ,
                      "Возможно, это желание потребует много усилий." , "Вероятно, знай - ты на верном пути!" ,
                      "Не исключено, что это не приведет к успеху." , "Может, помни - у тебя все получится!" ,
                      "Скорее всего, это не лучший путь." , "Возможно, если ты будешь верить в себя!" ,
                      "Не уверена, что стоит надеяться на это." , "Наверняка, успех не заставит себя ждать!" ,
                      "Возможно, это не приведет к счастью." , "Может, помни - мечты сбываются!" ,
                      "Не исключено, что это не твой день." , "Вероятно, и всё будет хорошо!" ,
                      "Скорее всего, не искушай судьбу." , "Есть шанс, что если ты готов к новому!" ,
                      "Возможно, это желание не принесет удачи." , "Наверняка, вперед к новым высотам!" ,
                      "Не исключено, что лучше пересмотреть свои планы." , "Может, не забудь о своих мечтах!" ,
                      "Скорее всего, это не твой путь." , "Возможно, если будешь действовать!" ,
                      "Есть вероятность, что это желание слишком рискованное." , "Уверен, звезды поддерживают тебя!" ,
                      "Не исключено, что не стоит на это надеяться." , "Вероятно, помни - ты сможешь это сделать!" ,
                      "Скорее всего, это не приведет к хорошему результату." ,
                      "Возможно, и всё получится, если будешь верить в себя!" ,
                      "Не исключено, что это не приведет к успеху." , "Может, знай - ты на правильном пути!" ,
                      "Вероятно, лучше обдумай другой план." , "Есть вероятность, что удача будет с тобой!" ,
                      "Не исключено, что это не приведет к счастью." , "Скорее всего, вперед к новым приключениям!" ,
                      "Возможно, лучше оставить это желание." , "Может, подумай о других вариантах." ,
                      "Не уверена, что это стоит твоего времени." , "Вероятно, это не твой лучший ход." ,
                      "Есть шанс, что это станет началом чего-то нового!" , "Скорее всего, стоит обдумать свои шаги." ,
                      "Возможно, если ты будешь терпеливым!" , "Не исключено, что успех будет с тобой!" ,
                      "Наверняка, если будешь верить в себя!" , "Есть вероятность, что стоит рискнуть." ,
                      "Может, это не так уж и сложно!" , "Не уверена, что это принесет тебе счастье." ,
                      "Скорее всего, не стоит упускать шанс!" , "Возможно, если ты будешь следовать своему сердцу." ,
                      "Вероятно, это станет только началом пути!" , "Может, удача на твоей стороне!" ,
                      "Не исключено, что это будет нелегко." , "Возможно, успех не заставит себя ждать." ,
                      "Скорее всего, не стоит бояться изменений!" , "Может, помни, что все возможно!" ,
                      "Не исключено, что ты сможешь это сделать!" , "Вероятно, все идет к лучшему!" ,
                      "Есть вероятность, что это принесет тебе радость." ])
                #await message.reply(
                    #f'🐧 <b>{answer}</b>' ,

                    #parse_mode="HTML" , disable_web_page_preview=True)



























































































































#qs







