import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

/**
 * «Око нисходит» — the All-Seeing Eye descends onto a real location.
 *
 * When the Architect over-zooms the ritual globe (or points the Eye at a soul
 * from their dossier), we drop out of the hand-drawn obsidian globe and into a
 * real dark-satellite map framed by the ritual HUD: reticle, vignette, corner
 * brackets, and a live coordinate/altitude readout. Zoom carries all the way
 * down to streets, a village, a single house.
 *
 * Imagery: Esri World Imagery (no API key). Tiles are dimmed + warmed by CSS
 * (`.cc-mapview .leaflet-tile-pane`) so the real world reads as obsidian & gold.
 */

const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const RISE_Z = 4.3    // scroll out to here and the Eye ascends back to the globe
const HOUSE_Z = 18    // as deep as the descent flies on arrival

export default function CommandMap({ target, onRise, dim = false }) {
  const hostRef = useRef(null)
  const mapRef = useRef(null)
  const armedRef = useRef(false)
  const [read, setRead] = useState({ lat: target.lat, lon: target.lon, z: 6 })

  useEffect(() => {
    const map = L.map(hostRef.current, {
      zoomControl: false, attributionControl: true,
      minZoom: 3, maxZoom: 19, zoomSnap: 0, zoomDelta: 0.6,
      wheelPxPerZoomLevel: 90, worldCopyJump: true,
    })
    mapRef.current = map
    L.tileLayer(ESRI, { maxZoom: 19, attribution: 'Esri · Maxar · Earthstar Geographics' }).addTo(map)

    const at = [target.lat, target.lon]
    // the descent: arrive high, then fall onto the target
    map.setView(at, 6, { animate: false })
    map.flyTo(at, HOUSE_Z, { duration: 2.6, easeLinearity: 0.14 })

    // targeted soul, pulsing green over their real rooftop
    const icon = L.divIcon({
      className: '', iconSize: [18, 18],
      html: `<div class="cc-soulpin"><span>${escapeHtml(target.name)}</span></div>`,
    })
    L.marker(at, { icon, interactive: false }).addTo(map)

    const sync = () => {
      const c = map.getCenter()
      setRead({ lat: c.lat, lon: c.lng, z: map.getZoom() })
      // scroll all the way out → the Eye ascends
      if (armedRef.current && map.getZoom() <= RISE_Z) { armedRef.current = false; onRise() }
    }
    map.on('move zoom', sync)
    // don't let the initial descent (which passes through low zoom) trip the ascent
    const armT = setTimeout(() => { armedRef.current = true }, 2900)
    sync()

    return () => { clearTimeout(armT); map.off(); map.remove(); mapRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className={`cc-mapview${dim ? ' cc-mapview-dim' : ''}`}>
      <div ref={hostRef} className="cc-mapcanvas" />

      {/* ritual HUD over the real world */}
      <div className="cc-mapframe" aria-hidden="true">
        <span className="cc-mbrk tl" /><span className="cc-mbrk tr" />
        <span className="cc-mbrk bl" /><span className="cc-mbrk br" />
        <div className="cc-reticle">
          <svg viewBox="0 0 220 220">
            <circle cx="110" cy="110" r="96" fill="none" stroke="rgba(198,167,92,.32)" strokeWidth="1" strokeDasharray="3 8" />
            <circle cx="110" cy="110" r="58" fill="none" stroke="rgba(231,205,134,.5)" strokeWidth="1" />
            <path d="M110 8 v32 M110 180 v32 M8 110 h32 M180 110 h32" stroke="rgba(231,205,134,.6)" strokeWidth="1" />
            <circle cx="110" cy="110" r="2.4" fill="rgba(231,205,134,.9)" />
          </svg>
        </div>
        <div className="cc-scan" />
      </div>

      <div className="cc-mhud tl">
        <div className="cc-mhud-t">◉ Око наведено</div>
        <div className="cc-mhud-s"><span className="k">цель:</span> {target.name}{target.sub ? ` · ${target.sub}` : ''}</div>
      </div>
      <div className="cc-mhud tr">
        <div>{read.lat.toFixed(4)}, {normLon(read.lon).toFixed(4)}</div>
        <div className="cc-mhud-s"><span className="k">высота Ока:</span> z{read.z.toFixed(1)}</div>
      </div>

      <button className="cc-rise" onClick={onRise}>▲ Подняться <small>ESC</small></button>
    </div>
  )
}

function escapeHtml(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])) }
function normLon(l) { return ((l + 540) % 360) - 180 }
