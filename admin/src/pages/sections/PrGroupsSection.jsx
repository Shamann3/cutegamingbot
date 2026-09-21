import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import '../../styles/nika.css'
import '../../styles/pr-groups.css'
import TgPhoto, { loadTgPhotoUrl } from '../../components/TgPhoto'
import ImageLightbox from '../../components/ImageLightbox'
import { showToast } from '../../components/ToastHost'
import { CopyableId, CopyableUsername } from '../../components/Copyable'
import { useIsPhone } from '../../lib/useIsDesktop'
import {
  acceptPrGroup,
  blockPrChat,
  fetchPrArchive,
  fetchPrClaim,
  fetchPrLive,
  fetchPrOverview,
  fetchPrPeople,
  fetchPrPerson,
  fetchPrQueue,
  fetchPrSettings,
  rejectPrGroup,
  savePrSettings,
  stopPrGroup,
  togglePrNika,
  unblockPrChat,
} from '../../lib/adminClient'

const TABS = [
  { id: 'queue', label: 'Очередь' },
  { id: 'live', label: 'Живые' },
  { id: 'people', label: 'Люди' },
  { id: 'archive', label: 'Архив' },
  { id: 'system', label: 'Система' },
]

const SEEDING = new Set(['accepting', 'fulfilling'])

function fmt(n) {
  return new Intl.NumberFormat('ru-RU').format(Number(n) || 0)
}

