/**
 * Марка Cute Epsilon, разобранная на независимые части SVG:
 *   · eps-crest-eye     — контур глаза + диск + орёл
 *   · eps-crest-wing-l  — 4 пера слева
 *   · eps-crest-wing-r  — 4 пера справа
 *   · eps-crest-crown   — корона
 *   · eps-crest-words   — CUTE / EPSILON
 *
 * Каждая группа анимируется отдельно через CSS.
 */
export default function EpsilonCrestMark({ className = '' }) {
  return (
    <svg
      className={`eps-crest${className ? ` ${className}` : ''}`}
      viewBox="0 0 240 278"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* ═══════════════ ОКО ═══════════════ */}
      <g className="eps-crest-part eps-crest-eye">
        {/* Толстое миндалевидное кольцо */}
        <path
          d="M38 112
             C62 72 92 52 120 52
             C148 52 178 72 202 112
             C178 152 148 172 120 172
             C92 172 62 152 38 112 Z
             M66 112
             C84 86 102 74 120 74
             C138 74 156 86 174 112
             C156 138 138 150 120 150
             C102 150 84 138 66 112 Z"
          fill="#fff"
          fillRule="evenodd"
        />
        {/* Диск зрачка */}
        <circle cx="120" cy="112" r="30" fill="#fff" />
        {/* Силуэт орла / грифона — смотрит вправо */}
        <g className="eps-crest-eagle" fill="#050505">
          {/* Голова + клюв */}
          <path d="
            M104 108
            C104 96 112 88 124 88
            C132 88 138 92 142 98
            L152 104
            L142 106
            C140 112 136 118 128 122
            C118 126 108 122 104 114
            Z
          " />
          {/* Хохолок */}
          <path d="M108 92 C104 84 100 78 98 74 C106 78 112 84 116 90 Z" />
          {/* Шея / плечо */}
          <path d="M108 118 C112 128 120 132 130 130 C122 134 112 132 106 124 Z" />
          {/* Глаз орла — точка */}
          <circle cx="128" cy="100" r="2.2" fill="#fff" />
        </g>
      </g>

      {/* ═══════════════ ЛЕВОЕ КРЫЛО ═══════════════ */}
      <g className="eps-crest-part eps-crest-wing eps-crest-wing-l">
        <path d="M86 68 C64 48 40 36 14 32 C36 50 54 66 70 82 C76 76 82 72 86 68 Z" fill="#fff" />
        <path d="M80 78 C56 62 30 54 6 54 C30 70 48 84 64 96 C70 90 76 84 80 78 Z" fill="#fff" />
        <path d="M76 90 C54 80 30 76 8 80 C30 92 48 100 62 108 C68 102 72 96 76 90 Z" fill="#fff" />
        <path d="M74 102 C56 98 36 100 18 108 C38 112 54 114 66 116 C70 110 72 106 74 102 Z" fill="#fff" />
      </g>

      {/* ═══════════════ ПРАВОЕ КРЫЛО ═══════════════ */}
      <g className="eps-crest-part eps-crest-wing eps-crest-wing-r">
        <path d="M154 68 C176 48 200 36 226 32 C204 50 186 66 170 82 C164 76 158 72 154 68 Z" fill="#fff" />
        <path d="M160 78 C184 62 210 54 234 54 C210 70 192 84 176 96 C170 90 164 84 160 78 Z" fill="#fff" />
        <path d="M164 90 C186 80 210 76 232 80 C210 92 192 100 178 108 C172 102 168 96 164 90 Z" fill="#fff" />
        <path d="M166 102 C184 98 204 100 222 108 C202 112 186 114 174 116 C170 110 168 106 166 102 Z" fill="#fff" />
      </g>

      {/* ═══════════════ КОРОНА ═══════════════ */}
      <g className="eps-crest-part eps-crest-crown">
        {/* Дуга-основание */}
        <path
          d="M86 62
             C98 52 110 48 120 48
             C130 48 142 52 154 62
             L148 68
             C138 60 128 56 120 56
             C112 56 102 60 92 68 Z"
          fill="#fff"
        />
        {/* Боковые зубцы */}
        <path d="M88 64 L78 34 L104 58 Z" fill="#fff" />
        <path d="M152 64 L162 34 L136 58 Z" fill="#fff" />
        {/* Центральный зубец */}
        <path d="M110 56 L120 16 L130 56 Z" fill="#fff" />
        {/* Ромб на острие */}
        <path d="M120 8 L128 18 L120 28 L112 18 Z" fill="#fff" />
      </g>

      {/* ═══════════════ WORDMARK ═══════════════ */}
      <g className="eps-crest-part eps-crest-words">
        <text
          x="120"
          y="204"
          textAnchor="middle"
          fill="#fff"
          fontFamily="Inter, system-ui, sans-serif"
          fontSize="30"
          fontWeight="700"
          letterSpacing="0.2em"
        >
          CUTE
        </text>
        <text
          x="120"
          y="236"
          textAnchor="middle"
          fill="#fff"
          fontFamily="Inter, system-ui, sans-serif"
          fontSize="22"
          fontWeight="700"
          letterSpacing="0.32em"
        >
          EPSILON
        </text>
      </g>
    </svg>
  )
}
