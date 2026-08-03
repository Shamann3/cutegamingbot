/**
 * Чистое поле грядки без нарисованных веточек.
 * Только почва / влажность / сухость / готовность — фото-фон фермы делает атмосферу.
 */
export default function SoilField({
  status = 'growing',
  moist = false,
  dry = false,
  ready = false,
  className = '',
}) {
  return (
    <div
      className={[
        'soil-field',
        moist ? 'soil-field--moist' : '',
        dry ? 'soil-field--dry' : '',
        ready ? 'soil-field--ready' : '',
        status === 'empty' ? 'soil-field--empty' : '',
        className,
      ].filter(Boolean).join(' ')}
      aria-hidden
    >
      <div className="soil-field-earth" />
      <div className="soil-field-furrows" />
      <div className="soil-field-depth" />
      <div className="soil-field-rim" />
      {ready && <div className="soil-field-ready-glow" />}
      {moist && !dry && <div className="soil-field-dew" />}
    </div>
  )
}
