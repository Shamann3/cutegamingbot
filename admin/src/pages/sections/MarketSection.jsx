import { useCallback, useEffect, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import AdminSelect from '../../components/AdminSelect'
import {
  cancelMarketListing,
  fetchMarketListings,
  fetchMarketOverview,
} from '../../lib/adminClient'

function formatKut(value) {
  if (value == null) return '-'
  return Number(value).toLocaleString('ru-RU')
}

function formatDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

function suspiciousLabel(reason) {
  if (reason === 'high') return 'Завышена'
  if (reason === 'low') return 'Занижена'
  if (reason === 'out_of_bounds') return 'Вне лимита'
  if (reason === 'high_no_ref') return 'Очень дорого'
  return 'Подозрительно'
}

function ListingRow({ row, onCancel, cancellingId }) {
  const busy = cancellingId === row.listingId

  return (
    <tr className={row.suspicious ? 'panel-market-row-suspicious' : ''}>
      <td className="panel-economy-dex-id">#{row.listingId}</td>
      <td>
        {row.emoji} {row.itemName}
        <span className="panel-market-item-id">{row.itemId}</span>
      </td>
      <td>{row.quantity}</td>
      <td className="panel-economy-dex-effective">{formatKut(row.price)}</td>
      <td>{formatKut(row.totalValue)}</td>
      <td>
        <span>{row.sellerName}</span>
        {row.sellerUsername && (
          <span className="panel-market-seller-handle">@{row.sellerUsername}</span>
        )}
        <span className="panel-market-item-id">{row.sellerId}</span>
      </td>
      <td className="panel-market-date">{formatDate(row.createdAt)}</td>
      <td>
        {row.suspicious && (
          <span className={`panel-market-flag panel-market-flag-${row.suspiciousReason || 'warn'}`}>
            {suspiciousLabel(row.suspiciousReason)}
            {row.referencePrice != null && (
              <span className="panel-market-ref">
                {' '}
                (эталон {formatKut(row.referencePrice)})
              </span>
            )}
          </span>
        )}
      </td>
      <td>
        <button
          type="button"
          className="panel-users-btn panel-users-btn-danger"
          disabled={busy}
          onClick={() => onCancel(row)}
        >
          {busy ? '…' : 'Снять'}
        </button>
      </td>
    </tr>
  )
}

export default function MarketSection() {
  const [overview, setOverview] = useState(null)
  const [listings, setListings] = useState({ listings: [], total: 0 })
  const [query, setQuery] = useState('')
  const [itemFilter, setItemFilter] = useState('')
  const [suspiciousOnly, setSuspiciousOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [listLoading, setListLoading] = useState(false)
  const [cancellingId, setCancellingId] = useState(null)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [cancelTarget, setCancelTarget] = useState(null)
  const [cancelReason, setCancelReason] = useState('')

  const loadOverview = useCallback(async () => {
    setError('')
    try {
      const data = await fetchMarketOverview()
      setOverview(data)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить биржу')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadListings = useCallback(async (opts = {}) => {
    setListLoading(true)
    setError('')
    try {
      const data = await fetchMarketListings({
        q: opts.q ?? '',
        itemId: opts.itemId ?? '',
        suspicious: opts.suspicious ?? false,
      })
      setListings(data)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить лоты')
    } finally {
      setListLoading(false)
    }
  }, [])

  useEffect(() => {
    loadOverview()
    loadListings({ q: '', itemId: '', suspicious: false })
  }, [loadOverview, loadListings])

  const handleSearch = (e) => {
    e.preventDefault()
    loadListings({ q: query, itemId: itemFilter, suspicious: suspiciousOnly })
  }

  const openCancelDialog = (row) => {
    setCancelTarget(row)
    setCancelReason('')
  }

  const closeCancelDialog = () => {
    if (cancellingId) return
    setCancelTarget(null)
    setCancelReason('')
  }

  const confirmCancel = async () => {
    if (!cancelTarget) return

    const listingId = cancelTarget.listingId
    setCancellingId(listingId)
    setError('')
    setInfo('')
    try {
      await cancelMarketListing(listingId, cancelReason.trim())
      setInfo(`Лот #${listingId} снят, продавец получит сообщение в боте`)
      setCancelTarget(null)
      setCancelReason('')
      await Promise.all([
        loadOverview(),
        loadListings({ q: query, itemId: itemFilter, suspicious: suspiciousOnly }),
      ])
    } catch (err) {
      setError(err.message || 'Не удалось снять лот')
    } finally {
      setCancellingId(null)
    }
  }

  const today = overview?.today
  const suspicious = overview?.suspicious || []

  return (
    <div className="panel-market">
      <AdminActionModal
        open={Boolean(cancelTarget)}
        title={cancelTarget ? `Снять лот #${cancelTarget.listingId}?` : ''}
        description={
          cancelTarget
            ? `Предмет вернётся продавцу ${cancelTarget.sellerId}. Сообщение уйдёт в игрового бота.`
            : ''
        }
        confirmText="Снять лот"
        danger
        loading={Boolean(cancellingId)}
        showReason
        reason={cancelReason}
        onReasonChange={setCancelReason}
        reasonPlaceholder="Причина для игрока (необязательно)"
        onConfirm={confirmCancel}
        onCancel={closeCancelDialog}
      />

      <article className="panel-shelf panel-shelf-page panel-market-head">
        <p className="panel-shelf-label">Market · Биржа</p>
        <h2 className="panel-page-title">Игровая биржа</h2>
        <p className="panel-page-lead">
          Активные лоты, модерация и подозрительные цены
          {overview?.date && ` · сегодня ${overview.date} (${overview.timezone})`}
        </p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
      </article>

      <div className="panel-economy-stats">
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Активные лоты</p>
          <p className="panel-economy-stat-value">
            {loading ? '…' : overview?.activeListings ?? '-'}
          </p>
          <p className="panel-shelf-muted">Сейчас на бирже</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Сделок за день</p>
          <p className="panel-economy-stat-value">{loading ? '…' : today?.deals ?? '-'}</p>
          <p className="panel-shelf-muted">Покупок (market_buy)</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Объём за день</p>
          <p className="panel-economy-stat-value">
            {loading ? '…' : formatKut(today?.volumeKut)}
          </p>
          <p className="panel-shelf-muted">
            {loading ? '…' : `${today?.itemsSold ?? 0} предметов продано`}
          </p>
        </article>
      </div>

      {suspicious.length > 0 && (
        <article className="panel-shelf panel-market-suspicious">
          <p className="panel-shelf-label">Подозрительные цены</p>
          <p className="panel-shelf-muted">
            Сравнение с медианой продаж за 7 дней, активных лотов или ценой в dex (×3 / ÷3)
          </p>
          <ul className="panel-market-suspicious-list">
            {suspicious.map((row) => (
              <li key={row.listingId}>
                <span>
                  #{row.listingId} {row.emoji} {row.itemName} - {formatKut(row.price)} kut
                </span>
                <span className={`panel-market-flag panel-market-flag-${row.suspiciousReason}`}>
                  {suspiciousLabel(row.suspiciousReason)}
                  {row.priceRatio != null && ` (${row.priceRatio}×)`}
                </span>
                <button
                  type="button"
                  className="panel-users-btn panel-users-btn-danger"
                  disabled={cancellingId === row.listingId}
                  onClick={() => openCancelDialog(row)}
                >
                  Снять
                </button>
              </li>
            ))}
          </ul>
        </article>
      )}

      <article className="panel-shelf panel-market-listings">
        <p className="panel-shelf-label">Активные лоты</p>

        <form className="panel-market-filters" onSubmit={handleSearch}>
          <input
            className="panel-users-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Предмет, id или продавец"
            disabled={listLoading}
          />
          <AdminSelect
            value={itemFilter}
            onChange={setItemFilter}
            disabled={listLoading}
            placeholder="Все предметы"
            options={[
              { value: '', label: 'Все предметы' },
              ...(overview?.itemFilters || []).map((item) => ({
                value: item.itemId,
                label: `${item.emoji} ${item.name} (${item.listings})`,
              })),
            ]}
          />
          <label className="panel-market-check">
            <input
              type="checkbox"
              checked={suspiciousOnly}
              onChange={(e) => setSuspiciousOnly(e.target.checked)}
              disabled={listLoading}
            />
            Только подозрительные
          </label>
          <button type="submit" className="panel-users-btn panel-users-btn-primary" disabled={listLoading}>
            {listLoading ? '…' : 'Применить'}
          </button>
        </form>

        <p className="panel-shelf-muted">Найдено: {listings.total}</p>

        <div className="panel-economy-dex-wrap">
          <table className="panel-economy-dex-table panel-market-table">
            <thead>
              <tr>
                <th>Лот</th>
                <th>Предмет</th>
                <th>Qty</th>
                <th>Цена</th>
                <th>Сумма</th>
                <th>Продавец</th>
                <th>Создан</th>
                <th>Флаг</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {listings.listings.map((row) => (
                <ListingRow
                  key={row.listingId}
                  row={row}
                  onCancel={openCancelDialog}
                  cancellingId={cancellingId}
                />
              ))}
            </tbody>
          </table>
          {!listLoading && listings.listings.length === 0 && (
            <p className="panel-shelf-muted panel-economy-dex-empty">Активных лотов нет</p>
          )}
        </div>
      </article>
    </div>
  )
}
