import { useCallback, useEffect, useState } from 'react'
import { fetchRightsBoard, purgeStaffMember, saveGroupPosition } from '../../lib/adminClient'
import PositionEditor from '../../components/PositionEditor'

export default function RightsSection() {
  const [groups, setGroups] = useState([])
  const [chatId, setChatId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [savingId, setSavingId] = useState(null)
  const [purgeId, setPurgeId] = useState('')
  const [purging, setPurging] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const data = await fetchRightsBoard()
      const items = data.groups || []
      setGroups(items)
      setChatId((current) => current ?? items[0]?.chatId ?? null)
    } catch (err) {
      setError(err.message || 'Права не открылись')
    }
  }, [])

  useEffect(() => { load() }, [load])

  const current = groups.find((group) => group.chatId === chatId) || null

  const save = async (row) => {
    setSavingId(row.id)
    setError('')
    setNotice('')
    try {
      await saveGroupPosition(row.id, { title: row.title.trim(), rights: row.rights || [] })
      setNotice(`Должность «${row.title.trim()}» сохранена`)
      await load()
    } catch (err) {
      setError(err.message || 'Должность не сохранилась')
    } finally {
      setSavingId(null)
    }
  }

  const purge = async (event) => {
    event.preventDefault()
    const id = Number(purgeId)
    if (!id) {
      setError('Введите id человека')
      return
    }
    if (!window.confirm('Убрать допуск? Человек выйдет из панели сотрудника и из групп. Снова войти можно только новой заявкой и новым ключом.')) return
    setPurging(true)
    setError('')
    setNotice('')
    try {
      await purgeStaffMember(id)
      setNotice('Допуск снят. Для входа нужна новая заявка и новый ключ.')
      setPurgeId('')
    } catch (err) {
      setError(err.message || 'Сбросить допуск не удалось')
    } finally {
      setPurging(false)
    }
  }

  return (
    <section className="panel-shelf-page realm-in-panel">
      <h1 className="panel-page-title">Права</h1>
      <p className="panel-page-lead">Должности групп и полный сброс допуска. Вкладки панели сотрудника задаются в разделе «Админ панель».</p>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {notice && <p className="realm-note" role="status">{notice}</p>}
      {groups.length > 0 && (
        <ul className="realm-list">
          {groups.map((group) => (
            <li key={group.chatId}>
              <button type="button" className={group.chatId === chatId ? 'is-on' : ''} onClick={() => setChatId(group.chatId)}>
                <strong>{group.title}</strong>
                <span>{group.positions?.length || 0} должностей</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {current && (
        <PositionEditor positions={current.positions || []} creator onSave={save} savingId={savingId} />
      )}
      {!groups.length && !error && <p className="realm-copy">Официальных групп пока нет. Отметьте группу в панели администраторов.</p>}
      <form className="realm-form" onSubmit={purge}>
        <h2 className="realm-h">Убрать допуск</h2>
        <p className="realm-copy">Кроме создателя проекта. Человек регистрируется заново и получает новый ключ.</p>
        <label>
          Id человека
          <input inputMode="numeric" value={purgeId} onChange={(event) => setPurgeId(event.target.value)} />
        </label>
        <button type="submit" className="realm-back" disabled={purging}>{purging ? 'Снимаем…' : 'Убрать допуск'}</button>
      </form>
    </section>
  )
}
