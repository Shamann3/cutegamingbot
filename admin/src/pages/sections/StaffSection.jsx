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
  purgeStaffMember,
  takeStaffComplaint,
  reissueStaffKey,
  showStaffKey,
  appointGroupAdmin,
  checkRealmMember,
  dismissGroupAdmin,
  disableGroupAccess,
  reissueGroupKey,
  issueOwnGroupKey,
  showGroupKey,
  fetchRightsBoard,
} from '../../lib/adminClient'
import AdminSelect from '../../components/AdminSelect'
import DarkPick from '../../components/DarkPick'
import CountUp from '../../components/CountUp'
import { EntryGuideBoard } from '../../components/EntryGuide'
import { showToast } from '../../components/ToastHost'
import { CopyableId, CopyableUsername } from '../../components/Copyable'
import UserLookupPreview from '../../components/UserLookupPreview'
import { APPLICATION_QUESTIONS, PAYOUT_OPTIONS } from '../../config/applicationQuestions'
import PayrollSalariesTab from './payroll/SalariesTab'
import DeedPay from './payroll/DeedPay'
import CreatorPay from './payroll/CreatorPay'
import PayrollBonusesTab from './payroll/BonusesTab'
import PayrollSettingsTab from './payroll/SettingsTab'
import PayrollMySalaryTab from './payroll/MySalaryTab'
import StatDesk from './StatDesk'
import { filterSectionTabs } from '../../constants/panelAccessTree'
import RightsSection from './RightsSection'
import StaffAccessPane from './StaffAccessPane'
import StaffPreviewPane from './StaffPreviewPane'
import GroupApplicationsPane from './GroupApplicationsPane'
import OfficialGroupsPane from './OfficialGroupsPane'
import GroupPreviewPane from './GroupPreviewPane'
import AccessKeySheet from '../../components/AccessKeySheet'
import OwnKeyControl from '../../components/OwnKeyControl'
import EverywhereSeat from '../../components/EverywhereSeat'

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

