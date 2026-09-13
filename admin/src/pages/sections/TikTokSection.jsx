import { useCallback, useEffect, useMemo, useState } from 'react'
import '../../styles/tiktok.css'
import TgPhoto from '../../components/TgPhoto'
import ImageLightbox from '../../components/ImageLightbox'
import { showToast } from '../../components/ToastHost'
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
  { id: 'settings', label: 'Настройки', hint: 'Тег, награда, причины отказа. Меняй только если понимаешь последствия.' },
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
          <b>{people.length ? people.map((p) => p.name).join(', ') : 'никого'}</b>
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
        <li>Слева очередь. Открой карточку — справа 15 кадров сразу, не 15 тикетов.</li>
        <li>Красная рамка: код нашёл похожий кадр. Нажми фото — сравни и отметь «копия» или «не копия».</li>
        <li>Видео: открой ссылку, впиши просмотры. Под полем сразу видно, сколько кут уйдёт.</li>
      </ol>
      <button type="button" className="tt-btn tt-btn-ok" onClick={onClose}>Понятно, к очереди</button>
    </div>
  )
}

function CommentCase({ item, onOpen }) {
  return (
    <button type="button" className="tt-card" onClick={() => onOpen(item)}>
      <div className="tt-card-top">
        <strong>{playerName(item.user)}</strong>
        <span>{fmtDate(item.createdAt)}</span>
      </div>
      <div className="tt-card-nicks">{(item.nicks || []).map((n) => `@${n}`).join(' · ') || 'нет ников'}</div>
      <div className="tt-card-flags">
        <span>{(item.photos || []).length} фото</span>
        {item.hasSimilar ? <span className="tt-flag-hot">есть похожие · {item.matchCount}</span> : <span>уникальные</span>}
      </div>
    </button>
  )
}

function CommentWorkspace({ item, onClose, onDone }) {
  const [busy, setBusy] = useState(false)
  const [lightbox, setLightbox] = useState(null)
  const [compare, setCompare] = useState(null)
  const [local, setLocal] = useState(item)

  useEffect(() => { setLocal(item) }, [item])

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

  const decide = async (fn, okText) => {
    setBusy(true)
    try {
      await fn()
      showToast(okText)
      onDone()
    } catch (err) {
      showToast(err.message || 'Ошибка')
    } finally {
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
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if (e.key === 'a' || e.key === 'A') decide(() => approveTiktokComment(local.id), 'Принято, 5 кут ушли')
      if (e.key === 'r' || e.key === 'R') decide(() => rejectTiktokComment(local.id), 'Отклонено, игроку ушёл ответ')
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [local.id])

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
        <button type="button" className="tt-btn" onClick={onClose}>К очереди</button>
      </div>

      <p className="tt-hint">Нажми кадр с красной рамкой — увидишь, на что он похож. A — принять, R — отклонить.</p>

      <div className="tt-grid">
        {(local.photos || []).map((photo, i) => {
          const hits = matchByIndex[i] || []
          return (
            <button
              key={photo.id || i}
              type="button"
              className={`tt-shot${hits.length ? ' tt-shot-hot' : ''}`}
              onClick={() => {
                if (hits.length) setCompare({ photo, hits })
                else setLightbox(photo.fileId)
              }}
            >
              <TgPhoto fileId={photo.fileId} style={{ width: '100%', height: 120, objectFit: 'cover' }} />
              <span>#{i + 1}{hits.length ? ` · ${hits.length} похож.` : ''}</span>
            </button>
          )
        })}
      </div>

      {compare && (
        <div className="tt-compare">
          <div className="tt-compare-col">
            <b>Этот кадр</b>
            <TgPhoto fileId={compare.photo.fileId} onClick={(src) => setLightbox(src)} />
          </div>
          <div className="tt-compare-list">
            {compare.hits.map((hit, i) => (
              <div key={i} className="tt-compare-hit">
                <TgPhoto fileId={hit.match.fileId} onClick={(src) => setLightbox(src)} />
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
      <p className="tt-hint">Эти цифры видит игрок в боте. Не меняй награду посреди живой очереди без причины.</p>
      <label>Тег комментариев<input value={form.commentTag || ''} onChange={(e) => set('commentTag', e.target.value)} /></label>
      <label>Хештег видео<input value={form.videoHashtag || ''} onChange={(e) => set('videoHashtag', e.target.value)} /></label>
      <label>Награда за пачку<input type="number" value={form.commentReward ?? 5} onChange={(e) => set('commentReward', e.target.value)} /></label>
      <label>Куты за 1000 просмотров<input type="number" value={form.kutPerUnit ?? 30} onChange={(e) => set('kutPerUnit', e.target.value)} /></label>
      <label>Пауза перепроверки, дни<input type="number" value={form.recheckDays ?? 7} onChange={(e) => set('recheckDays', e.target.value)} /></label>
      <label>Максимум ников<input type="number" value={form.maxNicks ?? 3} onChange={(e) => set('maxNicks', e.target.value)} /></label>
      <label>Скриншотов в пачке<input type="number" value={form.photosRequired ?? 15} onChange={(e) => set('photosRequired', e.target.value)} /></label>
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

  const load = useCallback(async () => {
    setLoading(true)
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
        const data = await fetchTiktokCommentsArchive()
        setComments(data.items || [])
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
      setLoading(false)
    }
  }, [tab, role, allowed])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!can(tab)) {
      const next = TABS.find((t) => can(t.id))
      if (next) setTab(next.id)
    }
  }, [tab, allowed, role])

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
            onClick={() => setTab(t.id)}
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
      ) : loading ? (
        <p className="tt-hint">Загружаем очередь…</p>
      ) : openCase ? (
        <CommentWorkspace item={openCase} onClose={() => setOpenCase(null)} onDone={() => { setOpenCase(null); load() }} />
      ) : tab === 'comments' || tab === 'archive' ? (
        <div className="tt-list">
          {comments.length === 0 && <p className="tt-empty">Пока пусто. Когда игрок пришлёт 15 скринов — карточка появится здесь.</p>}
          {comments.map((item) => (
            <CommentCase key={item.id} item={item} onOpen={setOpenCase} />
          ))}
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
              onDone={load}
            />
          ))}
        </div>
      ) : (
        settings && <SettingsForm initial={settings} onSaved={(s) => setOverview((cur) => ({ ...(cur || {}), settings: s }))} />
      )}
    </article>
  )
}
