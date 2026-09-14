import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import '../../styles/tiktok.css'
import TgPhoto from '../../components/TgPhoto'
import ImageLightbox from '../../components/ImageLightbox'
import { showToast } from '../../components/ToastHost'
import { getPhotoProxyUrl } from '../../lib/adminClient'
import {
  approveTiktokComment,
  approveTiktokVideo,
  fetchTiktokAccessMap,
  fetchTiktokComment,
  fetchTiktokComments,
  fetchTiktokCommentsArchive,
  fetchTiktokOverview,
  fetchTiktokSettings,
  fetchTiktokVideos,
  rejectTiktokComment,
  rejectTiktokVideo,
  saveTiktokSettings,
  saveTiktokVerdict,
} from '../../lib/adminClient'

const TABS = [
  { id: 'comments', label: 'Комментарии', hint: 'Одна заявка = 15 кадров. Красная рамка — код нашёл похожее.' },
  { id: 'videos', label: 'Видео', hint: 'Открой ссылку в TikTok, впиши просмотры. Код сам посчитает куты.' },
  { id: 'live', label: 'Живые', hint: 'Уже принятые ролики. Если игрок просит перепроверку — доплати разницу.' },
  { id: 'archive', label: 'Архив', hint: 'Закрытые дела. Здесь ничего начислять не нужно.' },
  { id: 'settings', label: 'Настройки', hint: 'Тег, причины отказа и тексты игроку. Цифры наград зафиксированы правилами.' },
]

const GUIDE_KEY = 'cf_tiktok_guide_v1'

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function playerName(user) {
  if (!user) return 'Игрок'
  if (user.displayName) return user.displayName
  if (user.username) return `@${user.username}`
  return `ID ${user.userId}`
}

function kutForViews(views, unit = 30) {
  const n = Math.max(0, Number(views) || 0)
  return Math.floor(n / 1000) * unit
}

function nextQueueItem(items, currentId) {
  if (!items?.length) return null
  if (currentId == null) return items[0]
  const idx = items.findIndex((item) => Number(item.id) === Number(currentId))
  if (idx < 0) return items[0]
  return items[idx + 1] || null
}

function shotFileId(photo) {
  return photo?.thumbFileId || photo?.fileId || ''
}

function fullFileId(photo) {
  return photo?.fileId || photo?.thumbFileId || ''
}

function LockCard({ tab, map }) {
  const info = (map?.tabs || []).find((t) => t.id === tab.id) || tab
  const roles = info.openRoles || []
  const people = info.openPeople || []
  return (
    <div className="tt-lock">
      <div className="tt-lock-seal">закрыто</div>
      <h3>{info.label || tab.label}</h3>
      <p className="tt-lock-blurb">{info.blurb || tab.hint}</p>
      <p className="tt-lock-teaser">{info.teaser}</p>
      <div className="tt-lock-who">
        <div>
          <span>Открыто должностям</span>
          <b>{roles.length ? roles.map((r) => r.label).join(', ') : 'пока никому из ролей'}</b>
        </div>
        <div>
          <span>Сейчас здесь работают</span>
          <b>{people.length ? people.map((p) => `${p.name}${p.roleLabel ? ` · ${p.roleLabel}` : ''}`).join(', ') : 'никого'}</b>
        </div>
      </div>
      <p className="tt-lock-push">Когда доверят выше — окажешься здесь. Доступ выдаёт создатель в «Админ панель».</p>
    </div>
  )
}

