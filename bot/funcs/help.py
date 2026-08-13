# -*- coding: utf-8 -*-
from aiogram import Bot, Dispatcher, types

from aiogram.enums import ParseMode, ChatType  # Импортируем ParseMode из aiogram.enums
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from aiogram import types
import aiogram
import random
from aiogram.types import Message
from bot.config.config import *
from bot.design.buttons import *
from main import dp,button_user_message_help,user_message_help,user_message_helpgame,user_message_brak,user_message_store,user_message_textglobhelp,user_message_gamehelp,user_message_ffunc


text_admin_help = f'''
<tg-emoji emoji-id='5352668069984510307'>🛡</tg-emoji> <b>Модерация · полная справка</b>

<tg-emoji emoji-id='5890838600433536921'>🔇</tg-emoji> <b>Мут</b>
<tg-emoji emoji-id='6023965819057217444'>🔇</tg-emoji> <b>Запрет писать в определенную группу</b>
<blockquote>Мут [срок (по желанию)] [пользователь] [причина (по желанию)]</blockquote>
<tg-emoji emoji-id='5843462551358148756'>🔇</tg-emoji> <b>Запрет писать во всех официальных группах проекта</b>
<blockquote>Муталл [срок (по желанию)] [пользователь] [причина (по желанию)]</blockquote>

<b>Снятие мута</b>
<blockquote>размут [пользователь]</blockquote>
<blockquote>размуталл [пользователь]</blockquote>


<tg-emoji emoji-id='5397679249937155116'>👋</tg-emoji> <b>Исключение с групп</b>
<tg-emoji emoji-id='5397976749436842796'>⚡</tg-emoji> <b>Кик - исключение с определенной группы</b>
<blockquote>Кик [пользователь] [причина (по желанию)]</blockquote>
<tg-emoji emoji-id='5397773700562960960'>🪖</tg-emoji> <b>Кикалл - исключение со всех официальных групп проекта</b>
<blockquote>Кикалл [пользователь] [причина (по желанию)]</blockquote>


<tg-emoji emoji-id='5296773795091094130'>💎</tg-emoji> <b>Блокировка</b> 
<tg-emoji emoji-id='4956337889593000947'>🚫</tg-emoji> <b>Блокировка в определенной группе</b>
<blockquote>Бан [срок (по желанию)] [пользователь] [причина (по желанию)]</blockquote>
<tg-emoji emoji-id='5472267631979405211'>🚫</tg-emoji> <b>Блокировка во всех официальных группах проекта</b>
<blockquote>Баналл [срок (по желанию)] [пользователь] [причина (по желанию)]</blockquote>
<tg-emoji emoji-id='5305629674058061875'>🐈‍⬛</tg-emoji> <b>Блокировка во всем проекте</b>
<blockquote>Банфулл [срок (по желанию)] [пользователь] [причина (по желанию)]</blockquote>

<b>Снятие блокировки в определенной группе</b>
<blockquote>Разбан [пользователь]</blockquote>
<blockquote>Разбаналл [пользователь]</blockquote>
<blockquote>Разбанфулл [пользователь]</blockquote>


<tg-emoji emoji-id='5352756722404466080'>🗽</tg-emoji> <b>Варн предупреждения</b>
<tg-emoji emoji-id='5213181173026533794'>⚠️</tg-emoji> <b>Выдать предупреждение в определенной группе проекта</b>
<blockquote>Варн [срок (по желанию)] [пользователь] [причина (по желанию)]</blockquote>
<tg-emoji emoji-id='5447644880824181073'>⚠️</tg-emoji> <b>Выдать предупреждение во всех группах проекта</b>
<blockquote>Варналл [срок (по желанию)] [пользователь] [причина (по желанию)]</blockquote>
<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Выдать предупреждение во всем проекте</b>
<blockquote>Варнфулл [срок (по желанию)] [пользователь] [причина (по желанию)]</blockquote>

<b>Снятие предупреждения</b>
<blockquote>Разварн [пользователь] </blockquote>
<blockquote>Разварналл [пользователь] </blockquote>
<blockquote>Разварнфулл [пользователь] </blockquote>


<tg-emoji emoji-id='6021405408663445899'>📋</tg-emoji> <b>Сводки и админка</b>
<b>Проверка своих наказаний</b>
<blockquote>Мои наказания</blockquote>
<b>Проверка предупреждений</b>
<blockquote>Мои варны</blockquote>
<b>Узнать админ-состав Эпсилона ( Защитная организация проекта ) </b>
<blockquote>Кто админ</blockquote>
<b>Узнать права сотрудников Эпсилона </b>
<blockquote>Права админов</blockquote>


<tg-emoji emoji-id='5397718596132554015'>🤙</tg-emoji> <b>Для выдачи наказания, обязательно нужно добавлять фото-доказательства</b>'''
clanss = f'''
<b>🛡️ Кланы</b>

🏰 <b>Создание клана</b>
<code>Создать клан [эмодзи клана]</code>

📜 <b>Личный клан</b>
<code>Мой клан</code>

📋 <b>Список кланов</b>
<code>Список кланов</code> 

💌 <b>Приглашение в свой клан</b>
<code>Пригласить в клан</code>

🧩 <b>Присоединение к клану</b>
<code>Присоединиться к клану [эмодзи клана]</code>

😎 <b>Повышение до заместителя клана</b>
<code>Повысить до заместителя</code>

😢 <b>Снятие заместителя клана</b>
<code>Снять заместителя</code>

📋 <b>Пользователи клана</b>
<code>Пользователи клана</code>

💰 <b>Раздачи кут участникам клана</b>
<code>Раздать клану [сумма]</code>

🚪 <b>Удаление участника</b> 
<code>Клан выгнать [@Username пользователя]</code>

🚶‍♂️ <b>Уход с клана</b>
<code>Покинуть клан</code>

✏️ <b>Переименование клана</b>
<code>Переименовать клан [новое название клана]</code>

❌ <b>Удаление клана</b>
<code>Удалить клан</code>

🏆 <b>Статистика кланов</b> 
<code>Топ клан</code>

⚔️ <b>Атака на другой клан</b> 
<code>Атаковать клан [эмодзи клана для атаки]</code>

⭐️ <b><i>Играя против игроков из враждебного клана, вы обмениваетесь не только кутами, но и рейтингом их кланов!</i></b>
    '''

bonus_block_zabhelp = ""
if enabled_bonus:
    bonus_block_zabhelp = """
<tg-emoji emoji-id='5429156545558506877'>🎁</tg-emoji> <b>Открытие бонуса</b>
<blockquote><code>Бонус</code></blockquote>
"""

