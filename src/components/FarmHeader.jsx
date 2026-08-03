import { seasonLabel } from '../constants/season'
import { useSettings } from '../context/SettingsContext'

const CREST_SRC = '/assets/cute-crest-2x.png?v=7'
const CREST_SRCSET = [
  '/assets/cute-crest-2x.png?v=7 460w',
  '/assets/cute-crest-3x.png?v=7 690w',
].join(', ')

/**
 * Верх фермы — «печать» как panel-brand в админке:
 * круглая марка + иерархия текста, без лишнего хлама.
 */
export default function FarmHeader({ isPreview }) {
  const { season } = useSettings()
  const seasonName = seasonLabel(season)

  return (
    <header className="farm-brand">
      <div className="farm-brand-seal" aria-hidden>
        <div className="farm-brand-halo" />
        <div className="farm-brand-ring" />
        <div className="farm-brand-mark">
          <img
            src={CREST_SRC}
            srcSet={CREST_SRCSET}
            sizes="72px"
            width={72}
            height={58}
            alt=""
            draggable={false}
            decoding="async"
            fetchPriority="high"
            className="farm-brand-crest"
          />
        </div>
      </div>

      <div className="farm-brand-meta">
        <p className="farm-brand-kicker">Cute Farming</p>
        <h1 className="farm-brand-title farm-title-serif">Ферма</h1>
        <p className="farm-brand-tag">{seasonName} · сезон открыт</p>
      </div>

      {isPreview && (
        <p className="farm-header-preview-badge">
          Превью UI без сервера
        </p>
      )}
    </header>
  )
}
