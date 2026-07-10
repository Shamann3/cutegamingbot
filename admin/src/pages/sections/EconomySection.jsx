import { useCallback, useEffect, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import AdminSelect from '../../components/AdminSelect'
import {
  bulkGrantKut,
  fetchEconomyDex,
  fetchEconomyOverview,
  patchEconomyDexItem,
  saveEconomySettings,
} from '../../lib/adminClient'
import { parseRequiredIntFields } from '../../lib/formNumbers'
import { notifyAdmin } from '../../lib/notify'

function formatKut(value) {
  if (value == null) return '-'
  return Number(value).toLocaleString('ru-RU')
}

function DexRow({ item, onSaved }) {
  const [price, setPrice] = useState(String(item.price ?? 0))
  const [dis, setDis] = useState(String(item.dis ?? 0))
  const [remains, setRemains] = useState(String(item.remains ?? 0))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setPrice(String(item.price ?? 0))
    setDis(String(item.dis ?? 0))
    setRemains(String(item.remains ?? 0))
  }, [item])

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const updated = await patchEconomyDexItem(item.id, {
        price: Number(price),
        dis: Number(dis),
        remains: Number(remains),
      })
      onSaved?.(updated)
      setPrice(String(updated.price ?? 0))
      setDis(String(updated.dis ?? 0))
      setRemains(String(updated.remains ?? 0))
      notifyAdmin(`Dex «${updated.name ?? updated.id}» обновлён`)
    } catch (err) {
      const message = err.message || 'Ошибка сохранения'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr>
      <td className="panel-economy-dex-id">{item.id}</td>
      <td>
        {item.emoji} {item.name}
      </td>
      <td>
        <input
          className="panel-economy-dex-input"
          value={price}
          onChange={(e) => setPrice(e.target.value.replace(/[^\d]/g, ''))}
          disabled={saving}
        />
      </td>
      <td>
        <input
          className="panel-economy-dex-input"
          value={dis}
          onChange={(e) => setDis(e.target.value.replace(/[^\d]/g, ''))}
          disabled={saving}
        />
      </td>
      <td className="panel-economy-dex-effective">{formatKut(item.effectivePrice)}</td>
      <td>
        <input
          className="panel-economy-dex-input"
          value={remains}
          onChange={(e) => setRemains(e.target.value.replace(/[^\d]/g, ''))}
          disabled={saving}
        />
      </td>
      <td>
        <button
          type="button"
          className="panel-users-btn"
          disabled={saving}
          onClick={handleSave}
        >
          {saving ? '…' : 'OK'}
        </button>
        {error && <span className="panel-economy-inline-error">{error}</span>}
      </td>
    </tr>
  )
}

