import { ACCENT_SWATCHES } from '../lib/accentTheme'

export default function AccentPalette({ value, onChange }) {
  const current = value?.id || ACCENT_SWATCHES[0].id

  return (
    <div className="accent-palette" role="group" aria-label="Цвет подсветки">
      <div className="accent-palette-head">
        <span className="accent-palette-title">Подсветка</span>
        <span className="accent-palette-current">{value?.label || 'Мята'}</span>
      </div>
      <div className="accent-palette-grid">
        {ACCENT_SWATCHES.map((swatch) => {
          const on = current === swatch.id
          return (
            <button
              key={swatch.id}
              type="button"
              className={`accent-swatch${on ? ' accent-swatch-on' : ''}`}
              style={{ '--swatch': swatch.hex }}
              title={swatch.label}
              aria-label={swatch.label}
              aria-pressed={on}
              onClick={() => onChange?.(swatch)}
            >
              <span className="accent-swatch-core" />
            </button>
          )
        })}
      </div>
    </div>
  )
}
