/**
 * Кликабельное имя/id → вкладка «Игроки» (поиск информации).
 * Тот же принцип, что onOpenUser в PanelShell.
 */
export default function OpenUserLink({
  userId,
  name,
  username,
  onOpenUser,
  className = '',
  children,
}) {
  const id = userId != null && userId !== '' ? Number(userId) : null
  const label = children
    || name
    || (username ? `@${String(username).replace(/^@/, '')}` : null)
    || (id ? `#${id}` : '—')

  if (!id || !onOpenUser) {
    return <span className={`e-user-plain ${className}`.trim()}>{label}</span>
  }

  return (
    <button
      type="button"
      className={`e-user-link ${className}`.trim()}
      onClick={(event) => {
        event.stopPropagation()
        onOpenUser(id)
      }}
      title="Открыть в поиске информации"
    >
      {label}
    </button>
  )
}
