import { useCallback, useEffect, useMemo, useState } from 'react'
import '../../styles/nika.css'
import '../../styles/pr-groups.css'
import TgPhoto, { loadTgPhotoUrl } from '../../components/TgPhoto'
import ImageLightbox from '../../components/ImageLightbox'
import { showToast } from '../../components/ToastHost'
import Copyable, { CopyableId, CopyableUsername } from '../../components/Copyable'
import { useIsPhone } from '../../lib/useIsDesktop'
import {
  acceptPrGroup,
  fetchPrArchive,
  fetchPrClaim,
  fetchPrLive,
  fetchPrOverview,
  fetchPrQueue,
  fetchPrSettings,
  rejectPrGroup,
  savePrSettings,
  togglePrNika,
} from '../../lib/adminClient'

const TABS = [
  { id: 'queue', label: 'Очередь' },
  { id: 'live', label: 'Живые' },
  { id: 'archive', label: 'Архив' },
  { id: 'system', label: 'Система' },
]

function fmt(n) {
  return new Intl.NumberFormat('ru-RU').format(Number(n) || 0)
}

function roleLabel(role) {
  return role === 'owner' ? 'своя группа' : 'привёл Кут'
}

function previewSplit(total, memberCount) {
  const GIFT_MIN = 5
  const GIFT_MAX = 12
  const GIFT_IDEAL = 8
  const members = Math.max(0, Number(memberCount) || 0)
  const expected = Math.min(40, Math.max(3, Math.round(members * 0.06)))
  const sum = Math.max(0, Number(total) || 0)
  if (sum <= 0) return { total: 0, table: 0, pool: 0, gift: GIFT_IDEAL, slots: 0, expected }
  let tableNeed = Math.max(6 * GIFT_IDEAL, 30)
  if (members < 15) tableNeed = Math.max(tableNeed, 40)
  tableNeed = Math.min(tableNeed, Math.max(Math.floor(sum / 2), 0))
  const minPool = GIFT_MIN
  let table = tableNeed
  if (sum - table < minPool && sum > minPool) table = sum - minPool
  if (table < 0) table = 0
  if (table > sum) table = sum
  const pool = sum - table
  let gift = expected > 0 && Math.floor(pool / expected) >= GIFT_IDEAL
    ? Math.min(GIFT_MAX, Math.floor(pool / expected))
    : (pool >= GIFT_MIN ? GIFT_MIN : Math.max(1, pool))
  if (gift < 1) gift = 1
  const slots = gift ? Math.floor(pool / gift) : 0
  return { total: sum, table, pool, gift, slots, expected }
}

function Identity({ chatId, username, link, user }) {
  return (
    <p className="nika-id-line">
      {user?.name ? <span className="nika-id-name">{user.name}</span> : null}
      {user?.id ? <CopyableId value={user.id} label="id" /> : null}
      {user?.username ? <CopyableUsername value={user.username} /> : null}
      {chatId ? <CopyableId value={chatId} label="id группы" /> : null}
      {username ? <CopyableUsername value={username} /> : null}
      {link ? <a className="nika-id-link" href={link} target="_blank" rel="noreferrer">ссылка</a> : null}
    </p>
  )
}

function MoneyHint({ money, rec }) {
  if (!money) return null
  return (
    <p className="nika-help">
      Можно на посев {fmt(money.spendable)} · запас Ники {fmt(money.nikaReserve)} · неделя {fmt(money.weeklyLeft)}
      {rec ? ` · раскол ${fmt(rec.total)} · баланс чата ${fmt(rec.table)} · подарки ${fmt(rec.pool)} · подарок ${fmt(rec.gift)} · хватит на ${fmt(rec.slots)}` : ''}
    </p>
  )
}

