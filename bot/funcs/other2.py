import random
from main import *

import pyowm
from datetime import datetime, timedelta
from google_trans_new import google_translator
from datetime import datetime
from yandex.Translater import Translater
from googletrans import Translator
from deep_translator import GoogleTranslator

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
from main import time


def parse_date(date_str):
    formats = ['%d.%m.%Y', '%Y.%m.%d']
    for fmt in formats:
        try:
            from datetime import datetime
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Date format for '{date_str}' is not recognized")

# Функция для получения склонения
def get_declension(number, one, few, many):
    if number % 10 == 1 and number % 100 != 11:
        return one
    elif number % 10 in [2, 3, 4] and (number % 100 < 10 or number % 100 > 20):
        return few
    else:
        return many

# Функция для форматирования чисел с правильными склонениями
def format_with_declension(number, one, few, many):
    formatted_number = "{:,.0f}".format(number).replace(",", ".")
    declension = get_declension(number, one, few, many)
    return f"{formatted_number} {declension}"


@dp.message()
async def  other2(message: Message):
    parts = message.text.lower().split()

    date_str = None  # Инициализация переменной для даты

    # Проверяем условия для извлечения даты
    if len(parts) >= 4 and parts [ 0 ] in [ 'кут' , 'кут,' , 'сколько' ] and parts [ 1 ] in [ 'времени' , 'секунд' ,
                                                                                              'минут' , 'дней' , 'лет' ,
                                                                                              'прошло' , 'сколько' ] and \
            parts [ 2 ] in [ 'прошло' , 'времени' , 'секунд' , 'лет' , 'минут' , 'дней' ] and parts [ 3 ] in [ 'с' ,
                                                                                                               'от' ,
                                                                                                               'со' ]:
        date_str = ' '.join(parts [ 4: ])

    elif len(parts) >= 3 and parts [ 0 ] in [ 'сколько' , 'кут' , 'кут,' ] and parts [ 1 ] in [ 'времени' , 'сколько' ,
                                                                                                'секунд' , 'минут' ,
                                                                                                'дней' , 'лет' ,
                                                                                                'прошло' ] and parts [
        2 ] in [ 'с' , 'от' , 'со' ]:
        date_str = ' '.join(parts [ 3: ])

    elif len(parts) >= 5 and parts [ 0 ] in [ 'кут' , 'кут,' ] and parts [ 1 ] == 'сколько' and parts [ 2 ] in [
        'времени' , 'сколько' , 'секунд' , 'минут' , 'дней' , 'лет' , 'прошло' ] and parts [ 3 ] in [ 'с' , 'от' ,
                                                                                                      'со' ]:
        date_str = ' '.join(parts [ 5: ])

    elif len(parts) >= 5 and parts [ 0 ] in [ 'кут' , 'кут,' ] and parts [ 1 ] == 'сколько' and parts [ 2 ] in [
        'времени' , 'сколько' , 'секунд' , 'минут' , 'дней' , 'лет' , 'прошло' ] and parts [ 3 ] in [ 'времени' ,
                                                                                                      'сколько' ,
                                                                                                      'секунд' ,
                                                                                                      'минут' , 'дней' ,
                                                                                                      'лет' ,
                                                                                                      'прошло' ] and \
            parts [ 4 ] in [ 'с' , 'от' , 'со' ]:
        date_str = ' '.join(parts [ 5: ])

    elif len(parts) >= 4 and parts [ 0 ] in [ 'кут' , 'кут,' ] and parts [ 1 ] == 'сколько' and parts [ 2 ] in [
        'времени' , 'сколько' , 'секунд' , 'минут' , 'дней' , 'лет' , 'прошло' ] and parts [ 3 ] in [ 'времени' ,
                                                                                                      'сколько' ,
                                                                                                      'секунд' ,
                                                                                                      'минут' , 'дней' ,
                                                                                                      'лет' ,
                                                                                                      'прошло' ] and \
            parts [ 4 ] in [ 'с' , 'от' , 'со' ]:
        date_str = ' '.join(parts [ 5: ])  # Исправлено

    # Проверка на символы в конце даты
    if date_str.endswith(('?' , ',' , '.')):
        if date_str [ -1 ] == '?':
            date_str = date_str [ :-1 ]  # Удаляем символ "?"
        elif date_str [ -1 ] == ',':
            date_str = date_str [ :-1 ].replace(',' , '.')  # Удаляем "," и заменяем все "," на "."
        elif date_str [ -1 ] == '.':
            date_str = date_str [ :-1 ]  # Удаляем символ "."




    # Если date_str всё равно пустой, выходим
    if not date_str:
        return  # Если дата не найдена, просто выходим из функции

    # Пробуем преобразовать строку даты в объект datetime
    try:
        from datetime import datetime
        now = datetime.now()  # Получаем текущее время
        date = parse_date(date_str)  # Пробуем распарсить дату
        delta = now - date

        # Вычисляем годы, дни, минуты и секунды
        days_passed = delta.days
        seconds_passed = int(delta.total_seconds())
        minutes_passed = seconds_passed // 60
        years_passed = days_passed // 365  # Оценка лет

        # Применяем форматирование и склонения
        days_str = format_with_declension(days_passed , "день" , "дня" , "дней")
        minutes_str = format_with_declension(minutes_passed , "минута" , "минуты" , "минут")
        seconds_str = format_with_declension(seconds_passed , "секунда" , "секунды" , "секунд")

        response_parts = [ ]
        if years_passed > 0:
            months_passed = (days_passed % 365) // 30
            years_float = round(years_passed + months_passed / 12 , 1)
            years_str = format_with_declension(int(years_float) , "год" , "года" , "лет")
            response_parts.append(f"<b><i>- {years_str} [ {years_float} ]</i></b>")
        if days_passed > 0:
            response_parts.append(f"<b><i>- {days_str}</i></b>")
        if minutes_passed > 0:
            response_parts.append(f"<b><i>- {minutes_str}</i></b>")
        if seconds_passed > 0:
            response_parts.append(f"<b><i>- {seconds_str}</i></b>")

        phrases1 = [ "Время летит, не оглядываясь." , "Минуты складываются в годы, не успеешь оглянуться." ,
            "Вчера казалось ближе, чем сегодня." , "Прошло с тех пор" , "С каждым мигом вчера становится дальше." ,
            "Время убегает, не догнать." ]
        selected_phrase = random.choice(phrases1)

        sticker_id = 'CAACAgIAAxkBAY-SnWcBaUo6ysY96c1JFYkuyXmramSeAAJOAANZu_wlDevP2fnQeCo2BA'
        await message.reply_sticker(sticker_id)

        response = f"🕰 <b>{selected_phrase}</b>\n\n" + "\n".join(
            response_parts) if response_parts else "🛠 Дата в будущем или формат даты неверен."
        await message.reply(response , parse_mode="HTML")

    except ValueError:
        await message.reply("✖️ Пожалуйста, введите дату в формате ДД.ММ.ГГГГ.")