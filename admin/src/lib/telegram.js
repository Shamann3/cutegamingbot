export function initAdminTelegram() {
  const tg = window.Telegram?.WebApp
  if (!tg) return null

  tg.ready()

  const applyViewport = () => {
    tg.expand()
    if (typeof tg.requestFullscreen === 'function') {
      try {
        tg.requestFullscreen()
      } catch {
        // уже в fullscreen или клиент отклонил
      }
    }
  }

  applyViewport()
  requestAnimationFrame(applyViewport)
  window.setTimeout(applyViewport, 120)

  tg.setHeaderColor('#050508')
  tg.setBackgroundColor('#050508')
  tg.disableVerticalSwipes?.()

  const syncFullscreenClass = () => {
    document.documentElement.classList.toggle('tg-fullscreen', Boolean(tg.isFullscreen))
  }

  syncFullscreenClass()
  tg.onEvent?.('fullscreenChanged', syncFullscreenClass)
  tg.onEvent?.('viewportChanged', () => {
    if (!tg.isFullscreen) applyViewport()
  })

  return tg
}

export function getTelegramUser() {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user
  if (!user?.id) return null
  return user
}
