/** Локальный показ формы. В собранной панели этой ветки нет. */
export const GROUP_PREVIEW_KEY = 'epsilon-preview'

export function isGroupPreviewKey(value) {
  return import.meta.env.DEV && String(value || '').trim() === GROUP_PREVIEW_KEY
}
