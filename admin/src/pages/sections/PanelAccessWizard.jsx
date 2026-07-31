import { useMemo, useState } from 'react'
import { wizardSlides, childKey } from '../../constants/panelAccessTree'

function memberName(m) {
  if (!m) return '—'
  return m.firstName || (m.username ? `@${m.username}` : `ID ${m.userId}`)
}

/**
 * «Простая настройка» — слайд-шоу по разделам для одного администратора.
 * onSetKey(userId, accessKey, allowed) — optimistic + API снаружи.
 */
export default function PanelAccessWizard({
  members = [],
  roleDefaults = {},
  busyKeys,
  onSetKey,
}) {
  const [userId, setUserId] = useState(members[0]?.userId ?? null)
  const [step, setStep] = useState(0)
  const slides = useMemo(() => wizardSlides(), [])

  const member = useMemo(
    () => members.find((m) => m.userId === userId) || null,
    [members, userId],
  )

  const slide = slides[step] || slides[0]
  const total = slides.length
  const progress = total ? Math.round(((step + 1) / total) * 100) : 0

  const isOn = (key) => {
    if (!member) return false
    if (Object.prototype.hasOwnProperty.call(member.overrides || {}, key)) {
      return !!member.overrides[key]
    }
    const roleMap = roleDefaults[member.role] || {}
    if (Object.prototype.hasOwnProperty.call(roleMap, key)) return !!roleMap[key]
    // Фоллбек: родители из effectiveSections, дети из effectiveTabs
    if (!key.includes('.')) {
      return (member.effectiveSections || []).includes(key)
    }
    const [parent, tab] = key.split('.')
    return (member.effectiveTabs?.[parent] || []).includes(tab)
  }

  const busy = (key) => busyKeys?.has(`wiz-${userId}-${key}`)

  const setAccess = (key, allowed) => {
    if (!member) return
    onSetKey?.(member.userId, key, allowed)
  }

  if (!members.length) {
    return (
      <div className="pa-pane">
        <p className="sec-empty">Нет администраторов для настройки</p>
      </div>
    )
  }

  return (
    <div className="pa-pane pa-pane-wizard">
      <div className="pa-wiz">
        <div className="pa-wiz-grid" aria-hidden="true" />

        <header className="pa-wiz-head">
          <div>
            <p className="pa-wiz-kicker">SIMPLE SETUP // GUIDE</p>
            <h3 className="pa-wiz-title">Простая настройка</h3>
            <p className="pa-wiz-sub">
              Выберите администратора — пройдём по разделам по одному и решим, что ему видно.
            </p>
          </div>
          <label className="pa-wiz-pick">
            <span>Администратор</span>
            <select
              className="sec-input"
              value={userId ?? ''}
              onChange={(e) => {
                setUserId(Number(e.target.value) || null)
                setStep(0)
              }}
            >
              {members.map((m) => (
                <option key={m.userId} value={m.userId}>
                  {memberName(m)} · {m.roleLabel}
                </option>
              ))}
            </select>
          </label>
        </header>

        <div className="pa-wiz-progress" aria-hidden="true">
          <div className="pa-wiz-progress-bar" style={{ width: `${progress}%` }} />
          <span className="pa-wiz-progress-txt">
            {step + 1} / {total}
          </span>
        </div>

        {slide && member && (
          <div className="pa-wiz-slide" key={`${member.userId}-${slide.id}`}>
            <div className="pa-wiz-slide-meta">
              <span className="pa-wiz-slide-idx">SECTION {String(step + 1).padStart(2, '0')}</span>
              <h4 className="pa-wiz-slide-title">{slide.label}</h4>
              <p className="pa-wiz-slide-blurb">{slide.blurb}</p>
            </div>

            <div className="pa-wiz-main-actions">
              <button
                type="button"
                className={`pa-wiz-big${isOn(slide.id) ? ' is-on' : ''}`}
                disabled={busy(slide.id)}
                onClick={() => setAccess(slide.id, true)}
              >
                <span className="pa-wiz-big-code">ALLOW</span>
                <span>Показывать раздел</span>
              </button>
              <button
                type="button"
                className={`pa-wiz-big pa-wiz-big-deny${!isOn(slide.id) ? ' is-on' : ''}`}
                disabled={busy(slide.id)}
                onClick={() => setAccess(slide.id, false)}
              >
                <span className="pa-wiz-big-code">DENY</span>
                <span>Скрыть раздел</span>
              </button>
            </div>

            {slide.tabs?.length > 0 && (
              <div className={`pa-wiz-children${!isOn(slide.id) ? ' is-dim' : ''}`}>
                <p className="pa-wiz-children-label">
                  Внутренние вкладки
                  {!isOn(slide.id) && <em> · сначала откройте раздел</em>}
                </p>
                <ul className="pa-wiz-child-list">
                  {slide.tabs.map((t) => {
                    const key = childKey(slide.id, t.id)
                    const on = isOn(key)
                    return (
                      <li key={t.id} className="pa-wiz-child">
                        <div className="pa-wiz-child-text">
                          <strong>{t.label}</strong>
                          <span>{t.blurb}</span>
                        </div>
                        <div className="pa-wiz-child-ops">
                          <button
                            type="button"
                            className={`pa-pill${on ? ' is-on' : ''}`}
                            disabled={!isOn(slide.id) || busy(key)}
                            onClick={() => setAccess(key, true)}
                          >
                            Видно
                          </button>
                          <button
                            type="button"
                            className={`pa-pill pa-pill-danger${!on ? ' is-on' : ''}`}
                            disabled={!isOn(slide.id) || busy(key)}
                            onClick={() => setAccess(key, false)}
                          >
                            Скрыто
                          </button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}

            <footer className="pa-wiz-nav">
              <button
                type="button"
                className="sec-btn sec-btn-ghost"
                disabled={step <= 0}
                onClick={() => setStep((s) => Math.max(0, s - 1))}
              >
                ← Назад
              </button>
              <div className="pa-wiz-dots" aria-hidden="true">
                {slides.map((s, i) => (
                  <button
                    key={s.id}
                    type="button"
                    className={`pa-wiz-dot${i === step ? ' is-on' : ''}${isOn(s.id) ? ' is-allowed' : ''}`}
                    onClick={() => setStep(i)}
                    title={s.label}
                  />
                ))}
              </div>
              {step < total - 1 ? (
                <button
                  type="button"
                  className="sec-btn sec-btn-primary pa-wiz-next"
                  onClick={() => setStep((s) => Math.min(total - 1, s + 1))}
                >
                  Далее →
                </button>
              ) : (
                <button
                  type="button"
                  className="sec-btn sec-btn-primary pa-wiz-next"
                  onClick={() => setStep(0)}
                >
                  В начало
                </button>
              )}
            </footer>
          </div>
        )}
      </div>
    </div>
  )
}
