import { useState } from 'react'
import { muteClock } from './GroupMuteLock'

function personKey(person) {
  return `${person.chatId || 0}-${person.userId}`
}

function HoldLine({ label, until, reason }) {
  const when = until ? muteClock(until) : ''
  return (
    <p className="seat-hold">
      <b>{label}</b>
      {when ? ` до ${when}` : ''}
      {reason ? `. ${reason}` : ''}
    </p>
  )
}

function PersonCard({ person, positions, busy, onLift, onDismiss, onReissue, renderExtra }) {
  const [open, setOpen] = useState(false)
  const [posId, setPosId] = useState('')
  const [termStart, setTermStart] = useState('')
  const [termEnd, setTermEnd] = useState('')
  const key = personKey(person)
  const chosen = (positions || []).find((item) => String(item.id) === String(posId)) || null
  const spam = chosen?.kind === 'spamblock'
  const posts = (positions || []).filter((item) => Number(item.rank) < 5)
  const held = Boolean(person.mutedUntil || person.banUntil || person.paused || person.warns)

  const reissue = () => {
    if (!chosen || !onReissue) return
    if (spam && !termEnd) return
    onReissue(person, chosen, { termStart, termEnd })
  }

  return (
    <article className={`seat-person${person.paused ? ' is-paused' : ''}${held ? ' is-held' : ''}`}>
      <header className="seat-person-head">
        <strong>{person.name || person.userId}{person.username ? ` · @${String(person.username).replace(/^@/, '')}` : ''}</strong>
        <span>
          {person.position || 'Должность'}
          {person.prefix ? ` · «${person.prefix}»` : ''}
          {Number.isFinite(Number(person.rank)) ? ` · ранг ${person.rank}` : ''}
          {person.termEnd ? ` · срок до ${person.termEnd}` : ''}
          {person.paused ? ' · должность отложена' : ''}
          {person.accessOff ? ' · доступ выключен' : ''}
        </span>
      </header>
      {held && (
        <div className="seat-holds">
          {person.mutedUntil && <HoldLine label="Мут" until={person.mutedUntil} reason={person.muteReason} />}
          {person.banUntil && <HoldLine label="Бан" until={person.banUntil} reason={person.banReason} />}
          {person.paused && (
            <HoldLine
              label="Должность снята на время бана"
              until={person.pauseUntil || person.banUntil}
              reason=""
            />
          )}
          {person.warns > 0 && <p className="seat-hold"><b>Предупреждения</b>{` · ${person.warns}`}</p>}
        </div>
      )}
      <div className="seat-person-actions">
        {person.mutedUntil && onLift && (
          <button type="button" disabled={busy} onClick={() => onLift(person, 'unmute')}>Снять мут</button>
        )}
        {person.banUntil && onLift && (
          <button type="button" disabled={busy} onClick={() => onLift(person, 'unban')}>Снять бан</button>
        )}
        {person.paused && !person.banUntil && onLift && (
          <button type="button" disabled={busy} onClick={() => onLift(person, 'restore')}>Вернуть должность</button>
        )}
        {onReissue && posts.length > 0 && (
          <button type="button" aria-expanded={open} disabled={busy} onClick={() => setOpen((value) => !value)}>
            {open ? 'Закрыть' : 'Перевыдать'}
          </button>
        )}
        {!person.paused && onDismiss && (
          <button type="button" disabled={busy} onClick={() => onDismiss(person)}>Снять должность</button>
        )}
        {renderExtra ? renderExtra(person) : null}
      </div>
      {open && (
        <div className="seat-reissue">
          <p>Какую должность поставить</p>
          <div className="seat-reissue-posts" role="listbox" aria-label="Должности">
            {posts.map((item) => (
              <button
                key={item.id}
                type="button"
                role="option"
                aria-selected={String(item.id) === String(posId)}
                className={String(item.id) === String(posId) ? 'is-on' : ''}
                onClick={() => setPosId(String(item.id))}
              >
                {item.title}
              </button>
            ))}
          </div>
          {spam && (
            <div className="seat-reissue-dates">
              <label>С какого числа
                <input type="date" value={termStart} onChange={(event) => setTermStart(event.target.value)} />
              </label>
              <label>По какое число
                <input type="date" value={termEnd} onChange={(event) => setTermEnd(event.target.value)} />
              </label>
            </div>
          )}
          <button type="button" disabled={busy || !chosen || (spam && !termEnd)} onClick={reissue}>
            Поставить должность
          </button>
        </div>
      )}
    </article>
  )
}

export default function SeatRoster({
  groups = [],
  busyKey = '',
  onLift,
  onDismiss,
  onReissue,
  renderExtra,
}) {
  const rows = (groups || []).filter((group) => group && (group.seats || group.positions))
  if (!rows.length) return null
  const total = rows.reduce((sum, group) => sum + (group.seats || []).length, 0)
  return (
    <section className="seat-roster" aria-label="Администраторы">
      <header className="seat-roster-head">
        <h3 className="realm-h">Администраторы</h3>
        <p className="realm-copy">
          {total
            ? `${total} на должностях. Наказание видно здесь же: мут должность не забирает, временный бан откладывает её до конца срока.`
            : 'На должностях пока никого нет.'}
        </p>
      </header>
      {rows.map((group) => {
        const people = group.seats || []
        return (
          <div key={group.chatId || group.title} className="seat-roster-group">
            {rows.length > 1 && <h4 className="realm-h">{group.title || 'Группа'}</h4>}
            {people.length === 0 && rows.length > 1 && <p className="realm-copy">В этой группе должностей ни у кого нет.</p>}
            <div className="seat-roster-list">
              {people.map((person) => (
                <PersonCard
                  key={personKey(person)}
                  person={{ ...person, chatId: person.chatId || group.chatId }}
                  positions={group.positions || []}
                  busy={busyKey === personKey(person)}
                  onLift={onLift}
                  onDismiss={onDismiss}
                  onReissue={onReissue}
                  renderExtra={renderExtra}
                />
              ))}
            </div>
          </div>
        )
      })}
    </section>
  )
}
