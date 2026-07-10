from aiogram.fsm.state import StatesGroup, State  # Изменение пути импорта для состояний
from bot.config.config import *
import random

def check_draw(listt: list):
    # Подсчитываем количество заполненных клеток
    count_filled_cells = 0
    for cell in listt:
        if cell in ["o", "x"]:
            count_filled_cells += 1
    # Если количество заполненных клеток равно 9, то это ничья
    return count_filled_cells == 9

def check_win(listt: list, side: str):
    # Проверяем выигрышные комбинации по горизонтали, вертикали и диагоналям
    win_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Горизонтали
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Вертикали
        [0, 4, 8], [2, 4, 6]              # Диагонали
    ]
    for combination in win_combinations:
        if all(listt[i] == side for i in combination):
            return True
    # Если нет выигрышной комбинации, проверяем, не наступила ли ничья
    if check_draw(listt):
        return "Draw"
    # Иначе продолжаем игру
    return False

class Start(StatesGroup):
    start_name= State()
    start_name1= State()
    start_name2= State()
    start_name3= State()

    start_name4= State()
    start_name5= State()
    start_name6= State()
    start_name7 = State()


class money(StatesGroup):
	money_cube = State()
	money_bolling = State()
	money_basketball = State()
	money_slots = State()
	send_money_to_user = State()

class links(StatesGroup):
    reward = State()
    link = State()


def is_number(_str):
	try:
		int(_str)
		return True
	except ValueError:
		return False



def create_mines_and_monets():
    position_mine = random.randint(0, 4)
    position_cush = random.randint(0, 4)
    if position_mine == position_cush:
        value = position_mine
        while position_mine == value:
            position_mine = random.randint(0,4)
    return [position_mine, position_cush]


def create_list_mines():
    listt = ["x","x","x","x","x",
            "x","x","x","x","x",
            "x","x","x","x","x",
            "x","x","x","x","x",
            "x","x","x","x","x",
    ]
    for i in range(0, 5):
        created_list = create_mines_and_monets()
        position_change = i*5
        listt[created_list[0] + position_change] = "*"
        listt[created_list[1] + position_change] = "$"
    return listt

import requests

def get_channel_id(link):
    BOT_TOKEN = TOKEN
    username = link[13:]
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id=@{username}"
    response = requests.get(url)
    data = response.json()
    return data["result"]["id"]

def random_element_with_chance(catalog):
    total_chance = sum([catalog[key][1] for key in catalog])
    total_chance += 20  # добавляем оставшиеся 20% вероятности
    rnd = random.uniform(0, total_chance)
    for key in catalog:
        if rnd < catalog[key][1]:
            return [key, "item"]
        rnd -= catalog[key][1]
    # если выпало оставшиеся 20% вероятности
    return [random.randint(10,100), "num"]