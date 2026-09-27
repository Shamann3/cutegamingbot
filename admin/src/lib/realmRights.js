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

export const REALM_RIGHTS = [...PAGE_RIGHTS, ...PUNISH_RIGHTS]
