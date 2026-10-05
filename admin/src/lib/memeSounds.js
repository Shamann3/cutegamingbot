/**
 * Мемный режим: один бросок на вход.
 * Мелодия играет до конца. Новая мелодия останавливает предыдущую,
 * чтобы быстрая сортировка «подходит / не подходит» не накладывала звуки.
 * Громкость 55%. Без дополнительных звуков мемы молчат.
 */
import { fetchMemeMode } from './adminClient'
import { readCueSoundsEnabled } from './cueSounds'

export const MEME_VOLUME = 0.55
export const DEFAULT_MEME_CHANCE = 10
const ROLL_KEY = 'cf_admin_meme_on'

const FILES = {
  logo: new URL('../../../public/84946-chelovek-pauk-mem.mp3', import.meta.url).href,
  gate: new URL('../../../public/9787-poroi-nam-nuzhno-prinjat-reshenie.mp3', import.meta.url).href,
  matrix: new URL('../../../public/47401-pu-pu-pu-pu-zavarjuka.mp3', import.meta.url).href,
  useful: new URL('../../../public/chto-vyi-umeete-delat.mp3', import.meta.url).href,
  punish: new URL('../../../public/there-is-a-penetration (1).mp3', import.meta.url).href,
  more: new URL('../../../public/damn-why-did-i-come-here.mp3', import.meta.url).href,
  entered: new URL('../../../public/well-let-the-people-go.mp3', import.meta.url).href,
  wont: new URL('../../../public/but-of-course-i-won39t-do-that.mp3', import.meta.url).href,
  wake: new URL('../../../public/silence-well-wake-up.mp3', import.meta.url).href,
  yes: new URL('../../../public/yes-yes-genady-gorin.mp3', import.meta.url).href,
  no: new URL('../../../public/nein.mp3', import.meta.url).href,
}

let visit = null
let current = null
let pendingKind = ''
let unlockInstalled = false

export function clampChance(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return DEFAULT_MEME_CHANCE
  return Math.max(0, Math.min(100, Math.round(number)))
}

export function parseExcludedIds(raw) {
  const parts = Array.isArray(raw) ? raw : String(raw || '').split(/[\s,;]+/)
  const seen = new Set()
  const ids = []
  for (const part of parts) {
    const text = String(part).trim()
    if (!/^\d+$/.test(text)) continue
    const number = Number(text)
    if (number <= 0 || seen.has(number)) continue
    seen.add(number)
    ids.push(number)
    if (ids.length >= 200) break
  }
  return ids
}

export function decideMeme({ chance = DEFAULT_MEME_CHANCE, exempt = false, stored = null, random = Math.random } = {}) {
  if (exempt) return false
  if (stored === '1') return true
  if (stored === '0') return false
  return random() * 100 < clampChance(chance)
}

function box() {
  try { return window.sessionStorage } catch { return null }
}

export function memeRolledOn() {
  return box()?.getItem(ROLL_KEY) === '1'
}

export function prepareMemeVisit() {
  if (!visit) visit = settle()
  return visit
}

async function settle() {
  let chance = DEFAULT_MEME_CHANCE
  let exempt = false
  try {
    const data = await fetchMemeMode()
    chance = clampChance(data?.chance)
    exempt = Boolean(data?.exempt)
  } catch { /* без сервера остаётся шанс по умолчанию */ }
  const store = box()
  if (exempt) {
    try { store?.setItem(ROLL_KEY, '0') } catch { /* ignore */ }
    return false
  }
  const stored = store?.getItem(ROLL_KEY)
  if (stored === '1' || stored === '0') return stored === '1'
  const on = decideMeme({ chance, random: Math.random })
  try { store?.setItem(ROLL_KEY, on ? '1' : '0') } catch { /* ignore */ }
  return on
}

function stopCurrent() {
  if (!current) return
  current.pause()
  try { current.currentTime = 0 } catch { /* ignore */ }
  current = null
}

export function stopMeme() {
  pendingKind = ''
  stopCurrent()
}

function installUnlock() {
  if (unlockInstalled || typeof document === 'undefined') return
  unlockInstalled = true
  const resume = () => {
    if (!pendingKind || !readCueSoundsEnabled()) return
    const kind = pendingKind
    pendingKind = ''
    startClip(kind)
  }
  document.addEventListener('pointerdown', resume, true)
  document.addEventListener('touchend', resume, true)
  window.addEventListener('epsilon-cue-sounds', (event) => {
    if (!event.detail) stopMeme()
  })
}

function startClip(kind) {
  if (!FILES[kind] || !memeRolledOn() || !readCueSoundsEnabled()) return false
  if (typeof Audio !== 'function') return false
  stopCurrent()
  const audio = new Audio(FILES[kind])
  audio.preload = 'auto'
  audio.loop = false
  audio.volume = MEME_VOLUME
  try { audio.playsInline = true } catch { /* ignore */ }
  current = audio
  const run = audio.play()
  if (run && typeof run.then === 'function') {
    run.then(() => {
      if (current === audio) audio.volume = MEME_VOLUME
    }).catch(() => {
      if (current === audio) pendingKind = kind
    })
  }
  return true
}

export async function playMeme(kind) {
  if (!FILES[kind]) return false
  installUnlock()
  const stored = box()?.getItem(ROLL_KEY)
  if (stored !== '1' && stored !== '0') {
    await Promise.race([
      prepareMemeVisit(),
      new Promise((resolve) => setTimeout(resolve, 1200)),
    ])
  }
  pendingKind = ''
  return startClip(kind)
}

export function playVerdictMeme(choice) {
  if (choice === 'clear') return playMeme('yes')
  if (choice === 'wrong') return playMeme('no')
  return false
}
