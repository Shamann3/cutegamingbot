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
  SALARY_PAYOUT_OPTIONS,
  StatusBadge,
  draftTotal,
  nameOf,
  payoutLabel,
  roleLabel,
} from './shared'

function todayIso() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

export default function PayrollSalariesTab({ isOwner, canPay = false }) {
  const [periodType, setPeriodType] = useState('week')
  const [rangeFrom, setRangeFrom] = useState('')
  const [rangeTo, setRangeTo] = useState('')
  const [periodStart, setPeriodStart] = useState('')
  const [periodEnd, setPeriodEnd] = useState('')
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
  const isCustom = periodType === 'custom'

  const load = useCallback(async () => {
    if (isCustom && (!rangeFrom || !rangeTo)) {
      setRows([])
      setPeriodLabel('Укажите даты начала и конца')
      return
    }
    setLoading(true)
    try {
      const startArg = isCustom ? rangeFrom : (rangeFrom || null)
      const endArg = isCustom ? rangeTo : null
      const data = await fetchStaffSalaries(periodType, startArg, endArg)
      setPeriodLabel(data.periodLabel || '')
      setPeriodStart(data.periodStart || '')
      setPeriodEnd(data.periodEnd || '')
      if (!isCustom && data.periodStart) {
        setRangeFrom(data.periodStart)
        if (data.periodEnd) setRangeTo(data.periodEnd)
      }
      const items = data.items || []
      setRows(items)
      const seeded = {}
      for (const m of items) {
        const s = m.salary
        seeded[m.userId] = {
          amount: s ? String(s.amount ?? s.baseAmount ?? '') : '',
          payoutType: s?.payoutType || m.payoutType || 'kut',
        }
      }
      setDrafts(seeded)
      const ap = await fetchSalaryAppeals()
      setAppeals(ap.items || [])
    } catch (err) {
      setRows([])
      setPeriodLabel(err?.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }, [periodType, rangeFrom, rangeTo, isCustom])

  useEffect(() => { load() }, [load])

  const setField = (userId, field, value) =>
    setDrafts((d) => ({ ...d, [userId]: { ...(d[userId] || {}), [field]: value } }))

  const handleSet = async (userId) => {
    const dft = drafts[userId] || {}
    const amount = Number.parseInt(dft.amount, 10)
    if (!Number.isFinite(amount) || amount < 0) {
      alert('Введите сумму')
      return
    }
    if (isCustom && (!rangeFrom || !rangeTo)) {
      alert('Укажите период: с какого и по какой день')
      return
    }
    setBusy(`set-${userId}`)
    try {
      await setStaffSalary({
        userId,
        baseAmount: amount,
        coefficient: 1,
        bonus: 0,
        bonusReason: '',
        penalty: 0,
        penaltyReason: '',
        payoutType: dft.payoutType || 'kut',
        periodType,
        periodStart: isCustom ? rangeFrom : (periodStart || rangeFrom || undefined),
        periodEnd: isCustom ? rangeTo : (periodEnd || undefined),
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
      <header className="payroll-header">
        <div>
          <h3 className="payroll-title">Зарплаты</h3>
          <p className="payroll-sub">
            {periodLabel || 'Период'}
            <span className="payroll-dot">·</span>
            выставить
            <span className="payroll-arrow">→</span>
            одобрить
            <span className="payroll-arrow">→</span>
            выплатить
          </p>
        </div>
        <div className="payroll-summary" aria-label="Сводка">
          <span><b>{pendingCount}</b> ждут</span>
          <span><b>{unpaidCount}</b> к выплате</span>
          <span><b>{notSetCount}</b> без суммы</span>
        </div>
      </header>

      <div className="payroll-toolbar">
        <div className="payroll-periods" role="tablist" aria-label="Период">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              role="tab"
              aria-selected={periodType === opt.value}
              className={`payroll-period${periodType === opt.value ? ' is-active' : ''}`}
              onClick={() => {
                setPeriodType(opt.value)
                if (opt.value === 'custom') {
                  const t = todayIso()
                  setRangeFrom((v) => v || t)
                  setRangeTo((v) => v || t)
                } else {
                  setRangeFrom('')
                  setRangeTo('')
                }
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <label className="payroll-date-field">
          <span>{isCustom ? 'С' : 'Дата'}</span>
          <input
            className="sec-input payroll-date"
            type="date"
            value={rangeFrom || periodStart || ''}
            onChange={(e) => setRangeFrom(e.target.value)}
            title={isCustom ? 'Начало периода' : 'Дата внутри периода'}
          />
        </label>
        {(isCustom || periodEnd) && (
          <label className="payroll-date-field">
            <span>По</span>
            <input
              className="sec-input payroll-date"
              type="date"
              value={isCustom ? rangeTo : (rangeTo || periodEnd || '')}
              onChange={(e) => setRangeTo(e.target.value)}
              disabled={!isCustom}
              title="Конец периода"
            />
          </label>
        )}

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
            Напомнить
          </button>
        )}
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="payroll-list">
        {rows.map((m) => {
          const s = m.salary
          const dft = drafts[m.userId] || {}
          const locked = s && s.status === 'paid'
          const total = draftTotal(dft)
          const savedType = s?.payoutType || dft.payoutType || 'kut'

          return (
            <article key={m.userId} className={`payroll-row${locked ? ' is-locked' : ''}`}>
              <div className="payroll-row-main">
                <div className="payroll-row-who">
                  <div className="payroll-row-name">{nameOf(m)}</div>
                  <div className="payroll-row-meta">
                    <span>{roleLabel(m.role)}</span>
                    {s ? <StatusBadge status={s.status} /> : <span className="payroll-status">не выставлено</span>}
                    {s?.status === 'partially_paid' && (
                      <span className="payroll-muted">{s.paidAmount}/{s.amount}</span>
                    )}
                    {s && <span className="payroll-muted">{payoutLabel(savedType)}</span>}
                  </div>
                </div>
                <div className="payroll-row-amount" aria-label="Сумма">
                  {total > 0 ? total : '—'}
                </div>
              </div>

              {!locked && (
                <div className="payroll-row-edit">
                  <label className="payroll-field">
                    <span>Сумма</span>
                    <input
                      className="sec-input"
                      type="number"
                      min="0"
                      inputMode="numeric"
                      placeholder="0"
                      value={dft.amount ?? ''}
                      onChange={(e) => setField(m.userId, 'amount', e.target.value)}
                    />
                  </label>
                  <label className="payroll-field">
                    <span>Способ</span>
                    <AdminSelect
                      value={dft.payoutType || 'kut'}
                      onChange={(v) => setField(m.userId, 'payoutType', v)}
                      options={SALARY_PAYOUT_OPTIONS}
                    />
                  </label>
                </div>
              )}

              <footer className="payroll-row-actions">
                {!locked && (
                  <button
                    type="button"
                    className="sec-btn sec-btn-sm"
                    disabled={busy === `set-${m.userId}`}
                    onClick={() => handleSet(m.userId)}
                  >
                    {s ? 'Сохранить' : 'Выставить'}
                  </button>
                )}
                {isOwner && s?.status === 'pending_approval' && (
                  <button
                    type="button"
                    className="sec-btn sec-btn-sm"
                    disabled={busy === `appr-${s.salaryId}`}
                    onClick={() => handleAction(approveStaffSalary, s.salaryId, `appr-${s.salaryId}`)}
                  >
                    Одобрить
                  </button>
                )}
                {canPay && s && ['approved', 'partially_paid'].includes(s.status) && (
                  <button
                    type="button"
                    className="sec-btn sec-btn-sm sec-btn-success"
                    disabled={busy === `pay-${s.salaryId}`}
                    onClick={() => setPayFor(m)}
                  >
                    {s.status === 'partially_paid' ? 'Доплатить' : 'Выплатить'}
                  </button>
                )}
                {s && s.status !== 'paid' && s.status !== 'cancelled' && (
                  <button
                    type="button"
                    className="sec-btn sec-btn-sm sec-btn-ghost"
                    disabled={busy === `cancel-${s.salaryId}`}
                    onClick={() => {
                      if (confirm('Снять начисление?')) {
                        handleAction(cancelStaffSalary, s.salaryId, `cancel-${s.salaryId}`)
                      }
                    }}
                  >
                    Снять
                  </button>
                )}
              </footer>
            </article>
          )
        })}
      </div>

      {!loading && rows.length === 0 && (
        <p className="sec-empty">
          {isCustom && (!rangeFrom || !rangeTo)
            ? 'Выберите даты «С» и «По»'
            : 'Нет сотрудников для начисления'}
        </p>
      )}

      {appeals.length > 0 && (
        <section className="payroll-appeals">
          <h4 className="payroll-section-title">Апелляции <span className="payroll-muted">{appeals.length}</span></h4>
          {appeals.map((a) => (
            <div key={a.appealId} className="payroll-appeal-row">
              <div>
                <strong>{nameOf(a)}</strong>
                <span className="payroll-muted"> · {a.amount}</span>
                <p className="payroll-reason">{a.reason}</p>
              </div>
              <button
                type="button"
                className="sec-btn sec-btn-ghost sec-btn-sm"
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
                }}
              >
                Рассмотреть
              </button>
            </div>
          ))}
        </section>
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