function ClaimCard({ item, settings, onBack, onChanged, canDecide }) {
  const hot = item.left?.tone === 'hot'
  const [seed, setSeed] = useState(String(hot ? 0 : (item.recommend?.total ?? 0)))
  const [term, setTerm] = useState(String(item.termDays || 14))
  const [nikaOn, setNikaOn] = useState(Boolean(item.nikaOn))
  const [reasons, setReasons] = useState([])
  const [custom, setCustom] = useState('')
  const [busy, setBusy] = useState(false)
  const [viewer, setViewer] = useState(null)
  const rec = useMemo(
    () => previewSplit(Number(seed) || 0, item.memberCount || 0),
    [seed, item.memberCount],
  )
  const catalog = settings?.rejectReasons || []
  const seedNum = Number(seed) || 0
  const overBudget = seedNum > (item.money?.spendable || 0) || seedNum > (item.money?.weeklyLeft || 0)

  const decide = async (fn, ok) => {
    if (busy) return
    setBusy(true)
    try {
      await fn()
      showToast(ok)
      onChanged()
      onBack()
    } catch (err) {
      showToast(err.message || 'Не вышло', 'error')
    } finally {
      setBusy(false)
    }
  }

  const openPhoto = async (photo) => {
    if (!photo?.fileId) return
    try {
      setViewer({ src: await loadTgPhotoUrl(photo.fileId, 'full'), alt: photo.label })
    } catch {
      showToast('Кадр не открылся')
    }
  }

  return (
    <article className="nika-panel prg-card">
      <div className="nika-panel-top">
        <div>
          <h2>{item.title}</h2>
          <Identity chatId={item.chatId} username={item.username} link={item.link} user={item.user} />
          {item.creator?.id ? <Identity user={item.creator} /> : null}
          <p className="nika-help">
            {roleLabel(item.role)} · {item.memberCount || 0} чел.
            {item.addedBy?.id ? ` · добавил ${item.addedBy.name || item.addedBy.id}` : ''}
            {item.alreadyKnown ? ' · группа уже в проекте' : ''}
          </p>
          {item.left ? <p className={`prg-flag is-${item.left.tone}`}>{item.left.label}</p> : null}
          {item.burned ? <p className="prg-flag is-hot">Сгорела после кика</p> : null}
        </div>
        <button type="button" className="nika-btn" onClick={onBack}>Назад</button>
      </div>

      {(item.photos || []).length ? (
        <div className="prg-photos">
          {item.photos.map((photo) => (
            <button key={photo.fileId || photo.label} type="button" className="prg-shot" onClick={() => openPhoto(photo)}>
              <span>{photo.label}</span>
              <TgPhoto fileId={photo.fileId} size="full" alt={photo.label} />
            </button>
          ))}
        </div>
      ) : (
        <p className="nika-help">Кадров ещё нет</p>
      )}

      <MoneyHint money={item.money} rec={canDecide ? rec : item.recommend} />
      {item.status === 'live' ? (
        <p className="nika-help">
          баланс чата {fmt(item.chatBalance)} · посев на баланс {fmt(item.tableAmount)} · замок {fmt(item.seedLock)}
          · подарки {fmt(item.poolLeft)} из {fmt(item.poolAmount)}
          · комиссия {fmt(item.commission)} · ему {fmt(item.paid)}
          {item.freeze ? ` · ${item.freeze === 'admin' ? 'нет админки' : 'не публичная'}` : ''}
        </p>
      ) : null}

      {canDecide && item.status === 'pending' ? (
        <>
          <div className="prg-fields">
            <label>
              Срок, дней
              <input value={term} onChange={(e) => setTerm(e.target.value.replace(/[^\d]/g, ''))} inputMode="numeric" />
            </label>
            <label>
              Всего кут
              <input value={seed} onChange={(e) => setSeed(e.target.value.replace(/[^\d]/g, ''))} inputMode="numeric" />
            </label>
          </div>
          <label className="prg-toggle">
            <input type="checkbox" checked={nikaOn} onChange={(e) => setNikaOn(e.target.checked)} />
            Тихий долив
          </label>
          <div className="prg-reasons">
            {catalog.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`nika-btn${reasons.includes(r.id) ? ' is-on' : ''}`}
                onClick={() => setReasons((cur) => (cur.includes(r.id) ? cur.filter((x) => x !== r.id) : [...cur, r.id]))}
              >
                {r.label}
              </button>
            ))}
          </div>
          <label className="prg-custom">
            Своя причина
            <textarea value={custom} onChange={(e) => setCustom(e.target.value)} rows={2} />
          </label>
          <div className="nika-card-actions prg-actions">
            <button
              type="button"
              className="nika-btn nika-btn-danger"
              disabled={busy || (!reasons.length && !custom.trim())}
              onClick={() => decide(() => rejectPrGroup(item.id, reasons, custom), 'Отклонено')}
            >
              Отказать
            </button>
            <button
              type="button"
              className="nika-btn nika-btn-primary"
              disabled={busy || overBudget}
              onClick={() => decide(
                () => acceptPrGroup(item.id, { seed: seedNum, termDays: Number(term) || 14, nikaOn }),
                'Принято, бот шлёт посев',
              )}
            >
              Принять
            </button>
          </div>
          {overBudget ? <p className="prg-flag is-hot">Больше, чем можно потратить сейчас</p> : null}
        </>
      ) : null}

      {item.status === 'live' ? (
        <div className="nika-card-actions">
          <button
            type="button"
            className={`nika-btn${item.nikaOn ? ' is-on' : ''}`}
            disabled={busy}
            onClick={async () => {
              if (busy) return
              setBusy(true)
              try {
                await togglePrNika(item.id)
                onChanged()
              } catch (err) {
                showToast(err.message || 'Не переключилось', 'error')
              } finally {
                setBusy(false)
              }
            }}
          >
            {item.nikaOn ? 'Тихий долив включён' : 'Тихий долив выкл'}
          </button>
        </div>
      ) : null}

      {viewer ? <ImageLightbox src={viewer.src} alt={viewer.alt} onClose={() => setViewer(null)} /> : null}
    </article>
  )
}

