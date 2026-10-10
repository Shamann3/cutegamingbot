export default function EverywhereSeat({ on, onChange }) {
  return (
    <button
      type="button"
      className={`seat-everywhere${on ? ' is-on' : ''}`}
      aria-pressed={on}
      onClick={() => onChange(!on)}
    >
      <span className="seat-everywhere-dot" aria-hidden="true" />
      <span>{on ? 'Сразу во все официальные группы' : 'Только эта группа'}</span>
    </button>
  )
}
