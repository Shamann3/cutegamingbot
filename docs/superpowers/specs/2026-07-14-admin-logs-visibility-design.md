# Admin panel Логи — Фаза 1: видимость Audit/Сбои + дедуп

## Проблема

Вкладки "Логи" в админке (`admin/src/pages/sections/LogsSection.jsx`) — Audit, Security,
Сбои — читают таблицы `audit_events` и `system_logs`. Но запись в БД для этих таблиц
завязана на те же флаги (`AUDIT_LOG_ENABLED`, `ERROR_REPORT_ENABLED`), что и отправка
уведомлений в Telegram-чат. Оба флага в `.env` выключены (`false`), поэтому:

- `server/audit_log.py::record_balance_event` обрывается до записи в `audit_events`
  для всех игровых событий (покупки, крафт, маркет, квесты) — Audit показывает
  почти только действия админов.
- `server/error_reporter.py::schedule_http_error` обрывается до записи в `system_logs`
  для обычных `HTTPException` (403/422/429 и т.п.) — Сбои показывает только
  необработанные краши.
- `server/app.py` дополнительно дублирует запись в `system_logs` для одной и той же
  500-ошибки (`_server_error` пишет один раз, `http_exception_handler` — второй раз),
  потому что дедуп-проверка сравнивает текст `detail` со строкой, которая совпадает
  только при `PRODUCTION=true`. Деплой сейчас работает с `APP_MODE=test`, так что
  проверка не срабатывает.

## Решение

Разделить "писать в БД" (всегда) и "слать в Telegram" (по флагу) — Telegram-флаги
остаются `false`, спама не будет.

1. **`server/audit_log.py::record_balance_event`** — убрать ранний `return` перед
   записью в `audit_events`; `AUDIT_LOG_ENABLED` продолжает управлять только
   `_notify_telegram(...)`.
2. **`server/error_reporter.py::schedule_http_error`** — убрать ранний `return` перед
   вызовом `report_error(...)`; `report_error` уже сам разделяет персист (всегда) и
   Telegram-доставку (по `ERROR_REPORT_ENABLED`).
3. **`server/app.py`** — заменить сравнение текста `detail == "Внутренняя ошибка
   сервера"` в `http_exception_handler` на явный маркер на самом объекте исключения
   (`_already_reported = True`, выставляется в `_server_error`). Не зависит от
   `PRODUCTION` и текста сообщения.

## Вне рамок этой фазы

- Флаги `AUDIT_LOG_ENABLED` / `ERROR_REPORT_ENABLED` (Telegram) не трогаем.
- Аудит P2P-переводов игрок→игрок (`bot/funcs/give.py`) — фаза 2, отдельный дизайн
  (нужна новая таблица/API, т.к. `cutehistory`/`moneyhistory` пишутся только в
  legacy-боте и не читаются `server/`).
- Тюнинг Security-детекции — фаза 3.

## Проверка

- Тестовая покупка в игре → одна новая строка в Audit.
- Намеренная 4xx (например rate-limit) → одна строка в Security/Сбои.
- Намеренная 500 (не в PRODUCTION) → ровно одна строка в Сбои, не две.
