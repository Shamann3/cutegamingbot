const API_PREFIX = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'

const TOKEN_KEY = 'cf_admin_token'

// Токен также держим в памяти на время сессии страницы. В Telegram WebView
// (особенно на телефонах) localStorage бывает недоступен/нестабилен, из-за чего
// только что сохранённый токен не читался обратно, и панель сразу выкидывала на
// вход. Память гарантирует доставку токена в текущей сессии на любом устройстве.
let _adminTokenMemory = ''

const DEFAULT_TIMEOUT_MS = 20000

// Registered callback invoked whenever the server returns 401 (expired/invalid session).
// Set this from the top-level app shell to trigger a logout/re-login flow.
let _onUnauthorizedCb = null
export function registerUnauthorizedHandler(cb) {
  _onUnauthorizedCb = cb
}

// Причина последнего разрыва сессии (для показа на экране входа, чтобы пользователь
// понимал, почему его вернули, а не «моргнуло без объяснений»).
let _sessionEndedReason = ''
export function takeSessionEndedReason() {
  const reason = _sessionEndedReason
  _sessionEndedReason = ''
  return reason
}



function adminHeaders() {

  const headers = {

    Accept: 'application/json',

    'Content-Type': 'application/json',

  }

  // Всегда шлём обход предупреждающей страницы ngrok. В preview (продакшн-сборке)
  // import.meta.env.DEV = false, и без этого заголовка ngrok мог возвращать HTML
  // вместо JSON на телефоне — из-за чего на ПК (dev) работало, а на телефоне нет.
  // Для не-ngrok доменов заголовок безвреден (просто игнорируется).
  headers['ngrok-skip-browser-warning'] = '1'



  const initData = window.Telegram?.WebApp?.initData

  if (initData) {

    headers['X-Telegram-Init-Data'] = initData

  } else if (import.meta.env.DEV && import.meta.env.VITE_DEV_USER_ID) {

    headers['X-Dev-User-Id'] = String(import.meta.env.VITE_DEV_USER_ID)

  }



  const token = getAdminToken()

  if (token) {

    headers.Authorization = `Bearer ${token}`

  }



  return headers

}



function mapAdminFetchError(error, path) {

  if (error?.name === 'AbortError') {

    return new Error(

      'Сервер не ответил вовремя. Проверь: start-1-server.bat и start-2-vite.bat запущены.',

    )

  }

  if (error instanceof TypeError) {

    return new Error(

      'Нет связи с API. Запусти API (:8000) и Vite (:5174), затем открой панель через admin-бота.',

    )

  }

  if (error instanceof Error && error.message) {

    return error

  }

  return new Error(`Ошибка запроса ${path}`)

}



async function parseError(response) {

  try {

    const data = await response.json()

    if (typeof data?.detail === 'string') return data.detail

    if (Array.isArray(data?.detail)) return data.detail[0]?.msg || 'Ошибка запроса'

  } catch {

    // ignore

  }

  return `Ошибка ${response.status}`

}



async function readJsonResponse(response, path) {

  const text = await response.text()

  if (!text) {

    if (!response.ok) {

      throw new Error(`Ошибка ${response.status}`)

    }

    return {}

  }



  try {

    return JSON.parse(text)

  } catch {

    if (text.includes('ngrok') || text.includes('<!DOCTYPE')) {

      throw new Error(

        'Ответ не от API (похоже на страницу ngrok). Перезапусти ngrok на порт 5174 и открой панель из admin-бота.',

      )

    }

    throw new Error(

      'Сервер вернул не JSON. Убедись, что API (:8000) и Vite (:5174) запущены.',

    )

  }

}



