import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import '../../styles/tiktok.css'
import TgPhoto, { loadTgPhotoUrl } from '../../components/TgPhoto'
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
  { id: 'comments', label: 'Комментарии', hint: 'Принять можно только полную пачку. Отклонить - в любой момент.' },
  { id: 'videos', label: 'Видео', hint: 'Откройте ролик, впишите просмотры. Куты посчитаются сами.' },
  { id: 'live', label: 'Живые', hint: 'Только ролики, которые игрок попросил перепроверить.' },
  { id: 'archive', label: 'Архив', hint: 'Закрытые заявки. Только просмотр.' },
  { id: 'settings', label: 'Настройки', hint: 'Хештеги и причины отказа. Награду меняет создатель.' },
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

function photoIds(photo) {
  if (!photo) return { thumb: '', full: '' }
  const nested = photo.hashes && typeof photo.hashes === 'object' ? photo.hashes : {}
  const full = String(photo.fileId || photo.file_id || nested.fileId || nested.file_id || '').trim()
  const thumb = String(photo.thumbFileId || photo.thumb_file_id || nested.thumbFileId || full).trim()
  return { thumb: thumb || full, full: full || thumb }
}

function shotFileId(photo) {
  return photoIds(photo).thumb
}

function fullFileId(photo) {
  return photoIds(photo).full
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

function caseStatus(item) {
  const count = item.photoCount || (item.photos || []).length
  const needed = item.photosRequired || 15
  if (item.status === 'approved') return 'принято'
  if (item.status === 'rejected') return 'отклонено'
  if (item.status === 'withdrawn') return 'отозвано'
  return `${count}/${needed}`
}

function statusFlagClass(item) {
  if (item.status === 'approved') return 'tt-flag-ok'
  if (item.status === 'rejected') return 'tt-flag-no'
  if (item.status === 'withdrawn') return 'tt-flag-muted'
  const count = item.photoCount || (item.photos || []).length
  const needed = item.photosRequired || 15
  if (item.incomplete ?? count < needed) return 'tt-flag-incomplete'
  return 'tt-flag-ok'
}

function plainText(html) {
  return String(html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

function Guide({ onClose }) {
  return (
    <div className="tt-guide">
      <button type="button" className="tt-guide-x" onClick={onClose} aria-label="Закрыть гид">×</button>
      <h3>Проверка TikTok</h3>
      <ol>
        <li>Откройте заявку и кадр. Примите или отклоните.</li>
        <li>Красная рамка - почти точный дубль. Для видео впишите просмотры из TikTok.</li>
      </ol>
      <button type="button" className="tt-btn tt-btn-ok" onClick={onClose}>Понятно</button>
    </div>
  )
}

function CommentCase({ item, onOpen, current }) {
  const count = item.photoCount || (item.photos || []).length
  const needed = item.photosRequired || 15
  const incomplete = item.incomplete ?? count < needed
  const closed = ['approved', 'rejected', 'withdrawn'].includes(item.status)
  return (
    <button
      type="button"
      className={`tt-card${incomplete && !closed ? ' is-incomplete' : ''}${current ? ' is-current' : ''}`}
      onClick={() => onOpen(item)}
    >
      <div className="tt-card-top">
        <strong>{playerName(item.user)}</strong>
        <span>{fmtDate(item.createdAt)}</span>
      </div>
      <div className="tt-card-nicks">{(item.nicks || []).map((n) => `@${n}`).join(' · ') || 'нет ников'}</div>
      <div className="tt-card-flags">
        <span className={statusFlagClass(item)}>{caseStatus(item)}</span>
        {!closed && item.hasSimilar ? <span className="tt-flag-hot">дубль</span> : null}
      </div>
    </button>
  )
}

function CommentWorkspace({ item, queue, onClose, onAdvance, onDecided, commentRejectReasons, readonly = false }) {
  const [busy, setBusy] = useState(false)
  const [viewer, setViewer] = useState(null)
  const [local, setLocal] = useState(item)
  const [reasons, setReasons] = useState([])
  const busyRef = useRef(false)

  useEffect(() => { setLocal(item); setViewer(null); setReasons([]) }, [item])

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

  const needed = local.photosRequired || 15
  const received = local.photoCount ?? (local.photos || []).length
  const incomplete = local.incomplete ?? received < needed
  const closed = ['approved', 'rejected', 'withdrawn'].includes(local.status)
  const viewOnly = readonly || closed
  const photos = (local.photos || []).filter((photo) => shotFileId(photo))
  const openable = photos.map((photo, index) => ({ photo, index: photo.index ?? index }))
  const crossHits = (local.matches || []).filter((m) => !m.sameCase).slice(0, 4)
  const intraHits = (local.matches || []).filter((m) => m.sameCase).slice(0, 2)

  const openAt = async (slotIndex) => {
    const photo = photos.find((itemPhoto) => (itemPhoto.index ?? 0) === slotIndex)
    const id = fullFileId(photo)
    if (!id) return
    try {
      const src = await loadTgPhotoUrl(id, 'full')
      setViewer({ src, index: slotIndex, alt: `Скрин ${slotIndex + 1}` })
    } catch {
      showToast('Кадр не открылся. Нажмите ещё раз или проверьте вход.')
    }
  }

  const openPhoto = async (photo) => {
    const idx = photos.findIndex((itemPhoto) => itemPhoto && fullFileId(itemPhoto) === fullFileId(photo))
    if (idx >= 0) {
      await openAt(photo.index ?? idx)
      return
    }
    const id = fullFileId(photo)
    if (!id) return
    try {
      setViewer({ src: await loadTgPhotoUrl(id, 'full'), index: -1, alt: 'Похожий кадр' })
    } catch {
      showToast('Кадр не открылся. Нажмите ещё раз или проверьте вход.')
    }
  }

  const stepViewer = (dir) => {
    if (!openable.length || viewer == null) return
    const pos = openable.findIndex((row) => row.index === viewer.index)
    const next = openable[(pos < 0 ? 0 : pos) + dir]
      || (dir > 0 ? openable[0] : openable[openable.length - 1])
    if (next) openAt(next.index)
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
    if (!a || !b) {
      showToast('У этих кадров нет отпечатка. Откройте оба и решите глазами.')
      return
    }
    try {
      await saveTiktokVerdict(a, b, verdict)
      showToast(verdict === 'copy' ? 'Отметили как одинаковые' : 'Отметили как разные')
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
        if (viewOnly) return
        const neededKey = local.photosRequired || 15
        const receivedKey = local.photoCount ?? (local.photos || []).length
        if ((local.incomplete ?? receivedKey < neededKey)) return
        e.preventDefault()
        decide(() => approveTiktokComment(local.id), `Принято, ${local.reward || ''} кут ушли`)
      }
      if (e.key === 'r' || e.key === 'R') {
        if (viewOnly) return
        if (!reasons.length) {
          showToast('Отметьте хотя бы одну причину отказа')
          return
        }
        e.preventDefault()
        decide(() => rejectTiktokComment(local.id, reasons), 'Отклонено, игроку ушёл ответ')
      }
      if (e.key === 'n' || e.key === 'N' || e.key === 'j' || e.key === 'J') {
        e.preventDefault()
        onAdvance(local.id)
      }
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [local, reasons, viewOnly, onAdvance, onClose])

  const nextHint = nextQueueItem(queue, local.id)

  const renderPair = (hit, i) => (
    <div key={`${hit.source?.id || i}-${hit.match?.id || i}`} className="tt-pair">
      <div className="tt-pair-col">
        <b>Этот кадр · #{(hit.source?.index ?? 0) + 1}</b>
        <TgPhoto
          fileId={fullFileId(hit.source)}
          size="full"
          lazy={false}
          alt={`Кадр ${(hit.source?.index ?? 0) + 1}`}
          onClick={() => openPhoto(hit.source)}
        />
      </div>
      <div className="tt-pair-col">
        <b>
          {hit.sameCase
            ? `В этой серии · #${(hit.match?.index ?? 0) + 1}`
            : `Другая заявка · #${(hit.match?.index ?? 0) + 1}`}
        </b>
        <TgPhoto
          fileId={fullFileId(hit.match)}
          size="full"
          lazy={false}
          alt="Похожий кадр"
          onClick={() => openPhoto(hit.match)}
        />
      </div>
      <div className="tt-pair-meta">
        <p>
          {hit.similarity ?? 0}%
          {hit.sameCase ? ' · внутри серии' : ''}
          {hit.verdict === 'copy' ? ' · одинаковые' : hit.verdict === 'unique' ? ' · разные' : ''}
        </p>
        <div className="tt-row">
          {!viewOnly && (
            <>
              <button type="button" className="tt-btn tt-btn-hot" onClick={() => markPair(hit, 'copy')}>Одинаковые</button>
              <button type="button" className="tt-btn" onClick={() => markPair(hit, 'unique')}>Разные</button>
            </>
          )}
        </div>
      </div>
    </div>
  )

  return (
    <div className="tt-work">
      <div className="tt-work-head">
        <div>
          <h3>{playerName(local.user)}</h3>
          <p>
            {(local.nicks || []).map((n) => `@${n}`).join(' · ') || 'нет ников'}
            {' · '}
            {fmtDate(local.createdAt)}
          </p>
        </div>
        <div className="tt-work-nav">
          <span className={statusFlagClass(local)}>{caseStatus(local)}</span>
          {nextHint ? (
            <button type="button" className="tt-btn" onClick={() => onAdvance(local.id)}>
              Следующее
            </button>
          ) : null}
          <button type="button" className="tt-btn" onClick={onClose}>К очереди</button>
        </div>
      </div>

      {incomplete && !viewOnly && (
        <div className="tt-incomplete-note">
          {received} из {needed}. Принять можно только полную пачку.
        </div>
      )}
      {viewOnly && (
        <div className="tt-incomplete-note">
          {local.status === 'rejected' && plainText(local.rejectText)
            ? plainText(local.rejectText)
            : 'Только просмотр'}
        </div>
      )}

      {photos.length === 0 ? (
        <p className="tt-empty">Нет скринов.</p>
      ) : (
      <div className="tt-grid" aria-label="Скриншоты серии">
        {photos.map((photo, i) => {
          const idx = photo.index ?? i
          const hits = matchByIndex[idx] || []
          const cross = hits.filter((h) => !h.sameCase)
          const copyHit = hits.some((h) => h.verdict === 'copy')
          const selected = viewer && viewer.index === idx
          return (
            <div
              key={photo.id || idx}
              role="button"
              tabIndex={0}
              className={`tt-shot${copyHit || cross.some((h) => (h.similarity || 0) >= 96) ? ' tt-shot-hot' : ''}${selected ? ' is-on' : ''}`}
              onClick={() => openAt(idx)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  openAt(idx)
                }
              }}
            >
              <TgPhoto
                fileId={shotFileId(photo)}
                size="thumb"
                lazy
                alt={`Скрин ${idx + 1}`}
                style={{ width: '100%', height: 148, objectFit: 'cover' }}
              />
              <span>#{idx + 1}{copyHit || cross.some((h) => (h.similarity || 0) >= 96) ? ' · дубль' : ''}</span>
            </div>
          )
        })}
      </div>
      )}

      {(crossHits.length > 0 || intraHits.length > 0) && (
        <div className="tt-similar">
          <h4>Похоже на другой кадр</h4>
          {crossHits.map(renderPair)}
          {intraHits.map(renderPair)}
        </div>
      )}

      {!viewOnly && (
        <>
          <div className="tt-reasons">
            <p className="tt-hint">Почему отклоняем. Игрок увидит эти пункты.</p>
            {(commentRejectReasons || []).map((r) => (
              <label key={r.id} className={`tt-reason-chip${reasons.includes(r.id) ? ' is-on' : ''}`}>
                <input
                  type="checkbox"
                  checked={reasons.includes(r.id)}
                  onChange={() => setReasons((cur) => (cur.includes(r.id) ? cur.filter((x) => x !== r.id) : [...cur, r.id]))}
                />
                {r.label || 'Причина без названия'}
              </label>
            ))}
          </div>
          <div className="tt-actions tt-actions-bar">
            <button
              type="button"
              className="tt-btn tt-btn-hot"
              disabled={busy || !reasons.length}
              onClick={() => decide(() => rejectTiktokComment(local.id, reasons), 'Отклонено')}
            >
              Отклонить
            </button>
            <button
              type="button"
              className="tt-btn tt-btn-ok"
              disabled={busy || incomplete}
              title={incomplete ? `Нельзя принять: ${received} из ${needed}` : ''}
              onClick={() => decide(() => approveTiktokComment(local.id), 'Принято')}
            >
              {incomplete ? `Принять · ${received}/${needed}` : 'Принять'}
            </button>
          </div>
        </>
      )}
      {viewer?.src && (
        <ImageLightbox
          src={viewer.src}
          alt={viewer.alt}
          caption={viewer.alt}
          index={Math.max(0, openable.findIndex((row) => row.index === viewer.index))}
          total={openable.length}
          onClose={() => setViewer(null)}
          onPrev={viewer.index >= 0 && openable.length > 1 ? () => stepViewer(-1) : undefined}
          onNext={viewer.index >= 0 && openable.length > 1 ? () => stepViewer(1) : undefined}
        />
      )}
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
      {(item.user?.nicks || []).length > 0 && (
        <div className="tt-card-nicks">{(item.user?.nicks || []).map((n) => `@${n}`).join(' · ')}</div>
      )}
      <a className="tt-link" href={item.url} target="_blank" rel="noreferrer">Открыть в TikTok</a>
      {item.recheckPending && (
        <div className="tt-flag-hot">перепроверка · было {old.toLocaleString('ru-RU')} просмотров</div>
      )}
      <label className="tt-field">
        <span>Просмотры сейчас</span>
        <input
          type="number"
          min="0"
          inputMode="numeric"
          value={views}
          onChange={(e) => setViews(e.target.value)}
          placeholder="Например 12500"
        />
        <small>
          {preview} кут
          {item.recheckPending ? ` · доплата ${delta} кут` : ''}
        </small>
      </label>
      {item.status === 'pending' && (
        <div className="tt-reasons">
          {(rejectReasons || []).map((r) => (
            <label key={r.id} className={`tt-reason-chip${reasons.includes(r.id) ? ' is-on' : ''}`}>
              <input
                type="checkbox"
                checked={reasons.includes(r.id)}
                onChange={() => setReasons((cur) => (cur.includes(r.id) ? cur.filter((x) => x !== r.id) : [...cur, r.id]))}
              />
              {r.label || 'Причина без названия'}
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
          Принять
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

function SettingsForm({ initial, onSaved, canEditRewards = false }) {
  const [form, setForm] = useState(initial)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setForm(initial) }, [initial])
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))
  const reasons = form.rejectReasons || []
  const photoReasons = form.commentRejectReasons || []
  const caps = form.rewardCaps || { commentMin: 1, commentMax: 500, videoMin: 1, videoMax: 5000 }
  const pack = Number(form.photosRequired ?? 15)
  const commentPay = Number(form.commentReward ?? 0)
  const videoPay = Number(form.kutPerUnit ?? 0)
  return (
    <form
      className="tt-settings"
      onSubmit={async (e) => {
        e.preventDefault()
        setBusy(true)
        try {
          const body = {
            commentTag: form.commentTag,
            videoHashtag: form.videoHashtag,
            rejectReasons: form.rejectReasons,
            commentRejectReasons: form.commentRejectReasons,
          }
          if (canEditRewards) {
            body.commentReward = Number(form.commentReward)
            body.kutPerUnit = Number(form.kutPerUnit)
          }
          const saved = await saveTiktokSettings(body)
          showToast('Настройки сохранены')
          onSaved(saved)
        } catch (err) {
          showToast(err.message || 'Не сохранилось')
        } finally {
          setBusy(false)
        }
      }}
    >
      <p className="tt-hint">Хештеги и тексты отказа. Пачка, пауза и лимит ников - правила продукта.</p>

      <div className={`tt-reward-card${canEditRewards ? '' : ' is-lock'}`}>
        <div className="tt-reward-head">
          <h4>Награды в кутах</h4>
          {canEditRewards ? (
            <span className="tt-lock-seal">создатель</span>
          ) : (
            <span className="tt-lock-seal">только создатель</span>
          )}
        </div>
        <p className="tt-hint">
          {canEditRewards
            ? 'Новые одобрения и доплаты за перепроверку считают по этим цифрам. Уже выплаченное не переписываем.'
            : 'Сейчас видишь актуальные цифры. Менять награду может только создатель проекта.'}
        </p>
        <div className="tt-reward-grid">
          <label className="tt-field">
            <span>Награда за полную пачку комментариев, кут</span>
            <input
              type="number"
              min={caps.commentMin}
              max={caps.commentMax}
              value={form.commentReward ?? ''}
              disabled={!canEditRewards}
              onChange={(e) => set('commentReward', e.target.value)}
            />
          </label>
          <label className="tt-field">
            <span>Награда за каждые 1000 просмотров, кут</span>
            <input
              type="number"
              min={caps.videoMin}
              max={caps.videoMax}
              value={form.kutPerUnit ?? ''}
              disabled={!canEditRewards}
              onChange={(e) => set('kutPerUnit', e.target.value)}
            />
          </label>
        </div>
        <div className="tt-reward-live">
          <span>{pack} скринов = {commentPay || '-'} кут</span>
          <span>каждые 1000 просмотров = {videoPay || '-'} кут</span>
        </div>
        <p className="tt-hint">Пачка: {caps.commentMin}-{caps.commentMax} кут. Видео: {caps.videoMin}-{caps.videoMax} кут за тысячу. Перепроверка: (новые тысячи - старые) x текущая награда.</p>
      </div>

      <label className="tt-field">
        <span>Хештег роликов для комментариев</span>
        <input value={form.commentTag || ''} onChange={(e) => set('commentTag', e.target.value)} placeholder="#тгзвезды" />
      </label>
      <label className="tt-field">
        <span>Хештег в ролике про бота</span>
        <input value={form.videoHashtag || ''} onChange={(e) => set('videoHashtag', e.target.value)} placeholder="#CuteGamingBot" />
      </label>
      <div className="tt-locked-nums">
        <span>пачка {pack} скринов</span>
        <span>перепроверка {form.recheckDays ?? 7} дн.</span>
        <span>ников ≤ {form.maxNicks ?? 3}</span>
      </div>

      <h4>Причины отказа комментариев</h4>
      <p className="tt-hint">Игрок получит выбранные пункты.</p>
      <div className="tt-reason-edit">
        {photoReasons.map((r, i) => (
          <div key={r.id || i} className="tt-reason-row">
            <input
              value={r.label || ''}
              onChange={(e) => {
                const next = photoReasons.map((row, idx) => (idx === i ? { ...row, label: e.target.value } : row))
                set('commentRejectReasons', next)
              }}
            />
            <button
              type="button"
              className="tt-btn"
              onClick={() => set('commentRejectReasons', photoReasons.filter((_, idx) => idx !== i))}
              disabled={photoReasons.length <= 1}
            >
              убрать
            </button>
          </div>
        ))}
        <button
          type="button"
          className="tt-btn"
          onClick={() => set('commentRejectReasons', [...photoReasons, { id: `photo_${Date.now()}`, label: '' }])}
        >
          Добавить причину
        </button>
      </div>

      <h4>Причины отказа видео</h4>
      <p className="tt-hint">Игрок получит выбранные пункты.</p>
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
      <button type="submit" className="tt-btn tt-btn-ok" disabled={busy}>Сохранить</button>
    </form>
  )
}

export default function TikTokSection({ panelTabs = null, role = null, isProjectCreator = false }) {
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
        const items = data.items || []
        setVideos(tab === 'live' ? items.filter((item) => item.recheckPending) : items)
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
        Откройте заявку, посмотрите скрины, примите или отклоните.
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
        <div className="tt-review">
          {(tab === 'comments' || tab === 'archive') && comments.length > 0 && (
            <aside className="tt-rail" aria-label="Очередь">
              {comments.map((item) => (
                <CommentCase
                  key={item.id}
                  item={item}
                  current={Number(openCase.id) === Number(item.id)}
                  onOpen={openFromQueue}
                />
              ))}
            </aside>
          )}
          <CommentWorkspace
            item={openCase}
            queue={comments}
            commentRejectReasons={settings?.commentRejectReasons}
            readonly={tab === 'archive'}
            onClose={() => setOpenCase(null)}
            onAdvance={advanceFrom}
            onDecided={afterDecide}
          />
        </div>
      ) : tab === 'comments' || tab === 'archive' ? (
        <div className="tt-list">
          {comments.length === 0 && (
            <p className="tt-empty">
              {tab === 'archive' ? 'Архив пуст.' : 'Очередь пуста. Неполная пачка тоже появится здесь.'}
            </p>
          )}
          {comments.map((item) => (
            <CommentCase
              key={item.id}
              item={item}
              current={Number(openCase?.id) === Number(item.id)}
              onOpen={openFromQueue}
            />
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
          {videos.length === 0 && (
            <p className="tt-empty">
              {tab === 'live' ? 'Нет запросов на перепроверку.' : 'Нет роликов на проверке.'}
            </p>
          )}
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
        settings && (
          <SettingsForm
            initial={settings}
            canEditRewards={Boolean(settings.canEditRewards || role === 'owner' || isProjectCreator)}
            onSaved={(s) => setOverview((cur) => ({ ...(cur || {}), settings: s }))}
          />
        )
      )}
    </article>
  )
}
