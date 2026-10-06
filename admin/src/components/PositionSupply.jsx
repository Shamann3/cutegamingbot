import { useEffect, useMemo, useState } from 'react'
import FocusWindow from './FocusWindow'
import { copyGroupPositions, fetchPositionTemplates, fetchRightsBoard, placePositionTemplate } from '../lib/adminClient'
import { placeBlock, supplyNotice } from '../lib/positionSupply'

function targetShape(group) {
  const rows = group?.positions || []
  return {
    titles: rows.map((row) => row.title),
    kinds: rows.map((row) => row.kind),
  }
}

export default function PositionSupply({ chatId, onPlaced }) {
  const [open, setOpen] = useState('')
  const [groups, setGroups] = useState([])
  const [templates, setTemplates] = useState([])
  const [sourceId, setSourceId] = useState(null)
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState(() => new Set())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  useEffect(() => {
    if (!open) return undefined
    let stop = false
    setError('')
    const load = async () => {
      try {
        const board = await fetchRightsBoard()
        if (stop) return
        const items = board.groups || []
        setGroups(items)
        const others = items.filter((group) => Number(group.chatId) !== Number(chatId))
        setSourceId((current) => (
          others.some((group) => Number(group.chatId) === Number(current))
            ? current
            : (others[0]?.chatId ?? null)
        ))
        if (open === 'kit') {
          const pack = await fetchPositionTemplates()
          if (!stop) setTemplates(pack.templates || [])
        }
      } catch (err) {
        if (!stop) setError(err.message || 'Список групп не открылся')
      }
    }
    load()
    return () => { stop = true }
  }, [open, chatId])

  const target = groups.find((group) => Number(group.chatId) === Number(chatId)) || null
  const shape = targetShape(target)
  const sources = groups.filter((group) => Number(group.chatId) !== Number(chatId))
  const source = sources.find((group) => Number(group.chatId) === Number(sourceId)) || null
  const needle = query.trim().toLowerCase()
  const visibleSources = sources.filter((group) => String(group.title || '').toLowerCase().includes(needle))

  const choices = useMemo(() => (source?.positions || []).map((row) => ({
    ...row,
    block: placeBlock({
      title: row.title,
      kind: row.kind,
      rank: row.rank,
      targetTitles: shape.titles,
      targetKinds: shape.kinds,
    }),
  })), [source, shape.titles, shape.kinds])

  const close = () => {
    setOpen('')
    setError('')
    setBusy('')
    setPicked(new Set())
    setQuery('')
  }

  const finish = async (data, verb) => {
    const text = supplyNotice(data, verb)
    if ((data?.placed || []).length) {
      close()
      await onPlaced?.(text)
      return
    }
    setError(text || 'Ничего не изменилось')
  }

  const placeTemplate = async (card) => {
    setBusy(card.id)
    setError('')
    try {
      const data = await placePositionTemplate({ chat_id: Number(chatId), template_id: card.id })
      await finish(data, 'Поставлена должность')
    } catch (err) {
      setError(err.message || 'Заготовка не встала')
    } finally {
      setBusy('')
    }
  }

  const copyPicked = async () => {
    const ids = [...picked]
    if (!source || !ids.length) return
    setBusy('copy')
    setError('')
    try {
      const data = await copyGroupPositions({
        chat_id: Number(chatId),
        source_chat_id: Number(source.chatId),
        ids,
      })
      await finish(data, ids.length === 1 ? 'Перенесена должность' : 'Перенесены должности')
    } catch (err) {
      setError(err.message || 'Должности не перенеслись')
    } finally {
      setBusy('')
    }
  }

  const takeAll = () => {
    setPicked(new Set(choices.filter((row) => !row.block).map((row) => row.id)))
  }

  if (!chatId) return null

  return (
    <div className="position-supply">
      <p className="realm-copy">Заготовки не стоят в группе сами. Их ставят, когда нужны. Готовые должности можно перенести из другой официальной группы: переносятся название и права, люди остаются на своих местах.</p>
      <div className="position-supply-actions">
        <button type="button" className="sec-btn" onClick={() => setOpen('kit')}>Заготовки</button>
        <button type="button" className="sec-btn" onClick={() => setOpen('copy')}>Из другой группы</button>
      </div>
      {open === 'kit' && (
        <FocusWindow
          title="Заготовки должностей"
          subtitle="Они не создаются вместе с группой. Кнопка ставит заготовку только в открытую группу и никого на неё не сажает."
          onClose={close}
        >
          {error && <p className="realm-alert" role="alert">{error}</p>}
          {templates.map((card) => {
            const block = placeBlock({
              title: card.title,
              kind: card.kind,
              rank: card.rank,
              targetTitles: shape.titles,
              targetKinds: shape.kinds,
            })
            return (
              <article key={card.id} className="supply-card">
                <h3>{card.title}</h3>
                <p>{card.blurb}</p>
                {block ? <p>{block}</p> : null}
                <button
                  type="button"
                  className="sec-btn"
                  disabled={Boolean(block) || busy === card.id}
                  aria-label={`Поставить ${card.title}`}
                  onClick={() => placeTemplate(card)}
                >
                  {busy === card.id ? 'Ставим…' : (block ? 'Уже стоит' : 'Поставить в эту группу')}
                </button>
              </article>
            )
          })}
          {!templates.length && !error && <p className="realm-copy">Заготовки открываются…</p>}
        </FocusWindow>
      )}
      {open === 'copy' && (
        <FocusWindow
          title="Перенести должности"
          subtitle="Название, права и вкладки. Люди остаются в прежней группе. Создатель группы не копируется."
          onClose={close}
          footer={(
            <button type="button" className="sec-btn is-on" disabled={!picked.size || busy === 'copy'} onClick={copyPicked}>
              {busy === 'copy' ? 'Переносим…' : (picked.size ? `Перенести выбранные · ${picked.size}` : 'Перенести выбранные')}
            </button>
          )}
        >
          {error && <p className="realm-alert" role="alert">{error}</p>}
          {!sources.length && !error && (
            <p className="realm-copy">Других официальных групп нет. Их добавляют во вкладке «Группы».</p>
          )}
          {sources.length > 0 && (
            <>
              <label className="realm-field">Откуда
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название группы" />
              </label>
              <ul className="realm-list">
                {visibleSources.map((group) => (
                  <li key={group.chatId}>
                    <button
                      type="button"
                      className={Number(group.chatId) === Number(sourceId) ? 'is-on' : ''}
                      onClick={() => { setSourceId(group.chatId); setPicked(new Set()) }}
                    >
                      <strong>{group.title}</strong>
                      <span>{group.positions?.length || 0} должностей</span>
                    </button>
                  </li>
                ))}
              </ul>
              {source && (
                <>
                  <div className="position-supply-actions">
                    <button type="button" className="sec-btn" onClick={takeAll}>Выбрать все, которые можно</button>
                  </div>
                  {choices.map((row) => (
                    row.block ? (
                      <p key={row.id} className="supply-skip">
                        <strong>{row.title}</strong>
                        <span>{row.block}</span>
                      </p>
                    ) : (
                      <button
                        key={row.id}
                        type="button"
                        className={`seat-pick${picked.has(row.id) ? ' is-on' : ''}`}
                        aria-pressed={picked.has(row.id)}
                        onClick={() => {
                          setPicked((current) => {
                            const next = new Set(current)
                            if (next.has(row.id)) next.delete(row.id)
                            else next.add(row.id)
                            return next
                          })
                        }}
                      >
                        <strong>{row.title}</strong>
                        <span>{row.kind === 'spamblock' ? 'спам-блок' : (row.kind === 'member' ? 'ранг 0' : `ранг ${row.rank}`)}</span>
                      </button>
                    )
                  ))}
                  {!choices.length && <p className="realm-copy">В этой группе нет должностей.</p>}
                </>
              )}
            </>
          )}
        </FocusWindow>
      )}
    </div>
  )
}
