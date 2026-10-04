import { useMemo, useState } from 'react'
import { formatUsd, kutQuote, starWords } from '../../../lib/kutRate'

export default function KutRate() {
  const [raw, setRaw] = useState('1')
  const quote = useMemo(() => kutQuote(raw), [raw])

  return (
    <form className="kut-rate" onSubmit={(event) => event.preventDefault()}>
      <h2>Сколько стоит кут</h2>
      <label>
        Кут
        <input
          inputMode="decimal"
          value={raw}
          onChange={(event) => setRaw(event.target.value.replace(/[^\d.,]/g, '').slice(0, 9))}
          aria-label="Сколько кут посчитать"
        />
      </label>
      <p className="kut-rate-out" aria-live="polite" key={`${quote.stars}:${quote.netUsd}`}>
        <strong>{starWords(quote.stars)}</strong>
        <span>{formatUsd(quote.grossUsd)} до комиссии</span>
        <span>{formatUsd(quote.netUsd)} после 30% Telegram</span>
      </p>
      <p className="kut-rate-note">
        В боте 1 кут равен 1 звезде. Вторая сумма — то, что остаётся после комиссии Telegram.
      </p>
    </form>
  )
}
