import { useEffect, useState } from 'react'
import AdminSelect from '../../components/AdminSelect'
import {
  fetchContractTemplates,
  fetchFragmentHealth,
  renderContract,
  sendContract,
} from '../../lib/adminClient'
import { payoutLabel } from './payroll/shared'

function nameOf(item) {
  if (!item) return '—'
  return item.firstName || (item.username ? `@${item.username}` : `ID ${item.userId}`)
}

/** Модалка выплаты: Stars (метод/username/Fragment) + договоры для crypto/card */
export default function PayrollPayModal({ member, busy, onClose, onSubmit }) {
  const s = member.salary
  const remaining = Math.max(0, (s.amount || 0) - (s.paidAmount || 0))
  const payoutType = s?.payoutType || member.payoutType || 'other'
  const [amount, setAmount] = useState(String(remaining))
  const [kind, setKind] = useState('payment')
  const [txid, setTxid] = useState('')
  const [proof, setProof] = useState('')
  const [starsMethod, setStarsMethod] = useState('auto')
  const [starsUsername, setStarsUsername] = useState(member.starsUsername || member.username || '')
  const [frag, setFrag] = useState(null)
  const [templates, setTemplates] = useState([])
  const [tplId, setTplId] = useState('')
  const [contractText, setContractText] = useState('')
  const [cBusy, setCBusy] = useState(false)

  useEffect(() => {
    if (payoutType === 'stars') {
      fetchFragmentHealth().then(setFrag).catch(() => setFrag(null))
    }
    if (payoutType === 'crypto' || payoutType === 'card') {
      fetchContractTemplates()
        .then((d) => {
          const items = (d.items || []).filter(
            (t) => t.enabled && (!t.payoutType || t.payoutType === payoutType || t.payoutType === 'other'),
          )
          setTemplates(items)
          if (items[0]) setTplId(String(items[0].id))
        })
        .catch(() => setTemplates([]))
    }
  }, [payoutType])

  const fragDead = frag && (frag.ok === false || (frag.ok === true && frag.ton != null && frag.ton <= 0))
  const fragUnknown = !frag || frag.ok == null || frag.stale

  const doRender = async () => {
    if (!tplId) return
    setCBusy(true)
    try {
      const r = await renderContract({
        templateId: Number(tplId),
        userId: member.userId,
        amount: Number.parseInt(amount, 10) || remaining,
        payoutType,
        periodLabel: s?.periodStart || '',
      })
      setContractText(r.text || '')
    } catch (e) {
      alert(e?.message || 'Ошибка')
    } finally {
      setCBusy(false)
    }
  }

  const doSendContract = async () => {
    if (!tplId) return
    setCBusy(true)
    try {
      await sendContract({
        templateId: Number(tplId),
        userId: member.userId,
        amount: Number.parseInt(amount, 10) || remaining,
        payoutType,
        periodLabel: s?.periodStart || '',
      })
      alert('Договор отправлен сотруднику в бот')
    } catch (e) {
      alert(e?.message || 'Ошибка')
    } finally {
      setCBusy(false)
    }
  }

  return (
    <div className="admin-modal-backdrop" role="presentation" onClick={() => !busy && onClose()}>
      <div className="admin-modal payroll-pay-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h3 className="admin-modal-title">Выплата</h3>
        <p className="admin-modal-desc">
          {nameOf(member)}
          <span className="payroll-dot">·</span>
          {payoutLabel(payoutType)}
          <span className="payroll-dot">·</span>
          остаток {remaining}
          {s.paidAmount > 0 ? ` из ${s.amount}` : ''}
        </p>

        <label className="admin-modal-field">
          <span>Сумма</span>
          <input
            className="sec-input"
            type="number"
            min="1"
            max={remaining}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            disabled={busy}
          />
        </label>
        <label className="admin-modal-field">
          <span>Тип</span>
          <AdminSelect
            value={kind}
            onChange={setKind}
            options={[
              { value: 'payment', label: 'Выплата' },
              { value: 'advance', label: 'Аванс' },
            ]}
          />
        </label>

        {payoutType === 'stars' && (
          <div className="payroll-pay-block">
            <p className="payroll-hint">
              {fragDead && `Fragment недоступен${frag?.error ? `: ${frag.error}` : ''}`}
              {!fragDead && frag?.ok && `Fragment OK${frag.ton != null ? ` · ${Number(frag.ton).toFixed(2)} TON` : ''}`}
              {fragUnknown && !fragDead && 'Fragment: нет свежих данных'}
            </p>
            <label className="admin-modal-field">
              <span>Метод</span>
              <AdminSelect
                value={starsMethod}
                onChange={setStarsMethod}
                options={[
                  { value: 'auto', label: 'Auto' },
                  { value: 'fragment', label: fragDead ? 'Fragment (нет)' : 'Fragment' },
                  { value: 'userbot', label: 'Userbot' },
                ]}
              />
            </label>
            {fragDead && starsMethod === 'fragment' && (
              <p className="payroll-hint payroll-hint-warn">Fragment не работает — Auto или Userbot</p>
            )}
            <label className="admin-modal-field">
              <span>Username</span>
              <input
                className="sec-input"
                value={starsUsername}
                onChange={(e) => setStarsUsername(e.target.value)}
                disabled={busy}
                placeholder="@username"
              />
            </label>
          </div>
        )}

        {(payoutType === 'crypto' || payoutType === 'card' || payoutType === 'other') && (
          <div className="payroll-pay-block">
            <label className="admin-modal-field">
              <span>TXID</span>
              <input className="sec-input" value={txid} onChange={(e) => setTxid(e.target.value)} disabled={busy} />
            </label>
            <label className="admin-modal-field">
              <span>Пруф</span>
              <input className="sec-input" value={proof} onChange={(e) => setProof(e.target.value)} disabled={busy} />
            </label>
          </div>
        )}

        {(payoutType === 'crypto' || payoutType === 'card') && (
          <div className="payroll-pay-block">
            <p className="payroll-my-label">Договор</p>
            <AdminSelect
              value={tplId}
              onChange={setTplId}
              options={[
                { value: '', label: '— шаблон —' },
                ...templates.map((t) => ({ value: String(t.id), label: t.name })),
              ]}
            />
            <div className="payroll-row-actions" style={{ marginTop: 8 }}>
              <button type="button" className="sec-btn sec-btn-sm" disabled={cBusy || !tplId} onClick={doRender}>
                Показать
              </button>
              <button
                type="button"
                className="sec-btn sec-btn-sm"
                disabled={cBusy || !contractText}
                onClick={() => { navigator.clipboard?.writeText(contractText); alert('Скопировано') }}
              >
                Копировать
              </button>
              <button type="button" className="sec-btn sec-btn-sm" disabled={cBusy || !tplId} onClick={doSendContract}>
                В бот
              </button>
            </div>
            {contractText && (
              <textarea className="sec-input payroll-textarea" rows={5} readOnly value={contractText} />
            )}
          </div>
        )}

        <div className="admin-modal-actions">
          <button type="button" className="panel-users-btn" disabled={busy} onClick={onClose}>Отмена</button>
          <button
            type="button"
            className="panel-users-btn panel-users-btn-primary"
            disabled={busy || (payoutType === 'stars' && starsMethod === 'fragment' && fragDead)}
            onClick={() => onSubmit({
              amount: Number.parseInt(amount, 10) || null,
              kind,
              txid: txid.trim(),
              proof: proof.trim(),
              starsMethod: payoutType === 'stars' ? starsMethod : null,
              starsUsername: payoutType === 'stars' ? starsUsername.trim() : null,
            })}
          >
            {busy ? '…' : (payoutType === 'stars' ? 'Заявка Stars' : 'Провести')}
          </button>
        </div>
      </div>
    </div>
  )
}
