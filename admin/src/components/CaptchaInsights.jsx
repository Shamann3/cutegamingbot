import { CopyableId, CopyableUsername } from './Copyable'

function fmt(n) {
  return Number(n || 0).toLocaleString('ru-RU')
}

function WhoMark({ name, userId, username, onOpen }) {
  return (
    <span className="cap-who">
      {onOpen && userId ? (
        <button type="button" className="cap-link" onClick={() => onOpen(userId)}>{name || 'игрок'}</button>
      ) : <span>{name || 'игрок'}</span>}
      {username ? <CopyableUsername value={username} /> : null}
      {userId ? <CopyableId value={userId} /> : null}
    </span>
  )
}

function ChatMark({ name, chatId, username, onOpen }) {
  return (
    <span className="cap-who">
      {onOpen && chatId ? (
        <button type="button" className="cap-link" onClick={() => onOpen(chatId)}>{name || 'группа'}</button>
      ) : <span>{name || 'группа'}</span>}
      {username ? <CopyableUsername value={username} label="username группы" /> : null}
      {chatId ? <CopyableId value={chatId} label="id группы" /> : null}
    </span>
  )
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

function FailNote({ ok }) {
  if (ok !== false) return null
  return <p className="grp-help">Капчу из базы прочитать не удалось — проверьте логи админки. Карточка не должна быть пустой после того, как кто-то написал в группу.</p>
}

export function CaptchaOverviewBlock({ data, onOpenChat, onOpenUser }) {
  const c = data || {}
  const facts = Array.isArray(c.facts) ? c.facts : []
  return (
    <div className="cap-block">
      <FailNote ok={c.ok} />
      <div className="grp-stat-grid">
        <div className="grp-stat"><span className="grp-stat-label">Прошли</span><strong className="grp-stat-value">{fmt(c.passed)}</strong><span className="grp-stat-hint">человек × групп</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Ошибки</span><strong className="grp-stat-value">{fmt(c.fails)}</strong><span className="grp-stat-hint">нажатий мимо</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Карточек</span><strong className="grp-stat-value">{fmt(c.shown)}</strong><span className="grp-stat-hint">показано</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Удалено</span><strong className="grp-stat-value">{fmt(c.blocked)}</strong><span className="grp-stat-hint">сообщений до капчи</span></div>
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
                <ChatMark name={g.name} chatId={g.chatId} username={g.username} onOpen={onOpenChat} />
                <span>{fmt(g.passed)}</span>
              </li>
            ))}
            {!(c.topGroups || []).length && <li className="grp-help">Ещё нет прохождений</li>}
          </ul>
          <h3 className="grp-card-title" style={{ marginTop: '1rem' }}>Кто чаще ошибается</h3>
          <ul className="cap-list">
            {(c.topFailUsers || []).map((u) => (
              <li key={u.userId}>
                <WhoMark name={u.name} userId={u.userId} username={u.username} onOpen={onOpenUser} />
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
  const waiting = Array.isArray(c.waiting) ? c.waiting : []
  const shown = Array.isArray(c.recentShown) ? c.recentShown : []
  const pendingPeople = Array.isArray(c.pendingPeople) ? c.pendingPeople : []
  const passed = Number(c.passed || 0)
  const notPassed = c.notPassedHint != null
    ? c.notPassedHint
    : (members != null ? Math.max(0, Number(members) - passed) : null)
  return (
    <div className="cap-block">
      <FailNote ok={c.ok} />
      <div className="grp-stat-grid">
        <div className="grp-stat"><span className="grp-stat-label">Статус</span><strong className="grp-stat-value">{c.enabled === false ? 'выкл' : 'вкл'}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Прошли</span><strong className="grp-stat-value">{fmt(passed)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Ещё не прошли</span><strong className="grp-stat-value">{notPassed == null ? '—' : fmt(notPassed)}</strong><span className="grp-stat-hint">{members != null ? `из ${fmt(members)} в Telegram` : 'если известен состав'}</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Карточек</span><strong className="grp-stat-value">{fmt(c.shown)}</strong><span className="grp-stat-hint">показано</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Удалено</span><strong className="grp-stat-value">{fmt(c.blocked)}</strong><span className="grp-stat-hint">сообщений до капчи</span></div>
        <div className="grp-stat"><span className="grp-stat-label">Писали, не прошли</span><strong className="grp-stat-value">{fmt(waiting.length || c.uniqueTriggered)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Висят сейчас</span><strong className="grp-stat-value">{fmt(c.pending)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Ошибки</span><strong className="grp-stat-value">{fmt(c.fails)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Доходят</span><strong className="grp-stat-value">{c.passRate == null ? '—' : `${c.passRate}%`}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">Среднее время</span><strong className="grp-stat-value">{dur(c.avgDurationMs)}</strong></div>
        <div className="grp-stat"><span className="grp-stat-label">При входе / из чата</span><strong className="grp-stat-value">{fmt(c.joinPasses)} / {fmt(c.messagePasses)}</strong></div>
      </div>
      {c.enabled === false && (
        <p className="grp-help">Владелец выключил капчу{c.disabledAt ? ` · ${when(c.disabledAt)}` : ''}{c.disabledBy ? <> · <CopyableId value={c.disabledBy} /></> : ''}</p>
      )}

      <div className="grp-card" style={{ marginBottom: '1rem' }}>
        <h3 className="grp-card-title">Типы карточек в этой группе</h3>
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
              <tr><td colSpan={4}>Пока нет показов в этой группе</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="grp-two">
        <div className="grp-card">
          <h3 className="grp-card-title">Ещё не прошли</h3>
          <ul className="cap-list">
            {waiting.map((u) => (
              <li key={`w-${u.userId}`}>
                <WhoMark name={u.name} userId={u.userId} username={u.username} onOpen={onOpenUser} />
                <span>{fmt(u.shown)} показ. · {fmt(u.fails)} ош. · {when(u.at)}</span>
              </li>
            ))}
            {pendingPeople.filter((p) => !waiting.some((w) => w.userId === p.userId)).map((p) => (
              <li key={`p-${p.userId}`}>
                <WhoMark name={p.name} userId={p.userId} username={p.username} onOpen={onOpenUser} />
                <span>висит · {p.variantLabel} · {when(p.at)}</span>
              </li>
            ))}
            {!waiting.length && !pendingPeople.length && <li className="grp-help">Все, кто писал, уже прошли — или капчу ещё не показывали</li>}
          </ul>
        </div>
        <div className="grp-card">
          <h3 className="grp-card-title">Последние сообщения до капчи</h3>
          <ul className="cap-list">
            {shown.map((f, i) => (
              <li key={`s-${f.userId}-${f.at}-${i}`}>
                <WhoMark name={f.name} userId={f.userId} username={f.username} onOpen={onOpenUser} />
                <span>{f.label}{f.preview ? ` · «${f.preview}»` : ''} · {when(f.at)}</span>
              </li>
            ))}
            {!shown.length && <li className="grp-help">Пока никто не писал до прохождения</li>}
          </ul>
        </div>
      </div>

      <div className="grp-two">
        <div className="grp-card">
          <h3 className="grp-card-title">Последние ошибки</h3>
          <ul className="cap-list">
            {(c.recentFails || []).map((f, i) => (
              <li key={`${f.userId}-${f.at}-${i}`}>
                <WhoMark name={f.name} userId={f.userId} username={f.username} onOpen={onOpenUser} />
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
                <WhoMark name={p.name} userId={p.userId} username={p.username} onOpen={onOpenUser} />
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
  const hasAny = groups.length > 0 || recent.length > 0 || pending.length > 0 || Number(c.shown) > 0 || Number(c.fails) > 0 || Number(c.blocked) > 0
  return (
    <div className="pu-dossier-captcha">
      <p className="pu-dossier-label">Капча в группах</p>
      {c.ok === false && (
        <p className="panel-shelf-muted">Капчу из базы прочитать не удалось</p>
      )}
      <div className="pu-dossier-grid">
        <div className="pu-dossier-tile">
          <span>Карточек</span>
          <strong>{fmt(c.shown)}</strong>
          <em>{c.blocked ? `удалили ${fmt(c.blocked)} сообщ.` : 'показали'}</em>
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
              <ChatMark name={g.name} chatId={g.chatId} username={g.username} onOpen={onOpenChat} />
              <em>прошёл · {g.variantLabel} · {g.attempts} попыт. · {when(g.passedAt)}</em>
            </li>
          ))}
        </ul>
      )}
      {recent.length > 0 && (
        <ul>
          {recent.slice(0, 8).map((e, i) => (
            <li key={`ev-${e.at}-${i}`}>
              <ChatMark name={e.chatName} chatId={e.chatId} username={e.chatUsername} onOpen={onOpenChat} />
              <em>{e.label}{e.preview ? ` · «${e.preview}»` : ''}{e.variantLabel ? ` · ${e.variantLabel}` : ''} · {when(e.at)}</em>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
