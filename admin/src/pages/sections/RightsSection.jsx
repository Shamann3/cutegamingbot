import { useCallback, useEffect, useMemo, useState } from 'react'
import { appointGroupAdmin, createGroupPosition, createStaffPost, deleteGroupPosition, fetchPanelAccess, fetchRightsBoard, purgeStaffMember, saveGroupPosition, setPanelRoleDefault } from '../../lib/adminClient'
import DarkPick from '../../components/DarkPick'
import FocusWindow from '../../components/FocusWindow'
import PositionEditor from '../../components/PositionEditor'
import RightSwitch from '../../components/RightSwitch'
import UserLookupPreview from '../../components/UserLookupPreview'
import { groupPositionPreview } from '../../lib/panelPreview'

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
  const [postTitle, setPostTitle] = useState('')
  const [postBusy, setPostBusy] = useState(false)

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

  const createPost = async (event) => {
    event.preventDefault()
    const title = postTitle.trim()
    if (title.length < 2) return
    setPostBusy(true)
    setError('')
    setNotice('')
    try {
      const created = await createStaffPost(title)
      setPostTitle('')
      setNotice(created.punishNote || `Должность «${created.label || title}» создана. Вкладки и наказания выключены — включите только то, что ей нужно.`)
      await load()
      if (created.id) {
        setRole(created.id)
        setOpen(true)
      }
    } catch (err) {
      setError(err.message || 'Должность не создалась')
    } finally {
      setPostBusy(false)
    }
  }

  return (
    <div>
      <p className="realm-copy">Это страницы панели сотрудника для всей должности сразу. Владелец видит всё, его здесь нет. Новую должность создаёт только создатель проекта: сначала все вкладки закрыты, потом вы включаете нужные. Наказания этой должности — в матрице выше, тоже с нуля.</p>
      <form className="realm-form staff-new-post" onSubmit={createPost}>
        <h2 className="realm-h">Новая должность сотрудника</h2>
        <label>Название
          <input value={postTitle} onChange={(event) => setPostTitle(event.target.value)} placeholder="Например, Ночной модератор" />
        </label>
        <button type="submit" className="realm-back" disabled={postBusy || postTitle.trim().length < 2}>
          {postBusy ? 'Создаём…' : 'Создать должность'}
        </button>
      </form>
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
                    hint="Открывает эту страницу всей должности. Если выключить, человек её не увидит."
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
                          hint="Вкладка внутри страницы. Работает только пока включена сама страница."
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

export default function RightsSection({ embedded = false, office = null, onPreview = null } = {}) {
  const [groups, setGroups] = useState([])
  const [chatId, setChatId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [savingId, setSavingId] = useState(null)
  const [purgeId, setPurgeId] = useState('')
  const [purgeQuery, setPurgeQuery] = useState('')
  const [purging, setPurging] = useState(false)
  const [chapter, setChapter] = useState(office === 'staff' ? 'staff' : 'group')
  const [posQuery, setPosQuery] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newRank, setNewRank] = useState('2')
  const [newKind, setNewKind] = useState('post')

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

  useEffect(() => {
    if (office === 'staff' || office === 'group') setChapter(office)
  }, [office])

  const createPosition = async (event) => {
    event.preventDefault()
    if (!chatId) return
    const title = newTitle.trim()
    if (title.length < 2) {
      setError('Название должности — хотя бы два символа')
      return
    }
    setError('')
    setNotice('')
    try {
      await createGroupPosition({
        chat_id: Number(chatId),
        title,
        rank: newKind === 'post' ? Math.min(4, Math.max(0, Number(newRank) || 0)) : 0,
        kind: newKind,
        rights: newKind === 'spamblock' ? [] : ['view_members'],
      })
      setNewTitle('')
      setNotice(`Должность «${title}» создана. Отметьте, какие наказания и страницы ей открыты, и сохраните.`)
      await load()
    } catch (err) {
      setError(err.message || 'Должность не создалась')
    }
  }

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

  const removePosition = async (row) => {
    const data = await deleteGroupPosition(row.id)
    const tail = data?.telegram ? ` ${data.telegram}` : ' Люди остаются в группе.'
    setNotice(`Должность «${row.title}» удалена.${tail}`)
    try {
      await load()
    } catch {
      /* должность уже снята, список обновится при следующем открытии */
    }
  }

  const appointHere = async (row, fields) => {
    const data = await appointGroupAdmin({
      chat_id: Number(chatId),
      user_id: fields.userId,
      position_id: row.id,
      reason: fields.reason || '',
      prefix: fields.prefix || '',
      term_start: fields.termStart || '',
      term_end: fields.termEnd || '',
    })
    setNotice(data?.telegram || `Должность «${row.title}» назначена`)
    try {
      await load()
    } catch {
      /* назначение уже записано */
    }
    return data
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
      {!office && (
        <>
          <p className={embedded ? 'pa-hint' : 'panel-page-lead'}>
            Сначала выберите, что выдаёте: страницы и наказания должности в группе или вкладки панели сотрудника.
          </p>
          <div className="realm-actions">
            <button type="button" className={chapter === 'group' ? 'is-on' : ''} onClick={() => setChapter('group')}>Должности группы</button>
            <button type="button" className={chapter === 'staff' ? 'is-on' : ''} onClick={() => setChapter('staff')}>Вкладки сотрудника</button>
          </div>
        </>
      )}
      {office === 'staff' && (
        <p className="pa-hint">Старший, младший и модератор уже есть. Новую должность добавляет только создатель проекта: вкладки и наказания у неё сначала выключены.</p>
      )}
      {office === 'group' && (
        <p className="pa-hint">Новую должность создаёт только создатель проекта. Обычная сразу получает «Кто пишет», наказания включаются отдельно. «Обычный пользователь» — ранг 0, только писать. «Спам-блок» — тоже ранг 0, без наказаний; срок задаётся, когда человека назначают.</p>
      )}
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
          <form className="realm-form staff-new-post" onSubmit={createPosition}>
            <h2 className="realm-h">Новая должность</h2>
            <label>Название
              <input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder="Например, Хелпер" />
            </label>
            <DarkPick
              label="Тип"
              value={newKind}
              options={[
                { value: 'post', label: 'Обычная должность', hint: 'права настраиваются отдельно' },
                { value: 'member', label: 'Обычный пользователь', hint: 'ранг 0, только писать' },
                { value: 'spamblock', label: 'Спам-блок', hint: 'ранг 0, без прав, со сроком' },
              ]}
              onChange={setNewKind}
            />
            {newKind === 'post' && (
              <label>Ранг, 0 как участник, 4 старше
                <input value={newRank} onChange={(event) => setNewRank(event.target.value.replace(/[^\d]/g, '').slice(0, 1))} inputMode="numeric" />
              </label>
            )}
            <button type="submit" className="realm-back" disabled={newTitle.trim().length < 2}>Создать должность</button>
          </form>
          <PositionEditor
            positions={(current.positions || []).filter((row) => String(row.title || '').toLowerCase().includes(posQuery.trim().toLowerCase()))}
            creator
            chatId={current.chatId}
            seats={current.seats || []}
            onSave={save}
            onDelete={removePosition}
            onAppoint={appointHere}
            savingId={savingId}
            onPreview={onPreview ? (row) => onPreview(groupPositionPreview(current, row)) : null}
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
