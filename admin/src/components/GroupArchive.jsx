import { useMemo, useState } from 'react'
import TgPhoto from './TgPhoto'
import { watchLevel, watchLine } from '../lib/shiftDesk'

const LOOK = {
  ban: { label: 'Бан', color: '#ef4444' },
  unban: { label: 'Разбан', color: '#22c55e' },
  mute: { label: 'Мут', color: '#f97316' },
  unmute: { label: 'Размут', color: '#2dd4bf' },
  kick: { label: 'Кик', color: '#a855f7' },
  warn: { label: 'Варн', color: '#eab308' },
  unwarn: { label: 'Разварн', color: '#84cc16' },
}

const FAMILY = {
  mute: ['mute', 'unmute'],
  ban: ['ban', 'unban'],
  kick: ['kick'],
  warn: ['warn', 'unwarn'],
}

const FILTERS = [
  { id: 'all', label: 'Все' },
  { id: 'mute', label: 'Муты' },
  { id: 'ban', label: 'Баны' },
  { id: 'kick', label: 'Кики' },
  { id: 'warn', label: 'Варны' },
  { id: 'repeat', label: 'Повторные' },
]

function when(iso) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function lookFor(action) {
  const key = String(action || '').toLowerCase()
  return LOOK[key] || { label: key || 'Запись', color: '#f4f4f4' }
}

export default function GroupArchive({ rows, repeats = new Map(), watch, onPunish }) {
  const [filter, setFilter] = useState('all')
  const [openId, setOpenId] = useState(null)
  const items = useMemo(() => {
    const list = rows || []
    if (filter === 'all') return list
    if (filter === 'repeat') {
      return list.filter((row) => (repeats.get(Number(row.target_user_id)) || 0) >= 2)
    }
    return list.filter((row) => (FAMILY[filter] || []).includes(String(row.action || '').toLowerCase()))
  }, [rows, filter, repeats])

  return (
    <div>
      <section className="watch-list">
        <h3 className="realm-h">Близко к бану</h3>
        <p className="realm-copy">Шкала этого чата: 3 предупреждения, и система банит сама. Жалобы игроков друг на друга отдельно не копятся — смотрите варны.</p>
        {watch === undefined && <p className="realm-copy">Смотрим предупреждения…</p>}
        {watch === null && <p className="realm-copy">Список варнов сейчас не открылся.</p>}
        {Array.isArray(watch) && watch.length === 0 && <p className="realm-copy">Никого с активным предупреждением в этом чате нет.</p>}
        <ul className="realm-list">
          {(watch || []).map((person) => {
            const level = watchLevel(person.warns)
            const times = repeats.get(Number(person.userId)) || 0
            return (
              <li key={person.userId} className={`watch-person is-${level || 'watch'}`}>
                <div className="realm-row">
                  <strong>{person.name || `#${person.userId}`}</strong>
                  <span>{person.warns} из 3</span>
                </div>
                <p className="realm-copy">{watchLine(level, person.warns)}{times >= 2 ? ` В последних записях архива ещё ${times}.` : ''}</p>
                {onPunish && (
                  <button type="button" className="realm-back" onClick={() => onPunish(String(person.userId))}>
                    Наказать
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      </section>
      <div className="realm-actions" aria-label="Какие наказания показать">
        {FILTERS.map((item) => (
          <button key={item.id} type="button" className={filter === item.id ? 'is-on' : ''} onClick={() => setFilter(item.id)}>
            {item.label}
          </button>
        ))}
      </div>
      {items.length === 0 && <p className="realm-copy">В этом чате таких записей пока нет.</p>}
      <div className="g-arc-grid">
        {items.map((row, index) => {
          const look = lookFor(row.action)
          const id = row.id ?? `${row.at || index}`
          const open = openId === id
          const player = row.targetName || (row.target_user_id ? `#${row.target_user_id}` : '—')
          return (
            <article
              key={id}
              className={open ? 'g-arc-card is-open' : 'g-arc-card'}
              style={{ '--cc': look.color }}
            >
              <button type="button" className="g-arc-hit" onClick={() => setOpenId(open ? null : id)} aria-expanded={open}>
                <span className="g-arc-badge" style={{ background: look.color }}>{look.label}</span>
                <time>{when(row.at || row.created_at)}</time>
                <span className="g-arc-who">
                  <span>
                    <small>Выдал</small>
                    <strong>{row.admin || '—'}</strong>
                  </span>
                  <span aria-hidden="true">→</span>
                  <span>
                    <small>В чате</small>
                    <strong>{player}</strong>
                  </span>
                </span>
                <span className={row.reason ? 'g-arc-reason' : 'g-arc-reason is-empty'}>
                  {row.reason || 'Причина не указана'}
                </span>
                <span className="g-arc-tags">
                  {(repeats.get(Number(row.target_user_id)) || 0) >= 2 && (
                    <span>В архиве {repeats.get(Number(row.target_user_id))} раз</span>
                  )}
                  {row.hasProof && <span>Есть фото</span>}
                  <span>{open ? 'Скрыть' : 'Открыть'}</span>
                </span>
              </button>
              {open && onPunish && row.target_user_id && (
                <button type="button" className="realm-back" onClick={() => onPunish(String(row.target_user_id))}>
                  Снова в форму наказания
                </button>
              )}
              {open && row.proofMediaId && <TgPhoto fileId={row.proofMediaId} className="g-arc-proof" />}
              {open && !row.proofMediaId && <p className="realm-copy">Фото доказательства нет.</p>}
              <span className="g-arc-stripe" style={{ background: look.color }} />
            </article>
          )
        })}
      </div>
    </div>
  )
}
