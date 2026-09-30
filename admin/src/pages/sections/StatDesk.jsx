import { useCallback, useEffect, useMemo, useState } from 'react'
import UserLookupPreview from '../../components/UserLookupPreview'
import {
  clearStatSeason,
  copyStatSeason,
  fetchStatBoard,
  fetchStatCatalog,
  fetchStatGroups,
  fetchStatPerson,
  saveStatValue,
} from '../../lib/adminClient'

function fmt(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '0'
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(number)
}

function digits(value) {
  return String(value || '').replace(/[^\d]/g, '').slice(0, 15)
}

function unclassifiedGames(person) {
  const read = (key) => Number((person?.fields || []).find((field) => field.key === key)?.raw || 0)
  const gap = read('games') - read('wins') - read('losses')
  return gap > 0 ? gap : 0
}

export default function StatDesk() {
  const [catalog, setCatalog] = useState(null)
  const [metricId, setMetricId] = useState('messages')
  const [period, setPeriod] = useState('day')
  const [groupQuery, setGroupQuery] = useState('')
  const [groups, setGroups] = useState([])
  const [chat, setChat] = useState(null)
  const [board, setBoard] = useState(null)
  const [userId, setUserId] = useState(null)
  const [personText, setPersonText] = useState('')
  const [person, setPerson] = useState(null)
  const [draft, setDraft] = useState({})
  const [zeroFrom, setZeroFrom] = useState('')
  const [zeroUntil, setZeroUntil] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')

  const metric = useMemo(
    () => (catalog?.metrics || []).find((item) => item.id === metricId) || null,
    [catalog, metricId],
  )

  useEffect(() => {
    let stop = false
    fetchStatCatalog()
      .then((data) => { if (!stop) setCatalog(data) })
      .catch((err) => { if (!stop) setError(err.message || 'Статистика не открылась') })
    return () => { stop = true }
  }, [])

  useEffect(() => {
    if (!metric) return
    if (!metric.periods.some((item) => item.id === period)) {
      setPeriod(metric.periods[0]?.id || 'all')
    }
  }, [metric, period])

  useEffect(() => {
    if (!metric?.needsGroup) {
      setGroups([])
      return undefined
    }
    const query = groupQuery.trim()
    if (query.length < 1) {
      setGroups([])
      return undefined
    }
    const timer = window.setTimeout(() => {
      fetchStatGroups(query)
        .then((data) => setGroups(data.items || []))
        .catch(() => setGroups([]))
    }, 220)
    return () => window.clearTimeout(timer)
  }, [groupQuery, metric])

  const loadBoard = useCallback(async () => {
    if (!metric) return
    if (metric.needsGroup && !chat) {
      setBoard(null)
      return
    }
    setBusy('board')
    try {
      const data = await fetchStatBoard({
        metric: metric.id,
        period,
        chat_id: chat?.chatId || 0,
      })
      setBoard(data)
      setError('')
    } catch (err) {
      setBoard(null)
      setError(err.message || 'Топ не открылся')
    } finally {
      setBusy('')
    }
  }, [metric, period, chat])

  useEffect(() => { loadBoard() }, [loadBoard])

  useEffect(() => {
    if (!metric || !userId) {
      setPerson(null)
      return undefined
    }
    if (metric.needsGroup && !chat) return undefined
    let stop = false
    fetchStatPerson({
      metric: metric.id,
      user_id: userId,
      period,
      chat_id: chat?.chatId || 0,
    })
      .then((data) => {
        if (stop) return
        setPerson(data)
        const next = {}
        ;(data.fields || []).forEach((field) => {
          if (field.key !== 'games') next[field.key] = String(field.raw ?? 0)
        })
        setDraft(next)
      })
      .catch((err) => {
        if (!stop) {
          setPerson(null)
          setError(err.message || 'Человек не открылся')
        }
      })
    return () => { stop = true }
  }, [metric, userId, period, chat])

  const pickMetric = (id) => {
    setMetricId(id)
    setPerson(null)
    setUserId(null)
    setPersonText('')
    setNotice('')
    setError('')
    setBoard(null)
  }

  const save = async (event) => {
    event.preventDefault()
    if (!metric || !userId) return
    if (metric.fields.some((field) => digits(draft[field.key]) === '')) {
      setError('Впишите число')
      return
    }
    const values = {}
    metric.fields.forEach((field) => {
      values[field.key] = Number(digits(draft[field.key]))
    })
    setBusy('save')
    setNotice('')
    setError('')
    try {
      await saveStatValue({
        metric: metric.id,
        period,
        chat_id: chat?.chatId || 0,
        user_id: userId,
        values,
      })
      setNotice('Сохранено. Топ в чате читает это же число.')
      await loadBoard()
      const fresh = await fetchStatPerson({
        metric: metric.id,
        user_id: userId,
        period,
        chat_id: chat?.chatId || 0,
      })
      setPerson(fresh)
    } catch (err) {
      setError(err.message || 'Сохранить не удалось')
    } finally {
      setBusy('')
    }
  }

  const copySeason = async () => {
    if (!metric) return
    setBusy('copy')
    setNotice('')
    setError('')
    try {
      await copyStatSeason({
        metric: metric.id,
        chat_id: chat?.chatId || 0,
        zero_from: zeroFrom,
        zero_until: zeroUntil,
      })
      setNotice('Копия снята. В указанные даты люди видят нули, потом копия складывается с тем, что прибавилось.')
      await loadBoard()
    } catch (err) {
      setError(err.message || 'Скопировать не удалось')
    } finally {
      setBusy('')
    }
  }

  const clearSeason = async () => {
    if (!metric) return
    if (!window.confirm('Убрать копию? Люди сразу снова увидят числа из базы.')) return
    setBusy('clear')
    setError('')
    try {
      await clearStatSeason({ metric: metric.id, chat_id: chat?.chatId || 0 })
      setNotice('Копия убрана. Топ снова показывает базу.')
      await loadBoard()
    } catch (err) {
      setError(err.message || 'Убрать копию не удалось')
    } finally {
      setBusy('')
    }
  }

  const season = board?.season
  const ready = Boolean(metric) && (!metric.needsGroup || chat)

  return (
    <div className="sec-tab-body stat-desk">
      <p className="realm-copy">
        Здесь те же топы, что открывают люди в чате. Число сохраняется туда, откуда топ его читает.
      </p>
      <div className="stat-metrics" role="tablist" aria-label="Какая статистика">
        {(catalog?.metrics || []).map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={item.id === metricId}
            className={`stat-metric${item.id === metricId ? ' is-on' : ''}`}
            onClick={() => pickMetric(item.id)}
          >
            {item.title}
          </button>
        ))}
      </div>
      {metric && <p className="realm-copy">{metric.blurb}</p>}
      {error && <p className="sec-error" role="alert">{error}</p>}
      {notice && <p className="realm-note" role="status">{notice}</p>}

      {metric?.needsGroup && (
        <div className="stat-group">
          <label className="staff-ga-field">Группа
            <input
              className="sec-input"
              value={groupQuery}
              placeholder="ID, @username или имя группы"
              autoComplete="off"
              onChange={(event) => setGroupQuery(event.target.value)}
            />
          </label>
          {chat && (
            <p className="realm-note">Выбрана {chat.title}{chat.username ? ` · @${chat.username}` : ''}</p>
          )}
          {groups.length > 0 && (
            <ul className="stat-picks">
              {groups.map((item) => (
                <li key={item.chatId}>
                  <button
                    type="button"
                    className={chat?.chatId === item.chatId ? 'is-on' : ''}
                    onClick={() => {
                      setChat(item)
                      setGroupQuery(item.title)
                      setGroups([])
                      setUserId(null)
                      setPerson(null)
                    }}
                  >
                    <strong>{item.title}</strong>
                    <span>{item.username ? `@${item.username}` : item.chatId}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {metric && metric.periods.length > 1 && (
        <div className="stat-periods" role="tablist" aria-label="Срок статистики">
          {metric.periods.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={period === item.id}
              className={`stat-period${period === item.id ? ' is-on' : ''}`}
              onClick={() => setPeriod(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      {ready && (
        <section className="stat-board" aria-busy={busy === 'board'}>
          <h3 className="realm-h">{metric.title}{board?.periodLabel ? ` · ${board.periodLabel}` : ''}</h3>
          {board?.total != null && <p className="realm-copy">Всего в чате за этот срок: {fmt(board.total)}</p>}
          {(board?.rows || []).length === 0 && <p className="realm-copy">В этом топе пока пусто. Человека всё равно можно найти ниже и задать число.</p>}
          <ol className="stat-rows">
            {(board?.rows || []).map((row) => (
              <li key={row.userId}>
                <button type="button" onClick={() => { setUserId(row.userId); setPersonText(String(row.userId)) }}>
                  <b>{row.place}</b>
                  <span>
                    <strong>{row.name}</strong>
                    {row.username ? <i>@{row.username}</i> : null}
                  </span>
                  <em>
                    {fmt(row.seen)} {board?.rowUnit || metric.rowUnit}
                    {row.wins != null ? <small>{fmt(row.wins)} побед · {fmt(row.losses)} проигрышей</small> : null}
                  </em>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      {ready && (
        <form className="stat-edit realm-form" onSubmit={save}>
          <h3 className="realm-h">Изменить число</h3>
          <UserLookupPreview
            value={personText}
            onChange={(value) => { setPersonText(value); setUserId(null) }}
            onResolved={(user) => setUserId(user?.userId ?? user?.user_id ?? null)}
            placeholder="ID, @username или имя"
            label="Человек"
          />
          {person && (
            <div className="stat-now">
              <p className="realm-copy">{person.name}{person.username ? ` · @${person.username}` : ''}</p>
              {(person.fields || []).map((field) => (
                <p key={field.key} className="stat-now-line">
                  <span>{field.label}</span>
                  <strong>в базе {fmt(field.raw)}</strong>
                  <strong>люди видят {fmt(field.seen)}</strong>
                  {field.copied != null && <span>в копии {fmt(field.copied)}, с тех пор {fmt(field.gained)}</span>}
                </p>
              ))}
            </div>
          )}
          {person && metric.fields.map((field) => (
            <label key={field.key} className="staff-ga-field">{field.label}
              <input
                className="sec-input"
                inputMode="numeric"
                value={draft[field.key] || ''}
                onChange={(event) => setDraft((prev) => ({ ...prev, [field.key]: digits(event.target.value) }))}
              />
            </label>
          ))}
          {person && metric.id === 'messages' && period === 'all' && (
            <p className="realm-copy">Всё время пишется отдельно от дня, недели, месяца и года. Так топ устроен в чате.</p>
          )}
          {person && metric.id === 'messages' && period !== 'all' && (
            <p className="realm-copy">Сумма за выбранный срок станет ровно такой. Разница ляжет на сегодня, если сегодня входит в этот срок.</p>
          )}
          {person && metric.id === 'players' && period === 'all' && (
            <p className="realm-copy">За всё время топ складывает победы и проигрыши. Сроки дня, недели, месяца и года при этом не меняются.</p>
          )}
          {person && metric.id === 'players' && period !== 'all' && (
            <p className="realm-copy">За этот срок в топе будет сумма побед и проигрышей. Она встанет на сегодня, если сегодня входит в срок.</p>
          )}
          {person && metric.id === 'players' && period !== 'all' && unclassifiedGames(person) > 0 && (
            <p className="realm-note">В топе за этот срок уже {fmt(unclassifiedGames(person))} игр без разделения на победы и проигрыши. Если сохранить нули, этот срок в топе станет нулём.</p>
          )}
          <button type="submit" className="sec-btn" disabled={!person || busy === 'save'}>
            {busy === 'save' ? 'Сохраняю…' : 'Сохранить'}
          </button>
        </form>
      )}

      {ready && (
        <section className="stat-season">
          <h3 className="realm-h">Копия статистики</h3>
          <p className="realm-copy">
            Снимается текущая статистика. С выбранной даты по выбранную люди видят нули.
            После конечной даты сохранённая копия и то, что прибавилось с момента копии, складываются.
          </p>
          {season && <p className="realm-note">{season.note} Окно {season.zeroFrom} — {season.zeroUntil}.</p>}
          <div className="stat-season-dates">
            <label className="staff-ga-field">С какого числа
              <input className="sec-input" type="date" value={zeroFrom} onChange={(event) => setZeroFrom(event.target.value)} />
            </label>
            <label className="staff-ga-field">По какое число
              <input className="sec-input" type="date" value={zeroUntil} onChange={(event) => setZeroUntil(event.target.value)} />
            </label>
          </div>
          <div className="stat-season-actions">
            <button type="button" className="sec-btn" disabled={!zeroFrom || !zeroUntil || busy === 'copy'} onClick={copySeason}>
              {busy === 'copy' ? 'Копирую…' : 'Скопировать'}
            </button>
            {season && (
              <button type="button" className="sec-btn sec-btn-ghost" disabled={busy === 'clear'} onClick={clearSeason}>
                Убрать копию
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
