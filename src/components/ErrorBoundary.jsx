import { Component } from 'react'
import { reportClientError } from '../lib/errorReporter'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    if (import.meta.env.DEV) {
      console.error('Cute Farming error:', error, info)
    }
    reportClientError({
      code: 'ERR_UI_CRASH',
      message: error?.message ?? 'React crash',
      path: window.location.pathname,
      context: info?.componentStack?.slice(0, 200) ?? '',
    })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="min-h-screen flex items-center justify-center p-6"
          style={{ background: '#070f0a' }}
        >
          <div
            className="max-w-sm rounded-2xl p-6 text-center shadow-lg"
            style={{
              background: 'linear-gradient(180deg, rgba(10, 24, 16, 0.96) 0%, rgba(6, 16, 10, 0.98) 100%)',
              border: '1px solid rgba(212, 175, 55, 0.35)',
            }}
          >
            <p className="text-4xl mb-3" aria-hidden>🌾</p>
            <h1 className="text-lg font-extrabold farm-title-serif" style={{ color: '#f5e6c8' }}>
              Что-то сломалось
            </h1>
            <p className="mt-2 text-sm" style={{ color: 'rgba(245, 230, 200, 0.6)' }}>
              Перезагрузите страницу. Если не помогло, пожалуйста, напишите в поддержку.
            </p>
            <button
              type="button"
              className="farm-btn-primary mt-4 w-full"
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
