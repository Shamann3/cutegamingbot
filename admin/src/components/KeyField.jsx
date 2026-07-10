import { useState } from 'react'

function EyeIcon({ off }) {
  if (off) {
    return (
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
        <path
          d="M3 3l18 18M10.6 10.7a2 2 0 002.7 2.9M9.9 5.1A9.6 9.6 0 0112 5c5 0 9 4.5 9 7 0 1-.7 2.3-1.9 3.6M6.1 6.2C3.9 7.6 3 9.9 3 11c0 2.5 4 7 9 7 1.3 0 2.5-.3 3.6-.8"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
      <path
        d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="2.6" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

export default function KeyField({
  label,
  value,
  onChange,
  placeholder = 'Секретный ключ',
  disabled = false,
  name = 'key',
}) {
  const [show, setShow] = useState(false)
  return (
    <label className="auth-field">
      <span className="auth-label">{label}</span>
      <div className="auth-key-wrap">
        <input
          className="auth-input auth-key-input"
          name={name}
          type={show ? 'text' : 'password'}
          autoComplete="off"
          autoCorrect="off"
          spellCheck="false"
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          required
        />
        <button
          type="button"
          className={`auth-key-eye${show ? ' is-on' : ''}`}
          onClick={() => setShow((prev) => !prev)}
          aria-label={show ? 'Скрыть ключ' : 'Показать ключ'}
          tabIndex={-1}
        >
          <EyeIcon off={show} />
        </button>
      </div>
    </label>
  )
}
