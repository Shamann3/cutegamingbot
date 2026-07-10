/** Коды ошибок - синхронизированы с server/error_codes.py */

const ERROR_CODES = {
  ERR_AUTH_401: 'Нет авторизации',
  ERR_AUTH_403: 'Доступ запрещён',
  ERR_AUTH_HASH: 'Неверная подпись Telegram',
  ERR_AUTH_NO_BOT: 'BOT_TOKEN не настроен',
  ERR_AUTH_NO_USER: 'Нет user в initData',
  ERR_AUTH_EXPIRED: 'Сессия истекла',
  ERR_NET_TIMEOUT: 'Таймаут API',
  ERR_NET_OFFLINE: 'Нет связи с API',
  ERR_NET_ABORT: 'Запрос прерван',
  ERR_API_400: 'Некорректный запрос',
  ERR_API_422: 'Неверное тело запроса',
  ERR_API_429: 'Слишком много запросов',
  ERR_API_500: 'Внутренняя ошибка сервера',
  ERR_API_503: 'Технические работы',
  ERR_API_UNKNOWN: 'Неизвестный ответ API',
  ERR_FARM_STATE: 'Не загрузилась ферма',
  ERR_FARM_PLANT: 'Ошибка посадки',
  ERR_FARM_WATER: 'Ошибка полива',
  ERR_FARM_HARVEST: 'Ошибка сбора урожая',
  ERR_FARM_CLEAR: 'Ошибка очистки грядки',
  ERR_FARM_BUY_PLOT: 'Ошибка покупки грядки',
  ERR_FARM_POLL: 'Фоновый опрос фермы',
  ERR_SHOP_CATALOG: 'Не загрузился каталог',
  ERR_SHOP_BUY: 'Ошибка покупки',
  ERR_SHOP_STOCK: 'Товар закончился',
  ERR_SHOP_BALANCE: 'Недостаточно КУТ',
  ERR_SHOP_POLL: 'Фоновый опрос биржи',
  ERR_DB_CONNECT: 'Нет подключения к PostgreSQL',
  ERR_DB_QUERY: 'Ошибка SQL-запроса',
  ERR_DB_TX: 'Ошибка транзакции',
  ERR_UI_CRASH: 'Падение React',
  ERR_UI_STATUS: 'Статус приложения',
  ERR_SEC_HASH_FAIL: 'Подделка initData',
  ERR_SEC_FAKE_INIT: 'Фейковый initData',
  ERR_SEC_EXPIRED_REPLAY: 'Просроченный initData',
  ERR_SEC_NO_AUTH: 'Запрос без авторизации',
  ERR_SEC_PROD_BYPASS: 'Обход prod-авторизации',
  ERR_SEC_DEV_SPOOF: 'Dev-auth с чужого IP',
  ERR_SEC_DEV_INVALID: 'Неверный dev user id',
  ERR_SEC_BODY_UID: 'user_id в теле запроса',
  ERR_SEC_BODY_BALANCE: 'Подмена баланса в теле',
  ERR_SEC_EXTRA_FIELDS: 'Лишние поля в запросе',
  ERR_SEC_RATE_ABUSE: 'Флуд запросами',
  ERR_SEC_SCAN_PATH: 'Сканирование путей',
  ERR_SEC_SQL_PROBE: 'SQL-инъекция в URL',
  ERR_SEC_SCANNER: 'Подозрительный User-Agent',
  ERR_SEC_INVALID_ITEM: 'Подмена itemId',
  ERR_SEC_REPORT_FLOOD: 'Флуд report-error',
  ERR_AUDIT_TG: 'Audit Telegram',
  ERR_ERR_TG: 'Error Telegram',
  ERR_CFG_STARTUP: 'Предупреждение при старте',
  ERR_UNK: 'Неизвестная ошибка',
}

export function codeForApiError(error, path = '') {
  if (!error) return 'ERR_UNK'
  const code = error.code
  if (code && ERROR_CODES[code]) return code
  if (code === 'auth') return 'ERR_AUTH_401'
  if (code === 'rate_limit') return 'ERR_SEC_RATE_ABUSE'
  if (code === 'maintenance') return 'ERR_API_503'
  if (code === 'timeout') return 'ERR_NET_TIMEOUT'
  if (code === 'network') return 'ERR_NET_OFFLINE'
  if (path.includes('/farm/state')) return 'ERR_FARM_STATE'
  if (path.includes('/shop/catalog')) return 'ERR_SHOP_CATALOG'
  if (path.includes('/shop/buy')) return 'ERR_SHOP_BUY'
  if (error.status === 401) return 'ERR_AUTH_401'
  if (error.status === 429) return 'ERR_SEC_RATE_ABUSE'
  if (error.status === 503) return 'ERR_API_503'
  if (error.status >= 500) return 'ERR_API_500'
  if (error.status === 400) return 'ERR_API_400'
  return 'ERR_API_UNKNOWN'
}
