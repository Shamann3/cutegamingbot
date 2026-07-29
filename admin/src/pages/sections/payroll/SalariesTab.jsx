import { useCallback, useEffect, useState } from 'react'
import AdminSelect from '../../../components/AdminSelect'
import {
  approveStaffSalary,
  cancelStaffSalary,
  fetchSalaryAppeals,
  fetchStaffSalaries,
  payStaffSalary,
  resolveSalaryAppeal,
  sendSalaryReminder,
  setStaffSalary,
} from '../../../lib/adminClient'
import PayrollPayModal from '../PayrollPayModal'
import {
  PERIOD_OPTIONS,
  ROLE_BADGE_COLOR,
  SALARY_PAYOUT_OPTIONS,
  StatusBadge,
  draftTotal,
  nameOf,
  roleLabel,
} from './shared'

export default function PayrollSalariesTab({ isOwner, canPay = false }) {
  const [periodType, setPeriodType] = useState('week')
  const [anchorDate, setAnchorDate] = useState('')
  const [periodStart, setPeriodStart] = useState('')
  const [periodLabel, setPeriodLabel] = useState('')
  const [rows, setRows] = useState([])
  const [appeals, setAppeals] = useState([])
  const [drafts, setDrafts] = useState({})
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(null)
  const [payFor, setPayFor] = useState(null)

  const pendingCount = rows.filter((m) => m.salary?.status === 'pending_approval').length
  const unpaidCount = rows.filter((m) => ['approved', 'partially_paid'].includes(m.salary?.status)).length
  const notSetCount = rows.filter((m) => !m.salary).length

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchStaffSalaries(periodType, anchorDate || null)
      setPeriodLabel(data.periodLabel || '')
      setPeriodStart(data.periodStart || '')
      const items = data.items || []
      setRows(items)
      const seeded = {}
      for (const m of items) {
        const s = m.salary
        seeded[m.userId] = {
          base: s ? String(s.baseAmount) : '',
          coefficient: s ? String(s.coefficient) : '1',
          bonus: s && s.bonus ? String(s.bonus) : '',
          bonusReason: s?.bonusReason || '',
          penalty: s && s.penalty ? String(s.penalty) : '',
          penaltyReason: s?.penaltyReason || '',
          payoutType: s?.payoutType || m.payoutType || 'kut',
        }
      }
      setDrafts(seeded)
      const ap = await fetchSalaryAppeals()
      setAppeals(ap.items || [])
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [periodType, anchorDate])

  useEffect(() => { load() }, [load])

  const setField = (userId, field, value) =>
    setDrafts((d) => ({ ...d, [userId]: { ...(d[userId] || {}), [field]: value } }))

  const handleSet = async (userId) => {
    const dft = drafts[userId] || {}
    const baseAmount = Number.parseInt(dft.base, 10)
    if (!Number.isFinite(baseAmount) || baseAmount < 0) {
      alert('Введите ставку')
      return
    }
    setBusy(`set-${userId}`)
    try {
      await setStaffSalary({
        userId,
        baseAmount,
        coefficient: Number.parseFloat(dft.coefficient) || 1,
        bonus: Number.parseInt(dft.bonus, 10) || 0,
        bonusReason: (dft.bonusReason || '').trim(),
        penalty: Number.parseInt(dft.penalty, 10) || 0,
        penaltyReason: (dft.penaltyReason || '').trim(),
        payoutType: dft.payoutType || 'kut',
        periodType,
        periodStart: periodStart || anchorDate || undefined,
      })
      await load()
    } catch (err) {
      alert(err?.message || 'Ошибка')
    } finally {
      setBusy(null)
    }
  }

  const handleAction = async (fn, id, key) => {
    setBusy(key)
    try {
      await fn(id)
      await load()
    } catch (err) {
      alert(err?.message || 'Ошибка')
    } finally {
      setBusy(null)
    }
  }

  const submitPay = async (payload) => {
    setBusy(`pay-${payFor.salary.salaryId}`)
    try {
      const r = await payStaffSalary(payFor.salary.salaryId, {
        ...payload,
        method: payFor.salary?.payoutType || payFor.payoutType || null,
      })
      setPayFor(null)
      if (r?.queued) {
        alert(`Заявка Stars: ${r.starPayout?.method || 'auto'} → @${r.starPayout?.starsUsername || '?'}`)
      }
      await load()
    } catch (err) {
      alert(err?.message || 'Ошибка')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="sec-tab-body payroll-tab">
      <div className="payroll-hero">
        <div>
          <h3 className="payroll-hero-title">Зарплаты</h3>
          <p className="payroll-hero-sub">
            Период: <strong>{periodLabel || '—'}</strong>
            {' · '}владелец одобряет → затем «Выплатить»
          </p>
        </div>
        <div className="payroll-hero-stats">
          <span className="payroll-stat payroll-stat-warn">⏳ {pendingCount}</span>
          <span className="payroll-stat payroll-stat-pay">💸 {unpaidCount}</span>
          <span className="payroll-stat">➖ {notSetCount}</span>
        </div>
      </div>

      <div className="payroll-toolbar">
        <AdminSelect
          value={periodType}
          onChange={(v) => { setPeriodType(v); setAnchorDate('') }}
          options={PERIOD_OPTIONS}
        />
        <input
          className="sec-input payroll-date"
          type="date"
          value={anchorDate || periodStart || ''}
          onChange={(e) => setAnchorDate(e.target.value)}
          title="Дата внутри нужного периода"
        />
        <button type="button" className="sec-btn sec-btn-ghost" onClick={load}>Обновить</button>
        {isOwner && (
          <button
            type="button"
            className="sec-btn sec-btn-ghost"
            disabled={busy === 'remind'}
            onClick={async () => {
              setBusy('remind')
              try {
                const r = await sendSalaryReminder()
                alert(r.sent ? 'Напоминание отправлено' : (r.detail || 'Нечего напоминать'))
              } catch (e) {
                alert(e?.message || 'Ошибка')
              } finally {
                setBusy(null)
              }
            }}
          >
            Напомнить владельцам
          </button>
        )}
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="payroll-grid">
        {rows.map((m) => {
          const s = m.salary
          const dft = drafts[m.userId] || {}
          const locked = s && s.status === 'paid'
          const total = draftTotal(dft)
          return (
            <article key={m.userId} className={`payroll-card${locked ? ' payroll-card-locked' : ''}`}>
              <header className="payroll-card-head">
                <div>
                  <div className="payroll-card-name">{nameOf(m)}</div>
                  <div className="payroll-card-meta">
                    <span className="staff-badge" style={{ '--badge-color': ROLE_BADGE_COLOR[m.role] || '#94a3b8' }}>
                      {roleLabel(m.role)}
                    </span>
                    {s && <StatusBadge status={s.status} />}
                    {s?.status === 'partially_paid' && (
                      <span className="payroll-muted">{s.paidAmount}/{s.amount}</span>
                    )}
                  </div>
                </div>
                <div className="payroll-card-total">
                  <span>Итого</span>
                  <b>{total}</b>
                </div>
              </header>

              <div className="payroll-fields">
                <label>Ставка
                  <input className="sec-input" type="number" min="0" disabled={locked}
                    value={dft.base ?? ''} onChange={(e) => setField(m.userId, 'base', e.target.value)} />
                </label>
                <label>Коэф.
                  <input className="sec-input" type="number" min="0" step="0.05" disabled={locked}
                    value={dft.coefficient ?? '1'} onChange={(e) => setField(m.userId, 'coefficient', e.target.value)} />
                </label>
                <label>Бонус
                  <input className="sec-input" type="number" min="0" disabled={locked}
                    value={dft.bonus ?? ''} onChange={(e) => setField(m.userId, 'bonus', e.target.value)} />
                </label>
                <label>Штраф
                  <input className="sec-input" type="number" min="0" disabled={locked}
                    value={dft.penalty ?? ''} onChange={(e) => setField(m.userId, 'penalty', e.target.value)} />
                </label>
              </div>

              <input className="sec-input" placeholder="За что бонус" disabled={locked}
                value={dft.bonusReason ?? ''} onChange={(e) => setField(m.userId, 'bonusReason', e.target.value)} />
              <input className="sec-input" placeholder="За что штраф" disabled={locked}
                value={dft.penaltyReason ?? ''} onChange={(e) => setField(m.userId, 'penaltyReason', e.target.value)} />

              <label className="payroll-payout-label">
                Способ
                <AdminSelect
                  value={dft.payoutType || 'kut'}
                  onChange={(v) => setField(m.userId, 'payoutType', v)}
                  disabled={locked}
                  options={SALARY_PAYOUT_OPTIONS}
                />
              </label>

              <footer className="payroll-card-actions">
                {!locked && (
                  <button type="button" className="sec-btn sec-btn-sm" disabled={busy === `set-${m.userId}`}
                    onClick={() => handleSet(m.userId)}>
                    {s ? 'Сохранить' : 'Выставить'}
                  </button>
                )}
                {isOwner && s?.status === 'pending_approval' && (
                  <button type="button" className="sec-btn sec-btn-sm" disabled={busy === `appr-${s.salaryId}`}
                    onClick={() => handleAction(approveStaffSalary, s.salaryId, `appr-${s.salaryId}`)}>
                    Одобрить
                  </button>
                )}
                {canPay && s && ['approved', 'partially_paid'].includes(s.status) && (
                  <button type="button" className="sec-btn sec-btn-sm sec-btn-success"
                    disabled={busy === `pay-${s.salaryId}`} onClick={() => setPayFor(m)}>
                    {s.status === 'partially_paid' ? 'Доплатить' : 'Выплатить'}
                  </button>
                )}
                {s && s.status !== 'paid' && s.status !== 'cancelled' && (
                  <button type="button" className="sec-btn sec-btn-sm sec-btn-ghost"
                    disabled={busy === `cancel-${s.salaryId}`}
                    onClick={() => {
                      if (confirm('Снять начисление?')) {
                        handleAction(cancelStaffSalary, s.salaryId, `cancel-${s.salaryId}`)
                      }
                    }}>
                    Снять
                  </button>
                )}
              </footer>
            </article>
          )
        })}
      </div>

      {!loading && rows.length === 0 && <p className="sec-empty">Нет сотрудников для начисления</p>}

      {appeals.length > 0 && (
        <div className="payroll-appeals">
          <h3 className="sec-ipban-section-title">Апелляции <span className="sec-count">{appeals.length}</span></h3>
          {appeals.map((a) => (
            <div key={a.appealId} className="payroll-appeal-row">
              <div>
                <strong>{nameOf(a)}</strong>
                <span className="payroll-muted"> · {a.amount}</span>
                <p className="staff-answer-a">{a.reason}</p>
              </div>
              <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm"
                disabled={busy === `appeal-${a.appealId}`}
                onClick={async () => {
                  const resolution = prompt('Решение (необязательно):') ?? ''
                  setBusy(`appeal-${a.appealId}`)
                  try {
                    await resolveSalaryAppeal(a.appealId, resolution)
                    await load()
                  } catch (e) {
                    alert(e?.message || 'Ошибка')
                  } finally {
                    setBusy(null)
                  }
                }}>
                Рассмотреть
              </button>
            </div>
          ))}
        </div>
      )}

      {payFor && (
        <PayrollPayModal
          member={payFor}
          busy={busy === `pay-${payFor.salary.salaryId}`}
          onClose={() => setPayFor(null)}
          onSubmit={submitPay}
        />
      )}
    </div>
  )
}
