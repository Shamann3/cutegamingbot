/**
 * Реалистичная растительность для печати входа:
 * плющ с прожилками, усики, папоротник у низа, золотая пыльца.
 */
export default function EntranceFlora() {
  return (
    <svg
      className="farm-ent-flora"
      viewBox="0 0 360 640"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
    >
      <defs>
        <linearGradient id="feLeafA" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#7ef0b4" />
          <stop offset="45%" stopColor="#2f9e64" />
          <stop offset="100%" stopColor="#14532d" />
        </linearGradient>
        <linearGradient id="feLeafB" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#9af5c8" />
          <stop offset="50%" stopColor="#3dd68c" />
          <stop offset="100%" stopColor="#1f7a4d" />
        </linearGradient>
        <linearGradient id="feStem" x1="0%" y1="100%" x2="0%" y2="0%">
          <stop offset="0%" stopColor="#0f3d28" />
          <stop offset="55%" stopColor="#2f9e64" />
          <stop offset="100%" stopColor="#6ee7b7" />
        </linearGradient>
        <radialGradient id="feBud" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#f7e7b0" />
          <stop offset="70%" stopColor="#e8c56a" />
          <stop offset="100%" stopColor="#b8892d" />
        </radialGradient>
        <filter id="feSoft" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="0.7" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Левый каскад плюща */}
      <g className="farm-ent-flora-branch farm-ent-flora-branch--l" filter="url(#feSoft)">
        <path
          className="farm-ent-flora-stem farm-ent-flora-stem--main"
          d="M6 560 C18 480, 10 400, 28 330 C46 260, 22 200, 48 140 C72 85, 54 48, 78 12"
          fill="none"
          stroke="url(#feStem)"
          strokeWidth="2.8"
          strokeLinecap="round"
        />
        <path
          className="farm-ent-flora-stem farm-ent-flora-stem--soft"
          d="M20 575 C36 500, 30 420, 52 350 C70 290, 58 230, 82 175 C98 135, 88 95, 108 55"
          fill="none"
          stroke="url(#feStem)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        {/* Усик */}
        <path
          className="farm-ent-flora-tendril"
          d="M48 300 C62 292, 74 305, 68 318 C62 328, 78 334, 86 322"
          fill="none"
        />
        <path
          className="farm-ent-flora-tendril"
          d="M72 160 C88 152, 98 168, 90 178 C84 186, 100 190, 108 176"
          fill="none"
        />

        <IvyLeaf x={36} y={420} rot={-28} scale={1.05} delay={0} />
        <IvyLeaf x={28} y={360} rot={-18} scale={0.95} delay={1} variant="b" />
        <IvyLeaf x={42} y={300} rot={-34} scale={1.1} delay={2} />
        <IvyLeaf x={54} y={245} rot={-12} scale={0.88} delay={3} variant="b" />
        <IvyLeaf x={48} y={190} rot={-40} scale={1} delay={4} />
        <IvyLeaf x={62} y={140} rot={-22} scale={0.82} delay={5} variant="b" />
        <IvyLeaf x={70} y={90} rot={-48} scale={0.92} delay={6} />
        <IvyLeaf x={78} y={48} rot={-16} scale={0.72} delay={7} variant="b" />

        <circle className="farm-ent-flora-bud farm-ent-flora-bud--1" cx="58" cy="268" r="2.4" fill="url(#feBud)" />
        <circle className="farm-ent-flora-bud farm-ent-flora-bud--2" cx="74" cy="118" r="2" fill="url(#feBud)" />
        <circle className="farm-ent-flora-bud farm-ent-flora-bud--3" cx="40" cy="388" r="1.7" fill="url(#feBud)" />
      </g>

      {/* Правый каскад */}
      <g className="farm-ent-flora-branch farm-ent-flora-branch--r" filter="url(#feSoft)">
        <path
          className="farm-ent-flora-stem farm-ent-flora-stem--main"
          d="M354 560 C342 480, 350 400, 332 330 C314 260, 338 200, 312 140 C288 85, 306 48, 282 12"
          fill="none"
          stroke="url(#feStem)"
          strokeWidth="2.8"
          strokeLinecap="round"
        />
        <path
          className="farm-ent-flora-stem farm-ent-flora-stem--soft"
          d="M340 575 C324 500, 330 420, 308 350 C290 290, 302 230, 278 175 C262 135, 272 95, 252 55"
          fill="none"
          stroke="url(#feStem)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <path
          className="farm-ent-flora-tendril"
          d="M312 300 C298 292, 286 305, 292 318 C298 328, 282 334, 274 322"
          fill="none"
        />
        <path
          className="farm-ent-flora-tendril"
          d="M288 160 C272 152, 262 168, 270 178 C276 186, 260 190, 252 176"
          fill="none"
        />

        <IvyLeaf x={324} y={420} rot={28} scale={1.05} delay={0} flip />
        <IvyLeaf x={332} y={360} rot={18} scale={0.95} delay={1} variant="b" flip />
        <IvyLeaf x={318} y={300} rot={34} scale={1.1} delay={2} flip />
        <IvyLeaf x={306} y={245} rot={12} scale={0.88} delay={3} variant="b" flip />
        <IvyLeaf x={312} y={190} rot={40} scale={1} delay={4} flip />
        <IvyLeaf x={298} y={140} rot={22} scale={0.82} delay={5} variant="b" flip />
        <IvyLeaf x={290} y={90} rot={48} scale={0.92} delay={6} flip />
        <IvyLeaf x={282} y={48} rot={16} scale={0.72} delay={7} variant="b" flip />

        <circle className="farm-ent-flora-bud farm-ent-flora-bud--1" cx="302" cy="268" r="2.4" fill="url(#feBud)" />
        <circle className="farm-ent-flora-bud farm-ent-flora-bud--2" cx="286" cy="118" r="2" fill="url(#feBud)" />
        <circle className="farm-ent-flora-bud farm-ent-flora-bud--3" cx="320" cy="388" r="1.7" fill="url(#feBud)" />
      </g>

      {/* Нижний папоротник / луг */}
      <g className="farm-ent-flora-ground">
        <path
          className="farm-ent-flora-stem farm-ent-flora-stem--ground"
          d="M28 618 C90 588, 180 582, 270 590 C300 594, 330 608, 344 622"
          fill="none"
          stroke="url(#feStem)"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <Fern tip={[56, 615]} lean={-1} />
        <Fern tip={[98, 618]} lean={-0.4} />
        <Fern tip={[148, 620]} lean={0.2} />
        <Fern tip={[198, 619]} lean={-0.15} />
        <Fern tip={[248, 617]} lean={0.55} />
        <Fern tip={[298, 616]} lean={1} />

        <IvyLeaf x={72} y={598} rot={-70} scale={0.7} delay={8} />
        <IvyLeaf x={210} y={596} rot={-95} scale={0.65} delay={9} variant="b" />
        <IvyLeaf x={286} y={600} rot={-110} scale={0.68} delay={10} />
      </g>

      {/* Пыльца / споры */}
      <g className="farm-ent-flora-spores">
        <circle className="farm-ent-flora-spore farm-ent-flora-spore--1" cx="96" cy="280" r="2.1" />
        <circle className="farm-ent-flora-spore farm-ent-flora-spore--2" cx="264" cy="240" r="1.7" />
        <circle className="farm-ent-flora-spore farm-ent-flora-spore--3" cx="130" cy="400" r="1.9" />
        <circle className="farm-ent-flora-spore farm-ent-flora-spore--4" cx="230" cy="360" r="1.5" />
        <circle className="farm-ent-flora-spore farm-ent-flora-spore--5" cx="180" cy="200" r="1.4" />
        <circle className="farm-ent-flora-spore farm-ent-flora-spore--6" cx="110" cy="150" r="1.6" />
      </g>
    </svg>
  )
}

