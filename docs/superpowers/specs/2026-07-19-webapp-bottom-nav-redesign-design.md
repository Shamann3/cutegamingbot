# Редизайн нижней навигации веб-приложения

Дата: 2026-07-19
Файлы: `src/App.jsx`, `src/components/TabBar.jsx`, `src/components/MoreMenu.jsx` (удаляется), `src/components/TabIcons.jsx`, `src/components/FarmHeader.jsx`, `src/components/ProfileModule.jsx`, новый `src/components/TradeModule.jsx`, новый `src/components/GiveawaysModule.jsx`, `src/hooks/useSwipeTabs.js`, `src/lib/telegram.js`, `src/styles/tabThemes.css`, `src/index.css`

## Задача

Сейчас нижняя панель — 3 вкладки (Ферма, Инвентарь, Магазин) + кнопка «Ещё» со спрятанным подменю (Крафты, Задания, Биржа, Профиль, Настройки). Биржа и Задания — ключевые фичи ретеншена и монетизации — похоронены за двумя тапами.

Новая нижняя панель, 5 позиций:

```
Ферма | Торговля | 🎁 Розыгрыши (по центру, крупнее, приподнята) | Задания | Профиль
```

«Ещё» и `MoreMenu.jsx` убираются полностью — некуда там больше ничего прятать.

## Что переезжает и куда

| Было | Стало |
|---|---|
| Магазин (таб `shop`, `ExchangeModule`) | сегмент «Магазин» в новом `TradeModule` (таб `trade`) |
| Биржа (таб `market`, `MarketplaceModule`) | сегмент «Биржа» + «Продать» в `TradeModule` |
| Инвентарь (таб `inventory`) | иконка-рюкзак в `FarmHeader`; `InventoryModule` не меняется, просто новая точка входа |
| Крафты (таб `craft`, из «Ещё») | иконка-верстак в `FarmHeader`; `CraftModule` не меняется |
| Настройки (таб `settings`, из «Ещё») | иконка-шестерёнка в шапке `ProfileModule`; `SettingsModule` не меняется |
| Задания (из «Ещё») | таб первого уровня, без изменений в `QuestsModule` |
| Профиль (из «Ещё») | таб первого уровня, без изменений в `ProfileModule`, кроме новой иконки настроек |
| — | **новый** таб «Розыгрыши» (`giveaways`), только заглушка |

Таб `chests` (гача-сундуки за звёзды) уже существует в `App.jsx`, но нигде не подключён к навигации — этим заходом не занимаемся, оставляем как есть (отдельная задача при необходимости).

## Центральная сложность: слияние Магазина и Биржи без поломки deep-link'ов

`ExchangeModule` (Магазин, покупка семян за КУТ) и `MarketplaceModule` (Биржа, лоты игроков) — независимые модули, оба использующие общие куски (`ShopSearch`, `ShopToolbar`, `ShopNavigation`, `ShopSkeletonGrid`, `KutBalance`, `DonateModal`, `useContextualDonate`). У `MarketplaceModule` уже есть кнопка «Продать из рюкзака» → `MarketSellModal`, читающая `sellableItems` — то есть флоу продажи из инвентаря уже существует, его не изобретаем заново.

Слияние — новый `TradeModule.jsx`, единый хедер («Торговля» + общий `KutBalance` + общий `DonateModal`), внутри плоский переключатель из 3 сегментов:

- **Магазин** — сегодняшний контент `ExchangeModule` (каталог семян/предметов за КУТ, покупка), без изменений в логике.
- **Биржа** — сегодняшний контент-браузер `MarketplaceModule` (лоты игроков, покупка), без карточки «Продать» и без модалки продажи.
- **Продать** — карточка «Продать из рюкзака» + `MarketSellModal` (как сегодня) **плюс новый блок «Мои лоты»**: список активных лотов текущего игрока с отменой (переиспользует уже существующие `cancelListing`/`MarketListingModal` из `useMarketplace` — новый рендер, не новая бизнес-логика).

