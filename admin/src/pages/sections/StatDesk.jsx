import { useCallback, useEffect, useRef, useState } from 'react'
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

function periodOf(metric, current) {
  const ids = (metric?.periods || []).map((item) => item.id)
  if (ids.includes(current)) return current
  return ids[0] || 'all'
}

function draftFrom(metric, source) {
  const next = {}
  if (!metric) return next
  if (source?.fields) {
    source.fields.forEach((field) => {
      if (field.key !== 'games') next[field.key] = String(field.raw ?? 0)
    })
    return next
  }
  if (metric.id === 'players') {
    next.wins = String(source?.wins ?? 0)
    next.losses = String(source?.losses ?? 0)
    return next
  }
  const key = metric.fields?.[0]?.key
  if (key) next[key] = String(source?.raw ?? source?.seen ?? 0)
  return next
}

function unclassifiedGames(person) {
  const read = (key) => Number((person?.fields || []).find((field) => field.key === key)?.raw || 0)
  const gap = read('games') - read('wins') - read('losses')
  return gap > 0 ? gap : 0
}

function paintRow(row, metric, values, hiding) {
  if (metric.id === 'players') {
    const games = Number(values.wins || 0) + Number(values.losses || 0)
    return {
      ...row,
      wins: values.wins,
      losses: values.losses,
      games,
      raw: games,
      seen: hiding ? 0 : games,
    }
  }
  const key = metric.fields[0]?.key
  const amount = Number(values[key] || 0)
  return { ...row, raw: amount, seen: hiding ? 0 : amount }
}

function StatEditor({
  metric,
  period,
  person,
  draft,
  onDraft,
  onSubmit,
  saving,
  error,
}) {
  const hidden = person?.season?.phase === 'zero'
  return (
    <form className="stat-row-edit" onSubmit={onSubmit}>
      {person && (person.fields || []).filter((field) => field.key !== 'games').map((field) => (
        <p key={field.key} className="stat-now-line">
          <span>{field.label}</span>
          <strong>{fmt(field.seen)} сейчас в топе</strong>
          {field.seen !== field.raw && <span>в базе {fmt(field.raw)}</span>}
        </p>
      ))}
      {!person && <p className="stat-loading">Считаю число…</p>}
      <div className="stat-fields">
        {metric.fields.map((field) => (
          <label key={field.key} className="staff-ga-field">{field.label}
            <input
              className="sec-input"
              inputMode="numeric"
              value={draft[field.key] ?? ''}
              onChange={(event) => onDraft(field.key, event.target.value)}
            />
          </label>
        ))}
      </div>
      {metric.id === 'messages' && period === 'all' && (
        <p className="realm-copy">Это число за всё время. День, неделя, месяц и год останутся как были.</p>
      )}
      {metric.id === 'messages' && period !== 'all' && (
        <p className="realm-copy">Сумма за выбранный срок станет ровно такой. Всё время при этом не меняется.</p>
      )}
      {metric.id === 'players' && period === 'all' && (
        <p className="realm-copy">Это победы и проигрыши за всё время. День, неделя, месяц и год останутся как были.</p>
      )}
      {metric.id === 'players' && period !== 'all' && (
        <p className="realm-copy">В топе за этот срок будет сумма этих двух чисел.</p>
      )}
      {metric.id === 'players' && period !== 'all' && unclassifiedGames(person) > 0 && (
        <p className="realm-note">
          За этот срок уже есть {fmt(unclassifiedGames(person))} игр без побед и проигрышей. После сохранения в топе останется только сумма этих двух чисел.
        </p>
      )}
      {hidden && person?.season?.zeroUntil && (
        <p className="realm-note">До {person.season.zeroUntil} люди видят ноль. Сохранение меняет число в базе.</p>
      )}
      {error && <p className="sec-error" role="alert">{error}</p>}
      <button type="submit" className="sec-btn" disabled={saving}>
        {saving ? 'Сохраняю…' : 'Сохранить в этот топ'}
      </button>
    </form>
  )
}

