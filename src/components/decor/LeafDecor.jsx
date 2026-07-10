/** SVG-листья и папоротники для рамок и декора (без emoji). */
import { useId } from 'react'

export function VineLeaf({ className = '', flip = false }) {
  return (
    <svg
      viewBox="0 0 32 20"
      className={`${flip ? 'scale-x-[-1]' : ''} ${className}`}
      aria-hidden
    >
      <path
        d="M2 18 C6 12 10 8 16 6 C22 8 26 12 30 18 C24 16 20 14 16 12 C12 14 8 16 2 18 Z"
        fill="#3d8f52"
      />
      <path
        d="M8 14 C10 11 13 9 16 8 C19 9 22 11 24 14 C21 13 18 12 16 11 C14 12 11 13 8 14 Z"
        fill="#5cb86a"
      />
      <path d="M15 11 L16 4 L17 11 Z" fill="#2e6b3a" />
    </svg>
  )
}

export function FernFrond({ className = '', flip = false }) {
  return (
    <svg
      viewBox="0 0 80 140"
      className={`${flip ? 'scale-x-[-1]' : ''} ${className}`}
      aria-hidden
    >
      <path d="M40 140 Q38 100 40 70 Q42 40 40 8" stroke="#1e4d30" strokeWidth="3" fill="none" />
      {[
        [40, 28, -28, -12],
        [40, 42, -32, -8],
        [40, 56, -30, -6],
        [40, 70, -26, -4],
        [40, 84, -22, -3],
        [40, 28, 28, -12],
        [40, 42, 32, -8],
        [40, 56, 30, -6],
        [40, 70, 26, -4],
        [40, 84, 22, -3],
      ].map(([cx, cy, dx, dy], i) => (
        <path
          key={i}
          d={`M${cx} ${cy} Q${cx + dx * 0.5} ${cy + dy * 0.5} ${cx + dx} ${cy + dy}`}
          stroke="#2d6b42"
          strokeWidth="2.5"
          fill="none"
        />
      ))}
      {[
        [32, 30, -18, -8],
        [48, 30, 18, -8],
        [30, 48, -20, -6],
        [50, 48, 20, -6],
        [28, 64, -18, -5],
        [52, 64, 18, -5],
      ].map(([x, y, dx, dy], i) => (
        <ellipse
          key={`e${i}`}
          cx={x + dx * 0.6}
          cy={y + dy * 0.6}
          rx={10}
          ry={5}
          fill="#3a8a50"
          transform={`rotate(${dx < 0 ? -35 : 35} ${x} ${y})`}
          opacity="0.9"
        />
      ))}
    </svg>
  )
}

export function GoldCorner({ className = '', rotate = 0 }) {
  const gradId = `corner-${useId().replace(/:/g, '')}`

  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      style={{ transform: `rotate(${rotate}deg)` }}
      aria-hidden
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#6b4423" />
          <stop offset="50%" stopColor="#f5d67a" />
          <stop offset="100%" stopColor="#fde68a" />
        </linearGradient>
      </defs>
      <path
        d="M2 22 C2 12 6 4 22 2"
        fill="none"
        stroke={`url(#${gradId})`}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M6 18 C6 14 9 10 16 8"
        fill="none"
        stroke="#fde68a"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  )
}