Оба модуля продолжают использовать свои хуки (`useShop`, `useMarketplace`) без изменений — `TradeModule` просто хостит оба и переключает видимость по сегменту (тот же паттерн `isActive`/`hidden`, что уже применяется в `App.jsx` между табами).

### Deep-link совместимость

Сейчас есть два независимых канала, завязанных на строковые id `shop`/`market`:

1. `getStartTab()` в `src/lib/telegram.js` — читает `?startapp=shop` / `?startapp=market` из Telegram `start_param`.
2. Два `window.addEventListener` в `App.jsx` на кастомные события `farm:go-to-shop` / `farm:go-to-market` (диспатчатся из `src/utils/itemPurchaseGuide.js` как fallback/сигнал «предмета не оказалось в открытом окне покупки, но посмотри его на бирже» — несут `{ search, itemId, highlightOnly }`). Оба всегда означают «перейти и подсветить для покупки», сценария «перейти чтобы продать» здесь нет — проверено по `itemPurchaseGuide.js`: `goToMarketSearch`/`farm:go-to-shop`-фоллбэк всегда покупательские.

(Отдельно есть `farm:open-shop-purchase` / `farm:open-market-purchase`, обрабатываемые в `ShopPurchaseGuideLayer`/`MarketPurchaseGuideLayer` — они просто открывают модалку покупки поверх текущего экрана и не зависят от активного таба, кроме одного момента: их колбэки `onNavigateShop`/`onNavigateMarket` в `App.jsx` вызывают `setTab('shop'|'market')`, чтобы после закрытия модалки пользователь оказался на нужном экране. Эти вызовы переезжают на `setTab('trade')` + `setTradeSegment(...)` вместе с остальными.)

Оба канала (`getStartTab` и `go-to-shop/market`) должны продолжать работать. План:

