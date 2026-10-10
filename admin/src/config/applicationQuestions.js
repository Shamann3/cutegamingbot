// Вопросы анкеты кандидата. Легко править: добавляй/меняй объекты.
// id ключ ответа (уходит в answers на бэкенд), type — 'text' (input) | 'textarea'.

export const APPLICATION_QUESTIONS = [
  {
    id: 'experience',
    label: 'Чем занимаешься? Опыт модерации',
    type: 'textarea',
    placeholder: 'От 50 до 2000 символов. Чем вы полезны команде.',
    required: true,
  },
  {
    id: 'time',
    label: 'Сколько времени готов уделять?',
    type: 'text',
    placeholder: 'Например: 3-4 часа в день',
    required: true,
  },
  {
    id: 'age_tz',
    label: 'Возраст / часовой пояс',
    type: 'text',
    placeholder: 'Например: 19, UTC+2',
    required: true,
  },
  {
    id: 'motivation',
    label: 'Почему хочешь к нам?',
    type: 'textarea',
    placeholder: 'От 50 до 2000 символов, если пишете',
    required: false,
  },
]

// Способы получения зарплаты для AdminSelect.
export const PAYOUT_OPTIONS = [
  { value: 'kut', label: 'кут' },
  { value: 'stars', label: 'Telegram Stars' },
  { value: 'crypto', label: 'Крипта' },
  { value: 'card', label: 'Карта / СБП' },
  { value: 'other', label: 'Другое' },
]
