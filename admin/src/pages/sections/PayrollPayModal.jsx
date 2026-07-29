import { useEffect, useState } from 'react'
import AdminSelect from '../../../components/AdminSelect'
import {
  fetchContractTemplates,
  fetchFragmentHealth,
  renderContract,
  sendContract,
} from '../../../lib/adminClient'

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
      <div className="admin-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h3 className="admin-modal-title">Выплата — {nameOf(member)}</h3>
        <p className="admin-modal-desc">
          Всего: {s.amount} · уже: {s.paidAmount || 0} · остаток: {remaining}
          {payoutType ? ` · ${payoutType}` : ''}
        </p>

        <label className="admin-modal-field">
          <span>Сумма</span>
          <input className="sec-input" type="number" min="1" max={remaining} value={amount}
            onChange={(e) => setAmount(e.target.value)} disabled={busy} />
        </label>
        <label className="admin-modal-field">
          <span>Тип</span>
          <AdminSelect value={kind} onChange={setKind} options={[
            { value: 'payment', label: 'Выплата' },
            { value: 'advance', label: 'Аванс' },
          ]} />
        </label>

        {payoutType === 'stars' && (
          <>
            <div style={{ marginBottom: 8, fontSize: '0.82rem' }}>
              {fragDead && (
                <span className="staff-badge" style={{ '--badge-color': '#ef4444' }}>
                  Fragment недоступен{frag?.error ? `: ${frag.error}` : ''}
                </span>
              )}
              {!fragDead && frag?.ok && (
                <span className="staff-badge" style={{ '--badge-color': '#34d399' }}>
                  Fragment OK{frag.ton != null ? ` · ${Number(frag.ton).toFixed(2)} TON` : ''}
                </span>
              )}
              {fragUnknown && !fragDead && (
                <span className="staff-badge" style={{ '--badge-color': '#94a3b8' }}>
                  Fragment: нет свежих данных
                </span>
              )}
            </div>
            <label className="admin-modal-field">
              <span>Метод Stars</span>
              <AdminSelect value={starsMethod} onChange={setStarsMethod} options={[
                { value: 'auto', label: 'Auto (Fragment → userbot)' },
                { value: 'fragment', label: fragDead ? 'Fragment (недоступен)' : 'Fragment' },
                { value: 'userbot', label: 'Userbot → канал' },
              ]} />
            </label>
            {fragDead && starsMethod === 'fragment' && (
              <p className="staff-hint" style={{ color: '#ef4444' }}>Fragment не работает — Auto или Userbot.</p>
            )}
            <label className="admin-modal-field">
              <span>Username для Stars</span>
              <input className="sec-input" value={starsUsername}
                onChange={(e) => setStarsUsername(e.target.value)} disabled={busy} placeholder="@username" />
            </label>
          </>
        )}

        {(payoutType === 'crypto' || payoutType === 'card' || payoutType === 'other') && (
          <>
            <label className="admin-modal-field">
              <span>TXID</span>
              <input className="sec-input" value={txid} onChange={(e) => setTxid(e.target.value)} disabled={busy} />
            </label>
            <label className="admin-modal-field">
              <span>Пруф</span>
              <input className="sec-input" value={proof} onChange={(e) => setProof(e.target.value)} disabled={busy} />
            </label>
          </>
        )}

        {(payoutType === 'crypto' || payoutType === 'card') && (
          <div style={{ marginTop: 8 }}>
            <p className="staff-hint">Договор</p>
            <AdminSelect value={tplId} onChange={setTplId} options={[
              { value: '', label: '— шаблон —' },
              ...templates.map((t) => ({ value: String(t.id), label: t.name })),
            ]} />
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <button type="button" className="sec-btn sec-btn-sm" disabled={cBusy || !tplId} onClick={doRender}>Показать</button>
              <button type="button" className="sec-btn sec-btn-sm" disabled={cBusy || !contractText}
                onClick={() => { navigator.clipboard?.writeText(contractText); alert('Скопировано') }}>Копировать</button>
              <button type="button" className="sec-btn sec-btn-sm" disabled={cBusy || !tplId} onClick={doSendContract}>В бот</button>
            </div>
            {contractText && (
              <textarea className="sec-input" rows={5} readOnly value={contractText}
                style={{ width: '100%', marginTop: 8, fontSize: '0.8rem' }} />
            )}
          </div>
        )}

        <div className="admin-modal-actions">
          <button className="panel-users-btn" disabled={busy} onClick={onClose}>Отмена</button>
          <button
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
