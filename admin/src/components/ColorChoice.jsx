import { useState } from 'react'
import { ACCENT_SWATCHES, applyAccentToDocument, loadStoredAccent, persistAccent } from '../lib/accentTheme'

/** Кружки цвета. Белый оставляет панель чёрно-белой. */
export default function ColorChoice({ onChange }) {
  const [current, setCurrent] = useState(() => loadStoredAccent())

  const pick = (swatch) => {
    const next = persistAccent({ ...swatch, glow: 55 })
    applyAccentToDocument(next)
    setCurrent(next)
    onChange?.(next)
  }

  return (
    <div className="color-choice" data-swipe-ignore>
      <p>Цвет кнопок. Белый оставляет панель чёрно-белой. Другой цвет перекрасит кнопки. Потом цвет можно сменить здесь же.</p>
      <div className="color-choice-row" role="listbox" aria-label="Цвет кнопок">
        {ACCENT_SWATCHES.map((swatch) => (
          <button
            key={swatch.id}
            type="button"
            role="option"
            aria-label={swatch.label}
            aria-selected={current.id === swatch.id}
            className={current.id === swatch.id ? 'is-on' : ''}
            style={{ background: swatch.hex }}
            onClick={() => pick(swatch)}
          />
        ))}
      </div>
    </div>
  )
}