function Row({ item, onOpen }) {
  return (
    <button type="button" className="prg-row" onClick={() => onOpen(item.id)}>
      <strong>{item.title}</strong>
      <span>{item.user?.name || item.user?.id} · {roleLabel(item.role)} · {item.memberCount || 0} чел.</span>
      {item.left ? <em className={`prg-flag is-${item.left.tone}`}>{item.left.hint}</em> : null}
      {item.freeze ? <em className="prg-flag is-warn">{item.freeze === 'admin' ? 'нет админки' : 'не публичная'}</em> : null}
    </button>
  )
}

export default function PrGroupsSection() {
  const phone = useIsPhone()
  const [tab, setTab] = useState('queue')
  const [data, setData] = useState(null)
  const [settings, setSettings] = useState(null)
  const [openId, setOpenId] = useState(null)
  const [open, setOpen] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [overview, queue, live, archive, sets] = await Promise.all([
        fetchPrOverview(),
        fetchPrQueue(),
        fetchPrLive(),
        fetchPrArchive(),
        fetchPrSettings(),
      ])
      setData({ overview, queue: queue.items || [], live: live.items || [], archive: archive.items || [] })
      setSettings(sets)
    } catch (err) {
      showToast(err.message || 'Не загрузилось', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!openId) {
      setOpen(null)
      return
    }
    fetchPrClaim(openId).then(setOpen).catch((err) => showToast(err.message || 'Карточка', 'error'))
  }, [openId])

  const list = tab === 'queue' ? data?.queue : tab === 'live' ? data?.live : data?.archive

  if (loading && !data) {
    return <section className="grp-page nika-page"><div className="nika-skel" aria-hidden="true" /></section>
  }

  return (
    <section className={`grp-page nika-page prg-page${phone ? ' is-phone' : ''}`}>
      <header className="nika-head">
        <div className="nika-head-copy">
          <h1>Пиар в группах</h1>
          <p>Новые группы: посев на баланс чата и подарки новичкам, доля комиссии с новых. Куты не печатаем.</p>
        </div>
        <div className={`nika-status${(data?.overview?.pending || 0) > 0 ? ' is-ok' : ' is-off'}`}>
          <b>{data?.overview?.pending || 0} в очереди</b>
          <span>можно {fmt(data?.overview?.spendable)} · живых {data?.overview?.live || 0}</span>
        </div>
      </header>

      <nav className="nika-seg" role="tablist" aria-label="Пиар в группах">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`nika-seg-btn${tab === t.id ? ' is-on' : ''}`}
            onClick={() => { setTab(t.id); setOpenId(null) }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab !== 'system' && open ? (
        <ClaimCard
          item={open}
          settings={settings}
          canDecide={tab === 'queue'}
          onBack={() => setOpenId(null)}
          onChanged={async () => {
            await load()
            if (openId) {
              try { setOpen(await fetchPrClaim(openId)) } catch { /* keep */ }
            }
          }}
        />
      ) : null}

      {tab !== 'system' && !open ? (
        <div className="nika-pane">
          <section className="nika-panel">
            <h2>{tab === 'queue' ? 'Очередь' : tab === 'live' ? 'Живые' : 'Архив'}</h2>
            <p className="nika-help">
              {tab === 'queue'
                ? 'Нажмите строку. Срок и всего кут — руками, раскол считает код.'
                : tab === 'live'
                  ? 'Баланс чата / баланс группы, подарки, новые, выплачено. Тихий долив — переключатель на карточке.'
                  : 'Закрытые заявки. Только просмотр.'}
            </p>
            {!(list || []).length ? (
              <article className="nika-empty">
                <h3>Пусто</h3>
                <p>{tab === 'queue' ? 'Новых сдач нет.' : tab === 'live' ? 'Живых групп нет.' : 'Архив пуст.'}</p>
              </article>
            ) : (
              <div className="prg-list">
                {(list || []).map((item) => (
                  <Row key={item.id} item={item} onOpen={setOpenId} />
                ))}
              </div>
            )}
          </section>
        </div>
      ) : null}

      {tab === 'system' ? (
        <SystemPane settings={settings} overview={data?.overview} onSave={async (next) => {
          try {
            const saved = await savePrSettings(next)
            setSettings(saved)
            showToast('Сохранили')
          } catch (err) {
            showToast(err.message || 'Не сохранилось', 'error')
          }
        }} />
      ) : null}
    </section>
  )
}

