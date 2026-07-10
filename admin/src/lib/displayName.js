import { getTelegramUser } from './telegram'

export function getAdminDisplayName() {
  const user = getTelegramUser()
  if (user?.first_name) {
    return user.first_name
  }
  if (user?.username) {
    return user.username
  }
  if (import.meta.env.VITE_ADMIN_DEV_NAME) {
    return import.meta.env.VITE_ADMIN_DEV_NAME
  }
  return 'admin'
}
