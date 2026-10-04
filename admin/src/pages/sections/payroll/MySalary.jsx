import { useCallback, useEffect, useState } from 'react'
import { claimDeed, fetchDeedMine, isPanelPreviewMode } from '../../../lib/adminClient'
import { countPhrase, formatKut } from '../../../lib/kutRate'

const CREATOR_CHAT = 'https://t.me/JerichoCute'

function lineCopy(line) {
  if (!(line.rewardKut > 0) || !(line.everyN > 0)) return 'Сумма за этот тип пока не назначена, поэтому выплаты по нему нет.'
  if (line.confirmed > 0 && line.into === 0) {
    return `Эта норма уже в сумме к выдаче. Следующие ${countPhrase(line.everyN, line.title)} снова дадут ${formatKut(line.rewardKut)}.`
  }
  return `Ещё ${countPhrase(line.left, line.title)} — и ${formatKut(line.rewardKut)}.`
}

function messageOf(error) {
  return error?.message || 'Не удалось открыть зарплату'
}

function openCreator() {
  const tg = window.Telegram?.WebApp
  if (typeof tg?.openTelegramLink === 'function') tg.openTelegramLink(CREATOR_CHAT)
  else window.open(CREATOR_CHAT, '_blank', 'noopener')
}

export default function MySalary() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [drawn, setDrawn] = useState(false)

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    setError('')
    try {
      setData(await fetchDeedMine())
    } catch (err) {
      setError(messageOf(err))
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!data) return undefined
    const frame = window.requestAnimationFrame(() => setDrawn(true))
    return () => window.cancelAnimationFrame(frame)
  }, [data])

  const owed = (data?.payouts || []).filter((item) => item.status === 'owed' && item.purse !== 'manual')
  const manual = (data?.payouts || []).filter((item) => item.status === 'owed' && item.purse === 'manual')
  const owedKut = owed.reduce((sum, item) => sum + Number(item.rewardKut || 0), 0)

  const claim = async () => {
    if (!owed.length || busy) return
    setBusy(true)
    setError('')
    setNote('')
    try {
      for (const item of owed) await claimDeed(item.id)
      setNote(owed.length > 1 ? 'Кут уже на балансе.' : `${formatKut(owedKut)} уже на балансе.`)
      await load()
    } catch (err) {
      setError(messageOf(err))
      await load()
    } finally {
      setBusy(false)
    }
  }

  if (isPanelPreviewMode()) {
    return <p className="staff-hint">В копии панели чужая зарплата не открывается. Своя видна в настоящем кабинете.</p>
  }
  if (!data) return <p className="staff-hint">{error || 'Считаем, сколько осталось до нормы…'}</p>

  const lines = data.lines || []

  return (
    <div className="my-pay">
      <p className="deed-lead">
        Здесь только то, что создатель уже засчитал. Ответ на карточке сам по себе в сумму не входит.
      </p>
      {Number(data.checksOpen) > 0 && (
        <p className="deed-lead">Проверок ждёт решения создателя: {data.checksOpen}. Пока он не согласится, они не приближают норму.</p>
      )}

      {(owedKut > 0 || manual.length > 0) && (
        <section className="my-pay-ready" aria-label="Можно забрать">
          <h2>{owedKut > 0 ? `${formatKut(owedKut)} можно забрать` : 'Эту сумму отдаёт создатель'}</h2>
          <p>
            {owedKut > 0
              ? 'Норма выполнена. Кут придёт на баланс сразу из технических групп. Если нужна другая выплата, напишите создателю и договоритесь.'
              : 'Эти нормы отмечены к личной выплате. Напишите @JerichoCute и договоритесь, как их отдать.'}
          </p>
          <div className="my-pay-actions">
            {owedKut > 0 && (
              <button type="button" className="sec-btn" disabled={busy} onClick={claim}>
                {busy ? 'Забираем…' : 'Забрать куты'}
              </button>
            )}
            <button type="button" className="sec-btn sec-btn-ghost" onClick={openCreator}>
              Написать @JerichoCute
            </button>
          </div>
          <ul className="my-pay-owed">
            {owed.map((item) => (
              <li key={item.id}>{item.actionLabel} · {formatKut(item.rewardKut)}</li>
            ))}
            {manual.map((item) => (
              <li key={item.id}>{item.actionLabel} · {formatKut(item.rewardKut)} · лично у создателя</li>
            ))}
          </ul>
        </section>
      )}

      {note && <p className="deed-flash" role="status">{note}</p>}
      {error && <p className="staff-hint" role="alert">{error}</p>}

      <h2 className="my-pay-next">До следующей суммы</h2>
      {lines.length === 0 && (
        <p className="staff-hint">Создатель ещё не включил оплату. Когда норма появится, здесь будет видно, сколько дел до неё осталось.</p>
      )}
      <div className="my-pay-lines">
        {lines.map((line, index) => {
          const width = line.everyN > 0 ? Math.min(100, Math.round((line.into / line.everyN) * 100)) : 0
          const showCount = line.rewardKut > 0 && line.everyN > 0
          return (
            <article
              key={line.actionType}
              className="my-pay-line"
              style={{ animationDelay: `${index * 55}ms` }}
            >
              <div className="my-pay-line-top">
                <h3>{line.title}</h3>
                <b>{line.confirmed} засчитано</b>
              </div>
              {showCount && (
                <p className="my-pay-count">
                  <b>{line.left}</b>
                  <span>осталось</span>
                </p>
              )}
              <div className="my-pay-bar" role="meter" aria-valuemin={0} aria-valuemax={line.everyN || 0} aria-valuenow={line.into || 0} aria-label={line.title}>
                <span style={{ width: drawn ? `${width}%` : '0%' }} />
              </div>
              <p>{lineCopy(line)}</p>
            </article>
          )
        })}
      </div>
    </div>
  )
}
