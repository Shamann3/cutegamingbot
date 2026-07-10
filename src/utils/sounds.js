let audioCtx = null

function getCtx() {
  try {
    if (!audioCtx) {
      audioCtx = new AudioContext()
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume().catch(() => {})
    }
    return audioCtx
  } catch {
    return null
  }
}

function tone(freq, duration, type = 'sine', volume = 0.12) {
  const ctx = getCtx()
  if (!ctx) return

  try {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = type
    osc.frequency.setValueAtTime(freq, ctx.currentTime)
    gain.gain.setValueAtTime(volume, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + duration)
  } catch {
    // Audio недоступен (iOS без жеста, WebView)
  }
}

function noiseBurst(duration = 0.08, volume = 0.06) {
  const ctx = getCtx()
  if (!ctx) return

  try {
    const bufferSize = Math.max(1, Math.floor(ctx.sampleRate * duration))
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate)
    const data = buffer.getChannelData(0)
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize)
    }
    const source = ctx.createBufferSource()
    const gain = ctx.createGain()
    source.buffer = buffer
    gain.gain.value = volume
    source.connect(gain)
    gain.connect(ctx.destination)
    source.start()
  } catch {
    // ignore
  }
}

function toneSweep(fromFreq, toFreq, duration, type = 'sine', volume = 0.08) {
  const ctx = getCtx()
  if (!ctx) return

  try {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = type
    osc.frequency.setValueAtTime(fromFreq, ctx.currentTime)
    osc.frequency.exponentialRampToValueAtTime(Math.max(40, toFreq), ctx.currentTime + duration)
    gain.gain.setValueAtTime(volume, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + duration)
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// Craft ritual WAV - загружается заранее, играет поверх синтеза во время ритуала
// ---------------------------------------------------------------------------

let _craftWavBytes = null      // raw ArrayBuffer - грузится сразу при импорте
let _craftWavBuffer = null     // декодированный AudioBuffer - создаётся при первом воспроизведении
let _craftWavDecoding = false  // guard: не запускать повторный decode пока идёт текущий

fetch('/assets/craft-ritual.wav')
  .then((r) => (r.ok ? r.arrayBuffer() : null))
  .then((buf) => { if (buf) _craftWavBytes = buf })
  .catch(() => {})

/**
 * Играет WAV-файл ритуала крафта с fade-in.
 * Возвращает функцию stop(fadeOutMs), которая плавно затихает.
 * Если звук ещё не декодирован - декодирует асинхронно и стартует как только готово.
 */
export function playCraftRitualSound({ volume = 0.40, fadeInMs = 750 } = {}) {
  const ctx = getCtx()
  if (!ctx) return () => {}

  let stopped = false
  let stopFn = () => {}

  const activate = (buffer) => {
    if (stopped) return
    try {
      const source = ctx.createBufferSource()
      const gain = ctx.createGain()
      source.buffer = buffer

      // Fade-in
      gain.gain.setValueAtTime(0.0001, ctx.currentTime)
      gain.gain.linearRampToValueAtTime(volume, ctx.currentTime + fadeInMs / 1000)

      source.connect(gain)
      gain.connect(ctx.destination)
      source.start()

      stopFn = (fadeOutMs = 900) => {
        try {
          const now = ctx.currentTime
          gain.gain.cancelScheduledValues(now)
          gain.gain.setValueAtTime(gain.gain.value, now)
          gain.gain.linearRampToValueAtTime(0.0001, now + fadeOutMs / 1000)
          source.stop(now + fadeOutMs / 1000 + 0.05)
        } catch {}
      }
    } catch {}
  }

  if (_craftWavBuffer) {
    activate(_craftWavBuffer)
  } else if (_craftWavBytes && !_craftWavDecoding) {
    _craftWavDecoding = true
    ctx.decodeAudioData(_craftWavBytes.slice(0))
      .then((buf) => { _craftWavBuffer = buf; _craftWavDecoding = false; activate(buf) })
      .catch(() => { _craftWavDecoding = false })
  }

  return (fadeOutMs = 900) => {
    stopped = true
    stopFn(fadeOutMs)
  }
}

// ---------------------------------------------------------------------------

export const farmSounds = {
  plant() {
    noiseBurst(0.06, 0.08)
    tone(320, 0.08, 'triangle', 0.1)
    setTimeout(() => tone(480, 0.1, 'triangle', 0.08), 60)
  },
  water() {
    tone(620, 0.05, 'sine', 0.07)
    setTimeout(() => tone(520, 0.07, 'sine', 0.06), 70)
    setTimeout(() => tone(440, 0.09, 'sine', 0.05), 140)
    setTimeout(() => noiseBurst(0.04, 0.04), 100)
  },
  harvest() {
    tone(523, 0.1, 'triangle', 0.1)
    setTimeout(() => tone(659, 0.1, 'triangle', 0.1), 90)
    setTimeout(() => tone(784, 0.15, 'triangle', 0.12), 180)
  },
  clear() {
    tone(280, 0.12, 'square', 0.06)
    setTimeout(() => noiseBurst(0.1, 0.05), 50)
  },
  craft() {
    noiseBurst(0.04, 0.05)
    tone(147, 0.28, 'sine', 0.07)
    setTimeout(() => tone(220, 0.22, 'triangle', 0.06), 120)
    setTimeout(() => toneSweep(262, 392, 0.35, 'sine', 0.05), 240)
  },
  craftWhirl() {
    toneSweep(330, 520, 0.22, 'triangle', 0.05)
    setTimeout(() => tone(440, 0.06, 'sine', 0.04), 60)
    setTimeout(() => tone(494, 0.06, 'sine', 0.04), 120)
    setTimeout(() => tone(554, 0.07, 'sine', 0.05), 180)
    setTimeout(() => noiseBurst(0.05, 0.035), 140)
  },
  craftClimax() {
    tone(659, 0.05, 'triangle', 0.11)
    setTimeout(() => tone(784, 0.07, 'triangle', 0.13), 45)
    setTimeout(() => tone(988, 0.09, 'triangle', 0.14), 90)
    setTimeout(() => noiseBurst(0.1, 0.07), 70)
    setTimeout(() => toneSweep(880, 1320, 0.18, 'sine', 0.06), 110)
  },
  craftSigil() {
    tone(110, 0.35, 'sine', 0.08)
    setTimeout(() => tone(220, 0.12, 'triangle', 0.1), 120)
    setTimeout(() => tone(440, 0.1, 'triangle', 0.12), 220)
    setTimeout(() => tone(880, 0.14, 'triangle', 0.1), 320)
    setTimeout(() => noiseBurst(0.14, 0.08), 280)
    setTimeout(() => toneSweep(660, 1320, 0.25, 'sine', 0.07), 350)
  },
  craftSuccess() {
    tone(523, 0.1, 'triangle', 0.12)
    setTimeout(() => tone(659, 0.1, 'triangle', 0.12), 85)
    setTimeout(() => tone(784, 0.12, 'triangle', 0.14), 170)
    setTimeout(() => tone(988, 0.18, 'triangle', 0.11), 260)
    setTimeout(() => tone(1175, 0.22, 'triangle', 0.08), 350)
    setTimeout(() => noiseBurst(0.06, 0.04), 320)
  },
  craftFail() {
    tone(233, 0.18, 'sawtooth', 0.06)
    setTimeout(() => toneSweep(196, 98, 0.35, 'sine', 0.05), 80)
    setTimeout(() => tone(147, 0.28, 'sawtooth', 0.04), 160)
    setTimeout(() => noiseBurst(0.16, 0.06), 100)
    setTimeout(() => noiseBurst(0.12, 0.04), 220)
  },
}
