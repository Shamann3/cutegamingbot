import { useEffect, useRef, useState } from 'react'

const HOLD_MS = 1800
const EXIT_MS = 700

export default function SplashPage({ displayName, onFinished }) {
  const [leaving, setLeaving] = useState(false)
  const doneRef = useRef(false)

  useEffect(() => {
    const t1 = setTimeout(() => setLeaving(true), HOLD_MS)
    const t2 = setTimeout(() => {
      if (!doneRef.current) { doneRef.current = true; onFinished() }
    }, HOLD_MS + EXIT_MS)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [onFinished])

  return (
    <div className="egl-screen">
      <p className={`egl-welcome ${leaving ? 'egl-welcome--out' : 'egl-welcome--in'}`}>
        Добро пожаловать{displayName ? `, ${displayName}` : ''}
      </p>
    </div>
  )
}
