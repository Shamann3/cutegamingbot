import { useEffect, useMemo, useState } from 'react'
import { PAGE_RIGHTS, PUNISH_RIGHTS, TELEGRAM_ADMIN_RIGHTS } from '../lib/realmRights'
import FocusWindow from './FocusWindow'
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

function toneOf(title, rank) {
  if (Number(rank) >= 5) return 'creator'
  const text = String(title || '').toLowerCase()
  if (text.includes('админ')) return 'admin'
  if (text.includes('модер')) return 'mod'
  if (text.includes('хелп') || text.includes('help')) return 'help'
  return 'seat'
}

export default function PositionEditor({ positions, creator, onSave, savingId, onPreview = null }) {
  const [drafts, setDrafts] = useState(positions || [])
  const [openId, setOpenId] = useState(null)

  useEffect(() => {
    setDrafts(positions || [])
  }, [positions])

  const byId = useMemo(() => {
    const map = new Map()
    for (const row of drafts) map.set(row.id, row)
    return map
  }, [drafts])

  const ordered = useMemo(
    () => [...drafts].sort((a, b) => Number(b.rank) - Number(a.rank)),
    [drafts],
  )

  const patch = (id, next) => {
    setDrafts((rows) => rows.map((row) => (row.id === id ? { ...row, ...next } : row)))
  }

  if (!drafts.length) {
    return <p className="realm-copy">Должностей пока нет. Создайте свою или отметьте группу официальной.</p>
  }

  const open = byId.get(openId) || null

  return (
    <div className="role-ladder">
      {ordered.map((row) => {
        const rights = new Set(row.rights || [])
        return (
          <button
            key={row.id}
            type="button"
            className={`role-card is-${toneOf(row.title, row.rank)}`}
            onClick={() => setOpenId(row.id)}
          >
            <span className="role-card-rank">Ранг {row.rank}</span>
            <strong>{row.title}</strong>
            <span>{rights.size} прав · нажать, чтобы настроить</span>
          </button>
        )
      })}
      {open && (
        <PositionSheet
          row={open}
          drafts={drafts}
          byId={byId}
          creator={creator}
          savingId={savingId}
          onPreview={creator ? onPreview : null}
          onClose={() => setOpenId(null)}
          onPatch={patch}
          onSave={onSave}
        />
      )}
    </div>
  )
}

function PositionSheet({ row, drafts, byId, creator, savingId, onClose, onPatch, onSave, onPreview }) {
  const locked = row.rank >= 5
  const rights = new Set(row.rights || [])
  const pages = PAGE_RIGHTS.filter((item) => creator || item.id !== 'manage_positions')
  const peer = lowerRankPeer(drafts, row.rank)
  const compareSet = peer ? new Set(byId.get(peer.id)?.rights || peer.rights || []) : null
  const toggle = (rightId, on) => {
    const next = new Set(rights)
    if (on) next.add(rightId)
    else next.delete(rightId)
    onPatch(row.id, { rights: [...next] })
  }

  return (
    <FocusWindow
      title={row.title || 'Должность'}
      subtitle={locked ? 'Создатель группы. Права полные, снять их нельзя.' : `Ранг ${row.rank}. Наказать можно только младшего.`}
      onClose={onClose}
    >
      <form
        className="realm-form role-sheet-form"
        onSubmit={(event) => {
          event.preventDefault()
          onSave(row)
        }}
      >
        <label>
          Название
          <input
            value={row.title}
            onChange={(event) => onPatch(row.id, { title: event.target.value })}
          />
        </label>
        {peer && (
          <p className="realm-note" role="status">
            Ориентир — младшая должность «{peer.title}» (ранг {peer.rank}).
          </p>
        )}
        <fieldset className="realm-rights-block" disabled={locked}>
          <legend>Страницы кабинета</legend>
          <RightList items={pages} rights={rights} locked={locked} onToggle={toggle} compareSet={compareSet} />
        </fieldset>
        <fieldset className="realm-rights-block" disabled={locked}>
          <legend>Наказания в этом чате</legend>
          <RightList items={PUNISH_RIGHTS} rights={rights} locked={locked} onToggle={toggle} compareSet={compareSet} />
        </fieldset>
        <fieldset className="realm-rights-block" disabled={locked}>
          <legend>Права Telegram в чате</legend>
          <RightList
            items={TELEGRAM_ADMIN_RIGHTS}
            rights={rights}
            locked={locked}
            onToggle={toggle}
            compareSet={compareSet}
          />
        </fieldset>
        {onPreview && (
          <button
            type="button"
            className="realm-back"
            onClick={() => onPreview(row)}
          >
            Открыть копию кабинета
          </button>
        )}
        <button type="submit" className="realm-back" disabled={savingId === row.id || row.title.trim().length < 2}>
          {savingId === row.id ? 'Запись…' : 'Сохранить должность'}
        </button>
      </form>
    </FocusWindow>
  )
}
