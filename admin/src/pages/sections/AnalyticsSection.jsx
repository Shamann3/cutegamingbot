import { useCallback, useEffect, useState } from 'react'
import {
  fetchAnalyticsCraft,
  fetchAnalyticsFarm,
  fetchAnalyticsMarket,
  fetchAnalyticsQuests,
  fetchAnalyticsRetention,
} from '../../lib/adminClient'
import { filterSectionTabs } from '../../constants/panelAccessTree'

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function fmtNum(n) {
  if (n == null) return '-'
  return Number(n).toLocaleString('ru-RU')
}

function fmtDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
    })
  } catch {
    return iso
  }
}

function fmtSeconds(s) {
  if (!s) return '-'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

const PERIOD_LABELS = { hourly: 'Часовые', daily: 'Дневные', weekly: 'Недельные' }

// ---------------------------------------------------------------------------
// Reusable chart primitives
// ---------------------------------------------------------------------------

const W = 600
const H = 160
const PAD = { top: 10, right: 12, left: 44, bottom: 28 }
const CW = W - PAD.left - PAD.right
const CH = H - PAD.top - PAD.bottom

function scaleX(i, len) {
  return PAD.left + (i / Math.max(len - 1, 1)) * CW
}
function scaleY(v, min, max) {
  const range = Math.max(max - min, 1)
  return PAD.top + CH - ((v - min) / range) * CH
}

function LineChart({ data, series, colors, yLabel = '' }) {
  if (!data || data.length === 0) return <EmptyChart />
  const allVals = series.flatMap((s) => data.map((d) => d[s] ?? 0))
  const yMax = Math.max(...allVals, 1)
  const xLabels = data.filter((_, i) => i === 0 || i === Math.floor(data.length / 2) || i === data.length - 1)
  const xLabelIdxs = new Set(
    [0, Math.floor(data.length / 2), data.length - 1].filter((i) => i >= 0 && i < data.length)
  )

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="analytics-chart" aria-label={yLabel}>
      {/* grid */}
      {[0, 0.25, 0.5, 0.75, 1].map((t) => {
        const y = PAD.top + CH * (1 - t)
        return (
          <g key={t}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke="#ffffff14" strokeWidth={1} />
            <text x={PAD.left - 4} y={y + 4} textAnchor="end" fontSize={9} fill="#6b7280">
              {fmtNum(Math.round(yMax * t))}
            </text>
          </g>
        )
      })}
      {/* lines */}
      {series.map((s, si) =>
        data.length > 1 ? (
          <polyline
            key={s}
            points={data.map((d, i) => `${scaleX(i, data.length)},${scaleY(d[s] ?? 0, 0, yMax)}`).join(' ')}
            fill="none"
            stroke={colors[si]}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ) : null
      )}
      {/* dots */}
      {series.map((s, si) =>
        data.map((d, i) => (
          <circle
            key={`${s}-${i}`}
            cx={scaleX(i, data.length)}
            cy={scaleY(d[s] ?? 0, 0, yMax)}
            r={3}
            fill={colors[si]}
          />
        ))
      )}
      {/* x labels */}
      {data.map((d, i) =>
        xLabelIdxs.has(i) ? (
          <text
            key={i}
            x={scaleX(i, data.length)}
            y={H - 4}
            textAnchor="middle"
            fontSize={9}
            fill="#6b7280"
          >
            {fmtDate(d.day || d.week)}
          </text>
        ) : null
      )}
    </svg>
  )
}