function Guide({ onClose }) {
  return (
    <div className="tt-guide">
      <button type="button" className="tt-guide-x" onClick={onClose} aria-label="Закрыть гид">×</button>
      <h3>Как разбирать TikTok за минуту</h3>
      <ol>
        <li>Слева очередь. Карточка открывает 15 превью сразу — полные кадры по клику, без перезагрузки страницы.</li>
        <li>Красная рамка: код нашёл похожий кадр. Сравни и отметь «копия» или «не копия». Решение за тобой.</li>
        <li>Видео: открой ссылку в TikTok, впиши просмотры. Под полем сразу видно, сколько кут уйдёт.</li>
        <li>Клавиши: A принять, R отклонить, N или J — следующее дело, Esc — к очереди.</li>
      </ol>
      <button type="button" className="tt-btn tt-btn-ok" onClick={onClose}>Понятно, к очереди</button>
    </div>
  )
}

function CommentCase({ item, onOpen }) {
  const count = item.photoCount || (item.photos || []).length
  return (
    <button type="button" className="tt-card" onClick={() => onOpen(item)}>
      <div className="tt-card-top">
        <strong>{playerName(item.user)}</strong>
        <span>{fmtDate(item.createdAt)}</span>
      </div>
      <div className="tt-card-nicks">{(item.nicks || []).map((n) => `@${n}`).join(' · ') || 'нет ников'}</div>
      <div className="tt-card-flags">
        <span>{count} фото</span>
        {item.hasSimilar ? <span className="tt-flag-hot">есть похожие · {item.matchCount}</span> : <span>уникальные</span>}
      </div>
    </button>
  )
}

