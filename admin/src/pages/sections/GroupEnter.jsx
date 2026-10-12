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

export function GroupSeal({ title, onEnter }) {
  return (
    <button type="button" className="grp-door grp-seal" onClick={onEnter}>
      <span className="grp-seal-kicker">Панель администратора</span>
      <strong>{title || 'Группа'}</strong>
      <span className="grp-seal-line" aria-hidden="true" />
      <span className="grp-seal-go">Открываем кабинет</span>
    </button>
  )
}

export default function GroupEnter({ groups, onPick, leavingId = null }) {
  const leaving = leavingId != null
  return (
    <div className={`grp-door grp-enter${leaving ? ' is-leaving' : ''}`}>
      <div className="grp-door-glow" aria-hidden="true" />
      <div className="grp-enter-card">
        <p className="grp-enter-kicker">Панель администратора</p>
        <h1>Ваши группы</h1>
        <p>Выберите группу, в которой у вас должность. Кабинет откроется в ней.</p>
        <ul>
          {(groups || []).map((group, index) => {
            const chosen = leavingId === group.chatId
            return (
              <li
                key={group.chatId}
                className={chosen ? 'is-chosen' : ''}
                style={{ animationDelay: `${70 + Math.min(index, 7) * 46}ms` }}
              >
                <button
                  type="button"
                  disabled={leaving && !chosen}
                  onClick={() => onPick(group.chatId)}
                >
                  <strong>{group.title || 'Группа'}</strong>
                  <span>{group.position || 'Должность'}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