ref_top_bonus_block = ""
if enabled_bonus:
    ref_top_bonus_block = """
<b><tg-emoji emoji-id='5033242607627535090'>🔰</tg-emoji> Бонусы для топ-3 лидеров в реферальной статистике
• 1-е место: 50% от покупок рефералов
• 2-е место: 40% от покупок рефералов
• 3-е место: 35% от покупок рефералов</b>
<blockquote><code>Реферальная статистика</code></blockquote>
"""

textzabhelp = f'''
<tg-emoji emoji-id='5303547422373349738'>💰</tg-emoji> <b>Как заработать кут?</b>

<tg-emoji emoji-id='5296561370303592127'>🌟</tg-emoji> <b><i>Куты - валюта для любых покупок в боте и не только!</i></b>

<tg-emoji emoji-id='5260547274957672345'>🎮</tg-emoji> <b>Игра на ставки</b>
<i>Играйте с другими пользователями на ставки в виде кутов. Побеждайте и увеличивайте свой баланс!</i>
<blockquote><code>Хелп игры</code></blockquote>
{bonus_block_zabhelp}
<tg-emoji emoji-id='5294245773045691151'>🍹</tg-emoji> <b>Выполнение заданий</b>
<i>Выполняйте задания подписываясь на каналы или группы, получая за это игровую валюту</i>
<blockquote><code>Задания</code></blockquote>

<tg-emoji emoji-id='5438449626426410465'>🎁</tg-emoji> <b>Промокоды</b>
<i>Активируйте промокоды и получайте куты</i>
<blockquote><code>Промолист</code></blockquote>
<blockquote><code>Промо [промокод]</code></blockquote>

<tg-emoji emoji-id='5438135471043542108'>🤝</tg-emoji> <b>Помощь от друзей</b>
<i>Ваши друзья могут передать вам куты - для этого им нужно ответить на ваше сообщение, написав:</i>
<blockquote><code>дать (сумма)</code></blockquote>

<tg-emoji emoji-id='5406683434124859552'>🛍</tg-emoji> <b>Торговля в магазине</b>
<i>Покупайте предметы в ограниченных количествах по низким ценам и продавайте их дороже. Зарабатывайте на разнице!</i>
<blockquote><code>Хелп магазин</code></blockquote>

<tg-emoji emoji-id='5438591983117435227'>🍻</tg-emoji> <b>Приглашение друзей</b>
<i>Приглашайте друзей и получайте куты за каждого нового участника, а также 25% от их покупок в магазине!</i>
<blockquote><code>Хелп реф</code></blockquote>
{ref_top_bonus_block}
<tg-emoji emoji-id='5229225792159888151'>💸</tg-emoji> <b>Удачных заработков!</b>
'''

textglobhelp = f'''
<tg-emoji emoji-id='5318959255385043017'>🎩</tg-emoji> <b>Что такое Кут? </b>
<tg-emoji emoji-id='5436339947080548936'>🌟</tg-emoji> <b>Кут - это элитный игровой Telegram-бот с собственной валютой.

<tg-emoji emoji-id='5294001020039363545'>🏆</tg-emoji> <i>Почему Кут - это круто?

<tg-emoji emoji-id='5192951739623447936'>🍹</tg-emoji> Упор сделан на качественный интерфейс, азартные механики и чувство VIP‑статуса.
<tg-emoji emoji-id='5321021153219732362'>⚡️</tg-emoji> Удобный и качественный интерфейс
<tg-emoji emoji-id='5294261673014626477'>🌟</tg-emoji> Пользователи могут обменивать Куты на Telegram Stars, Premium-подписку и другие награды.

<blockquote>Цель - не просто развлечь, а выделить пользователя среди остальных.</blockquote></i></b>
'''



textstore = f'''
<b><tg-emoji emoji-id='5319122988128299716'>🛍</tg-emoji> Магазин</b>

<tg-emoji emoji-id='5354854010769665740'>🎩</tg-emoji> <b><i>В магазине можно купить уникальные предметы. Каждый товар имеет ограниченное количество, поэтому предметы можно перепродавать за более высокую цену другим пользователям.</i></b>


<tg-emoji emoji-id='5424917782204547462'>🛍</tg-emoji> <b><i>Магазин предметов</i></b>
<blockquote><code>Магазин</code></blockquote>

<tg-emoji emoji-id='5294417588917393310'>🎒</tg-emoji> <b><i>Инвентарь</i></b>
<blockquote><code>Инвентарь</code></blockquote>

<tg-emoji emoji-id='5294515694560393247'>💰</tg-emoji> <b><i>Покупка предмета</i></b>
<blockquote><code>Купить [эмодзи предмета] [количество (по желанию)]</code></blockquote>

<tg-emoji emoji-id='5294406460657133642'>🍹</tg-emoji> <b><i>Крафт предметов</i></b>
<blockquote><code>Крафт [эмодзи предмета] + [эмодзи предмета]</code></blockquote>

<tg-emoji emoji-id='5438578110373069347'>🪄</tg-emoji> <b><i>Использование предмета</i></b>
<blockquote><code>Использовать [эмодзи предмета]</code></blockquote> 

<tg-emoji emoji-id='5438163474230312610'>💰</tg-emoji> <b><i>Выставление предмета в магазин</i></b>
<blockquote><code>Выставить [эмодзи предмета] [количество (необязательно)]</code></blockquote>

<tg-emoji emoji-id='5438449312893792440'>🚀</tg-emoji> <b><i>Передача предметов</i></b>
<blockquote><code>Передать [эмодзи предмета] [количество (по желанию, для продажи предмета обязательно)] [цена (по желанию,для продажи предмета обязательно)]</code></blockquote> 


<tg-emoji emoji-id='5355181686709580033'>🩵</tg-emoji><b> Оформление профиля</b>

<tg-emoji emoji-id='5354914436664548601'>🧡</tg-emoji> <b>Строка имени</b>
<blockquote><code>профильимя [предмет]</code></blockquote>

<tg-emoji emoji-id='5355097050084041640'>❤️</tg-emoji> <b>Строка юзернейма [если есть]</b>
<blockquote><code>профильюз [предмет]</code></blockquote>

<tg-emoji emoji-id='5354952477189894664'>🩷</tg-emoji> <b>Строка индентификатора</b>
<blockquote><code>профильид [предмет]</code></blockquote>

<tg-emoji emoji-id='5355101753073232197'>💛</tg-emoji> <b>Строка баланса</b>
<blockquote><code>профильбаланс [предмет]</code></blockquote>

<tg-emoji emoji-id='5355269445776338783'>💚</tg-emoji> <b>Строка выигранных кут</b>
<blockquote><code>профильвыиграно [предмет]</code></blockquote>

<tg-emoji emoji-id='5355223773094115550'>💙</tg-emoji> <b>Строка лимита</b>
<blockquote><code>профильлимит [предмет]</code></blockquote>

<tg-emoji emoji-id='5354837565339888644'>💜</tg-emoji> <b>Строка рефералов</b>
<blockquote><code>профильреф [предмет]</code></blockquote>

<b>Профиль тоже хочет быть красивым</b>
    '''

