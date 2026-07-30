import { useEffect, useState } from 'react'
import AdminSelect from '../../components/AdminSelect'
import {
  fetchContractTemplates,
  fetchStarGifts,
  renderContract,
  sendContract,
} from '../../lib/adminClient'
import { payoutLabel } from './payroll/shared'

function nameOf(item) {
  if (!item) return '—'
  return item.firstName || (item.username ? `@${item.username}` : `ID ${item.userId}`)
}

function normalizeStarsUser(value) {
  return String(value || '').trim().replace(/^@+/, '')
}

/** Модалка выплаты: Stars (канал → 👍 → userbot) + договоры для crypto/card */
export default function PayrollPayModal({ member, busy, onClose, onSubmit }) {
  const s = member.salary
  const remaining = Math.max(0, (s.amount || 0) - (s.paidAmount || 0))
  const payoutType = s?.payoutType || member.payoutType || 'other'
  const isStars = payoutType === 'stars'

  const [amount, setAmount] = useState(String(remaining))
  const [kind, setKind] = useState('payment')
  const [txid, setTxid] = useState('')
  const [proof, setProof] = useState('')
  const [starsUsername, setStarsUsername] = useState(
    normalizeStarsUser(member.starsUsername || member.username || ''),
  )
  const [gifts, setGifts] = useState([])
  const [giftId, setGiftId] = useState(0)
  const [giftMeta, setGiftMeta] = useState(null)
  const [giftsLoading, setGiftsLoading] = useState(false)
  const [templates, setTemplates] = useState([])
  const [tplId, setTplId] = useState('')
  const [contractText, setContractText] = useState('')
  const [cBusy, setCBusy] = useState(false)

  const amountNum = Number.parseInt(amount, 10) || 0
  const starsUserClean = normalizeStarsUser(starsUsername)
  const starsUserOk = starsUserClean.length >= 5

  useEffect(() => {
    if (payoutType !== 'crypto' && payoutType !== 'card') return
    fetchContractTemplates()
      .then((d) => {
        const items = (d.items || []).filter(
          (t) => t.enabled && (!t.payoutType || t.payoutType === payoutType || t.payoutType === 'other'),
        )
        setTemplates(items)
        if (items[0]) setTplId(String(items[0].id))
      })
      .catch(() => setTemplates([]))
  }, [payoutType])

  useEffect(() => {
    if (!isStars) {
      setGifts([])
      return
    }
    let cancelled = false
    setGiftsLoading(true)
    fetchStarGifts(null, false)
      .then((d) => {
        if (cancelled) return
        const items = d.items || []
        const exact = items.filter((g) => Number(g.stars) === amountNum)
        const rest = items.filter((g) => Number(g.stars) !== amountNum)
        setGifts(amountNum > 0 ? [...exact, ...rest] : items)
        setGiftId((prev) => {
          if (prev && !items.some((g) => Number(g.giftId) === Number(prev))) {
            setGiftMeta(null)
            return 0
          }
          return prev
        })
      })
      .catch(() => {
        if (!cancelled) setGifts([])
      })
      .finally(() => {
        if (!cancelled) setGiftsLoading(false)
      })
    return () => { cancelled = true }
  }, [isStars, amountNum])

  const selectGift = (g) => {
    if (!g) {
      setGiftId(0)
      setGiftMeta(null)
      return
    }
    setGiftId(Number(g.giftId))
    setGiftMeta(g)
    if (Number(g.stars) > 0 && Number(g.stars) !== amountNum) {
      setAmount(String(g.stars))
    }
  }

  const doRender = async () => {
    if (!tplId) return
    setCBusy(true)
    try {
      const r = await renderContract({
        templateId: Number(tplId),
        userId: member.userId,
        amount: amountNum || remaining,
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
        amount: amountNum || remaining,
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

  const submit = () => {
    if (!amountNum || amountNum < 1) {
      alert('Укажите сумму')
      return
    }
    if (isStars) {
      if (!starsUserOk) {
        alert('Укажите Telegram username для Stars (минимум 5 символов, без @)')
        return
      }
      if (!giftId) {
        const ok = confirm('Подарок не выбран — бот подберёт по сумме автоматически. Продолжить?')
        if (!ok) return
      }
    }
    onSubmit({
      amount: amountNum || null,
      kind,
      txid: txid.trim(),
      proof: proof.trim(),
      starsMethod: isStars ? 'userbot' : null,
      starsUsername: isStars ? starsUserClean : null,
      giftId: isStars ? (giftId || 0) : 0,
      giftEmoji: isStars ? (giftMeta?.emoji || '⭐') : '⭐',
      hasUpgrade: isStars ? (giftMeta?.hasUpgrade ? 1 : 0) : 0,
    })
  }

  const canSubmit = !busy && amountNum > 0 && (!isStars || starsUserOk)

  return (
    <div className="admin-modal-backdrop" role="presentation" onClick={() => !busy && onClose()}>
      <div
        className="admin-modal payroll-pay-modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="admin-modal-title">{isStars ? 'Заявка Stars' : 'Выплата'}</h3>
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

        {!isStars && (
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
        )}

        {isStars && (
          <div className="payroll-pay-block">
            <div className="payroll-flow-card">
              <p className="payroll-flow-step"><b>1</b> Заявка уходит в канал выводов</p>
              <p className="payroll-flow-step"><b>2</b> Владелец жмёт 👍 под сообщением</p>
              <p className="payroll-flow-step"><b>3</b> Юзербот отправляет подарок</p>
            </div>

            <label className="admin-modal-field">
              <span>Username Stars</span>
              <input
                className="sec-input"
                value={starsUsername}
                onChange={(e) => setStarsUsername(e.target.value)}
                disabled={busy}
                placeholder="username без @"
                autoComplete="off"
                spellCheck={false}
              />
            </label>
            {!starsUserOk && (
              <p className="payroll-hint payroll-hint-warn">Нужен валидный username (от 5 символов)</p>
            )}
            {starsUserOk && (
              <p className="payroll-hint">Получатель: @{starsUserClean}</p>
            )}

            <div className="payroll-gifts">
              <p className="payroll-my-label">Подарок</p>
              <p className="payroll-hint">
                {giftsLoading
                  ? 'Загрузка каталога…'
                  : `Как у игроков · ${gifts.length} шт. · точные ${amountNum || '—'}⭐ сверху`}
              </p>
              <div className="payroll-gifts-grid">
                <button
                  type="button"
                  className={`payroll-gift${giftId === 0 ? ' is-active' : ''}`}
                  onClick={() => selectGift(null)}
                  disabled={busy}
                >
                  <span className="payroll-gift-emoji">⭐</span>
                  <span className="payroll-gift-meta">Авто · {amountNum || '—'}⭐</span>
                </button>
                {gifts.map((g) => (
                  <button
                    key={g.giftId}
                    type="button"
                    className={`payroll-gift${Number(giftId) === Number(g.giftId) ? ' is-active' : ''}`}
                    onClick={() => selectGift(g)}
                    disabled={busy}
                    title={`${g.source || 'gift'} · ID ${g.giftId}`}
                  >
                    <span className="payroll-gift-emoji">{g.emoji || '🎁'}</span>
                    <span className="payroll-gift-meta">
                      {g.stars}⭐{g.hasUpgrade ? ' · NFT' : ''}
                      {g.source === 'live' ? ' · TG' : g.source === 'manual' ? ' · руч.' : ''}
                    </span>
                  </button>
                ))}
              </div>
            </div>
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
          <button type="button" className="panel-users-btn" disabled={busy} onClick={onClose}>
            Отмена
          </button>
          <button
            type="button"
            className="panel-users-btn panel-users-btn-primary"
            disabled={!canSubmit}
            onClick={submit}
          >
            {busy ? '…' : (isStars ? 'Отправить в канал' : 'Провести')}
          </button>
        </div>
      </div>
    </div>
  )
}
