/**
 * Орнаментальная золотая рамка с листьями (мокап).
 */
import { useId } from 'react'
import { GoldCorner, VineLeaf } from './decor/LeafDecor'

export default function VineFrame({ children, className = '', dashed = false, ...rest }) {
  const gradId = `gold-${useId().replace(/:/g, '')}`

  return (
    <div
      className={`farm-vine-frame ${dashed ? 'farm-vine-frame-dashed' : ''} ${className}`}
      {...rest}
    >
      <svg
        className="farm-vine-frame-svg"
        viewBox="0 0 200 200"
        preserveAspectRatio="none"
        aria-hidden
      >
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#fde68a" />
            <stop offset="35%" stopColor="#b8860b" />
            <stop offset="65%" stopColor="#f5d67a" />
            <stop offset="100%" stopColor="#6b4423" />
          </linearGradient>
        </defs>
        <rect
          x="2"
          y="2"
          width="196"
          height="196"
          rx="16"
          ry="16"
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth="2.5"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d="M18 2 Q40 8 60 2 M140 2 Q160 8 182 2 M2 18 Q8 40 2 60 M198 18 Q192 40 198 60"
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth="1.5"
          opacity="0.65"
          vectorEffect="non-scaling-stroke"
        />
      </svg>

      <GoldCorner className="farm-vine-corner farm-vine-corner-tl" rotate={0} />
      <GoldCorner className="farm-vine-corner farm-vine-corner-tr" rotate={90} />
      <GoldCorner className="farm-vine-corner farm-vine-corner-br" rotate={180} />
      <GoldCorner className="farm-vine-corner farm-vine-corner-bl" rotate={270} />

      <span className="farm-vine-leaf farm-vine-leaf-tl" aria-hidden>
        <VineLeaf className="w-7 h-4" />
      </span>
      <span className="farm-vine-leaf farm-vine-leaf-tr" aria-hidden>
        <VineLeaf className="w-7 h-4" flip />
      </span>
      <span className="farm-vine-leaf farm-vine-leaf-bl" aria-hidden>
        <VineLeaf className="w-6 h-3.5" />
      </span>
      <span className="farm-vine-leaf farm-vine-leaf-br" aria-hidden>
        <VineLeaf className="w-6 h-3.5" flip />
      </span>
      <span className="farm-vine-leaf farm-vine-leaf-mid-l" aria-hidden>
        <VineLeaf className="w-5 h-3 opacity-80" />
      </span>
      <span className="farm-vine-leaf farm-vine-leaf-mid-r" aria-hidden>
        <VineLeaf className="w-5 h-3 opacity-80" flip />
      </span>

      <div className="farm-vine-frame-inner">{children}</div>
    </div>
  )
}
