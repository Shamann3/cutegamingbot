import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { WORLD_BORDERS } from '../../lib/worldborders'
import { getAdminProfile } from '../../lib/adminProfile'

/**
 * Командный Пункт — owner-only «режим Бога».
 * Ritual command center built on ONE continuous MapLibre globe: spin the real
 * dark-satellite Earth and keep zooming, unbroken, from orbit down to a single
 * rooftop. Living souls (by geo/IP) glow on the sphere; gold country borders
 * engrave the obsidian world; the Great Alchemy levers, per-soul dossier with
 * Shadowban, and the Ragnarök freeze frame it.
 *
 * Imagery: Esri World Imagery (no API key), tinted obsidian+gold via raster
 * paint + a crimson/gold atmosphere. Runs on simulated data; real wiring seams
 * are marked `TODO(live)`. Destructive rites only affect this view until wired.
 */

/* Esri World Imagery — free, keyless, tiles down to z19 (a single house) */
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'

/* gold country borders, straight from the bundled Natural Earth rings → GeoJSON */
const BORDERS_GEOJSON = {
  type: 'FeatureCollection',
  features: WORLD_BORDERS.map((country) => ({
    type: 'Feature', properties: {},
    geometry: {
      type: 'MultiLineString',
      coordinates: country.map((ring) => {
        const c = []
        for (let i = 0; i < ring.length; i += 2) c.push([ring[i], ring[i + 1]])
        return c
      }),
    },
  })),
}

/* real cities → seeded souls */
const CITIES = [
  ['Мидас_77', 40.71, -74.0, 'Нью-Йорк', 'США'], ['bloodmoon', 51.51, -0.13, 'Лондон', 'Британия'],
  ['Сатоши', 35.68, 139.69, 'Токио', 'Япония'], ['v0id', 55.75, 37.62, 'Москва', 'Россия'],
  ['Люцифераза', 48.85, 2.35, 'Париж', 'Франция'], ['goldrush', -23.55, -46.63, 'Сан-Паулу', 'Бразилия'],
  ['Кали', 28.61, 77.2, 'Дели', 'Индия'], ['nyx', 52.52, 13.4, 'Берлин', 'Германия'],
  ['argent', -33.86, 151.2, 'Сидней', 'Австралия'], ['Гермес', 41.9, 12.49, 'Рим', 'Италия'],
  ['phantom', 1.35, 103.81, 'Сингапур', 'Сингапур'], ['Осирис', 30.04, 31.23, 'Каир', 'Египет'],
  ['wraith', 37.77, -122.41, 'Сан-Франциско', 'США'], ['Морана', 50.45, 30.52, 'Киев', 'Украина'],
  ['Sol_Invictus', 40.41, -3.7, 'Мадрид', 'Испания'], ['ashen', 43.65, -79.38, 'Торонто', 'Канада'],
  ['Велес', 59.93, 30.33, 'Петербург', 'Россия'], ['obol', 19.43, -99.13, 'Мехико', 'Мексика'],
  ['Танатос', 39.9, 116.4, 'Пекин', 'Китай'], ['mercury', -34.6, -58.38, 'Буэнос-Айрес', 'Аргентина'],
  ['Астарта', 25.2, 55.27, 'Дубай', 'ОАЭ'], ['hex', 22.32, 114.17, 'Гонконг', 'Китай'],
  ['Прометей', 37.98, 23.72, 'Афины', 'Греция'], ['signal', 34.05, -118.24, 'Лос-Анджелес', 'США'],
  ['Морок', 53.9, 27.56, 'Минск', 'Беларусь'], ['Кербер', -26.2, 28.04, 'Йоханнесбург', 'ЮАР'],
  ['nocturne', -37.81, 144.96, 'Мельбурн', 'Австралия'], ['Гея', -1.29, 36.82, 'Найроби', 'Кения'],
]
const seed = (s) => { const x = Math.sin(s * 99.7) * 10000; return x - Math.floor(x) }
const fmt = (n) => Math.round(n).toLocaleString('ru-RU')

function buildPlayers() {
  return CITIES.map((c, i) => ({
    name: c[0], lat: c[1], lon: c[2], city: c[3], country: c[4],
    shadow: false,
    id: 100000 + Math.floor(seed(i + 3) * 899999),
    ip: `${5 + Math.floor(seed(i) * 250)}.${Math.floor(seed(i + 1) * 255)}.${Math.floor(seed(i + 2) * 255)}.${Math.floor(seed(i + 7) * 255)}`,
    bal: Math.floor(seed(i + 9) * 4_000_000) + 2000,
    sus: Math.floor(seed(i + 5) * 88) + 8,
    dev: ['iPhone 15 · iOS 18', 'Pixel 8 · Android 15', 'Samsung S24', 'Desktop · Chrome', 'iPad · Safari'][Math.floor(seed(i + 4) * 5)],
    seen: ['только что', '2 мин', '7 мин', 'только что', '1 мин', 'только что'][Math.floor(seed(i + 6) * 6)],
  }))
}

/* souls → GeoJSON for the map's circle layers (occluded correctly behind the globe) */
function soulsFC(players) {
  return {
    type: 'FeatureCollection',
    features: players.map((p) => ({
      type: 'Feature',
      properties: { id: p.id, name: p.name, city: p.city, country: p.country, shadow: p.shadow ? 1 : 0 },
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
    })),
  }
}

const CH_ACTS = [
  ['g', 'начислил', '◇'], ['g', 'обменял', '⇄'], ['g', 'скрафтил', '⚒'], ['g', 'собрал урожай', '🌾'],
  ['', 'вошёл в игру', '⇲'], ['', 'купил на бирже', '$'], ['r', 'получил бан', '⛔'], ['r', 'помилован', '⚠'],
]
const nowTs = () => new Date().toTimeString().slice(0, 8)

