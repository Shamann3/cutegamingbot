import { useEffect, useLayoutEffect, useState } from 'react'
import { formatKut } from '../utils/formatKut'
import { useEscapeClose } from '../hooks/useEscapeClose'
import { openTelegramBotLink } from '../lib/telegram'
import {
  buildDonateBotUrl,
  DONATE_DEFAULT_AMOUNT,
  DONATE_DISCLAIMER,
  DONATE_MAX_AMOUNT,
  DONATE_MIN_AMOUNT,
  DONATE_PRESETS,
} from '../constants/donate'
import Portal from './Portal'

export default function DonateModal({
  isOpen,
  onClose,
  context = null,
  initialAmount = null,
}) {
  const [agreed, setAgreed] = useState(false)
  const [visible, setVisible] = useState(false)
  const [amountText, setAmountText] = useState(String(DONATE_DEFAULT_AMOUNT))

  useEscapeClose(isOpen && visible, onClose)

  useLayoutEffect(() => {
    if (!isOpen) return undefined

    const blockBackgroundScroll = (event) => {
      if (event.target.closest?.('.donate-modal-scroll')) return
      event.preventDefault()
    }

    document.addEventListener('touchmove', blockBackgroundScroll, { passive: false })
    return () => {
      document.removeEventListener('touchmove', blockBackgroundScroll)
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) {
      setVisible(false)
      return undefined
    }

    const nextAmount = initialAmount ?? context?.suggestedAmount ?? DONATE_DEFAULT_AMOUNT
    setAgreed(false)
    setAmountText(String(nextAmount))
    const openFrame = window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => setVisible(true))
    })

    return () => window.cancelAnimationFrame(openFrame)
  }, [isOpen, initialAmount, context?.suggestedAmount])

  if (!isOpen) return null

  const parsedAmount = Number.parseInt(amountText, 10)
  const hasValidAmount = Number.isFinite(parsedAmount) && parsedAmount >= DONATE_MIN_AMOUNT
  const amount = hasValidAmount ? Math.min(parsedAmount, DONATE_MAX_AMOUNT) : DONATE_MIN_AMOUNT
  const displayAmount = formatKut(hasValidAmount ? amount : 0)

  const canSubmit = agreed && hasValidAmount && amount >= DONATE_MIN_AMOUNT

  const setAmountValue = (next) => {
    const clamped = Math.max(DONATE_MIN_AMOUNT, Math.min(next, DONATE_MAX_AMOUNT))
    setAmountText(String(clamped))
  }

  const handleAmountInput = (event) => {
    const raw = event.target.value
    if (raw === '') {
      setAmountText('')
      return
    }

    const digitsOnly = raw.replace(/\D/g, '')
    if (digitsOnly === '') {
      setAmountText('')
      return
    }

    const next = Number.parseInt(digitsOnly, 10)
    if (!Number.isFinite(next)) return
    setAmountText(String(Math.min(next, DONATE_MAX_AMOUNT)))
  }

  const handleAmountBlur = () => {
    const next = Number.parseInt(amountText, 10)
    if (!Number.isFinite(next) || next < DONATE_MIN_AMOUNT) {
      setAmountText(String(DONATE_MIN_AMOUNT))
      return
    }
    setAmountText(String(Math.min(next, DONATE_MAX_AMOUNT)))
  }

  const handleConfirm = () => {
    if (!canSubmit) return
    openTelegramBotLink(buildDonateBotUrl(amount))
    onClose()
  }

  return (
    <Portal>
      <div
        className={`donate-modal-root ${visible ? 'donate-modal-root--open' : ''}`}
        role="presentation"
        onClick={onClose}
      >
        <div
          className={`donate-modal ${visible ? 'donate-modal--open' : ''}`}
          role="dialog"
          aria-modal="true"
          aria-labelledby="donate-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="donate-modal-shine" aria-hidden />
          <button type="button" className="donate-modal-close" onClick={onClose} aria-label="Закрыть">
            ×
          </button>

          <div className="donate-modal-hero">
            <div className="donate-modal-orbs" aria-hidden>
              <span className="donate-modal-orb donate-modal-orb--left">✨</span>
              <span className="donate-modal-orb donate-modal-orb--center">⭐</span>
              <span className="donate-modal-orb donate-modal-orb--right">✨</span>
            </div>
            <p className="donate-modal-eyebrow">Telegram Stars</p>
            <h2 id="donate-title" className="donate-modal-title">
              {context?.shortfall ? 'Не хватает КУТ' : 'Пополнение'}
            </h2>
            <p className="donate-modal-subtitle">
              {context?.shortfall
                ? `Пополните баланс${context.actionLabel ? `: ${context.actionLabel}` : ''}`
                : 'Быстро, безопасно, прямо в боте'}
            </p>
          </div>

          <div className="donate-modal-body">
            <div className="donate-modal-scroll">
              <div className="donate-stagger">
                {context?.shortfall ? (
                  <div className="donate-modal-context" role="status">
                    <p className="donate-modal-context-line">
                      Не хватает <strong>{formatKut(context.shortfall)} КУТ</strong>
                    </p>
                    <p className="donate-modal-context-detail">
                      {context.actionLabel ? `${context.actionLabel} · ` : ''}
                      нужно {formatKut(context.neededCost)} · у вас {formatKut(context.balance)}
                    </p>
                  </div>
                ) : null}

                <div className="donate-amount-card">
                  <div className="donate-amount-display">
                    <span className="donate-amount-display-value">{displayAmount}</span>
                    <span className="donate-amount-display-unit">КУТ</span>
                  </div>

                  <div className="donate-amount-stepper">
                    <button
                      type="button"
                      className="donate-step-btn"
                      onClick={() => setAmountValue(amount - 1)}
                      disabled={!hasValidAmount || amount <= DONATE_MIN_AMOUNT}
                      aria-label="Меньше"
                    >
                      −
                    </button>
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      className="donate-amount-input"
                      value={amountText}
                      onChange={handleAmountInput}
                      onBlur={handleAmountBlur}
                      aria-label="Сумма пополнения"
                    />
                    <button
                      type="button"
                      className="donate-step-btn"
                      onClick={() => setAmountValue(amount + 1)}
                      disabled={!hasValidAmount || amount >= DONATE_MAX_AMOUNT}
                      aria-label="Больше"
                    >
                      +
                    </button>
                  </div>

                  <div className="donate-amount-presets">
                    {DONATE_PRESETS.map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        className={`donate-amount-preset ${amount === preset ? 'donate-amount-preset--active' : ''}`}
                        onClick={() => setAmountValue(preset)}
                      >
                        {formatKut(preset)}
                      </button>
                    ))}
                    <button
                      type="button"
                      className={`donate-amount-preset donate-amount-preset--max ${amount === DONATE_MAX_AMOUNT ? 'donate-amount-preset--active' : ''}`}
                      onClick={() => setAmountValue(DONATE_MAX_AMOUNT)}
                    >
                      Макс
                    </button>
                  </div>

                  <p className="donate-amount-hint">
                    от {formatKut(DONATE_MIN_AMOUNT)} до {formatKut(DONATE_MAX_AMOUNT)} КУТ
                  </p>
                </div>

                <div className="donate-disclaimer">
                  <div className="donate-disclaimer-head">
                    <span className="donate-disclaimer-icon" aria-hidden>🔒</span>
                    <span className="donate-disclaimer-title">{DONATE_DISCLAIMER.title}</span>
                  </div>
                  {DONATE_DISCLAIMER.lines.map((line) => (
                    <p key={line} className="donate-disclaimer-line">{line}</p>
                  ))}
                </div>

                <label className={`donate-agree ${agreed ? 'donate-agree--checked' : ''}`}>
                  <input
                    type="checkbox"
                    className="donate-agree-input"
                    checked={agreed}
                    onChange={(event) => setAgreed(event.target.checked)}
                  />
                  <span className="donate-agree-box" aria-hidden>
                    <svg className="donate-agree-check" viewBox="0 0 12 10" fill="none">
                      <path
                        d="M1.2 5.2 4.4 8.4 10.8 1.6"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                  <span className="donate-agree-copy">
                    <span className="donate-agree-title">Согласен(на) перейти к оплате</span>
                    <span className="donate-agree-sub">Ознакомился(ась) с информацией выше</span>
                  </span>
                </label>
              </div>
            </div>
          </div>

          <div className="donate-modal-actions">
            <button type="button" className="donate-modal-cancel" onClick={onClose}>
              Отмена
            </button>
            <button
              type="button"
              className="donate-modal-confirm"
              disabled={!canSubmit}
              onClick={handleConfirm}
            >
              <span className="donate-modal-confirm-glow" aria-hidden />
              <span className="donate-modal-confirm-label">Перейти к оплате</span>
              <span className="donate-modal-confirm-amount">{displayAmount} КУТ</span>
            </button>
          </div>
        </div>
      </div>
    </Portal>
  )
}
