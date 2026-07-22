import { useEffect, useRef, useState } from 'react'

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

// Витрина приза: если админ прикрепил к розыгрышу анимацию (видео-стикер
// Telegram .webm или Lottie-json — например «мишку», купленного в TG), она
// крутится вместо статичного эмодзи. Без animation ведёт себя как раньше —
// просто рендерит emoji, так что все существующие розыгрыши не меняются.
export default function AnimatedPrizeIcon({ emoji, animation, iconClassName, mediaClassName }) {
  const [failed, setFailed] = useState(false)

  if (!animation?.url || failed) {
    return <span className={iconClassName} aria-hidden>{emoji}</span>
  }

  if (animation.type === 'lottie') {
    return <LottieMedia url={animation.url} className={mediaClassName} onError={() => setFailed(true)} />
  }

  const reduced = prefersReducedMotion()
  return (
    <video
      className={mediaClassName}
      src={animation.url}
      autoPlay={!reduced}
      loop={!reduced}
      muted
      playsInline
      preload="auto"
      onError={() => setFailed(true)}
      aria-hidden
    />
  )
}

function LottieMedia({ url, className, onError }) {
  const containerRef = useRef(null)

  useEffect(() => {
    let anim = null
    let cancelled = false

    Promise.all([
      import('lottie-web'),
      fetch(url).then((res) => {
        if (!res.ok) throw new Error(`lottie fetch ${res.status}`)
        return res.json()
      }),
    ])
      .then(([{ default: lottie }, animationData]) => {
        if (cancelled || !containerRef.current) return
        const reduced = prefersReducedMotion()
        anim = lottie.loadAnimation({
          container: containerRef.current,
          renderer: 'svg',
          loop: !reduced,
          autoplay: !reduced,
          animationData,
        })
      })
      .catch(() => { if (!cancelled) onError() })

    return () => {
      cancelled = true
      anim?.destroy()
    }
  }, [url, onError])

  return <div ref={containerRef} className={className} aria-hidden />
}
