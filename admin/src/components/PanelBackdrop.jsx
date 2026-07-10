export default function PanelBackdrop({ active = true }) {
  return (
    <>
      <div
        className={`splash-ambient ${active ? 'splash-ambient-active' : ''}`}
        aria-hidden="true"
      />
      <div
        className={`splash-glow ${active ? 'splash-glow-active' : ''}`}
        aria-hidden="true"
      />
    </>
  )
}