function IvyLeaf({ x, y, rot = 0, scale = 1, delay = 0, variant = 'a', flip = false }) {
  const fill = variant === 'b' ? 'url(#feLeafB)' : 'url(#feLeafA)'
  const sx = flip ? -scale : scale
  return (
    <g
      className={`farm-ent-flora-leaf farm-ent-flora-leaf--d${delay}`}
      transform={`translate(${x} ${y}) rotate(${rot}) scale(${sx} ${scale})`}
    >
      {/* силуэт листа плюща */}
      <path
        d="M0 0
           C6 -4, 12 -2, 14 4
           C18 0, 22 -6, 20 -12
           C26 -10, 30 -4, 28 2
           C34 2, 36 8, 32 12
           C36 16, 34 22, 28 22
           C30 28, 24 32, 18 28
           C14 34, 6 32, 4 24
           C-2 28, -6 22, -2 16
           C-8 14, -8 6, -2 4
           C-4 -2, -2 -4, 0 0 Z"
        fill={fill}
        opacity="0.92"
      />
      {/* блик */}
      <path
        d="M6 2 C10 0, 14 2, 15 6 C12 5, 9 4, 6 2 Z"
        fill="rgba(244,239,226,0.22)"
      />
      {/* центральная прожилка */}
      <path
        d="M4 4 C10 8, 16 14, 20 22"
        fill="none"
        stroke="rgba(4,20,12,0.45)"
        strokeWidth="0.7"
        strokeLinecap="round"
      />
      {/* боковые прожилки */}
      <path
        d="M8 8 C12 7, 16 6, 18 4 M10 14 C14 12, 18 12, 22 10 M12 20 C16 18, 20 18, 24 16"
        fill="none"
        stroke="rgba(4,20,12,0.28)"
        strokeWidth="0.45"
        strokeLinecap="round"
      />
    </g>
  )
}

function Fern({ tip, lean = 0 }) {
  const [x, y] = tip
  const blades = [-18, -10, -4, 4, 10, 18]
  return (
    <g className="farm-ent-flora-fern" transform={`translate(${x} ${y})`}>
      <path
        className="farm-ent-flora-blade"
        d={`M0 0 C${lean * 4} -28, ${lean * 6} -48, ${lean * 8} -72`}
        fill="none"
      />
      {blades.map((dx, i) => (
        <ellipse
          key={i}
          className="farm-ent-flora-fern-lobe"
          cx={dx * 0.55 + lean * (i + 1)}
          cy={-12 - i * 9}
          rx={5.5 - i * 0.35}
          ry={2.4}
          transform={`rotate(${dx * 1.8 + lean * 8} ${dx * 0.55} ${-12 - i * 9})`}
        />
      ))}
    </g>
  )
}
