import AccentAura from './AccentAura'
import EpsilonLogo from './EpsilonLogo'
import PanelAppearance from './PanelAppearance'

/** Общая карточка входа: те же цвет, ширина и низ, что у панели сотрудника. */
export default function EntryFrame({ title, lead, personal = false, onBack, children }) {
  return (
    <div className={`auth-screen auth-screen-panel auth-screen-fortress${personal ? ' is-personal' : ''}`}>
      <AccentAura />
      <div className="auth-card entry-card entry-stable">
        <header className="auth-header">
          <div className="auth-logo-wrap">
            <EpsilonLogo className="auth-logo" size="lg" alt="Cute Epsilon" />
          </div>
          <h1 className="auth-title">{title}</h1>
          {lead && <p className="auth-subtitle">{lead}</p>}
        </header>
        <PanelAppearance />
        {children}
        {onBack && (
          <button type="button" className="entry-back" onClick={onBack}>
            К выбору панели
          </button>
        )}
      </div>
    </div>
  )
}
