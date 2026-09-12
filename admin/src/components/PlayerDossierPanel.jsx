import { useEffect, useState } from 'react'
import { patchOwnerUserFields } from '../lib/adminClient'
import { notifyAdmin } from '../lib/notify'

function fmt(n) {
  return Number(n || 0).toLocaleString('ru-RU')
}

/** Досье игрока в стиле профиля бота + owner-edit */
export default function PlayerDossierPanel({
  intel,
  isOwner = false,
  canEdit = false,
  onSaved,
}) {
  const d = intel?.dossier || {}
  const ach = intel?.achievements?.items || []
  const secrets = d.ownerSecrets
  const [draft, setDraft] = useState({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isOwner || !canEdit) return
    setDraft({
      donate: d.donated ?? 0,
      canwithdrawal: d.withdrawLimit ?? 0,
      wins: d.wins ?? 0,
      loose: d.losses ?? 0,
      winamount: d.winAmount ?? 0,
      give: d.transferLimit ?? 0,
      referrals: d.referrals ?? 0,
      demo: secrets?.demo ?? 0,
      zeroDemo: secrets?.zeroDemo ?? 0,
      registeredAt: d.registeredAt ? String(d.registeredAt).slice(0, 16) : '',
    })
  }, [intel, isOwner, canEdit, d.donated, d.withdrawLimit, d.wins, d.losses, d.winAmount, d.transferLimit, d.referrals, d.registeredAt, secrets?.demo, secrets?.zeroDemo])

  const save = async () => {
    if (!canEdit || !isOwner || !intel?.profile?.userId) return
    setSaving(true)
    try {
      const payload = {
        donate: Number(draft.donate),
        canwithdrawal: Number(draft.canwithdrawal),
        wins: Number(draft.wins),
        loose: Number(draft.loose),
        winamount: Number(draft.winamount),
        give: Number(draft.give),
        referrals: Number(draft.referrals),
        demo: Number(draft.demo),
        zeroDemo: Number(draft.zeroDemo),
      }
      if (draft.registeredAt) payload.registeredAt = draft.registeredAt
      await patchOwnerUserFields(intel.profile.userId, payload)
      notifyAdmin('Параметры игрока сохранены')
      onSaved?.()
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка сохранения', { error: true })
    } finally {
      setSaving(false)
    }
  }

  const ms = d.growthFundMilestone

  return (
    <div className="pu-dossier">
      <div className="pu-dossier-grid">
        <div className="pu-dossier-tile">
          <span>Фонд Роста</span>
          <strong>{fmt(d.growthFundContributed)} кут</strong>
          {ms && (
            <em>{ms.bar} · {fmt(ms.progress)}/{fmt(ms.target)}</em>
          )}
        </div>
        <div className="pu-dossier-tile">
          <span>Задоначено</span>
          <strong>{fmt(d.donated)} кут</strong>
        </div>
        <div className="pu-dossier-tile">
          <span>Выиграно</span>
          <strong>{fmt(d.winAmount)} кут</strong>
          <em>W {fmt(d.wins)} · L {fmt(d.losses)}</em>
        </div>
        <div className="pu-dossier-tile">
          <span>Переводы до</span>
          <strong>~{fmt(d.transferLimit)} кут</strong>
        </div>
        <div className="pu-dossier-tile">
          <span>Лимит выводов</span>
          <strong>{fmt(d.withdrawLimit)} кут</strong>
        </div>
        <div className="pu-dossier-tile">
          <span>Рефералы</span>
          <strong>{fmt(d.referrals)}</strong>
          {d.referrerName && <em>от {d.referrerName}</em>}
        </div>
        <div className="pu-dossier-tile">
          <span>Репутация</span>
          <strong>+{fmt(d.reputationPlus)} · −{fmt(d.reputationMinus)}</strong>
        </div>
        <div className="pu-dossier-tile">
          <span>Регистрация</span>
          <strong>{d.registeredAtLabel || '—'}</strong>
          {d.accountAge && <em>{d.accountAge}</em>}
        </div>
      </div>

      {(d.sponsoredChats || []).length > 0 && (
        <div className="pu-dossier-roles">
          <p className="pu-dossier-label">Роли в группах</p>
          <ul>
            {d.sponsoredChats.map((c) => (
              <li key={c.chatId}>
                Спонсор / архитектор · <strong>{c.name}</strong>
                {c.username ? ` @${c.username}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="pu-dossier-ach">
        <p className="pu-dossier-label">Витрина · {ach.length}</p>
        {ach.length === 0 ? (
          <p className="panel-shelf-muted">Достижений нет</p>
        ) : (
          <ul>
            {ach.map((a) => (
              <li key={a.instance_id}>
                <span>{a.icon_fallback || '⭐'}</span>
                <strong>{a.title || a.unique_code || a.instance_id}</strong>
                <em>{a.kind === 'official' ? 'офиц.' : 'своб.'}</em>
              </li>
            ))}
          </ul>
        )}
      </div>

      {isOwner && secrets && (
        <div className="pu-dossier-owner">
          <p className="pu-dossier-label">Только владелец · demo / 0demo</p>
          <div className="pu-dossier-owner-row">
            <div><span>demo</span><strong>{fmt(secrets.demo)}</strong></div>
            <div><span>0demo</span><strong>{fmt(secrets.zeroDemo)}</strong></div>
          </div>
        </div>
      )}

      {isOwner && canEdit && (
        <div className="pu-dossier-edit">
          <p className="pu-dossier-label">Редактирование параметров</p>
          <div className="pu-dossier-edit-grid">
            {[
              ['donate', 'Донат'],
              ['canwithdrawal', 'Лимит выводов'],
              ['wins', 'Wins'],
              ['loose', 'Losses'],
              ['winamount', 'Выиграно'],
              ['give', 'Лимит переводов'],
              ['referrals', 'Рефералы'],
              ['demo', 'demo'],
              ['zeroDemo', '0demo'],
            ].map(([key, label]) => (
              <label key={key} className="pu-field">
                <span className="pu-field-label">{label}</span>
                <input
                  className="panel-users-input pu-field-input"
                  value={draft[key] ?? ''}
                  onChange={(e) => setDraft((s) => ({ ...s, [key]: e.target.value.replace(/[^\d-]/g, '') }))}
                />
              </label>
            ))}
            <label className="pu-field pu-field-wide">
              <span className="pu-field-label">Дата регистрации</span>
              <input
                className="panel-users-input pu-field-input"
                type="datetime-local"
                value={draft.registeredAt || ''}
                onChange={(e) => setDraft((s) => ({ ...s, registeredAt: e.target.value }))}
              />
            </label>
          </div>
          <button type="button" className="panel-users-btn pu-action-cta" disabled={saving} onClick={save}>
            {saving ? '…' : 'Сохранить параметры'}
          </button>
        </div>
      )}
    </div>
  )
}
