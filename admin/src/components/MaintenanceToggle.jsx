import { useCallback, useState } from 'react'
import { setMaintenanceState } from '../lib/adminClient'
import { notifyAdmin } from '../lib/notify'

export default function MaintenanceToggle({ initialEnabled, onChange }) {
  const [enabled, setEnabled] = useState(Boolean(initialEnabled))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const toggle = useCallback(async () => {
    const next = !enabled
    setError('')
    setLoading(true)

    try {
      const data = await setMaintenanceState(next)
      setEnabled(Boolean(data.maintenance))
      onChange?.(Boolean(data.maintenance))
      notifyAdmin(data.maintenance ? 'Техработы включены' : 'Игра снова доступна')
    } catch (err) {
      const message = err.message || 'Не удалось изменить режим'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setLoading(false)
    }
  }, [enabled, onChange])

  return (
    <div className="panel-maintenance">
      <div className="panel-maintenance-head">
        <p className="panel-shelf-label">Техработы</p>
        <button
          type="button"
          className={`panel-toggle${enabled ? ' panel-toggle-on' : ''}`}
          role="switch"
          aria-checked={enabled}
          disabled={loading}
          onClick={toggle}
        >
          <span className="panel-toggle-thumb" />
        </button>
      </div>

      <p className={`panel-maintenance-status${enabled ? ' panel-maintenance-active' : ''}`}>
        {enabled ? 'Игра закрыта для игроков' : 'Игра доступна'}
      </p>
      <p className="panel-maintenance-note">Флаг хранится в базе данных</p>

      {error && <p className="panel-shelf-error">{error}</p>}
    </div>
  )
}
