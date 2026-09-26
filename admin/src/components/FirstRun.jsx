import { useState } from 'react'

export const STAFF_STEPS = [
  {
    title: 'Открыто только ваше',
    body: 'В меню слева — разделы вашей должности. Чего нет в списке, того у вас нет. Искать по всей панели не нужно.',
  },
  {
    title: 'Поиск в шапке',
    body: 'Начните печатать название раздела. Стрелки и Enter переносят сразу туда.',
  },
  {
    title: 'С чего начать',
    body: 'Чаще всего нужны «Игроки» и «Архив». Остальные разделы можно не открывать, пока они не понадобятся.',
  },
  {
    title: 'Двери',
    body: 'Кнопка «Двери» внизу меню возвращает к выбору панели. Из аккаунта это не выходит.',
  },
]

export const GROUP_STEPS = [
  {
    title: 'Цифра на обзоре',
    body: 'Пока группа не выбрана — сколько чатов в базе. В открытом чате — сообщения за 30 дней.',
  },
  {
    title: 'Свой чат',
    body: 'Нажмите группу в списке. Люди, архив и действия относятся только к ней.',
  },
  {
    title: 'Действие',
    body: 'Мут, бан, кик и варн пишутся в архив этого чата. Нужны id человека и причина.',
  },
  {
    title: 'Ещё',
    body: 'Там правила CuteRules и возврат к дверям.',
  },
]

export default function FirstRun({ storageKey, steps, onDone }) {
  const [index, setIndex] = useState(0)
  const step = steps[index]
  const last = index >= steps.length - 1

  const finish = () => {
    try {
      localStorage.setItem(storageKey, '1')
    } catch {
      /* ignore */
    }
    onDone?.()
  }

  return (
    <div className="firstrun" role="dialog" aria-modal="true" aria-labelledby="firstrun-title">
      <div className="firstrun-sheet">
        <p className="firstrun-kicker">
          {index + 1} / {steps.length}
        </p>
        <h2 id="firstrun-title" className="firstrun-title">{step.title}</h2>
        <p className="firstrun-body">{step.body}</p>
        <div className="firstrun-dots" aria-hidden="true">
          {steps.map((_, i) => (
            <span key={i} className={i === index ? 'is-on' : ''} />
          ))}
        </div>
        <div className="firstrun-actions">
          <button type="button" className="firstrun-skip" onClick={finish}>
            Пропустить
          </button>
          <button type="button" className="firstrun-next" onClick={last ? finish : () => setIndex((n) => n + 1)}>
            {last ? 'Понятно' : 'Дальше'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function firstRunSeen(storageKey) {
  try {
    return localStorage.getItem(storageKey) === '1'
  } catch {
    return true
  }
}
