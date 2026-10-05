/**
 * Короткие звуки панели: вход логотипа и подтверждение сохранения.
 * Громкость фиксирована около 50%. По умолчанию включены.
 * Сам логотип и его таймлайн здесь не меняются — только момент звука.
 */

const STORAGE_KEY = 'cf_admin_cue_sounds'
export const CUE_VOLUME = 0.5
/** Совпадает с animation-delay появления логотипа в entrance.css */
export const LOGO_CUE_DELAY_MS = 1100
/** Туманная обводка .ent-stamp уже видна: старт 2.2с, пик около 2.6с */
export const FOG_CUE_DELAY_MS = 2600
const ARM_MS = 12000
const SEAL_GAP_MS = 480

const ENTER_URL = new URL('../../../public/звук входа.mp3', import.meta.url).href
const SEAL_URL = new URL('../../../public/звук сохранения чего либо.mp3', import.meta.url).href

const COMMIT_RE = /(сохран|подтверд|запис|примен|одобр|отклон|выда|созда|добав|снять|снят|включ|выключ|отправ|зачисл|начисл|забра|готово|подходит|неправильно|непонятно|удал|забан|разбан|размут|кик|варн|наказ|засчита|зачест|зафиксир|принять|голос|предупрежд)/i
const SILENT_PATH = /\/auth\/|\/pulse(?:\/|$|\?)|\/broadcast\/preview$|\/contract-templates\/render$/

let armedUntil = 0
let lastSeal = 0
let installed = false
let primed = false
let pending = ''
let clipToken = 0
const clips = { enter: null, seal: null }

function storage() {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function readCueSoundsEnabled() {
  const box = storage()
  if (!box) return true
  try {
    const raw = box.getItem(STORAGE_KEY)
    if (raw === '0' || raw === 'false') return false
  } catch { /* нет хранилища — звуки остаются включёнными */ }
  return true
}

function hushClips() {
  pending = ''
  clipToken += 1
  for (const audio of Object.values(clips)) {
    if (!audio) continue
    audio.volume = 0
    try { audio.pause() } catch { /* ignore */ }
    try { audio.currentTime = 0 } catch { /* ignore */ }
  }
}

export function writeCueSoundsEnabled(on) {
  const next = Boolean(on)
  const box = storage()
  try { box?.setItem(STORAGE_KEY, next ? '1' : '0') } catch { /* ignore */ }
  if (!next) hushClips()
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('epsilon-cue-sounds', { detail: next }))
  }
  return next
}

export function isCommitControl(text) {
  const value = String(text || '').replace(/\s+/g, ' ').trim()
  if (!value || /^отмена$/i.test(value)) return false
  return COMMIT_RE.test(value)
}

export function pathIsSilent(path) {
  return SILENT_PATH.test(String(path || '').split('?')[0])
}

export function writeIsMutable(method) {
  return ['POST', 'PUT', 'PATCH', 'DELETE'].includes(String(method || 'GET').toUpperCase())
}

export function armSaveCue(now = Date.now()) {
  armedUntil = now + ARM_MS
}

export function disarmSaveCue() {
  armedUntil = 0
}

export function writeShouldChime(method, path, now = Date.now()) {
  if (!writeIsMutable(method) || pathIsSilent(path)) return false
  return now <= armedUntil
}

function ensure(kind) {
  if (typeof Audio !== 'function') return null
  if (!clips[kind]) {
    const audio = new Audio(kind === 'enter' ? ENTER_URL : SEAL_URL)
    audio.preload = 'auto'
    audio.loop = false
    clips[kind] = audio
  }
  return clips[kind]
}

function duckEnter() {
  const enter = clips.enter
  if (!enter || enter.paused) return
  enter.volume = 0.18
}

function playClip(kind) {
  if (!readCueSoundsEnabled()) return false
  const audio = ensure(kind)
  if (!audio) return false
  if (kind === 'seal') {
    const now = Date.now()
    if (now - lastSeal < SEAL_GAP_MS) return false
    lastSeal = now
    duckEnter()
  }
  clipToken += 1
  audio.volume = CUE_VOLUME
  try { audio.currentTime = 0 } catch { /* файл ещё не открыт */ }
  const run = audio.play()
  if (run && typeof run.catch === 'function') {
    run.catch(() => { pending = kind })
  }
  return true
}

export function playEnterCue() {
  return playClip('enter')
}

export function playSealCue() {
  return playClip('seal')
}

export function noteCommittedWrite(method, path, ok, now = Date.now()) {
  if (!writeShouldChime(method, path, now)) return false
  armedUntil = 0
  if (ok) playSealCue()
  return Boolean(ok)
}

export function noteSuccessToast(message, kind = 'success') {
  if (kind === 'error') return false
  if (!isCommitControl(message)) return false
  return playSealCue()
}

function controlOf(target) {
  const node = target?.closest?.('button, [role="button"], input[type="submit"], a')
  if (!node) return null
  if (node.closest('[data-cue="off"], .panel-cue-switch, .panel-music-card, .pocket-tools-music')) return null
  return node
}

function armFromControl(node) {
  if (!node) return
  if (node.dataset?.cue === 'save' || node.closest?.('[data-cue="save"]')) {
    armSaveCue()
    return
  }
  const text = `${node.getAttribute?.('aria-label') || ''} ${node.innerText || node.value || ''}`
  if (isCommitControl(text)) armSaveCue()
}

function prime() {
  if (!readCueSoundsEnabled()) return
  if (primed) return
  const enter = ensure('enter')
  const seal = ensure('seal')
  if (!enter || !seal) return
  primed = true
  const token = clipToken
  for (const audio of [enter, seal]) {
    audio.volume = 0
    const run = audio.play()
    const restore = () => {
      if (token !== clipToken) return
      audio.pause()
      try { audio.currentTime = 0 } catch { /* ignore */ }
      audio.volume = CUE_VOLUME
    }
    if (run && typeof run.then === 'function') run.then(restore).catch(() => { primed = false; audio.volume = CUE_VOLUME })
    else restore()
  }
}

function onGesture(event) {
  if (!readCueSoundsEnabled()) {
    pending = ''
    return
  }
  prime()
  if (pending && readCueSoundsEnabled()) {
    const kind = pending
    pending = ''
    playClip(kind)
  }
  if (event.type !== 'keydown' || event.repeat) return
  const key = event.key
  if (key !== 'ArrowLeft' && key !== 'ArrowRight' && key !== 'ArrowDown') return
  if (event.target?.closest?.('input, textarea, select, [contenteditable="true"]')) return
  armSaveCue()
}

function onClick(event) {
  armFromControl(controlOf(event.target))
}

function onSubmit(event) {
  const submitter = event.submitter || event.target?.querySelector?.('[type="submit"]')
  armFromControl(controlOf(submitter))
}

export function installCueSounds() {
  if (installed || typeof document === 'undefined') return
  installed = true
  document.addEventListener('pointerdown', onGesture, true)
  document.addEventListener('keydown', onGesture, true)
  document.addEventListener('click', onClick, true)
  document.addEventListener('submit', onSubmit, true)
}
