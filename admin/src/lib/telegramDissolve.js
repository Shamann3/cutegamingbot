/**
 * Испарение DOM-элемента на частицы (как удаление сообщения в Telegram).
 * Максимум ~0.7 с. Не удаляет узел из DOM — только визуально «рассыпает».
 */

const MAX_MS = 700

function rand(a, b) {
  return a + Math.random() * (b - a)
}

async function snapshotElement(el) {
  const rect = el.getBoundingClientRect()
  const w = Math.max(1, Math.ceil(rect.width))
  const h = Math.max(1, Math.ceil(rect.height))
  // Чуть уменьшаем разрешение — быстрее и «пиксельнее», как в Telegram
  const scale = Math.min(1, 360 / Math.max(w, h))
  const cw = Math.max(1, Math.round(w * scale))
  const ch = Math.max(1, Math.round(h * scale))

  const canvas = document.createElement('canvas')
  canvas.width = cw
  canvas.height = ch
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return null

  try {
    const clone = el.cloneNode(true)
    clone.querySelectorAll('img, video, iframe, canvas').forEach((node) => {
      node.replaceWith(document.createElement('span'))
    })
    const wrap = document.createElement('div')
    wrap.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml')
    wrap.style.cssText = `width:${w}px;height:${h}px;overflow:hidden;background:#0c0c0e;`
    wrap.appendChild(clone)

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${cw}" height="${ch}">
      <foreignObject width="100%" height="100%" transform="scale(${scale})">
        ${new XMLSerializer().serializeToString(wrap)}
      </foreignObject>
    </svg>`
    const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }))
    const img = await new Promise((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve(image)
      image.onerror = reject
      image.src = url
    })
    URL.revokeObjectURL(url)
    ctx.drawImage(img, 0, 0)
    return { canvas, ctx, scale, rect, cw, ch }
  } catch {
    // Fallback: сетка «пыли» цветами панели — всё равно похоже на Telegram
    const cs = getComputedStyle(el)
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--e-accent').trim() || '#88aaff'
    const parse = (raw, fallback) => {
      const m = String(raw || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i)
      if (!m) return fallback
      return [Number(m[1]), Number(m[2]), Number(m[3])]
    }
    const bg = parse(cs.backgroundColor, [18, 18, 20])
    const ac = parse(accent.startsWith('#')
      ? `rgb(${parseInt(accent.slice(1, 3), 16)},${parseInt(accent.slice(3, 5), 16)},${parseInt(accent.slice(5, 7), 16)})`
      : accent, [136, 170, 255])
    const cell = 6
    for (let y = 0; y < ch; y += cell) {
      for (let x = 0; x < cw; x += cell) {
        const mix = Math.random()
        const c = mix > 0.72 ? ac : mix > 0.45 ? [240, 240, 245] : bg
        ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`
        ctx.globalAlpha = mix > 0.72 ? 0.85 : 0.95
        ctx.fillRect(x, y, cell - 1, cell - 1)
      }
    }
    ctx.globalAlpha = 1
    return { canvas, ctx, scale, rect, cw, ch }
  }
}

function buildParticles(ctx, cw, ch, rect, scale) {
  const cell = Math.max(3, Math.round(5 * scale || 5))
  const data = ctx.getImageData(0, 0, cw, ch).data
  const particles = []
  const maxParticles = 900

  for (let y = 0; y < ch; y += cell) {
    for (let x = 0; x < cw; x += cell) {
      const i = (y * cw + x) * 4
      const a = data[i + 3]
      if (a < 28) continue
      const r = data[i]
      const g = data[i + 1]
      const b = data[i + 2]
      // Чуть разрежаем, если слишком плотно
      if (particles.length > maxParticles && Math.random() > 0.35) continue

      const px = rect.left + x / scale
      const py = rect.top + y / scale
      const size = cell / scale * rand(0.7, 1.25)
      // Telegram: частицы улетают в стороны и чуть вверх, с разбросом
      const angle = rand(-Math.PI * 0.85, -Math.PI * 0.15) + rand(-0.55, 0.55)
      const speed = rand(38, 140)
      particles.push({
        x: px,
        y: py,
        ox: px,
        oy: py,
        vx: Math.cos(angle) * speed + rand(-28, 28),
        vy: Math.sin(angle) * speed - rand(20, 90),
        size,
        r,
        g,
        b,
        a: a / 255,
        rot: rand(0, Math.PI * 2),
        vr: rand(-6, 6),
        delay: rand(0, 0.28),
      })
    }
  }
  return particles
}

