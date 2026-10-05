export const PAGE_RIGHTS = [
  { id: 'view_members', label: 'Кто пишет', hint: 'Список людей на «Активности». Саму вкладку включает блок выше.' },
  { id: 'view_archive', label: 'Карточки', hint: 'Наказания внутри архива. Саму вкладку включает блок выше. Наказать можно, только если ниже включено само наказание.' },
  { id: 'view_analytics', label: 'Цифры', hint: 'Суммы за день, месяц и год на «Активности». Список людей может остаться закрытым.' },
  { id: 'manage_positions', label: 'Младшие должности', hint: 'Можно менять должности строго младше своей. Вкладку «Права» включает блок выше. Новую должность создаёт только создатель проекта.' },
]

export const PUNISH_RIGHTS = [
  { id: 'punish_mute', label: 'Мут', hint: 'Только этот чат. Затыкает человека младше и снимает этот мут. Другие группы не трогает.' },
  { id: 'punish_ban', label: 'Бан в чате', hint: 'Только этот чат. Бан и разбан в этой группе. На весь проект не действует: для этого есть «Банфулл».' },
  { id: 'punish_kick', label: 'Кик', hint: 'Только этот чат. Убирает человека из группы. Вернуть его этим правом нельзя.' },
  { id: 'punish_warn', label: 'Варн', hint: 'Только этот чат. Пишет предупреждение. Из чата человека не удаляет.' },
  { id: 'punish_voice', label: 'Голос', hint: 'Только этот чат. Запрещает голосовые и кружки. Текст остаётся.' },
]

/** Права Telegram в чате: админские + отправка контента. Без передачи владения. */
export const TELEGRAM_ADMIN_RIGHTS = [
  { id: 'can_manage_chat', label: 'Управлять чатом', hint: 'Журнал чата и список участников. Само по себе не банит и не удаляет сообщения. У спам-блока этот флаг включён только в Telegram, чтобы человек мог писать.' },
  { id: 'can_change_info', label: 'Изменять профиль', hint: 'Можно менять название, фото и описание чата.' },
  { id: 'can_delete_messages', label: 'Удалять сообщения', hint: 'Можно удалять чужие сообщения в этом чате.' },
  { id: 'can_restrict_members', label: 'Ограничивать участников', hint: 'Мут и бан средствами Telegram. В панели наказание всё равно требует отдельного переключателя выше.' },
  { id: 'can_invite_users', label: 'Приглашать', hint: 'Ссылки-приглашения и добавление людей' },
  { id: 'can_pin_messages', label: 'Закреплять', hint: 'Закреплённые сообщения' },
  { id: 'can_manage_topics', label: 'Темы', hint: 'Управление темами форума' },
  { id: 'can_manage_video_chats', label: 'Видеочаты', hint: 'Управление видеочатами' },
  { id: 'can_promote_members', label: 'Назначать админов', hint: 'Выдавать права младшим администраторам' },
  { id: 'can_post_messages', label: 'Публиковать', hint: 'Посты в канале (для каналов)' },
  { id: 'can_edit_messages', label: 'Редактировать посты', hint: 'Правка чужих постов в канале' },
  { id: 'can_send_messages', label: 'Писать сообщения', hint: 'Текстовые сообщения в чате' },
  { id: 'can_send_photos', label: 'Фото', hint: 'Отправка фотографий' },
  { id: 'can_send_videos', label: 'Видео', hint: 'Отправка видео' },
  { id: 'can_send_audios', label: 'Аудио', hint: 'Отправка аудиофайлов' },
  { id: 'can_send_documents', label: 'Документы', hint: 'Отправка файлов' },
  { id: 'can_send_voice_notes', label: 'Голосовые', hint: 'Голосовые сообщения' },
  { id: 'can_send_video_notes', label: 'Кружки', hint: 'Видеосообщения-кружки' },
  { id: 'can_send_polls', label: 'Опросы', hint: 'Создание опросов' },
  { id: 'can_send_other_messages', label: 'Стикеры и GIF', hint: 'Стикеры, GIF и игры' },
  { id: 'can_add_web_page_previews', label: 'Превью ссылок', hint: 'Превью веб-страниц в сообщениях' },
]

/** Наказания шире одного чата. Сами не включаются от бана или мута в группе. */
export const PROJECT_RIGHTS = [
  { id: 'muteall', label: 'Муталл', hint: 'Все официальные группы. Мут в каждой из них. Мут одного чата это не включает.' },
  { id: 'kickall', label: 'Кикалл', hint: 'Все официальные группы. Кик из каждой. Кик из одного чата это не включает.' },
  { id: 'warnall', label: 'Варналл', hint: 'Все официальные группы. Предупреждение в каждой. Варн одного чата это не включает.' },
  { id: 'banall', label: 'Баналл', hint: 'Все официальные группы. Бан в каждой. Это ещё не бан всего проекта.' },
  { id: 'warnfull', label: 'Варнфулл', hint: 'Весь проект. Предупреждение не только в группах. Варн чата это не включает.' },
  { id: 'banfull', label: 'Банфулл', hint: 'Весь проект. Бан везде. Снять его из карточки человека нельзя. Бан чата это не включает.' },
]

export function grantedWide(catalog, rights) {
  const have = rights instanceof Set ? rights : new Set(rights || [])
  return (catalog || []).filter((item) => item?.id && have.has(item.id))
}

export const REALM_RIGHTS = [...PAGE_RIGHTS, ...PUNISH_RIGHTS, ...TELEGRAM_ADMIN_RIGHTS, ...PROJECT_RIGHTS]
