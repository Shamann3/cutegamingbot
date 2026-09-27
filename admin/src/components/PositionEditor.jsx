import { useEffect, useState } from 'react'
import { PAGE_RIGHTS, PUNISH_RIGHTS } from '../lib/realmRights'
import RightSwitch from './RightSwitch'

function RightList({ items, rights, locked, onToggle }) {
  return (
    <div className="realm-right-grid">
      {items.map((item) => (
        <RightSwitch
          key={item.id}
          on={rights.has(item.id)}
          disabled={locked}
          title={item.label}
          hint={item.hint}
          onChange={(next) => onToggle(item.id, next)}
        />
      ))}
    </div>
  )
}

export default function PositionEditor({ positions, creator, onSave, savingId }) {
  const [drafts, setDrafts] = useState(positions || [])

  useEffect(() => {
    setDrafts(positions || [])
  }, [positions])

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
            <fieldset className="realm-rights-block" disabled={locked}>
              <legend>Страницы кабинета</legend>
              <RightList items={pages} rights={rights} locked={locked} onToggle={toggle} />
            </fieldset>
            <fieldset className="realm-rights-block" disabled={locked}>
              <legend>Наказания в этом чате</legend>
              <p className="realm-copy">Любое наказание само открывает страницу «Активность».</p>
              <RightList items={PUNISH_RIGHTS} rights={rights} locked={locked} onToggle={toggle} />
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