gamehelp = f'''
<tg-emoji emoji-id='5319229795375018323'>🎮</tg-emoji> <b>Многопользовательские игры :

<tg-emoji emoji-id='5424687267014801006'>♟</tg-emoji> Шашки
<blockquote><code>Шашки [ставка]</code></blockquote>

<tg-emoji emoji-id='5188239353045868629'>🪵</tg-emoji> Найди пару
<blockquote><code>Мемори [ставка]</code></blockquote>

<tg-emoji emoji-id='5370783443175086955'>🍪</tg-emoji> Бинго
<blockquote><code>Бинго [ставка]</code></blockquote>

<tg-emoji emoji-id='5226711870492126219'>🎡</tg-emoji> Фортуна
<blockquote><code>Фортуна [ставка]</code></blockquote>

<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> Кости
<blockquote><code>Кости [ставка]</code></blockquote>

<tg-emoji emoji-id='5222486447306602688'>🔫</tg-emoji> Дуэли
<blockquote><code>Дуэль [ставка]</code></blockquote>

<tg-emoji emoji-id='5269254848703902904'>🦅</tg-emoji> Орел или решка
<blockquote><code>Орел [ставка]</code> / <code>Решка [ставка]</code></blockquote>

<tg-emoji emoji-id='5237808360882977239'>✂️</tg-emoji> Камень-ножницы-бумагa
<blockquote><code>Кнб [ставка]</code></blockquote>

<tg-emoji emoji-id='5469913852462242978'>🧨</tg-emoji> Мины
<blockquote><code>Мины [ставка]</code></blockquote>

<tg-emoji emoji-id='5226660202035554522'>☑️</tg-emoji> Крестики-нолики
<blockquote><code>Кн [ставка]</code></blockquote>


<tg-emoji emoji-id='5458599894992316450'>🧸</tg-emoji> Одиночные игры :
<i>Для игры нужна группа с кутами на балансе</i>

<tg-emoji emoji-id='5204467307153234577'>🍀</tg-emoji> Башня
<blockquote><code>как играть в Башни</code></blockquote>

<tg-emoji emoji-id='5438449312893792440'>🌴</tg-emoji> Риск
<blockquote><code>Как играть в Риск</code></blockquote>

<tg-emoji emoji-id='5246916607833304803'>💫</tg-emoji> Плиты
<blockquote><code>Как играть в Плиты</code></blockquote>

<tg-emoji emoji-id='5469654973308476699'>💣</tg-emoji> Бомбы
<blockquote><code>Как играть в Бомбы</code></blockquote>

<tg-emoji emoji-id='5296306038792808890'>📈</tg-emoji> Трейд
<blockquote><code>Как играть в Трейд</code></blockquote>

<tg-emoji emoji-id='5363877049863786071'>🎱</tg-emoji> Шарик
<blockquote><code>Как играть в Шарик</code></blockquote>

<tg-emoji emoji-id='5782990399672946716'>🎗</tg-emoji> Провода
<blockquote><code>Как играть в Провода</code></blockquote>

<tg-emoji emoji-id='5891135206580031104'>🎰</tg-emoji> Слоты
<blockquote><code>Как играть в слоты</code></blockquote>

<tg-emoji emoji-id='5891181665241271999'>🏀</tg-emoji> Баскетбол
<blockquote><code>Как играть в Баскет</code></blockquote>

<tg-emoji emoji-id='5890787425898205095'>⚽️</tg-emoji> Футбол
<blockquote><code>Как играть в Футбол</code></blockquote>

<tg-emoji emoji-id='5891120371762990493'>🎳</tg-emoji> Боулинг
<blockquote><code>Как играть в Боулинг</code></blockquote>

<tg-emoji emoji-id='5890815115552362075'>🎯</tg-emoji> Дартс
<blockquote><code>Как играть в Дартс</code></blockquote>

<tg-emoji emoji-id='5890971177484029249'>🎲</tg-emoji> Кубик
<blockquote><code>Как играть в Куб</code></blockquote>

<tg-emoji emoji-id='5321499578216769477'>🎩</tg-emoji> Рулетка
<blockquote><code>Как играть в Рулетку</code></blockquote>


<tg-emoji emoji-id='5303410911132814482'>💰</tg-emoji> Дополнительные игры :

<tg-emoji emoji-id='5249238643247179904'>⭐️</tg-emoji> Слова
<blockquote><code>@CuteGamingBot Слова</code></blockquote>


Не выиграет только тот кто не играет.</b>
'''


