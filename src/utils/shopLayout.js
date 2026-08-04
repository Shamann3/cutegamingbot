/** 4 ряда на экране - pageSize = columns × rows */
export const SHOP_LAYOUT_ROWS = 4

const BREAKPOINT_TABLET = 520
const BREAKPOINT_DESKTOP = 900

export function shopLayoutForWidth(width) {
  const safeWidth = Math.max(0, Number(width) || 0)
  if (safeWidth < BREAKPOINT_TABLET) {
    return { columns: 2, pageSize: 2 * SHOP_LAYOUT_ROWS }
  }
  if (safeWidth < BREAKPOINT_DESKTOP) {
    return { columns: 3, pageSize: 3 * SHOP_LAYOUT_ROWS }
  }
  return { columns: 4, pageSize: 4 * SHOP_LAYOUT_ROWS }
}

export function shopGridClassForColumns(columns) {
  if (columns >= 4) return 'shop-shelf-grid-cols-4'
  if (columns >= 3) return 'shop-shelf-grid-cols-3'
  return 'shop-shelf-grid-cols-2'
}

/** Грядки — всегда 2 в ряд (телефон и ПК). */
export function farmGridClassForColumns(_columns) {
  return 'farm-plots-grid-cols-2'
}