async function adminRequest(path, { method = 'GET', body, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {

  const controller = new AbortController()

  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)



  try {

    const response = await fetch(`${API_PREFIX}${path}`, {

      method,

      headers: adminHeaders(),

      body: body != null ? JSON.stringify(body) : undefined,

      signal: controller.signal,

    })



    const data = await readJsonResponse(response, path)



    if (!response.ok) {

      const detail =

        typeof data?.detail === 'string'

          ? data.detail

          : Array.isArray(data?.detail)

            ? data.detail[0]?.msg || 'Ошибка запроса'

            : `Ошибка ${response.status}`

      if (response.status === 401) {

        const base = detail || 'Сессия завершена. Войдите снова.'

        _sessionEndedReason = `${base} [${path} · 401]`

        if (_onUnauthorizedCb) _onUnauthorizedCb(_sessionEndedReason)

      }

      const httpError = new Error(detail)

      httpError.status = response.status

      throw httpError

    }



    return data

  } catch (error) {

    throw mapAdminFetchError(error, path)

  } finally {

    window.clearTimeout(timeoutId)

  }

}



export function getAdminToken() {

  // Приоритет — токен из памяти: работает даже если localStorage заблокирован.
  if (_adminTokenMemory) return _adminTokenMemory

  try {

    const stored = localStorage.getItem(TOKEN_KEY)
    if (stored) {
      _adminTokenMemory = stored
      return stored
    }

    // Migrate legacy sessionStorage token (one-time).
    const legacy = sessionStorage.getItem(TOKEN_KEY)
    if (legacy) {
      _adminTokenMemory = legacy
      try { localStorage.setItem(TOKEN_KEY, legacy) } catch { /* ignore */ }
      try { sessionStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ }
      return legacy
    }

    return ''

  } catch {

    return _adminTokenMemory || ''

  }

}



export function setAdminToken(token) {

  // В памяти — основной источник (переживает недоступность localStorage).
  _adminTokenMemory = token || ''

  try {

    if (token) {

      localStorage.setItem(TOKEN_KEY, token)

    } else {

      localStorage.removeItem(TOKEN_KEY)

    }

    try { sessionStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ }

  } catch {

    // localStorage недоступен (например, Telegram WebView) — токен уже в памяти.

  }

}



export function getAdminSessionExpiryMs() {

  const token = getAdminToken()

  if (!token) return null

  const parts = token.split('.')

  // Support both legacy 3-part tokens (user.exp.sig)
  // and new 4-part tokens (user.iat.exp.sig)
  let exp
  if (parts.length === 4) {
    exp = Number.parseInt(parts[2], 10)
  } else if (parts.length === 3) {
    exp = Number.parseInt(parts[1], 10)
  } else {
    return null
  }

  if (!Number.isFinite(exp)) return null

  return exp * 1000

}



export function isAdminSessionValid() {

  const exp = getAdminSessionExpiryMs()

  return exp !== null && exp > Date.now()

}



async function adminFetch(path, options = {}) {
  return adminRequest(path, options)
}

export async function fetchAdminAuthStatus() {

  return adminRequest('/auth/status')

}



export async function startAdminRegistration(inviteKey) {

  return adminRequest('/auth/register/start', {

    method: 'POST',

    body: { inviteKey },

  })

}



export async function confirmAdminRegistration(setupToken, totp) {

  return adminRequest('/auth/register/confirm', {

    method: 'POST',

    body: { setupToken, totp },

  })

}



export async function revealRegisterCode(setupToken, totp) {

  return adminRequest('/auth/register/reveal-code', {

    method: 'POST',

    body: { setupToken, totp },

  })

}



export async function verifyLoginKey(loginKey) {

  return adminRequest('/auth/login/verify-key', {

    method: 'POST',

    body: { loginKey },

  })

}



export async function revealLoginCode(loginKey, totp) {

  return adminRequest('/auth/login/reveal-code', {

    method: 'POST',

    body: { loginKey, totp },

  })

}



export async function submitAdminApplication({ answers, payoutType, payoutDetails }) {

  return adminRequest('/auth/application', {

    method: 'POST',

    body: { answers, payoutType, payoutDetails },

  })

}



export async function loginAdmin(loginKey, totp) {

  return adminRequest('/auth/login', {

    method: 'POST',

    body: { loginKey, totp },

  })

}



export async function fetchAdminMe() {

  return adminRequest('/auth/me')

}



export async function acceptStaffRules() {

  return adminRequest('/staff/accept-rules', { method: 'POST', body: {} })

}



export async function fetchStaffApplications(status = 'pending') {

  const params = new URLSearchParams({ status })

  return adminRequest(`/staff/applications?${params}`)

}



export async function approveStaffApplication(applicationId, role) {

  return adminRequest(`/staff/applications/${applicationId}/approve`, {

    method: 'POST',

    body: { role },

  })

}



export async function rejectStaffApplication(applicationId, reason = '') {

  return adminRequest(`/staff/applications/${applicationId}/reject`, {

    method: 'POST',

    body: { reason },

  })

}



export async function fetchStaffMembers() {

  return adminRequest('/staff/members')

}



export async function fetchStaffSalaries() {

  return adminRequest('/staff/salaries')

}



export async function setStaffSalary(payload) {

  return adminRequest('/staff/salaries', {

    method: 'POST',

    body: payload,

  })

}



export async function approveStaffSalary(salaryId) {

  return adminRequest(`/staff/salaries/${salaryId}/approve`, { method: 'POST', body: {} })

}



export async function payStaffSalary(salaryId, { amount = null, method = null, kind = 'payment', txid = '', proof = '' } = {}) {

  return adminRequest(`/staff/salaries/${salaryId}/pay`, {

    method: 'POST',

    body: { amount, method, kind, txid, proof },

  })

}



export async function fetchStaffLedger(period = 'month', userId = null) {

  const params = new URLSearchParams({ period })

  if (userId) params.set('userId', String(userId))

  return adminRequest(`/staff/ledger?${params}`)

}



export async function fetchStaffUnpaid() {

  return adminRequest('/staff/unpaid')

}



export async function fetchMemberStats(memberId, period = 'week') {

  return adminRequest(`/staff/members/${memberId}/stats?period=${period}`)

}



export async function fetchStaffLeaderboard(period = 'week') {

  return adminRequest(`/staff/leaderboard?period=${period}`)

}



export async function sendSalaryReminder() {

  return adminRequest('/staff/reminders/send', { method: 'POST', body: {} })

}



export async function fetchPendingPayouts() {

  return adminRequest('/staff/payouts/pending')

}



export async function confirmPendingPayout(payoutId) {

  return adminRequest(`/staff/payouts/pending/${payoutId}/confirm`, { method: 'POST', body: {} })

}



export async function cancelPendingPayout(payoutId) {

  return adminRequest(`/staff/payouts/pending/${payoutId}`, { method: 'DELETE' })

}



export async function fetchMemberCard(memberId, period = 'week') {

  return adminRequest(`/staff/members/${memberId}/card?period=${period}`)

}



export async function fetchMemberAudit(memberId, { limit = 50, offset = 0 } = {}) {

  return adminRequest(`/staff/members/${memberId}/audit?limit=${limit}&offset=${offset}`)

}



export async function addMemberNote(memberId, text) {

  return adminRequest(`/staff/members/${memberId}/notes`, { method: 'POST', body: { text } })

}



export async function deleteMemberNote(memberId, noteId) {

  return adminRequest(`/staff/members/${memberId}/notes/${noteId}`, { method: 'DELETE' })

}



export async function addMemberStrike(memberId, reason) {

  return adminRequest(`/staff/members/${memberId}/strikes`, { method: 'POST', body: { reason } })

}

export async function removeStaffStrike(memberId, strikeId) {
  return adminRequest(`/staff/members/${memberId}/strikes/${strikeId}`, { method: 'DELETE' })
}



export async function setMemberAvailability(memberId, availability, until = null) {

  return adminRequest(`/staff/members/${memberId}/availability`, {

    method: 'POST', body: { availability, until },

  })

}



export async function fetchStaffShifts(userId = null) {

  const q = userId ? `?userId=${userId}` : ''

  return adminRequest(`/staff/shifts${q}`)

}



export async function addStaffShift({ userId, startsAt, endsAt, note = '' }) {

  return adminRequest('/staff/shifts', { method: 'POST', body: { userId, startsAt, endsAt, note } })

}



export async function deleteStaffShift(shiftId) {

  return adminRequest(`/staff/shifts/${shiftId}`, { method: 'DELETE' })

}



export async function fetchApplicationQuestionsAdmin() {

  return adminRequest('/staff/questions')

}



export async function upsertApplicationQuestion(payload) {

  return adminRequest('/staff/questions', { method: 'POST', body: payload })

}



export async function deleteApplicationQuestion(questionId) {

  return adminRequest(`/staff/questions/${questionId}`, { method: 'DELETE' })

}



export async function fetchApplicationQuestions() {

  return adminRequest('/auth/application-questions')

}



export async function cancelStaffSalary(salaryId) {

  return adminRequest(`/staff/salaries/${salaryId}/cancel`, { method: 'POST', body: {} })

}



export async function fetchMySalary() {

  return adminRequest('/staff/my-salary')

}

export async function claimKutSalary() {
  return adminRequest('/staff/my-salary/claim-kut', { method: 'POST' })
}



export async function appealMySalary(salaryId, reason) {

  return adminRequest(`/staff/my-salary/${salaryId}/appeal`, {

    method: 'POST',

    body: { reason },

  })

}



export async function fetchSalaryAppeals() {

  return adminRequest('/staff/appeals')

}



export async function resolveSalaryAppeal(appealId, resolution = '') {

  return adminRequest(`/staff/appeals/${appealId}/resolve`, {

    method: 'POST',

    body: { resolution },

  })

}



export async function suspendStaffMember(memberId) {

  return adminRequest(`/staff/members/${memberId}/suspend`, {

    method: 'POST',

    body: {},

  })

}



export async function unsuspendStaffMember(memberId) {

  return adminRequest(`/staff/members/${memberId}/unsuspend`, {

    method: 'POST',

    body: {},

  })

}



export async function changeMemberRole(memberId, role, reason = '') {

  return adminRequest(`/staff/members/${memberId}/role`, {

    method: 'POST',

    body: { role, reason },

  })

}



export async function fetchMemberRoleHistory(memberId) {

  return adminRequest(`/staff/members/${memberId}/history`)

}



export async function setMemberCurator(memberId, curatorId) {

  return adminRequest(`/staff/members/${memberId}/curator`, {

    method: 'POST',

    body: { curatorId },

  })

}



export async function fetchDashboardStats() {

  return adminFetch('/dashboard/stats')

}



export async function fetchOnlineSummary() {

  return adminFetch('/dashboard/online')

}



export async function fetchOnlineDay(day) {

  const params = new URLSearchParams({ day })

  return adminFetch(`/dashboard/online/day?${params}`)

}



export async function fetchOnlineRange(from, to) {

  const params = new URLSearchParams({ from, to })

  return adminFetch(`/dashboard/online/range?${params}`)

}



export async function fetchDashboardServer() {

  return adminFetch('/dashboard/server')

}



export async function fetchMaintenanceState() {
  return adminFetch('/system/maintenance')
}

export async function setMaintenanceState(enabled) {
  return adminFetch('/system/maintenance', {
    method: 'POST',
    body: { enabled },
  })
}

export async function fetchAllSettings() {
  return adminFetch('/system/settings')
}

export async function saveAllSettings(fields) {
  return adminFetch('/system/settings', { method: 'POST', body: fields })
}

export async function fetchSettingsHistory({ category = null, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (category) params.set('category', category)
  return adminFetch(`/system/settings/history?${params}`)
}



export function logoutAdmin() {
  setAdminToken('')
}

// ---------------------------------------------------------------------------
// Events & Scheduling
// ---------------------------------------------------------------------------

export async function fetchUpcomingEvents() {
  return adminFetch('/events/upcoming')
}

export async function fetchTimedQuests() {
  return adminFetch('/events/timed-quests')
}

export async function fetchScheduledBroadcasts({ limit = 50, offset = 0 } = {}) {
  return adminFetch(`/events/scheduled-broadcasts?limit=${limit}&offset=${offset}`)
}

export async function scheduleQuestEvent(questId, scheduleFields) {
  return adminFetch(`/content/quests/${questId}`, {
    method: 'PATCH',
    body: scheduleFields,
  })
}


export function hasTelegramInitData() {
  return Boolean(window.Telegram?.WebApp?.initData)
}

export async function fetchRecentAdminAccounts(limit = 30) {
  const params = new URLSearchParams({ limit: String(limit) })
  return adminFetch(`/accounts/recent?${params}`)
}

export async function searchAdminAccounts(query) {
  const params = new URLSearchParams({ q: query })
  return adminFetch(`/accounts/search?${params}`)
}

export async function fetchAdminAccount(userId) {
  return adminFetch(`/accounts/${userId}`)
}

export async function searchAdminUsers(query) {
  const params = new URLSearchParams({ q: query })
  return adminFetch(`/users/search?${params}`)
}

export async function fetchAdminUser(userId) {
  return adminFetch(`/users/${userId}`)
}

export async function fetchAdminUserAudit(userId, { limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  return adminFetch(`/users/${userId}/audit?${params}`)
}

export async function fetchAdminUserCuteHistory(userId, {
  dateFrom = '', dateTo = '', direction = '', q = '',
  onlyTransfers = false, limit = 50, offset = 0,
} = {}) {
  const params = new URLSearchParams()
  if (dateFrom) params.set('dateFrom', dateFrom)
  if (dateTo) params.set('dateTo', dateTo)
  if (direction) params.set('direction', direction)
  if (q) params.set('q', q)
  if (onlyTransfers) params.set('onlyTransfers', 'true')
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  return adminFetch(`/users/${userId}/cute-history?${params}`)
}

export async function adjustAdminUserBalance(userId, delta, note = '') {
  return adminFetch(`/users/${userId}/balance`, {
    method: 'POST',
    body: { delta, note },
  })
}

export async function adjustAdminUserItem(userId, itemId, delta, note = '') {
  return adminFetch(`/users/${userId}/items`, {
    method: 'POST',
    body: { itemId, delta, note },
  })
}

export async function setAdminUserBanned(userId, banned, reason = '', evidence = '', proofMediaId = '') {
  return adminFetch(`/users/${userId}/ban`, {
    method: 'POST',
    body: { banned, reason, evidence, proofMediaId },
  })
}

export async function fetchMemberActions(memberId) {
  return adminFetch(`/staff/members/${memberId}/actions`)
}

export async function fetchStaffComplaints(status = null) {
  const params = status ? `?status=${status}` : ''
  return adminFetch(`/staff/complaints${params}`)
}

export async function createStaffComplaint({ targetAdminId, subject = '', reason }) {
  return adminFetch('/staff/complaints', {
    method: 'POST',
    body: { targetAdminId, subject, reason },
  })
}

export async function takeStaffComplaint(complaintId) {
  return adminFetch(`/staff/complaints/${complaintId}/take`, { method: 'POST', body: {} })
}

export async function resolveStaffComplaint(complaintId, { resolution = '', penalty = 0, strike = false } = {}) {
  return adminFetch(`/staff/complaints/${complaintId}/resolve`, {
    method: 'POST',
    body: { resolution, penalty, strike },
  })
}

export async function fetchMyComplaints() {
  return adminFetch('/staff/my-complaints')
}

export async function submitComplaintEvidence(complaintId, evidence) {
  return adminFetch(`/staff/my-complaints/${complaintId}/evidence`, {
    method: 'POST',
    body: { evidence },
  })
}

export async function resetAdminUserOnboarding(userId) {
  return adminFetch(`/users/${userId}/onboarding/reset`, { method: 'POST', body: {} })
}

export async function fetchEconomyOverview() {
  return adminFetch('/economy/overview')
}

export async function fetchEconomyDex({ q = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({
    q,
    limit: String(limit),
    offset: String(offset),
  })
  return adminFetch(`/economy/dex?${params}`)
}

export async function patchEconomyDexItem(itemId, patch) {
  return adminFetch(`/economy/dex/${encodeURIComponent(itemId)}`, {
    method: 'PATCH',
    body: patch,
  })
}

export async function saveEconomySettings(settings) {
  return adminFetch('/economy/settings', {
    method: 'POST',
    body: settings,
  })
}

export async function bulkGrantKut({ delta, target, note = '' }) {
  return adminFetch('/economy/grants', {
    method: 'POST',
    body: { delta, target, note },
  })
}

export async function fetchMarketOverview() {
  return adminFetch('/market/overview')
}

export async function fetchMarketListings({
  q = '',
  itemId = '',
  sellerId = '',
  suspicious = false,
  limit = 50,
  offset = 0,
} = {}) {
  const params = new URLSearchParams({
    q,
    limit: String(limit),
    offset: String(offset),
    suspicious: suspicious ? 'true' : 'false',
  })
  if (itemId) params.set('itemId', itemId)
  if (sellerId) params.set('sellerId', String(sellerId))
  return adminFetch(`/market/listings?${params}`)
}

export async function cancelMarketListing(listingId, reason = '') {
  return adminFetch(`/market/listings/${listingId}/cancel`, {
    method: 'POST',
    body: { reason },
  })
}

export async function fetchFarmOverview() {
  return adminFetch('/farm/overview')
}

export async function saveFarmSettings(settings) {
  return adminFetch('/farm/settings', {
    method: 'POST',
    body: settings,
  })
}

export async function fetchFarmUser(userId) {
  return adminFetch(`/farm/users/${userId}`)
}

export async function resetFarmUserPlots(userId, plotId = null) {
  const params = plotId ? `?plotId=${plotId}` : ''
  return adminFetch(`/farm/users/${userId}/reset${params}`, { method: 'POST', body: {} })
}

export async function globalFarmReset() {
  return adminFetch('/farm/global-reset', { method: 'POST', body: {} })
}

export async function fetchContentOverview() {
  return adminFetch('/content/overview')
}

export async function fetchContentDex({ q = '', limit = 50, offset = 0, scope = 'all' } = {}) {
  const params = new URLSearchParams({
    q,
    limit: String(limit),
    offset: String(offset),
    scope,
  })
  return adminFetch(`/content/dex?${params}`)
}

export async function createContentDexItem(payload) {
  return adminFetch('/content/dex', { method: 'POST', body: payload })
}

export async function patchContentDexItem(itemId, payload) {
  return adminFetch(`/content/dex/${encodeURIComponent(itemId)}`, {
    method: 'PATCH',
    body: payload,
  })
}

export async function createContentCrop(payload) {
  return adminFetch('/content/crops', { method: 'POST', body: payload })
}

export async function patchContentCrop(cropId, payload) {
  return adminFetch(`/content/crops/${cropId}`, { method: 'PATCH', body: payload })
}

export async function deleteContentCrop(cropId) {
  return adminFetch(`/content/crops/${cropId}`, { method: 'DELETE' })
}

export async function createContentCraft(payload) {
  return adminFetch('/content/craft', { method: 'POST', body: payload })
}

export async function patchContentCraft(recipeId, payload) {
  return adminFetch(`/content/craft/${recipeId}`, { method: 'PATCH', body: payload })
}

export async function deleteContentCraft(recipeId) {
  return adminFetch(`/content/craft/${recipeId}`, { method: 'DELETE' })
}

export async function fetchCraftMap() {
  return adminFetch('/content/craft-map')
}

export async function saveCraftMapPositions(positions) {
  return adminFetch('/content/craft-map/positions', {
    method: 'POST',
    body: { positions },
  })
}

export async function createContentQuest(payload) {
  return adminFetch('/content/quests', { method: 'POST', body: payload })
}

export async function patchContentQuest(questId, payload) {
  return adminFetch(`/content/quests/${questId}`, { method: 'PATCH', body: payload })
}

export async function deleteContentQuest(questId) {
  return adminFetch(`/content/quests/${questId}`, { method: 'DELETE' })
}

export async function fetchGiveawaysAdmin() {
  return adminFetch('/content/giveaways')
}

export async function createGiveawayAdmin(payload) {
  return adminFetch('/content/giveaways', { method: 'POST', body: payload })
}

export async function patchGiveawayAdmin(giveawayId, payload) {
  return adminFetch(`/content/giveaways/${giveawayId}`, { method: 'PATCH', body: payload })
}

export async function deleteGiveawayAdmin(giveawayId) {
  return adminFetch(`/content/giveaways/${giveawayId}`, { method: 'DELETE' })
}

export async function completeGiveawayAdmin(giveawayId) {
  return adminFetch(`/content/giveaways/${giveawayId}/complete`, { method: 'POST' })
}

export async function fetchBroadcastOverview() {
  return adminFetch('/broadcast/overview')
}

export async function fetchBroadcastHistory({ limit = 30, offset = 0, status = '' } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (status) params.set('status', status)
  return adminFetch(`/broadcast/history?${params}`)
}

export async function cancelBroadcastRun(runId) {
  return adminFetch(`/broadcast/runs/${runId}/cancel`, { method: 'POST', body: {} })
}

export async function refreshAdminSession() {
  const data = await adminFetch('/auth/refresh', { method: 'POST', body: {} })
  if (data.token) setAdminToken(data.token)
  return data
}

export async function previewBroadcast(payload) {
  return adminFetch('/broadcast/preview', { method: 'POST', body: payload })
}

export async function countBroadcastRecipients(payload) {
  return adminFetch('/broadcast/count', { method: 'POST', body: payload })
}

export async function sendBroadcast(payload) {
  return adminFetch('/broadcast/send', { method: 'POST', body: payload })
}

export async function saveBroadcastTemplate(payload) {
  return adminFetch('/broadcast/templates', { method: 'POST', body: payload })
}

export async function deleteBroadcastTemplate(templateId) {
  return adminFetch(`/broadcast/templates/${templateId}`, { method: 'DELETE' })
}

export async function fetchDailyRotationSettings() {
  return adminFetch('/broadcast/daily-rotation')
}

export async function saveDailyRotationSettings(payload) {
  return adminFetch('/broadcast/daily-rotation', { method: 'POST', body: payload })
}

export async function runDailyRotationNow() {
  return adminFetch('/broadcast/daily-rotation/run-now', { method: 'POST', body: {} })
}

export async function fetchBroadcastRunRecipients(runId, { limit = 50, offset = 0, status = '', channel = '' } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (status) params.set('status', status)
  if (channel) params.set('channel', channel)
  return adminFetch(`/broadcast/runs/${runId}/recipients?${params}`)
}

export async function fetchLogsOverview() {
  return adminFetch('/logs/overview')
}

export async function fetchAuditLogs({ userId = '', eventType = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (userId) params.set('userId', String(userId))
  if (eventType) params.set('eventType', eventType)
  return adminFetch(`/logs/audit?${params}`)
}

export async function fetchSystemLogs({ category = 'security', userId = '', code = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({
    category,
    limit: String(limit),
    offset: String(offset),
  })
  if (userId) params.set('userId', String(userId))
  if (code) params.set('code', code)
  return adminFetch(`/logs/system?${params}`)
}

export async function fetchTransferLogs({ userId = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (userId) params.set('userId', String(userId))
  return adminFetch(`/logs/transfers?${params}`)
}

// ---------------------------------------------------------------------------
// Extended player profile
// ---------------------------------------------------------------------------

export async function fetchPlayerQuests(userId) {
  return adminFetch(`/users/${userId}/quests`)
}

export async function fetchPlayerBans(userId) {
  return adminFetch(`/users/${userId}/bans`)
}

export async function fetchPlayerNotes(userId) {
  return adminFetch(`/users/${userId}/notes`)
}

export async function upsertPlayerNote(userId, { text, noteId = null }) {
  return adminFetch(`/users/${userId}/notes`, { method: 'POST', body: { text, noteId } })
}

export async function deletePlayerNote(userId, noteId) {
  return adminFetch(`/users/${userId}/notes/${noteId}`, { method: 'DELETE' })
}

export async function exportPlayerProfile(userId) {
  return adminFetch(`/users/${userId}/export`)
}

// ---------------------------------------------------------------------------
// Dex full CRUD
// ---------------------------------------------------------------------------

export async function fetchDexItemFull(itemId) {
  return adminFetch(`/content/dex/${itemId}`)
}

export async function updateDexItemFull(itemId, body) {
  return adminFetch(`/content/dex/${itemId}`, { method: 'PUT', body })
}

export async function deleteContentDexItem(itemId) {
  return adminFetch(`/content/dex/${itemId}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export async function fetchAnalyticsQuests({ days = 30 } = {}) {
  return adminFetch(`/analytics/quests?days=${days}`)
}

export async function fetchAnalyticsFarm({ days = 30 } = {}) {
  return adminFetch(`/analytics/farm?days=${days}`)
}

export async function fetchAnalyticsMarket({ days = 30, itemId = null } = {}) {
  const params = new URLSearchParams({ days: String(days) })
  if (itemId) params.set('itemId', itemId)
  return adminFetch(`/analytics/market?${params}`)
}

export async function fetchAnalyticsCraft({ days = 30 } = {}) {
  return adminFetch(`/analytics/craft?days=${days}`)
}

export async function fetchAnalyticsRetention({ days = 30 } = {}) {
  return adminFetch(`/analytics/retention?days=${days}`)
}

// ---------------------------------------------------------------------------
// Security: admin audit log
// ---------------------------------------------------------------------------

export async function fetchAdminAuditLog({ adminUserId, action, targetType, limit = 50, offset = 0 } = {}) {
  const p = new URLSearchParams({ limit, offset })
  if (adminUserId) p.set('admin_user_id', adminUserId)
  if (action) p.set('action', action)
  if (targetType) p.set('target_type', targetType)
  return adminFetch(`/security/audit?${p}`)
}

export async function fetchAdminAuditActions() {
  return adminFetch('/security/audit/actions')
}

// ---------------------------------------------------------------------------
// Security: IP bans
// ---------------------------------------------------------------------------

export async function fetchIpBans() {
  return adminFetch('/security/ip-bans')
}

export async function addIpBan({ ipOrCidr, reason = '', expiresAt = null }) {
  return adminFetch('/security/ip-bans', {
    method: 'POST',
    body: { ipOrCidr, reason, expiresAt },
  })
}

export async function removeIpBan(banId) {
  return adminFetch(`/security/ip-bans/${banId}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Security: sessions / 2FA
// ---------------------------------------------------------------------------

export async function fetchAdminSessions() {
  return adminFetch('/security/sessions')
}

export async function forceReauth(userId = null) {
  return adminFetch('/security/sessions/force-reauth', {
    method: 'POST',
    body: { userId },
  })
}


// ---------------------------------------------------------------------------
// Support tickets
// ---------------------------------------------------------------------------

export async function fetchSupportTickets(status = 'open') {
  const params = new URLSearchParams({ status })
  return adminRequest(`/support/tickets?${params}`)
}

export async function fetchSupportTicket(ticketId) {
  return adminRequest(`/support/tickets/${ticketId}`)
}

export async function claimSupportTicket(ticketId) {
  return adminRequest(`/support/tickets/${ticketId}/claim`, { method: 'POST' })
}

export async function replySupportTicket(ticketId, text, photoFileId = '') {
  return adminRequest(`/support/tickets/${ticketId}/reply`, {
    method: 'POST',
    body: { text, photoFileId },
  })
}

export async function closeSupportTicket(ticketId, notify = true) {
  return adminRequest(`/support/tickets/${ticketId}/close`, {
    method: 'POST',
    body: { notify },
  })
}

export async function fetchSupportStats() {
  return adminRequest('/support/stats')
}

export function getPhotoProxyUrl(fileId) {
  const prefix = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'
  const token = getAdminToken()
  return `${prefix}/photo-proxy?file_id=${encodeURIComponent(fileId)}&t=${encodeURIComponent(token || '')}`
}

export async function fetchAppeals({ status = '', limit = 50, offset = 0 } = {}) {
  const p = new URLSearchParams({ limit, offset })
  if (status) p.set('status', status)
  return adminRequest(`/appeals?${p}`)
}

export async function takeAppeal(appealId) {
  return adminRequest(`/appeals/${appealId}/take`, { method: 'POST' })
}

export async function resolveAppeal(appealId, { approve, resolution = '' }) {
  return adminRequest(`/appeals/${appealId}/resolve`, { method: 'POST', body: { approve, resolution } })
}

export async function fetchAppealMessages(appealId) {
  return adminRequest(`/appeals/${appealId}/messages`)
}

export async function sendAppealMessage(appealId, { text = '', photoFileId = '' }) {
  return adminRequest(`/appeals/${appealId}/message`, { method: 'POST', body: { text, photoFileId } })
}

function _uploadHeaders() {
  const headers = {}
  if (import.meta.env.DEV) headers['ngrok-skip-browser-warning'] = '1'
  const initData = window.Telegram?.WebApp?.initData
  if (initData) headers['X-Telegram-Init-Data'] = initData
  else if (import.meta.env.DEV && import.meta.env.VITE_DEV_USER_ID) headers['X-Dev-User-Id'] = String(import.meta.env.VITE_DEV_USER_ID)
  const token = getAdminToken()
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

async function _uploadFile(path, file, text = '') {
  const form = new FormData()
  form.append('file', file)
  if (text) form.append('text', text)
  const prefix = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'
  const resp = await fetch(`${prefix}${path}`, { method: 'POST', headers: _uploadHeaders(), body: form })
  if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.detail || 'Ошибка загрузки') }
  return resp.json()
}

async function _uploadForm(path, method, fields) {
  const form = new FormData()
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined || value === null) continue
    form.append(key, value)
  }
  const prefix = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'
  const resp = await fetch(`${prefix}${path}`, { method, headers: _uploadHeaders(), body: form })
  if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.detail || 'Ошибка запроса') }
  return resp.json()
}

export async function uploadAppealPhoto(appealId, file, text = '') {
  return _uploadFile(`/appeals/${appealId}/upload`, file, text)
}

export async function uploadTicketPhoto(ticketId, file, text = '') {
  return _uploadFile(`/support/tickets/${ticketId}/reply-with-photo`, file, text)
}

export async function uploadBanEvidence(file) {
  return _uploadFile('/users/upload-evidence', file)
}

export async function fetchPlayerInventory(userId) {
  return adminRequest(`/users/${userId}/inventory`)
}

export async function fetchModerationRecent(limit = 5) {
  return adminRequest(`/moderation/recent?limit=${limit}`)
}

export async function fetchPlayerModerationHistory(playerId) {
  return adminRequest(`/moderation/player-history/${playerId}`)
}

export async function fetchModeratorStats(period = 'week') {
  return adminRequest(`/moderation/moderator-stats?period=${period}`)
}

export async function fetchModerationLogs({ actionType = '', playerId = '', sortBy = 'date', limit = 50, offset = 0 } = {}) {
  const p = new URLSearchParams({ limit, offset, sort_by: sortBy })
  if (actionType) p.set('action_type', actionType)
  if (playerId) p.set('player_id', playerId)
  return adminRequest(`/moderation/logs?${p}`)
}

export async function deleteModerationLog(logId) {
  return adminRequest(`/moderation/logs/${logId}`, { method: 'DELETE' })
}

export async function fetchModerationProof(logId) {
  return adminRequest(`/moderation/proof/${logId}`)
}

export async function postModerationUnban(userId) {
  return adminRequest(`/moderation/unban/${userId}`, { method: 'POST' })
}

// ---------------------------------------------------------------------------
// Invite tokens
// ---------------------------------------------------------------------------

export async function deleteStaffMember(userId) {
  return adminRequest(`/staff/members/${userId}`, { method: 'DELETE' })
}

export async function fetchInviteTokens() {
  return adminRequest('/staff/invites')
}

export async function createInviteToken(label = '') {
  return adminRequest('/staff/invites', { method: 'POST', body: { label } })
}

export async function revokeInviteToken(tokenId) {
  return adminRequest(`/staff/invites/${tokenId}/revoke`, { method: 'POST' })
}

export async function deleteInviteToken(tokenId) {
  return adminRequest(`/staff/invites/${tokenId}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Group Post Campaigns
// ---------------------------------------------------------------------------

export async function fetchGroupPostCampaigns() {
  return adminFetch('/group-posts')
}

export async function createGroupPostCampaign({ label, chatIds, telegramText, buttons, intervalMinutes, photoFile }) {
  return _uploadForm('/group-posts', 'POST', {
    label: label || '',
    chat_ids: chatIds,
    telegram_text: telegramText || '',
    buttons: JSON.stringify(buttons || []),
    interval_minutes: String(intervalMinutes),
    ...(photoFile ? { photo: photoFile } : {}),
  })
}

export async function updateGroupPostCampaign(campaignId, { label, chatIds, telegramText, buttons, intervalMinutes, photoFile, clearPhoto }) {
  const fields = {}
  if (label !== undefined) fields.label = label
  if (chatIds !== undefined) fields.chat_ids = chatIds
  if (telegramText !== undefined) fields.telegram_text = telegramText
  if (buttons !== undefined) fields.buttons = JSON.stringify(buttons)
  if (intervalMinutes !== undefined) fields.interval_minutes = String(intervalMinutes)
  if (photoFile) fields.photo = photoFile
  if (clearPhoto) fields.clear_photo = 'true'
  return _uploadForm(`/group-posts/${campaignId}`, 'PATCH', fields)
}

export async function pauseGroupPostCampaign(campaignId) {
  return adminFetch(`/group-posts/${campaignId}/pause`, { method: 'POST', body: {} })
}

export async function resumeGroupPostCampaign(campaignId) {
  return adminFetch(`/group-posts/${campaignId}/resume`, { method: 'POST', body: {} })
}

export async function runGroupPostCampaignNow(campaignId) {
  return adminFetch(`/group-posts/${campaignId}/run-now`, { method: 'POST', body: {} })
}

export async function deleteGroupPostCampaign(campaignId) {
  return adminFetch(`/group-posts/${campaignId}`, { method: 'DELETE' })
}

export async function fetchGroupPostCampaignLog(campaignId, { limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return adminFetch(`/group-posts/${campaignId}/log?${params}`)
}

export async function fetchKnownChats() {
  return adminFetch('/group-posts/known-chats')
}

export async function fetchGroupPostCampaignPhotoBlob(campaignId) {
  const resp = await fetch(`${API_PREFIX}/group-posts/${campaignId}/photo`, {
    headers: adminHeaders(),
  })
  if (!resp.ok) throw new Error(`Ошибка ${resp.status}`)
  return resp.blob()
}
