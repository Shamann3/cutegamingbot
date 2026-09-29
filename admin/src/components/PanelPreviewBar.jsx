export default function PanelPreviewBar({ title, detail, onExit }) {
  return (
    <div className="preview-bar" role="status">
      <p>
        <strong>{title}</strong>
        <span>{detail}</span>
      </p>
      <button type="button" className="preview-bar-exit" onClick={onExit}>
        Выйти из копии
      </button>
    </div>
  )
}
