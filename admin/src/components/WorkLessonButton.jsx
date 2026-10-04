export default function WorkLessonButton({ onClick, disabled = false }) {
  return (
    <div className="work-lesson-bar">
      <button type="button" className="work-lesson-btn" onClick={onClick} disabled={disabled}>
        <span className="work-lesson-glyph" aria-hidden="true" />
        <span>Обучение по вкладке «Работа»</span>
      </button>
    </div>
  )
}