function when(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function roleLabel(role) {
  return role === 'owner' ? 'своя группа' : 'привёл Кут'
}

function statusLabel(status, freeze) {
  if (freeze === 'admin') return 'нет админки'
  if (freeze === 'public') return 'не публичная'
  return {
    pending: 'ждёт решения',
    accepting: 'посев',
    fulfilling: 'посев',
    live: 'живая',
    ending: 'снимаем',
    rejected: 'отказ',
    ended: 'срок вышел',
    burned: 'сгорела',
    expired: 'время вышло',
    cancelled: 'сняли',
    photos: 'фото',
    wait_confirm: 'ждёт подтверждение',
    confirm_retry: 'ещё шанс',
  }[status] || status || '—'
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

function Identity({ chatId, username, link, user, caption }) {
  return (
    <p className="nika-id-line">
      {caption ? <span className="prg-id-cap">{caption}</span> : null}
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

function Facts({ item }) {
  const rows = [
    ['Статус', statusLabel(item.status, item.freeze)],
    ['Роль', roleLabel(item.role)],
    ['Людей в группе', fmt(item.memberCount)],
    ['Баланс группы', fmt(item.chatBalance)],
    ['Посев всего', fmt(item.seedTotal)],
    ['На баланс группы', fmt(item.tableAmount)],
    ['Подарки, остаток', `${fmt(item.poolLeft)} из ${fmt(item.poolAmount)}`],
    ['Размер подарка', fmt(item.giftSize)],
    ['Замок посева', fmt(item.seedLock)],
    ['Посев проведён', item.seedApplied ? 'да' : 'нет'],
    ['Срок, дней', fmt(item.termDays)],
    ['Осталось дней', item.daysLeft == null ? '—' : fmt(item.daysLeft)],
    ['Новых людей', fmt(item.newcomers)],
    ['Подарков выдано', fmt(item.gifts)],
    ['Комиссия новых', fmt(item.commission)],
    ['Ему начислено', fmt(item.paid)],
    ['Тихий долив', item.nikaOn ? 'вкл' : 'выкл'],
    ['Группа уже в проекте', item.alreadyKnown ? 'да' : 'нет'],
    ['Создана', when(item.createdAt)],
    ['Подтверждена', when(item.confirmedAt)],
    ['Принята', when(item.acceptedAt)],
    ['Жива до', when(item.liveUntil)],
    ['Приём закрыт до', item.blockedUntil ? when(item.blockedUntil) : 'нет'],
    ['Почему закрыт', item.blockReason || '—'],
    ['Обновлена', when(item.updatedAt)],
  ]
  return (
    <dl className="prg-facts">
      {rows.map(([k, v]) => (
        <div key={k} className="prg-fact">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function ClaimCard({ item, settings, onBack, onChanged, onItem, onOpenPerson, canDecide }) {
  const hot = item.left?.tone === 'hot'
  const [seed, setSeed] = useState(String(hot ? 0 : (item.recommend?.total ?? 0)))
  const [term, setTerm] = useState(String(item.termDays || 14))
  const [nikaOn, setNikaOn] = useState(Boolean(item.nikaOn))
  const [reasons, setReasons] = useState([])
  const [custom, setCustom] = useState('')
  const [stopReason, setStopReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [viewer, setViewer] = useState(null)
  const wasSeed = useRef(item.status)
  const rec = useMemo(
    () => previewSplit(Number(seed) || 0, item.memberCount || 0),
    [seed, item.memberCount],
  )
  const catalog = settings?.rejectReasons || []
  const seedNum = Number(seed) || 0
  const overBudget = seedNum > (item.money?.spendable || 0) || seedNum > (item.money?.weeklyLeft || 0)
  const seeding = SEEDING.has(item.status)
  const pending = item.status === 'pending'
  const canStop = ['pending', 'live', 'accepting', 'fulfilling', 'photos', 'wait_confirm', 'confirm_retry', 'ending'].includes(item.status)

  useEffect(() => {
    const prev = wasSeed.current
    if (SEEDING.has(prev) && item.status === 'live') {
      showToast('Посев на балансе группы. Заявка живая.')
    }
    wasSeed.current = item.status
  }, [item.status])

  const decide = async (fn, ok, { stay } = {}) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await fn()
      showToast(ok)
      if (res?.claim) onItem?.(res.claim)
      await onChanged()
      if (!stay) onBack()
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
          <Identity chatId={item.chatId} username={item.username} link={item.link} user={item.user} caption="заявил" />
          {item.creator?.id ? <Identity user={item.creator} caption="создатель" /> : null}
          {item.addedBy?.id ? <Identity user={item.addedBy} caption="добавил бота" /> : null}
          <p className="nika-help">
            {roleLabel(item.role)} · {statusLabel(item.status, item.freeze)} · {item.memberCount || 0} чел.
            {item.alreadyKnown ? ' · группа уже в проекте' : ''}
          </p>
          {item.left ? <p className={`prg-flag is-${item.left.tone}`}>{item.left.label}</p> : null}
          {item.burned ? <p className="prg-flag is-hot">Сгорела после кика</p> : null}
          {item.rejectText ? <p className="prg-flag is-hot">{item.rejectText}</p> : null}
        </div>
        <div className="prg-card-nav">
          {item.userId ? (
            <button type="button" className="nika-btn" onClick={() => onOpenPerson?.(item.userId)}>
              Человек
            </button>
          ) : null}
          <button type="button" className="nika-btn" onClick={onBack}>Назад</button>
        </div>
      </div>

      {seeding ? (
        <p className="prg-seed">
          {item.seedApplied
            ? 'Куты уже на балансе группы. Карточка сейчас станет живой.'
            : 'Бот сейчас переводит куты на баланс группы. Карточка сама обновится.'}
        </p>
      ) : null}

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

      <Facts item={item} />

      {canDecide && pending ? (
        <>
          <div className="prg-fields">
            <label>
              Срок, дней
              <input value={term} onChange={(e) => setTerm(e.target.value.replace(/[^\d]/g, ''))} inputMode="numeric" />
            </label>
            <label className="prg-kut-label">
              Всего кут
              <MoneyHint money={item.money} rec={rec} />
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
                'Принято, бот шлёт посев и напишет в личку',
                { stay: true },
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
                await onChanged()
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

      {item.blockedUntil ? (
        <p className="prg-flag is-warn">
          Приём этой группы закрыт до {when(item.blockedUntil)}
          {item.blockReason ? ` · ${item.blockReason}` : ''}
        </p>
      ) : null}

      {canStop || item.chatId ? (
        <div className="prg-stop">
          {canStop ? (
            <>
              <label className="prg-stop-reason">
                Почему снимаем
                <input value={stopReason} onChange={(e) => setStopReason(e.target.value)} placeholder="Коротко, увидит заявитель" />
              </label>
              <button
                type="button"
                className="nika-btn nika-btn-danger"
                disabled={busy}
                onClick={() => decide(() => stopPrGroup(item.id, { days: 0, reason: stopReason }), 'Группу снимаем', { stay: true })}
              >
                Снять с программы
              </button>
              {[7, 14, 31].map((days) => (
                <button
                  key={days}
                  type="button"
                  className="nika-btn nika-btn-danger"
                  disabled={busy}
                  onClick={() => decide(
                    () => stopPrGroup(item.id, { days, reason: stopReason }),
                    `Сняли и закрыли на ${days} дн.`,
                    { stay: true },
                  )}
                >
                  Снять и закрыть на {days} дн.
                </button>
              ))}
            </>
          ) : null}
          {item.blockedUntil ? (
            <button
              type="button"
              className="nika-btn"
              disabled={busy}
              onClick={() => decide(() => unblockPrChat(item.chatId), 'Приём снова открыт', { stay: true })}
            >
              Открыть приём
            </button>
          ) : item.chatId && !canStop ? (
            [7, 14, 31].map((days) => (
              <button
                key={`block-${days}`}
                type="button"
                className="nika-btn"
                disabled={busy}
                onClick={() => decide(
                  () => blockPrChat(item.chatId, { days, reason: stopReason }),
                  `Приём закрыт на ${days} дн.`,
                  { stay: true },
                )}
              >
                Закрыть приём на {days} дн.
              </button>
            ))
          ) : null}
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
      <span>
        {item.user?.name || item.user?.id} · {roleLabel(item.role)} · {statusLabel(item.status, item.freeze)} · {item.memberCount || 0} чел.
      </span>
      {item.left ? <em className={`prg-flag is-${item.left.tone}`}>{item.left.hint}</em> : null}
      {item.freeze ? <em className="prg-flag is-warn">{item.freeze === 'admin' ? 'нет админки' : 'не публичная'}</em> : null}
      {SEEDING.has(item.status) ? <em className="prg-flag is-ok">посев идёт</em> : null}
    </button>
  )
}

function PeoplePane({ query, onQuery, items, person, onOpenPerson, onOpenClaim, loading }) {
  if (person) {
    const gift = person.gift || {}
    return (
      <div className="nika-pane">
        <section className="nika-panel">
          <div className="nika-panel-top">
            <div>
              <h2>{person.user?.name || person.user?.id}</h2>
              <Identity user={person.user} />
              <p className="nika-help">
                заявок {fmt((person.claims || []).length)} · выплачено {fmt(person.paid)}
                {gift.amount ? ` · подарок новичка ${fmt(gift.amount)}` : ''}
              </p>
            </div>
            <button type="button" className="nika-btn" onClick={() => onOpenPerson(null)}>К людям</button>
          </div>
          {!(person.claims || []).length ? (
            <article className="nika-empty">
              <h3>Нет заявок</h3>
              <p>У этого человека ещё нет сдач групп.</p>
            </article>
          ) : (
            <div className="prg-list">
              {(person.claims || []).map((item) => (
                <Row key={item.id} item={item} onOpen={onOpenClaim} />
              ))}
            </div>
          )}
        </section>
      </div>
    )
  }

  return (
    <div className="nika-pane">
      <section className="nika-panel">
        <h2>Люди</h2>
        <p className="nika-help">id, @username, имя или название группы. Откройте человека — увидите его заявки.</p>
        <label className="prg-custom">
          Поиск
          <input
            className="prg-search"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder="@username, id, группа"
          />
        </label>
        {loading && !items.length ? <p className="nika-help">Ищем…</p> : null}
        {!loading && !items.length ? (
          <article className="nika-empty">
            <h3>Никого</h3>
            <p>По этому запросу людей с заявками нет.</p>
          </article>
        ) : (
          <div className="prg-list">
            {items.map((row) => (
              <button key={row.id} type="button" className="prg-row" onClick={() => onOpenPerson(row.id)}>
                <strong>{row.name || row.id}</strong>
                <span>
                  {row.username ? `@${row.username} · ` : ''}
                  заявок {fmt(row.claims)} · ждёт {fmt(row.pending)}
                  {row.seeding ? ` · посев ${fmt(row.seeding)}` : ''}
                  · живых {fmt(row.live)} · выплачено {fmt(row.paid)}
                </span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
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
  const [peopleQ, setPeopleQ] = useState('')
  const [people, setPeople] = useState([])
  const [person, setPerson] = useState(null)
  const [peopleBusy, setPeopleBusy] = useState(false)

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

  const loadPeople = useCallback(async (needle) => {
    setPeopleBusy(true)
    try {
      const res = await fetchPrPeople(needle)
      setPeople(res.items || [])
    } catch (err) {
      showToast(err.message || 'Люди', 'error')
    } finally {
      setPeopleBusy(false)
    }
  }, [])

  const openPerson = useCallback(async (userId) => {
    if (!userId) {
      setPerson(null)
      return
    }
    try {
      setPerson(await fetchPrPerson(userId))
      setTab('people')
    } catch (err) {
      showToast(err.message || 'Карточка человека', 'error')
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (tab !== 'people') return undefined
    const timer = setTimeout(() => { loadPeople(peopleQ) }, 280)
    return () => clearTimeout(timer)
  }, [tab, peopleQ, loadPeople])

  useEffect(() => {
    if (!openId) {
      setOpen(null)
      return
    }
    fetchPrClaim(openId).then(setOpen).catch((err) => showToast(err.message || 'Карточка', 'error'))
  }, [openId])

  const needPoll = Boolean(
    (data?.queue || []).some((item) => SEEDING.has(item.status))
    || (open && SEEDING.has(open.status)),
  )

  useEffect(() => {
    if (!needPoll) return undefined
    const timer = setInterval(async () => {
      await load()
      if (openId) {
        try { setOpen(await fetchPrClaim(openId)) } catch { /* keep */ }
      }
    }, 2500)
    return () => clearInterval(timer)
  }, [needPoll, load, openId])

  const refreshOpen = async () => {
    await load()
    if (openId) {
      try { setOpen(await fetchPrClaim(openId)) } catch { /* keep */ }
    }
    if (person?.user?.id) {
      try { setPerson(await fetchPrPerson(person.user.id)) } catch { /* keep */ }
    }
  }

  const list = tab === 'queue' ? data?.queue : tab === 'live' ? data?.live : data?.archive
  const pending = data?.overview?.pending || 0
  const seeding = data?.overview?.seeding || 0
  const liveCount = data?.overview?.live || 0
  const tabCount = (id) => {
    if (id === 'queue') return pending
    if (id === 'live') return liveCount
    return 0
  }

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
        <div className={`nika-status${pending || seeding ? ' is-ok' : ' is-off'}`}>
          <b>{pending} новых</b>
          <span>
            посев {seeding} · живых {liveCount} · можно {fmt(data?.overview?.spendable)}
          </span>
        </div>
      </header>

      <nav className="nika-seg" role="tablist" aria-label="Пиар в группах">
        {TABS.map((t) => {
          const count = tabCount(t.id)
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`nika-seg-btn${tab === t.id ? ' is-on' : ''}`}
              onClick={() => { setTab(t.id); setOpenId(null) }}
            >
              {t.label}
              {count > 0 ? <i>{count > 99 ? '99+' : count}</i> : null}
            </button>
          )
        })}
      </nav>

      {tab !== 'system' && tab !== 'people' && open ? (
        <ClaimCard
          item={open}
          settings={settings}
          canDecide={tab === 'queue'}
          onBack={() => setOpenId(null)}
          onItem={setOpen}
          onOpenPerson={(userId) => { setOpenId(null); openPerson(userId) }}
          onChanged={refreshOpen}
        />
      ) : null}

      {tab === 'people' && open ? (
        <ClaimCard
          item={open}
          settings={settings}
          canDecide={open.status === 'pending'}
          onBack={() => setOpenId(null)}
          onItem={setOpen}
          onOpenPerson={(userId) => { setOpenId(null); openPerson(userId) }}
          onChanged={refreshOpen}
        />
      ) : null}

      {tab !== 'system' && tab !== 'people' && !open ? (
        <div className="nika-pane">
          <section className="nika-panel">
            <h2>{tab === 'queue' ? 'Очередь' : tab === 'live' ? 'Живые' : 'Архив'}</h2>
            <p className="nika-help">
              {tab === 'queue'
                ? 'Новые заявки и посев. После «Принять» остаётесь на карточке, пока бот не переведёт куты.'
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

      {tab === 'people' && !open ? (
        <PeoplePane
          query={peopleQ}
          onQuery={setPeopleQ}
          items={people}
          person={person}
          loading={peopleBusy}
          onOpenPerson={(id) => { if (!id) setPerson(null); else openPerson(id) }}
          onOpenClaim={setOpenId}
        />
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
