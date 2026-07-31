import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  approveStaffApplication,
  changeMemberRole,
  createStaffComplaint,
  addMemberNote,
  addMemberStrike,
  removeStaffStrike,
  addStaffShift,
  cancelPendingPayout,
  confirmPendingPayout,
  createInviteToken,
  deleteInviteToken,
  deleteStaffMember,
  deleteMemberNote,
  deleteStaffShift,
  deleteApplicationQuestion,
  fetchApplicationQuestionsAdmin,
  fetchInviteTokens,
  fetchMemberActions,
  fetchMemberAudit,
  fetchMemberCard,
  fetchMemberRoleHistory,
  fetchMyComplaints,
  fetchPendingPayouts,
  fetchStaffShifts,
  revokeInviteToken,
  setMemberAvailability,
  upsertApplicationQuestion,
  fetchStaffApplications,
  fetchStaffComplaints,
  fetchStaffLeaderboard,
  fetchStaffMembers,
  rejectStaffApplication,
  resolveStaffComplaint,
  setMemberCurator,
  submitComplaintEvidence,
  suspendStaffMember,
  takeStaffComplaint,
  unsuspendStaffMember,
} from '../../lib/adminClient'
import AdminSelect from '../../components/AdminSelect'
import CountUp from '../../components/CountUp'
import { showToast } from '../../components/ToastHost'
import { APPLICATION_QUESTIONS, PAYOUT_OPTIONS } from '../../config/applicationQuestions'
import PayrollSalariesTab from './payroll/SalariesTab'
import PayrollBonusesTab from './payroll/BonusesTab'
import PayrollSettingsTab from './payroll/SettingsTab'
import PayrollMySalaryTab from './payroll/MySalaryTab'
import { filterSectionTabs } from '../../constants/panelAccessTree'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}

function timeSince(iso) {
  if (!iso) return 'никогда'
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return 'только что'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} мин назад`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} ч назад`
  return `${Math.floor(diff / 86_400_000)} дн назад`
}

const QUESTION_LABELS = Object.fromEntries(
  APPLICATION_QUESTIONS.map((q) => [q.id, q.label]),
)
const PAYOUT_LABELS = Object.fromEntries(
  PAYOUT_OPTIONS.map((o) => [o.value, o.label]),
)

const ASSIGN_ROLE_OPTIONS = [
  { value: 'moderator', label: 'Модератор' },
  { value: 'junior_admin', label: 'Младший администратор' },
  { value: 'senior_admin', label: 'Старший администратор' },
]

const ROLE_BADGE_COLOR = {
  owner: '#f59e0b',
  senior_admin: '#a78bfa',
  junior_admin: '#60a5fa',
  moderator: '#34d399',
  suspended: '#f87171',
}

const ROLE_LABELS = {
  owner: 'Владелец',
  senior_admin: 'Старший',
  junior_admin: 'Младший',
  moderator: 'Модератор',
  suspended: 'Отстранён',
  applicant: 'Кандидат',
}

function roleLabel(role) {
  return ROLE_LABELS[role] || role || '-'
}

function nameOf(item) {
  return item.firstName || (item.username ? `@${item.username}` : null) || `ID ${item.userId}`
}

// ---------------------------------------------------------------------------
// Review modal
// ---------------------------------------------------------------------------

