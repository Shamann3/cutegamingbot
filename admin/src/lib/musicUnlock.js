import { useMusicMode } from '../lib/musicMode'

/** Dispatch so PanelBackgroundMusic can start after unmute without waiting for a second tap. */
export function bumpMusicUnlock() {
  try {
    window.dispatchEvent(new CustomEvent('epsilon-music-unlock'))
  } catch {
    /* ignore */
  }
}

export { useMusicMode }
