const CREST_SRC = '/assets/cute-crest-2x.png?v=7'
const CREST_SRCSET = [
  '/assets/cute-crest-2x.png?v=7 460w',
  '/assets/cute-crest-3x.png?v=7 690w',
].join(', ')

export default function FarmHeader({ isPreview }) {
  return (
    <header className="farm-header text-center">
      <div className="farm-header-crest-wrap mx-auto">
        <div className="farm-header-crest-glow" aria-hidden />
        <img
          src={CREST_SRC}
          srcSet={CREST_SRCSET}
          sizes="160px"
          width={230}
          height={187}
          alt="Cute Farming"
          draggable={false}
          decoding="async"
          fetchPriority="high"
          className="farm-header-crest-img"
        />
      </div>

      <div className="farm-header-titles">
        <p className="farm-header-cute farm-title-serif">CUTE</p>
        <h1 className="farm-header-title farm-title-serif">Фермерство</h1>
      </div>

      {isPreview && (
        <p className="farm-header-preview-badge">
          Превью UI без сервера
        </p>
      )}
    </header>
  )
}