other = f'''
<b><tg-emoji emoji-id='5354789281317548026'>🍭</tg-emoji> Дополнительные функции</b>

<tg-emoji emoji-id='5283075860188898177'>🌤</tg-emoji> <b><i>Погода в городе</i></b>
<blockquote><code>Погода [город]</code></blockquote>

<tg-emoji emoji-id='5255937074242020424'>📡</tg-emoji> <b><i>Время в городе</i></b>
<blockquote><code>Время [город]</code></blockquote>

<tg-emoji emoji-id='5467550297599516219'>🙊</tg-emoji> <b><i>Повторение фраз</i></b>
<blockquote><code>Кут скажи [сообщение]</code></blockquote>

<tg-emoji emoji-id='5269254848703902904'>🌕</tg-emoji> <b><i>Орел или решка</i></b>
<blockquote><code>Кут орел или решка?</code></blockquote>

<tg-emoji emoji-id='5389062952835886404'>☝️</tg-emoji> <b><i>Что же выберет кут?</i></b>
<blockquote><code>Кут [привет] или [пока]</code></blockquote>

<tg-emoji emoji-id='5332505749740341554'>📅</tg-emoji> <b><i>Недавние новости в мире</i></b>
<blockquote><code>Кут покажи новости</code></blockquote>

<tg-emoji emoji-id='5318963211049901195'>🚀</tg-emoji> <b><i>Анекдот от кута</i></b>
<blockquote><code>Кут анекдот</code></blockquote>

<tg-emoji emoji-id='5314665117017718786'>⏳</tg-emoji> <b><i>Сколько времени пришло с определенной даты</i></b>
<blockquote><code>кут сколько прошло времени с [дата]</code></blockquote>

<tg-emoji emoji-id='5375129357373165375'>🔗</tg-emoji> <b><i>Переводчик</i></b>
<blockquote><code>Кут переведи</code></blockquote>

<tg-emoji emoji-id='5341334596183163309'>📱</tg-emoji> <b><i>Калькулятор</i></b>
<blockquote><code>Кут посчитай 1+1</code></blockquote>

<tg-emoji emoji-id='5420552583603320881'>🌐</tg-emoji> <b><i>Поисковик информации</i></b>
<blockquote><code>кут, что такое [вопрос]</code></blockquote>

<tg-emoji emoji-id='5280924618444514633'>🐻‍❄️</tg-emoji> <b><i>Выбор любого числа, между указанными числами</i></b>
<blockquote><code>Кут рандом [1 число] [2 число]</code></blockquote>

<tg-emoji emoji-id='5418331857878016419'>💬</tg-emoji> <b><i>Скрытое сообщение</i></b>
<blockquote><code>Прошептать [сообщение]</code></blockquote>

<tg-emoji emoji-id='5469870473292556436'>🍺</tg-emoji> <b><i>Стикеры</i></b>
<blockquote><code>Кут стик</code></blockquote>

<tg-emoji emoji-id='5442983582882601962'>🗿</tg-emoji> <b><i>Эмодзи</i></b>
<blockquote><code>Кут эмодзи</code></blockquote>

<tg-emoji emoji-id='5434121252874756456'>🕊</tg-emoji> <b><i>Цитата</i></b>
<blockquote><code>Кут цитата</code></blockquote>

<tg-emoji emoji-id='5323479382046554875'>🧙</tg-emoji> <b><i>Миф</i></b>
<blockquote><code>Кут миф</code></blockquote>

<tg-emoji emoji-id='5289600830339557025'>📜</tg-emoji> <b><i>Стих</i></b>
<blockquote><code>Кут стих</code></blockquote>

<tg-emoji emoji-id='5463359272807045552'>🧠</tg-emoji> <b><i>Факты</i></b>
<blockquote><code>Кут факт</code></blockquote>

<tg-emoji emoji-id='5891226736628076283'>🎲</tg-emoji> <b><i>Рандом число</i></b>
<blockquote><code>Кут число</code></blockquote>

<tg-emoji emoji-id='5449850741667668411'>🌿</tg-emoji> <b><i>Темы для разговора</i></b>
<blockquote><code>Кут, темы для разговора</code></blockquote>
    '''

ffunc = f'''
<b><tg-emoji emoji-id='5415629520289950139'>🔧</tg-emoji> Функции</b>

<tg-emoji emoji-id='5321499578216769477'>🎩</tg-emoji> <b><i>Профиль</i></b> 
<blockquote><code>Кто я</code></blockquote>

<tg-emoji emoji-id='5292146637844543370'>💰</tg-emoji> <b><i>Текущий баланс</i></b>
<blockquote><code>Б</code></blockquote>
    
<tg-emoji emoji-id='5438523525633701958'>🎁</tg-emoji> <b><i>Передача кут</i></b>
<blockquote><code>Дать / передать</code></blockquote>

<tg-emoji emoji-id='5265042082786992759'>📝</tg-emoji> <b><i>История действий</i></b>
<blockquote><code>История</code></blockquote>
    
<tg-emoji emoji-id='5246963307012714601'>📚</tg-emoji> <b><i>Статистика</i></b>
<blockquote><code>Топ</code></blockquote>

<tg-emoji emoji-id='5256187664108899227'>🥷</tg-emoji> <b><i>Кто ты?</i></b> 
<blockquote><code>Кто ты\n[в ответ на текст пользователя]</code></blockquote>

<tg-emoji emoji-id='5350572310627632617'>✅</tg-emoji> <b><i>Репутация</i></b>
<blockquote><code>+/- | ответив на сообщение пользователя</code></blockquote>

<tg-emoji emoji-id='6028346797368283073'>✈️</tg-emoji> <b><i>Приветствие при входе в группу</i></b>
<blockquote>+приветствие</blockquote>
<blockquote>-приветствие</blockquote>

<tg-emoji emoji-id='5904248647972820334'>💭</tg-emoji> <b><i>Статистика в группе</i></b>
<blockquote>+стата</blockquote>
<blockquote>-стата</blockquote>

<tg-emoji emoji-id='5891211339170326418'>⌛️</tg-emoji> <b><i>Задержка игр в группе</i></b>
<blockquote><b><i>+задержка (число)</i></b></blockquote>
<blockquote><b><i>-задержка (число)</i></b></blockquote>

<tg-emoji emoji-id='5251344521546965676'>🏖</tg-emoji> <b><i>Баланс группы</i></b>
<blockquote><code>Бч</code></blockquote>

<tg-emoji emoji-id='5472178859300363509'>🏖</tg-emoji> <b><i>Пополнить баланс группы</i></b>
<blockquote><code>Положить [сумма пополнения]</code></blockquote>

<tg-emoji emoji-id='5199790590279033017'>🏖</tg-emoji> <b><i>Снять с баланса группы</i></b>
<blockquote><code>Снять [сумма снятия]</code></blockquote>
'''

brak = f'''
<b>🌹 Браки</b>

❤️ <b><i>Создание брака</i></b>
<code>Брак [в ответ на текст пользователя]</code>

💋 <b><i>Информация о своем браке</i></b>
<code>Мой брак</code> 

💔 <b><i>Развод с пользователем</i></b> 
<code>Развод</code> 

❤️‍🔥 <b><i>Любовь - это сила, которая преображает мир.</i></b> 
    '''

texteditprofile = f'''
<b>🩵 Оформление профиля</b>
<b>Профиль тоже хочет быть красивым</b>

🧡 <b>Строка имени</b>
<blockquote><code>профильимя [предмет]</code></blockquote>

❤️ <b>Строка юзернейма [если есть]</b>
<blockquote><code>профильюз [предмет]</code></blockquote>

🩷 <b>Строка индентификатора</b>
<blockquote><code>профильид [предмет]</code></blockquote>

💛 <b>Строка баланса</b>
<blockquote><code>профильбаланс [предмет]</code></blockquote>

💚 <b>Строка выигранных кут</b>
<blockquote><code>профильвыиграно [предмет]</code></blockquote>

💙 <b>Строка лимита</b>
<blockquote><code>профильлимит [предмет]</code></blockquote>

💜<b>Строка рефералов</b>
<blockquote><code>профильреф [предмет]</code></blockquote>
    '''

