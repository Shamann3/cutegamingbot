import { useEffect, useMemo, useState } from 'react'
import { fetchBalanceCalm, fetchBalanceLedger, saveBalanceCalm } from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'

const MAX_SECONDS = 7 * 24 * 3600

function fmt(value) {
  return Number(value || 0).toLocaleString('ru-RU')
}

function oneLeft(total) {
  const safe = Math.max(0, Math.floor(Number(total) || 0))
  const word = (count, one, few, many) => {
    const tail = count % 100
    if (Math.floor(tail / 10) !== 1 && count % 10 === 1) return `${count} ${one}`
    if (Math.floor(tail / 10) !== 1 && [2, 3, 4].includes(count % 10)) return `${count} ${few}`
    return `${count} ${many}`
  }
  if (safe >= 3600) return word(Math.floor(safe / 3600), 'час', 'часа', 'часов')
  if (safe >= 60) return word(Math.floor(safe / 60), 'минута', 'минуты', 'минут')
  return word(safe, 'секунда', 'секунды', 'секунд')
}

function leftClock(total) {
  const safe = Math.max(0, Math.floor(Number(total) || 0))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const seconds = safe % 60
  return `${hours}ч/${minutes}м/${seconds}с`
}

function splitSeconds(total) {
  const safe = Math.max(0, Math.floor(Number(total) || 0))
  return {
    hours: Math.floor(safe / 3600),
    minutes: Math.floor((safe % 3600) / 60),
    seconds: safe % 60,
  }
}

function joinSeconds(hours, minutes, seconds) {
  const whole = Math.floor(Number(hours) || 0) * 3600
    + Math.floor(Number(minutes) || 0) * 60
    + Math.floor(Number(seconds) || 0)
  if (whole < 1) return 1
  return Math.min(MAX_SECONDS, whole)
}

function useRise(value) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    const target = Math.max(0, Math.floor(Number(value) || 0))
    const reduce = typeof window !== 'undefined'
      && window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      setShown(target)
      return undefined
    }
    let frame = 0
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min(1, (now - start) / 720)
      const eased = 1 - (1 - t) ** 3
      setShown(Math.round(target * eased))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value])
  return shown
}

function Pot({ label, hint, value, delay, share }) {
  const shown = useRise(value)
  return (
    <article className="bal-pot" style={{ animationDelay: `${delay}ms` }}>
      <p className="bal-pot-label">{label}</p>
      <strong className="bal-pot-value">{fmt(shown)}</strong>
      <em className="bal-pot-hint">{hint}</em>
      <span className="bal-pot-bar" aria-hidden="true">
        <i style={{ width: `${Math.max(4, Math.round((share || 0) * 100))}%` }} />
      </span>
    </article>
  )
}

function PersonLine({ person, detail, onOpen }) {
  const name = person.name || 'игрок'
  const handle = person.username ? `@${person.username}` : `#${person.userId}`
  return (
    <li className="bal-person">
      <button type="button" onClick={onOpen}>
        <strong>{name}</strong>
        <em>{handle}</em>
      </button>
      <span>{detail}</span>
    </li>
  )
}

function Wallet({ person, onOpenGroup }) {
  if (!person) return null
  const groups = person.groups || []
  return (
    <div className="bal-wallet">
      <div className="bal-wallet-head">
        <strong>{person.name || 'игрок'}</strong>
        <em>{person.username ? `@${person.username}` : `#${person.userId}`}</em>
      </div>
      <div className="bal-wallet-sums">
        <p>
          <span>На личном балансе</span>
          <strong>{fmt(person.balance)}</strong>
        </p>
        <p>
          <span>На бч групп, где он есть</span>
          <strong>{fmt(person.groupsChat)}</strong>
        </p>
        <p>
          <span>Заморозка в этих группах</span>
          <strong>{fmt(person.groupsDex)}</strong>
        </p>
      </div>
      {groups.length === 0 ? (
        <p className="bal-empty">В группах с кутами его нет.</p>
      ) : (
        <ul className="bal-groups">
          {groups.map((group) => {
            const Tag = onOpenGroup ? 'button' : 'div'
            return (
              <li key={group.chatId}>
                <Tag
                  type={onOpenGroup ? 'button' : undefined}
                  onClick={onOpenGroup ? () => onOpenGroup(group.chatId) : undefined}
                >
                  <strong>{group.name || 'группа'}</strong>
                  <em>
                    {group.username ? `@${group.username}` : `#${group.chatId}`}
                    {group.technical ? ' · проект' : ''}
                    {group.creator ? ' · создатель' : ''}
                  </em>
                </Tag>
                <span>
                  {fmt(group.chat)} на бч
                  {group.dex ? ` · ${fmt(group.dex)} заморозка` : ''}
                </span>
              </li>
            )
          })}
        </ul>
      )}
      {person.groupsHidden > 0 && (
        <p className="bal-empty">Ещё {fmt(person.groupsHidden)} групп с кутами. Выше — самые большие.</p>
      )}
    </div>
  )
}