- `AppShell` держит `tab` (теперь принимает `'trade'` вместо `'shop'`/`'market'`) и новый `tradeSegment` (`'shop' | 'market' | 'sell'`).
- `getStartTab()`: `VALID_TABS` дополняется `trade`; значения `shop`/`market` остаются валидными как **алиасы** — маппятся в `{ tab: 'trade', tradeSegment: 'shop' | 'market' }` на стороне `App.jsx` (сам `telegram.js` просто возвращает исходную строку, разбор алиасов — в `AppWithOnboarding`/`AppShell`, чтобы не размазывать словарь по файлам).
- Обработчики `farm:go-to-shop` / `farm:go-to-market` в `App.jsx`: вместо `setTab('shop')`/`setTab('market')` делают `setTab('trade')` + `setTradeSegment('shop'|'market')`, остальная логика (search/itemId/highlightOnly передаются в `TradeModule` как проп, привязанный к нужному сегменту) не меняется по сути, только имя стейта.
- `handleGuideNavigateShop`/`handleGuideNavigateMarket` (колбэки `onNavigateShop`/`onNavigateMarket` из guide-layer'ов) аналогично переключаются на `setTab('trade')` + `setTradeSegment(...)`.

### Свайпы между табами

`src/hooks/useSwipeTabs.js` — `TAB_ORDER` меняется с `['farm', 'inventory', 'craft', 'quests', 'shop', 'market', 'settings']` на `['farm', 'trade', 'giveaways', 'quests', 'profile']`. Инвентарь/крафт/настройки больше не участвуют в горизонтальном свайпе (они не в главном ряду) — это ожидаемо, попадают туда только через свои иконки-входы.

## FarmHeader: новые точки входа

`src/components/FarmHeader.jsx` сейчас — просто герб и заголовок, без интерактивных элементов. Добавляются две маленькие иконки-кнопки (рюкзак → `setTab('inventory')`, верстак → `setTab('craft')`), стилистически как компактные круглые кнопки в углу шапки (не полноценные табы — без лейблов, только иконка + `aria-label`). Иконки уже есть в `TabIcons.jsx` (`Inventory`, `Craft`), новых svg рисовать не нужно.

## ProfileModule: точка входа в настройки

`src/components/ProfileModule.jsx` — в шапку модуля добавляется иконка-шестерёнка (уже есть `Settings` в `TabIcons.jsx`), по клику `setTab('settings')`.

## Розыгрыши — только заглушка

Новый `src/components/GiveawaysModule.jsx`: тот же shell-паттерн, что у остальных модулей (`FarmBackground` + `TabAtmosphere variant="giveaways"` + `VineFrame`), внутри — иконка 🎁 и текст «Скоро». Никакой загрузки данных, никакого таймера/бейджа/API. Проп `isActive` как у соседей, для консистентности с остальными табами (пауза анимаций/музыки и т.д. по общему паттерну).

Новый `tab-theme-giveaways` блок CSS-переменных и `tab-atmosphere--giveaways` в `src/styles/tabThemes.css` — по образцу существующих (`tab-theme-quests` как ближайший по духу акцент, тёплый/золотой, но свой отдельный оттенок, чтобы визуально не путался с Магазином/Сундуками).

Новая иконка `Gift` в `TabIcons.jsx` (подарочная коробка, тот же stroke-стиль, что у остальных).

## Визуальный акцент центральной кнопки

`src/index.css`: `.app-tab-bar-inner` — `grid-template-columns: repeat(4, ...)` → `repeat(5, ...)`. Кнопка `giveaways` получает модификатор-класс (например `app-tab-btn-giveaways`): визуально крупнее (шире/выше соседей), приподнята над рядом (`transform: translateY(-Npx)` + свой бэкграунд-круг), с **постоянным** мягким свечением акцентного цвета (не только в активном состоянии, как у остальных вкладок) — чтобы читалось как магнит/витрина, а не рядовая вкладка. Никакой логики таймера — чисто CSS-акцент.

## Порядок реализации (укрупнённо)

1. `TabIcons.jsx` — добавить `Gift`, добавить акцент `giveaways` в `TAB_ACCENTS`.
2. `tabThemes.css` — добавить тему/атмосферу `giveaways`, обновить блок «Нижняя панель вкладок» под новый набор data-active-tab значений (`trade`, `giveaways` вместо `shop`/`market`/старых секретных табов в баре).
3. `GiveawaysModule.jsx` — новый файл, заглушка.
4. `TradeModule.jsx` — новый файл: хостит существующий JSX/логику `ExchangeModule` и `MarketplaceModule` под общим хедером и сегмент-переключателем; `MarketplaceModule`/`ExchangeModule` как файлы могут остаться (переиспользуются как внутренние вью) или быть инлайнены — решается в момент реализации по факту связности кода.
5. `FarmHeader.jsx` — иконки инвентаря/крафта.
6. `ProfileModule.jsx` — иконка настроек.
7. `TabBar.jsx` — новый список из 5 табов, убрать кнопку «Ещё» и рендер `MoreMenu`.
8. Удалить `MoreMenu.jsx`.
9. `App.jsx` — заменить блоки `shop`/`market` на единый `trade` (+`tradeSegment`), добавить блок `giveaways`, поправить обработчики `farm:go-to-shop/market` и `getStartTab()`-алиасы.
10. `useSwipeTabs.js` — новый `TAB_ORDER`.
11. `lib/telegram.js` — `VALID_TABS` дополнить `trade`, оставить `shop`/`market` как принимаемые (для алиас-маппинга в App.jsx).

## Вне объёма (явно)

- Сегмент «Графики» (история цен) — нет данных ни в БД, ни в API, требует отдельной бэкенд-фичи (таблица снимков цен + крон). Не делаем.
- Реальная логика розыгрышей: таймер, бейдж с обратным отсчётом, механика розыгрыша, бэкенд. Не делаем — только вкладка-заглушка.
- Тап по грядке (`PlotCard.jsx`) не открывает инвентарь — такого решения не было, не делаем.
- Таб `chests` не подключается к навигации в рамках этой задачи.
