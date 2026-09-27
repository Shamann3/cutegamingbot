import { useEffect, useMemo, useState } from 'react'
import { PAGE_RIGHTS, PUNISH_RIGHTS, TELEGRAM_ADMIN_RIGHTS } from '../lib/realmRights'
import RightSwitch from './RightSwitch'

function RightList({ items, rights, locked, onToggle, compareSet }) {
  return (
    <div className="realm-right-grid">
      {items.map((item) => {
        const on = rights.has(item.id)
        const lowerOn = compareSet ? compareSet.has(item.id) : null
        const hint = [
          item.hint,
          lowerOn === true && !on ? 'У младшей должности включено' : null,
          lowerOn === false && on ? 'У младшей должности выключено' : null,
        ].filter(Boolean).join(' · ')
        return (
          <RightSwitch
            key={item.id}
            on={on}
            disabled={locked}
            title={item.label}
            hint={hint}
            onChange={(next) => onToggle(item.id, next)}
          />
        )
      })}
    </div>
  )
}

function lowerRankPeer(positions, rank) {
  const juniors = (positions || [])
    .filter((row) => Number(row.rank) < Number(rank))
    .sort((a, b) => Number(b.rank) - Number(a.rank))
  return juniors[0] || null
}

export default function PositionEditor({ positions, creator, onSave, savingId }) {
  const [drafts, setDrafts] = useState(positions || [])

  useEffect(() => {
    setDrafts(positions || [])
  }, [positions])

  const byId = useMemo(() => {
    const map = new Map()
    for (const row of drafts) map.set(row.id, row)
    return map
  }, [drafts])

  const patch = (id, next) => {
    setDrafts((rows) => rows.map((row) => (row.id === id ? { ...row, ...next } : row)))
  }

  if (!drafts.length) {
    return <p className="realm-copy">Должностей пока нет. Создайте свою или отметьте группу официальной.</p>
  }

  return (
    <div className="realm-positions">
      {drafts.map((row) => {
        const locked = row.rank >= 5
        const rights = new Set(row.rights || [])
        const pages = PAGE_RIGHTS.filter((item) => creator || item.id !== 'manage_positions')
        const peer = lowerRankPeer(drafts, row.rank)
        const compareSet = peer ? new Set(byId.get(peer.id)?.rights || peer.rights || []) : null
        const toggle = (rightId, on) => {
          const next = new Set(rights)
          if (on) next.add(rightId)
          else next.delete(rightId)
          patch(row.id, { rights: [...next] })
        }
        return (
          <form
            key={row.id}
            className="realm-form"
            onSubmit={(event) => {
              event.preventDefault()
              onSave(row)
            }}
          >
            <label>
              Название
              <input
                value={row.title}
                onChange={(event) => patch(row.id, { title: event.target.value })}
              />
            </label>
            <p className="realm-copy">
              {locked
                ? 'Создатель группы. Страницы и наказания полные, снять их нельзя.'
                : `Ранг ${row.rank}. Обзор и «Ещё» есть всегда. Наказать можно только младшего.`}
            </p>
            {peer && (
              <p className="realm-note" role="status">
                Ориентир — младшая должность «{peer.title}» (ранг {peer.rank}): серые подсказки
                показывают, что у неё уже включено или ещё нет.
              </p>
            )}
            {!peer && Number(row.rank) > 0 && (
              <p className="realm-copy">Ниже по рангу должностей нет — сравнивать не с чем.</p>
            )}
            <fieldset className="realm-rights-block" disabled={locked}>
              <legend>Страницы кабинета</legend>
              <RightList items={pages} rights={rights} locked={locked} onToggle={toggle} compareSet={compareSet} />
            </fieldset>
            <fieldset className="realm-rights-block" disabled={locked}>
              <legend>Наказания в этом чате</legend>
              <p className="realm-copy">Любое наказание само открывает страницу «Активность».</p>
              <RightList items={PUNISH_RIGHTS} rights={rights} locked={locked} onToggle={toggle} compareSet={compareSet} />
            </fieldset>
            <fieldset className="realm-rights-block" disabled={locked}>
              <legend>Права Telegram в чате</legend>
              <p className="realm-copy">Как у администратора Telegram. Передачу владения сюда не ставим.</p>
              <RightList
                items={TELEGRAM_ADMIN_RIGHTS}
                rights={rights}
                locked={locked}
                onToggle={toggle}
                compareSet={compareSet}
              />
            </fieldset>
            <button type="submit" className="realm-back" disabled={savingId === row.id || row.title.trim().length < 2}>
              {savingId === row.id ? 'Запись…' : 'Сохранить должность'}
            </button>
          </form>
        )
      })}
    </div>
  )
}