function CommentWorkspace({ item, queue, onClose, onAdvance, onDecided }) {
  const [busy, setBusy] = useState(false)
  const [lightbox, setLightbox] = useState(null)
  const [compare, setCompare] = useState(null)
  const [local, setLocal] = useState(item)
  const busyRef = useRef(false)

  useEffect(() => { setLocal(item); setCompare(null) }, [item])

  const matchByIndex = useMemo(() => {
    const map = {}
    for (const m of local.matches || []) {
      const idx = m.source?.index
      if (idx == null) continue
      if (!map[idx]) map[idx] = []
      map[idx].push(m)
    }
    return map
  }, [local.matches])

  const openFull = (photo) => {
    const id = fullFileId(photo)
    if (!id) return
    setLightbox(getPhotoProxyUrl(id, 'full'))
  }

  const decide = async (fn, okText) => {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    try {
      await fn()
      showToast(okText)
      onDecided(local.id)
    } catch (err) {
      showToast(err.message || 'Ошибка')
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }

  const markPair = async (pair, verdict) => {
    const a = pair.source?.phash || pair.source?.ahash
    const b = pair.match?.phash || pair.match?.ahash
    if (!a || !b) return
    try {
      await saveTiktokVerdict(a, b, verdict)
      showToast(verdict === 'copy' ? 'Отметили как копию' : 'Отметили как разные')
      const fresh = await fetchTiktokComment(local.id)
      setLocal(fresh)
    } catch (err) {
      showToast(err.message || 'Не удалось сохранить')
    }
  }

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return
      if (document.querySelector('.img-lightbox')) return
      if (e.key === 'a' || e.key === 'A') {
        e.preventDefault()
        decide(() => approveTiktokComment(local.id), 'Принято, 5 кут ушли')
      }
      if (e.key === 'r' || e.key === 'R') {
        e.preventDefault()
        decide(() => rejectTiktokComment(local.id), 'Отклонено, игроку ушёл ответ')
      }
      if (e.key === 'n' || e.key === 'N' || e.key === 'j' || e.key === 'J') {
        e.preventDefault()
        onAdvance(local.id)
      }
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [local.id, onAdvance, onClose])

  const nextHint = nextQueueItem(queue, local.id)

  return (
    <div className="tt-work">
      <div className="tt-work-head">
        <div>
          <h3>{playerName(local.user)}</h3>
          <p>
            {(local.nicks || []).map((n) => `@${n}`).join(' · ')}
            {' · '}
            {fmtDate(local.createdAt)}
          </p>
          <div className="tt-break">
            {(local.nickBreakdown || []).map((row) => (
              <span key={row.nick}>@{row.nick}: {row.count}</span>
            ))}
          </div>
        </div>
        <div className="tt-work-nav">
          <button type="button" className="tt-btn" onClick={() => onAdvance(local.id)} disabled={!nextHint}>
            Следующее{nextHint ? '' : ' · конец'}
          </button>
          <button type="button" className="tt-btn" onClick={onClose}>К очереди</button>
        </div>
      </div>

      <p className="tt-hint">
        Превью лёгкие, полный кадр — по клику. Красная рамка: сравни. A принять · R отклонить · N следующее.
      </p>

      <div className="tt-grid">
        {(local.photos || []).map((photo, i) => {
          const hits = matchByIndex[i] || []
          const thumb = shotFileId(photo)
          return (
            <button
              key={photo.id || i}
              type="button"
              className={`tt-shot${hits.length ? ' tt-shot-hot' : ''}`}
              onClick={() => {
                if (hits.length) setCompare({ photo, hits })
                else openFull(photo)
              }}
            >
              <TgPhoto
                fileId={thumb}
                size="thumb"
                lazy
                style={{ width: '100%', height: 120, objectFit: 'cover' }}
              />
              <span>#{i + 1}{hits.length ? ` · ${hits.length} похож.` : ''}</span>
            </button>
          )
        })}
      </div>

      {compare && (
        <div className="tt-compare">
          <div className="tt-compare-col">
            <b>Этот кадр</b>
            <TgPhoto
              fileId={fullFileId(compare.photo)}
              size="full"
              lazy={false}
              onClick={() => openFull(compare.photo)}
            />
          </div>
          <div className="tt-compare-list">
            {compare.hits.map((hit, i) => (
              <div key={`${hit.match?.id || i}`} className="tt-compare-hit">
                <TgPhoto
                  fileId={fullFileId(hit.match)}
                  size="full"
                  lazy={false}
                  onClick={() => openFull(hit.match)}
                />
                <p>
                  Заявка #{hit.match.caseId} · игрок {hit.match.userId} · дистанция {hit.distance}
                  {hit.verdict ? ` · уже: ${hit.verdict === 'copy' ? 'копия' : 'не копия'}` : ''}
                </p>
                <div className="tt-row">
                  <button type="button" className="tt-btn tt-btn-hot" onClick={() => markPair(hit, 'copy')}>Копия</button>
                  <button type="button" className="tt-btn" onClick={() => markPair(hit, 'unique')}>Не копия</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="tt-actions">
        <button type="button" className="tt-btn tt-btn-ok" disabled={busy} onClick={() => decide(() => approveTiktokComment(local.id), 'Принято')}>
          Всё правильно
        </button>
        <button type="button" className="tt-btn tt-btn-hot" disabled={busy} onClick={() => decide(() => rejectTiktokComment(local.id), 'Отклонено')}>
          Отклонить
        </button>
      </div>
      {lightbox && <ImageLightbox src={lightbox} onClose={() => setLightbox(null)} />}
    </div>
  )
}

function VideoCard({ item, settings, onDone, rejectReasons }) {
  const [views, setViews] = useState(item.lastViews || '')
  const [reasons, setReasons] = useState([])
  const [busy, setBusy] = useState(false)
  const unit = settings?.kutPerUnit || 30
  const preview = kutForViews(views, unit)
  const old = item.lastViews || 0
  const oldKut = kutForViews(old, unit)
  const delta = Math.max(0, preview - oldKut)

  const run = async (fn, ok) => {
    setBusy(true)
    try {
      await fn()
      showToast(ok)
      onDone()
    } catch (err) {
      showToast(err.message || 'Ошибка')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="tt-video">
      <div className="tt-card-top">
        <strong>{playerName(item.user)}</strong>
        <span>{fmtDate(item.createdAt)}</span>
      </div>
      <div className="tt-card-nicks">{(item.user?.nicks || []).map((n) => `@${n}`).join(' · ')}</div>
      <a className="tt-link" href={item.url} target="_blank" rel="noreferrer">Открыть в TikTok</a>
      {item.recheckPending && <div className="tt-flag-hot">перепроверка · было {old} просмотров</div>}
      <label className="tt-field">
        <span>Просмотры сейчас</span>
        <input
          type="number"
          min="0"
          value={views}
          onChange={(e) => setViews(e.target.value)}
          placeholder="Например 12500"
        />
        <small>
          {Number(views) || 0} → {Math.floor((Number(views) || 0) / 1000)} × {unit} = {preview} кут
          {item.recheckPending ? ` · доплата ${delta}` : ''}
        </small>
      </label>
      {item.status === 'pending' && (
        <div className="tt-reasons">
          {(rejectReasons || []).map((r) => (
            <label key={r.id}>
              <input
                type="checkbox"
                checked={reasons.includes(r.id)}
                onChange={() => setReasons((cur) => (cur.includes(r.id) ? cur.filter((x) => x !== r.id) : [...cur, r.id]))}
              />
              {r.label}
            </label>
          ))}
        </div>
      )}
      <div className="tt-actions">
        <button
          type="button"
          className="tt-btn tt-btn-ok"
          disabled={busy || views === ''}
          onClick={() => run(() => approveTiktokVideo(item.id, Number(views)), 'Начислили')}
        >
          Принять и начислить
        </button>
        {item.status === 'pending' && (
          <button
            type="button"
            className="tt-btn tt-btn-hot"
            disabled={busy || !reasons.length}
            onClick={() => run(() => rejectTiktokVideo(item.id, reasons), 'Отклонено')}
          >
            Отклонить
          </button>
        )}
      </div>
    </div>
  )
}

function SettingsForm({ initial, onSaved }) {
  const [form, setForm] = useState(initial)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setForm(initial) }, [initial])
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))
  const reasons = form.rejectReasons || []
  const barnums = form.barnumRejects || []
  return (
    <form
      className="tt-settings"
      onSubmit={async (e) => {
        e.preventDefault()
        setBusy(true)
        try {
          const saved = await saveTiktokSettings({
            commentTag: form.commentTag,
            videoHashtag: form.videoHashtag,
            commentReward: Number(form.commentReward),
            viewsPerUnit: Number(form.viewsPerUnit),
            kutPerUnit: Number(form.kutPerUnit),
            recheckDays: Number(form.recheckDays),
            maxNicks: Number(form.maxNicks),
            photosRequired: Number(form.photosRequired),
            rejectReasons: form.rejectReasons,
            barnumRejects: form.barnumRejects,
          })
          showToast('Настройки сохранены')
          onSaved(saved)
        } catch (err) {
          showToast(err.message || 'Не сохранилось')
        } finally {
          setBusy(false)
        }
      }}
    >
      <p className="tt-hint">Тег и тексты отказа можно править. Цифры 15 / 5 / 30 / 1000 / 7 / 3 — правила продукта, не ломай их без причины.</p>
      <label>Тег комментариев<input value={form.commentTag || ''} onChange={(e) => set('commentTag', e.target.value)} /></label>
      <label>Хештег видео<input value={form.videoHashtag || ''} onChange={(e) => set('videoHashtag', e.target.value)} /></label>
      <div className="tt-locked-nums">
        <span>пачка {form.photosRequired ?? 15} скринов</span>
        <span>{form.commentReward ?? 5} кут</span>
        <span>{form.kutPerUnit ?? 30} кут / 1000</span>
        <span>перепроверка {form.recheckDays ?? 7} дн.</span>
        <span>ников ≤ {form.maxNicks ?? 3}</span>
      </div>

      <h4>Причины отказа видео</h4>
      <p className="tt-hint">Чеклист на карточке ролика. Коротко, по делу, без CMS.</p>
      <div className="tt-reason-edit">
        {reasons.map((r, i) => (
          <div key={r.id || i} className="tt-reason-row">
            <input
              value={r.label || ''}
              onChange={(e) => {
                const next = reasons.map((row, idx) => (idx === i ? { ...row, label: e.target.value } : row))
                set('rejectReasons', next)
              }}
            />
            <button
              type="button"
              className="tt-btn"
              onClick={() => set('rejectReasons', reasons.filter((_, idx) => idx !== i))}
              disabled={reasons.length <= 1}
            >
              убрать
            </button>
          </div>
        ))}
        <button
          type="button"
          className="tt-btn"
          onClick={() => set('rejectReasons', [...reasons, { id: `custom_${Date.now()}`, label: '' }])}
        >
          Добавить причину
        </button>
      </div>

      <h4>Ответ игроку при отказе комментариев</h4>
      <p className="tt-hint">Размытые формулировки. Не пиши «копия» и не объясняй, как обойти проверку.</p>
      <div className="tt-reason-edit">
        {barnums.map((text, i) => (
          <div key={i} className="tt-barnum-row">
            <textarea
              rows={3}
              value={text}
              onChange={(e) => set('barnumRejects', barnums.map((row, idx) => (idx === i ? e.target.value : row)))}
            />
            <button
              type="button"
              className="tt-btn"
              onClick={() => set('barnumRejects', barnums.filter((_, idx) => idx !== i))}
              disabled={barnums.length <= 1}
            >
              убрать
            </button>
          </div>
        ))}
        <button
          type="button"
          className="tt-btn"
          onClick={() => set('barnumRejects', [...barnums, ''])}
          disabled={barnums.length >= 12}
        >
          Добавить формулировку
        </button>
      </div>
      <button type="submit" className="tt-btn tt-btn-ok" disabled={busy}>Сохранить</button>
    </form>
  )
}

export default function TikTokSection({ panelTabs = null, role = null }) {
  const allowed = panelTabs?.tiktok
  const can = (id) => role === 'owner' || allowed == null || allowed.includes(id)
  const [tab, setTab] = useState(() => TABS.find((t) => can(t.id))?.id || 'comments')
  const [guide, setGuide] = useState(() => !localStorage.getItem(GUIDE_KEY))
  const [map, setMap] = useState(null)
  const [overview, setOverview] = useState(null)
  const [comments, setComments] = useState([])
  const [videos, setVideos] = useState([])
  const [openCase, setOpenCase] = useState(null)
  const [loading, setLoading] = useState(true)
  const [archiveOffset, setArchiveOffset] = useState(0)

  const load = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true)
    try {
      const [ov, access] = await Promise.all([
        fetchTiktokOverview().catch(() => null),
        fetchTiktokAccessMap().catch(() => null),
      ])
      setOverview(ov)
      setMap(access)
      if (tab === 'comments' && can('comments')) {
        const data = await fetchTiktokComments('pending')
        setComments(data.items || [])
      } else if (tab === 'archive' && can('archive')) {
        const data = await fetchTiktokCommentsArchive({ limit: 20, offset: 0 })
        setComments(data.items || [])
        setArchiveOffset(data.items?.length || 0)
      } else if ((tab === 'videos' || tab === 'live') && can(tab)) {
        const data = await fetchTiktokVideos(tab === 'live' ? 'live' : 'pending')
        setVideos(data.items || [])
      } else if (tab === 'settings' && can('settings')) {
        const s = await fetchTiktokSettings()
        setOverview((cur) => ({ ...(cur || {}), settings: s }))
      }
    } catch (err) {
      showToast(err.message || 'Не удалось загрузить TikTok')
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [tab, role, allowed])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!can(tab)) {
      const next = TABS.find((t) => can(t.id))
      if (next) setTab(next.id)
    }
  }, [tab, allowed, role])

  const openFromQueue = async (item) => {
    if (!item) {
      setOpenCase(null)
      return
    }
    if (item.photos?.length) {
      setOpenCase(item)
      return
    }
    try {
      const full = await fetchTiktokComment(item.id)
      setOpenCase(full)
    } catch (err) {
      showToast(err.message || 'Не открылось')
    }
  }

  const advanceFrom = async (currentId, { remove = false } = {}) => {
    const nxt = nextQueueItem(comments, currentId)
    if (remove) {
      setComments((cur) => cur.filter((c) => Number(c.id) !== Number(currentId)))
    }
    if (nxt) await openFromQueue(nxt)
    else setOpenCase(null)
    load({ quiet: true })
  }

  const afterDecide = async (currentId) => {
    await advanceFrom(currentId, { remove: true })
  }

  const locked = !can(tab)
  const settings = overview?.settings

  return (
    <article className="panel-shelf panel-shelf-page tt-page">
      <p className="panel-shelf-label">TikTok</p>
      <h2 className="panel-page-title">Очередь заработка</h2>
      <p className="panel-page-lead">
        Игрок не берёт задание — читает и присылает доказательства. Твоя работа: быстро решить, настоящее это или нет.
      </p>

      {guide && (
        <Guide
          onClose={() => {
            localStorage.setItem(GUIDE_KEY, '1')
            setGuide(false)
          }}
        />
      )}

      <div className="tt-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`tt-tab${tab === t.id ? ' is-on' : ''}${can(t.id) ? '' : ' is-lock'}`}
            onClick={() => { setOpenCase(null); setTab(t.id) }}
          >
            {t.label}
            {!can(t.id) ? ' · замок' : ''}
            {t.id === 'comments' && overview?.pendingComments ? ` · ${overview.pendingComments}` : ''}
            {t.id === 'videos' && overview?.pendingVideos ? ` · ${overview.pendingVideos}` : ''}
            {t.id === 'live' && overview?.pendingRechecks ? ` · ${overview.pendingRechecks}` : ''}
          </button>
        ))}
      </div>

      <p className="tt-hint">{TABS.find((t) => t.id === tab)?.hint}</p>

      {locked ? (
        <LockCard tab={TABS.find((t) => t.id === tab)} map={map} />
      ) : loading && !openCase ? (
        <p className="tt-hint">Загружаем очередь…</p>
      ) : openCase ? (
        <CommentWorkspace
          item={openCase}
          queue={comments}
          onClose={() => setOpenCase(null)}
          onAdvance={advanceFrom}
          onDecided={afterDecide}
        />
      ) : tab === 'comments' || tab === 'archive' ? (
        <div className="tt-list">
          {comments.length === 0 && <p className="tt-empty">Пока пусто. Когда игрок пришлёт 15 скринов — карточка появится здесь.</p>}
          {comments.map((item) => (
            <CommentCase key={item.id} item={item} onOpen={openFromQueue} />
          ))}
          {tab === 'archive' && comments.length >= 20 && (
            <button
              type="button"
              className="tt-btn"
              onClick={async () => {
                try {
                  const data = await fetchTiktokCommentsArchive({ limit: 20, offset: archiveOffset })
                  const extra = data.items || []
                  setComments((cur) => [...cur, ...extra])
                  setArchiveOffset((n) => n + extra.length)
                } catch (err) {
                  showToast(err.message || 'Архив не догрузился')
                }
              }}
            >
              Ещё из архива
            </button>
          )}
        </div>
      ) : tab === 'videos' || tab === 'live' ? (
        <div className="tt-list">
          {videos.length === 0 && <p className="tt-empty">Нет роликов в этой папке.</p>}
          {videos.map((item) => (
            <VideoCard
              key={item.id}
              item={item}
              settings={settings}
              rejectReasons={settings?.rejectReasons}
              onDone={() => load({ quiet: true })}
            />
          ))}
        </div>
      ) : (
        settings && <SettingsForm initial={settings} onSaved={(s) => setOverview((cur) => ({ ...(cur || {}), settings: s }))} />
      )}
    </article>
  )
}
