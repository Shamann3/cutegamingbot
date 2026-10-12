export function cabinetNeedsGroupPick(groupCount, preview) {
  return !preview && Number(groupCount) > 1
}

/** list — несколько групп, seal — вход в выбранную, in — кабинет. */
export function cabinetArrival(groupCount, preview) {
  if (preview) return 'in'
  if (cabinetNeedsGroupPick(groupCount, preview)) return 'list'
  if (Number(groupCount) === 1) return 'seal'
  return 'in'
}

export function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** После выбора группы: список собирается, затем печать, затем кабинет. */
export const ENTRANCE_LEAVE_MS = 700
export const ENTRANCE_SEAL_MS = 1040

export function entrancePace() {
  if (prefersReducedMotion()) return { leave: 0, seal: 0 }
  if (typeof document !== 'undefined' && document.body.classList.contains('perf-light')) {
    return { leave: 360, seal: 520 }
  }
  return { leave: ENTRANCE_LEAVE_MS, seal: ENTRANCE_SEAL_MS }
}

export function GroupSeal({ title, position, onEnter }) {
  const role = String(position || '').trim()
  return (
    <button type="button" className="grp-door grp-seal" onClick={onEnter}>
      <span className="grp-seal-kicker">Панель администратора</span>
      <strong>{title || 'Группа'}</strong>
      <span className="grp-seal-line" aria-hidden="true" />
      {role ? <span className="grp-seal-role">{role}</span> : null}
      <span className="grp-seal-go">Открываем кабинет</span>
      <span className="grp-seal-track" aria-hidden="true"><i /></span>
    </button>
  )
}

export default function GroupEnter({ groups, onPick, leavingId = null }) {
  const leaving = leavingId != null
  const list = groups || []
  const chosenIndex = leaving ? list.findIndex((group) => group.chatId === leavingId) : -1
  return (
    <div className={`grp-door grp-enter${leaving ? ' is-leaving' : ''}`}>
      <div className="grp-door-glow" aria-hidden="true" />
      <div className="grp-enter-card">
        <p className="grp-enter-kicker">Панель администратора</p>
        <h1>Ваши группы</h1>
        <p>Выберите группу, в которой у вас должность. Кабинет откроется в ней.</p>
        <ul>
          {list.map((group, index) => {
            const chosen = leavingId === group.chatId
            const delay = leaving
              ? (chosen ? 50 : Math.min(Math.abs(index - Math.max(chosenIndex, 0)), 4) * 42)
              : 70 + Math.min(index, 7) * 46
            return (
              <li
                key={group.chatId}
                className={chosen ? 'is-chosen' : ''}
                style={{ animationDelay: `${delay}ms` }}
              >
                <button
                  type="button"
                  disabled={leaving && !chosen}
                  onClick={() => onPick(group.chatId)}
                >
                  <strong>{group.title || 'Группа'}</strong>
                  <span>{group.position || 'Должность'}</span>
                  {chosen ? <i className="grp-pick-line" aria-hidden="true" /> : null}
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
