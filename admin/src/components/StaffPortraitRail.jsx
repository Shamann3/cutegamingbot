const iconBase = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
}

function MedalIcon({ id }) {
  if (id === 'access' || id === 'tabs') {
    return (
      <svg {...iconBase}>
        <rect x="3.5" y="3.5" width="7" height="7" rx="1.4" />
        <rect x="13.5" y="3.5" width="7" height="7" rx="1.4" />
        <rect x="3.5" y="13.5" width="7" height="7" rx="1.4" />
        <rect x="13.5" y="13.5" width="7" height="7" rx="1.4" />
      </svg>
    )
  }
  if (id === 'tenure') {
    return (
      <svg {...iconBase}>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v4.2L15 16" />
      </svg>
    )
  }
  if (id === 'tickets' || id === 'replies') {
    return (
      <svg {...iconBase}>
        <path d="M5 6.5h14v9.2H9.2L5 19.5V6.5z" />
        <path d="M8.5 10h7M8.5 13h4.5" />
      </svg>
    )
  }
  if (id === 'tt_ok' || id === 'tt_no') {
    return (
      <svg {...iconBase}>
        <rect x="6" y="4" width="12" height="16" rx="3" />
        <path d="M10 8h4M9 12h6M9 16h4" />
      </svg>
    )
  }
  return (
    <svg {...iconBase}>
      <path d="M12 3.5l2.1 4.4 4.8.6-3.5 3.3.9 4.8L12 14.6 7.7 16.6l.9-4.8L5.1 8.5l4.8-.6L12 3.5z" />
    </svg>
  )
}

function SealMark() {
  return (
    <svg className="pu-staff-seal-svg" viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="13" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="16" cy="16" r="9.2" fill="none" stroke="currentColor" strokeWidth="1.1" opacity="0.55" />
      <path
        d="M16 9.2l1.55 3.35 3.7.42-2.75 2.55.74 3.65L16 17.4l-3.24 1.77.74-3.65-2.75-2.55 3.7-.42L16 9.2z"
        fill="currentColor"
      />
    </svg>
  )
}

/** Портрет сотрудника: только если API прислал staffPortrait. */
export default function StaffPortraitRail({ portrait }) {
  if (!portrait?.portrait) return null

  const achievements = Array.isArray(portrait.achievements) ? portrait.achievements : []
  const sections = Array.isArray(portrait.sections) ? portrait.sections : []

  return (
    <section className="pu-staff-rail" aria-label={`Администратор · ${portrait.roleLabel || ''}`}>
      <div className="pu-staff-rail-top">
        <div className="pu-staff-seal" title="Администратор проекта">
          <SealMark />
        </div>
        <div className="pu-staff-identity">
          <h3 className="pu-staff-role">{portrait.roleLabel || 'Администратор'}</h3>
          {portrait.tenureLabel && (
            <p className="pu-staff-tenure">
              в команде {portrait.tenureLabel}
              {portrait.hiredAt ? ` · с ${String(portrait.hiredAt).slice(0, 10)}` : ''}
            </p>
          )}
        </div>
      </div>

      <blockquote className="pu-staff-portrait">{portrait.portrait}</blockquote>

      {achievements.length > 0 && (
        <ul className="pu-staff-medals">
          {achievements.map((item) => (
            <li key={item.id} className="pu-staff-medal" title={item.detail || item.title}>
              <span className="pu-staff-medal-icon">
                <MedalIcon id={item.id} />
              </span>
              <strong>{item.value}</strong>
              <span>{item.title}</span>
            </li>
          ))}
        </ul>
      )}

      {sections.length > 0 && (
        <ul className="pu-staff-access">
          {sections.map((sec) => (
            <li key={sec.label}>{sec.label}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