export default function BalancesCalm({ onOpenGroup } = {}) {
  const [form, setForm] = useState(null)
  const [ledger, setLedger] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [focus, setFocus] = useState(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(q.trim()), 320)
    return () => clearTimeout(timer)
  }, [q])

  useEffect(() => {
    let gone = false
    fetchBalanceCalm()
      .then((data) => { if (!gone) setForm(data) })
      .catch((err) => { if (!gone) setError(err.message || 'Настройка не открылась') })
    return () => { gone = true }
  }, [])

  useEffect(() => {
    let gone = false
    fetchBalanceLedger({ q: debouncedQ, focus })
      .then((data) => { if (!gone) setLedger(data) })
      .catch((err) => { if (!gone) setError(err.message || 'Картина кут не открылась') })
    return () => { gone = true }
  }, [debouncedQ, focus])

  const parts = useMemo(() => splitSeconds(form?.seconds ?? 86400), [form?.seconds])
  const windowSeconds = joinSeconds(parts.hours, parts.minutes, parts.seconds)
  const games = Number(form?.games) || 5
  const pots = ledger?.pots || {}
  const system = Number(pots.system) || 0
  const share = (key) => (system > 0 ? (Number(pots[key]) || 0) / system : 0)

  async function save() {
    if (!form) return
    setSaving(true)
    try {
      const next = await saveBalanceCalm({
        enabled: Boolean(form.enabled),
        games: Number(form.games),
        seconds: joinSeconds(parts.hours, parts.minutes, parts.seconds),
      })
      setForm(next)
      notifyAdmin('Балансы сохранены')
    } catch (err) {
      notifyAdmin(err.message || 'Не сохранилось', { error: true })
    } finally {
      setSaving(false)
    }
  }

  function openPerson(userId) {
    setQ(String(userId))
    setFocus(userId)
  }

  function setPart(key, raw) {
    setForm((row) => {
      const piece = splitSeconds(row?.seconds ?? 86400)
      const next = joinSeconds(
        key === 'hours' ? raw : piece.hours,
        key === 'minutes' ? raw : piece.minutes,
        key === 'seconds' ? raw : piece.seconds,
      )
      return { ...row, seconds: next }
    })
  }

  if (!form && !ledger) {
    return <p className="panel-shelf-muted" style={{ padding: '1rem' }}>{error || 'Собираю картину кут…'}</p>
  }

  const search = ledger?.search || { users: [], items: [] }

  return (
    <div className="bal-ledger">
      <header className="bal-hero">
        <p className="panel-shelf-label">Балансы</p>
        <h3>Где лежат куты</h3>
        <p>
          Игроки, живые группы и технические группы проекта — отдельно.
          Вся система — это их сумма.
        </p>
      </header>

      {error && <p className="panel-shelf-error">{error}</p>}
      {(ledger?.warnings || []).map((line) => (
        <p key={line} className="bal-warn">{line}</p>
      ))}

      <div className="bal-pots">
        <Pot label="У игроков" hint="личные балансы" value={pots.users} delay={40} share={share('users')} />
        <Pot label="У групп" hint="чат и покупки живых групп" value={pots.groups} delay={110} share={share('groups')} />
        <Pot label="У проекта" hint="технические группы" value={pots.project} delay={180} share={share('project')} />
        <Pot label="Вся система" hint={`все балансы: ${fmt(pots.allBalances)}`} value={pots.system} delay={250} share={1} />
      </div>

      <div className="bal-split" aria-hidden="true">
        <i className="is-users" style={{ flexGrow: Math.max(share('users'), 0.04) }} />
        <i className="is-groups" style={{ flexGrow: Math.max(share('groups'), 0.04) }} />
        <i className="is-project" style={{ flexGrow: Math.max(share('project'), 0.04) }} />
      </div>

      <div className="bal-columns">
        <section className="bal-column">
          <h4>Кто чаще играет</h4>
          <p>Игры на куты за последние 7 дней, в любой группе.</p>
          <ul>
            {(ledger?.players || []).length === 0 && <li className="bal-empty">Пока тихо</li>}
            {(ledger?.players || []).map((person) => (
              <PersonLine
                key={person.userId}
                person={person}
                detail={`${fmt(person.games)} игр`}
                onOpen={() => openPerson(person.userId)}
              />
            ))}
          </ul>
        </section>
        <section className="bal-column">
          <h4>Кто чаще двигает куты</h4>
          <p>Последние операции: начисления, списания, переводы.</p>
          <ul>
            {(ledger?.operations || []).length === 0 && <li className="bal-empty">Пока тихо</li>}
            {(ledger?.operations || []).map((person) => (
              <PersonLine
                key={person.userId}
                person={person}
                detail={`${fmt(person.ops)} · ${fmt(person.moved)} кут`}
                onOpen={() => openPerson(person.userId)}
              />
            ))}
          </ul>
        </section>
      </div>

      <section className="bal-search">
        <h4>Найти человека</h4>
        <p>Имя, @username или id. Личные куты и куты групп показаны отдельно. Нажмите группу, чтобы открыть её карточку.</p>
        <input
          className="sec-input"
          value={q}
          placeholder="Имя, @username или id"
          aria-label="Поиск по игроку"
          onChange={(event) => {
            setQ(event.target.value)
            setFocus(null)
          }}
        />
        {search.users.length > 1 && (
          <div className="bal-chips">
            {search.users.map((person) => (
              <button
                key={person.userId}
                type="button"
                className={search.focus === person.userId ? 'is-on' : ''}
                onClick={() => setFocus(person.userId)}
              >
                {person.name || 'игрок'}
                <em>личные {fmt(person.balance)}</em>
                <em>группы {fmt(person.groupsChat)}</em>
              </button>
            ))}
          </div>
        )}
        <Wallet
          person={search.users.find((person) => person.userId === search.focus) || search.users[0]}
          onOpenGroup={onOpenGroup}
        />
        <ul className="bal-feed">
          {debouncedQ && search.users.length === 0 && <li className="bal-empty">Такого человека нет</li>}
          {search.users.length > 0 && search.items.length === 0 && <li className="bal-empty">Движений пока нет</li>}
          {search.items.map((item) => (
            <li key={item.id} className={item.direction === 'in' ? 'is-in' : 'is-out'}>
              <div>
                <strong>{item.cause || 'операция'}</strong>
                <em>{item.when || ''}</em>
              </div>
              <span>{item.direction === 'in' ? '+' : '−'}{fmt(item.amount)} кут</span>
              {item.group && (
                <p>
                  {item.transfer
                    ? 'Перевод в группе'
                    : item.direction === 'in'
                      ? 'Снято из группы'
                      : 'Положено в группу'}
                  {' '}
                  {item.group.name || 'группа'}
                  {item.group.username ? ` @${item.group.username}` : ''}
                </p>
              )}
            </li>
          ))}
        </ul>
      </section>

      {form && (
        <section className="bal-rule">
          <div className="sys-group-head">
            <h3 className="sys-group-title">Когда куты в покое</h3>
          </div>
          <p className="panel-shelf-muted">
            Игры считаются в любой группе. Пока за этот срок их набрано достаточно,
            обливать нельзя. Зонтик, дождевик, навес и сейф закрывают сразу, даже без этих игр.
          </p>
          <div className={`sys-toggle-row${form.enabled ? ' is-on' : ''}`}>
            <div className="sys-toggle-copy">
              <strong>Покой включён</strong>
              <em>Выключено — пистолетик снова берёт куты у всех, у кого нет купленной защиты.</em>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={Boolean(form.enabled)}
              className={`panel-toggle${form.enabled ? ' panel-toggle-on' : ''}`}
              disabled={saving}
              onClick={() => setForm((row) => ({ ...row, enabled: !row.enabled }))}
            >
              <span className="panel-toggle-thumb" />
            </button>
          </div>
          <div className="bal-fields">
            <label>
              <strong>Игр</strong>
              <input
                className="sec-input"
                type="number"
                min="1"
                max="100"
                value={form.games}
                aria-label="Игр за срок"
                onChange={(event) => setForm((row) => ({ ...row, games: event.target.value }))}
              />
            </label>
            <label>
              <strong>Часы</strong>
              <input
                className="sec-input"
                type="number"
                min="0"
                max="168"
                value={parts.hours}
                aria-label="Часы срока"
                onChange={(event) => setPart('hours', event.target.value)}
              />
            </label>
            <label>
              <strong>Минуты</strong>
              <input
                className="sec-input"
                type="number"
                min="0"
                max="59"
                value={parts.minutes}
                aria-label="Минуты срока"
                onChange={(event) => setPart('minutes', event.target.value)}
              />
            </label>
            <label>
              <strong>Секунды</strong>
              <input
                className="sec-input"
                type="number"
                min="0"
                max="59"
                value={parts.seconds}
                aria-label="Секунды срока"
                onChange={(event) => setPart('seconds', event.target.value)}
              />
            </label>
          </div>
          <p className="bal-preview">
            {form.enabled
              ? `0/${games} | осталось ${oneLeft(windowSeconds)}`
              : 'Сейчас покой выключен.'}
          </p>
          <button type="button" className="sec-btn" disabled={saving} onClick={save}>
            {saving ? 'Сохраняю…' : 'Сохранить'}
          </button>
        </section>
      )}

      <style>{`
        .bal-page { position: relative; }
        .bal-ledger { display: flex; flex-direction: column; gap: 1rem; position: relative; }
        .bal-ledger::before {
          content: "";
          position: absolute;
          inset: -12px -8px auto;
          height: 1px;
          background: linear-gradient(90deg, transparent, rgba(125, 211, 252, 0.7), transparent);
          animation: bal-scan 4.8s ease-in-out infinite;
        }
        .bal-hero h3 {
          margin: 0.15rem 0;
          font-size: 1.45rem;
          letter-spacing: 0.04em;
          text-shadow: 0 0 18px rgba(125, 211, 252, 0.28);
        }
        .bal-hero p { margin: 0; color: rgba(226, 232, 240, 0.68); max-width: 40rem; }
        .bal-pots {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 0.75rem;
        }
        .bal-pot {
          position: relative;
          padding: 0.95rem 1rem 0.85rem;
          border-radius: 18px;
          background:
            linear-gradient(180deg, rgba(125, 211, 252, 0.08), rgba(255,255,255,0.02) 42%, rgba(8, 12, 20, 0.2)),
            rgba(8, 14, 24, 0.35);
          border: 1px solid rgba(125, 211, 252, 0.22);
          box-shadow: inset 0 0 0 1px rgba(255,255,255,0.03), 0 10px 30px rgba(0, 0, 0, 0.18);
          animation: bal-rise 0.6s ease both;
          overflow: hidden;
        }
        .bal-pot::after {
          content: "";
          position: absolute;
          top: 0; left: -40%;
          width: 40%;
          height: 100%;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,0.14), transparent);
          animation: bal-sheen 5.5s ease-in-out infinite;
        }
        .bal-pot-label { margin: 0; font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; color: rgba(125, 211, 252, 0.78); }
        .bal-pot-value {
          display: block;
          margin: 0.4rem 0 0.15rem;
          font-size: 1.55rem;
          font-variant-numeric: tabular-nums;
          letter-spacing: 0.02em;
          color: #f8fafc;
          text-shadow: 0 0 16px rgba(216, 196, 138, 0.35);
        }
        .bal-pot-hint { display: block; font-style: normal; font-size: 0.75rem; opacity: 0.55; }
        .bal-pot-bar { display: block; height: 3px; margin-top: 0.75rem; border-radius: 99px; background: rgba(255,255,255,0.08); overflow: hidden; }
        .bal-pot-bar i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #7dd3fc, #d8c48a); transform-origin: left; animation: bal-fill 0.8s ease both; }
        .bal-split { display: flex; height: 8px; border-radius: 99px; overflow: hidden; gap: 3px; }
        .bal-split i { display: block; border-radius: 99px; transform-origin: left; animation: bal-fill 0.9s ease both; }
        .bal-split .is-users { background: #d8c48a; }
        .bal-split .is-groups { background: #7eb6a4; }
        .bal-split .is-project { background: #8aa0c8; }
        .bal-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
        .bal-column, .bal-search, .bal-rule {
          padding: 1rem 1rem 1.05rem;
          border-radius: 18px;
          border: 1px solid rgba(125, 211, 252, 0.16);
          background: linear-gradient(180deg, rgba(15, 23, 42, 0.45), rgba(255,255,255,0.02));
          box-shadow: inset 0 0 24px rgba(125, 211, 252, 0.04);
          animation: bal-rise 0.7s ease both;
        }
        .bal-column h4, .bal-search h4, .bal-rule h3 { margin: 0 0 0.25rem; }
        .bal-column p, .bal-search p { margin: 0 0 0.75rem; color: rgba(255,255,255,0.55); font-size: 0.85rem; }
        .bal-column ul, .bal-feed { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.4rem; }
        .bal-person, .bal-feed li {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 0.15rem 0.75rem;
          padding: 0.45rem 0;
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .bal-person button { background: none; border: 0; color: inherit; text-align: left; padding: 0; cursor: pointer; }
        .bal-person strong, .bal-feed strong { display: block; font-weight: 600; }
        .bal-person em, .bal-feed em { font-style: normal; opacity: 0.5; font-size: 0.78rem; }
        .bal-person span, .bal-feed span { font-variant-numeric: tabular-nums; align-self: center; }
        .bal-feed li.is-in span { color: #7eb6a4; }
        .bal-feed li.is-out span { color: #e09898; }
        .bal-feed p { grid-column: 1 / -1; margin: 0; }
        .bal-empty { opacity: 0.5; }
        .bal-search .sec-input { width: 100%; margin-bottom: 0.75rem; }
        .bal-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.75rem; }
        .bal-chips button {
          border: 1px solid rgba(255,255,255,0.12);
          background: transparent;
          color: inherit;
          border-radius: 999px;
          padding: 0.3rem 0.7rem;
          cursor: pointer;
        }
        .bal-chips button.is-on { border-color: #d8c48a; }
        .bal-chips em { display: block; font-style: normal; color: rgba(226, 232, 240, 0.78); font-size: 0.72rem; }
        .bal-wallet { margin: 0.2rem 0 0.9rem; }
        .bal-wallet-head strong { display: block; font-size: 1.05rem; }
        .bal-wallet-head em { font-style: normal; color: rgba(226, 232, 240, 0.78); font-size: 0.82rem; }
        .bal-wallet-sums {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 0.55rem;
          margin: 0.7rem 0;
        }
        .bal-wallet-sums p {
          margin: 0;
          padding: 0.7rem 0.75rem;
          border-radius: 14px;
          border: 1px solid rgba(125, 211, 252, 0.2);
          background: rgba(8, 14, 24, 0.35);
        }
        .bal-wallet-sums span { display: block; font-size: 0.75rem; color: rgba(226, 232, 240, 0.78); }
        .bal-wallet-sums strong {
          display: block;
          margin-top: 0.25rem;
          font-size: 1.2rem;
          font-variant-numeric: tabular-nums;
          color: #f8fafc;
        }
        .bal-groups { list-style: none; margin: 0; padding: 0; }
        .bal-groups li {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 0.35rem 0.75rem;
          align-items: center;
          padding: 0.45rem 0;
          border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .bal-groups button, .bal-groups div { background: none; border: 0; color: inherit; text-align: left; padding: 0; }
        .bal-groups button { cursor: pointer; }
        .bal-groups button:focus-visible { outline: 2px solid rgba(125, 211, 252, 0.7); outline-offset: 3px; }
        .bal-groups strong { display: block; }
        .bal-groups em { font-style: normal; color: rgba(226, 232, 240, 0.78); font-size: 0.78rem; }
        .bal-groups span { font-variant-numeric: tabular-nums; }
        @media (max-width: 700px) {
          .bal-wallet-sums { grid-template-columns: 1fr; }
        }
        .bal-fields { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.6rem; margin: 0.9rem 0; }
        .bal-fields label { display: flex; flex-direction: column; gap: 0.3rem; }
        .bal-fields strong { font-size: 0.78rem; font-weight: 600; }
        .bal-fields .sec-input { width: 100%; }
        .bal-preview {
          font-variant-numeric: tabular-nums;
          letter-spacing: 0.03em;
          margin: 0 0 0.8rem;
          padding: 0.65rem 0.8rem;
          border-radius: 14px;
          border: 1px solid rgba(216, 196, 138, 0.28);
          background: rgba(216,196,138,0.08);
          box-shadow: 0 0 18px rgba(216, 196, 138, 0.08);
        }
        .bal-warn { margin: 0; color: #e0c27a; font-size: 0.85rem; }
        @keyframes bal-rise {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: none; }
        }
        @keyframes bal-fill {
          from { transform: scaleX(0); }
          to { transform: scaleX(1); }
        }
        @keyframes bal-scan {
          0%, 100% { opacity: 0.25; transform: scaleX(0.6); }
          50% { opacity: 1; transform: scaleX(1); }
        }
        @keyframes bal-sheen {
          0%, 55% { transform: translateX(0); opacity: 0; }
          70% { opacity: 1; }
          100% { transform: translateX(380%); opacity: 0; }
        }
        @media (max-width: 900px) {
          .bal-pots, .bal-columns, .bal-fields { grid-template-columns: 1fr 1fr; }
        }
        @media (max-width: 640px) {
          .bal-pots, .bal-columns, .bal-fields { grid-template-columns: 1fr; }
        }
        @media (prefers-reduced-motion: reduce) {
          .bal-pot, .bal-column, .bal-search, .bal-rule, .bal-pot-bar i, .bal-split i, .bal-ledger::before, .bal-pot::after { animation: none; }
        }
      `}</style>
    </div>
  )
}
