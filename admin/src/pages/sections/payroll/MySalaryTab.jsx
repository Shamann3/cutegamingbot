import { useCallback, useEffect, useState } from 'react'
import AdminSelect from '../../../components/AdminSelect'
import CountUp from '../../../components/CountUp'
import {
  appealMySalary,
  claimKutBonus,
  claimKutSalary,
  fetchMyPayoutProfile,
  fetchMySalary,
  updateMyPayoutProfile,
} from '../../../lib/adminClient'
import { SALARY_PAYOUT_OPTIONS, StatusBadge, fmtDate } from './shared'

export default function PayrollMySalaryTab() {
  const [items, setItems] = useState([])
  const [bonuses, setBonuses] = useState([])
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [appealFor, setAppealFor] = useState(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [data, prof] = await Promise.all([
        fetchMySalary(),
        fetchMyPayoutProfile().catch(() => null),
      ])
      setItems(data.items || [])
      setBonuses(data.bonuses || [])
      setProfile(prof)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const current = items[0]
  const claimableBonus = bonuses.find(
    (b) => ['approved', 'partially_paid'].includes(b.status)
      && b.payoutType === 'kut'
      && b.amount > (b.paidAmount || 0),
  )
  const remainingKut = current
    ? Math.max(0, (current.amount || 0) - (current.paidAmount || 0))
    : 0

  const saveProfile = async () => {
    if (!profile) return
    setBusy(true)
    try {
      const r = await updateMyPayoutProfile({
        payoutType: profile.payoutType,
        payoutDetails: profile.payoutDetails,
        starsUsername: profile.starsUsername,
        cryptoNetwork: profile.cryptoNetwork,
        cryptoAddress: profile.cryptoAddress,
        cardBank: profile.cardBank,
        cardNumber: profile.cardNumber,
        cardHolder: profile.cardHolder,
        cardSbpPhone: profile.cardSbpPhone,
      })
      setProfile(r)
      alert('Реквизиты сохранены')
    } catch (err) {
      alert(err?.message || 'Ошибка')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="sec-tab-body payroll-tab">
      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="payroll-my-grid">
        {current ? (
          <div className="payroll-my-card">
            <p className="staff-salary-card-label">
              Зарплата
              {current.periodType
                ? ` · ${current.periodType}: ${current.periodStart || current.weekStart}`
                : ''}
            </p>
            <p className="staff-salary-card-amount"><CountUp value={current.amount} /></p>
            <StatusBadge status={current.status} />

            <div className="staff-payslip-breakdown">
              <div><span>Ставка</span><b>{current.baseAmount}</b></div>
              <div><span>Коэффициент</span><b>×{current.coefficient}</b></div>
              {current.bonus > 0 && (
                <div><span>Бонус{current.bonusReason ? ` (${current.bonusReason})` : ''}</span><b>+{current.bonus}</b></div>
              )}
              {current.penalty > 0 && (
                <div><span>Штраф{current.penaltyReason ? ` (${current.penaltyReason})` : ''}</span><b>−{current.penalty}</b></div>
              )}
              <div className="staff-payslip-breakdown-total"><span>К выплате</span><b>{current.amount}</b></div>
            </div>

            {current.status === 'paid' && current.txid === 'kut-self-claim' && (
              <p className="staff-hint">Получено в kut на игровой баланс</p>
            )}
            {current.status === 'paid' && current.txid && current.txid !== 'kut-self-claim' && (
              <p className="staff-hint">Выплачено. TXID: {current.txid}</p>
            )}

            {['approved', 'partially_paid'].includes(current.status) && current.payoutType === 'kut' && remainingKut > 0 && (
              <button type="button" className="sec-btn sec-btn-success" disabled={busy}
                onClick={async () => {
                  setBusy(true)
                  try {
                    const r = await claimKutSalary()
                    await load()
                    alert(`Получено ${r.amount} kut`)
                  } catch (err) {
                    alert(err?.message || 'Ошибка')
                  } finally {
                    setBusy(false)
                  }
                }}>
                Получить {remainingKut} kut
              </button>
            )}

            {current.status !== 'paid' && current.status !== 'cancelled' && !current.appealId && (
              <button type="button" className="sec-btn sec-btn-ghost" disabled={busy}
                onClick={() => setAppealFor(current)}>
                Подать апелляцию
              </button>
            )}
            {current.appealStatus === 'open' && (
              <p className="staff-hint">Апелляция ожидает рассмотрения</p>
            )}
          </div>
        ) : (
          !loading && <p className="sec-empty">Зарплата ещё не назначена</p>
        )}

        {claimableBonus && (
          <div className="payroll-my-card">
            <p className="staff-salary-card-label">Премия в kut</p>
            <p className="staff-salary-card-amount">
              <CountUp value={claimableBonus.amount - (claimableBonus.paidAmount || 0)} />
            </p>
            {claimableBonus.reason && <p className="payroll-reason">{claimableBonus.reason}</p>}
            <button type="button" className="sec-btn sec-btn-success" disabled={busy}
              onClick={async () => {
                setBusy(true)
                try {
                  const r = await claimKutBonus()
                  await load()
                  alert(`Премия ${r.amount} kut получена`)
                } catch (e) {
                  alert(e?.message || 'Ошибка')
                } finally {
                  setBusy(false)
                }
              }}>
              Получить премию
            </button>
          </div>
        )}

        {profile && (
          <div className="payroll-my-card payroll-my-card-wide">
            <p className="staff-salary-card-label">Реквизиты для выплат</p>
            <label className="payroll-payout-label">Способ
              <AdminSelect value={profile.payoutType || 'other'}
                onChange={(v) => setProfile((p) => ({ ...p, payoutType: v }))}
                options={SALARY_PAYOUT_OPTIONS} />
            </label>
            <div className="payroll-fields">
              <label>Stars @username
                <input className="sec-input" value={profile.starsUsername || ''}
                  onChange={(e) => setProfile((p) => ({ ...p, starsUsername: e.target.value }))} />
              </label>
              <label>Сеть крипты
                <input className="sec-input" value={profile.cryptoNetwork || ''}
                  onChange={(e) => setProfile((p) => ({ ...p, cryptoNetwork: e.target.value }))} />
              </label>
              <label>Адрес
                <input className="sec-input" value={profile.cryptoAddress || ''}
                  onChange={(e) => setProfile((p) => ({ ...p, cryptoAddress: e.target.value }))} />
              </label>
              <label>Банк
                <input className="sec-input" value={profile.cardBank || ''}
                  onChange={(e) => setProfile((p) => ({ ...p, cardBank: e.target.value }))} />
              </label>
              <label>Карта
                <input className="sec-input" value={profile.cardNumber || ''}
                  onChange={(e) => setProfile((p) => ({ ...p, cardNumber: e.target.value }))} />
              </label>
              <label>ФИО
                <input className="sec-input" value={profile.cardHolder || ''}
                  onChange={(e) => setProfile((p) => ({ ...p, cardHolder: e.target.value }))} />
              </label>
              <label>СБП телефон
                <input className="sec-input" value={profile.cardSbpPhone || ''}
                  onChange={(e) => setProfile((p) => ({ ...p, cardSbpPhone: e.target.value }))} />
              </label>
            </div>
            <button type="button" className="sec-btn sec-btn-sm" disabled={busy} onClick={saveProfile}>
              Сохранить реквизиты
            </button>
          </div>
        )}
      </div>

      {items.length > 1 && (
        <div className="payroll-history">
          <h3 className="sec-ipban-section-title">История</h3>
          {items.slice(1).map((s) => (
            <div key={s.salaryId} className="payroll-history-row">
              <span>{fmtDate(s.periodStart || s.weekStart)}</span>
              <StatusBadge status={s.status} />
              <b>{s.amount}</b>
            </div>
          ))}
        </div>
      )}

      {appealFor && (
        <div className="admin-modal-backdrop" role="presentation" onClick={() => !busy && setAppealFor(null)}>
          <div className="admin-modal" role="dialog" onClick={(e) => e.stopPropagation()}>
            <h3 className="admin-modal-title">Апелляция</h3>
            <p className="admin-modal-desc">Сумма: {appealFor.amount}</p>
            <textarea className="admin-modal-textarea" rows={4} value={reason}
              onChange={(e) => setReason(e.target.value)} placeholder="Почему не согласны"
              disabled={busy} />
            <div className="admin-modal-actions">
              <button type="button" className="panel-users-btn" disabled={busy} onClick={() => setAppealFor(null)}>Отмена</button>
              <button type="button" className="panel-users-btn panel-users-btn-primary"
                disabled={busy || !reason.trim()}
                onClick={async () => {
                  setBusy(true)
                  try {
                    await appealMySalary(appealFor.salaryId, reason.trim())
                    setAppealFor(null)
                    setReason('')
                    await load()
                  } catch (err) {
                    alert(err?.message || 'Ошибка')
                  } finally {
                    setBusy(false)
                  }
                }}>
                Отправить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
