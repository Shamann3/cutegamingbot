import { useCallback, useEffect, useState } from 'react'
import AccentPalette from './AccentPalette'
import { applyAccentToDocument, loadStoredAccent, persistAccent } from '../lib/accentTheme'

/** Цвет и прозрачность на экранах входа, где нет бокового меню. */
export default function PanelAppearance() {
  const [accent, setAccent] = useState(() => loadStoredAccent())

  useEffect(() => {
    applyAccentToDocument(accent)
  }, [accent])

  const onChange = useCallback((next) => {
    const saved = persistAccent(next)
    applyAccentToDocument(saved, { flash: true })
    setAccent(saved)
  }, [])

  return (
    <div className="panel-appearance">
      <AccentPalette value={accent} onChange={onChange} />
    </div>
  )
}