wordhelp = [
    "📚 Что я могу? Узнайте!",
    "📗 Проверьте, я интересен!",
    "📕 Почему я космический бот?",
    "📙 Я крут! Хотите знать как?",
    "📘 Кто я? Узнайте сейчас!",
    "📚 Почему все говорят обо мне?",
    "📗 Как я стал классным?",
    "📕 У меня много интересного!",
    "📘 Все в курсе, а вы?",
    "📚 Я из другой галактики!",
    "📗 Я готов рассказать всё!",
    "📕 Чем я полезен?",
    "📘 Загадочный, но доступный!",
    "📚 Узнайте мой секрет!",
    "📗 Все в восторге! А вы?",
    "📕 Я загадка! Хотите разгадать?",
    "📘 Есть что рассказать!",
    "📚 Я звезда! Узнайте почему!"
]

bonus_help_block = ""
if enabled_bonus:
    bonus_help_block = """
🎁 <b>Открывайте бонусы</b>
<blockquote><b><code>Бонус</code></b></blockquote>
"""

texthelpgame = f"""
🚀 <b>Как начать играть?</b>

💰 <b>Игры на ставки</b>
<b><blockquote>Например : <code>Крестики нолики 10</code></blockquote></b>

🎮 <b>Игры без ставок</b>
<b><blockquote>Например : <code>Крестики нолики</code></blockquote></b>

🎰 <b>Одиночные игры</b>
<b><blockquote>Например : <code>Башня 10</code></blockquote></b>


<blockquote>💰 <b>Куты - игровая валюта для игр и покупок в боте</b></blockquote>

🎮 <b>Играйте на ставки и выигрывайте куты у других игроков.</b>
<blockquote><b><code>Хелп игры</code></b></blockquote>

🛒 <b>Торгуйте на бирже. Покупайте дешевле, продавайте дороже.</b>
<blockquote><b><code>Хелп биржа</code></b></blockquote>
{bonus_help_block}
📚 <b>Помощь : <code>Хелп</code></b>
"""

kinghelp = """
<tg-emoji emoji-id='5425094988260188065'>💪</tg-emoji> <b>Вы хотите, чтобы ваша группа стала живее и активнее? Система «Царь статистики» создана именно для этого. </b>

<blockquote><b><tg-emoji emoji-id='5246750298109656142'>🕺</tg-emoji> Вы сами выбираете период (день, неделя, месяц) и назначаете награды для трёх лучших участников - все призы автоматически списываются с вашего баланса.</b></blockquote>
 
<blockquote><b><tg-emoji emoji-id='5382316645840619380'>🖊</tg-emoji> Никаких сложностей : включите, задайте призы, и топ-3 получат своё. Гибкие настройки под ваш стиль - и активность взлетит. Попробуйте - вы увидите результат сразу.</b></blockquote>
<b>Просто напишите в группе «<code>система царя статистики</code>»</b>
"""

user_message_admin_help = LazyGameStore("user_message_admin_help")

# --- Help: только автор сообщения «хелп» может нажимать кнопки ---
_HELP_ADMIN_ALIASES = frozenset({
    "хелп админы", "хелп админ", "хелп админка", "хелп модерация", "хелп наказания",
    "админы хелп", "админ хелп", "админка хелп", "модерация хелп", "наказания хелп",
    "хелп/админы", "хелп/админ", "хелп/админка", "хелп/модерация", "хелп/наказания",
    "админы/хелп", "админ/хелп", "админка/хелп", "модерация/хелп", "наказания/хелп",
    "help admin", "help admins", "help moderation", "help punishments",
})


def _help_norm(text: str) -> str:
    return " ".join((text or "").lower().strip().split())


def _help_register_message(user_id: int, message_id: int) -> None:
    user_message_help[user_id] = message_id
    user_message_help.save()


def _help_is_message_owner(user_id: int, message_id: int) -> bool:
    return user_id in user_message_help and user_message_help[user_id] == message_id


async def _help_reject_intruder(call: types.CallbackQuery) -> None:
    await call.answer(random.choice(randommessagehelp))


def _help_owner_guard(user_id: int, message_id: int) -> bool:
    """True нажал автор help-сообщения."""
    return _help_is_message_owner(user_id, message_id)


def is_admin_help_text(text: str | None) -> bool:
    return _help_norm(text or "") in _HELP_ADMIN_ALIASES


