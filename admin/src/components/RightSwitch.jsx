export default function RightSwitch({ on, disabled, title, hint, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      disabled={disabled}
      className={on ? 'realm-switch is-on' : 'realm-switch'}
      onClick={() => onChange(!on)}
    >
      <span className="realm-switch-track" aria-hidden="true">
        <span className="realm-switch-knob" />
      </span>
      <span className="realm-switch-copy">
        <strong>{title}</strong>
        {hint ? <em>{hint}</em> : null}
      </span>
    </button>
  )
}
