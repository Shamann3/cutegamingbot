import { useCallback, useEffect, useState } from 'react'
import BottomSheet from './BottomSheet'
import { fetchCollection, buyCosmetic, equipCosmetic } from '../lib/chestClient'
import { RARITY_ACCENT, RARITY_LABEL, SLOT_EFFECT } from '../constants/chests'

export default function ChestCollection({ isActive, onChanged, focusShards = false }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState(null)

  const load = useCallback(async () => {
    try {
      const res = await fetchCollection()
      setData(res)
      setError(null)
    } catch (e) {
      // Keep any prior data on refresh failures; only surface the error
      // state (with retry) when we have nothing to show yet.
      setError(e?.message || 'Не удалось загрузить коллекцию')
    }
  }, [])

  useEffect(() => { if (isActive) load() }, [isActive, load])

  const doBuy = async (item) => {
    setBusy(true)
    try {
      await buyCosmetic(item.cosmeticId)
      setSelected(null)
      await load()
      onChanged?.()
      return true
    } catch (e) {
      window.alert(e?.message || 'Не удалось купить')
      return false
    } finally { setBusy(false) }
  }

  const doEquip = async (item, equipped) => {
    setBusy(true)
    try {
      await equipCosmetic(item.cosmeticId, equipped)
      await load()
      return true
    } catch (e) {
      window.alert(e?.message || 'Не удалось')
      return false
    } finally { setBusy(false) }
  }

  const emitChanged = () => window.dispatchEvent(new Event('cosmetics:changed'))
  const doBuyAndClose = async (item) => { const ok = await doBuy(item); if (ok) emitChanged() }
  const doEquipAndClose = async (item, val) => { const ok = await doEquip(item, val); if (ok) { emitChanged(); setSelected(null) } }

  if (!data && error) {
    return (
      <div className="chest-collection-error">
        <p className="chest-collection-error-text">{error}</p>
        <button type="button" className="chest-collection-retry-btn" onClick={load}>Повторить</button>
      </div>
    )
  }

  if (!data) return <div className="chest-collection-loading">Загрузка…</div>

  const renderItem = (item) => (
    <button
      key={item.cosmeticId}
      className={`chest-col-item${item.owned ? ' owned' : ' locked'}`}
      style={item.owned ? { borderColor: RARITY_ACCENT[item.rarity] } : undefined}
      onClick={() => setSelected(item)}
      disabled={busy}
    >
      <span className={`chest-col-emoji${item.owned ? '' : ' dim'}`}>{item.emoji}</span>
      {item.owned
        ? (item.equipped ? <span className="chest-col-badge">надето</span> : null)
        : <span className="chest-col-price">💎 {item.shardCost}</span>}
    </button>
  )

  const purchasableSets = focusShards
    ? data.sets
        .map((set) => ({ ...set, items: set.items.filter((item) => !item.owned) }))
        .filter((set) => set.items.length > 0)
    : data.sets

  const purchasableLoose = focusShards
    ? data.loose.filter((item) => !item.owned)
    : data.loose

  const nothingToBuy = focusShards && purchasableSets.length === 0 && purchasableLoose.length === 0

  return (
    <div className="chest-collection">
      <div className={focusShards ? 'chest-col-shards chest-col-shards-focus' : 'chest-col-shards'}>💎 {data.shards} осколков</div>
      {nothingToBuy && (
        <div className="chest-collection-empty">Пока нечего покупать за осколки</div>
      )}
      {purchasableSets.map((set) => (
        <section key={set.code} className="chest-col-set">
          <div className="chest-col-set-head">
            <span className="chest-col-set-name">{set.name}</span>
            <span className="chest-col-set-reward">🎁 {set.rewardValue}</span>
          </div>
          {!focusShards && (
            <>
              <div className="chest-col-bar"><i style={{ width: `${set.total ? (100 * set.owned / set.total) : 0}%` }} /></div>
              <div className="chest-col-prog">{set.owned} / {set.total} собрано</div>
            </>
          )}
          <div className="chest-col-grid">{set.items.map(renderItem)}</div>
        </section>
      ))}
      {purchasableLoose.length > 0 && (
        <section className="chest-col-set">
          <div className="chest-col-set-name">Прочее</div>
          <div className="chest-col-grid">{purchasableLoose.map(renderItem)}</div>
        </section>
      )}

      {selected && (
        <BottomSheet isOpen={!!selected} onClose={() => setSelected(null)} title={selected.name} showApply={false}>
          <div className="chest-detail">
            <div className="chest-detail-emoji-wrap"><span className="chest-detail-emoji">{selected.emoji}</span></div>
            <div className="chest-detail-rarity" style={{ color: RARITY_ACCENT[selected.rarity] }}>{RARITY_LABEL[selected.rarity]}</div>
            {selected.description ? <p className="chest-detail-desc">{selected.description}</p> : null}
            <p className="chest-detail-effect">✨ {SLOT_EFFECT[selected.slot] || ''}</p>
            {!selected.owned ? (
              <button className="farm-btn-primary chest-detail-btn" disabled={busy || data.shards < selected.shardCost}
                onClick={() => doBuyAndClose(selected)}>
                {data.shards < selected.shardCost ? 'Не хватает осколков' : `Купить за ${selected.shardCost} осколков`}
              </button>
            ) : selected.equipped ? (
              <button className="farm-btn-primary chest-detail-btn" disabled={busy} onClick={() => doEquipAndClose(selected, false)}>Снять</button>
            ) : (
              <button className="farm-btn-primary chest-detail-btn" disabled={busy} onClick={() => doEquipAndClose(selected, true)}>Поставить</button>
            )}
          </div>
        </BottomSheet>
      )}
    </div>
  )
}