export default function StatDesk() {
  const [catalog, setCatalog] = useState(null)
  const [metricId, setMetricId] = useState('messages')
  const [period, setPeriod] = useState('day')
  const [groupQuery, setGroupQuery] = useState('')
  const [groupPack, setGroupPack] = useState(null)
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
  const [rowError, setRowError] = useState('')
  const [loadingBoard, setLoadingBoard] = useState(false)
  const [loadingGroups, setLoadingGroups] = useState(false)
  const [saving, setSaving] = useState(false)
  const [seasonBusy, setSeasonBusy] = useState('')
  const dirtyRef = useRef(false)
  const boardToken = useRef(0)
  const groupToken = useRef(0)

  const metric = (catalog?.metrics || []).find((item) => item.id === metricId) || null
  const periodOk = Boolean(metric?.periods?.some((item) => item.id === period))
  const showPeople = Boolean(metric) && periodOk && (!metric.needsGroup || chat)
  const boardReady = Boolean(board) && board.metric === metric?.id && board.period === period
  const rows = boardReady ? (board.rows || []) : []
  const groupsReady = groupPack?.period === period
  const groupItems = groupsReady ? (groupPack.items || []) : []

  useEffect(() => {
    let stop = false
    fetchStatCatalog()
      .then((data) => { if (!stop) setCatalog(data) })
      .catch((err) => { if (!stop) setError(err.message || 'Статистика не открылась') })
    return () => { stop = true }
  }, [])

  useEffect(() => {
    if (!metric || periodOk) return
    setBoard(null)
    setPerson(null)
    setDraft({})
    setPeriod(periodOf(metric, period))
  }, [metric, period, periodOk])

  useEffect(() => {
    if (!metric?.needsGroup || chat || !periodOk) return undefined
    const token = ++groupToken.current
    const wanted = period
    const query = groupQuery.trim()
    setLoadingGroups(true)
    const timer = window.setTimeout(() => {
      fetchStatGroups(query, wanted)
        .then((data) => {
          if (token !== groupToken.current) return
          if (data?.period && data.period !== wanted) return
          setGroupPack({ ...(data || {}), period: data?.period || wanted, items: data?.items || [] })
        })
        .catch((err) => {
          if (token !== groupToken.current) return
          setGroupPack({ period: wanted, periodLabel: '', items: [] })
          setError(err.message || 'Группы не открылись')
        })
        .finally(() => {
          if (token === groupToken.current) setLoadingGroups(false)
        })
    }, query ? 200 : 0)
    return () => window.clearTimeout(timer)
  }, [metric, period, periodOk, groupQuery, chat])

  const refreshBoard = useCallback(async () => {
    if (!metric || !metric.periods.some((item) => item.id === period)) return null
    if (metric.needsGroup && !chat) {
      setBoard(null)
      setLoadingBoard(false)
      return null
    }
    const token = ++boardToken.current
    const wantedPeriod = period
    const wantedMetric = metric.id
    setLoadingBoard(true)
    try {
      const data = await fetchStatBoard({
        metric: wantedMetric,
        period: wantedPeriod,
        chat_id: chat?.chatId || 0,
      })
      if (token !== boardToken.current) return null
      if (data.period !== wantedPeriod || data.metric !== wantedMetric) return null
      setBoard(data)
      setError('')
      return data
    } catch (err) {
      if (token !== boardToken.current) return null
      setBoard(null)
      setError(err.message || 'Топ не открылся')
      throw err
    } finally {
      if (token === boardToken.current) setLoadingBoard(false)
    }
  }, [metric, period, chat])

  useEffect(() => {
    refreshBoard().catch(() => {})
  }, [refreshBoard])

  useEffect(() => {
    if (!metric || !userId || !periodOk) return undefined
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
        if (!dirtyRef.current) setDraft(draftFrom(metric, data))
      })
      .catch((err) => {
        if (!stop) setRowError(err.message || 'Человек не открылся')
      })
    return () => { stop = true }
  }, [metric, userId, period, periodOk, chat])

  const pickMetric = (id) => {
    const item = (catalog?.metrics || []).find((entry) => entry.id === id)
    if (!item || item.id === metricId) return
    boardToken.current += 1
    groupToken.current += 1
    setMetricId(id)
    setPeriod(periodOf(item, period))
    setBoard(null)
    setGroupPack(null)
    setPerson(null)
    setUserId(null)
    setPersonText('')
    setDraft({})
    dirtyRef.current = false
    setRowError('')
    setError('')
    setNotice('')
  }

  const pickPeriod = (id) => {
    if (id === period) return
    boardToken.current += 1
    groupToken.current += 1
    setPeriod(id)
    setBoard(null)
    setGroupPack(null)
    setPerson(null)
    setDraft({})
    dirtyRef.current = false
    setRowError('')
    setError('')
    setNotice('')
  }

  const openPerson = (row) => {
    if (Number(userId) === Number(row.userId)) {
      setUserId(null)
      setPerson(null)
      setDraft({})
      dirtyRef.current = false
      setRowError('')
      return
    }
    dirtyRef.current = false
    setUserId(Number(row.userId))
    setPersonText('')
    setPerson(null)
    setDraft(draftFrom(metric, row))
    setRowError('')
    setNotice('')
  }

  const chooseFound = (user) => {
    const id = Number(user?.userId ?? user?.user_id)
    if (!Number.isFinite(id) || id <= 0) return
    dirtyRef.current = false
    setUserId(id)
    setPerson(null)
    setDraft({})
    setRowError('')
    setNotice('')
  }

  const leaveGroup = () => {
    boardToken.current += 1
    setChat(null)
    setBoard(null)
    setUserId(null)
    setPerson(null)
    setDraft({})
    setPersonText('')
    dirtyRef.current = false
    setNotice('')
    setRowError('')
  }

  const editDraft = (key, value) => {
    dirtyRef.current = true
    setDraft((prev) => ({ ...prev, [key]: digits(value) }))
  }

  const save = async (event) => {
    event.preventDefault()
    if (!metric || !userId) {
      setRowError('Выберите человека в списке')
      return
    }
    if (metric.needsGroup && !chat) {
      setRowError('Сначала выберите группу')
      return
    }
    if (metric.fields.some((field) => digits(draft[field.key]) === '')) {
      setRowError('Впишите число')
      return
    }
    const values = {}
    metric.fields.forEach((field) => {
      values[field.key] = Number(digits(draft[field.key]))
    })
    const hiding = board?.season?.phase === 'zero'
    const shown = metric.id === 'players'
      ? Number(values.wins || 0) + Number(values.losses || 0)
      : Number(values[metric.fields[0].key] || 0)
    setSaving(true)
    setRowError('')
    setNotice('')
    try {
      await saveStatValue({
        metric: metric.id,
        period,
        chat_id: chat?.chatId || 0,
        user_id: userId,
        values,
      })
      setBoard((prev) => {
        if (!prev || prev.period !== period || prev.metric !== metric.id) return prev
        return {
          ...prev,
          rows: (prev.rows || []).map((row) => (
            Number(row.userId) === Number(userId) ? paintRow(row, metric, values, hiding) : row
          )),
        }
      })
      setNotice(hiding
        ? `В базе теперь ${fmt(shown)}. Люди видят 0 до ${board?.season?.zeroUntil || 'конца окна'}.`
        : `Сохранено. В этом топе теперь ${fmt(shown)}.`)
      dirtyRef.current = false
      try {
        await refreshBoard()
        const fresh = await fetchStatPerson({
          metric: metric.id,
          user_id: userId,
          period,
          chat_id: chat?.chatId || 0,
        })
        setPerson(fresh)
        setDraft(draftFrom(metric, fresh))
      } catch {
        setRowError('Число записано. Если список не изменился, откройте этот срок ещё раз.')
      }
    } catch (err) {
      setRowError(err.message || 'Сохранить не удалось')
    } finally {
      setSaving(false)
    }
  }

  const copySeason = async () => {
    if (!metric) return
    setSeasonBusy('copy')
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
      await refreshBoard()
    } catch (err) {
      setError(err.message || 'Скопировать не удалось')
    } finally {
      setSeasonBusy('')
    }
  }

  const clearSeason = async () => {
    if (!metric) return
    if (!window.confirm('Убрать копию? Люди сразу снова увидят числа из базы.')) return
    setSeasonBusy('clear')
    setError('')
    try {
      await clearStatSeason({ metric: metric.id, chat_id: chat?.chatId || 0 })
      setNotice('Копия убрана. Топ снова показывает базу.')
      await refreshBoard()
    } catch (err) {
      setError(err.message || 'Убрать копию не удалось')
    } finally {
      setSeasonBusy('')
    }
  }

  const season = boardReady ? board.season : null
  const editor = showPeople && userId ? (
    <StatEditor
      metric={metric}
      period={period}
      person={person}
      draft={draft}
      onDraft={editDraft}
      onSubmit={save}
      saving={saving}
      error={rowError}
    />
  ) : null

  return (
    <div className="sec-tab-body stat-desk">
      <p className="realm-copy">
        Один срок — один топ, такой же, как в чате. Число правится в строке и сразу записывается в этот топ.
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

      {metric && metric.periods.length > 1 && (
        <div className="stat-periods" role="tablist" aria-label="Срок статистики">
          {metric.periods.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={period === item.id}
              className={`stat-period${period === item.id ? ' is-on' : ''}`}
              onClick={() => pickPeriod(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
      {metric?.id === 'messages' && (
        <p className="realm-copy">День, неделя, месяц, год и всё время считаются отдельно. Сейчас на экране только выбранный срок.</p>
      )}
      {metric?.id === 'players' && (
        <p className="realm-copy">За всё время топ складывает победы и проигрыши. День, неделя, месяц и год считают только свои игры.</p>
      )}

      {metric?.needsGroup && !chat && (
        <div className="stat-group">
          <label className="staff-ga-field">Группа за этот срок
            <input
              className="sec-input"
              value={groupQuery}
              placeholder="ID, @username или имя группы"
              autoComplete="off"
              onChange={(event) => setGroupQuery(event.target.value)}
            />
          </label>
          {loadingGroups && !groupsReady && <p className="stat-loading">Считаю группы…</p>}
          {groupsReady && groupItems.length === 0 && (
            <p className="realm-copy">
              {groupQuery.trim()
                ? 'Такой группы нет. Проверьте имя, @username или ID.'
                : 'За этот срок в группах пока нет сообщений. Выберите другой срок или найдите группу по имени.'}
            </p>
          )}
          {groupItems.length > 0 && (
            <ul className="stat-picks">
              {groupItems.map((item) => (
                <li key={item.chatId}>
                  <button
                    type="button"
                    onClick={() => {
                      boardToken.current += 1
                      setChat(item)
                      setBoard(null)
                      setUserId(null)
                      setPerson(null)
                      setDraft({})
                      setNotice('')
                      setRowError('')
                    }}
                  >
                    <span>
                      <strong>{item.title}</strong>
                      <i>{item.username ? `@${item.username}` : item.chatId}</i>
                    </span>
                    {item.amount != null && <em>{fmt(item.amount)} сообщений</em>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {metric?.needsGroup && chat && (
        <div className="stat-chosen">
          <span>
            <strong>{chat.title}</strong>
            <i>{chat.username ? `@${chat.username}` : chat.chatId}</i>
          </span>
          <button type="button" className="sec-btn sec-btn-ghost" onClick={leaveGroup}>Все группы</button>
        </div>
      )}

      {showPeople && (
        <section className="stat-board" aria-busy={loadingBoard}>
          <h3 className="realm-h">
            {metric.title}{boardReady && board.periodLabel ? ` · ${board.periodLabel}` : ''}
          </h3>
          {season?.phase === 'zero' && (
            <p className="realm-note">До {season.zeroUntil} люди видят нули. Рядом с нулём написано число в базе.</p>
          )}
          {boardReady && board.total != null && (
            <p className="realm-copy">Всего за этот срок: {fmt(board.total)}</p>
          )}
          {loadingBoard && !boardReady && <p className="stat-loading">Считаю этот топ…</p>}
          {boardReady && rows.length === 0 && (
            <p className="realm-copy">В этом топе пока никого. Ниже можно найти человека и задать число.</p>
          )}
          <ol className="stat-rows">
            {rows.map((row) => {
              const open = Number(userId) === Number(row.userId)
              return (
                <li key={row.userId} className={`stat-row${open ? ' is-open' : ''}`}>
                  <button type="button" aria-pressed={open} onClick={() => openPerson(row)}>
                    <b>{row.place}</b>
                    <span>
                      <strong>{row.name}</strong>
                      {row.username ? <i>@{row.username}</i> : null}
                    </span>
                    <em>
                      {fmt(row.seen)} {board.rowUnit || metric.rowUnit}
                      {row.raw !== row.seen ? <small>в базе {fmt(row.raw)}</small> : null}
                    </em>
                  </button>
                  {open && editor}
                </li>
              )
            })}
          </ol>
          {boardReady && userId && !rows.some((row) => Number(row.userId) === Number(userId)) && (
            <div className="stat-row is-open stat-outside">
              <p className="realm-copy">{person?.name || 'Человек'}{person?.username ? ` · @${person.username}` : ''}</p>
              {editor}
            </div>
          )}
          {boardReady && (
            <div className="stat-add">
              <p className="realm-copy">Нет в списке — найдите человека и задайте число в этом же топе.</p>
              <UserLookupPreview
                value={personText}
                onChange={setPersonText}
                onResolved={chooseFound}
                placeholder="ID, @username или имя"
                label="Человек"
              />
            </div>
          )}
        </section>
      )}

      {showPeople && (
        <details className="stat-season">
          <summary>Копия на даты</summary>
          <p className="realm-copy">
            С выбранной даты по выбранную люди видят нули. После конечной даты сохранённая копия и то, что прибавилось с момента копии, складываются.
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
            <button type="button" className="sec-btn" disabled={!zeroFrom || !zeroUntil || seasonBusy === 'copy'} onClick={copySeason}>
              {seasonBusy === 'copy' ? 'Копирую…' : 'Скопировать'}
            </button>
            {season && (
              <button type="button" className="sec-btn sec-btn-ghost" disabled={seasonBusy === 'clear'} onClick={clearSeason}>
                Убрать копию
              </button>
            )}
          </div>
        </details>
      )}
    </div>
  )
}
