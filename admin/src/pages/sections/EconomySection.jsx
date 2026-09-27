import { useCallback, useEffect, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import AdminSelect from '../../components/AdminSelect'
import {
  bulkGrantKut,
  fetchEconomyOverview,
  saveEconomySettings,
} from '../../lib/adminClient'
import { parseRequiredIntFields } from '../../lib/formNumbers'
import { notifyAdmin } from '../../lib/notify'
import { IdentityBits } from '../../components/Copyable'

function formatKut(value) {
  if (value == null) return '-'
  return Number(value).toLocaleString('ru-RU')
}

export default function EconomySection({ onNavigate } = {}) {
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [savingSettings, setSavingSettings] = useState(false)
  const [granting, setGranting] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const [defaultBalance, setDefaultBalance] = useState('')

  const [grantDelta, setGrantDelta] = useState('')
  const [grantTarget, setGrantTarget] = useState('all')
  const [grantNote, setGrantNote] = useState('')
  const [grantDialogOpen, setGrantDialogOpen] = useState(false)

  const applyOverview = useCallback((data) => {
    setOverview(data)
    const s = data?.settings
    if (s) {
      setDefaultBalance(String(s.defaultBalance ?? ''))
    }
  }, [])

  const loadOverview = useCallback(async () => {
    setError('')
    try {
      const data = await fetchEconomyOverview()
      applyOverview(data)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить экономику')
    } finally {
      setLoading(false)
    }
  }, [applyOverview])

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  const handleSaveSettings = async () => {
    setError('')
    setInfo('')
    let payload
    try {
      payload = parseRequiredIntFields(
        { defaultBalance },
        { defaultBalance: 'Стартовый баланс' },
      )
    } catch (err) {
      const message = err.message || 'Проверьте поля настроек'
      setError(message)
      notifyAdmin(message, { error: true })
      return
    }

    setSavingSettings(true)
    try {
      const settings = await saveEconomySettings(payload)
      const message = 'Настройки экономики сохранены'
      setInfo(message)
      notifyAdmin(message)
      setOverview((prev) => (prev ? { ...prev, settings } : prev))
      await loadOverview()
    } catch (err) {
      const message = err.message || 'Ошибка сохранения'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setSavingSettings(false)
    }
  }

  const handleGrant = () => {
    const delta = Number(grantDelta)
    if (!delta || Number.isNaN(delta)) {
      const message = 'Укажите сумму кут (можно отрицательную для списания)'
      setError(message)
      notifyAdmin(message, { error: true })
      return
    }
    setGrantDialogOpen(true)
  }

  const confirmGrant = async () => {
    const delta = Number(grantDelta)
    if (!delta || Number.isNaN(delta)) return

    setGranting(true)
    setError('')
    setInfo('')
    try {
      const result = await bulkGrantKut({
        delta,
        target: grantTarget,
        note: grantNote.trim(),
      })
      setGrantDialogOpen(false)
      const message =
        `Выдано ${result.success} игрокам` +
        (result.skipped ? `, пропущено ${result.skipped}` : '')
      setInfo(message)
      notifyAdmin(message)
      await loadOverview()
    } catch (err) {
      const message = err.message || 'Ошибка выдачи'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setGranting(false)
    }
  }

  const stats = overview?.stats
  const craft = overview?.craftRecipes || []
  const envDefaults = overview?.settings?.envDefaults

  return (
    <div className="panel-economy">
      <AdminActionModal
        open={grantDialogOpen}
        title="Массовая выдача кут?"
        description={
          grantTarget === 'online'
            ? `Выдать ${grantDelta} кут онлайн-игрокам. Текст из поля «Комментарий» уйдёт в игрового бота.`
            : `Выдать ${grantDelta} кут всем игрокам. Текст из поля «Комментарий» уйдёт в игрового бота.`
        }
        confirmText="Выдать"
        loading={granting}
        onConfirm={confirmGrant}
        onCancel={() => {
          if (!granting) setGrantDialogOpen(false)
        }}
      />
      <article className="panel-shelf panel-shelf-page panel-economy-head">
        <p className="panel-shelf-label">Economy · Экономика</p>
        <h2 className="panel-page-title">Экономика игры</h2>
        <p className="panel-page-lead">Баланс, стартовые кут и массовые ивенты</p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
      </article>

      <div className="panel-economy-stats">
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">кут в системе</p>
          <p className="panel-economy-stat-value">{loading ? '…' : formatKut(stats?.totalKut)}</p>
          <p className="panel-shelf-muted">Сумма балансов всех игроков</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Игроков</p>
          <p className="panel-economy-stat-value">{loading ? '…' : stats?.players ?? '-'}</p>
          <p className="panel-shelf-muted">
            Средний баланс: {loading ? '…' : formatKut(stats?.avgBalance)}
          </p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Магазин</p>
          <p className="panel-economy-stat-value">
            {loading ? '…' : `${stats?.shopInStock ?? 0} / ${stats?.dexItems ?? 0}`}
          </p>
          <p className="panel-shelf-muted">В продаже / всего в каталоге</p>
        </article>
      </div>

      <div className="panel-economy-grid-2">
        <article className="panel-shelf">
          <p className="panel-shelf-label">Настройки</p>
          <h3 className="panel-users-subtitle">Стартовый баланс</h3>
          <p className="panel-shelf-muted">
            Env: balance {envDefaults?.defaultBalance}
          </p>
          <p className="panel-shelf-muted">
            Цены грядок и очистка — в разделе «Ферма»
          </p>
          <div className="panel-economy-settings-form">
            <label className="panel-economy-field">
              <span>DEFAULT_BALANCE (новые игроки)</span>
              <input
                className="panel-users-input"
                value={defaultBalance}
                onChange={(e) => setDefaultBalance(e.target.value.replace(/[^\d]/g, ''))}
                disabled={loading || savingSettings}
              />
            </label>
            <button
              type="button"
              className="panel-users-btn panel-users-btn-primary panel-action-btn"
              disabled={loading || savingSettings}
              onClick={handleSaveSettings}
            >
              {savingSettings ? 'Сохраняем…' : 'Сохранить'}
            </button>
            {(error || info) && (
              <p className={`panel-action-notice${error ? ' panel-action-notice-error' : ' panel-action-notice-ok'}`}>
                {error || info}
              </p>
            )}
          </div>
        </article>

        <article className="panel-shelf">
          <p className="panel-shelf-label">Массовая выдача кут</p>
          <h3 className="panel-users-subtitle">Ивенты</h3>
          <div className="panel-economy-settings-form">
            <label className="panel-economy-field">
              <span>Сумма (± кут)</span>
              <input
                className="panel-users-input"
                value={grantDelta}
                onChange={(e) => setGrantDelta(e.target.value.replace(/[^\d-]/g, ''))}
                placeholder="500"
                disabled={granting}
              />
            </label>
            <label className="panel-economy-field">
              <span>Кому</span>
              <AdminSelect
                value={grantTarget}
                onChange={setGrantTarget}
                disabled={granting}
                options={[
                  { value: 'all', label: 'Всем (не забаненным)' },
                  { value: 'online', label: 'Только онлайн' },
                ]}
              />
            </label>
            <label className="panel-economy-field">
              <span>Комментарий (сообщение в боте)</span>
              <input
                className="panel-users-input"
                value={grantNote}
                onChange={(e) => setGrantNote(e.target.value)}
                placeholder="Новогодний ивент"
                disabled={granting}
              />
            </label>
            <button
              type="button"
              className="panel-users-btn panel-users-btn-primary panel-action-btn"
              disabled={granting || loading}
              onClick={handleGrant}
            >
              {granting ? 'Выдаём…' : 'Выдать'}
            </button>
            {info && !error && (
              <p className="panel-action-notice panel-action-notice-ok">{info}</p>
            )}
            {!loading && stats && (
              <p className="panel-shelf-muted">
                Онлайн сейчас: {stats.onlineNow}. Забаненные пропускаются.
              </p>
            )}
          </div>
        </article>
      </div>

      <div className="panel-economy-grid-2">
        <article className="panel-shelf">
          <p className="panel-shelf-label">Грядки</p>
          <h3 className="panel-users-subtitle">Цены и очистка</h3>
          <p className="panel-shelf-muted">
            Стоимость покупки грядки и очистка засохшей — во вкладке «Ферма». Здесь только баланс и ивенты.
          </p>
        </article>

        <article className="panel-shelf">
          <p className="panel-shelf-label">Крафт</p>
          <h3 className="panel-users-subtitle">Рецепты</h3>
          <p className="panel-shelf-muted">Редактирование: Контент → Крафт</p>
          {craft.length === 0 && !loading && (
            <p className="panel-shelf-muted">Рецепты не настроены</p>
          )}
          <ul className="panel-economy-craft-list">
            {craft.map((recipe) => (
              <li key={recipe.id}>
                <span className="panel-economy-craft-title">
                  #{recipe.id} · {recipe.successPercent}%
                </span>
                <span>
                  {recipe.ingredients.map((ing) => `${ing.emoji} ${ing.name}`).join(' + ')}
                  {' → '}
                  {recipe.result.emoji} {recipe.result.name}
                </span>
              </li>
            ))}
          </ul>
        </article>
      </div>

      <article className="panel-shelf panel-economy-top-rich">
        <p className="panel-shelf-label">Топ богачей</p>
        <ol className="panel-economy-rich-list">
          {(stats?.topRich || []).map((row, index) => (
            <li key={row.userId} className={row.banned ? 'panel-economy-rich-banned' : ''}>
              <span className="panel-economy-rich-rank">{index + 1}</span>
              <span className="panel-economy-rich-name">
                {row.displayName}{' '}
                <IdentityBits userId={row.userId} username={row.username} />
                {row.banned && ' · ban'}
              </span>
              <span className="panel-economy-rich-balance">{formatKut(row.balance)} кут</span>
            </li>
          ))}
          {!loading && !(stats?.topRich || []).length && (
            <li className="panel-shelf-muted">Пока нет игроков</li>
          )}
        </ol>
      </article>

      <article className="panel-shelf panel-economy-dex">
        <p className="panel-shelf-label">Каталог предметов</p>
        <p className="panel-page-lead" style={{ margin: '6px 0 12px' }}>
          Каталог предметов перенесён в Контент → Предметы
        </p>
        {typeof onNavigate === 'function' && (
          <button
            type="button"
            className="panel-users-btn panel-users-btn-primary"
            onClick={() => onNavigate('content')}
          >
            Открыть Контент → Предметы
          </button>
        )}
      </article>
    </div>
  )
}