async def send_admin_help(message: Message) -> None:
    """Справка модерации: «хелп админы» и синонимы."""
    user_id = message.from_user.id
    try:
        sent = await message.reply(
            text_admin_help,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=btn_help,
        )
    except TelegramBadRequest as exc:
        err = str(exc).lower()
        if "message is too long" in err or "text is too long" in err:
            split_at = text_admin_help.rfind("\n", 0, len(text_admin_help) // 2)
            if split_at < 0:
                split_at = len(text_admin_help) // 2
            await message.reply(
                text_admin_help[:split_at],
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            sent = await message.reply(
                text_admin_help[split_at:].lstrip("\n"),
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=btn_help,
            )
        else:
            print(f"[HELP][ADMIN] reply failed: {exc}")
            raise
    _help_register_message(user_id, sent.message_id)


async def help(message: Message):
    if message.text == "/help@CuteGamingBot" or message.text.lower() in [ "/help@Cute3TestBot", "/help@CuteGamingBot","помощь" , "хелп" , "help" , "/help","хепл","hepl" ]:
        user_id = message.from_user.id
        from bot.design.buttons import btn_help
        #if message.chat.type == ChatType.PRIVATE:
            #await message.answer("📚")
        randomwordhelp = random.choice(wordhelp)

        button_user_message_help [ user_id ] = {}
        button_user_message_help [ user_id ] [ 'keyboard_join' ] = btn_help
        print(button_user_message_help [ user_id ])
        print(button_user_message_help [ user_id ] [ 'keyboard_join' ])
        sent_messagehelp1 = await message.answer(
            f'📚' , reply_markup=btn_help , parse_mode="HTML")
        
        _help_register_message(user_id, sent_messagehelp1.message_id)
    button_user_message_help.save()

    if is_admin_help_text(message.text):
        await send_admin_help(message)

    if message.text and message.text.lower() in ["хелп царь", "царь хелп", "царь помощь", "help king"]:
        await message.reply(kinghelp, parse_mode="HTML", disable_web_page_preview=True)

    if message.text.lower() in [ "/rules","правила" , "где правила" , "правила группы" , "правила чата" , "смотреть правила" ]:
        if str(message.chat.id) in cute_groups:  # Проверяем, что сообщение в разрешённой группе
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[  # передаем список кнопок
                    [ types.InlineKeyboardButton(text="Читать правила" , url="https://t.me/CuteRules") ] ])
            await message.reply("📚" , reply_markup=keyboard , parse_mode="HTML")


    if message.text in [ "🚀 Как играть?","🚀 как играть?" ]:
        user_id = message.from_user.id
        # Создаем кнопку "_" и клавиатуру
        button = InlineKeyboardButton(text=" " , callback_data="help_store99", style="default" ,
                icon_custom_emoji_id="5226660202035554522")

        # Create the keyboard and set the inline_keyboard field explicitly
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])

        # Отправляем сообщение с клавиатурой
        sent_messagestore1 = await message.reply(
            texthelpgame , parse_mode="HTML" , reply_markup=keyboard)

        # Сохраняем message_id
        user_message_helpgame [ user_id ] = sent_messagestore1.message_id
    user_message_helpgame.save()
    if message.text.lower() in [ "Хелп магазин" , "хелп магазин" , "биржа магазин" , "магазин хелп","Хелп/магазин" , "хелп/магазин" , "магазин/хелп" , "магазин/хелп" ]:
        user_id = message.from_user.id
        # Создаем кнопку "_" и клавиатуру
        button = InlineKeyboardButton(text=" " , callback_data="help_store10", style="default" ,
                icon_custom_emoji_id="5226660202035554522")

        # Create the keyboard and set the inline_keyboard field explicitly
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])

        # Отправляем сообщение с клавиатурой
        sent_messagestore = await message.reply(
            textstore , parse_mode="HTML" , reply_markup=keyboard)

        # Сохраняем message_id
        user_message_store [ user_id ] = sent_messagestore.message_id
    user_message_store.save()

    if message.text.lower()  in [ "Хелп основное","хелп основное","основное хелп","Основное хелп","Главное о боте","главное о боте","главное хелп","Главное хелп","хелп главное","Хелп главное","Хелп/основное","хелп/основное","основное/хелп","Основное/хелп","Главное о боте","главное о боте","главное/хелп","Главное/хелп","хелп/главное","Хелп/главное" ]:
        user_id = message.from_user.id
        # Создаем кнопку "_" и клавиатуру
        button = InlineKeyboardButton(text=" " , callback_data="textglobhelp", style="default" ,
                icon_custom_emoji_id="5226660202035554522")

        # Create the keyboard and set the inline_keyboard field explicitly
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
        sent_messagetextglobhelp = await message.reply(textglobhelp, reply_markup=keyboard, parse_mode="HTML")

        user_message_textglobhelp [ user_id ] = sent_messagetextglobhelp.message_id
    user_message_textglobhelp.save()


    if message.text.lower() in [ "кут игры","игры кута","кутовские игры","игры кут","Хелп игры","хелп игры","игры хелп","Игры хелп", "Хелп/игры","хелп/игры","игры/хелп","Игры/хелп"]:
        user_id = message.from_user.id
        # Создаем кнопку "_" и клавиатуру
        button = InlineKeyboardButton(text=" " , callback_data="gamehelp", style="default" ,
                icon_custom_emoji_id="5226660202035554522")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
        sent_messagetextgamehelp = await message.reply(gamehelp, reply_markup=keyboard, parse_mode="HTML")

        user_message_gamehelp [ user_id ] = sent_messagetextgamehelp.message_id
    user_message_gamehelp.save()

    if message.text.lower() in [ "хелп разное","хелп разное","разное хелп","разное хелп", "Хелп/разное","хелп/разное","разное/хелп","разное/хелп"]:
        user_id = message.from_user.id
        # Создаем кнопку "_" и клавиатуру
        button = InlineKeyboardButton(text=" " , callback_data="gamehelp", style="default" ,
                icon_custom_emoji_id="5226660202035554522")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
        sent_messagetextgamehelp = await message.reply(textglobhelp, reply_markup=keyboard, parse_mode="HTML")

        user_message_gamehelp [ user_id ] = sent_messagetextgamehelp.message_id
    user_message_gamehelp.save()


    if message.text.lower()  in [ "хелп функции","хелп функции","функции хелп","функции хелп", "Хелп/функции","хелп/функции","функции/хелп","функции/хелп"]:
        user_id = message.from_user.id
        # Создаем кнопку "_" и клавиатуру
        button = InlineKeyboardButton(text=" " , callback_data="ffunc", style="default" ,
                icon_custom_emoji_id="5226660202035554522")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
        sent_messagetextffunc = await message.reply(ffunc, reply_markup=keyboard, parse_mode="HTML")

        user_message_ffunc [ user_id ] = sent_messagetextffunc.message_id
    user_message_ffunc.save()


    if message.text.lower() in [ "Хелп брак","хелп брак","брак хелп","брак хелп","Браки хелп","браки хелп","хелп браки","Хелп браки","Хелп/брак","хелп/брак","брак/хелп","брак/хелп","Браки/хелп","браки/хелп","хелп/браки","Хелп/браки"]:
        user_id = message.from_user.id
        # Создаем кнопку "_" и клавиатуру
        button = InlineKeyboardButton(text=" " , callback_data="brak", style="default" ,
                icon_custom_emoji_id="5226660202035554522")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ [ button ] ])
        sent_messagetextbrak = await message.reply(brak, reply_markup=keyboard, parse_mode="HTML")

        user_message_brak [ user_id ] = sent_messagetextbrak.message_id
    user_message_brak.save()







@dp.callback_query(lambda c: c.data.startswith('help_btnadmin'))
async def admin_help_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    message_id = call.message.message_id

    if not _help_owner_guard(user_id, message_id):
        await _help_reject_intruder(call)
        return

    try:
        await call.message.edit_text(
            text=text_admin_help,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=btn_help,
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith('9help_editprofile'))
async def qwehelp_editprofile(call: types.CallbackQuery):

    linkk = f"https://t.me/{call.from_user.username}"
    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:


        await call.message.edit_text(
            text=texteditprofile, parse_mode="HTML", disable_web_page_preview=True, reply_markup=btn_help9)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data.startswith('help_editprofile'))
async def asundifcallback_main(call: types.CallbackQuery):

    linkk = f"https://t.me/{call.from_user.username}"
    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    print("qqaspdqldqqq1")

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
            text=texteditprofile, parse_mode="HTML", disable_web_page_preview=True, reply_markup=btn_help)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified
