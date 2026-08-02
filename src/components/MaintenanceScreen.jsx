export default function MaintenanceScreen() {
  return (
    <div className="maintenance-screen">
      <div className="maintenance-card">
        <div className="farm-header-crest-wrap maintenance-crest-wrap">
          <div className="farm-header-crest-glow" aria-hidden />
          <img
            src="/assets/cute-crest.png?v=4"
            alt=""
            draggable={false}
            className="farm-header-crest-img"
          />
        </div>

        <p className="farm-header-cute maintenance-eyebrow">Технические работы</p>
        <h1 className="farm-header-title farm-title-serif maintenance-title">
          Ферма ненадолго закрыта
        </h1>
        <p className="maintenance-text">
          Загляните чуть позже всё будет готово.
        </p>

        <button
          type="button"
          className="farm-btn-primary maintenance-retry"
          onClick={() => window.location.reload()}
        >
          Проверить снова
        </button>
      </div>
    </div>
  )
}