function ReviewModal({ application, onClose, onApproved, onRejected }) {
  const [role, setRole] = useState('moderator')
  const [reason, setReason] = useState('')
  const [showReject, setShowReject] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (!application) return null

  const handleApprove = async () => {
    setError('')
    setLoading(true)
    try {
      await approveStaffApplication(application.id, role)
      onApproved()
    } catch (err) {
      setError(err?.message || 'Не удалось принять заявку')
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async () => {
    setError('')
    setLoading(true)
    try {
      await rejectStaffApplication(application.id, reason.trim())
      onRejected()
    } catch (err) {
      setError(err?.message || 'Не удалось отклонить заявку')
    } finally {
      setLoading(false)
    }
  }

  const answers = application.answers || {}
  const answerKeys = [
    ...APPLICATION_QUESTIONS.map((q) => q.id).filter((id) => answers[id]),
    ...Object.keys(answers).filter((k) => !QUESTION_LABELS[k]),
  ]

  return (
    <div className="admin-modal-backdrop" role="presentation" onClick={() => !loading && onClose()}>
      <div
        className="admin-modal staff-review-modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="admin-modal-title">{nameOf(application)}</h3>
        <p className="admin-modal-desc">
          Подана {fmtDate(application.createdAt)} · ID {application.userId}
        </p>

        <div className="staff-answers">
          {answerKeys.map((key) => (
            <div className="staff-answer" key={key}>
              <span className="staff-answer-q">{QUESTION_LABELS[key] || key}</span>
              <span className="staff-answer-a">{answers[key]}</span>
            </div>
          ))}
          <div className="staff-answer">
            <span className="staff-answer-a">
              {PAYOUT_LABELS[application.payoutType] || application.payoutType || '-'}
              {application.payoutDetails ? ` · ${application.payoutDetails}` : ''}
            </span>
          </div>
        </div>

        {error && <p className="sec-error">{error}</p>}

        {!showReject ? (
          <>
            <label className="admin-modal-field">
              <span>Назначить роль</span>
              <AdminSelect value={role} onChange={setRole} options={ASSIGN_ROLE_OPTIONS} />
            </label>
            <div className="admin-modal-actions">
              <button type="button" className="panel-users-btn" data-modal-cancel disabled={loading} onClick={onClose}>
                Закрыть
              </button>
              <button type="button" className="panel-users-btn panel-users-btn-danger" disabled={loading} onClick={() => setShowReject(true)}>
                Отклонить
              </button>
              <button type="button" className="panel-users-btn panel-users-btn-primary" data-modal-confirm disabled={loading} onClick={handleApprove}>
                {loading ? '…' : 'Принять'}
              </button>
            </div>
          </>
        ) : (
          <>
            <label className="admin-modal-field">
              <span>Причина отклонения</span>
              <textarea
                className="admin-modal-textarea"
                rows={3}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Необязательно"
                disabled={loading}
              />
            </label>
            <div className="admin-modal-actions">
              <button type="button" className="panel-users-btn" data-modal-cancel disabled={loading} onClick={() => setShowReject(false)}>
                Назад
              </button>
              <button type="button" className="panel-users-btn panel-users-btn-danger" data-modal-confirm disabled={loading} onClick={handleReject}>
                {loading ? '…' : 'Подтвердить отклонение'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Applications
// ---------------------------------------------------------------------------

function ApplicationsTab() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchStaffApplications('pending')
      setItems(data.items || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="sec-tab-body">
      <div className="sec-audit-filters">
        <button className="sec-btn sec-btn-ghost" onClick={load}>Обновить</button>
        <span className="sec-audit-count">{items.length} заявок</span>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-cards">
        {items.map((app) => (
          <button key={app.id} className="staff-card" onClick={() => setActive(app)}>
            <div className="staff-card-main">
              <span className="staff-card-name">{nameOf(app)}</span>
              <span className="staff-card-date">{fmtDate(app.createdAt)}</span>
            </div>
            <span className="staff-badge staff-badge-pulse" style={{ '--badge-color': '#fbbf24' }}>
              ожидает
            </span>
          </button>
        ))}
        {!loading && items.length === 0 && (
          <p className="sec-empty">Новых заявок нет</p>
        )}
      </div>

      {active && (
        <ReviewModal
          application={active}
          onClose={() => setActive(null)}
          onApproved={() => { setActive(null); load() }}
          onRejected={() => { setActive(null); load() }}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Member actions feed modal
// ---------------------------------------------------------------------------

const ACTION_LABELS = {
  ban: '🔴 Бан',
  unban: '🟢 Разбан',
  mute: '🔇 Мут',
  unmute: '🔊 Размут',
  kick: '👢 Кик',
  warn: '⚠️ Варн',
  unwarn: '🧹 Разварн',
}

function MemberActionsModal({ member, onClose, onSaved, canManageStaff = false }) {
  const [items, setItems] = useState(null)
  const [history, setHistory] = useState(null)
  const [card, setCard] = useState(null)
  const [busy, setBusy] = useState(false)
  // Локальное состояние доступности — обновляется сразу после API без ожидания перезагрузки
  const [availability, setAvailabilityLocal] = useState(member.availability || 'active')

  const loadCard = useCallback(async () => {
    try {
      const data = await fetchMemberCard(member.userId, 'week')
      setCard(data)
    } catch {
      setCard(null)
    }
  }, [member.userId])

  useEffect(() => {
    let cancelled = false
    fetchMemberActions(member.userId)
      .then((d) => { if (!cancelled) setItems(d.items || []) })
      .catch(() => { if (!cancelled) setItems([]) })
    fetchMemberRoleHistory(member.userId)
      .then((d) => { if (!cancelled) setHistory(d.items || []) })
      .catch(() => { if (!cancelled) setHistory([]) })
    loadCard()
    return () => { cancelled = true }
  }, [member.userId, loadCard])

  const stats = card?.stats
  const fmtResp = (sec) => {
    if (sec == null) return '-'
    if (sec < 60) return `${sec} сек`
    if (sec < 3600) return `${Math.round(sec / 60)} мин`
    return `${(sec / 3600).toFixed(1)} ч`
  }

  const addNote = async () => {
    const text = prompt('Заметка о сотруднике:')
    if (!text || !text.trim()) return
    setBusy(true)
    try {
      await addMemberNote(member.userId, text.trim())
      await loadCard()
      onSaved?.()
    }
    catch (e) { alert(e?.message || 'Ошибка') } finally { setBusy(false) }
  }
  const delNote = async (noteId) => {
    if (!confirm('Удалить заметку?')) return
    setBusy(true)
    try {
      await deleteMemberNote(member.userId, noteId)
      await loadCard()
      onSaved?.()
    }
    catch (e) { alert(e?.message || 'Ошибка') } finally { setBusy(false) }
  }
  const giveStrike = async () => {
    const reason = prompt('Причина страйка:')
    if (!reason || !reason.trim()) return
    setBusy(true)
    try {
      await addMemberStrike(member.userId, reason.trim())
      await loadCard()
      onSaved?.()
    }
    catch (e) { alert(e?.message || 'Ошибка') } finally { setBusy(false) }
  }

  const dropStrike = async (strikeId) => {
    if (!confirm('Снять страйк досрочно?')) return
    setBusy(true)
    try {
      await removeStaffStrike(member.userId, strikeId)
      await loadCard()
      onSaved?.()
    }
    catch (e) { alert(e?.message || 'Ошибка') } finally { setBusy(false) }
  }
  const setAvail = async (avail) => {
    setBusy(true)
    try {
      await setMemberAvailability(member.userId, avail)
      setAvailabilityLocal(avail)
      await loadCard()
      onSaved?.()  // перезагружает список в MembersTab
    }
    catch (e) { alert(e?.message || 'Ошибка') } finally { setBusy(false) }
  }

  return (
    <div className="admin-modal-backdrop" role="presentation" onClick={onClose}>
      <div className="admin-modal staff-review-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h3 className="admin-modal-title">{nameOf(member)} - дашборд</h3>
        <p className="admin-modal-desc">
          {roleLabel(member.role)} · статистика за неделю
          {card?.currentSalary ? ` · зарплата: ${card.currentSalary.amount} (${card.currentSalary.status})` : ' · зарплата не назначена'}
          {` · жалоб: ${card?.complaintsTotal ?? 0} (открыто ${card?.complaintsOpen ?? 0})`}
        </p>

        {stats && (
          <div className="staff-stats-grid">
            <div><span>Действий</span><b><CountUp value={stats.actionsTotal} /></b></div>
            <div><span>Баны</span><b><CountUp value={stats.bans} /></b></div>
            <div><span>Разбаны</span><b><CountUp value={stats.unbans} /></b></div>
            <div><span>Муты</span><b><CountUp value={stats.mutes} /></b></div>
            <div><span>Жалоб взял</span><b><CountUp value={stats.complaintsTaken} /></b></div>
            <div><span>Жалоб закрыл</span><b><CountUp value={stats.complaintsResolved} /></b></div>
            <div><span>Реакция</span><b>{fmtResp(stats.avgResponseSeconds)}</b></div>
            <div><span>Часов онлайн</span><b>{(stats.onlineMinutes / 60).toFixed(1)}</b></div>
          </div>
        )}

        <div className="staff-manage-block">
          <span className="auth-label">Доступность: {availability === 'vacation' ? 'в отпуске' : availability === 'afk' ? 'афк' : 'активен'}</span>
          <div className="staff-member-buttons">
            <button className="sec-btn sec-btn-sm" disabled={busy} onClick={() => setAvail('active')}>Активен</button>
            <button className="sec-btn sec-btn-sm" disabled={busy} onClick={() => setAvail('vacation')}>Отпуск</button>
            <button className="sec-btn sec-btn-sm" disabled={busy} onClick={() => setAvail('afk')}>АФК</button>
          </div>
        </div>

        <div className="staff-answers">
          <div className="staff-action-head" style={{ justifyContent: 'space-between' }}>
            <h4 className="sec-ipban-section-title">Страйки {card?.activeStrikes ? `(активных ${card.activeStrikes})` : ''}</h4>
            {canManageStaff && (
              <button className="sec-btn sec-btn-sm" disabled={busy} onClick={giveStrike}>+ страйк</button>
            )}
          </div>
          {card?.strikes?.length === 0 && <p className="sec-empty">Страйков нет</p>}
          {card?.strikes?.map((s) => (
            <div className="staff-action" key={s.id}>
              <div className="staff-action-head">
                <span className="staff-badge" style={{ '--badge-color': s.active ? '#f87171' : '#94a3b8' }}>
                  {s.active ? 'активен' : 'сгорел'}
                </span>
                <span className="staff-card-date">{fmtDate(s.createdAt)} → {fmtDate(s.expiresAt)}</span>
                {s.active && canManageStaff && (
                  <button
                    className="sec-btn sec-btn-ghost sec-btn-sm"
                    disabled={busy}
                    onClick={() => dropStrike(s.id)}
                    style={{ marginLeft: 'auto' }}
                  >
                    Снять
                  </button>
                )}
              </div>
              {s.reason && <p className="staff-answer-a">{s.reason}</p>}
            </div>
          ))}

          <div className="staff-action-head" style={{ justifyContent: 'space-between', marginTop: '1rem' }}>
            <h4 className="sec-ipban-section-title">Заметки</h4>
            <button className="sec-btn sec-btn-sm" disabled={busy} onClick={addNote}>+ заметка</button>
          </div>
          {card?.notes?.length === 0 && <p className="sec-empty">Заметок нет</p>}
          {card?.notes?.map((n) => (
            <div className="staff-action" key={n.id}>
              <div className="staff-action-head">
                <span className="staff-card-date">{fmtDate(n.createdAt)} · admin {n.authorId}</span>
                <button className="sec-btn sec-btn-ghost sec-btn-sm" disabled={busy} onClick={() => delNote(n.id)}>✕</button>
              </div>
              <p className="staff-answer-a">{n.text}</p>
            </div>
          ))}

          <h4 className="sec-ipban-section-title" style={{ marginTop: '1rem' }}>История должностей</h4>
          {history === null && <p className="sec-loading">Загрузка…</p>}
          {history && history.length === 0 && <p className="sec-empty">Изменений роли не было</p>}
          {history && history.map((h) => (
            <div className="staff-action" key={h.id}>
              <div className="staff-action-head">
                <span className="staff-badge" style={{ '--badge-color': '#a78bfa' }}>
                  {roleLabel(h.oldRole)} → {roleLabel(h.newRole)}
                </span>
                <span className="staff-card-date">{fmtDate(h.createdAt)}</span>
              </div>
              {h.reason && <p className="staff-answer-a"><b>Причина:</b> {h.reason}</p>}
            </div>
          ))}

          <h4 className="sec-ipban-section-title" style={{ marginTop: '1rem' }}>Действия (наказания)</h4>
          {items === null && <p className="sec-loading">Загрузка…</p>}
          {items && items.length === 0 && <p className="sec-empty">Действий пока нет</p>}
          {items && items.map((a) => (
            <div className="staff-action" key={a.id}>
              <div className="staff-action-head">
                <span className="staff-badge" style={{ '--badge-color': '#f87171' }}>
                  {ACTION_LABELS[a.actionType] || a.actionType}
                </span>
                {a.targetPlayerId && <span className="staff-card-date">игрок {a.targetPlayerId}</span>}
                <span className="staff-card-date">{fmtDate(a.createdAt)}</span>
              </div>
              {a.reason && <p className="staff-answer-a"><b>Причина:</b> {a.reason}</p>}
              {a.evidence && <p className="staff-answer-a"><b>Доказательства:</b> {a.evidence}</p>}
            </div>
          ))}
        </div>

        <div className="admin-modal-actions">
          <button type="button" className="panel-users-btn" data-modal-cancel data-modal-confirm onClick={onClose}>Закрыть</button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Member manage modal (роль + куратор)
// ---------------------------------------------------------------------------

function MemberManageModal({ member, members, canAssignRoles, onClose, onSaved }) {
  const [role, setRole] = useState(member.role)
  const [roleReason, setRoleReason] = useState('')
  const [curatorId, setCuratorId] = useState(member.curatorId ? String(member.curatorId) : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const curatorOptions = [
    { value: '', label: '— без куратора —' },
    ...members
      .filter((m) => m.userId !== member.userId && (m.role === 'senior_admin' || m.role === 'owner'))
      .map((m) => ({ value: String(m.userId), label: `${nameOf(m)} (${roleLabel(m.role)})` })),
  ]

  const saveRole = async () => {
    if (role === member.role) { setError('Роль не изменилась'); return }
    setError(''); setBusy(true)
    try {
      await changeMemberRole(member.userId, role, roleReason.trim())
      onSaved()
    } catch (err) {
      setError(err?.message || 'Ошибка смены роли')
    } finally { setBusy(false) }
  }

  const saveCurator = async () => {
    setError(''); setBusy(true)
    try {
      await setMemberCurator(member.userId, curatorId ? Number(curatorId) : null)
      onSaved()
    } catch (err) {
      setError(err?.message || 'Ошибка назначения куратора')
    } finally { setBusy(false) }
  }

  return (
    <div className="admin-modal-backdrop" role="presentation" onClick={() => !busy && onClose()}>
      <div className="admin-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h3 className="admin-modal-title">{nameOf(member)} — управление</h3>
        <p className="admin-modal-desc">Текущая роль: {roleLabel(member.role)}</p>

        {error && <p className="sec-error">{error}</p>}

        {canAssignRoles && member.role !== 'owner' && (
          <div className="staff-manage-block">
            <span className="auth-label">Сменить должность</span>
            <AdminSelect value={role} onChange={setRole} options={ASSIGN_ROLE_OPTIONS} />
            <input
              className="sec-input"
              placeholder="Причина (необязательно)"
              value={roleReason}
              onChange={(e) => setRoleReason(e.target.value)}
            />
            <button className="sec-btn sec-btn-sm" disabled={busy} onClick={saveRole}>
              Применить роль
            </button>
          </div>
        )}

        {member.role !== 'owner' && (
          <div className="staff-manage-block">
            <span className="auth-label">Куратор (старший)</span>
            <AdminSelect value={curatorId} onChange={setCuratorId} options={curatorOptions} />
            <button className="sec-btn sec-btn-sm" disabled={busy} onClick={saveCurator}>
              Сохранить куратора
            </button>
          </div>
        )}

        <div className="admin-modal-actions">
          <button type="button" className="panel-users-btn" data-modal-cancel data-modal-confirm disabled={busy} onClick={onClose}>Закрыть</button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Members
// ---------------------------------------------------------------------------

function MembersTab({ canAssignRoles, isOwner, myUserId, canManageStaff }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [acting, setActing] = useState(null)
  const [manageMember, setManageMember] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchStaffMembers()
      setItems(data.items || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  const [feedMember, setFeedMember] = useState(null)

  useEffect(() => { load() }, [load])

  const handleSuspend = async (member) => {
    if (!confirm(`Отстранить ${nameOf(member)}?`)) return
    setActing(member.userId)
    try {
      await suspendStaffMember(member.userId)
      await load()
    } catch (err) {
      alert(err?.message || 'Не удалось отстранить')
    } finally {
      setActing(null)
    }
  }

  const handleUnsuspend = async (member) => {
    if (!confirm(`Вернуть ${nameOf(member)} к работе?`)) return
    setActing(member.userId)
    try {
      await unsuspendStaffMember(member.userId)
      await load()
    } catch (err) {
      alert(err?.message || 'Не удалось вернуть')
    } finally {
      setActing(null)
    }
  }

  const handleDelete = async (member) => {
    if (!confirm(`Удалить аккаунт ${nameOf(member)} полностью? Это действие необратимо.`)) return
    setActing(member.userId)
    try {
      await deleteStaffMember(member.userId)
      await load()
    } catch (err) {
      alert(err?.message || 'Не удалось удалить')
    } finally {
      setActing(null)
    }
  }

  return (
    <div className="sec-tab-body">
      <div className="sec-audit-filters">
        <button className="sec-btn sec-btn-ghost" onClick={load}>Обновить</button>
        <span className="sec-audit-count">{items.length} сотрудников</span>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-members">
        {items.map((m) => (
          <div key={m.userId} className="staff-member-row">
            <div className="staff-member-info">
              <span className="staff-card-name">{nameOf(m)}</span>
              <span className="staff-badge" style={{ '--badge-color': ROLE_BADGE_COLOR[m.role] || '#94a3b8' }}>
                {m.roleLabel}
              </span>
              {m.status === 'suspended' && (
                <span className="staff-badge" style={{ '--badge-color': '#f87171' }}>отстранён</span>
              )}
              {m.availability === 'vacation' && (
                <span className="staff-badge" style={{ '--badge-color': '#fbbf24' }}>отпуск</span>
              )}
              {m.availability === 'afk' && (
                <span className="staff-badge" style={{ '--badge-color': '#94a3b8' }}>афк</span>
              )}
              {m.activeStrikes > 0 && (
                <span className="staff-badge" style={{ '--badge-color': '#f87171' }}>страйки: {m.activeStrikes}</span>
              )}
            </div>
            <div className="staff-member-meta">
              <span>Нанят: {fmtDate(m.hiredAt)}</span>
              <span>Активность: {timeSince(m.lastSeenAt)}</span>
              {m.curatorName && <span>Куратор: {m.curatorName}</span>}
            </div>
            <div className="staff-member-buttons">
              {(() => {
                const isSelf = myUserId != null && m.userId === myUserId
                return (
                  <>
                    {!isSelf && (
                      <button
                        className="sec-btn sec-btn-ghost sec-btn-sm"
                        onClick={() => setFeedMember(m)}
                      >
                        История
                      </button>
                    )}
                    {m.role !== 'owner' && !isSelf && (
                      <button
                        className="sec-btn sec-btn-ghost sec-btn-sm"
                        onClick={() => setManageMember(m)}
                      >
                        Управление
                      </button>
                    )}
                    {m.role !== 'owner' && m.status !== 'suspended' && !isSelf && (
                      <button
                        className="sec-btn sec-btn-ghost sec-btn-sm"
                        disabled={acting === m.userId}
                        onClick={() => handleSuspend(m)}
                      >
                        {acting === m.userId ? '…' : 'Отстранить'}
                      </button>
                    )}
                    {m.role !== 'owner' && m.status === 'suspended' && !isSelf && (
                      <>
                        <button
                          className="sec-btn sec-btn-sm sec-btn-success"
                          disabled={acting === m.userId}
                          onClick={() => handleUnsuspend(m)}
                        >
                          {acting === m.userId ? '…' : 'Вернуть'}
                        </button>
                        {isOwner && (
                          <button
                            className="sec-btn sec-btn-sm sec-btn-danger"
                            disabled={acting === m.userId}
                            onClick={() => handleDelete(m)}
                          >
                            Удалить
                          </button>
                        )}
                      </>
                    )}
                    {isSelf && (
                      <span className="sec-empty" style={{ fontSize: '0.75rem', opacity: 0.5 }}>это вы</span>
                    )}
                  </>
                )
              })()}
            </div>
          </div>
        ))}
        {!loading && items.length === 0 && (
          <p className="sec-empty">Сотрудников пока нет</p>
        )}
      </div>

      {feedMember && (
        <MemberActionsModal member={feedMember} onClose={() => setFeedMember(null)} onSaved={load} canManageStaff={canManageStaff} />
      )}

      {manageMember && (
        <MemberManageModal
          member={manageMember}
          members={items}
          canAssignRoles={canAssignRoles}
          onClose={() => setManageMember(null)}
          onSaved={() => { setManageMember(null); load() }}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Complaints (management — owner/senior)
// ---------------------------------------------------------------------------

const COMPLAINT_STATUS = {
  open: { label: 'открыта', color: '#fbbf24' },
  in_progress: { label: 'в работе', color: '#fb923c' },
  resolved: { label: 'закрыта', color: '#34d399' },
}

function ComplaintsTab() {
  const [items, setItems] = useState([])
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(null)
  const [target, setTarget] = useState('')
  const [reason, setReason] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchStaffComplaints()
      setItems(data.items || [])
      const mem = await fetchStaffMembers()
      setMembers((mem.items || []).filter((m) => m.role !== 'owner'))
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const memberOptions = members.map((m) => ({ value: String(m.userId), label: `${nameOf(m)} (${m.roleLabel})` }))

  const handleCreate = async () => {
    if (!target || !reason.trim()) { alert('Выберите сотрудника и укажите причину'); return }
    setBusy('create')
    try {
      await createStaffComplaint({ targetAdminId: Number(target), reason: reason.trim() })
      setTarget('')
      setReason('')
      await load()
    } catch (err) {
      alert(err?.message || 'Ошибка')
    } finally {
      setBusy(null)
    }
  }

  const handleTake = async (id) => {
    setBusy(`take-${id}`)
    try { await takeStaffComplaint(id); await load() }
    catch (err) { alert(err?.message || 'Ошибка') }
    finally { setBusy(null) }
  }

  const handleResolve = async (id) => {
    const resolution = prompt('Решение по жалобе:') ?? ''
    const penaltyRaw = prompt('Авто-штраф к зарплате (0 = без штрафа):', '0') ?? '0'
    const penalty = Math.max(0, Number.parseInt(penaltyRaw, 10) || 0)
    const strike = confirm('Выдать сотруднику страйк? (OK — да)')
    setBusy(`res-${id}`)
    try { await resolveStaffComplaint(id, { resolution, penalty, strike }); await load() }
    catch (err) { alert(err?.message || 'Ошибка') }
    finally { setBusy(null) }
  }

  return (
    <div className="sec-tab-body">
      <div className="sec-ipban-form">
        <h3 className="sec-ipban-form-title">Новая жалоба на сотрудника</h3>
        <div className="staff-complaint-form">
          <AdminSelect value={target} onChange={setTarget} options={memberOptions} placeholder="Сотрудник" />
          <input
            className="sec-input"
            placeholder="Причина жалобы"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button className="sec-btn sec-btn-sm" disabled={busy === 'create'} onClick={handleCreate}>
            Подать
          </button>
        </div>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-members">
        {items.map((c) => {
          const st = COMPLAINT_STATUS[c.status] || {}
          return (
            <div key={c.id} className="staff-complaint-row">
              <div className="staff-member-info">
                <span className="staff-card-name">
                  {c.targetAdminId
                    ? `на ${c.targetFirstName || (c.targetUsername ? `@${c.targetUsername}` : `ID ${c.targetAdminId}`)}`
                    : 'на модерацию (без адресата)'}
                </span>
                <span className="staff-badge" style={{ '--badge-color': c.source === 'player' ? '#f59e0b' : '#94a3b8' }}>
                  {c.source === 'player' ? `от игрока ${c.complainantPlayerId ?? ''}` : 'от стаффа'}
                </span>
                <span className="staff-badge" style={{ '--badge-color': st.color || '#94a3b8' }}>{st.label || c.status}</span>
                <span className="staff-card-date">{fmtDate(c.createdAt)}</span>
              </div>
              <p className="staff-answer-a"><b>Причина:</b> {c.reason}</p>
              {c.evidence && <p className="staff-answer-a"><b>Доказательства от сотрудника:</b> {c.evidence}</p>}
              {c.resolution && <p className="staff-answer-a"><b>Решение:</b> {c.resolution}</p>}
              <div className="staff-member-buttons">
                {c.status === 'open' && (
                  <button className="sec-btn sec-btn-sm" disabled={busy === `take-${c.id}`} onClick={() => handleTake(c.id)}>
                    Взять в работу
                  </button>
                )}
                {c.status !== 'resolved' && (
                  <button className="sec-btn sec-btn-sm sec-btn-success" disabled={busy === `res-${c.id}`} onClick={() => handleResolve(c.id)}>
                    Закрыть с решением
                  </button>
                )}
              </div>
            </div>
          )
        })}
        {!loading && items.length === 0 && <p className="sec-empty"></p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: My complaints (worker attaches evidence)
// ---------------------------------------------------------------------------

function MyComplaintsTab() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [drafts, setDrafts] = useState({})
  const [busy, setBusy] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchMyComplaints()
      setItems(data.items || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSubmit = async (id) => {
    const evidence = (drafts[id] || '').trim()
    if (!evidence) { alert('Введите доказательства'); return }
    setBusy(id)
    try {
      await submitComplaintEvidence(id, evidence)
      await load()
    } catch (err) {
      alert(err?.message || 'Ошибка')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="sec-tab-body">
      <p className="staff-hint">
        Жалобы на вас, взятые в работу. Вы обязаны приложить доказательства
        (скриншоты/логи мута), иначе решение будет принято не в вашу пользу.
      </p>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-members">
        {items.map((c) => {
          const st = COMPLAINT_STATUS[c.status] || {}
          return (
            <div key={c.id} className="staff-complaint-row">
              <div className="staff-member-info">
                <span className="staff-badge" style={{ '--badge-color': st.color || '#94a3b8' }}>{st.label || c.status}</span>
                <span className="staff-card-date">{fmtDate(c.createdAt)}</span>
              </div>
              <p className="staff-answer-a"><b>Причина:</b> {c.reason}</p>
              {c.evidence && <p className="staff-answer-a"><b>Ваши доказательства:</b> {c.evidence}</p>}
              {c.status === 'in_progress' && (
                <div className="staff-complaint-form">
                  <textarea
                    className="sec-input"
                    rows={2}
                    placeholder="Доказательства мута: ссылки на скриншоты/логи"
                    value={drafts[c.id] ?? c.evidence ?? ''}
                    onChange={(e) => setDrafts((d) => ({ ...d, [c.id]: e.target.value }))}
                  />
                  <button className="sec-btn sec-btn-sm" disabled={busy === c.id} onClick={() => handleSubmit(c.id)}>
                    {busy === c.id ? '…' : 'Приложить'}
                  </button>
                </div>
              )}
              {c.status === 'open' && (
                <p className="staff-hint">Ожидает рассмотрения владельцем.</p>
              )}
            </div>
          )
        })}
        {!loading && items.length === 0 && <p className="sec-empty">Жалоб на вас нет</p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Ledger (реестр выплат)
// ---------------------------------------------------------------------------

const PERIODS = [
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'all', label: 'Всё время' },
]

function LedgerTab() {
  const [period, setPeriod] = useState('month')
  const [data, setData] = useState(null)
  const [pending, setPending] = useState([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await fetchStaffLedger(period))
      const p = await fetchPendingPayouts()
      setPending(p.items || [])
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => { load() }, [load])

  const confirmPayout = async (id) => {
    setBusy(`c-${id}`)
    try { await confirmPendingPayout(id); await load() }
    catch (e) { alert(e?.message || 'Ошибка') } finally { setBusy(null) }
  }
  const cancelPayout = async (id) => {
    if (!confirm('Отменить запрос на выплату?')) return
    setBusy(`x-${id}`)
    try { await cancelPendingPayout(id); await load() }
    catch (e) { alert(e?.message || 'Ошибка') } finally { setBusy(null) }
  }

  const exportCsv = () => {
    if (!data?.items?.length) return
    const head = ['Дата', 'Сотрудник', 'Роль', 'Сумма', 'Способ', 'Тип', 'TXID']
    const rows = data.items.map((it) => [
      it.paidAt || '',
      it.firstName || (it.username ? `@${it.username}` : it.userId),
      it.role || '', it.amount, it.method || '', it.kind, it.txid || '',
    ])
    const csv = [head, ...rows].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `payments_${period}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="sec-tab-body">
      <div className="sec-audit-filters">
        <AdminSelect value={period} onChange={setPeriod} options={PERIODS} />
        <button className="sec-btn sec-btn-ghost" onClick={load}>Обновить</button>
        <button className="sec-btn sec-btn-ghost" onClick={exportCsv} disabled={!data?.items?.length}>
          Экспорт CSV
        </button>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      {pending.length > 0 && (
        <div className="staff-appeals">
          <h3 className="sec-ipban-section-title">🔐 На подтверждении <span className="sec-count">{pending.length}</span></h3>
          {pending.map((p) => (
            <div key={p.id} className="staff-member-row">
              <div className="staff-member-info">
                <span className="staff-card-name">{p.firstName || (p.username ? `@${p.username}` : `ID ${p.userId}`)}</span>
                <span className="staff-badge" style={{ '--badge-color': '#fbbf24' }}>
                  {p.kind === 'advance' ? 'аванс' : 'выплата'} {p.amount} {p.method || ''}
                </span>
              </div>
              <div className="staff-member-buttons">
                <button className="sec-btn sec-btn-sm sec-btn-success" disabled={busy === `c-${p.id}`} onClick={() => confirmPayout(p.id)}>
                  Подтвердить
                </button>
                <button className="sec-btn sec-btn-ghost sec-btn-sm" disabled={busy === `x-${p.id}`} onClick={() => cancelPayout(p.id)}>
                  Отменить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {data && (
        <>
          <div className="staff-debts-banner">
            <span className="staff-badge" style={{ '--badge-color': '#34d399' }}>Всего выплачено: {data.total}</span>
            {Object.entries(data.byMethod).map(([m, v]) => (
              <span key={m} className="staff-badge" style={{ '--badge-color': '#94a3b8' }}>{m}: {v}</span>
            ))}
          </div>

          <div className="staff-members">
            {data.items.map((it) => (
              <div key={it.id} className="staff-member-row">
                <div className="staff-member-info">
                  <span className="staff-card-name">{it.firstName || (it.username ? `@${it.username}` : `ID ${it.userId}`)}</span>
                  <span className="staff-badge" style={{ '--badge-color': it.kind === 'advance' ? '#fbbf24' : '#34d399' }}>
                    {it.kind === 'advance' ? 'аванс' : 'выплата'} {it.amount}
                  </span>
                  {it.method && <span className="staff-card-date">{it.method}</span>}
                </div>
                <div className="staff-member-meta">
                  <span>{fmtDate(it.paidAt)}</span>
                  {it.txid && <span>TXID: {it.txid}</span>}
                </div>
              </div>
            ))}
            {data.items.length === 0 && <p className="sec-empty">Выплат за период нет</p>}
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Leaderboard / отчёты
// ---------------------------------------------------------------------------

function LeaderboardTab() {
  const [period, setPeriod] = useState('week')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await fetchStaffLeaderboard(period)
      setItems(d.items || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => { load() }, [load])

  const fmtResp = (sec) => {
    if (sec == null) return '—'
    if (sec < 60) return `${sec}с`
    if (sec < 3600) return `${Math.round(sec / 60)}м`
    return `${(sec / 3600).toFixed(1)}ч`
  }

  return (
    <div className="sec-tab-body">
      <div className="sec-audit-filters">
        <AdminSelect value={period} onChange={setPeriod} options={PERIODS} />
        <button className="sec-btn sec-btn-ghost" onClick={load}>Обновить</button>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-members">
        {items.map((m, i) => (
          <div key={m.userId} className="staff-member-row">
            <div className="staff-member-info">
              <span className="staff-card-name">#{i + 1} {nameOf(m)}</span>
              <span className="staff-badge" style={{ '--badge-color': ROLE_BADGE_COLOR[m.role] || '#94a3b8' }}>
                {roleLabel(m.role)}
              </span>
              <span className="staff-badge" style={{ '--badge-color': '#94a3b8' }}>счёт {m.score}</span>
            </div>
            <div className="staff-member-meta">
              <span>действий: {m.actionsTotal}</span>
              <span>жалоб: {m.complaintsResolved}/{m.complaintsTaken}</span>
              <span>реакция: {fmtResp(m.avgResponseSeconds)}</span>
              <span>онлайн: {(m.onlineMinutes / 60).toFixed(1)}ч</span>
            </div>
          </div>
        ))}
        {!loading && items.length === 0 && <p className="sec-empty">Нет данных</p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Shifts (график смен)
// ---------------------------------------------------------------------------

const ATTENDANCE = {
  upcoming: { label: 'предстоит', color: '#94a3b8' },
  attended: { label: 'был на смене', color: '#34d399' },
  missed: { label: 'не вышел', color: '#f87171' },
  ongoing: { label: 'идёт', color: '#fb923c' },
}

function ShiftsTab() {
  const [items, setItems] = useState([])
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ userId: '', startsAt: '', endsAt: '', note: '' })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await fetchStaffShifts()
      setItems(d.items || [])
      const m = await fetchStaffMembers()
      setMembers((m.items || []).filter((x) => x.role !== 'owner'))
    } catch { setItems([]) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const memberOptions = members.map((m) => ({ value: String(m.userId), label: nameOf(m) }))

  const add = async () => {
    if (!form.userId || !form.startsAt || !form.endsAt) { alert('Заполните сотрудника и время'); return }
    setBusy(true)
    try {
      await addStaffShift({
        userId: Number(form.userId),
        startsAt: new Date(form.startsAt).toISOString(),
        endsAt: new Date(form.endsAt).toISOString(),
        note: form.note.trim(),
      })
      setForm({ userId: '', startsAt: '', endsAt: '', note: '' })
      await load()
    } catch (e) { alert(e?.message || 'Ошибка') } finally { setBusy(false) }
  }

  const remove = async (id) => {
    if (!confirm('Удалить смену?')) return
    await deleteStaffShift(id)
    await load()
  }

  return (
    <div className="sec-tab-body">
      <div className="sec-ipban-form">
        <h3 className="sec-ipban-form-title">Новая смена</h3>
        <div className="staff-complaint-form">
          <AdminSelect value={form.userId} onChange={(v) => setForm((f) => ({ ...f, userId: v }))} options={memberOptions} placeholder="Сотрудник" />
          <input className="sec-input" type="datetime-local" value={form.startsAt} onChange={(e) => setForm((f) => ({ ...f, startsAt: e.target.value }))} />
          <input className="sec-input" type="datetime-local" value={form.endsAt} onChange={(e) => setForm((f) => ({ ...f, endsAt: e.target.value }))} />
          <input className="sec-input" placeholder="заметка" value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
          <button className="sec-btn sec-btn-sm" disabled={busy} onClick={add}>Добавить</button>
        </div>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-members">
        {items.map((s) => {
          const at = ATTENDANCE[s.attendance] || {}
          return (
            <div key={s.id} className="staff-member-row">
              <div className="staff-member-info">
                <span className="staff-card-name">{s.firstName || (s.username ? `@${s.username}` : `ID ${s.userId}`)}</span>
                <span className="staff-badge" style={{ '--badge-color': at.color || '#94a3b8' }}>{at.label || s.attendance}</span>
              </div>
              <div className="staff-member-meta">
                <span>{fmtDate(s.startsAt)} → {fmtDate(s.endsAt)}</span>
                <span>был: {(s.presentMinutes / 60).toFixed(1)}ч</span>
                {s.note && <span>{s.note}</span>}
              </div>
              <button className="sec-btn sec-btn-ghost sec-btn-sm" onClick={() => remove(s.id)}>✕</button>
            </div>
          )
        })}
        {!loading && items.length === 0 && <p className="sec-empty"></p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Questions (шаблоны вопросов анкеты)
// ---------------------------------------------------------------------------

function QuestionsTab({ isOwner = false }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ key: '', label: '', type: 'text', required: true, sortOrder: 0 })

  const load = useCallback(async () => {
    setLoading(true)
    try { setItems((await fetchApplicationQuestionsAdmin()).items || []) }
    catch { setItems([]) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const add = async () => {
    if (!form.key.trim() || !form.label.trim()) { alert('Ключ и текст обязательны'); return }
    setBusy(true)
    try {
      await upsertApplicationQuestion({
        key: form.key.trim(), label: form.label.trim(), type: form.type,
        required: form.required, sortOrder: Number(form.sortOrder) || 0, enabled: true,
      })
      setForm({ key: '', label: '', type: 'text', required: true, sortOrder: 0 })
      await load()
    } catch (e) { alert(e?.message || 'Ошибка') } finally { setBusy(false) }
  }

  const toggle = async (q) => {
    await upsertApplicationQuestion({ ...q, enabled: !q.enabled })
    await load()
  }
  const remove = async (id) => {
    if (!confirm('Удалить вопрос?')) return
    await deleteApplicationQuestion(id)
    await load()
  }

  return (
    <div className="sec-tab-body">
      <p className="staff-hint">Эти вопросы видит кандидат при подаче заявки. Ключ (латиница) идентификатор ответа.</p>
      {isOwner && (
        <div className="sec-ipban-form">
          <h3 className="sec-ipban-form-title">Новый вопрос</h3>
          <div className="staff-complaint-form">
            <input className="sec-input" placeholder="ключ (напр. experience)" value={form.key} onChange={(e) => setForm((f) => ({ ...f, key: e.target.value }))} />
            <input className="sec-input" placeholder="текст вопроса" value={form.label} onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))} />
            <AdminSelect value={form.type} onChange={(v) => setForm((f) => ({ ...f, type: v }))} options={[
              { value: 'text', label: 'Короткий' }, { value: 'textarea', label: 'Развёрнутый' },
            ]} />
            <input className="sec-input staff-salary-input" type="number" placeholder="порядок" value={form.sortOrder} onChange={(e) => setForm((f) => ({ ...f, sortOrder: e.target.value }))} />
            <button className="sec-btn sec-btn-sm" disabled={busy} onClick={add}>Добавить</button>
          </div>
        </div>
      )}

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-members">
        {items.map((q) => (
          <div key={q.id} className="staff-member-row">
            <div className="staff-member-info">
              <span className="staff-card-name">{q.label}</span>
              <span className="staff-badge" style={{ '--badge-color': '#94a3b8' }}>{q.type === 'textarea' ? 'развёрнутый' : 'короткий'}</span>
              {q.required && <span className="staff-badge" style={{ '--badge-color': '#fbbf24' }}>обязательный</span>}
              {!q.enabled && <span className="staff-badge" style={{ '--badge-color': '#94a3b8' }}>выключен</span>}
            </div>
            {isOwner && (
              <div className="staff-member-buttons">
                <button className="sec-btn sec-btn-ghost sec-btn-sm" onClick={() => toggle(q)}>{q.enabled ? 'Выключить' : 'Включить'}</button>
                <button className="sec-btn sec-btn-ghost sec-btn-sm" onClick={() => remove(q.id)}>✕</button>
              </div>
            )}
          </div>
        ))}
        {!loading && items.length === 0 && <p className="sec-empty">Вопросов нет</p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Invites
// ---------------------------------------------------------------------------

const TOKEN_STATUS = {
  used:    { label: 'использован', color: 'var(--e-text-3)' },
  revoked: { label: 'отозван',     color: 'var(--e-text-4)' },
  active:  { label: 'активен',     color: 'var(--e-text)' },
}

function tokenStatus(t) {
  if (t.revokedAt) return TOKEN_STATUS.revoked
  if (t.usedBy) return TOKEN_STATUS.used
  return TOKEN_STATUS.active
}

function InvitesTab() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(null)
  const [label, setLabel] = useState('')
  const [copiedId, setCopiedId] = useState(null)
  const copyTimerRef = useRef(null)

  useEffect(() => () => clearTimeout(copyTimerRef.current), [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchInviteTokens()
      setItems(data.items || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    setBusy('create')
    try {
      await createInviteToken(label.trim())
      setLabel('')
      await load()
    } catch (err) {
      alert(err?.message || 'Ошибка')
    } finally {
      setBusy(null)
    }
  }

  const handleRevoke = async (item) => {
    if (!confirm(`Отозвать инвайт «${item.label || item.token}»?`)) return
    setBusy(`rev-${item.id}`)
    try {
      await revokeInviteToken(item.id)
      await load()
    } catch (err) {
      alert(err?.message || 'Ошибка')
    } finally {
      setBusy(null)
    }
  }

  const handleDelete = async (item) => {
    if (!confirm(`Удалить инвайт «${item.label || item.token}»? Это действие нельзя отменить.`)) return
    setBusy(`del-${item.id}`)
    try {
      await deleteInviteToken(item.id)
      await load()
    } catch (err) {
      alert(err?.message || 'Ошибка')
    } finally {
      setBusy(null)
    }
  }

  const handleCopy = (item) => {
    navigator.clipboard?.writeText(item.token).catch(() => {})
    setCopiedId(item.id)
    clearTimeout(copyTimerRef.current)
    copyTimerRef.current = setTimeout(() => setCopiedId(null), 2000)
  }

  const activeCount = items.filter((t) => !t.revokedAt && !t.usedBy).length

  return (
    <div className="sec-tab-body">
      <p className="staff-hint">
        Каждый админ получает свой уникальный ключ.
      </p>

      <div className="sec-ipban-form">
        <h3 className="sec-ipban-form-title">Создать инвайт</h3>
        <div className="staff-complaint-form">
          <input
            className="sec-input"
            placeholder="Метка (для кого, например «для Сани»)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !busy && handleCreate()}
          />
          <button className="sec-btn sec-btn-sm" disabled={busy === 'create'} onClick={handleCreate}>
            {busy === 'create' ? '…' : 'Создать'}
          </button>
        </div>
      </div>

      <div className="sec-audit-filters">
        <button className="sec-btn sec-btn-ghost" onClick={load}>Обновить</button>
        <span className="sec-audit-count">активных: {activeCount} / всего: {items.length}</span>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-members">
        {items.map((t) => {
          const st = tokenStatus(t)
          return (
            <div key={t.id} className="staff-member-row">
              <div className="staff-member-info">
                <span className="staff-card-name">{t.label || '(без метки)'}</span>
                <span className="staff-badge" style={{ '--badge-color': st.color }}>{st.label}</span>
                {t.usedByName && (
                  <span className="staff-card-date">использовал: {t.usedByName}</span>
                )}
              </div>
              <div className="staff-member-meta">
                <code
                  className="staff-invite-token staff-invite-token-copy"
                  title="Нажми чтобы скопировать"
                  onClick={() => handleCopy(t)}
                  style={{ cursor: 'pointer' }}
                >
                  {copiedId === t.id ? '✓ Скопировано!' : t.token}
                </code>
                <span className="staff-card-date">создан: {fmtDate(t.createdAt)}</span>
                {t.usedAt && <span className="staff-card-date">использован: {fmtDate(t.usedAt)}</span>}
                {t.revokedAt && <span className="staff-card-date">отозван: {fmtDate(t.revokedAt)}</span>}
              </div>
              <div className="staff-member-buttons">
                {!t.usedBy && !t.revokedAt && (
                  <>
                    <button
                      className="sec-btn sec-btn-sm"
                      onClick={() => handleCopy(t)}
                    >
                      {copiedId === t.id ? 'Скопировано!' : 'Копировать'}
                    </button>
                    <button
                      className="sec-btn sec-btn-ghost sec-btn-sm"
                      disabled={busy === `rev-${t.id}`}
                      onClick={() => handleRevoke(t)}
                    >
                      {busy === `rev-${t.id}` ? '…' : 'Отозвать'}
                    </button>
                  </>
                )}
                <button
                  className="sec-btn sec-btn-danger sec-btn-sm"
                  disabled={busy === `del-${t.id}`}
                  onClick={() => handleDelete(t)}
                >
                  {busy === `del-${t.id}` ? '…' : 'Удалить'}
                </button>
              </div>
            </div>
          )
        })}
        {!loading && items.length === 0 && (
          <p className="sec-empty">Инвайтов пока нет. Создайте первый выше.</p>
        )}
      </div>
    </div>
  )
}


// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function StaffSection({ role, permissions = [], myUserId = null, panelTabs = null }) {
  const perms = useMemo(() => new Set(permissions), [permissions])
  const isOwner = role === 'owner'

  const tabs = useMemo(() => {
    const list = []
    if (perms.has('review_applications')) list.push({ id: 'applications', label: 'Заявки' })
    if (perms.has('manage_staff')) list.push({ id: 'members', label: 'Сотрудники' })
    if (perms.has('assign_roles')) list.push({ id: 'invites', label: 'Инвайты' })
    if (perms.has('set_salary')) list.push({ id: 'salaries', label: 'Зарплаты' })
    if (perms.has('set_salary')) list.push({ id: 'bonuses', label: 'Премии' })
    if (perms.has('pay_salary')) list.push({ id: 'ledger', label: 'Реестр' })
    if (isOwner) list.push({ id: 'payoutsettings', label: 'Настройки выплат' })
    if (perms.has('manage_staff')) list.push({ id: 'leaderboard', label: 'Отчёты' })
    if (perms.has('manage_staff')) list.push({ id: 'shifts', label: 'Смены' })
    if (perms.has('manage_staff')) list.push({ id: 'complaints', label: 'Жалобы' })
    if (perms.has('manage_staff')) list.push({ id: 'questions', label: 'Анкета' })
    if (role && role !== 'owner') list.push({ id: 'mysalary', label: 'Моя зарплата' })
    if (role && role !== 'owner') list.push({ id: 'mycomplaints', label: 'Жалобы на меня' })
    return filterSectionTabs('staff', list, panelTabs)
  }, [perms, role, isOwner, panelTabs])

  const [tab, setTab] = useState(null)
  const activeTab = tab && tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id

  return (
    <section className="panel-security">
      <header className="sec-header">
        <h2 className="sec-title">Стафф</h2>
        <p className="sec-subtitle">
          Заявки, сотрудники, зарплаты и выплаты
        </p>
      </header>

      <nav className="sec-tabs" aria-label="Разделы стаффа">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`sec-tab${activeTab === t.id ? ' sec-tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {/* Каждая вкладка сама рендерит .sec-tab-body — без внешней обёртки,
          иначе вложенный overflow ломает прокрутку (Зарплаты и др.). */}
      {activeTab === 'applications' && <ApplicationsTab />}
      {activeTab === 'members' && <MembersTab canAssignRoles={perms.has('assign_roles')} isOwner={isOwner} myUserId={myUserId} canManageStaff={perms.has('manage_staff')} />}
      {activeTab === 'invites' && <InvitesTab />}
      {activeTab === 'salaries' && (
        <PayrollSalariesTab isOwner={isOwner} canPay={perms.has('pay_salary')} myUserId={myUserId} />
      )}
      {activeTab === 'bonuses' && <PayrollBonusesTab isOwner={isOwner} canPay={perms.has('pay_salary')} />}
      {activeTab === 'ledger' && <LedgerTab />}
      {activeTab === 'payoutsettings' && <PayrollSettingsTab />}
      {activeTab === 'leaderboard' && <LeaderboardTab />}
      {activeTab === 'shifts' && <ShiftsTab />}
      {activeTab === 'complaints' && <ComplaintsTab />}
      {activeTab === 'questions' && <QuestionsTab isOwner={isOwner} />}
      {activeTab === 'mysalary' && <PayrollMySalaryTab />}
      {activeTab === 'mycomplaints' && <MyComplaintsTab />}
      {!activeTab && <p className="sec-empty sec-tab-body">Нет доступных разделов</p>}
    </section>
  )
}