@dp.callback_query(lambda c: c.data.startswith('9help_btn1'))
async def callbadfssgfafdsack_main(call: types.CallbackQuery):

    linkk = f"https://t.me/{call.from_user.username}"
    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:


        await call.message.edit_text(
            text=textglobhelp, parse_mode="HTML", disable_web_page_preview=True, reply_markup=btn_help9)


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data.startswith('help_btn1'))
async def callbadfsDFGGQack_main(call: types.CallbackQuery):

    linkk = f"https://t.me/{call.from_user.username}"
    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
            text=textglobhelp, parse_mode="HTML", disable_web_page_preview=True, reply_markup=btn_help)


    except TelegramBadRequest as e:

        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)

        pass  # Игнорируем ошибку MessageNotModified
@dp.callback_query(lambda c: c.data.startswith('9help_btn22'))
async def callbaYTRWEQck_main(call: types.CallbackQuery):

    linkk = f"https://t.me/{call.from_user.username}"
    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:


        await call.message.edit_text(
            text=textzabhelp, parse_mode="HTML", disable_web_page_preview=True, reply_markup=btn_help9)

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified
@dp.callback_query(lambda c: c.data.startswith('help_btn22'))
async def callback_erwqedsaCXZmain(call: types.CallbackQuery):

    linkk = f"https://t.me/{call.from_user.username}"
    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
            text=textzabhelp, parse_mode="HTML", disable_web_page_preview=True, reply_markup=btn_help)

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

#🚀 Краш <pre>краш [ставка] [коэфициэнт]</pre>
#🦋 Бабочка <pre>бк [ставка]</pre>

@dp.callback_query(lambda c: c.data.startswith('9help_btn2'))
async def callQWRQWRQback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:

        await call.message.edit_text(
        text=gamehelp,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=btn_help9
    )

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data.startswith('help_btn2'))
async def call12412512back_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return
        await call.message.edit_text(
        text=gamehelp,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=btn_help
    )

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

#<b>🎡 Игры кута :</b>
#🎲 Кубик <pre>Куб [ставка]</pre>
#🎰 Слоты <pre>Слоты [ставка]</pre>
#🏀 Баскетбол <pre>Баскет [ставка]</pre>
#🎳 Боулинг <pre>Боул [ставка]</pre>
#🎯 Дартс <pre>Дарт [ставка]</pre>
#⚽️ Футбол <pre>Футбол [ставка]</pre>
#📈 Трейд <pre>Трейд [вверх/вниз] [ставка]</pre>
#💣 Мины <pre>Мины [ставка]</pre>
#🎰 Казино <pre>Казино [ставка]</pre>
#🎱 Шарик <pre>Шарик [ставка]</pre>
#🪨✂️📄 Кнб <pre>кнб [ставка]</pre>
#🪙 Орёл или решка <pre>Орёл/Решка [ставка]</pre>
#🎡 Фортуна
#<pre>1. Фортуна [ставка] [число]
#2. Фортуна [ставка] [1 число] [2 число]
#3. Фортуна [ставка] [к (красное) / ч (черное)]
#4. Фортуна [ставка] [п (парное) / н (непарное)]
#</pre>
#🚀 Краш <pre>Краш [коэффициент] [ставка]</pre>
#🎩 Крестики нолики <pre>Кн [ставка]</pre>
#🎲 Кости <pre>Кости [ставка]</pre>
#🔫 Дуэли <pre>Дуэль [ставка]</pre>
#🎩 Крестики нолики <pre>Кн [ставка]</pre>
#🎩 В азарте сила, в игре свобода, в победе страсть.

@dp.callback_query(lambda c: c.data.startswith('9help_btn3'))
async def callbacrvecek_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:


        await call.message.edit_text(
        text=other , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help9)

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data.startswith('help_btn3'))
async def call1dacadcaback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
        text=other , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help)

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified
@dp.callback_query(lambda c: c.data.startswith('9help_btnfunk'))
async def calybybybrvcrelback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:

        await call.message.edit_text(
        text=ffunc , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help9)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified
@dp.callback_query(lambda c: c.data.startswith('help_btnfunk'))
async def calltewdxwback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return
        await call.message.edit_text(
        text=ffunc , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified


@dp.callback_query(lambda c: c.data.startswith('9help_btnking'))
async def callback_help_king_9(call: types.CallbackQuery):
    try:
        await call.message.edit_text(
            text=kinghelp,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=btn_help9,
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith('help_btnking'))
async def callback_help_king(call: types.CallbackQuery):
    user_id = call.from_user.id
    message_id = call.message.message_id
    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return
        await call.message.edit_text(
            text=kinghelp,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=btn_help,
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith('9help_btn4'))
async def caloakdaslpdlback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type


    randommessagehelp1 = random.choice(randommessagehelp)

    try:


        await call.message.edit_text(
        text=brak , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help9)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data.startswith('help_btn4'))
async def callbacsqdqwdqk_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type


    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
        text=brak , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified
@dp.callback_query(lambda c: c.data.startswith('9help_btn5'))
async def callback_aosdaslpdmain(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:


        await call.message.edit_text(
        text=textstore , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help9)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data.startswith('help_btn5'))
async def capasldpalsdallback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
        text=textstore , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified
@dp.callback_query(lambda c: c.data.startswith('9help_btn6'))
async def callapsdlasdlback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:


        await call.message.edit_text(
        text=clanss , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help9)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified
@dp.callback_query(lambda c: c.data.startswith('help_btn6'))
async def callback_mpaspdoasoain(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
        text=clanss , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified


@dp.callback_query(lambda c: c.data.startswith('help_btn7'))
async def caakodaklspdqlqsqllback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
        text=f'''
<b>🌳 Золотое дерево</b>

🎩 Золотое дерево – растущее богатство, сила процветания в каждом листе, ветке.

🌱 Увеличение дерева <pre>Растить дерево</pre>

📜 Информация о вашем дереве <pre>Мое дерево</pre> 

👑 Статистика чата <pre>Топ чата</pre> 

🍀 Официальная статистика  <pre>Стата дерево</pre> 

🍁 Тряска дерева <pre>Трясти дерево</pre> 

💸 Посади семя золота, чтобы собрать урожай богатства.
    ''' , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help)


    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data.startswith('help_btn8'))