export default function EconomySection() {
  const [overview, setOverview] = useState(null)
  const [dex, setDex] = useState({ items: [], total: 0 })
  const [dexQuery, setDexQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [dexLoading, setDexLoading] = useState(false)
  const [savingSettings, setSavingSettings] = useState(false)
  const [granting, setGranting] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const [defaultBalance, setDefaultBalance] = useState('')
  const [plotPriceStep, setPlotPriceStep] = useState('')
  const [clearCost, setClearCost] = useState('')

  const [grantDelta, setGrantDelta] = useState('')
  const [grantTarget, setGrantTarget] = useState('all')
  const [grantNote, setGrantNote] = useState('')
  const [grantDialogOpen, setGrantDialogOpen] = useState(false)

  const applyOverview = useCallback((data) => {
    setOverview(data)
    const s = data?.settings
    if (s) {
      setDefaultBalance(String(s.defaultBalance ?? ''))
      setPlotPriceStep(String(s.plotPriceStep ?? ''))
      setClearCost(String(s.clearCost ?? ''))
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

  const loadDex = useCallback(async (query) => {
    setDexLoading(true)
    try {
      const data = await fetchEconomyDex({ q: (query ?? '').trim() })
      setDex(data)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить dex')
    } finally {
      setDexLoading(false)
    }
  }, [])

  useEffect(() => {
    loadOverview()
    loadDex('')
  }, [loadOverview, loadDex])

  const handleSaveSettings = async () => {
    setError('')
    setInfo('')
    let payload
    try {
      payload = parseRequiredIntFields(
        {
          defaultBalance,
          plotPriceStep,
          clearCost,
        },
        {
          defaultBalance: 'Стартовый баланс',
          plotPriceStep: 'Шаг цены грядки',
          clearCost: 'Стоимость очистки',
        },
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
      const message = 'Укажите сумму kut (можно отрицательную для списания)'
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
  const plots = overview?.plots || []
  const craft = overview?.craftRecipes || []
  const envDefaults = overview?.settings?.envDefaults

  return (
    <div className="panel-economy">
      <AdminActionModal
        open={grantDialogOpen}
        title="Массовая выдача kut?"
        description={
          grantTarget === 'online'
            ? `Выдать ${grantDelta} kut онлайн-игрокам. Текст из поля «Комментарий» уйдёт в игрового бота.`
            : `Выдать ${grantDelta} kut всем игрокам. Текст из поля «Комментарий» уйдёт в игрового бота.`
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
        <p className="panel-page-lead">Баланс kut, магазин dex, грядки и массовые ивенты</p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
      </article>

      <div className="panel-economy-stats">
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Kut в системе</p>
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
          <p className="panel-shelf-muted">В продаже / всего в dex</p>
        </article>
      </div>

      <div className="panel-economy-grid-2">
        <article className="panel-shelf">
          <p className="panel-shelf-label">Настройки</p>
          <h3 className="panel-users-subtitle">Стартовый баланс и цены</h3>
          <p className="panel-shelf-muted">
            Env: balance {envDefaults?.defaultBalance}, грядка +{envDefaults?.plotPriceStep},
            очистка {envDefaults?.clearCost}
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
            <label className="panel-economy-field">
              <span>Шаг цены грядки (PLOT_PRICE_STEP)</span>
              <input
                className="panel-users-input"
                value={plotPriceStep}
                onChange={(e) => setPlotPriceStep(e.target.value.replace(/[^\d]/g, ''))}
                disabled={loading || savingSettings}
              />
            </label>
            <label className="panel-economy-field">
              <span>Очистка засохшей грядки (CLEAR_COST)</span>
              <input
                className="panel-users-input"
                value={clearCost}
                onChange={(e) => setClearCost(e.target.value.replace(/[^\d]/g, ''))}
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
          <p className="panel-shelf-label">Массовая выдача kut</p>
          <h3 className="panel-users-subtitle">Ивенты</h3>
          <div className="panel-economy-settings-form">
            <label className="panel-economy-field">
              <span>Сумма (± kut)</span>
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
          <h3 className="panel-users-subtitle">Стоимость покупки</h3>
          <p className="panel-shelf-muted">#1 бесплатна при регистрации</p>
          <ul className="panel-economy-plot-list panel-farm-plot-preview">
            {plots.map((row) => (
              <li key={row.plotId}>
                <span>Грядка #{row.plotId}</span>
                <strong>{formatKut(row.price)} kut</strong>
              </li>
            ))}
            {!loading && plots.length === 0 && (
              <li className="panel-shelf-muted">Нет данных</li>
            )}
          </ul>
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
                {row.displayName}
                {row.username && ` @${row.username}`}
                {row.banned && ' · ban'}
              </span>
              <span className="panel-economy-rich-balance">{formatKut(row.balance)} kut</span>
            </li>
          ))}
          {!loading && !(stats?.topRich || []).length && (
            <li className="panel-shelf-muted">Пока нет игроков</li>
          )}
        </ol>
      </article>

      <article className="panel-shelf panel-economy-dex">
        <p className="panel-shelf-label">Каталог dex · магазин</p>
        <form
          className="panel-users-search-form"
          onSubmit={(e) => {
            e.preventDefault()
            loadDex(dexQuery)
          }}
        >
          <input
            className="panel-users-input"
            value={dexQuery}
            onChange={(e) => setDexQuery(e.target.value)}
            placeholder="Поиск по имени или id"
            disabled={dexLoading}
          />
          <button type="submit" className="panel-users-btn" disabled={dexLoading}>
            {dexLoading ? '…' : 'Найти'}
          </button>
        </form>
        <p className="panel-shelf-muted">
          price базовая цена, dis цена со скидкой (если &gt; 0). Всего: {dex.total}
        </p>
        <div className="panel-economy-dex-wrap">
          <table className="panel-economy-dex-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Предмет</th>
                <th>price</th>
                <th>dis</th>
                <th>итого</th>
                <th>remains</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {dex.items.map((item) => (
                <DexRow
                  key={item.id}
                  item={item}
                  onSaved={(updated) => {
                    setDex((prev) => ({
                      ...prev,
                      items: prev.items.map((row) =>
                        row.id === updated.id
                          ? { ...row, ...updated, effectivePrice: updated.effectivePrice }
                          : row,
                      ),
                    }))
                    setInfo(`Dex #${updated.id} обновлён`)
                  }}
                />
              ))}
            </tbody>
          </table>
          {!dexLoading && dex.items.length === 0 && (
            <p className="panel-shelf-muted panel-economy-dex-empty">Ничего не найдено</p>
          )}
        </div>
      </article>
    </div>
  )
}
