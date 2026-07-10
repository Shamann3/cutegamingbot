import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import { buyShopItem, fetchShopCatalog } from '../lib/shopClient'
import { usePlayerSync } from '../context/PlayerSyncContext'
import { useSettings } from '../context/SettingsContext'
import { PERF_MODES, PERF_POLL_MS } from '../constants/performance'
import { useShopLayout } from './useShopLayout'
import { shopGridClassForColumns } from '../utils/shopLayout'
import { canAuthenticate, getAuthErrorMessage } from '../lib/telegram'
import { reportClientError } from '../lib/errorReporter'

const PURCHASE_TOAST_MS = 3200
const SEARCH_DEBOUNCE_MS = 350

function formatShopError(error) {
  if (error instanceof ApiError) return error.message
  return error?.message ?? 'Ошибка магазина'
}

export function useShop({ isActive = true } = {}) {
  const { performanceMode } = useSettings()
  const shopPollMs = PERF_POLL_MS[performanceMode]?.shop ?? PERF_POLL_MS[PERF_MODES.FULL].shop
  const { columns, pageSize } = useShopLayout()
  const gridClassName = shopGridClassForColumns(columns)
  const { kut: sharedKut, syncFromShop } = usePlayerSync()
  const [kut, setKut] = useState(0)
  const [sortFilters, setSortFilters] = useState([])
  const [activeCategory, setActiveCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [priceFilter, setPriceFilter] = useState('all')
  const [sortBy, setSortBy] = useState('name')
  const [sortOrder, setSortOrder] = useState('asc')
  const [items, setItems] = useState([])
  const [page, setPage] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [totalItems, setTotalItems] = useState(0)
  const [initialLoading, setInitialLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [errorCode, setErrorCode] = useState(null)
  const [buyingItemId, setBuyingItemId] = useState(null)
  const [purchaseMessage, setPurchaseMessage] = useState(null)
  const busyRef = useRef(false)
  const toastTimeoutRef = useRef(null)
  const queryRef = useRef({
    category: 'all',
    page: 0,
    search: '',
    priceFilter: 'all',
    sortBy: 'name',
    sortOrder: 'asc',
    pageSize: 8,
  })
  const mountedRef = useRef(false)
  const prevPageSizeRef = useRef(pageSize)

  const displayKut = sharedKut ?? kut

  const applyCatalog = useCallback((data, { syncPlayer = true } = {}) => {
    setKut(data.kut ?? 0)
    setSortFilters(data.sortFilters ?? [])
    setActiveCategory(data.activeCategory ?? 'all')
    setSearch(data.search ?? queryRef.current.search ?? '')
    setDebouncedSearch(data.search ?? queryRef.current.search ?? '')
    setPriceFilter(data.priceFilter ?? queryRef.current.priceFilter ?? 'all')
    setSortBy(data.sortBy ?? queryRef.current.sortBy ?? 'name')
    setSortOrder(data.sortOrder ?? queryRef.current.sortOrder ?? 'asc')
    setItems(data.items ?? [])
    setPage(data.page ?? 0)
    setTotalPages(data.totalPages ?? 0)
    setTotalItems(data.totalItems ?? 0)
    setError(null)
    setErrorCode(null)
    if (syncPlayer) {
      syncFromShop(data)
    }
  }, [syncFromShop])

  const showPurchaseMessage = useCallback((message) => {
    setPurchaseMessage(message)
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current)
    }
    toastTimeoutRef.current = setTimeout(() => {
      setPurchaseMessage(null)
      toastTimeoutRef.current = null
    }, PURCHASE_TOAST_MS)
  }, [])

  const loadCatalog = useCallback(async (options, { silent = false } = {}) => {
    const {
      category,
      page: nextPage,
      search: searchQuery,
      priceFilter: nextPriceFilter,
      sortBy: nextSortBy,
      sortOrder: nextSortOrder,
      pageSize: nextPageSize,
    } = options

    queryRef.current = {
      category,
      page: nextPage,
      search: searchQuery,
      priceFilter: nextPriceFilter,
      sortBy: nextSortBy,
      sortOrder: nextSortOrder,
      pageSize: nextPageSize,
    }

    if (!silent) {
      setRefreshing(true)
    }
    try {
      const data = await fetchShopCatalog({
        category,
        page: nextPage,
        search: searchQuery,
        priceFilter: nextPriceFilter,
        sortBy: nextSortBy,
        sortOrder: nextSortOrder,
        pageSize: nextPageSize,
      })
      applyCatalog(data)
      return data
    } catch (e) {
      setError(formatShopError(e))
      setErrorCode(e instanceof ApiError ? e.code : 'api')
      throw e
    } finally {
      if (!silent) {
        setRefreshing(false)
      }
    }
  }, [applyCatalog])

  const currentQuery = useCallback(() => ({
    ...queryRef.current,
    pageSize,
  }), [pageSize])

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setDebouncedSearch(search.trim())
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timeoutId)
  }, [search])

  useEffect(() => {
    let cancelled = false

    if (!canAuthenticate()) {
      setError(getAuthErrorMessage())
      setErrorCode('auth')
      setInitialLoading(false)
      return undefined
    }

    if (!isActive) {
      return undefined
    }

    const isFirstLoad = !mountedRef.current
    mountedRef.current = true

    if (isFirstLoad) {
      setInitialLoading(true)
    } else {
      setRefreshing(true)
    }

    const q = currentQuery()
    loadCatalog({ ...q, page: 0, search: debouncedSearch }, { silent: !isFirstLoad })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) {
          setInitialLoading(false)
          setRefreshing(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [debouncedSearch, isActive, loadCatalog, currentQuery])

  useEffect(() => {
    if (!isActive || !canAuthenticate()) return undefined
    if (prevPageSizeRef.current === pageSize) return undefined

    prevPageSizeRef.current = pageSize
    const q = currentQuery()
    loadCatalog({ ...q, page: 0, pageSize }, { silent: !initialLoading }).catch(() => {})
    return undefined
  }, [pageSize, isActive, loadCatalog, currentQuery, initialLoading])

  useEffect(() => {
    if (!isActive || !canAuthenticate()) {
      return undefined
    }

    let intervalId = null

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId)
        intervalId = null
      }
    }

    const poll = () => {
      if (busyRef.current || initialLoading) return
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      loadCatalog(currentQuery(), { silent: true }).catch((error) => {
        if (error instanceof ApiError && error.code === 'auth') {
          stopPolling()
          return
        }
        reportClientError({
          code: 'ERR_SHOP_POLL',
          message: error?.message ?? '',
          path: '/api/shop/catalog',
          context: 'poll',
        })
      })
    }

    intervalId = window.setInterval(poll, shopPollMs)

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        poll()
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      stopPolling()
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [initialLoading, isActive, shopPollMs, loadCatalog, currentQuery])

  useEffect(() => {
    const timeout = toastTimeoutRef.current
    return () => {
      if (timeout) clearTimeout(timeout)
    }
  }, [])

  const runCatalogAction = useCallback(async (action) => {
    if (busyRef.current) return
    busyRef.current = true
    setRefreshing(true)
    setError(null)
    setErrorCode(null)
    try {
      await action()
    } catch (e) {
      setError(formatShopError(e))
      setErrorCode(e instanceof ApiError ? e.code : 'api')
    } finally {
      busyRef.current = false
      setRefreshing(false)
    }
  }, [])

  const selectSort = useCallback(async (filterId) => {
    if (filterId === activeCategory) return
    const q = currentQuery()
    await runCatalogAction(() => loadCatalog({ ...q, category: filterId, page: 0 }))
  }, [activeCategory, currentQuery, loadCatalog, runCatalogAction])

  const resetSort = useCallback(async () => {
    if (activeCategory === 'all' && !debouncedSearch && priceFilter === 'all') return
    setSearch('')
    const q = currentQuery()
    await runCatalogAction(() => loadCatalog({
      ...q,
      category: 'all',
      page: 0,
      search: '',
      priceFilter: 'all',
    }))
  }, [activeCategory, currentQuery, debouncedSearch, loadCatalog, priceFilter, runCatalogAction])

  const goToPage = useCallback(async (nextPage) => {
    if (nextPage < 0 || nextPage >= totalPages) return
    const q = currentQuery()
    await runCatalogAction(() => loadCatalog({ ...q, page: nextPage }))
  }, [currentQuery, loadCatalog, runCatalogAction, totalPages])

  const changePriceFilter = useCallback(async (nextFilter) => {
    if (nextFilter === priceFilter) return
    const q = currentQuery()
    await runCatalogAction(() => loadCatalog({ ...q, priceFilter: nextFilter, page: 0 }))
  }, [currentQuery, loadCatalog, priceFilter, runCatalogAction])

  const changeSortBy = useCallback(async (nextSortBy) => {
    if (nextSortBy === sortBy) return
    const q = currentQuery()
    await runCatalogAction(() => loadCatalog({ ...q, sortBy: nextSortBy, page: 0 }))
  }, [currentQuery, loadCatalog, runCatalogAction, sortBy])

  const changeSortOrder = useCallback(async (nextSortOrder) => {
    if (nextSortOrder === sortOrder) return
    const q = currentQuery()
    await runCatalogAction(() => loadCatalog({ ...q, sortOrder: nextSortOrder, page: 0 }))
  }, [currentQuery, loadCatalog, runCatalogAction, sortOrder])

  const changeSort = useCallback(async (nextSortBy, nextSortOrder) => {
    if (nextSortBy === sortBy && nextSortOrder === sortOrder) return
    const q = currentQuery()
    await runCatalogAction(() =>
      loadCatalog({ ...q, sortBy: nextSortBy, sortOrder: nextSortOrder, page: 0 }),
    )
  }, [currentQuery, loadCatalog, runCatalogAction, sortBy, sortOrder])

  const buyItem = useCallback(async (itemId, quantity = 1) => {
    if (busyRef.current || buyingItemId) return null
    busyRef.current = true
    setBuyingItemId(itemId)
    setError(null)
    setErrorCode(null)
    try {
      const q = currentQuery()
      const data = await buyShopItem(itemId, { ...q, quantity })
      applyCatalog(data)
      const purchased = data.purchased
      if (purchased) {
        const paid = purchased.paid ?? 0
        const qty = purchased.quantity ?? 1
        const paidText = paid > 0 ? ` за ${paid} кут` : ''
        showPurchaseMessage(`Вы купили: ${purchased.name} ×${qty}${paidText}`)
      }
      return data
    } catch (e) {
      setError(formatShopError(e))
      setErrorCode(e instanceof ApiError ? e.code : 'api')
      throw e
    } finally {
      busyRef.current = false
      setBuyingItemId(null)
    }
  }, [
    applyCatalog,
    buyingItemId,
    currentQuery,
    showPurchaseMessage,
  ])

  return {
    kut: displayKut,
    sortFilters,
    activeCategory,
    search,
    setSearch,
    priceFilter,
    sortBy,
    sortOrder,
    items,
    page,
    totalPages,
    totalItems,
    pageSize,
    columns,
    gridClassName,
    initialLoading,
    refreshing,
    loading: initialLoading || refreshing,
    error,
    errorCode,
    buyingItemId,
    purchaseMessage,
    selectSort,
    resetSort,
    goToPage,
    changePriceFilter,
    changeSortBy,
    changeSortOrder,
    changeSort,
    buyItem,
  }
}
