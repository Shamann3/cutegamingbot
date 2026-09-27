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

/** Права администратора чата Telegram (без передачи владения). */
export const TELEGRAM_ADMIN_RIGHTS = [
  { id: 'can_change_info', label: 'Изменять профиль', hint: 'Название, фото и описание чата' },
  { id: 'can_delete_messages', label: 'Удалять сообщения', hint: 'Удаление чужих сообщений в чате' },
  { id: 'can_restrict_members', label: 'Ограничивать участников', hint: 'Мут, бан и ограничения в чате' },
  { id: 'can_invite_users', label: 'Приглашать', hint: 'Ссылки-приглашения и добавление людей' },
  { id: 'can_pin_messages', label: 'Закреплять', hint: 'Закреплённые сообщения' },
  { id: 'can_manage_topics', label: 'Темы', hint: 'Управление темами форума' },
  { id: 'can_manage_video_chats', label: 'Видеочаты', hint: 'Управление видеочатами' },
  { id: 'can_post_messages', label: 'Публиковать', hint: 'Посты в канале (для каналов)' },
  { id: 'can_edit_messages', label: 'Редактировать посты', hint: 'Правка чужих постов в канале' },
]

export const REALM_RIGHTS = [...PAGE_RIGHTS, ...PUNISH_RIGHTS, ...TELEGRAM_ADMIN_RIGHTS]