function SystemPane({ settings, overview, onSave }) {
  const [reasons, setReasons] = useState(settings?.rejectReasons || [])
  useEffect(() => { setReasons(settings?.rejectReasons || []) }, [settings])
  return (
    <div className="nika-pane">
      <section className="nika-panel">
        <h2>Как платим</h2>
        <p className="nika-help">
          35% комиссии новых · 2 живых посева · 15% spendable в неделю · тихий долив: 3 новых / 24ч, до 20 кут раз в 12 часов, не больше половины баланса группы.
        </p>
        <p className="nika-help">Сейчас можно потратить {fmt(overview?.spendable)} · неделя {fmt(overview?.weeklyLeft)}</p>
      </section>
      <section className="nika-panel">
        <h2>Причины отказа</h2>
        <p className="nika-help">Плитки на карточке очереди. Можно добавить свою.</p>
        {(reasons || []).map((r, i) => (
          <div key={r.id || i} className="prg-fields">
            <label>
              Причина
              <input
                value={r.label || ''}
                onChange={(e) => {
                  const next = reasons.slice()
                  next[i] = { ...r, label: e.target.value }
                  setReasons(next)
                }}
              />
            </label>
            <button type="button" className="nika-btn" onClick={() => setReasons(reasons.filter((_, idx) => idx !== i))}>Убрать</button>
          </div>
        ))}
        <div className="nika-card-actions">
          <button type="button" className="nika-btn" onClick={() => setReasons([...reasons, { id: `custom_${Date.now()}`, label: '' }])}>Добавить</button>
          <button type="button" className="nika-btn nika-btn-primary" onClick={() => onSave({ rejectReasons: reasons })}>Сохранить</button>
        </div>
      </section>
    </div>
  )
}