async def calakdoaksdaslback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
        text=f'''
<b>🏡 Имущество</b>

🎩 Покупка домов <pre>Дома / Купить дом</pre>

🔑 Мой дом, моя крепость <pre>Мой дом</pre>

💸 Продажа дома <pre>Продать дом</pre>

👑 Пополнение хранилища <pre>Положить [сумма]</pre>

✨ Снятие с хранилища <pre>Снять [сумма]</pre>

🎩 Пополнение ктк хранилища <pre>Положить ктк [сумма]</pre>

📯 Снятие ктк с хранилища <pre>Снять ктк [сумма]</pre>

🚙 Покупка машин <pre>Купить машину</pre>

🚛 Гараж <pre>Мои машины</pre>

🛺 Продажа машины <pre>Продать машину</pre>

🚁 Покупка вертолета <pre>Купить вертолет</pre>

🪁 Ангар вертолетов <pre>Мой вертолет</pre>

💲 Продажа вертолета <pre>Продать вертолет</pre>


🏠 Имущество - наш кусочек мира, наполненный заботой и уютом
    ''' , parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help)

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data.startswith('help_btn9'))
async def cadaspdlasaallback_main(call: types.CallbackQuery):

    user_id = call.from_user.id
    message_id = call.message.message_id

    chat_type = call.message.chat.type



    randommessagehelp1 = random.choice(randommessagehelp)

    try:
        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        await call.message.edit_text(
        text=f'''
<b>🧑🏼‍🌾 Фермерство</b>

🧑🏼‍🌾 Огород - маленький мир, где растет урожай и цветет радость.

🌱 Создание огорода <pre>Создать огород</pre>

🪴 Информация о огороде <pre>Мой огород</pre>

🍃 Удаление культуры <pre>Выкопать культуру</pre>

🌱 Для выращивания культур, сначала нужно купить в магазине семена растений. После этого необходимо использовать сажанец из инвентаря и начать растить культуру до тех пор пока она не вырастет. Когда овощи или фрукты будут у вас в инвентаре, их можно продать в магазине и заработать куты.


🏡 <b>Чтобы создать свой собственный огород, нужен дом, где можно вырастить растения. </b>
    ''', parse_mode="HTML" , disable_web_page_preview=True , reply_markup=btn_help)

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("🥹 Вы уже находитесь в этой вкладке" , show_alert=True)
        pass  # Игнорируем ошибку MessageNotModified

@dp.callback_query(lambda c: c.data.startswith('help_deletehelp'))
async def calasdspaldasqwsqflback_top(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id

        chat_type = call.message.chat.type


        randommessagehelp1 = random.choice(randommessagehelp)

        if not _help_owner_guard(user_id, message_id):
            await _help_reject_intruder(call)
            return

        print('124')
        await call.answer("Сообщение удалено")
        await call.message.delete()


    except Exception as e:
        print(f"Произошла ошибка при обработке запроса333: {e}")


@dp.callback_query(lambda c: c.data.startswith('help_store99'))
async def calisackascvaslback_top(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id

        chat_type = call.message.chat.type



        randommessagehelp1 = random.choice(randommessagehelp)

        if chat_type != 'private':  # Проверка выполняется только если сообщение не в приватном чате
            if user_id not in user_message_helpgame or user_message_helpgame [ user_id ] != message_id:
                await call.answer(randommessagehelp1)
                return


        await call.answer("Сообщение удалено")
        await call.message.delete()


    except Exception as e:
        print(f"Произошла ошибка при обработке запроса5: {e}")

@dp.callback_query(lambda c: c.data.startswith('help_store10'))
async def cahfduascniamwwallback_top(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id

        chat_type = call.message.chat.type



        randommessagehelp1 = random.choice(randommessagehelp)

        if chat_type != 'private':  # Проверка выполняется только если сообщение не в приватном чате
            if user_id not in user_message_store or user_message_store [ user_id ] != message_id:
                await call.answer(randommessagehelp1)
                return

        print('124')
        await call.answer("Сообщение удалено")
        await call.message.delete()


    except Exception as e:
        print(f"Произошла ошибка при обработке запроса7: {e}")


@dp.callback_query(lambda c: c.data.startswith('textglobhelp'))
async def callback_tadfhadj9fwop(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id

        chat_type = call.message.chat.type


        randommessagehelp1 = random.choice(randommessagehelp)

        if chat_type != 'private':  # Проверка выполняется только если сообщение не в приватном чате
            if user_id not in user_message_textglobhelp or user_message_textglobhelp [ user_id ] != message_id:
                await call.answer(randommessagehelp1)
                return

        print('124')
        await call.answer("Сообщение удалено")
        await call.message.delete()


    except Exception as e:
        print(f"Произошла ошибка при обработке запроса8: {e}")


@dp.callback_query(lambda c: c.data.startswith('gamehelp'))
async def callbacqwdjqsoqkqzxcvk_top(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id

        chat_type = call.message.chat.type



        randommessagehelp1 = random.choice(randommessagehelp)

        if chat_type != 'private':  # Проверка выполняется только если сообщение не в приватном чате
            if user_id not in user_message_gamehelp or user_message_gamehelp [ user_id ] != message_id:
                await call.answer(randommessagehelp1)
                return

        print('124')
        await call.answer("Сообщение удалено")
        await call.message.delete()


    except Exception as e:
        print(f"Произошла ошибка при обработке запроса9: {e}")


@dp.callback_query(lambda c: c.data.startswith('ffunc'))
async def caakdoakscijllback_top(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id

        chat_type = call.message.chat.type



        randommessagehelp1 = random.choice(randommessagehelp)

        if chat_type != 'private':  # Проверка выполняется только если сообщение не в приватном чате
            if user_id not in user_message_ffunc or user_message_ffunc [ user_id ] != message_id:
                await call.answer(randommessagehelp1)
                return

        print('124')
        await call.answer("Сообщение удалено")
        await call.message.delete()


    except Exception as e:
        print(f"Произошла ошибка при обработке запроса10: {e}")


@dp.callback_query(lambda c: c.data.startswith('brak'))
async def akdfadfkoasdmccallback_top(call: types.CallbackQuery):

    try:
        user_id = call.from_user.id
        message_id = call.message.message_id

        chat_type = call.message.chat.type


        randommessagehelp1 = random.choice(randommessagehelp)

        if chat_type != 'private':  # Проверка выполняется только если сообщение не в приватном чате
            if user_id not in user_message_brak or user_message_brak [ user_id ] != message_id:
                await call.answer(randommessagehelp1)
                return

        print('124')
        await call.answer("Сообщение удалено")
        await call.message.delete()


    except Exception as e:
        print(f"Произошла ошибка при обработке запроса11: {e}")


