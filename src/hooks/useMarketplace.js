import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import {
  buyMarketListing,
  cancelMarketListing,
  fetchMarketCatalog,
  fetchMarketSellable,
  listMarketItem,
} from '../lib/marketClient'
import { usePlayerSync } from '../context/PlayerSyncContext'
import { useSettings } from '../context/SettingsContext'
import { PERF_MODES, PERF_POLL_MS } from '../constants/performance'
import { useShopLayout } from './useShopLayout'
import { shopGridClassForColumns } from '../utils/shopLayout'
import { canAuthenticate, getAuthErrorMessage } from '../lib/telegram'
import { reportClientError } from '../lib/errorReporter'

const TOAST_MS = 3200
const SEARCH_DEBOUNCE_MS = 350

function formatError(error) {
  if (error instanceof ApiError) return error.message
  return error?.message ?? 'Ошибка биржи'
}

export function useMarketplace({ isActive = true } = {}) {
  const { performanceMode } = useSettings()
  const pollMs = PERF_POLL_MS[performanceMode]?.shop ?? PERF_POLL_MS[PERF_MODES.FULL].shop
  const { columns, pageSize } = useShopLayout()
  const gridClassName = shopGridClassForColumns(columns)
  const { kut: sharedKut, syncFromMarket } = usePlayerSync()
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
  const [busyListingId, setBusyListingId] = useState(null)
  const [sellableItems, setSellableItems] = useState([])
  const [sellableLoading, setSellableLoading] = useState(false)
  const [sellableError, setSellableError] = useState(null)
  const [commissionPercent, setCommissionPercent] = useState(7)
  const [actionMessage, setActionMessage] = useState(null)
  const busyRef = useRef(false)
  const buyBusyRef = useRef(false)
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

  const showMessage = useCallback((message) => {
    setActionMessage(message)
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current)
    toastTimeoutRef.current = setTimeout(() => {
      setActionMessage(null)
      toastTimeoutRef.current = null
    }, TOAST_MS)
  }, [])

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
    if (data.commissionPercent != null) {
      setCommissionPercent(data.commissionPercent)
    }
    setError(null)
    setErrorCode(null)
    if (syncPlayer) syncFromMarket(data)
  }, [syncFromMarket])

  const loadCatalog = useCallback(async (options, { silent = false } = {}) => {
    const next = { ...options }
    queryRef.current = next
    if (!silent) setRefreshing(true)
    try {
      const data = await fetchMarketCatalog(next)
      applyCatalog(data)
      return data
    } catch (e) {
      setError(formatError(e))
      setErrorCode(e instanceof ApiError ? e.code : 'api')
      throw e
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [applyCatalog])

  const currentQuery = useCallback(() => ({ ...queryRef.current, pageSize }), [pageSize])

  const loadSellable = useCallback(async () => {
    setSellableLoading(true)
    setSellableError(null)
    try {
      const data = await fetchMarketSellable()
      setSellableItems(data.items ?? [])
      if (data.kut != null) setKut(data.kut)
      if (data.commissionPercent != null) setCommissionPercent(data.commissionPercent)
      return data
    } catch (e) {
      setSellableError(formatError(e))
      throw e
    } finally {
      setSellableLoading(false)
    }
  }, [])

  useEffect(() => {
    const timeoutId = setTimeout(() => setDebouncedSearch(search.trim()), SEARCH_DEBOUNCE_MS)
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
    if (!isActive) return undefined

    const isFirstLoad = !mountedRef.current
    mountedRef.current = true
    if (isFirstLoad) setInitialLoading(true)
    else setRefreshing(true)

    const q = currentQuery()
    loadCatalog({ ...q, page: 0, search: debouncedSearch }, { silent: !isFirstLoad })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) {
          setInitialLoading(false)
          setRefreshing(false)
        }
      })
    return () => { cancelled = true }
  }, [debouncedSearch, isActive, loadCatalog, currentQuery])

  useEffect(() => {
    if (!isActive || !canAuthenticate() || prevPageSizeRef.current === pageSize) return undefined
    prevPageSizeRef.current = pageSize
    loadCatalog({ ...currentQuery(), page: 0, pageSize }, { silent: !initialLoading }).catch(() => {})
    return undefined
  }, [pageSize, isActive, loadCatalog, currentQuery, initialLoading])

  useEffect(() => {
    if (!isActive || !canAuthenticate()) return undefined
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
      loadCatalog(currentQuery(), { silent: true }).catch((err) => {
        if (err instanceof ApiError && err.code === 'auth') stopPolling()
      })
    }
    intervalId = window.setInterval(poll, pollMs)
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') poll()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      stopPolling()
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [initialLoading, isActive, pollMs, loadCatalog, currentQuery])

  useEffect(() => () => {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current)
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
      setError(formatError(e))
      setErrorCode(e instanceof ApiError ? e.code : 'api')
    } finally {
      busyRef.current = false
      setRefreshing(false)
    }
  }, [])

  const selectSort = useCallback(async (filterId) => {
    if (filterId === activeCategory) return
    await runCatalogAction(() => loadCatalog({ ...currentQuery(), category: filterId, page: 0 }))
  }, [activeCategory, currentQuery, loadCatalog, runCatalogAction])

  const resetSort = useCallback(async () => {
    if (activeCategory === 'all' && !debouncedSearch && priceFilter === 'all') return
    setSearch('')
    await runCatalogAction(() => loadCatalog({
      ...currentQuery(),
      category: 'all',
      page: 0,
      search: '',
      priceFilter: 'all',
    }))
  }, [activeCategory, currentQuery, debouncedSearch, loadCatalog, priceFilter, runCatalogAction])

  const goToPage = useCallback(async (nextPage) => {
    if (nextPage < 0 || nextPage >= totalPages) return
    await runCatalogAction(() => loadCatalog({ ...currentQuery(), page: nextPage }))
  }, [currentQuery, loadCatalog, runCatalogAction, totalPages])

  const changePriceFilter = useCallback(async (nextFilter) => {
    if (nextFilter === priceFilter) return
    await runCatalogAction(() => loadCatalog({ ...currentQuery(), priceFilter: nextFilter, page: 0 }))
  }, [currentQuery, loadCatalog, priceFilter, runCatalogAction])

  const changeSort = useCallback(async (nextSortBy, nextSortOrder) => {
    if (nextSortBy === sortBy && nextSortOrder === sortOrder) return
    await runCatalogAction(() =>
      loadCatalog({ ...currentQuery(), sortBy: nextSortBy, sortOrder: nextSortOrder, page: 0 }),
    )
  }, [currentQuery, loadCatalog, runCatalogAction, sortBy, sortOrder])

  const buyListing = useCallback(async (listingId, quantity = 1) => {
    if (buyBusyRef.current) return null
    buyBusyRef.current = true
    setBusyListingId(listingId)
    setError(null)
    setErrorCode(null)
    try {
      const data = await buyMarketListing(listingId, { ...currentQuery(), quantity })
      applyCatalog(data)
      syncFromMarket(data)
      const purchased = data.purchased
      if (purchased) {
        showMessage(`Куплено: ${purchased.emoji ?? ''} ${purchased.name} ×${purchased.quantity}`)
      }
      return data
    } catch (e) {
      setError(formatError(e))
      setErrorCode(e instanceof ApiError ? e.code : 'api')
      throw e
    } finally {
      buyBusyRef.current = false
      setBusyListingId(null)
    }
  }, [applyCatalog, currentQuery, showMessage, syncFromMarket])

  const cancelListing = useCallback(async (listingId) => {
    if (buyBusyRef.current) return null
    buyBusyRef.current = true
    setBusyListingId(listingId)
    setError(null)
    setErrorCode(null)
    try {
      const data = await cancelMarketListing(listingId, currentQuery())
      applyCatalog(data)
      syncFromMarket(data)
      showMessage('Лот снят с биржи')
      return data
    } catch (e) {
      setError(formatError(e))
      setErrorCode(e instanceof ApiError ? e.code : 'api')
      throw e
    } finally {
      buyBusyRef.current = false
      setBusyListingId(null)
    }
  }, [applyCatalog, currentQuery, showMessage, syncFromMarket])

  const createListing = useCallback(async (itemId, price, quantity = 1) => {
    if (buyBusyRef.current) return null
    buyBusyRef.current = true
    setBusyListingId('__creating__')
    setError(null)
    setErrorCode(null)
    setSellableError(null)
    try {
      const data = await listMarketItem(itemId, price, { ...currentQuery(), quantity })
      applyCatalog(data)
      syncFromMarket(data)
      const listed = data.listed
      if (listed) {
        showMessage(`Выставлено: ${listed.emoji ?? ''} ${listed.name} ×${listed.quantity}`)
      }
      await loadSellable().catch(() => {})
      return data
    } catch (e) {
      const msg = formatError(e)
      // Показываем ошибку и в модалке выставления, и в общем баннере.
      setSellableError(msg)
      setError(msg)
      setErrorCode(e instanceof ApiError ? e.code : 'api')
      throw e
    } finally {
      buyBusyRef.current = false
      setBusyListingId(null)
    }
  }, [applyCatalog, currentQuery, loadSellable, showMessage, syncFromMarket])

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
    gridClassName,
    initialLoading,
    refreshing,
    error,
    errorCode,
    busyListingId,
    actionMessage,
    sellableItems,
    sellableLoading,
    sellableError,
    commissionPercent,
    selectSort,
    resetSort,
    goToPage,
    changePriceFilter,
    changeSort,
    buyListing,
    cancelListing,
    createListing,
    loadSellable,
  }
}
