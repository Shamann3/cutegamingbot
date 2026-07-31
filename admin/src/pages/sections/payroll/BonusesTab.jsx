import { useCallback, useEffect, useState } from 'react'
import AdminSelect from '../../../components/AdminSelect'
import {
  approveStaffBonus,
  cancelStaffBonus,
  createStaffBonus,
  fetchStaffBonuses,
  fetchStaffMembers,
  payStaffBonus,
} from '../../../lib/adminClient'
import { SALARY_PAYOUT_OPTIONS, StatusBadge, nameOf, roleLabel } from './shared'

export default function PayrollBonusesTab({ isOwner, canPay = false }) {
  const [items, setItems] = useState([])
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(null)
  const [form, setForm] = useState({ userId: '', amount: '', reason: '', payoutType: 'kut' })
  const [payFor, setPayFor] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [b, m] = await Promise.all([fetchStaffBonuses(), fetchStaffMembers()])
      setItems(b.items || [])
      setMembers((m.items || []).filter((x) => x.role !== 'owner' && x.status === 'active'))
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    const userId = Number.parseInt(form.userId, 10)
    const amount = Number.parseInt(form.amount, 10)
    if (!userId || !amount) {
      alert('Укажите сотрудника и сумму')
      return
    }
    setBusy('create')
    try {
      await createStaffBonus({
        userId,
        amount,
        reason: form.reason.trim(),
        payoutType: form.payoutType,
      })
      setForm({ userId: '', amount: '', reason: '', payoutType: 'kut' })
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
          <h3 className="payroll-title">Премии</h3>
          <p className="payroll-sub">Разовые выплаты вне оклада</p>
        </div>
      </header>

      <div className="payroll-create">
        <div className="payroll-fields payroll-fields-create">
          <label className="payroll-field">Сотрудник
            <AdminSelect
              value={form.userId}
              onChange={(v) => setForm((f) => ({ ...f, userId: v }))}
              options={[
                { value: '', label: '— выберите —' },
                ...members.map((m) => ({ value: String(m.userId), label: `${nameOf(m)} · ${roleLabel(m.role)}` })),
              ]}
            />
          </label>
          <label className="payroll-field">Сумма
            <input className="sec-input" type="number" min="1" value={form.amount}
              onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} />
          </label>
          <label className="payroll-field">Способ
            <AdminSelect value={form.payoutType}
              onChange={(v) => setForm((f) => ({ ...f, payoutType: v }))}
              options={SALARY_PAYOUT_OPTIONS} />
          </label>
        </div>
        <input className="sec-input" placeholder="Причина" value={form.reason}
          onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))} />
        <div className="payroll-toolbar">
          <button type="button" className="sec-btn sec-btn-sm sec-btn-success" disabled={busy === 'create'} onClick={handleCreate}>
            Выставить
          </button>
          <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={load}>Обновить</button>
        </div>
      </div>

      {loading && <p className="sec-loading">Загрузка…</p>}

      <div className="payroll-list">
        {items.map((b) => (
          <article key={b.bonusId} className="payroll-row">
            <div className="payroll-row-main">
              <div className="payroll-row-who">
                <div className="payroll-row-name">{nameOf(b)}</div>
                <div className="payroll-row-meta">
                  {b.role && <span>{roleLabel(b.role)}</span>}
                  <StatusBadge status={b.status} />
                  <span className="payroll-muted">{SALARY_PAYOUT_OPTIONS.find((o) => o.value === b.payoutType)?.label || b.payoutType}</span>
                </div>
              </div>
              <div className="payroll-row-amount">{b.amount}</div>
            </div>
            {b.reason && <p className="payroll-reason">{b.reason}</p>}
            <footer className="payroll-row-actions">
              {isOwner && b.status === 'pending_approval' && (
                <button type="button" className="sec-btn sec-btn-sm" disabled={busy === `appr-${b.bonusId}`}
                  onClick={async () => {
                    setBusy(`appr-${b.bonusId}`)
                    try { await approveStaffBonus(b.bonusId); await load() }
                    catch (e) { alert(e?.message || 'Ошибка') }
                    finally { setBusy(null) }
                  }}>Одобрить</button>
              )}
              {canPay && ['approved', 'partially_paid'].includes(b.status) && (
                <button type="button" className="sec-btn sec-btn-sm sec-btn-success" onClick={() => setPayFor(b)}>
                  Выплатить
                </button>
              )}
              {b.status !== 'paid' && b.status !== 'cancelled' && (
                <button type="button" className="sec-btn sec-btn-sm sec-btn-ghost" disabled={busy === `cancel-${b.bonusId}`}
                  onClick={async () => {
                    if (!confirm('Отменить премию?')) return
                    setBusy(`cancel-${b.bonusId}`)
                    try { await cancelStaffBonus(b.bonusId); await load() }
                    catch (e) { alert(e?.message || 'Ошибка') }
                    finally { setBusy(null) }
                  }}>Снять</button>
              )}
            </footer>
          </article>
        ))}
      </div>

      {!loading && items.length === 0 && <p className="sec-empty">Премий пока нет</p>}

      {payFor && (
        <div className="admin-modal-backdrop" role="presentation" onClick={() => setPayFor(null)}>
          <div className="admin-modal" role="dialog" onClick={(e) => e.stopPropagation()}>
            <h3 className="admin-modal-title">Выплата премии — {nameOf(payFor)}</h3>
            <p className="admin-modal-desc">{payFor.amount} · {payFor.payoutType}</p>
            <div className="admin-modal-actions">
              <button type="button" className="panel-users-btn" data-modal-cancel onClick={() => setPayFor(null)}>Отмена</button>
              <button type="button" className="panel-users-btn panel-users-btn-primary" data-modal-confirm disabled={!!busy}
                onClick={async () => {
                  setBusy(`pay-${payFor.bonusId}`)
                  try {
                    await payStaffBonus(payFor.bonusId, { method: payFor.payoutType })
                    setPayFor(null)
                    await load()
                  } catch (e) {
                    alert(e?.message || 'Ошибка')
                  } finally {
                    setBusy(null)
                  }
                }}>Провести</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
