import { useCallback, useEffect, useState } from 'react'
import CountUp from '../../../components/CountUp'
import { fetchDeedAnalytics, isPanelPreviewMode, tuneDeedRates } from '../../../lib/adminClient'
import { motionQuiet } from './DeckCard'

const ORDER = ['ban', 'mute', 'kick', 'warn', 'check_admin', 'check_staff']

function messageOf(error) {
  return error?.message || 'Касса не открылась'
}

function dayLabel(iso) {
  const date = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function levelOf(value, max) {
  if (!value || !max) return '0'
  const ratio = value / max
  if (ratio > 0.75) return '4'
  if (ratio > 0.5) return '3'
  if (ratio > 0.25) return '2'
  return '1'
}

function sumOf(point) {
  return (Number(point?.issue) || 0) + (Number(point?.admin) || 0) + (Number(point?.staff) || 0)
}

export default function PurseDesk() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [day, setDay] = useState('')
  const [grown, setGrown] = useState(false)

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    setError('')
    try {
      setData(await fetchDeedAnalytics())
    } catch (err) {
      setError(messageOf(err))
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!data) return undefined
    if (motionQuiet()) {
      setGrown(true)
      return undefined
    }
    setGrown(false)
    const id = requestAnimationFrame(() => setGrown(true))
    return () => cancelAnimationFrame(id)
  }, [data])

  const apply = async (auto, now) => {
    setBusy(now ? 'tune' : 'auto')
    setError('')
    try {
      setData(await tuneDeedRates({ auto, now }))
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy('')
    }
  }

  if (isPanelPreviewMode()) {
    return <p className="staff-hint">В копии панели касса не открывается.</p>
  }
  if (!data) {
    return <p className="staff-hint">{error || 'Считаем кассу…'}</p>
  }

  const paid = data.paid?.all || {}
  const week = data.paid?.week || {}
  const month = data.paid?.month || {}
  const days = data.days || []
  const max = Math.max(...days.map(sumOf), 1)
  const picked = days.find((item) => item.day === day) || null
  const rates = [...(data.rates || [])].sort((a, b) => {
    const ai = ORDER.indexOf(a.actionType)
    const bi = ORDER.indexOf(b.actionType)
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi)
  })
  const auto = Boolean(data.tune?.auto)

  return (
    <div className="purse-desk">
      <p className="deed-lead">
        Код смотрит технические группы и сам ставит нормы: за неделю зарплаты забирают не больше 15% их кута и не трогают последние 40%.
      </p>
      {error && <p className="staff-hint" role="alert">{error}</p>}
      <div className="act-bento">
        <p>
          <strong><CountUp value={data.purse} /></strong>
          <span>кут лежит в {data.groups || 0} технических группах</span>
        </p>
        <p>
          <strong><CountUp value={week.all} /></strong>
          <span>кут ушёл из групп на зарплаты за 7 дней</span>
        </p>
        <p>
          <strong><CountUp value={data.owed?.all} /></strong>
          <span>кут ещё ждёт, пока вы отпустите выплату</span>
        </p>
        <p>
          <strong><CountUp value={paid.all} /></strong>
          <span>кут уже ушёл из групп на зарплаты</span>
        </p>
      </div>
      <p className="deed-lead">
        Из этой суммы выдавшим {paid.issue || 0}, администраторам за проверки {paid.admin || 0}, сотрудникам за проверки {paid.staff || 0}.
        {Number(data.manualPaid) > 0 ? ` Ещё ${data.manualPaid} кут вы отметили сами, группы это не платили.` : ''}
      </p>
      <p className="deed-lead">
        За 30 дней из групп на зарплаты ушёл {month.all || 0}: выдавшим {month.issue || 0}, администраторам {month.admin || 0}, сотрудникам {month.staff || 0}.
      </p>
      <div className="purse-days">
        <div className="act-bars" role="list" aria-label="Кут на зарплаты по дням">
          {days.map((point, index) => {
            const total = sumOf(point)
            const height = total ? Math.max(8, Math.round((total / max) * 100)) : 6
            return (
              <button
                key={point.day}
                type="button"
                role="listitem"
                className={day === point.day ? 'is-on' : ''}
                data-level={levelOf(total, max)}
                aria-pressed={day === point.day}
                aria-label={`${dayLabel(point.day)}: ${total} кут`}
                onClick={() => setDay(day === point.day ? '' : point.day)}
              >
                <i style={{ height: grown ? `${height}%` : '6%', transitionDelay: `${index * 28}ms` }}>
                  {point.issue > 0 && <b className="is-issue" style={{ flex: `${point.issue} 1 0` }} />}
                  {point.admin > 0 && <b className="is-admin" style={{ flex: `${point.admin} 1 0` }} />}
                  {point.staff > 0 && <b className="is-staff" style={{ flex: `${point.staff} 1 0` }} />}
                </i>
              </button>
            )
          })}
        </div>
        <p className="purse-key">
          <span><i className="is-issue" /> выдавшим</span>
          <span><i className="is-admin" /> администраторам</span>
          <span><i className="is-staff" /> сотрудникам</span>
        </p>
        <p className="staff-hint">
          {picked
            ? `${dayLabel(picked.day)}: ${sumOf(picked)} кут. Выдавшим ${picked.issue}, администраторам ${picked.admin}, сотрудникам ${picked.staff}.`
            : '14 дней. Нажмите столбец, чтобы увидеть день.'}
        </p>
      </div>
      <p className="deed-lead">{data.tune?.note || (auto ? 'Нормы пока не подстраивались.' : 'Нормы сейчас ваши. Группы их не меняют.')}</p>
      <ul className="purse-rates">
        {rates.map((rate) => (
          <li key={rate.actionType}>
            <strong>{rate.title}</strong>
            <span>
              {rate.enabled ? `каждые ${rate.everyN} = ${rate.rewardKut} кут` : 'выключено'}
              {rate.unit && rate.unit !== '0' ? ` · ${rate.unit} за карточку` : ''}
              {rate.idealUnit && rate.idealUnit !== rate.unit ? ` · верхняя цена ${rate.idealUnit}` : ''}
            </span>
          </li>
        ))}
      </ul>
      {(data.people || []).length > 0 && (
        <div className="deed-lines">
          <h3 className="staff-punish-title">Кто сколько получил из групп</h3>
          {data.people.map((person) => (
            <article key={person.id} className="staff-member-row">
              <div className="staff-member-info">
                <span className="staff-card-name">{person.name}</span>
                <span className="staff-card-date">
                  выдавшим {person.issue} · проверки администратора {person.admin} · проверки сотрудника {person.staff}
                  {person.owed > 0 ? ` · ждёт ${person.owed}` : ''}
                </span>
              </div>
              <strong className="purse-person">{person.paid.toLocaleString('ru-RU')}</strong>
            </article>
          ))}
        </div>
      )}
      <label className="deed-check">
        <input
          type="checkbox"
          checked={auto}
          disabled={Boolean(busy)}
          onChange={(event) => apply(event.target.checked, event.target.checked)}
        />
        <span>{auto ? 'Группы сами держат нормы' : 'Нормы зафиксированы вручную'}</span>
      </label>
      <div className="deed-choice">
        <button type="button" className="sec-btn" disabled={Boolean(busy)} onClick={() => apply(true, true)}>
          {busy === 'tune' ? 'Считаем группы…' : 'Подстроить сейчас'}
        </button>
      </div>
    </div>
  )
}
