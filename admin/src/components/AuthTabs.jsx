export default function AuthTabs({ mode, onChange }) {
  return (
    <div className="auth-tabs" role="tablist" aria-label="Авторизация">
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'login'}
        className={`auth-tab ${mode === 'login' ? 'auth-tab-active' : ''}`}
        onClick={() => onChange('login')}
      >
        Вход
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'register'}
        className={`auth-tab ${mode === 'register' ? 'auth-tab-active' : ''}`}
        onClick={() => onChange('register')}
      >
        Регистрация
      </button>
      <span
        className="auth-tabs-indicator"
        style={{ transform: mode === 'login' ? 'translateX(0%)' : 'translateX(100%)' }}
        aria-hidden="true"
      />
    </div>
  )
}
