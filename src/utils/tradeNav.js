const LEGACY_TRADE_SEGMENT = {
  shop: 'shop',
  market: 'market',
}

/** Разбирает id таба из deep-link (?startapp=... / start_param) в {tab, tradeSegment}. */
export function resolveStartTab(rawTab) {
  if (rawTab in LEGACY_TRADE_SEGMENT) {
    return { tab: 'trade', tradeSegment: LEGACY_TRADE_SEGMENT[rawTab] }
  }
  if (rawTab === 'trade') {
    return { tab: 'trade', tradeSegment: 'shop' }
  }
  // Вкладка розыгрышей скрыта — deep-link ведёт на ферму.
  if (rawTab === 'giveaways') {
    return { tab: 'farm', tradeSegment: 'shop' }
  }
  return { tab: rawTab || 'farm', tradeSegment: 'shop' }
}
