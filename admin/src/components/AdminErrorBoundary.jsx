import { Component } from 'react'

export default class AdminErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message ?? 'Unknown error' }
  }

  componentDidCatch(error, info) {
    if (import.meta.env.DEV) {
      console.error('[AdminPanel] Uncaught error:', error, info?.componentStack)
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          minHeight: '100dvh', padding: '24px', background: '#050508',
        }}>
          <div style={{
            maxWidth: 420, width: '100%', background: 'rgba(10, 10, 10, 0.92)',
            border: '1px solid rgba(239, 68, 68, 0.35)', borderRadius: 16, padding: '28px 24px',
            textAlign: 'center', color: '#e5e5e5',
          }}>
            <p style={{ fontSize: 40, marginBottom: 12 }}>⚠️</p>
            <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
              Ошибка панели администратора
            </h1>
            <p style={{ fontSize: 13, color: '#9ca3af', marginBottom: 20 }}>
              Произошла непредвиденная ошибка. Перезагрузите страницу.
            </p>
            {this.state.message && (
              <pre style={{
                fontSize: 11, color: '#fca5a5', background: '#050508',
                borderRadius: 6, padding: '8px 12px', textAlign: 'left',
                overflowX: 'auto', marginBottom: 20,
              }}>
                {this.state.message}
              </pre>
            )}
            <button
              style={{
                background: 'rgba(220, 220, 220, 0.12)', color: '#fff', border: '1px solid rgba(220, 220, 220, 0.28)',
                borderRadius: 8, padding: '10px 24px', fontSize: 14,
                cursor: 'pointer', fontWeight: 600,
              }}
              onClick={() => window.location.reload()}
            >
              Перезагрузить
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