export default function CommandCenterSection({ onExit, architect }) {
  const reduce = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, [])
  const architectName = useMemo(
    () => architect || getAdminProfile()?.displayName || getAdminProfile()?.username || 'Архитектор',
    [architect],
  )

  const mapWrapRef = useRef(null)
  const mapRef = useRef(null)
  const engine = useRef({
    rush: false, eclipse: false, frozen: false,
    players: buildPlayers(), reduce,
  })

  const [levers, setLevers] = useState({ craft: 62, tax: 8, gravity: 100 })
  const [rites, setRites] = useState({ rush: false, eclipse: false, silence: false })
  const [frozen, setFrozen] = useState(false)
  const [soundOn, setSoundOn] = useState(false)
  const [dossierId, setDossierId] = useState(null)
  const [, forceTick] = useState(0)
  const [chron, setChron] = useState([])
  const [counters, setCounters] = useState({ souls: 3712, tx: 340, pulse: 'Ровно', stable: 'Стабильно' })
  const [toasts, setToasts] = useState([])
  const [decree, setDecree] = useState(null)
  const [view, setView] = useState({ z: 1.9, lat: 25, lon: 20, deep: false })

  const dossier = dossierId != null ? engine.current.players.find((p) => p.id === dossierId) : null

  /* ---------- toasts ---------- */
  const toast = useCallback((msg, kind = '', icon = '') => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t, { id, msg, kind, icon }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000)
  }, [])

  /* ---------- chronicles ---------- */
  const pushChron = useCallback((html) => {
    setChron((c) => [...c, { id: Math.random().toString(36).slice(2), t: nowTs(), html }].slice(-60))
  }, [])
  const chronTick = useCallback(() => {
    const ps = engine.current.players
    const p = ps[Math.floor(Math.random() * ps.length)]
    const a = CH_ACTS[Math.floor(Math.random() * CH_ACTS.length)]
    const amt = Math.floor(Math.random() * 90000) + 50
    const cls = a[0] ? ` class="${a[0]}"` : ''
    pushChron(`${p.name} ${a[1]} <span${cls}>${a[2]}${a[0] === 'r' ? '' : ' ' + fmt(amt)}</span>`)
  }, [pushChron])

  useEffect(() => {
    for (let i = 0; i < 14; i++) chronTick()
    const id = setInterval(() => { if (!engine.current.frozen) chronTick() }, 1600)
    return () => clearInterval(id)
  }, [chronTick])

  /* ---------- counters ---------- */
  useEffect(() => {
    let souls = 3712
    const id = setInterval(() => {
      const e = engine.current
      souls += Math.floor((Math.random() - 0.42) * 14)
      if (e.eclipse) souls -= 6
      if (e.rush) souls += 9
      souls = Math.max(1200, souls)
      let tx = 340 + Math.floor((Math.random() - 0.5) * 40)
      if (e.rush) tx *= 3
      if (e.eclipse) tx = Math.floor(tx * 0.35)
      setCounters({
        souls, tx,
        pulse: e.frozen ? 'Стоп' : e.rush ? 'Бешеный' : e.eclipse ? 'Слабый' : 'Ровно',
        stable: e.frozen ? 'Заморожено' : e.rush ? 'Перегрев' : e.eclipse ? 'Обвал' : 'Стабильно',
      })
    }, 1400)
    return () => clearInterval(id)
  }, [])

  /* ---------- webaudio (opt-in) ---------- */
  const audio = useRef({ ac: null, drone: null })
  const ensureAC = () => {
    if (!audio.current.ac) audio.current.ac = new (window.AudioContext || window.webkitAudioContext)()
    return audio.current.ac
  }
  const playTone = useCallback((kind) => {
    if (!soundOn || !audio.current.ac) return
    const ac = audio.current.ac
    const now = ac.currentTime
    const o = ac.createOscillator()
    const g = ac.createGain()
    o.connect(g).connect(ac.destination)
    const map = {
      rise: [220, 660, 'triangle', 0.9, 0.09], gold: [520, 880, 'triangle', 0.7, 0.08],
      tick: [440, 440, 'square', 0.05, 0.02], shadow: [400, 90, 'sawtooth', 0.7, 0.09],
      low: [120, 70, 'sine', 0.6, 0.08], off: [300, 200, 'sine', 0.25, 0.05], gong: [70, 40, 'sine', 3.2, 0.22],
    }
    const m = map[kind] || map.tick
    o.type = m[2]
    o.frequency.setValueAtTime(m[0], now)
    o.frequency.exponentialRampToValueAtTime(Math.max(m[1], 20), now + m[3])
    g.gain.setValueAtTime(0.0001, now)
    g.gain.exponentialRampToValueAtTime(m[4], now + 0.02)
    g.gain.exponentialRampToValueAtTime(0.0001, now + m[3])
    o.start(now)
    o.stop(now + m[3] + 0.1)
    if (kind === 'gong') {
      const o2 = ac.createOscillator(); const g2 = ac.createGain()
      o2.type = 'sine'; o2.frequency.value = 105; o2.connect(g2).connect(ac.destination)
      g2.gain.setValueAtTime(0.12, now); g2.gain.exponentialRampToValueAtTime(0.0001, now + 3)
      o2.start(now); o2.stop(now + 3.2)
    }
  }, [soundOn])

  const toggleSound = () => {
    setSoundOn((on) => {
      const next = !on
      if (next) {
        const ac = ensureAC()
        ac.resume()
        const d = { o1: ac.createOscillator(), o2: ac.createOscillator(), g: ac.createGain(), lfo: ac.createOscillator(), lg: ac.createGain() }
        d.o1.type = 'sine'; d.o1.frequency.value = 55; d.o2.type = 'sine'; d.o2.frequency.value = 55.6
        d.g.gain.value = 0; d.lfo.frequency.value = 0.12; d.lg.gain.value = 0.02
        d.lfo.connect(d.lg).connect(d.g.gain)
        d.o1.connect(d.g); d.o2.connect(d.g); d.g.connect(ac.destination)
        d.o1.start(); d.o2.start(); d.lfo.start()
        d.g.gain.linearRampToValueAtTime(0.06, ac.currentTime + 2)
        audio.current.drone = d
      } else if (audio.current.drone) {
        const ac = audio.current.ac; const d = audio.current.drone
        d.g.gain.linearRampToValueAtTime(0, ac.currentTime + 0.6)
        setTimeout(() => { try { d.o1.stop(); d.o2.stop(); d.lfo.stop() } catch { /* ignore */ } }, 700)
        audio.current.drone = null
      }
      return next
    })
  }
  useEffect(() => () => {
    // cleanup audio on unmount
    try { audio.current.drone?.g?.disconnect() } catch { /* ignore */ }
    try { audio.current.ac?.close() } catch { /* ignore */ }
  }, [])

  /* ---------- 3D globe engine (orthographic sphere, plain 2D canvas) ---------- */
  const litRef = useRef(0)
  useEffect(() => {
    const cv = canvasRef.current
    const wrap = mapWrapRef.current
    if (!cv || !wrap) return
    const ctx = cv.getContext('2d')
    let W = 0, H = 0, dpr = 1, cx = 0, cy = 0, baseR = 0
    let raf = 0, last = 0, acc = 0, yaw = 0
    /* view controls: eased zoom + drag-to-rotate with release momentum */
    let zoom = 1, zoomTarget = 1, pitch = -20 * D, spinVel = 0, lastInteract = 0
    let dragging = false, moved = false, downX = 0, downY = 0, lastX = 0, lastY = 0, overZoom = 0
    const ZMIN = 0.75, ZMAX = 3.6, PITCH_LIMIT = 1.15
    const e = engine.current
    /* spin around the polar axis (yaw), then tilt the pole toward the eye (pitch) */
    const rot = (v, cw, sw, cp, sp) => {
      const x = v[0] * cw + v[2] * sw, z = -v[0] * sw + v[2] * cw, y = v[1]
      return [x, y * cp - z * sp, y * sp + z * cp]
    }

    function resize() {
      const r = wrap.getBoundingClientRect()
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = r.width; H = r.height
      if (W < 2 || H < 2) return
      cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + 'px'; cv.style.height = H + 'px'
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      cx = W / 2; cy = H * 0.57; baseR = Math.min(W * 0.30, H * 0.46)
    }

    function spawnArc() {
      const live = e.players.filter((p) => !p.shadow)
      if (live.length < 2) return
      const a = live[Math.floor(Math.random() * live.length)]
      const b = live[Math.floor(Math.random() * live.length)]
      if (a === b) return
      e.arcs.push({ a: a.v, b: b.v, t: 0, speed: 0.006 + Math.random() * 0.008, gold: e.rush })
    }

    function draw(time) {
      if (W < 2 || H < 2) return
      const cw = Math.cos(yaw), sw = Math.sin(yaw)
      const cp = Math.cos(pitch), sp = Math.sin(pitch)
      const R = baseR * zoom
      const dim = e.eclipse ? 0.45 : 1
      ctx.clearRect(0, 0, W, H)

      /* atmosphere — thin gold halo bleeding into crimson */
      const atm = ctx.createRadialGradient(cx, cy, R * 0.92, cx, cy, R * 1.16)
      atm.addColorStop(0, 'rgba(198,167,92,0)')
      atm.addColorStop(0.6, `rgba(198,167,92,${0.10 * dim})`)
      atm.addColorStop(0.75, `rgba(122,18,32,${(e.eclipse ? 0.22 : 0.14)})`)
      atm.addColorStop(1, 'rgba(122,18,32,0)')
      ctx.fillStyle = atm; ctx.beginPath(); ctx.arc(cx, cy, R * 1.16, 0, 6.28); ctx.fill()

      /* obsidian sphere body */
      ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.28); ctx.clip()
      const body = ctx.createRadialGradient(cx - R * 0.28, cy - R * 0.34, R * 0.1, cx, cy, R * 1.05)
      body.addColorStop(0, '#14100c'); body.addColorStop(0.55, '#0d0709'); body.addColorStop(1, '#050303')
      ctx.fillStyle = body; ctx.fillRect(cx - R, cy - R, 2 * R, 2 * R)

      /* graticule — meridians + parallels, only the near hemisphere */
      ctx.strokeStyle = `rgba(198,167,92,${0.07 * dim})`; ctx.lineWidth = 1
      for (let lon = -180; lon < 180; lon += 30) {
        ctx.beginPath(); let started = false
        for (let lat = -80; lat <= 80; lat += 4) {
          const p = rot(llToVec(lat, lon), cw, sw, cp, sp)
          if (p[2] <= 0) { started = false; continue }
          const sx = cx + R * p[0], sy = cy - R * p[1]
          started ? ctx.lineTo(sx, sy) : ctx.moveTo(sx, sy); started = true
        }
        ctx.stroke()
      }
      for (let lat = -60; lat <= 60; lat += 30) {
        ctx.beginPath(); let started = false
        for (let lon = -180; lon <= 180; lon += 4) {
          const p = rot(llToVec(lat, lon), cw, sw, cp, sp)
          if (p[2] <= 0) { started = false; continue }
          const sx = cx + R * p[0], sy = cy - R * p[1]
          started ? ctx.lineTo(sx, sy) : ctx.moveTo(sx, sy); started = true
        }
        ctx.stroke()
      }

      /* land body — dim warm-gold texture (continents read as landmass); souls stay green */
      const col = e.rush ? '231,205,134' : '56,226,123'
      const dotS = 1.5 * Math.min(1.9, Math.sqrt(zoom)) // stay crisp as you zoom in
      for (const L of LAND) {
        const p = rot(L.v, cw, sw, cp, sp)
        if (p[2] <= 0.02) continue
        const sx = cx + R * p[0], sy = cy - R * p[1]
        const a = L.b * (0.35 + 0.65 * p[2]) * dim
        ctx.fillStyle = L.city ? `rgba(120,235,170,${a * 0.8})` : `rgba(191,158,96,${a * 0.6})`
        ctx.fillRect(sx, sy, dotS, dotS)
      }

      /* engraved country borders — gilded coastlines + political lines, near hemisphere only */
      ctx.lineJoin = 'round'; ctx.lineCap = 'round'
      ctx.strokeStyle = e.rush ? `rgba(240,214,150,${0.6 * dim})` : `rgba(214,186,120,${0.5 * dim})`
      ctx.lineWidth = zoom > 1.8 ? 1.1 : 0.85
      for (const ring of RINGS) {
        ctx.beginPath(); let bs = false
        for (let i = 0; i < ring.length; i++) {
          const p = rot(ring[i], cw, sw, cp, sp)
          if (p[2] <= 0.015) { bs = false; continue }
          const sx = cx + R * p[0], sy = cy - R * p[1]
          bs ? ctx.lineTo(sx, sy) : ctx.moveTo(sx, sy); bs = true
        }
        ctx.stroke()
      }
      ctx.restore()

      /* faint specular sheen — sells the sphere as lit from upper-left */
      ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.28); ctx.clip()
      const sh = ctx.createRadialGradient(cx - R * 0.32, cy - R * 0.4, 0, cx - R * 0.32, cy - R * 0.4, R * 0.9)
      sh.addColorStop(0, `rgba(231,205,134,${0.06 * dim})`); sh.addColorStop(1, 'rgba(231,205,134,0)')
      ctx.fillStyle = sh; ctx.fillRect(cx - R, cy - R, 2 * R, 2 * R); ctx.restore()

      /* transaction arcs — great circles lifting off the surface */
      for (let i = e.arcs.length - 1; i >= 0; i--) {
        const s = e.arcs[i]
        if (!e.frozen) s.t += s.speed * (e.eclipse ? 0.5 : 1)
        if (s.t >= 1) { e.arcs.splice(i, 1); continue }
        const pt = (t) => {
          const v = norm([s.a[0] * (1 - t) + s.b[0] * t, s.a[1] * (1 - t) + s.b[1] * t, s.a[2] * (1 - t) + s.b[2] * t])
          const lift = 1 + 0.28 * Math.sin(Math.PI * t)
          return rot([v[0] * lift, v[1] * lift, v[2] * lift], cw, sw, cp, sp)
        }
        ctx.strokeStyle = s.gold ? `rgba(231,205,134,${0.09 * dim})` : `rgba(150,240,180,${0.05 * dim})`
        ctx.lineWidth = 1; ctx.beginPath(); let st2 = false
        for (let t = 0; t <= 1; t += 0.04) {
          const p = pt(t); if (p[2] <= 0) { st2 = false; continue }
          const sx = cx + R * p[0], sy = cy - R * p[1]
          st2 ? ctx.lineTo(sx, sy) : ctx.moveTo(sx, sy); st2 = true
        }
        ctx.stroke()
        for (let k = 0; k < 8; k++) {
          const t = s.t - k * 0.02; if (t < 0 || t > 1) continue
          const p = pt(t); if (p[2] <= 0) continue
          const sx = cx + R * p[0], sy = cy - R * p[1]
          const a = (1 - k / 8) * 0.9 * dim
          ctx.fillStyle = s.gold ? `rgba(255,214,120,${a})` : `rgba(170,255,200,${a})`
          ctx.beginPath(); ctx.arc(sx, sy, Math.max(2.4 - k * 0.22, 0.5), 0, 6.28); ctx.fill()
        }
      }

      /* souls — only those on the near face; track screen pos for hover/dossier */
      let lit = 0
      for (const p of e.players) {
        const q = rot(p.v, cw, sw, cp, sp)
        p.vis = q[2] > 0.02
        if (!p.vis) continue
        const sx = cx + R * q[0], sy = cy - R * q[1]
        p.sx = sx; p.sy = sy
        const depth = 0.4 + 0.6 * q[2]
        if (p.shadow) {
          ctx.strokeStyle = `rgba(122,18,32,${0.55 * depth})`; ctx.lineWidth = 1.2
          ctx.beginPath(); ctx.arc(sx, sy, 4.5, 0, 6.28); ctx.stroke()
          ctx.fillStyle = `rgba(76,12,21,${0.5 * depth})`; ctx.beginPath(); ctx.arc(sx, sy, 1.4, 0, 6.28); ctx.fill()
          continue
        }
        lit++
        const b = e.reduce ? 0.7 : 0.55 + 0.45 * Math.sin(time * 0.0018 + p.phase)
        const g = ctx.createRadialGradient(sx, sy, 0, sx, sy, 14)
        g.addColorStop(0, `rgba(${col},${0.6 * b * depth * dim})`); g.addColorStop(1, `rgba(${col},0)`)
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(sx, sy, 14, 0, 6.28); ctx.fill()
        ctx.fillStyle = e.rush ? `rgba(255,236,190,${0.9 * depth})` : `rgba(214,255,224,${0.92 * depth})`
        ctx.beginPath(); ctx.arc(sx, sy, 2, 0, 6.28); ctx.fill()
      }
      if (litRef.current !== lit) litRef.current = lit

      /* labels — hubs always; every soul once you zoom in. Fade toward the limb */
      ctx.font = '10px ui-monospace,"Cascadia Code",Consolas,monospace'; ctx.textBaseline = 'middle'
      const labelAll = zoom > 1.8
      const thr = zoom > 1.6 ? 0.2 : 0.35
      for (const p of e.players) {
        if (p.shadow || (!p.hub && !labelAll)) continue
        const q = rot(p.v, cw, sw, cp, sp)
        if (q[2] <= thr) continue
        const sx = cx + R * q[0], sy = cy - R * q[1]
        const a = Math.min(1, (q[2] - thr) / 0.28)
        ctx.strokeStyle = `rgba(198,167,92,${0.3 * a})`; ctx.lineWidth = 1
        ctx.beginPath(); ctx.moveTo(sx + 3, sy - 3); ctx.lineTo(sx + 11, sy - 11); ctx.stroke()
        ctx.fillStyle = `rgba(231,205,134,${0.9 * a})`
        ctx.fillText(p.hub ? p.city.toUpperCase() : p.city, sx + 14, sy - 12)
      }
    }

    /* keep wheeling in at max magnification → the Eye descends onto the point
       under the crosshair (nearest living soul, else the bare coordinates) */
    function triggerDescend() {
      let best = null, bd = 150
      for (const p of e.players) {
        if (!p.vis || p.shadow) continue
        const d = Math.hypot(p.sx - cx, p.sy - cy)
        if (d < bd) { bd = d; best = p }
      }
      if (best) { onDescendRef.current?.({ lat: best.lat, lon: best.lon, name: best.name, sub: `${best.city}, ${best.country}` }); return }
      const lat = Math.max(-85, Math.min(85, pitch / D))
      const lon = ((-yaw / D + 540) % 360) - 180
      onDescendRef.current?.({ lat, lon, name: 'Неизвестный сектор', sub: `${lat.toFixed(2)}, ${lon.toFixed(2)}` })
    }

    function loop(time) {
      const dt = last ? Math.min(time - last, 60) : 16
      last = time
      if (e.paused) { raf = requestAnimationFrame(loop); return } // on the descent map
      zoom += (zoomTarget - zoom) * 0.12 // eased zoom
      if (!e.reduce && !e.frozen) {
        if (!dragging) {
          yaw += spinVel                 // coast on release momentum…
          spinVel *= 0.94
          if (Math.abs(spinVel) < 0.00003 && time - lastInteract > 2200) yaw += dt * 0.00008 // …then resume the slow drift
        }
        acc += dt
        const interval = e.rush ? 120 : e.eclipse ? 900 : 420
        if (acc > interval) { acc = 0; if (e.arcs.length < (e.rush ? 40 : 20)) spawnArc() }
      }
      draw(time)
      raf = requestAnimationFrame(loop)
    }

    /* ---- mouse: wheel to zoom, grab to rotate, click a soul for its dossier ---- */
    const markInteract = () => {
      lastInteract = performance.now()
      if (!interactedRef.current) { interactedRef.current = true; setInteracted(true) }
    }
    const localXY = (ev) => { const r = cv.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top] }
    const onWheel = (ev) => {
      ev.preventDefault()
      // once pinned at max magnification, further zoom-in intent charges the descent
      if (zoomTarget >= ZMAX - 1e-3 && ev.deltaY < 0) {
        overZoom += -ev.deltaY
        if (overZoom > 220) { overZoom = 0; triggerDescend() }
      } else if (ev.deltaY > 0) { overZoom = 0 }
      zoomTarget = Math.min(ZMAX, Math.max(ZMIN, zoomTarget * Math.exp(-ev.deltaY * 0.0015)))
      markInteract()
    }
    const onDown = (ev) => {
      dragging = true; moved = false; spinVel = 0
      downX = lastX = ev.clientX; downY = lastY = ev.clientY
      try { cv.setPointerCapture(ev.pointerId) } catch { /* ignore */ }
      cv.style.cursor = 'grabbing'; markInteract()
    }
    const onMove = (ev) => {
      if (dragging) {
        const dx = ev.clientX - lastX, dy = ev.clientY - lastY
        lastX = ev.clientX; lastY = ev.clientY
        if (Math.abs(ev.clientX - downX) + Math.abs(ev.clientY - downY) > 3) moved = true
        const k = 0.005 / Math.max(zoom, 0.8)
        yaw += dx * k
        pitch = Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, pitch + dy * k * 0.8))
        spinVel = dx * k
        markInteract()
        return
      }
      const [mx, my] = localXY(ev)
      const p = nearest(mx, my)
      if (p) { cv.style.cursor = 'pointer'; setTip({ x: p.sx, y: p.sy, name: p.name, city: p.city, country: p.country }) }
      else { cv.style.cursor = 'grab'; setTip(null) }
    }
    const onUp = (ev) => {
      if (!dragging) return
      dragging = false
      try { cv.releasePointerCapture(ev.pointerId) } catch { /* ignore */ }
      cv.style.cursor = 'grab'
      if (!moved) { const [mx, my] = localXY(ev); const p = nearest(mx, my); if (p) { setDossierId(p.id); playTone('tick') } }
      markInteract()
    }
    const onLeave = () => { if (!dragging) { cv.style.cursor = 'grab'; setTip(null) } }

    cv.addEventListener('wheel', onWheel, { passive: false })
    cv.addEventListener('pointerdown', onDown)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    cv.addEventListener('pointerleave', onLeave)

    const ro = new ResizeObserver(resize)
    ro.observe(wrap)
    resize()
    cv.style.cursor = 'grab'
    if (e.reduce) for (let i = 0; i < 8; i++) spawnArc()
    raf = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(raf); ro.disconnect()
      cv.removeEventListener('wheel', onWheel)
      cv.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      cv.removeEventListener('pointerleave', onLeave)
    }
  }, [])

  /* ---------- pointer: hover tip, drag-rotate, wheel-zoom (bound in the engine effect) ---------- */
  const [tip, setTip] = useState(null)
  const [interacted, setInteracted] = useState(false)
  const interactedRef = useRef(false)
  const nearest = (mx, my) => {
    let best = null, bd = 16
    for (const p of engine.current.players) {
      if (!p.vis) continue
      const d = Math.hypot(p.sx - mx, p.sy - my); if (d < bd) { bd = d; best = p }
    }
    return best
  }

  /* ---------- levers & rites ---------- */
  const onLever = (key, value) => {
    setLevers((l) => ({ ...l, [key]: value }))
    if (Math.random() < 0.15) playTone('tick')
    // TODO(live): debounce → saveEconomySettings/saveFarmSettings with the mapped field.
  }
  const setRite = (key) => {
    setRites((prev) => {
      const on = !prev[key]
      const next = { ...prev, [key]: on }
      if (key === 'rush') {
        engine.current.rush = on
        if (on) { next.eclipse = false; engine.current.eclipse = false }
        setDecree(on ? 'rush' : null)
        playTone(on ? 'gold' : 'off')
        toast(on ? '🜚 Золотая Лихорадка объявлена · золото хлынуло' : 'Лихорадка утихла', '', '🜚')
      }
      if (key === 'eclipse') {
        engine.current.eclipse = on
        if (on) { next.rush = false; engine.current.rush = false }
        setDecree(on ? 'eclipse' : null)
        playTone(on ? 'low' : 'off')
        toast(on ? '🜄 Затмение · мир беднеет' : 'Затмение отступило', '', '🜄')
      }
      if (key === 'silence') {
        playTone(on ? 'low' : 'off')
        toast(on ? '🜃 Биржа умолкла для всех' : 'Голоса торга вернулись', '', '🜃')
      }
      // keep decree in sync when rush/eclipse cancel each other
      if (key === 'rush' && on) setDecree('rush')
      if (key === 'eclipse' && on) setDecree('eclipse')
      return next
    })
    // TODO(live): map rites to event_scheduler / economy_settings toggles.
  }

  /* ---------- shadowban / pardon ---------- */
  const shadowban = (p) => {
    if (p.shadow) return
    p.shadow = true
    forceTick((n) => n + 1)
    toast('Иллюзия соткана · ' + p.name + ' заперт в тени', 'wrath', '◐')
    playTone('shadow')
    // TODO(live): POST a real shadowban flag; the bot keeps responding but drops writes.
  }
  const pardon = (p) => {
    if (!p.shadow) { toast(p.name + ' и так на свету', '', '✧'); return }
    p.shadow = false
    forceTick((n) => n + 1)
    toast(p.name + ' помилован · возвращён в базу', '', '✧')
  }

  /* ---------- «Око нисходит» — descend onto a real location ---------- */
  const descend = useCallback((target) => {
    if (!target) return
    engine.current.paused = true // freeze the globe RAF while we're on the map
    setDossierId(null)
    setFocus(target)
    playTone('low')
    toast('Око нисходит · ' + target.name, '', '◉')
  }, [playTone, toast])
  const rise = useCallback(() => {
    engine.current.paused = false
    setFocus(null)
    playTone('rise')
  }, [playTone])
  useEffect(() => { onDescendRef.current = descend }, [descend])

  /* ---------- ragnarok (hold to arm) ---------- */
  const ragFill = useRef(null)
  const holdRAF = useRef(0)
  const HOLD = 1400
  const beginHold = () => {
    if (engine.current.frozen) return
    const start = performance.now()
    const step = (t) => {
      const p = Math.min((t - start) / HOLD, 1)
      if (ragFill.current) ragFill.current.style.width = p * 100 + '%'
      if (p >= 1) { ragnarok(); return }
      holdRAF.current = requestAnimationFrame(step)
    }
    holdRAF.current = requestAnimationFrame(step)
  }
  const endHold = () => {
    cancelAnimationFrame(holdRAF.current)
    if (!engine.current.frozen && ragFill.current) ragFill.current.style.width = '0%'
  }
  const ragnarok = () => {
    engine.current.frozen = true
    setFrozen(true)
    if (ragFill.current) ragFill.current.style.width = '100%'
    playTone('gong')
    // TODO(live): call a guarded /system freeze — NOT wired; freezes only this view.
  }
  const thaw = () => {
    engine.current.frozen = false
    setFrozen(false)
    if (ragFill.current) ragFill.current.style.width = '0%'
    toast('Мир оживлён · время течёт вновь', '', '✧')
  }

  /* ---------- console ---------- */
  const consoleInput = useRef(null)
  const onConsole = (ev) => {
    ev.preventDefault()
    const v = (consoleInput.current?.value || '').trim()
    if (!v) return
    pushChron(`<span class="g">Воля Архитектора:</span> ${v.replace(/[<>]/g, '')}`)
    toast('Воля начертана · ' + v.slice(0, 40), '', '◉')
    playTone('tick')
    consoleInput.current.value = ''
  }

  /* ---------- keyboard ---------- */
  useEffect(() => {
    const onKey = (ev) => {
      if (ev.key === 'Escape') {
        if (focus) { rise(); return }
        if (dossierId != null) { setDossierId(null); return }
        onExit?.()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dossierId, onExit, focus, rise])

  useEffect(() => { if (!reduce) playTone('rise') }, []) // entrance sting (no-op unless sound on)

  return (
    <div className={`cc${reduce ? ' cc-reduce' : ''}${frozen ? ' cc-frozen' : ''}`}>
      {/* rail */}
      <nav className="cc-rail" aria-label="Командный пункт">
        <button className="cc-glyph cc-on" title="Карта Мира">◬</button>
        <button className="cc-glyph" title="Всевидящее око · надзор">⊚</button>
        <button className="cc-glyph" title="Великая Алхимия">🜛</button>
        <button className="cc-glyph" title="Судьбы">☿</button>
        <span className="cc-sep" />
        <button className="cc-glyph" data-kill="true" title="Рагнарёк" onClick={() => { toast('Удерживай печать Рагнарёка внизу', 'wrath', '🜏') }}>🜏</button>
        <button className="cc-glyph" title="Свернуть · вернуться в кабинет (ESC)" onClick={() => onExit?.()}>⟲<small>ESC</small></button>
      </nav>

      {/* top */}
      <header className="cc-top">
        <div className="cc-brand">Ordo</div>
        <div className="cc-stat"><b>{fmt(counters.tx)}</b><span>Сделок / мин</span></div>
        <div className="cc-stat"><b>{new Set(engine.current.players.map((p) => p.country)).size}</b><span>Стран</span></div>
        <div className="cc-stat"><b style={{ color: frozen ? '#8fc7e0' : rites.rush ? '#E7CD86' : rites.eclipse ? '#c76' : undefined }}>{counters.pulse}</b><span>Пульс бота</span></div>
        <div className="cc-spacer" />
        <button className={`cc-tbtn${soundOn ? ' cc-on' : ''}`} onClick={toggleSound} aria-pressed={soundOn} title="Ритуальный гул">♪</button>
      </header>

      {/* map */}
      <div className="cc-map" ref={mapWrapRef}>
        <canvas ref={canvasRef} className="cc-world" />
        <div className={`cc-maphint${interacted ? ' cc-hidden' : ''}`} aria-hidden="true">
          <span>колесо — приблизить</span><span>тяни — вращать мир</span><span>глубже — сойти к дому</span>
        </div>
        <div className={`cc-decree${decree ? ' cc-decree-' + decree : ''}`}>
          {decree === 'rush' ? '🜚 Золотая Лихорадка' : decree === 'eclipse' ? '🜄 Затмение · Кризис' : ''}
        </div>

        <div className="cc-crown">
          <svg className="cc-crown-eye" viewBox="0 0 120 96" fill="none" aria-hidden="true">
            <g className="cc-rays" stroke="#8A6D2F" strokeWidth="1">
              <line x1="60" y1="8" x2="60" y2="-6" /><line x1="60" y1="8" x2="40" y2="-2" /><line x1="60" y1="8" x2="80" y2="-2" />
              <line x1="60" y1="8" x2="26" y2="6" /><line x1="60" y1="8" x2="94" y2="6" />
            </g>
            <path d="M60 14 L104 84 L16 84 Z" stroke="#C6A75C" strokeWidth="1.4" fill="rgba(198,167,92,0.04)" />
            <path d="M60 14 L60 84 M38 49 L82 49" stroke="#5E4A20" strokeWidth=".7" />
            <ellipse cx="60" cy="64" rx="19" ry="10" stroke="#E7CD86" strokeWidth="1.3" />
            <circle cx="60" cy="64" r="4.6" fill="#E7CD86" />
            <circle cx="60" cy="64" r="10" stroke="#C6A75C" strokeWidth=".7" />
          </svg>
          <div className="cc-crown-title">◉ Командный Пункт <span>· Архитектор: <b>{architectName}</b></span></div>
          <div className="cc-crown-sub">Влияние в матрице: <span className="cc-num">{fmt(counters.souls)}</span> душ · <em style={{ color: frozen ? '#8fc7e0' : rites.rush ? '#E7CD86' : rites.eclipse ? '#c76' : undefined }}>{counters.stable}</em></div>
        </div>

        <aside className="cc-chron">
          <h4>Хроники Бытия</h4>
          <div className="cc-chron-feed">
            {chron.map((l) => (
              <div className="cc-chron-line" key={l.id}><span className="t">{l.t}</span> <span dangerouslySetInnerHTML={{ __html: l.html }} /></div>
            ))}
          </div>
        </aside>

        <div className="cc-vig" />
        {tip && (
          <div className="cc-tip" style={{ left: tip.x, top: tip.y }}>
            <span className="c">{tip.name}</span> · <small>{tip.city}, {tip.country}</small>
          </div>
        )}
        <div className="cc-legend">
          <span><i style={{ background: '#38E27B', boxShadow: '0 0 6px #38E27B' }} />Живая душа</span>
          <span><i style={{ background: '#B31E2B', boxShadow: '0 0 6px #7A1220' }} />Тень (shadowban)</span>
          <span><i style={{ background: '#9be7b4' }} />Сделка</span>
        </div>

        <form className="cc-console" autoComplete="off" onSubmit={onConsole}>
          <span className="cc-prompt">&gt;_</span>
          <input ref={consoleInput} placeholder="начертать волю Архитектора…" aria-label="Командная консоль" />
        </form>
      </div>

      {/* alchemy */}
      <aside className="cc-alch">
        <h3>🜛 Великая Алхимия</h3>
        <p className="cc-h-sub">Законы физики бота · ручной привод</p>

        <div className="cc-lever">
          <div className="cc-lh"><div><span className="cc-ll">Шанс крафта</span><span className="cc-lc">вероятность успеха</span></div><span className="cc-lv">{levers.craft}%</span></div>
          <input className="cc-dial" type="range" min="0" max="100" value={levers.craft} aria-label="Шанс крафта"
            style={{ '--f': levers.craft + '%' }} onChange={(e) => onLever('craft', +e.target.value)} />
        </div>
        <div className="cc-lever">
          <div className="cc-lh"><div><span className="cc-ll">Налог биржи</span><span className="cc-lc">комиссия сделок</span></div><span className="cc-lv">{levers.tax}%</span></div>
          <input className="cc-dial" type="range" min="0" max="40" value={levers.tax} aria-label="Налог биржи"
            style={{ '--f': (levers.tax / 40) * 100 + '%' }} onChange={(e) => onLever('tax', +e.target.value)} />
        </div>
        <div className="cc-lever">
          <div className="cc-lh"><div><span className="cc-ll">Гравитация золота</span><span className="cc-lc">частота дропа</span></div><span className="cc-lv">×{(levers.gravity / 100).toFixed(1)}</span></div>
          <input className="cc-dial" type="range" min="20" max="300" value={levers.gravity} aria-label="Гравитация золота"
            style={{ '--f': ((levers.gravity - 20) / 280) * 100 + '%' }} onChange={(e) => onLever('gravity', +e.target.value)} />
        </div>

        <div className="cc-rites">
          <div className="cc-rite">
            <div><div className="cc-rt">🜚 Золотая Лихорадка</div><div className="cc-rd">глобальный ивент изобилия</div></div>
            <button className={`cc-latch${rites.rush ? ' cc-on' : ''}`} role="switch" aria-checked={rites.rush} aria-label="Золотая Лихорадка" onClick={() => setRite('rush')} />
          </div>
          <div className="cc-rite">
            <div><div className="cc-rt">🜄 Затмение</div><div className="cc-rd">экономический кризис</div></div>
            <button className={`cc-latch${rites.eclipse ? ' cc-on' : ''}`} role="switch" aria-checked={rites.eclipse} aria-label="Затмение" onClick={() => setRite('eclipse')} />
          </div>
          <div className="cc-rite cc-doom">
            <div><div className="cc-rt">🜃 Обет Молчания</div><div className="cc-rd">заморозить биржу для всех</div></div>
            <button className={`cc-latch cc-doom${rites.silence ? ' cc-on' : ''}`} role="switch" aria-checked={rites.silence} aria-label="Обет молчания" onClick={() => setRite('silence')} />
          </div>
        </div>
      </aside>

      {/* ragnarok */}
      <footer className="cc-rag">
        <div className="cc-rag-lbl">Экстренный протокол<b>необратимо для всех сессий</b></div>
        <span className="cc-rag-hint">Удерживай печать · 1.4с</span>
        <div className="cc-spacer" />
        <button className="cc-rag-seal" onPointerDown={beginHold} onPointerUp={endHold} onPointerLeave={endHold}
          onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) beginHold() }} onKeyUp={endHold}>
          <span className="cc-fill" ref={ragFill} /><span>🜏 Рагнарёк</span>
        </button>
      </footer>

      {/* dossier */}
      {dossier && (
        <aside className="cc-dossier cc-open">
          <button className="cc-dclose" onClick={() => setDossierId(null)} aria-label="Закрыть досье">✕</button>
          <div className="cc-dhead">
            <div className="cc-dav">{dossier.name[0].toUpperCase()}</div>
            <div><div className="cc-dn">{dossier.name}</div><div className="cc-di">ID {dossier.id} · {dossier.dev}</div></div>
          </div>
          <span className={`cc-dstate${dossier.shadow ? ' cc-shadow' : ''}`}>{dossier.shadow ? '◐ Заперт в иллюзии' : '● Активен · пишется в базу'}</span>
          <div className="cc-drow"><span className="k">IP-адрес</span><span className="v">{dossier.ip}</span></div>
          <div className="cc-drow"><span className="k">Геолокация</span><span className="v">{dossier.city}, {dossier.country}</span></div>
          <div className="cc-drow"><span className="k">Координаты</span><span className="v">{dossier.lat.toFixed(2)}, {dossier.lon.toFixed(2)}</span></div>
          <div className="cc-drow"><span className="k">Баланс</span><span className="v">◇ {fmt(dossier.bal)}</span></div>
          <div className="cc-drow"><span className="k">Последний вход</span><span className="v">{dossier.seen}</span></div>
          <div className="cc-dsus">
            <div className="cc-sl"><span>Индекс подозрительности</span><span>{dossier.sus}%</span></div>
            <div className="cc-bar"><i style={{ width: dossier.sus + '%' }} /></div>
          </div>
          <button className="cc-eye-btn" onClick={() => descend({ lat: dossier.lat, lon: dossier.lon, name: dossier.name, sub: `${dossier.city}, ${dossier.country}` })}>
            ◉ Навести Око<span className="sub">сойти к реальному месту · дом, улица, село</span>
          </button>
          <div className="cc-dacts">
            <button className={`cc-wrath-btn${dossier.shadow ? ' cc-done' : ''}`} onClick={() => shadowban(dossier)}>
              <span className="g">🜏</span>
              <span>{dossier.shadow ? 'Иллюзия уже соткана' : 'Луч Гнева · Shadowban'}
                <span className="sub">{dossier.shadow ? 'действия не пишутся в базу' : 'бот «работает», но действия исчезают'}</span></span>
            </button>
            <button className="cc-calm-btn" onClick={() => pardon(dossier)}>✧ Помиловать<span className="sub">снять теневой бан</span></button>
          </div>
        </aside>
      )}

      {/* freeze */}
      {frozen && (
        <div className="cc-freeze">
          <div className="cc-fbox">
            <svg className="cc-fsig" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M12 2v20M2 12h20M5 5l14 14M19 5L5 19" /></svg>
            <div className="cc-ft">Система заморожена</div>
            <div className="cc-fs">Рагнарёк исполнен. Основной бот остановлен, действия игроков не пишутся в базу. Время застыло по воле Владельца.</div>
            <button className="cc-thaw" onClick={thaw}>Оживить мир</button>
          </div>
        </div>
      )}

      {/* «Око нисходит» — real dark-satellite descent */}
      {focus && <CommandMap target={focus} onRise={rise} dim={rites.eclipse} />}

      {/* toasts */}
      <div className="cc-toasts">
        {toasts.map((t) => (
          <div className={`cc-toast${t.kind === 'wrath' ? ' cc-wrath' : ''}`} key={t.id}>
            {t.icon && <span className="i">{t.icon}</span>}{t.msg}
          </div>
        ))}
      </div>
    </div>
  )
}
