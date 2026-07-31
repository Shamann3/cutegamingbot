import { useEffect, useMemo, useState } from 'react'
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

/** Модалка выплаты: Stars (мультиподарки → N сообщений в канал → 👍) */
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
  const [selected, setSelected] = useState([]) // [{giftId, giftEmoji, hasUpgrade, stars}]
  const [giftsLoading, setGiftsLoading] = useState(false)
  const [templates, setTemplates] = useState([])
  const [tplId, setTplId] = useState('')
  const [contractText, setContractText] = useState('')
  const [cBusy, setCBusy] = useState(false)

  const amountNum = Number.parseInt(amount, 10) || 0
  const starsUserClean = normalizeStarsUser(starsUsername)
  const starsUserOk = starsUserClean.length >= 5
  const selectedSum = useMemo(
    () => selected.reduce((acc, g) => acc + Number(g.stars || 0), 0),
    [selected],
  )
  const sumOk = selected.length === 0 || selectedSum === amountNum
  const remainingToPick = Math.max(0, amountNum - selectedSum)

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
        const budget = remainingToPick > 0 ? remainingToPick : amountNum
        const exact = items.filter((g) => Number(g.stars) === budget)
        const fit = items.filter((g) => Number(g.stars) <= budget && Number(g.stars) !== budget)
        const rest = items.filter((g) => Number(g.stars) > budget)
        setGifts(amountNum > 0 ? [...exact, ...fit, ...rest] : items)
      })
      .catch(() => {
        if (!cancelled) setGifts([])
      })
      .finally(() => {
        if (!cancelled) setGiftsLoading(false)
      })
    return () => { cancelled = true }
  }, [isStars, amountNum, remainingToPick])

  const addGift = (g) => {
    if (!g) return
    const stars = Number(g.stars) || 0
    if (stars <= 0) return
    if (selectedSum + stars > amountNum) {
      alert(`Не влезает: ${selectedSum}+${stars} > ${amountNum}. Уберите подарок или увеличьте сумму.`)
      return
    }
    setSelected((prev) => [
      ...prev,
      {
        giftId: Number(g.giftId),
        giftEmoji: g.emoji || '⭐',
        hasUpgrade: g.hasUpgrade ? 1 : 0,
        stars,
      },
    ])
  }

  const removeGiftAt = (idx) => {
    setSelected((prev) => prev.filter((_, i) => i !== idx))
  }

  const clearGifts = () => setSelected([])

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
      if (selected.length > 0 && selectedSum !== amountNum) {
        alert(`Сумма подарков ${selectedSum}⭐ ≠ выплате ${amountNum}⭐`)
        return
      }
      if (selected.length === 0) {
        const ok = confirm(
          'Подарки не выбраны — в канал уйдёт 1 заявка на всю сумму, бот подберёт подарок сам. Продолжить?',
        )
        if (!ok) return
      }
    }
    const first = selected[0]
    onSubmit({
      amount: amountNum || null,
      kind,
      txid: txid.trim(),
      proof: proof.trim(),
      starsMethod: isStars ? 'userbot' : null,
      starsUsername: isStars ? starsUserClean : null,
      giftId: first ? first.giftId : 0,
      giftEmoji: first ? first.giftEmoji : '⭐',
      hasUpgrade: first ? first.hasUpgrade : 0,
      gifts: isStars && selected.length > 0 ? selected : null,
    })
  }

  const canSubmit = !busy && amountNum > 0 && (!isStars || (starsUserOk && sumOk))

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
            onChange={(e) => {
              setAmount(e.target.value)
              setSelected([])
            }}
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
              <p className="payroll-flow-step"><b>1</b> Выберите 1+ подарков на сумму выплаты</p>
              <p className="payroll-flow-step"><b>2</b> Каждый подарок = отдельное сообщение в канале</p>
              <p className="payroll-flow-step"><b>3</b> 👍 под каждым → юзербот отправит подарок</p>
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
              <div className="payroll-gift-basket">
                <p className="payroll-my-label">Корзина подарков</p>
                <p className={`payroll-hint${sumOk ? '' : ' payroll-hint-warn'}`}>
                  Собрано <b>{selectedSum}</b> / {amountNum}⭐
                  {selected.length > 0 ? ` · ${selected.length} сообщ. в канале` : ' · авто 1 сообщ.'}
                  {remainingToPick > 0 && selected.length > 0 ? ` · ещё ${remainingToPick}⭐` : ''}
                </p>
                {selected.length > 0 && (
                  <div className="payroll-basket-list">
                    {selected.map((g, idx) => (
                      <button
                        key={`${g.giftId}-${idx}`}
                        type="button"
                        className="payroll-basket-item"
                        onClick={() => removeGiftAt(idx)}
                        disabled={busy}
                        title="Убрать"
                      >
                        <span>{g.giftEmoji || '🎁'}</span>
                        <span>{g.stars}⭐</span>
                        <span className="payroll-basket-x">×</span>
                      </button>
                    ))}
                    <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={clearGifts} disabled={busy}>
                      Очистить
                    </button>
                  </div>
                )}
              </div>

              <p className="payroll-my-label">Каталог</p>
              <p className="payroll-hint">
                {giftsLoading
                  ? 'Загрузка…'
                  : `Нажмите подарок, чтобы добавить. Для 115⭐ — например 50+50+15.`}
              </p>
              <div className="payroll-gifts-grid">
                {gifts.map((g) => {
                  const stars = Number(g.stars) || 0
                  const fits = selectedSum + stars <= amountNum
                  return (
                    <button
                      key={g.giftId}
                      type="button"
                      className={`payroll-gift${fits ? '' : ' is-disabled'}`}
                      onClick={() => addGift(g)}
                      disabled={busy || !fits}
                      title={`${g.source || 'gift'} · ID ${g.giftId}`}
                    >
                      <span className="payroll-gift-emoji">{g.emoji || '🎁'}</span>
                      <span className="payroll-gift-meta">
                        {g.stars}⭐{g.hasUpgrade ? ' · NFT' : ''}
                      </span>
                    </button>
                  )
                })}
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
          <button type="button" className="panel-users-btn" data-modal-cancel disabled={busy} onClick={onClose}>
            Отмена
          </button>
          <button
            type="button"
            className="panel-users-btn panel-users-btn-primary"
            data-modal-confirm
            disabled={!canSubmit}
            onClick={submit}
          >
            {busy
              ? '…'
              : (isStars
                ? (selected.length > 1 ? `В канал · ${selected.length} сообщ.` : 'Отправить в канал')
                : 'Провести')}
          </button>
        </div>
      </div>
    </div>
  )
}
