function fmt(n) {
  return Number(n || 0).toLocaleString('ru-RU')
}

function dur(ms) {
  if (ms == null || !Number.isFinite(Number(ms))) return '—'
  const s = Math.max(0, Number(ms) / 1000)
  if (s < 10) return `${s.toFixed(1)} с`
  if (s < 90) return `${Math.round(s)} с`
  return `${Math.round(s / 60)} мин`
}

function when(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return String(iso).slice(0, 16)
  }
}

export function CaptchaOverviewBlock({ data, onOpenChat, onOpenUser }) {
  const c = data || {}
  const facts = Array.isArray(c.facts) ? c.facts : []
  return (
    <div className="cap-block">
      <div className="grp-stat-grid">
        <div className="grp-stat"><span className="grp-stat-label">Прошли</span><strong className="grp-stat-value">{fmt(c.passed)}</strong><span className="grp-stat-hint">человек × групп</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Ошибки</span><strong className="grp-stat-value">{fmt(c.fails)}</strong><span className="grp-stat-hint">нажатий мимо</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Карточек</span><strong className="grp-stat-value">{fmt(c.shown)}</strong><span className="grp-stat-hint">показано</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Доходят</span><strong className="grp-stat-value">{c.passRate == null ? '—' : `${c.passRate}%`}</strong><span className="grp-stat-hint">с первой карточки до успеха</span></div>
        <div className="grp-stat"><span className="grp-stat-label">С первой попытки</span><strong className="grp-stat-value">{c.firstTryRate == null ? '—' : `${c.firstTryRate}%`}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Среднее время</span><strong className="grp-stat-value">{dur(c.avgDurationMs)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Висят сейчас</span><strong className="grp-stat-value">{fmt(c.pending)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Выключили</span><strong className="grp-stat-value">{fmt(c.disabledChats)}</strong><span className="grp-stat-hint">групп</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Групп с капчей</span><strong className="grp-stat-value">{fmt(c.enabledChats)}</strong><span className="grp-stat-hint">где уже показывали</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Последнее событие</span><strong className="grp-stat-value">{when(c.lastEventAt)}</strong></div>
      </div>

      {facts.length > 0 && (
        <div className="cap-facts">
          {facts.map((f) => <p key={f}>{f}</p>)}
        </div>
      )}

      <div className="grp-two">
        <div className="grp-card">
          <h3 className="grp-card-title">Типы карточек</h3>
          <table className="grp-table">
            <thead>
              <tr><th>Тип</th><th>Показ</th><th>Успех</th><th>Ошибки</th></tr>
            </thead>
            <tbody>
              {(c.variants || []).map((v) => (
                <tr key={v.variant}>
                  <td>{v.label}</td>
                  <td>{fmt(v.shown)}</td>
                  <td>{fmt(v.passed)}</td>
                  <td>{fmt(v.fails)}{v.failRate != null ? ` · ${v.failRate}%` : ''}</td>
                </tr>
              ))}
              {!(c.variants || []).length && (
                <tr><td colSpan={4}>Пока нет данных — появятся после первых капч</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="grp-card">
          <h3 className="grp-card-title">Где чаще проходят</h3>
          <ul className="cap-list">
            {(c.topGroups || []).map((g) => (
              <li key={g.chatId}>
                <button type="button" className="cap-link" onClick={() => onOpenChat?.(g.chatId)}>
                  {g.name}
                </button>
                <span>{fmt(g.passed)}</span>
              </li>
            ))}
            {!(c.topGroups || []).length && <li className="grp-help">Ещё нет прохождений</li>}
          </ul>
          <h3 className="grp-card-title" style={{ marginTop: '1rem' }}>Кто чаще ошибается</h3>
          <ul className="cap-list">
            {(c.topFailUsers || []).map((u) => (
              <li key={u.userId}>
                <button type="button" className="cap-link" onClick={() => onOpenUser?.(u.userId)}>
                  {u.name}{u.username ? ` · @${u.username}` : ''}
                </button>
                <span>{fmt(u.fails)}</span>
              </li>
            ))}
            {!(c.topFailUsers || []).length && <li className="grp-help">Ошибок ещё нет</li>}
          </ul>
        </div>
      </div>
    </div>
  )
}

export function CaptchaChatBlock({ data, members, onOpenUser }) {
  const c = data || {}
  return (
    <div className="cap-block">
      <div className="grp-stat-grid">
        <div className="grp-stat"><span className="grp-stat-label">Статус</span><strong className="grp-stat-value">{c.enabled === false ? 'выкл' : 'вкл'}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Прошли</span><strong className="grp-stat-value">{fmt(c.passed)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Ещё не прошли</span><strong className="grp-stat-value">{c.notPassedHint == null ? '—' : fmt(c.notPassedHint)}</strong><span className="grp-stat-hint">{members != null ? `из ${fmt(members)} в Telegram` : 'если известен состав'}</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Ошибки</span><strong className="grp-stat-value">{fmt(c.fails)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Доходят</span><strong className="grp-stat-value">{c.passRate == null ? '—' : `${c.passRate}%`}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Среднее время</span><strong className="grp-stat-value">{dur(c.avgDurationMs)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">При входе</span><strong className="grp-stat-value">{fmt(c.joinPasses)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Со старых участников</span><strong className="grp-stat-value">{fmt(c.messagePasses)}</strong></div>
      </div>
      {c.enabled === false && (
        <p className="grp-help">Владелец выключил капчу{c.disabledAt ? ` · ${when(c.disabledAt)}` : ''}{c.disabledBy ? ` · id ${c.disabledBy}` : ''}</p>
      )}

      <div className="grp-two">
        <div className="grp-card">
          <h3 className="grp-card-title">Последние ошибки</h3>
          <ul className="cap-list">
            {(c.recentFails || []).map((f, i) => (
              <li key={`${f.userId}-${f.at}-${i}`}>
                <button type="button" className="cap-link" onClick={() => onOpenUser?.(f.userId)}>
                  {f.name}
                </button>
                <span>{f.variantLabel} · {when(f.at)}</span>
              </li>
            ))}
            {!(c.recentFails || []).length && <li className="grp-help">Пока без ошибок</li>}
          </ul>
        </div>
        <div className="grp-card">
          <h3 className="grp-card-title">Последние прохождения</h3>
          <ul className="cap-list">
            {(c.recentPasses || []).map((p) => (
              <li key={`${p.userId}-${p.at}`}>
                <button type="button" className="cap-link" onClick={() => onOpenUser?.(p.userId)}>
                  {p.name}
                </button>
                <span>{p.variantLabel} · {dur(p.durationMs)} · {p.attempts} попыт.</span>
              </li>
            ))}
            {!(c.recentPasses || []).length && <li className="grp-help">Ещё никто не прошёл</li>}
          </ul>
        </div>
      </div>
    </div>
  )
}

export function CaptchaDossierBlock({ data, onOpenChat }) {
  const c = data || {}
  const groups = Array.isArray(c.groups) ? c.groups : []
  const recent = Array.isArray(c.recent) ? c.recent : []
  const pending = Array.isArray(c.pendingCards) ? c.pendingCards : []
  const hasAny = groups.length > 0 || recent.length > 0 || pending.length > 0 || Number(c.shown) > 0 || Number(c.fails) > 0
  return (
    <div className="pu-dossier-captcha">
      <p className="pu-dossier-label">Капча в группах</p>
      <div className="pu-dossier-grid">
        <div className="pu-dossier-tile">
          <span>Карточек</span>
          <strong>{fmt(c.shown)}</strong>
          <em>показали</em>
        </div>
        <div className="pu-dossier-tile">
          <span>Прошёл</span>
          <strong>{fmt(c.passedGroups)}</strong>
          <em>групп навсегда</em>
        </div>
        <div className="pu-dossier-tile">
          <span>Ошибки</span>
          <strong>{fmt(c.fails)}</strong>
          <em>неверных нажатий</em>
        </div>
        <div className="pu-dossier-tile">
          <span>Среднее время</span>
          <strong>{dur(c.avgDurationMs)}</strong>
          {c.firstTryPasses ? <em>с первой: {fmt(c.firstTryPasses)}</em> : <em>{c.lastShownAt ? `показ ${when(c.lastShownAt)}` : 'ещё нет успеха'}</em>}
        </div>
      </div>
      {c.hardestVariant && (
        <p className="panel-shelf-muted">Чаще путает «{c.hardestVariant.label}»</p>
      )}
      {pending.length > 0 && (
        <p className="panel-shelf-muted">Сейчас висит карточка в {pending.map((p) => p.name).join(', ')}</p>
      )}
      {!hasAny && (
        <p className="panel-shelf-muted">В группах капчу ещё не показывали</p>
      )}
      {groups.length > 0 && (
        <ul>
          {groups.map((g) => (
            <li key={`pass-${g.chatId}`}>
              <button type="button" className="cap-link" onClick={() => onOpenChat?.(g.chatId)}>
                {g.name}
              </button>
              <em>прошёл · {g.variantLabel} · {g.attempts} попыт. · {when(g.passedAt)}</em>
            </li>
          ))}
        </ul>
      )}
      {recent.length > 0 && (
        <ul>
          {recent.slice(0, 8).map((e, i) => (
            <li key={`ev-${e.at}-${i}`}>
              <button type="button" className="cap-link" onClick={() => onOpenChat?.(e.chatId)}>
                {e.chatName}
              </button>
              <em>{e.label}{e.variantLabel ? ` · ${e.variantLabel}` : ''} · {when(e.at)}</em>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
