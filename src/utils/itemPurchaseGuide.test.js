import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

vi.mock('../lib/shopClient', () => ({
  fetchShopCatalog: vi.fn(),
  fetchShopOffer: vi.fn(async () => ({ item: null, kut: 0 })),
}))
vi.mock('../lib/marketClient', () => ({
  fetchMarketCatalog: vi.fn(async () => ({ items: [], kut: 0 })),
  fetchMarketOffer: vi.fn(async () => ({ item: null, kut: 0 })),
}))

import { fetchShopCatalog, fetchShopOffer } from '../lib/shopClient'
import { fetchMarketOffer } from '../lib/marketClient'
import { guideToItemPurchase } from './itemPurchaseGuide'

describe('guideToItemPurchase', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchShopOffer.mockResolvedValue({ item: null, kut: 0 })
    fetchMarketOffer.mockResolvedValue({ item: null, kut: 0 })
    globalThis.window = {
      dispatchEvent: vi.fn(() => true),
    }
    globalThis.CustomEvent = class CustomEvent {
      constructor(type, init = {}) {
        this.type = type
        this.detail = init.detail
      }
    }
  })

  afterEach(() => {
    delete globalThis.window
    delete globalThis.CustomEvent
  })

  it('prefers exact seed id over fuzzy crop name', async () => {
    fetchShopCatalog.mockResolvedValue({
      kut: 100,
      items: [
        { id: 'harvest_tree', name: 'Дерево', remains: 9 },
        { id: 'seed_tree', name: 'Саженец дерева', remains: 25 },
      ],
    })

    const result = await guideToItemPurchase({
      itemId: 'seed_tree',
      name: 'Дерево',
      search: 'seed_tree',
      itemCatalog: {
        seed_tree: { id: 'seed_tree', name: 'Саженец дерева', emoji: '🌱' },
        harvest_tree: { id: 'harvest_tree', name: 'Дерево', emoji: '🪵' },
      },
    })

    expect(result.destination).toBe('shop')
    expect(result.item.id).toBe('seed_tree')
  })

  it('does not fuzzy-buy harvest product when looking for sapling', async () => {
    fetchShopCatalog.mockResolvedValue({
      kut: 100,
      items: [
        { id: 'harvest_tree', name: 'Дерево', remains: 9 },
      ],
    })

    const result = await guideToItemPurchase({
      itemId: 'seed_tree',
      name: 'Саженец дерева',
      search: 'seed_tree',
      itemCatalog: {
        seed_tree: { id: 'seed_tree', name: 'Саженец дерева', emoji: '🌱' },
      },
    })

    expect(result.item?.id).not.toBe('harvest_tree')
  })

  it('opens the shop purchase for a dex item that is not on the shelf page', async () => {
    fetchShopOffer.mockResolvedValue({
      kut: 40,
      item: { id: '277', name: 'Пистолетик', remains: 1000000, openStock: true },
    })

    const result = await guideToItemPurchase({
      itemId: '277',
      name: 'Пистолетик',
    })

    expect(result.destination).toBe('shop')
    expect(result.item.id).toBe('277')
    expect(fetchShopCatalog).not.toHaveBeenCalled()
    const event = globalThis.window.dispatchEvent.mock.calls[0][0]
    expect(event.type).toBe('farm:open-shop-purchase')
    expect(event.detail.item.name).toBe('Пистолетик')
  })

  it('opens the market purchase when the shop has no stock', async () => {
    fetchShopOffer.mockResolvedValue({ item: null, kut: 10 })
    fetchMarketOffer.mockResolvedValue({
      kut: 10,
      item: { id: '90', itemId: '294', name: 'Вода', quantity: 3, price: 5, isMine: false },
    })

    const result = await guideToItemPurchase({
      itemId: '294',
      name: 'Вода',
    })

    expect(result.destination).toBe('market')
    expect(result.item.itemId).toBe('294')
    const event = globalThis.window.dispatchEvent.mock.calls[0][0]
    expect(event.type).toBe('farm:open-market-purchase')
  })
})