/**
 * @param {HTMLElement | null} el
 * @param {{ duration?: number }} [opts]
 * @returns {Promise<void>}
 */
export function telegramDissolve(el, opts = {}) {
  if (!el || typeof document === 'undefined') return Promise.resolve()
  const duration = Math.min(MAX_MS, Math.max(280, opts.duration ?? MAX_MS))
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
  if (reduced) {
    el.style.opacity = '0'
    return Promise.resolve()
  }

  return snapshotElement(el).then((snap) => {
    if (!snap) {
      el.style.opacity = '0'
      return
    }
    const { ctx: srcCtx, cw, ch, rect, scale } = snap
    const particles = buildParticles(srcCtx, cw, ch, rect, scale)
    if (!particles.length) {
      el.style.opacity = '0'
      return
    }

    const pad = 120
    const layer = document.createElement('canvas')
    layer.width = Math.ceil(rect.width + pad * 2)
    layer.height = Math.ceil(rect.height + pad * 2)
    layer.className = 'panel-dissolve-canvas'
    Object.assign(layer.style, {
      position: 'fixed',
      left: `${rect.left - pad}px`,
      top: `${rect.top - pad}px`,
      width: `${rect.width + pad * 2}px`,
      height: `${rect.height + pad * 2}px`,
      pointerEvents: 'none',
      zIndex: '430',
    })
    document.body.appendChild(layer)
    const ctx = layer.getContext('2d')

    // Прячем исходник сразу — частицы уже нарисованы
    const prevVis = el.style.visibility
    const prevPe = el.style.pointerEvents
    el.style.visibility = 'hidden'
    el.style.pointerEvents = 'none'

    const t0 = performance.now()

    return new Promise((resolve) => {
      const tick = (now) => {
        const t = Math.min(1, (now - t0) / duration)
        ctx.clearRect(0, 0, layer.width, layer.height)

        for (const p of particles) {
          const local = Math.max(0, Math.min(1, (t - p.delay) / (1 - p.delay)))
          if (local <= 0) {
            ctx.globalAlpha = p.a
            ctx.fillStyle = `rgb(${p.r},${p.g},${p.b})`
            ctx.fillRect(p.ox - rect.left + pad, p.oy - rect.top + pad, p.size, p.size)
            continue
          }
          // ease-out cubic — быстро стартуют, мягко гаснут
          const e = 1 - (1 - local) ** 3
          const x = p.ox + p.vx * e - rect.left + pad
          const y = p.oy + p.vy * e + 18 * e * e - rect.top + pad
          const alpha = p.a * (1 - local) ** 1.35
          if (alpha < 0.02) continue
          ctx.save()
          ctx.translate(x + p.size / 2, y + p.size / 2)
          ctx.rotate(p.rot + p.vr * e)
          ctx.globalAlpha = alpha
          ctx.fillStyle = `rgb(${p.r},${p.g},${p.b})`
          const s = p.size * (1 - e * 0.45)
          ctx.fillRect(-s / 2, -s / 2, s, s)
          ctx.restore()
        }

        if (t < 1) {
          requestAnimationFrame(tick)
        } else {
          layer.remove()
          el.style.visibility = prevVis
          el.style.pointerEvents = prevPe
          resolve()
        }
      }
      requestAnimationFrame(tick)
    })
  }).catch(() => {
    el.style.opacity = '0'
  })
}
