import { useEffect, useState } from 'react'
import { REALM_RIGHTS } from '../lib/realmRights'

export default function PositionEditor({ positions, creator, onSave, savingId }) {
  const [drafts, setDrafts] = useState(positions || [])

  useEffect(() => {
    setDrafts(positions || [])
  }, [positions])

  const patch = (id, next) => {
    setDrafts((rows) => rows.map((row) => (row.id === id ? { ...row, ...next } : row)))
  }

  if (!drafts.length) {
    return <p className="realm-copy">Должностей в этой группе ещё нет. Сначала отметьте группу официальной.</p>
  }

  return (
    <div className="realm-positions">
      {drafts.map((row) => {
        const locked = row.rank >= 5
        const rights = new Set(row.rights || [])
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
            <p className="realm-copy">{locked ? 'Создатель группы. Права полные и не снимаются.' : `Ранг ${row.rank}. Наказать можно только тех, кто младше.`}</p>
            {!locked && (
              <div className="realm-right-grid">
                {REALM_RIGHTS.filter((item) => creator || item.id !== 'manage_positions').map((item) => (
                  <label key={item.id} className="realm-check">
                    <input
                      type="checkbox"
                      checked={rights.has(item.id)}
                      onChange={(event) => {
                        const next = new Set(rights)
                        if (event.target.checked) next.add(item.id)
                        else next.delete(item.id)
                        patch(row.id, { rights: [...next] })
                      }}
                    />
                    {item.label}
                  </label>
                ))}
              </div>
            )}
            <button type="submit" className="realm-back" disabled={savingId === row.id || row.title.trim().length < 2}>
              {savingId === row.id ? 'Запись…' : 'Сохранить должность'}
            </button>
          </form>
        )
      })}
    </div>
  )
}