function BarChart({ data, valueKey, labelKey, colors, horizontal = false }) {
  if (!data || data.length === 0) return <EmptyChart />
  const max = Math.max(...data.map((d) => d[valueKey] ?? 0), 1)
  const barH = horizontal ? 18 : null
  const gapH = horizontal ? 6 : null
  const totalH = horizontal ? data.length * (barH + gapH) + PAD.top + PAD.bottom : H

  if (horizontal) {
    const hw = 600
    const hleft = 140
    const hright = 12
    const htop = PAD.top
    const barW = hw - hleft - hright
    return (
      <svg viewBox={`0 0 ${hw} ${totalH}`} className="analytics-chart">
        {data.map((d, i) => {
          const val = d[valueKey] ?? 0
          const w = (val / max) * barW
          const y = htop + i * (barH + gapH)
          const color = Array.isArray(colors) ? colors[i % colors.length] : colors
          return (
            <g key={i}>
              <text x={hleft - 6} y={y + barH / 2 + 4} textAnchor="end" fontSize={10} fill="#9ca3af">
                {String(d[labelKey] || '').slice(0, 16)}
              </text>
              <rect x={hleft} y={y} width={Math.max(w, 2)} height={barH} rx={3} fill={color} opacity={0.85} />
              <text x={hleft + Math.max(w, 2) + 4} y={y + barH / 2 + 4} fontSize={10} fill="#d1d5db">
                {fmtNum(val)}
              </text>
            </g>
          )
        })}
      </svg>
    )
  }

  const barW = CW / data.length - 4
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="analytics-chart">
      {data.map((d, i) => {
        const val = d[valueKey] ?? 0
        const bh = (val / max) * CH
        const x = PAD.left + i * (CW / data.length) + 2
        const y = PAD.top + CH - bh
        const color = Array.isArray(colors) ? colors[i % colors.length] : colors
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={bh} rx={2} fill={color} opacity={0.8} />
            {data.length <= 12 && (
              <text x={x + barW / 2} y={H - 4} textAnchor="middle" fontSize={9} fill="#6b7280">
                {fmtDate(d[labelKey])}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

function Heatmap({ data }) {
  if (!data || data.length === 0) return <EmptyChart />
  const DAYS = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
  const maxVal = Math.max(...data.map((d) => d.count), 1)
  const cellW = 22
  const cellH = 14
  const leftPad = 24
  const topPad = 20
  const W_MAP = leftPad + 24 * cellW + 4
  const H_MAP = topPad + 7 * cellH + 4

  const lookup = {}
  data.forEach((d) => {
    lookup[`${d.dow}-${d.hour}`] = d.count
  })

  return (
    <svg viewBox={`0 0 ${W_MAP} ${H_MAP}`} className="analytics-heatmap">
      {Array.from({ length: 24 }, (_, h) => (
        <text key={h} x={leftPad + h * cellW + cellW / 2} y={topPad - 4} textAnchor="middle" fontSize={8} fill="#6b7280">
          {h % 6 === 0 ? h : ''}
        </text>
      ))}
      {DAYS.map((day, dow) => (
        <text key={dow} x={leftPad - 3} y={topPad + dow * cellH + cellH / 2 + 4} textAnchor="end" fontSize={8} fill="#6b7280">
          {day}
        </text>
      ))}
      {DAYS.map((_, dow) =>
        Array.from({ length: 24 }, (_, h) => {
          const cnt = lookup[`${dow}-${h}`] || 0
          const intensity = cnt / maxVal
          const g = Math.round(80 + intensity * 100)
          const fill = cnt === 0 ? '#ffffff08' : `rgba(99,${g},246,${0.15 + intensity * 0.85})`
          return (
            <rect
              key={`${dow}-${h}`}
              x={leftPad + h * cellW + 1}
              y={topPad + dow * cellH + 1}
              width={cellW - 2}
              height={cellH - 2}
              rx={2}
              fill={fill}
            />
          )
        })
      )}
    </svg>
  )
}

function EmptyChart() {
  return (
    <div className="analytics-empty-chart">
      <span>Нет данных за период</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Shared UI
// ---------------------------------------------------------------------------

function StatRow({ label, value, sub }) {
  return (
    <div className="analytics-stat-row">
      <span className="analytics-stat-label">{label}</span>
      <span className="analytics-stat-value">{value}</span>
      {sub && <span className="analytics-stat-sub">{sub}</span>}
    </div>
  )
}

function SectionCard({ title, children }) {
  return (
    <div className="analytics-card">
      <h3 className="analytics-card-title">{title}</h3>
      {children}
    </div>
  )
}

function ChartLegend({ items }) {
  return (
    <div className="analytics-legend">
      {items.map(({ color, label }) => (
        <span key={label} className="analytics-legend-item">
          <span className="analytics-legend-dot" style={{ background: color }} />
          {label}
        </span>
      ))}
    </div>
  )
}

function DaysFilter({ value, onChange }) {
  return (
    <div className="analytics-days-filter">
      {[7, 14, 30, 90].map((d) => (
        <button
          key={d}
          className={`analytics-days-btn${value === d ? ' active' : ''}`}
          onClick={() => onChange(d)}
        >
          {d}д
        </button>
      ))}
    </div>
  )
}

function LoadState({ loading, error, onRetry }) {
  if (loading) return <div className="analytics-loading">Загрузка…</div>
  if (error) return (
    <div className="analytics-error">
      <span>{error}</span>
      <button onClick={onRetry} className="analytics-retry-btn">Повторить</button>
    </div>
  )
  return null
}

// ---------------------------------------------------------------------------
// Tab: Квесты
// ---------------------------------------------------------------------------

function QuestsTab({ days, onDaysChange }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await fetchAnalyticsQuests({ days }))
    } catch (e) {
      setError(e.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => { load() }, [load])

  return (
    <div className="analytics-tab-body">
      <DaysFilter value={days} onChange={onDaysChange} />
      <LoadState loading={loading} error={error} onRetry={load} />
      {data && (
        <div className="analytics-grid">
          <SectionCard title="График взятий / выполнений по дням">
            <ChartLegend items={[{ color: '#6366f1', label: 'Взято' }, { color: '#22c55e', label: 'Выполнено' }]} />
            <LineChart
              data={data.byDay}
              series={['accepted', 'completed']}
              colors={['#6366f1', '#22c55e']}
            />
          </SectionCard>

          <SectionCard title="Среднее время выполнения">
            {data.avgByPeriod.length === 0 ? (
              <EmptyChart />
            ) : (
              data.avgByPeriod.map((r) => (
                <StatRow
                  key={r.period}
                  label={PERIOD_LABELS[r.period] || r.period}
                  value={fmtSeconds(r.avgSeconds)}
                  sub={`выборка: ${r.sampleCount}`}
                />
              ))
            )}
          </SectionCard>

          <SectionCard title="Процент завершения по заданиям">
            {data.perQuest.length === 0 ? (
              <EmptyChart />
            ) : (
              <div className="analytics-table-wrap">
                <table className="analytics-table">
                  <thead>
                    <tr>
                      <th>Quest ID</th>
                      <th>Взяли</th>
                      <th>Выполнили</th>
                      <th>%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.perQuest.map((r) => (
                      <tr key={r.questId}>
                        <td>{r.questId || '-'}</td>
                        <td>{fmtNum(r.accepted)}</td>
                        <td>{fmtNum(r.completed)}</td>
                        <td>
                          <span className={`analytics-rate ${r.rate >= 50 ? 'good' : 'low'}`}>
                            {r.rate}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Популярность заданий (взятия)">
            <BarChart
              data={data.perQuest.slice(0, 10)}
              valueKey="accepted"
              labelKey="questId"
              colors="#6366f1"
              horizontal
            />
          </SectionCard>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Ферма
// ---------------------------------------------------------------------------

function FarmTab({ days, onDaysChange }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await fetchAnalyticsFarm({ days }))
    } catch (e) {
      setError(e.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => { load() }, [load])

  return (
    <div className="analytics-tab-body">
      <DaysFilter value={days} onChange={onDaysChange} />
      <LoadState loading={loading} error={error} onRetry={load} />
      {data && (
        <div className="analytics-grid">
          <SectionCard title="Соотношение посаженных → собранных → засохших">
            <div className="analytics-ratio-bar">
              {[
                { label: 'Посажено', value: data.ratios.planted, color: '#6366f1' },
                { label: 'Собрано', value: data.ratios.harvested, color: '#22c55e' },
                { label: 'Засохло', value: data.ratios.withered, color: '#ef4444' },
                { label: 'Полито', value: data.ratios.watered, color: '#38bdf8' },
              ].map((item) => (
                <div key={item.label} className="analytics-ratio-item">
                  <div className="analytics-ratio-dot" style={{ background: item.color }} />
                  <div className="analytics-ratio-label">{item.label}</div>
                  <div className="analytics-ratio-val">{fmtNum(item.value)}</div>
                </div>
              ))}
            </div>
            <div className="analytics-loss-rate">
              Потери (посажено − собрано): <strong>{data.ratios.lossRate}%</strong>
            </div>
          </SectionCard>

          <SectionCard title="Активность фермы по дням">
            <ChartLegend items={[
              { color: '#6366f1', label: 'Посадка' },
              { color: '#22c55e', label: 'Сбор' },
              { color: '#38bdf8', label: 'Полив' },
            ]} />
            <LineChart
              data={data.byDay}
              series={['planted', 'harvested', 'watered']}
              colors={['#6366f1', '#22c55e', '#38bdf8']}
            />
          </SectionCard>

          <SectionCard title="Топ культур по посадкам">
            <BarChart
              data={data.topCrops.slice(0, 12)}
              valueKey="plants"
              labelKey="cropId"
              colors="#a78bfa"
              horizontal
            />
          </SectionCard>

          <SectionCard title={`Тепловая карта активности (UTC, ${days} дней)`}>
            <p className="analytics-hint">Цвет = количество действий (посадка + полив + сбор) по часу и дню недели</p>
            <Heatmap data={data.heatmap} />
          </SectionCard>

          <SectionCard title="Грядки">
            <StatRow label="Среднее грядок на игрока" value={String(data.avgPlotsPerPlayer)} />
          </SectionCard>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Биржа
// ---------------------------------------------------------------------------

function MarketTab({ days, onDaysChange }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [itemIdFilter, setItemIdFilter] = useState('')
  const [pendingItem, setPendingItem] = useState('')
  const [histPage, setHistPage] = useState(0)
  const HIST_PER_PAGE = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await fetchAnalyticsMarket({ days, itemId: itemIdFilter || null }))
    } catch (e) {
      setError(e.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }, [days, itemIdFilter])

  useEffect(() => { load() }, [load])

  const handleItemSearch = () => {
    setItemIdFilter(pendingItem.trim())
    setHistPage(0)
  }

  const histSlice = data ? data.history.slice(histPage * HIST_PER_PAGE, (histPage + 1) * HIST_PER_PAGE) : []

  return (
    <div className="analytics-tab-body">
      <div className="analytics-toolbar">
        <DaysFilter value={days} onChange={onDaysChange} />
        <div className="analytics-item-search">
          <input
            className="analytics-input"
            placeholder="ID предмета (для графика цены)"
            value={pendingItem}
            onChange={(e) => setPendingItem(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleItemSearch()}
          />
          <button className="analytics-search-btn" onClick={handleItemSearch}>Найти</button>
          {itemIdFilter && (
            <button className="analytics-clear-btn" onClick={() => { setItemIdFilter(''); setPendingItem('') }}>✕</button>
          )}
        </div>
      </div>
      <LoadState loading={loading} error={error} onRetry={load} />
      {data && (
        <div className="analytics-grid">
          <SectionCard title="Итоги биржи">
            <div className="analytics-stat-grid">
              <StatRow label="Сделок совершено" value={fmtNum(data.totals.soldCount)} />
              <StatRow label="Активных лотов" value={fmtNum(data.totals.activeCount)} />
              <StatRow label="Отменено" value={fmtNum(data.totals.cancelledCount)} />
              <StatRow label="Общий объём" value={`${fmtNum(data.totals.totalVolume)} КУТ`} />
            </div>
          </SectionCard>

          <SectionCard title="Объём сделок по дням">
            <LineChart
              data={data.volumeByDay}
              series={['transactions']}
              colors={['#f59e0b']}
            />
          </SectionCard>

          {itemIdFilter && data.priceChart.length > 0 && (
            <SectionCard title={`График цены: ${itemIdFilter}`}>
              <ChartLegend items={[
                { color: '#6366f1', label: 'Средняя цена' },
                { color: '#22c55e', label: 'Мин' },
                { color: '#ef4444', label: 'Макс' },
              ]} />
              <LineChart
                data={data.priceChart}
                series={['avgPrice', 'minPrice', 'maxPrice']}
                colors={['#6366f1', '#22c55e', '#ef4444']}
              />
            </SectionCard>
          )}

          <SectionCard title="Топ предметов по объёму (КУТ)">
            <BarChart
              data={data.topItems.slice(0, 12)}
              valueKey="totalKut"
              labelKey="itemId"
              colors="#f59e0b"
              horizontal
            />
          </SectionCard>

          <SectionCard title="Топ продавцов">
            {data.topSellers.length === 0 ? <EmptyChart /> : (
              <div className="analytics-table-wrap">
                <table className="analytics-table">
                  <thead>
                    <tr><th>Seller ID</th><th>Сделок</th><th>Выручка</th></tr>
                  </thead>
                  <tbody>
                    {data.topSellers.map((r) => (
                      <tr key={r.sellerId}>
                        <td>{r.sellerId}</td>
                        <td>{fmtNum(r.transactions)}</td>
                        <td>{fmtNum(r.totalKut)} КУТ</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          <SectionCard title="История сделок">
            {histSlice.length === 0 ? <EmptyChart /> : (
              <>
                <div className="analytics-table-wrap">
                  <table className="analytics-table analytics-table-sm">
                    <thead>
                      <tr>
                        <th>Дата</th>
                        <th>Предмет</th>
                        <th>Кол-во</th>
                        <th>Цена</th>
                        <th>Итого</th>
                        <th>Продавец</th>
                      </tr>
                    </thead>
                    <tbody>
                      {histSlice.map((r) => (
                        <tr key={r.id}>
                          <td>{fmtDate(r.createdAt)}</td>
                          <td>{r.itemId}</td>
                          <td>{r.quantity}</td>
                          <td>{fmtNum(r.price)}</td>
                          <td>{fmtNum(r.total)}</td>
                          <td>{r.sellerId}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="analytics-pagination">
                  <button
                    className="analytics-page-btn"
                    disabled={histPage === 0}
                    onClick={() => setHistPage((p) => p - 1)}
                  >← Назад</button>
                  <span className="analytics-page-info">
                    {histPage * HIST_PER_PAGE + 1}–{Math.min((histPage + 1) * HIST_PER_PAGE, data.history.length)} из {data.history.length}
                  </span>
                  <button
                    className="analytics-page-btn"
                    disabled={(histPage + 1) * HIST_PER_PAGE >= data.history.length}
                    onClick={() => setHistPage((p) => p + 1)}
                  >Вперёд →</button>
                </div>
              </>
            )}
          </SectionCard>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Крафт
// ---------------------------------------------------------------------------

function CraftTab({ days, onDaysChange }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await fetchAnalyticsCraft({ days }))
    } catch (e) {
      setError(e.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => { load() }, [load])

  return (
    <div className="analytics-tab-body">
      <DaysFilter value={days} onChange={onDaysChange} />
      <LoadState loading={loading} error={error} onRetry={load} />
      {data && (
        <div className="analytics-grid">
          <SectionCard title="Итоги крафта">
            <div className="analytics-stat-grid">
              <StatRow label="Всего крафтов" value={fmtNum(data.totals.total)} />
              <StatRow label="Успешных" value={fmtNum(data.totals.successes)} />
              <StatRow label="Провалов" value={fmtNum(data.totals.fails)} />
              <StatRow label="Общий % успеха" value={`${data.totals.overallRate}%`} />
            </div>
          </SectionCard>

          <SectionCard title="Крафты по дням">
            <ChartLegend items={[
              { color: '#22c55e', label: 'Успех' },
              { color: '#ef4444', label: 'Провал' },
            ]} />
            <LineChart
              data={data.byDay}
              series={['successes', 'fails']}
              colors={['#22c55e', '#ef4444']}
            />
          </SectionCard>

          <SectionCard title="Рецепты реальный % успеха">
            {data.perRecipe.length === 0 ? <EmptyChart /> : (
              <div className="analytics-table-wrap">
                <table className="analytics-table">
                  <thead>
                    <tr>
                      <th>Рецепт</th>
                      <th>Всего</th>
                      <th>✅</th>
                      <th>❌</th>
                      <th>Реальный %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.perRecipe.map((r) => (
                      <tr key={r.recipeId}>
                        <td>
                          {r.resultEmoji} {r.resultName || r.recipeKey || r.recipeId}
                        </td>
                        <td>{fmtNum(r.total)}</td>
                        <td className="analytics-cell-success">{fmtNum(r.successes)}</td>
                        <td className="analytics-cell-fail">{fmtNum(r.fails)}</td>
                        <td>
                          <span className={`analytics-rate ${r.realRate >= 50 ? 'good' : 'low'}`}>
                            {r.realRate}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Топ рецептов по количеству крафтов">
            <BarChart
              data={data.perRecipe.slice(0, 10).map((r) => ({
                ...r,
                label: `${r.resultEmoji || ''} ${r.resultName || r.recipeKey || r.recipeId || ''}`.trim(),
              }))}
              valueKey="total"
              labelKey="label"
              colors="#a78bfa"
              horizontal
            />
          </SectionCard>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Удержание
// ---------------------------------------------------------------------------

function RetentionTab({ days, onDaysChange }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await fetchAnalyticsRetention({ days }))
    } catch (e) {
      setError(e.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => { load() }, [load])

  return (
    <div className="analytics-tab-body">
      <DaysFilter value={days} onChange={onDaysChange} />
      <LoadState loading={loading} error={error} onRetry={load} />
      {data && (
        <div className="analytics-grid">
          <SectionCard title="Активность игроков">
            <div className="analytics-stat-grid">
              <StatRow label="Всего игроков" value={fmtNum(data.totals.totalPlayers)} />
              <StatRow label="Активны за 24ч" value={fmtNum(data.totals.active1d)} />
              <StatRow label="Активны за 7 дней" value={fmtNum(data.totals.active7d)} />
              <StatRow label="Активны за 30 дней" value={fmtNum(data.totals.active30d)} />
            </div>
          </SectionCard>

          <SectionCard title="Retention (из последних 35 дней)">
            {data.retention.length === 0 ? (
              <p className="analytics-hint">Нет достаточно данных game_events для расчёта retention.</p>
            ) : (
              <div className="analytics-retention-blocks">
                {[
                  { day: 1, label: 'Day-1', color: '#6366f1' },
                  { day: 7, label: 'Day-7', color: '#a78bfa' },
                  { day: 30, label: 'Day-30', color: '#818cf8' },
                ].map(({ day, label, color }) => {
                  const r = data.retention.find((x) => x.day === day)
                  return (
                    <div key={day} className="analytics-retention-block" style={{ borderColor: color }}>
                      <div className="analytics-retention-label">{label}</div>
                      <div className="analytics-retention-rate" style={{ color }}>
                        {r ? `${r.rate}%` : '-'}
                      </div>
                      <div className="analytics-retention-sub">
                        {r ? `${r.returned} из ${r.total}` : 'нет данных'}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </SectionCard>

          <SectionCard title="Новые регистрации по дням">
            <BarChart
              data={data.newByDay}
              valueKey="registrations"
              labelKey="day"
              colors="#6366f1"
            />
          </SectionCard>

          <SectionCard title="Распределение баланса (всех игроков)">
            <BarChart
              data={data.balanceDist}
              valueKey="count"
              labelKey="bucket"
              colors={['#6366f1', '#818cf8', '#a78bfa', '#c4b5fd', '#ddd6fe', '#ede9fe', '#f5f3ff']}
              horizontal
            />
          </SectionCard>

          <SectionCard title="Когортный анализ (по неделям регистрации)">
            {data.cohortWeekly.length === 0 ? <EmptyChart /> : (
              <div className="analytics-table-wrap">
                <table className="analytics-table">
                  <thead>
                    <tr>
                      <th>Неделя</th>
                      <th>Зарегистрировалось</th>
                      <th>Вернулись D+1</th>
                      <th>Вернулись D+7</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.cohortWeekly.map((r) => (
                      <tr key={r.week}>
                        <td>{fmtDate(r.week)}</td>
                        <td>{fmtNum(r.registered)}</td>
                        <td>
                          {fmtNum(r.retainedD1)}
                          {r.registered > 0 && (
                            <span className="analytics-pct"> ({Math.round(r.retainedD1 / r.registered * 100)}%)</span>
                          )}
                        </td>
                        <td>
                          {fmtNum(r.retainedD7)}
                          {r.registered > 0 && (
                            <span className="analytics-pct"> ({Math.round(r.retainedD7 / r.registered * 100)}%)</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'quests', label: '🎯 Квесты' },
  { id: 'farm', label: '🌱 Ферма' },
  { id: 'market', label: '📊 Биржа' },
  { id: 'craft', label: '⚗️ Крафт' },
  { id: 'retention', label: '👥 Удержание' },
]

export default function AnalyticsSection({ panelTabs = null }) {
  const tabs = filterSectionTabs('analytics', TABS, panelTabs)
  const [tab, setTab] = useState(tabs[0]?.id || 'quests')
  const activeTab = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id
  const [days, setDays] = useState(30)

  return (
    <div className="analytics-section">
      <div className="analytics-header">
        <h2 className="analytics-title">Аналитика</h2>
      </div>

      <div className="analytics-tabs">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`analytics-tab${activeTab === t.id ? ' active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="analytics-content">
        {activeTab === 'quests'    && <QuestsTab    days={days} onDaysChange={setDays} />}
        {activeTab === 'farm'      && <FarmTab      days={days} onDaysChange={setDays} />}
        {activeTab === 'market'    && <MarketTab    days={days} onDaysChange={setDays} />}
        {activeTab === 'craft'     && <CraftTab     days={days} onDaysChange={setDays} />}
        {activeTab === 'retention' && <RetentionTab days={days} onDaysChange={setDays} />}
      </div>
    </div>
  )
}
