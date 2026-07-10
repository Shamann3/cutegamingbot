import { formatKut } from './formatKut'
import { EMPTY_VALUE } from './displayText'

function formatPrice(value) {
  if (value == null || value <= 0) return null
  return `${formatKut(value)} кут`
}

function lotWord(count) {
  if (count === 1) return '1 предложение'
  if (count >= 2 && count <= 4) return `${formatKut(count)} предложения`
  return `${formatKut(count)} предложений`
}

export function inventoryTileHint(item) {
  if (item.meta?.trim()) return item.meta.trim()

  const eco = item.economy
  if (!eco) return item.groupLabel

  const parts = []
  const market = eco.market ?? {}
  const shop = eco.shop ?? {}

  const price = market.avgPrice ?? market.minPrice ?? market.referencePrice ?? shop.effectivePrice
  if (price) parts.push(`≈${formatKut(price)} кут`)

  if (market.quantity > 0) {
    parts.push(`биржа: ${formatKut(market.quantity)} шт`)
  } else if (shop.inShop && shop.remains > 0) {
    parts.push(`магазин: ${formatKut(shop.remains)} шт`)
  }

  if (eco.listedByYou > 0) {
    parts.push(`ваши: ${formatKut(eco.listedByYou)} шт`)
  }

  return parts.length ? parts.join(' · ') : item.groupLabel
}

export function inventoryEconomyRows(item) {
  const eco = item.economy
  if (!eco) return []

  const rows = []
  const shop = eco.shop ?? {}
  const market = eco.market ?? {}

  if (shop.inShop) {
    const priceLine = shop.salePrice
      ? `${formatKut(shop.salePrice)} кут за шт (скидка, обычно ${formatKut(shop.price)})`
      : `${formatPrice(shop.effectivePrice) ?? EMPTY_VALUE} за шт`
    rows.push({
      id: 'shop-stock',
      label: 'Магазин',
      value: `В наличии ${formatKut(shop.remains)} шт · ${priceLine}`,
    })
  } else {
    rows.push({
      id: 'shop-stock',
      label: 'Магазин',
      value: 'Сейчас не продаётся',
    })
  }

  if (market.quantity > 0) {
    const details = [`Игроки продают ${formatKut(market.quantity)} шт`, lotWord(market.listingCount)]
    if (market.avgPrice) {
      details.push(`в среднем ${formatKut(market.avgPrice)} кут за шт`)
    } else if (market.minPrice) {
      details.push(`от ${formatKut(market.minPrice)} кут за шт`)
    }
    if (market.minPrice && market.maxPrice && market.minPrice !== market.maxPrice) {
      details.push(`цены от ${formatKut(market.minPrice)} до ${formatKut(market.maxPrice)} кут`)
    }
    rows.push({
      id: 'market-supply',
      label: 'Биржа',
      value: details.join(' · '),
    })
  } else if (market.listable) {
    rows.push({
      id: 'market-supply',
      label: 'Биржа',
      value: 'Сейчас никто не продаёт · можно выставить свой лот',
    })
  } else {
    rows.push({
      id: 'market-supply',
      label: 'Биржа',
      value: 'Этот предмет нельзя продать на бирже',
    })
  }

  if (market.recentMedianPrice) {
    rows.push({
      id: 'market-recent',
      label: 'Недавние покупки',
      value: `За последние 7 дней покупали примерно по ${formatKut(market.recentMedianPrice)} кут за шт`,
    })
  } else if (market.referencePrice && !market.avgPrice) {
    rows.push({
      id: 'market-reference',
      label: 'Примерная цена',
      value: `Ориентир: около ${formatKut(market.referencePrice)} кут за шт`,
    })
  }

  if (eco.listedByYou > 0) {
    rows.push({
      id: 'market-own',
      label: 'Ваши лоты',
      value: `Уже выставлено на продажу: ${formatKut(eco.listedByYou)} шт`,
    })
  }

  const reference = market.referencePrice ?? market.avgPrice ?? shop.effectivePrice
  if (reference && item.count > 0) {
    rows.push({
      id: 'estimate',
      label: 'Ваш запас',
      value: `${formatKut(item.count)} шт ≈ ${formatKut(reference * item.count)} кут, если продать по ~${formatKut(reference)} за шт`,
    })
  }

  return rows
}

/** Цена за штуку только с биржи (для заголовка «стоимость на бирже»). */
export function inventoryMarketUnitPrice(item) {
  const market = item.economy?.market ?? {}
  return (
    market.avgPrice
    ?? market.minPrice
    ?? market.recentMedianPrice
    ?? market.referencePrice
    ?? null
  )
}

/** Цена за штуку для оценки запаса (биржа → недавние сделки → ориентир → магазин). */
export function inventoryUnitPrice(item) {
  const shop = item.economy?.shop ?? {}
  return inventoryMarketUnitPrice(item) ?? (shop.inShop ? shop.effectivePrice : null) ?? null
}

/** Общая стоимость запаса на бирже (кол-во × цена за шт). */
export function inventoryExchangeTotal(item) {
  const unit = inventoryMarketUnitPrice(item)
  const count = item.count ?? 0
  if (unit == null || unit <= 0 || count <= 0) return null
  return Math.round(unit * count)
}

/** Четыре ячейки для карточки предмета (2×2). */
export function inventoryItemCardCells(item) {
  const eco = item.economy
  const market = eco?.market ?? {}
  const shop = eco?.shop ?? {}
  const listed = eco?.listedByYou ?? 0
  const unit = inventoryMarketUnitPrice(item)
    ?? (shop.inShop ? shop.effectivePrice : null)

  const cells = [
    {
      id: 'own',
      label: 'У вас',
      value: `${formatKut(item.count)} шт`,
      icon: '🎒',
    },
    {
      id: 'unit',
      label: 'За штуку',
      value: unit ? `${formatKut(unit)} кут` : EMPTY_VALUE,
      icon: '💱',
    },
    {
      id: 'shop',
      label: 'Магазин',
      value: shop.inShop && shop.effectivePrice
        ? `${formatKut(shop.effectivePrice)} кут`
        : 'Не продаётся',
      icon: '🏪',
    },
    {
      id: 'market',
      label: listed > 0 ? 'Ваши лоты' : 'На бирже',
      value: listed > 0
        ? `${formatKut(listed)} шт`
        : market.quantity > 0
          ? `${formatKut(market.quantity)} шт`
          : market.listable
            ? 'Нет лотов'
            : EMPTY_VALUE,
      icon: '📊',
    },
  ]

  if (item.meta?.trim()) {
    cells[3] = {
      id: 'meta',
      label: 'Состояние',
      value: item.meta.trim(),
      icon: '⚙️',
    }
  }

  return cells
}
