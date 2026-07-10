export default function AppLoadingScreen() {
  return (
    <div className="app-loading-screen" role="status" aria-live="polite" aria-busy="true">
      <div className="app-loading-card">
        <div className="app-loading-crest" aria-hidden>🌾</div>
        <p className="app-loading-title">Cute Farming</p>
        <p className="app-loading-text">Загрузка…</p>
        <div className="app-loading-spinner" aria-hidden />
      </div>
    </div>
  )
}
