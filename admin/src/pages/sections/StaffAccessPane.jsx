import { useState } from 'react'
import PanelAccessSection from './PanelAccessSection'
import StaffPunishRole from '../../components/StaffPunishRole'

const MODES = [
  { id: 'role', label: 'Должность' },
  { id: 'person', label: 'Один человек' },
  { id: 'steps', label: 'По шагам' },
  { id: 'compare', label: 'Сравнение' },
]

export default function StaffAccessPane({ isProjectCreator = false, onOpenPreview = null }) {
  const [mode, setMode] = useState('role')
  const [role, setRole] = useState('senior_admin')

  return (
    <div className="staff-access">
      <p className="staff-hint">
        Сначала должность: какие страницы панели она видит и какие наказания может ставить.
        Исключение одному человеку перекрывает должность. Сравнение показывает, у кого доступ разошёлся.
      </p>
      <nav className="sec-tabs" aria-label="Как настраивать доступ">
        {MODES.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`sec-tab${mode === item.id ? ' sec-tab-active' : ''}`}
            aria-current={mode === item.id ? 'page' : undefined}
            onClick={() => setMode(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {mode === 'role' && (
        <>
          <PanelAccessSection only="defaults" isProjectCreator={isProjectCreator} onRole={setRole} onOpenPreview={onOpenPreview} />
          {isProjectCreator && <StaffPunishRole role={role} />}
        </>
      )}
      {mode === 'person' && (
        <PanelAccessSection only="members" isProjectCreator={isProjectCreator} />
      )}
      {mode === 'steps' && (
        <PanelAccessSection only="wizard" isProjectCreator={isProjectCreator} />
      )}
      {mode === 'compare' && (
        <PanelAccessSection only="compare" isProjectCreator={isProjectCreator} />
      )}
    </div>
  )
}