function ReviewModal({ application, onClose, onApproved, onRejected, onOpenUser = null }) {
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
          Подана {fmtDate(application.createdAt)} · <CopyableId value={application.userId} />
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
              {onOpenUser && (
                <button
                  type="button"
                  className="panel-users-btn"
                  disabled={loading}
                  onClick={() => { onOpenUser(application.userId); onClose() }}
                >
                  Открыть в Игроках
                </button>
              )}
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

function ApplicationsTab({ onOpenUser = null }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [active, setActive] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchStaffApplications('pending')
      setItems(data.items || [])
    } catch (err) {
      setItems([])
      setError(err?.message || 'Заявки сотрудников не открылись')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="sec-tab-body staff-apps staff-apps-staff">
      <p className="staff-hint">
        Заявки в команду проекта. Одобрение выдаёт должность панели сотрудника. Это не заявка администратора группы.
      </p>
      {error && (
        <div className="pa-error" role="alert">
          <p className="sec-error">{error}</p>
          <button type="button" className="sec-btn sec-btn-sm" onClick={load}>Повторить</button>
        </div>
      )}
      <div className="sec-audit-filters">
        <button className="sec-btn sec-btn-ghost" onClick={load}>Обновить</button>
        <span className="sec-audit-count">{items.length} заявок</span>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-app-list">
        {items.map((app) => (
          <div key={app.id} className="staff-app-card">
            <button type="button" className="staff-app-open" onClick={() => setActive(app)}>
              <span className="staff-card-name">{nameOf(app)}</span>
              <span className="staff-card-date">{fmtDate(app.createdAt)}</span>
              <span className="staff-badge staff-badge-pulse" style={{ '--badge-color': '#fbbf24' }}>
                ожидает
              </span>
            </button>
            {onOpenUser && (
              <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={() => onOpenUser(app.userId)}>
                Открыть в Игроках
              </button>
            )}
          </div>
        ))}
        {!loading && items.length === 0 && !error && (
          <p className="sec-empty">Новых заявок в команду нет</p>
        )}
      </div>

      {active && (
        <ReviewModal
          application={active}
          onOpenUser={onOpenUser}
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

function MembersTab({ canAssignRoles, isOwner, myUserId, canManageStaff, isProjectCreator = false }) {
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
  const [accessSheet, setAccessSheet] = useState(null)

  useEffect(() => { load() }, [load])

  const lookStaffKey = async (member) => {
    setActing(member.userId)
    setAccessSheet({ member, step: 'look', key: '', error: '', copy: '' })
    try {
      const data = await showStaffKey(member.userId)
      const loginKey = data?.loginKey || ''
      setAccessSheet({
        member,
        step: 'look',
        key: loginKey,
        error: '',
        copy: loginKey ? '' : 'Сейчас действующего ключа нет. Когда доступ включён, ключ откроется здесь.',
      })
    } catch (err) {
      setAccessSheet({
        member,
        step: 'look',
        key: '',
        error: err?.message || 'Ключ не открылся',
        copy: '',
      })
    } finally {
      setActing(null)
    }
  }

  const confirmAccess = async () => {
    if (!accessSheet || accessSheet.step === 'shown' || accessSheet.step === 'look') return
    const member = accessSheet.member
    setActing(member.userId)
    setAccessSheet((current) => (current ? { ...current, error: '' } : current))
    try {
      if (accessSheet.step === 'off') {
        await suspendStaffMember(member.userId)
        await load()
        setAccessSheet(null)
      } else {
        const data = await reissueStaffKey(member.userId)
        const loginKey = data?.loginKey || ''
        if (!loginKey) throw new Error('Сервер не вернул ключ')
        await load()
        setAccessSheet((current) => (current ? { ...current, step: 'shown', key: loginKey, error: '' } : current))
      }
    } catch (err) {
      setAccessSheet((current) => (
        current ? { ...current, error: err?.message || 'Не вышло' } : current
      ))
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
      alert(err.message || 'Не удалось удалить')
    } finally {
      setActing(null)
    }
  }

  const handlePurge = async (member) => {
    if (!window.confirm(`Убрать допуск ${nameOf(member)}? Он выйдет из панели сотрудника и из групп. Снова войти можно только новой заявкой и новым ключом.`)) return
    setActing(member.userId)
    try {
      await purgeStaffMember(member.userId)
      await load()
    } catch (err) {
      alert(err.message || 'Сбросить допуск не удалось')
    } finally {
      setActing(null)
    }
  }

  return (
    <div className="sec-tab-body">
      <div className="sec-audit-filters">
        <button className="sec-btn sec-btn-ghost" onClick={load}>Обновить</button>
        <span className="sec-audit-count">{items.length} сотрудников</span>
        <p className="realm-copy">Отключение закрывает вход и гасит старый ключ. Роль остаётся. Новый ключ можно выдать потом.{isProjectCreator ? ' Действующий ключ другого человека открывается кнопкой «Ключ».' : ''}</p>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="staff-members">
        {items.map((m) => (
          <div key={m.userId} className="staff-member-row">
            <div className="staff-member-info">
              <span className="staff-card-name">{nameOf(m)}</span>
              {m.username ? <CopyableUsername value={m.username} /> : null}
              {m.userId ? <CopyableId value={m.userId} /> : null}
              <span className="staff-badge" style={{ '--badge-color': ROLE_BADGE_COLOR[m.role] || '#94a3b8' }}>
                {m.roleLabel}
              </span>
              {m.status === 'suspended' && (
                <span className="staff-badge" style={{ '--badge-color': '#f87171' }}>доступ выключен</span>
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
                    {isProjectCreator && !isSelf && (
                      <button
                        className="sec-btn sec-btn-sm sec-btn-danger"
                        disabled={acting === m.userId}
                        onClick={() => handlePurge(m)}
                      >
                        {acting === m.userId ? '…' : 'Убрать допуск'}
                      </button>
                    )}
                    {isProjectCreator && !isSelf && (
                      <button
                        className="sec-btn sec-btn-ghost sec-btn-sm"
                        disabled={acting === m.userId}
                        onClick={() => lookStaffKey(m)}
                      >
                        Ключ
                      </button>
                    )}
                    {m.role !== 'owner' && m.status !== 'suspended' && !isSelf && (
                      <button
                        className="sec-btn sec-btn-ghost sec-btn-sm"
                        disabled={acting === m.userId}
                        onClick={() => setAccessSheet({ member: m, step: 'off', key: '', error: '' })}
                      >
                        Отключить
                      </button>
                    )}
                    {m.role !== 'owner' && m.status === 'suspended' && !isSelf && (
                      <>
                        <button
                          className="sec-btn sec-btn-sm sec-btn-success"
                          disabled={acting === m.userId}
                          onClick={() => setAccessSheet({ member: m, step: 'key', key: '', error: '' })}
                        >
                          Выдать ключ
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
                    {isSelf && <OwnKeyControl variant="inline" />}
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

      <AccessKeySheet
        open={Boolean(accessSheet)}
        name={accessSheet ? nameOf(accessSheet.member) : ''}
        kind="staff"
        step={accessSheet?.step || 'off'}
        busy={Boolean(accessSheet && acting === accessSheet.member.userId)}
        error={accessSheet?.error || ''}
        issuedKey={accessSheet?.key || ''}
        copy={accessSheet?.copy || ''}
        onClose={() => { if (!acting) setAccessSheet(null) }}
        onConfirm={confirmAccess}
      />

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

function LedgerTab({ isProjectCreator = false }) {
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
        {isProjectCreator && (
          <button className="sec-btn sec-btn-ghost" onClick={exportCsv} disabled={!data?.items?.length}>
            Экспорт CSV
          </button>
        )}
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      {pending.length > 0 && (
        <div className="staff-appeals">
          <h3 className="sec-ipban-section-title">🔐 На подтверждении <span className="sec-count">{pending.length}</span></h3>
          {pending.map((p) => (
            <div key={p.id} className="staff-member-row">
              <div className="staff-member-info">
                <span className="staff-card-name">{p.firstName || (p.username ? `@${p.username}` : `ID ${p.userId}`)}</span>
                {p.username ? <CopyableUsername value={p.username} /> : null}
                {p.userId ? <CopyableId value={p.userId} /> : null}
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
                  {it.username ? <CopyableUsername value={it.username} /> : null}
                  {it.userId ? <CopyableId value={it.userId} /> : null}
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
              {m.username ? <CopyableUsername value={m.username} /> : null}
              {m.userId ? <CopyableId value={m.userId} /> : null}
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
                {s.username ? <CopyableUsername value={s.username} /> : null}
                {s.userId ? <CopyableId value={s.userId} /> : null}
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

function positionPrefix(position) {
  if (!position) return ''
  const stored = String(position.prefix || '').trim()
  if (stored) return stored.slice(0, 16)
  if (position.kind === 'spamblock') return 'спам блок'
  if (position.kind === 'member') return ''
  return String(position.title || '').trim().slice(0, 16)
}

function positionHint(position) {
  if (position.kind === 'spamblock') return 'ранг 0, нужен срок'
  if (position.kind === 'member' || Number(position.rank) <= 0) return 'ранг 0'
  return `ранг ${position.rank}`
}

function InvitesTab({ isProjectCreator = false, scope = 'both', myUserId = null }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(null)
  const [label, setLabel] = useState('')
  const [copiedId, setCopiedId] = useState(null)
  const copyTimerRef = useRef(null)

  // Group-admin invite (appoint + show entry key)
  const [groups, setGroups] = useState([])
  const [gaUser, setGaUser] = useState('')
  const [gaUserId, setGaUserId] = useState(null)
  const [gaChatId, setGaChatId] = useState('')
  const [gaPosId, setGaPosId] = useState('')
  const [gaReason, setGaReason] = useState('')
  const [gaKey, setGaKey] = useState('')
  const [gaError, setGaError] = useState('')
  const [gaNote, setGaNote] = useState('')
  const [gaStart, setGaStart] = useState('')
  const [gaEnd, setGaEnd] = useState('')
  const [gaCheck, setGaCheck] = useState('')
  const [gaEverywhere, setGaEverywhere] = useState(false)
  const [accessSheet, setAccessSheet] = useState(null)
  const [ownSheet, setOwnSheet] = useState(null)

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

  useEffect(() => {
    if (!isProjectCreator) return undefined
    let cancelled = false
    fetchRightsBoard()
      .then((data) => {
        if (cancelled) return
        const list = data.groups || []
        setGroups(list)
        if (list[0] && !gaChatId) setGaChatId(String(list[0].chatId))
      })
      .catch(() => { if (!cancelled) setGroups([]) })
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isProjectCreator])

  const gaGroup = groups.find((x) => String(x.chatId) === String(gaChatId)) || null
  const gaPositions = useMemo(() => {
    return (gaGroup?.positions || []).filter((p) => Number(p.rank) < 5)
  }, [gaGroup])
  const gaPost = gaPositions.find((p) => String(p.id) === String(gaPosId)) || null
  const gaSpam = gaPost?.kind === 'spamblock'
  const gaPrefix = positionPrefix(gaPost)

  const handleCreate = async (e) => {
    e?.preventDefault?.()
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

  const handleGroupAppoint = async (e) => {
    e?.preventDefault?.()
    setGaError('')
    setGaKey('')
    setGaNote('')
    const uid = Number(gaUserId || String(gaUser).replace(/\D/g, ''))
    const chatId = Number(gaChatId)
    const positionId = Number(gaPosId)
    if (!uid || !chatId || !positionId) {
      setGaError('Выберите человека, группу и должность')
      return
    }
    if (gaSpam && !gaEnd) {
      setGaError('Для спам-блока укажите, по какое число держать должность')
      return
    }
    setBusy('ga')
    try {
      const res = await appointGroupAdmin({
        chat_id: chatId,
        user_id: uid,
        position_id: positionId,
        reason: gaReason.trim() || 'Назначение из панели',
        prefix: gaPrefix,
        term_start: gaSpam ? gaStart : '',
        term_end: gaSpam ? gaEnd : '',
        everywhere: gaEverywhere,
      })
      setGaKey(res?.entryKey || '')
      setGaNote(res?.telegram || (gaPrefix ? `В группе стоит префикс «${gaPrefix}».` : 'Должность назначена.'))
      setGaUser('')
      setGaUserId(null)
      setGaReason('')
      setGaPosId('')
      setGaStart('')
      setGaEnd('')
      setGaCheck('')
      const data = await fetchRightsBoard()
      setGroups(data.groups || [])
    } catch (err) {
      setGaError(err?.message || 'Не удалось выдать ключ админа группы')
    } finally {
      setBusy(null)
    }
  }

  const reloadGroups = async () => {
    const data = await fetchRightsBoard()
    setGroups(data.groups || [])
  }

  const confirmOwnKey = async () => {
    if (!ownSheet || ownSheet.step === 'shown') return
    setBusy('own-key')
    setOwnSheet((current) => (current ? { ...current, error: '' } : current))
    try {
      const data = await issueOwnGroupKey()
      const entryKey = data?.entryKey || ''
      if (!entryKey) throw new Error('Сервер не вернул ключ')
      setOwnSheet({ step: 'shown', key: entryKey, error: '' })
    } catch (err) {
      setOwnSheet((current) => (
        current ? { ...current, error: err?.message || 'Не вышло' } : current
      ))
    } finally {
      setBusy(null)
    }
  }

  const lookGroupKey = async (person) => {
    setBusy(`access-${person.userId}`)
    setAccessSheet({ person, step: 'look', key: '', error: '', copy: '' })
    try {
      const data = await showGroupKey(person.userId)
      const entryKey = data?.entryKey || ''
      setAccessSheet({
        person,
        step: 'look',
        key: entryKey,
        error: '',
        copy: entryKey
          ? ''
          : 'Копии этого ключа нет: он выдан до того, как панель стала его хранить. Отключите доступ и выдайте новый — тогда ключ останется у вас.',
      })
    } catch (err) {
      setAccessSheet({
        person,
        step: 'look',
        key: '',
        error: err?.message || 'Ключ не открылся',
        copy: '',
      })
    } finally {
      setBusy(null)
    }
  }

  const confirmGroupAccess = async () => {
    if (!accessSheet || accessSheet.step === 'shown' || accessSheet.step === 'look') return
    const person = accessSheet.person
    setBusy(`access-${person.userId}`)
    setAccessSheet((current) => (current ? { ...current, error: '' } : current))
    try {
      if (accessSheet.step === 'off') {
        await disableGroupAccess(person.userId)
        await reloadGroups()
        setAccessSheet(null)
      } else {
        const data = await reissueGroupKey(person.userId)
        const entryKey = data?.entryKey || ''
        if (!entryKey) throw new Error('Сервер не вернул ключ')
        await reloadGroups()
        setAccessSheet((current) => (current ? { ...current, step: 'shown', key: entryKey, error: '' } : current))
      }
    } catch (err) {
      setAccessSheet((current) => (
        current ? { ...current, error: err?.message || 'Не вышло' } : current
      ))
    } finally {
      setBusy(null)
    }
  }

  const handleDismiss = async (person) => {
    const name = person.name || person.userId
    if (!window.confirm(`Снять должность «${person.position}» с ${name}? Человек останется в группе обычным участником, префикс в чате снимется.`)) return
    setGaError('')
    setGaNote('')
    setBusy(`off-${person.userId}`)
    try {
      const res = await dismissGroupAdmin({ chat_id: Number(gaChatId), user_id: person.userId })
      setGaNote(res?.telegram || 'Должность снята, префикс в группе убран.')
      const data = await fetchRightsBoard()
      setGroups(data.groups || [])
    } catch (err) {
      setGaError(err?.message || 'Снять должность не удалось')
    } finally {
      setBusy(null)
    }
  }

  const handleSpamCheck = async () => {
    const uid = Number(gaUserId || String(gaUser).replace(/\D/g, ''))
    if (!gaChatId || !uid) {
      setGaCheck('Сначала выберите человека и группу')
      return
    }
    setGaCheck('Смотрим ответ Telegram…')
    try {
      const data = await checkRealmMember(gaChatId, uid)
      setGaCheck(data.note || 'Telegram ничего не добавил')
      if (data.until) setGaEnd(data.until)
    } catch (err) {
      setGaCheck(err.message || 'Проверка не ответила')
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
    <div className="sec-tab-body staff-invites-tab">
      <p className="staff-hint">
        {scope === 'group'
          ? 'Личный ключ кабинета группы. Создатель открывает его у человека на должности и может скопировать снова.'
          : 'Ключ входа в панель сотрудника. Человек вводит его на экране регистрации, затем подтверждает код из аутентификатора.'}
      </p>

      {isProjectCreator && <EntryGuideBoard office={scope === 'group' ? 'group' : 'staff'} />}

      {scope !== 'group' && <div className="sec-ipban-form staff-invite-block">
        <h3 className="sec-ipban-form-title">Ключ для сотрудника проекта</h3>
        <form className="staff-complaint-form staff-invite-form" onSubmit={handleCreate}>
          <input
            className="sec-input staff-invite-label-input"
            type="text"
            name="inviteLabel"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            inputMode="text"
            placeholder="Метка (для кого, например «для Сани»)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            disabled={busy === 'create'}
          />
          <button type="submit" className="sec-btn sec-btn-sm" disabled={busy === 'create'}>
            {busy === 'create' ? '…' : 'Создать'}
          </button>
        </form>
      </div>}

      {scope !== 'staff' && <div className="sec-ipban-form staff-group-admin-invite staff-invite-block">
        <h3 className="sec-ipban-form-title">Ключ для админа группы</h3>
        {!isProjectCreator ? (
          <p className="staff-hint">
            Выдать ключ админа группы может только создатель проекта (назначение должности + личный ключ входа).
          </p>
        ) : (
          <form className="staff-invite-form staff-ga-form" onSubmit={handleGroupAppoint}>
            <div className="staff-ga-own">
              <p className="realm-copy">Если ключ уже действует, откройте «Мой ключ» в настройках: он виден и изнутри панели. Эта кнопка выдаёт новый, только когда действующего нет.</p>
              <button
                type="button"
                className="sec-btn sec-btn-sm"
                onClick={() => setOwnSheet({ step: 'key', key: '', error: '' })}
              >
                Получить ключ кабинета
              </button>
            </div>
            <UserLookupPreview
              value={gaUser}
              onChange={(v) => { setGaUser(v); setGaUserId(null) }}
              onResolved={(u) => setGaUserId(u?.userId ?? u?.user_id ?? null)}
              placeholder="ID, @username или имя"
              label="Человек"
            />
            <DarkPick
              label="Группа"
              value={gaChatId}
              placeholder="Выберите группу"
              options={groups.map((g) => ({
                value: String(g.chatId),
                label: g.title || String(g.chatId),
                hint: `${g.seats?.length || 0} на должностях`,
              }))}
              onChange={(next) => { setGaChatId(next); setGaPosId('') }}
            />
            <DarkPick
              label="Должность"
              value={gaPosId}
              placeholder="Выберите должность"
              options={gaPositions.map((p) => ({
                value: String(p.id),
                label: p.title,
                hint: positionHint(p),
              }))}
              onChange={setGaPosId}
            />
            {gaPost && (
              <p className="realm-copy">
                {gaPrefix
                  ? `В группе автоматически встанет префикс «${gaPrefix}».`
                  : 'Это обычный участник: префикс в группе не ставится.'}
              </p>
            )}
            {gaSpam && (
              <div className="staff-ga-term">
                <p className="realm-copy">Спам-блок не даёт наказаний. Укажите срок: с какого числа по какое должность держится. Когда срок выйдет, должность и префикс снимутся сами.</p>
                <label className="staff-ga-field">С какого числа
                  <input className="sec-input" type="date" value={gaStart} onChange={(e) => setGaStart(e.target.value)} />
                </label>
                <label className="staff-ga-field">По какое число
                  <input className="sec-input" type="date" value={gaEnd} onChange={(e) => setGaEnd(e.target.value)} />
                </label>
                <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={handleSpamCheck}>Проверить ответ Telegram</button>
                {gaCheck && <p className="realm-note" role="status">{gaCheck}</p>}
              </div>
            )}
            <label className="staff-ga-field">
              <span>Для чего?</span>
              <input
                className="sec-input"
                type="text"
                value={gaReason}
                onChange={(e) => setGaReason(e.target.value)}
                placeholder="Причина назначения"
                autoComplete="off"
              />
            </label>
            <EverywhereSeat on={gaEverywhere} onChange={setGaEverywhere} />
            <button type="submit" className="sec-btn sec-btn-sm" disabled={busy === 'ga'}>
              {busy === 'ga' ? '…' : 'Назначить и выдать ключ'}
            </button>
            {gaError && <p className="sec-error">{gaError}</p>}
            {gaNote && <p className="realm-note" role="status">{gaNote}</p>}
            {gaKey && (
              <p className="realm-alert staff-ga-key" data-copyable="1">
                Личный ключ (один показ): <code>{gaKey}</code>
              </p>
            )}
            {gaGroup && (
            <div className="staff-ga-seats">
              <h4 className="realm-h">Сейчас на должностях</h4>
              <p className="realm-copy">Отключение закрывает кабинет и гасит старый ключ. Должность остаётся. Снятие убирает должность и префикс, из чата человека не исключает.</p>
              {(gaGroup.seats || []).length === 0 && <p className="realm-copy">В этой группе должностей ни у кого нет.</p>}
              <ul className="realm-list">
                {(gaGroup?.seats || []).map((person) => {
                  const isSelf = myUserId != null && person.userId === myUserId
                  return (
                  <li key={person.userId} className={`realm-row staff-ga-person${person.accessOff ? ' is-access-off' : ''}`}>
                    <strong>{person.name || person.userId}{person.username ? ` · @${person.username}` : ''}</strong>
                    <span>
                      {person.position}{person.prefix ? ` · «${person.prefix}»` : ''}{person.termEnd ? ` · до ${person.termEnd}` : ''}
                      {person.mutedUntil ? ' · мут, должность на месте' : ''}
                      {person.banUntil ? ' · бан, должность отложена' : ''}
                      {person.paused ? ' · ждёт конца бана' : ''}
                      {person.accessOff ? ' · доступ выключен' : ''}
                    </span>
                    <div className="staff-ga-actions">
                      {isProjectCreator && !isSelf && !person.accessOff && (
                        <button
                          type="button"
                          className="sec-btn sec-btn-ghost sec-btn-sm"
                          disabled={busy === `access-${person.userId}`}
                          onClick={() => lookGroupKey(person)}
                        >
                          Ключ
                        </button>
                      )}
                      {!isSelf && !person.accessOff && (
                        <button
                          type="button"
                          className="sec-btn sec-btn-ghost sec-btn-sm"
                          disabled={busy === `access-${person.userId}`}
                          onClick={() => setAccessSheet({ person, step: 'off', key: '', error: '' })}
                        >
                          Отключить
                        </button>
                      )}
                      {!isSelf && person.accessOff && (
                        <button
                          type="button"
                          className="sec-btn sec-btn-sm sec-btn-success"
                          disabled={busy === `access-${person.userId}`}
                          onClick={() => setAccessSheet({ person, step: 'key', key: '', error: '' })}
                        >
                          Выдать ключ
                        </button>
                      )}
                      <button
                        type="button"
                        className="sec-btn sec-btn-ghost sec-btn-sm"
                        disabled={busy === `off-${person.userId}`}
                        onClick={() => handleDismiss(person)}
                      >
                        {busy === `off-${person.userId}` ? '…' : 'Снять должность'}
                      </button>
                    </div>
                  </li>
                  )
                })}
              </ul>
            </div>
            )}
          </form>
        )}
      </div>}

      {scope !== 'group' && <>
      <div className="sec-audit-filters">
        <button type="button" className="sec-btn sec-btn-ghost" onClick={load}>Обновить</button>
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
                  data-copyable="1"
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
                      type="button"
                      className="sec-btn sec-btn-sm"
                      onClick={() => handleCopy(t)}
                    >
                      {copiedId === t.id ? 'Скопировано!' : 'Копировать'}
                    </button>
                    <button
                      type="button"
                      className="sec-btn sec-btn-ghost sec-btn-sm"
                      disabled={busy === `rev-${t.id}`}
                      onClick={() => handleRevoke(t)}
                    >
                      {busy === `rev-${t.id}` ? '…' : 'Отозвать'}
                    </button>
                  </>
                )}
                <button
                  type="button"
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
      </>}

      <AccessKeySheet
        open={Boolean(ownSheet)}
        name="Ваш кабинет"
        kind="group"
        copy="Этот ключ открывает панель администратора. Он показывается один раз."
        step={ownSheet?.step || 'key'}
        busy={busy === 'own-key'}
        error={ownSheet?.error || ''}
        issuedKey={ownSheet?.key || ''}
        onClose={() => { if (busy !== 'own-key') setOwnSheet(null) }}
        onConfirm={confirmOwnKey}
      />

      <AccessKeySheet
        open={Boolean(accessSheet)}
        name={accessSheet?.person?.name || (accessSheet ? String(accessSheet.person.userId) : '')}
        kind="group"
        step={accessSheet?.step || 'off'}
        busy={Boolean(accessSheet && busy === `access-${accessSheet.person.userId}`)}
        error={accessSheet?.error || ''}
        issuedKey={accessSheet?.key || ''}
        copy={accessSheet?.copy || ''}
        onClose={() => { if (!String(busy || '').startsWith('access-')) setAccessSheet(null) }}
        onConfirm={confirmGroupAccess}
      />
    </div>
  )
}


// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const OFFICES = [
  { id: 'staff', title: 'Сотрудники', detail: 'Панель сотрудника проекта' },
  { id: 'group', title: 'Администраторы', detail: 'Кабинет официальных групп' },
]

export default function StaffSection({ role, permissions = [], myUserId = null, panelTabs = null, isProjectCreator = false, entry = null, onOpenPreview = null, onOpenUser = null }) {
  const perms = useMemo(() => new Set(permissions), [permissions])
  const isOwner = role === 'owner'
  const canConfigure = isProjectCreator || perms.has('manage_panel_access')

  const workTabs = useMemo(() => {
    const list = []
    if (perms.has('manage_staff')) list.push({ id: 'members', label: 'Люди' })
    if (perms.has('set_salary') && !isProjectCreator) list.push({ id: 'salaries', label: 'Зарплаты' })
    if (perms.has('set_salary')) list.push({ id: 'bonuses', label: 'Премии' })
    if (perms.has('pay_salary')) list.push({ id: 'ledger', label: 'Реестр' })
    if (isOwner) list.push({ id: 'payoutsettings', label: 'Настройки выплат' })
    if (perms.has('manage_staff')) list.push({ id: 'leaderboard', label: 'Отчёты' })
    if (perms.has('manage_staff')) list.push({ id: 'shifts', label: 'Смены' })
    if (perms.has('manage_staff')) list.push({ id: 'complaints', label: 'Жалобы' })
    if (perms.has('manage_staff')) list.push({ id: 'questions', label: 'Анкета' })
    if (role && role !== 'owner') list.push({ id: 'mysalary', label: 'Моя зарплата' })
    if (role && role !== 'owner') list.push({ id: 'mycomplaints', label: 'Жалобы на меня' })
    if (!isProjectCreator && role && role !== 'applicant') {
      list.unshift({ id: 'deeds', label: 'За дело' })
    }
    const filtered = filterSectionTabs('staff', list, panelTabs)
    return filtered
  }, [perms, role, isOwner, panelTabs, isProjectCreator])

  const offices = useMemo(() => {
    const allowed = panelTabs?.staff
    const open = (id) => !Array.isArray(allowed) || allowed.includes(id)
    const canPreview = isProjectCreator && typeof onOpenPreview === 'function'
    const staff = []
    const group = []
    if (canConfigure) staff.push({ id: 'access', label: 'Доступ' })
    if (canPreview) staff.push({ id: 'view', label: 'Копия панели' })
    if (perms.has('review_applications') && open('applications')) staff.push({ id: 'apps', label: 'Заявки' })
    if (perms.has('assign_roles') && open('invites')) staff.push({ id: 'keys', label: 'Ключи' })
    if (isProjectCreator) staff.push({ id: 'pay', label: 'Зарплаты' })
    if (isProjectCreator) staff.push({ id: 'stats', label: 'Статистика' })
    if (workTabs.length) staff.push({ id: 'work', label: 'Команда' })
    if (isProjectCreator) {
      group.push({ id: 'groups', label: 'Группы' })
      group.push({ id: 'posts', label: 'Должности' })
      if (canPreview) group.push({ id: 'view', label: 'Копия кабинета' })
      group.push({ id: 'apps', label: 'Заявки' })
      group.push({ id: 'keys', label: 'Ключи' })
    }
    return { staff, group }
  }, [canConfigure, perms, panelTabs, workTabs, isProjectCreator, onOpenPreview])

  const [office, setOffice] = useState(() => (entry?.office === 'group' ? 'group' : 'staff'))
  const [picked, setPicked] = useState(() => ({
    staff: entry?.office === 'staff' ? entry.slice || null : null,
    group: entry?.office === 'group' ? entry.slice || null : null,
  }))
  const [workTab, setWorkTab] = useState(null)

  useEffect(() => {
    if (!entry?.office) return
    setOffice(entry.office)
    setPicked((prev) => ({ ...prev, [entry.office]: entry.slice || null }))
  }, [entry])

  const both = offices.staff.length > 0 && offices.group.length > 0
  const activeOffice = offices[office]?.length ? office : (offices.staff.length ? 'staff' : 'group')
  const pool = offices[activeOffice] || []
  const activeId = pool.some((item) => item.id === picked[activeOffice]) ? picked[activeOffice] : pool[0]?.id
  const activeWork = workTab && workTabs.some((item) => item.id === workTab) ? workTab : workTabs[0]?.id
  const pick = (id) => setPicked((prev) => ({ ...prev, [activeOffice]: id }))
  const onStaff = activeOffice === 'staff'
  const onGroup = activeOffice === 'group'

  return (
    <section className="panel-security staff-desk">
      <header className="sec-header">
        <h2 className="sec-title">Стафф</h2>
        <p className="sec-subtitle">
          {both
            ? 'Выберите, чью панель настраиваете: сотрудников проекта или администраторов групп'
            : 'Доступ, заявки, ключи, люди и выплаты команды проекта'}
        </p>
      </header>

      {both && (
        <div className="staff-offices" role="tablist" aria-label="Чью панель настраиваем">
          {OFFICES.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={activeOffice === item.id}
              className={`staff-office-btn${activeOffice === item.id ? ' is-on' : ''}`}
              onClick={() => setOffice(item.id)}
            >
              <strong>{item.title}</strong>
              <span>{item.detail}</span>
            </button>
          ))}
        </div>
      )}

      {pool.length > 0 && (
        <nav className="sec-tabs staff-office-tabs" aria-label={onGroup ? 'Администраторы' : 'Сотрудники'}>
          {pool.map((item) => (
            <button
              key={`${activeOffice}-${item.id}`}
              type="button"
              className={`sec-tab${activeId === item.id ? ' sec-tab-active' : ''}`}
              aria-current={activeId === item.id ? 'page' : undefined}
              onClick={() => pick(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      )}

      <div className="staff-desk-main">
          {onStaff && activeId === 'pay' && (
            <CreatorPay
              showPayroll={perms.has('set_salary')}
              payroll={<PayrollSalariesTab isOwner={isOwner} canPay={perms.has('pay_salary')} myUserId={myUserId} />}
            />
          )}
          {onStaff && activeId === 'access' && (
            <StaffAccessPane isProjectCreator={isProjectCreator} onOpenPreview={onOpenPreview} />
          )}
          {onStaff && activeId === 'view' && <StaffPreviewPane onOpen={onOpenPreview} />}
          {onStaff && activeId === 'apps' && <ApplicationsTab onOpenUser={onOpenUser} />}
          {onStaff && activeId === 'keys' && <InvitesTab isProjectCreator={isProjectCreator} scope="staff" myUserId={myUserId} />}
          {onStaff && activeId === 'stats' && <StatDesk />}
          {onStaff && activeId === 'work' && (
            <>
              <nav className="sec-tabs staff-work-tabs" aria-label="Команда">
                {workTabs.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`sec-tab${activeWork === item.id ? ' sec-tab-active' : ''}`}
                    onClick={() => setWorkTab(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>
              {activeWork === 'deeds' && <DeedPay isProjectCreator={isProjectCreator} />}
              {activeWork === 'members' && <MembersTab canAssignRoles={perms.has('assign_roles')} isOwner={isOwner} myUserId={myUserId} canManageStaff={perms.has('manage_staff')} isProjectCreator={isProjectCreator} />}
              {activeWork === 'salaries' && (
                <PayrollSalariesTab isOwner={isOwner} canPay={perms.has('pay_salary')} myUserId={myUserId} />
              )}
              {activeWork === 'bonuses' && <PayrollBonusesTab isOwner={isOwner} canPay={perms.has('pay_salary')} />}
              {activeWork === 'ledger' && <LedgerTab isProjectCreator={isProjectCreator} />}
              {activeWork === 'payoutsettings' && <PayrollSettingsTab />}
              {activeWork === 'leaderboard' && <LeaderboardTab />}
              {activeWork === 'shifts' && <ShiftsTab />}
              {activeWork === 'complaints' && <ComplaintsTab />}
              {activeWork === 'questions' && <QuestionsTab isOwner={isOwner} />}
              {activeWork === 'mysalary' && <PayrollMySalaryTab />}
              {activeWork === 'mycomplaints' && <MyComplaintsTab />}
            </>
          )}

          {onGroup && activeId === 'groups' && <OfficialGroupsPane />}
          {onGroup && activeId === 'posts' && (
            <div className="staff-posts">
              <RightsSection embedded office="group" onPreview={onOpenPreview} />
            </div>
          )}
          {onGroup && activeId === 'view' && <GroupPreviewPane onOpen={onOpenPreview} />}
          {onGroup && activeId === 'apps' && <GroupApplicationsPane onOpenUser={onOpenUser} />}
          {onGroup && activeId === 'keys' && <InvitesTab isProjectCreator={isProjectCreator} scope="group" myUserId={myUserId} />}

          {!activeId && <p className="sec-empty">Нет доступных разделов</p>}
      </div>
    </section>
  )
}
