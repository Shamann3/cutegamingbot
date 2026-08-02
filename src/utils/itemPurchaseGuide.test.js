import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

vi.mock('../lib/shopClient', () => ({
  fetchShopCatalog: vi.fn(),
}))
vi.mock('../lib/marketClient', () => ({
  fetchMarketCatalog: vi.fn(async () => ({ items: [], kut: 0 })),
}))

import { fetchShopCatalog } from '../lib/shopClient'
import { guideToItemPurchase } from './itemPurchaseGuide'

describe('guideToItemPurchase', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
})
