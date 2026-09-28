import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchPanelAccess, fetchRightsBoard, purgeStaffMember, saveGroupPosition, setPanelRoleDefault } from '../../lib/adminClient'
import FocusWindow from '../../components/FocusWindow'
import PositionEditor from '../../components/PositionEditor'
import RightSwitch from '../../components/RightSwitch'
import UserLookupPreview from '../../components/UserLookupPreview'

const STAFF_GROUP_LABELS = {
  overview: 'С чего начать',
  people: 'Люди',
  economy: 'Деньги и группы',
  content: 'Игры и призы',
  team: 'Команда',
  insights: 'Цифры',
  system: 'Настройки',
  official: 'Официальные группы',
}

function StaffTabsEditor() {
  const [pack, setPack] = useState(null)
  const [role, setRole] = useState('')
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busyKey, setBusyKey] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      const data = await fetchPanelAccess()
      setPack(data)
      setRole((current) => current || data.roles?.[0]?.id || '')
    } catch (err) {
      setError(err.message || 'Вкладки панели не открылись')
    }
  }, [])

  useEffect(() => { load() }, [load])

  const groups = useMemo(() => {
    const tree = pack?.tree || []
    const order = Object.keys(STAFF_GROUP_LABELS)
    const known = new Set(order)
    const extra = [...new Set(tree.map((item) => item.group).filter((id) => id && !known.has(id)))]
    return [...order, ...extra]
      .map((id) => ({
        id,
        label: STAFF_GROUP_LABELS[id] || id,
        items: tree.filter((item) => item.group === id),
      }))
      .filter((group) => group.items.length)
  }, [pack])

  const enabled = (key) => Boolean(pack?.roleDefaults?.[role]?.[key])

  const toggle = async (key, next) => {
    if (!role) return
    setBusyKey(key)
    setError('')
    setNotice('')
    setPack((current) => {
      if (!current) return current
      const roleDefaults = {
        ...current.roleDefaults,
        [role]: { ...(current.roleDefaults?.[role] || {}), [key]: next },
      }
      return { ...current, roleDefaults }
    })
    try {
      await setPanelRoleDefault({ role, sectionId: key, enabled: next })
      setNotice('Вкладки этой должности сохранены')
    } catch (err) {
      setError(err.message || 'Вкладка не сохранилась')
      await load()
    } finally {
      setBusyKey('')
    }
  }

  return (
    <div>
      <p className="realm-copy">Это страницы панели сотрудника для всей должности сразу. Владелец видит всё, его здесь нет. Внутренняя вкладка работает только если открыта сама страница. Исключение одному человеку по-прежнему ставится в «Админ панель».</p>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {notice && <p className="realm-note" role="status">{notice}</p>}
      <div className="role-ladder">
        {(pack?.roles || []).map((item) => {
          const packOn = pack?.roleDefaults?.[item.id] || {}
          const count = Object.values(packOn).filter(Boolean).length
          return (
            <button
              key={item.id}
              type="button"
              className="role-card is-staff"
              onClick={() => { setRole(item.id); setOpen(true) }}
            >
              <span className="role-card-rank">Панель сотрудника</span>
              <strong>{item.label}</strong>
              <span>{count} открытых вкладок · нажать, чтобы настроить</span>
            </button>
          )
        })}
      </div>
      {open && role && (
        <FocusWindow
          title={(pack?.roles || []).find((item) => item.id === role)?.label || 'Должность'}
          subtitle="Вкладки этой должности в панели сотрудника. Владелец видит всё."
          onClose={() => setOpen(false)}
        >
          {groups.map((group) => (
            <section key={group.id} className="realm-rights-block">
              <h3>{group.label}</h3>
              {group.items.map((section) => (
                <div key={section.id}>
                  <RightSwitch
                    on={enabled(section.id)}
                    disabled={busyKey === section.id}
                    title={section.label}
                    onChange={(next) => toggle(section.id, next)}
                  />
                  {enabled(section.id) && (section.children || []).length > 0 && (
                    <div className="realm-right-nested">
                      {section.children.map((child) => (
                        <RightSwitch
                          key={child.key}
                          on={enabled(child.key)}
                          disabled={busyKey === child.key}
                          title={child.label}
                          onChange={(next) => toggle(child.key, next)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </section>
          ))}
        </FocusWindow>
      )}
    </div>
  )
}

export default function RightsSection({ embedded = false } = {}) {
  const [groups, setGroups] = useState([])
  const [chatId, setChatId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [savingId, setSavingId] = useState(null)
  const [purgeId, setPurgeId] = useState('')
  const [purgeQuery, setPurgeQuery] = useState('')
  const [purging, setPurging] = useState(false)
  const [chapter, setChapter] = useState('group')
  const [posQuery, setPosQuery] = useState('')

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
      setPurgeQuery('')
    } catch (err) {
      setError(err.message || 'Сбросить допуск не удалось')
    } finally {
      setPurging(false)
    }
  }

  return (
    <section className={embedded ? 'realm-in-panel pa-rights-embed' : 'panel-shelf-page realm-in-panel'}>
      {!embedded && <h1 className="panel-page-title">Права</h1>}
      <p className={embedded ? 'pa-hint' : 'panel-page-lead'}>
        Сначала выберите, что выдаёте: страницы и наказания должности в группе или вкладки панели сотрудника.
      </p>
      <div className="realm-actions">
        <button type="button" className={chapter === 'group' ? 'is-on' : ''} onClick={() => setChapter('group')}>Должности группы</button>
        <button type="button" className={chapter === 'staff' ? 'is-on' : ''} onClick={() => setChapter('staff')}>Вкладки сотрудника</button>
      </div>
      {chapter === 'staff' && <StaffTabsEditor />}
      {chapter === 'group' && (
      <>
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
        <>
          <label className="realm-field">Найти должность в этой группе
            <input value={posQuery} onChange={(event) => setPosQuery(event.target.value)} placeholder="Название" />
          </label>
          <PositionEditor
            positions={(current.positions || []).filter((row) => String(row.title || '').toLowerCase().includes(posQuery.trim().toLowerCase()))}
            creator
            onSave={save}
            savingId={savingId}
          />
        </>
      )}
      {!groups.length && !error && <p className="realm-copy">Официальных групп пока нет. Отметьте группу в панели администраторов.</p>}
      <form className="realm-form" onSubmit={purge}>
        <h2 className="realm-h">Убрать допуск</h2>
        <p className="realm-copy">Кроме создателя проекта. Человек регистрируется заново и получает новый ключ.</p>
        <UserLookupPreview
          value={purgeQuery}
          onChange={(v) => { setPurgeQuery(v); setPurgeId('') }}
          onResolved={(u) => setPurgeId(u ? String(u.userId ?? u.user_id ?? '') : '')}
          placeholder="ID, @username или имя"
          label="Человек"
        />
        <button type="submit" className="realm-back" disabled={purging}>{purging ? 'Снимаем…' : 'Убрать допуск'}</button>
      </form>
      </>
      )}
    </section>
  )
}
