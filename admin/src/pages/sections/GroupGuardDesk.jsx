import { useEffect, useMemo, useState } from 'react'
import { addGuardAllow, fetchGuardDesk, removeGuardAllow, saveGroupGuard, saveGuardPolicy } from '../../lib/adminClient'
import RightSwitch from '../../components/RightSwitch'
import GroupLookupPreview from '../../components/GroupLookupPreview'

const KINDS = { link: 'Ссылка', flood: 'Флуд', captcha: 'Капча' }

function ruleLine(row) {
  return [
    row.captcha ? 'Капча включена' : 'Капча выключена',
    row.links ? 'ссылки удаляются' : 'ссылки проходят',
    row.flood ? 'флуд удаляется' : 'флуд проходит',
  ].join('. ') + '.'
}

function hourLabel(hour) {
  const value = Number(hour)
  const safe = Number.isFinite(value) ? ((value % 24) + 24) % 24 : 9
  return `${String(safe).padStart(2, '0')}:00`
}

/** Нормализация поиска: strip @, извлечь t.me/xxx, оставить id/текст. */
function normalizeGroupQuery(raw) {
  let text = String(raw || '').trim().toLowerCase()
  if (!text) return ''
  text = text.replace(/^@+/, '')
  const tme = text.match(/(?:https?:\/\/)?(?:t\.me|telegram\.me)\/(?:c\/)?([+\w.-]+)/i)
  if (tme) {
    const token = tme[1].replace(/^@/, '')
    if (/^\d+$/.test(token)) return `-100${token}`
    return token.toLowerCase()
  }
  return text.replace(/^https?:\/\//, '').replace(/\/+$/, '')
}

function groupMatchesQuery(item, query) {
  const q = normalizeGroupQuery(query)
  if (!q) return true
  const title = String(item.title || '').toLowerCase()
  const chatId = String(item.chatId ?? '')
  const username = String(item.username || '').replace(/^@/, '').toLowerCase()
  return title.includes(q) || chatId.includes(q) || (username && (username.includes(q) || `@${username}`.includes(q)))
}

export default function GroupGuardDesk() {
  const [pack, setPack] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')
  const [query, setQuery] = useState('')
  const [openId, setOpenId] = useState(null)
  const [userId, setUserId] = useState('')
  const [note, setNote] = useState('')

  const load = () => {
    setError('')
    return fetchGuardDesk()
      .then((data) => setPack(data))
      .catch((err) => setError(err.message || 'Правила не открылись'))
  }

  useEffect(() => { load() }, [])

  const policy = pack?.policy || { captcha: true, links: false, flood: false, morning: true, morningHour: 9 }
  const groups = pack?.groups || []
  const customCount = groups.filter((item) => item.custom).length
  const shown = useMemo(() => {
    if (!query.trim()) return groups
    return groups.filter((item) => groupMatchesQuery(item, query))
  }, [groups, query])

  const run = async (key, job) => {
    setBusy(key)
    setError('')
    setNotice('')
    try {
      const data = await job()
      if (data?.policy) setPack(data)
      else setPack(await fetchGuardDesk())
      setNotice('Сохранено')
    } catch (err) {
      setError(err.message || 'Не сохранилось. Повторите.')
    } finally {
      setBusy('')
    }
  }

  const savePolicy = (next) => run('policy', () => saveGuardPolicy(next))

  return (
    <article className="panel-shelf panel-shelf-page guard-desk">
      <header className="guard-head">
        <h2 className="panel-page-title">Защита групп</h2>
        <p className="realm-copy guard-sub">
          Общее правило сверху. Ниже — своё для отдельных групп и люди, которых бот не удаляет.
        </p>
      </header>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {notice && !error && <p className="realm-copy">{notice}</p>}
      {!pack && !error && <p className="realm-copy">Открываю правила…</p>}

      <section className="guard-block">
        <h3>Для всех групп</h3>
        <p className="realm-copy">
          {customCount
            ? `Своё правило останется у ${customCount}. Остальные группы повторят то, что вы включите здесь.`
            : 'Своего правила пока ни у кого нет. Переключатель меняет все официальные группы сразу.'}
        </p>
        <RightSwitch
          on={Boolean(policy.captcha)}
          disabled={!pack || busy === 'policy'}
          title="Капча"
          hint="Новый человек проходит проверку, прежде чем писать"
          onChange={(value) => savePolicy({ ...policy, captcha: value })}
        />
        <RightSwitch
          on={Boolean(policy.links)}
          disabled={!pack || busy === 'policy'}
          title="Ссылки и пересылки"
          hint="Чужие ссылки и пересланные сообщения бот убирает"
          onChange={(value) => savePolicy({ ...policy, links: value })}
        />
        <RightSwitch
          on={Boolean(policy.flood)}
          disabled={!pack || busy === 'policy'}
          title="Антифлуд"
          hint="Шесть сообщений за восемь секунд бот убирает"
          onChange={(value) => savePolicy({ ...policy, flood: value })}
        />
        <RightSwitch
          on={Boolean(policy.morning)}
          disabled={!pack || busy === 'policy'}
          title="Утренняя личка"
          hint="Администраторам группы приходит сводка: сегодня, вчера и кто на двух предупреждениях из трёх"
          onChange={(value) => savePolicy({ ...policy, morning: value })}
        />
        <div className="guard-hour">
          <button
            type="button"
            className="realm-back"
            disabled={!pack || !policy.morning || busy === 'policy'}
            onClick={() => savePolicy({ ...policy, morningHour: (Number(policy.morningHour) + 23) % 24 })}
          >
            Раньше
          </button>
          <label className="guard-hour-manual">
            <span className="visually-hidden">Час рассылки</span>
            <input
              className="guard-field guard-hour-input"
              type="time"
              step={3600}
              value={hourLabel(policy.morningHour)}
              disabled={!pack || !policy.morning || busy === 'policy'}
              onChange={(event) => {
                const raw = String(event.target.value || '')
                const hour = Number(raw.split(':')[0])
                if (!Number.isFinite(hour) || hour < 0 || hour > 23) return
                savePolicy({ ...policy, morningHour: hour })
              }}
              aria-label="Время утренней сводки"
            />
            <input
              className="guard-field guard-hour-num"
              type="number"
              min={0}
              max={23}
              inputMode="numeric"
              value={Number(policy.morningHour) % 24}
              disabled={!pack || !policy.morning || busy === 'policy'}
              onChange={(event) => {
                const hour = Number(event.target.value)
                if (!Number.isFinite(hour) || hour < 0 || hour > 23) return
                savePolicy({ ...policy, morningHour: Math.round(hour) })
              }}
              aria-label="Час сводки вручную, 0–23"
              title="Час 0–23"
            />
          </label>
          <button
            type="button"
            className="realm-back"
            disabled={!pack || !policy.morning || busy === 'policy'}
            onClick={() => savePolicy({ ...policy, morningHour: (Number(policy.morningHour) + 1) % 24 })}
          >
            Позже
          </button>
          <span>по времени сервера · {hourLabel(policy.morningHour)}</span>
        </div>
      </section>

      <section className="guard-block guard-block-custom">
        <h3>Своё правило</h3>
        <p className="realm-copy">Группа из этого списка может отличаться от общего. «Как у всех» возвращает её обратно.</p>
        <div className="guard-lookup">
          <GroupLookupPreview
            value={query}
            onChange={setQuery}
            onResolved={(row) => {
              if (!row) return
              const id = Number(row.chat_id ?? row.chatId)
              if (Number.isFinite(id)) setOpenId(id)
            }}
            label="Найти группу"
            placeholder="Id, @username, ссылка t.me или название"
          />
        </div>
        {pack && shown.length === 0 && <p className="realm-copy">Таких групп нет.</p>}
        <ul className="guard-groups">
          {shown.map((item) => (
            <li key={item.chatId} className="guard-group">
              <h3>{item.title}</h3>
              <p className="guard-meta">
                {item.username ? `@${item.username} · ` : ''}#{item.chatId}
                {' · '}{item.custom ? 'Своё правило. ' : 'Как у всех. '}{ruleLine(item)}
              </p>
              <div className="guard-tools">
                <button type="button" className="realm-back" onClick={() => setOpenId(openId === item.chatId ? null : item.chatId)}>
                  {openId === item.chatId ? 'Скрыть' : 'Изменить только эту'}
                </button>
                {item.custom && (
                  <button
                    type="button"
                    className="realm-back"
                    disabled={busy === item.chatId}
                    onClick={() => run(item.chatId, () => saveGroupGuard(item.chatId, { follow: true }))}
                  >
                    Как у всех
                  </button>
                )}
              </div>
              {openId === item.chatId && (
                <div className="guard-open">
                  <RightSwitch
                    on={Boolean(item.captcha)}
                    disabled={busy === item.chatId}
                    title="Капча в этой группе"
                    hint="Только здесь, общее правило не изменится"
                    onChange={(value) => run(item.chatId, () => saveGroupGuard(item.chatId, { captcha: value, links: item.links, flood: item.flood }))}
                  />
                  <RightSwitch
                    on={Boolean(item.links)}
                    disabled={busy === item.chatId}
                    title="Ссылки в этой группе"
                    hint="Только здесь"
                    onChange={(value) => run(item.chatId, () => saveGroupGuard(item.chatId, { captcha: item.captcha, links: value, flood: item.flood }))}
                  />
                  <RightSwitch
                    on={Boolean(item.flood)}
                    disabled={busy === item.chatId}
                    title="Антифлуд в этой группе"
                    hint="Только здесь"
                    onChange={(value) => run(item.chatId, () => saveGroupGuard(item.chatId, { captcha: item.captcha, links: item.links, flood: value }))}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="guard-block">
        <h3>Кого бот не удаляет</h3>
        <p className="realm-copy">
          Должность защищает только в своей группе. Человек из этого списка может писать ссылки и не проходит капчу во всех официальных группах. Пометка нужна, чтобы потом вспомнить, для чего он здесь.
        </p>
        <form
          className="guard-tools"
          onSubmit={(event) => {
            event.preventDefault()
            const id = Number(String(userId).trim())
            if (!Number.isFinite(id) || id <= 0) {
              setError('Напишите числовой id человека')
              return
            }
            run('allow', async () => {
              const data = await addGuardAllow(id, note.trim())
              setUserId('')
              setNote('')
              return data
            })
          }}
        >
          <input
            className="guard-field"
            inputMode="numeric"
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            placeholder="Id человека"
            aria-label="Id человека"
          />
          <input
            className="guard-field"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="для чего?"
            aria-label="для чего?"
            maxLength={80}
          />
          <button type="submit" className="realm-back" disabled={busy === 'allow'}>Добавить</button>
        </form>
        {(pack?.allow || []).length === 0 && pack && <p className="realm-copy">Список пуст.</p>}
        <ul className="guard-groups">
          {(pack?.allow || []).map((person) => (
            <li key={person.userId} className="guard-person">
              <strong>{person.name || 'Без имени'} · #{person.userId}</strong>
              <span>{person.note}</span>
              <button type="button" className="realm-back" disabled={busy === person.userId} onClick={() => run(person.userId, () => removeGuardAllow(person.userId))}>
                Убрать
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="guard-block">
        <h3>Кого поймали</h3>
        {(pack?.hits || []).length === 0 && pack && <p className="realm-copy">Пока пусто.</p>}
        <ul className="guard-groups">
          {(pack?.hits || []).map((hit, index) => (
            <li key={`${hit.at || index}-${hit.userId || index}`} className="guard-person">
              <strong>{hit.title || 'Группа'}</strong>
              <span>{KINDS[hit.kind] || hit.kind} · {hit.userId ? `#${hit.userId}` : '—'} {hit.detail || ''}</span>
            </li>
          ))}
        </ul>
      </section>
    </article>
  )
}
