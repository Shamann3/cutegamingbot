import { useEffect, useState } from 'react'
import { playSealCue, readCueSoundsEnabled, writeCueSoundsEnabled } from '../lib/cueSounds'

export default function CueSoundSwitch() {
  const [enabled, setEnabled] = useState(readCueSoundsEnabled)

  useEffect(() => {
    const sync = () => setEnabled(readCueSoundsEnabled())
    window.addEventListener('epsilon-cue-sounds', sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener('epsilon-cue-sounds', sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  const toggle = () => {
    const next = writeCueSoundsEnabled(!readCueSoundsEnabled())
    setEnabled(next)
    if (next) playSealCue()
  }

  return (
    <>
    <button
      type="button"
      className={`panel-cue-switch${enabled ? ' is-on' : ''}`}
      aria-pressed={enabled}
      data-cue="off"
      onClick={toggle}
    >
      <span className="panel-cue-track" aria-hidden="true">
        <span className="panel-cue-knob" />
      </span>
      <span className="panel-cue-copy">
        <strong>Дополнительные звуки</strong>
        <em>{enabled ? 'Включены' : 'Выключены'}</em>
      </span>
    </button>
    <p className="panel-cue-foot">
      {enabled
        ? 'Короткие звуки и мемы включены. Музыка играет, только если её ползунок не на нуле.'
        : 'Панель молчит целиком: ни мемов, ни коротких звуков, ни музыки. Громкость музыки сохранится.'}
    </p>
    </>
  )
}
