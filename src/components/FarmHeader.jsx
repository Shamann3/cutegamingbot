import { seasonLabel } from '../constants/season'
import { useSettings } from '../context/SettingsContext'

const CREST_SRC = '/assets/cute-crest-2x.png?v=7'
const CREST_SRCSET = [
  '/assets/cute-crest-2x.png?v=7 460w',
  '/assets/cute-crest-3x.png?v=7 690w',
].join(', ')

/**
 * Главный экран фермы — полноценный герб + мягкая типографика.
 */
export default function FarmHeader({ isPreview }) {
  const { season } = useSettings()
  const seasonName = seasonLabel(season)

  return (
    <header className="farm-header">
      <div className="farm-header-crest-wrap">
        <div className="farm-header-crest-glow" aria-hidden />
        <img
          src={CREST_SRC}
          srcSet={CREST_SRCSET}
          sizes="(min-width: 640px) 200px, 168px"
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
        <p className="farm-header-cute farm-title-serif">Cute</p>
        <h1 className="farm-header-title farm-title-serif">Фермерство</h1>
        <p className="farm-header-season">{seasonName} · сезон открыт</p>
      </div>

      {isPreview && (
        <p className="farm-header-preview-badge">
          Превью UI без сервера
        </p>
      )}
    </header>
  )
}
