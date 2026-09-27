export const PAGE_RIGHTS = [
  { id: 'view_members', label: 'Кто пишет', hint: 'Имена и число сообщений на странице «Активность»' },
  { id: 'view_archive', label: 'Архив', hint: 'Карточки наказаний и фото этой группы' },
  { id: 'view_analytics', label: 'Цифры', hint: 'Сообщения за день, месяц и год на той же странице' },
  { id: 'manage_positions', label: 'Права', hint: 'Менять должности младше своей' },
]

export const PUNISH_RIGHTS = [
  { id: 'punish_mute', label: 'Мут', hint: 'Заткнуть в этом чате' },
  { id: 'punish_ban', label: 'Бан в чате', hint: 'Только эта группа, не весь проект' },
  { id: 'punish_kick', label: 'Кик', hint: 'Убрать из этого чата' },
  { id: 'punish_warn', label: 'Варн', hint: 'Предупреждение в этом чате' },
  { id: 'punish_voice', label: 'Голос', hint: 'Запретить голосовые и кружки, текст оставить' },
]

/** Права Telegram в чате: админские + отправка контента. Без передачи владения. */
export const TELEGRAM_ADMIN_RIGHTS = [
  { id: 'can_manage_chat', label: 'Управлять чатом', hint: 'Общее администрирование чата' },
  { id: 'can_change_info', label: 'Изменять профиль', hint: 'Название, фото и описание чата' },
  { id: 'can_delete_messages', label: 'Удалять сообщения', hint: 'Удаление чужих сообщений в чате' },
  { id: 'can_restrict_members', label: 'Ограничивать участников', hint: 'Мут, бан и ограничения в чате' },
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

export const REALM_RIGHTS = [...PAGE_RIGHTS, ...PUNISH_RIGHTS, ...TELEGRAM_ADMIN_RIGHTS]
