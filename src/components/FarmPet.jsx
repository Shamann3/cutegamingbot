import { useEffect, useRef, useState } from 'react'

// Питомец живёт НА грядках: перескакивает между случайными точками над сеткой,
// смотрит по направлению прыжка и делает маленькие «фермерские» дела.
const EMOTES = ['🌱', '💧', '💕', '✨', '💤', '🐛', '🎵']

function randomSpot() {
  return { x: 14 + Math.random() * 72, y: 24 + Math.random() * 56 }
}

export default function FarmPet({ emoji }) {
  const [spot, setSpot] = useState(randomSpot)
  const [facing, setFacing] = useState(1)
  const [emote, setEmote] = useState(null)
  const [hop, setHop] = useState(0)
  const prevX = useRef(spot.x)

  useEffect(() => {
    if (!emoji) return undefined
    let alive = true
    let emoteTimer
    let showTimer

    const roam = () => {
      if (!alive) return
      const next = randomSpot()
      setFacing(next.x >= prevX.current ? 1 : -1)
      prevX.current = next.x
      setSpot(next)
      setHop((h) => h + 1)
      // прискакав заняться делом
      emoteTimer = window.setTimeout(() => {
        if (!alive) return
        setEmote(EMOTES[Math.floor(Math.random() * EMOTES.length)])
        showTimer = window.setTimeout(() => alive && setEmote(null), 1900)
      }, 1500)
    }

    roam()
    const id = window.setInterval(roam, 3900)
    return () => {
      alive = false
      window.clearInterval(id)
      window.clearTimeout(emoteTimer)
      window.clearTimeout(showTimer)
    }
  }, [emoji])

  if (!emoji) return null

  return (
    <div className="farm-pet-layer" aria-hidden>
      <div className="farm-pet-body" style={{ left: `${spot.x}%`, top: `${spot.y}%` }}>
        <div key={hop} className="farm-pet-move">
          <span className="farm-pet-shadow" />
          <span className="farm-pet-hop">
            <span className="farm-pet-glyph" style={{ transform: `scaleX(${facing})` }}>{emoji}</span>
          </span>
        </div>
        {emote && <span className="farm-pet-emote">{emote}</span>}
      </div>
    </div>
  )
}
