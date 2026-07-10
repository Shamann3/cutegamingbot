/** Обратная связь в Telegram WebApp или fallback alert. */
export function notifyAdmin(message, { error = false } = {}) {
  const text = String(message || '').trim()
  if (!text) return

  const tg = window.Telegram?.WebApp
  if (typeof tg?.showAlert === 'function') {
    tg.showAlert(text)
    if (typeof tg.HapticFeedback?.notificationOccurred === 'function') {
      tg.HapticFeedback.notificationOccurred(error ? 'error' : 'success')
    }
    return
  }

  if (error) {
    window.alert(text)
  }
}
