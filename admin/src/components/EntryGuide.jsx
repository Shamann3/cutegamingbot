import { Fragment, useCallback, useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { OFFICE_SCREENS, SCREENS, WORDS } from '../entry_design'
import { blocksOf, inlineParts, stepStates } from '../lib/guideText'

const LEAVE_MS = 220
// Запоздалый click того же касания не должен закрыть только что открытый лист.
const OPEN_GRACE_MS = 350
const TAG = { b: 'strong', i: 'em', u: 'u', code: 'code' }

function leaveDelay() {
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)')
  return media?.matches ? 0 : LEAVE_MS
}

function part(node, key) {
  if (typeof node === 'string') return <Fragment key={key}>{node}</Fragment>
  const Tag = TAG[node.tag] || 'span'
  return <Tag key={key}>{node.kids.map(part)}</Tag>
}

function Rich({ text }) {
  return <>{inlineParts(text).map(part)}</>
}

function GuideBody({ text }) {
  return blocksOf(text).map((block, index) => {
    if (block.kind === 'head') {
      return <h3 key={index} className="entry-guide-h"><Rich text={block.lines[0]} /></h3>
    }
    if (block.kind === 'steps') {
      return (
        <ol key={index} className="entry-guide-ol" start={block.start}>
          {block.lines.map((line, i) => <li key={i}><Rich text={line} /></li>)}
        </ol>
      )
    }
    if (block.kind === 'list') {
      return (
        <ul key={index} className="entry-guide-ul">
          {block.lines.map((line, i) => <li key={i}><Rich text={line} /></li>)}
        </ul>
      )
    }
    return (
      <p key={index} className="entry-guide-p">
        {block.lines.map((line, i) => (
          <Fragment key={i}>
            {i > 0 && <br />}
            <Rich text={line} />
          </Fragment>
        ))}
      </p>
    )
  })
}

function GuideSheet({ open, title, text, onClose, backTo }) {
  const titleId = useId()
  const sheetRef = useRef(null)
  const [mounted, setMounted] = useState(open)
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    if (open) {
      setMounted(true)
      setLeaving(false)
      return undefined
    }
    if (!mounted) return undefined
    setLeaving(true)
    const timer = window.setTimeout(() => {
      setMounted(false)
      setLeaving(false)
      backTo?.current?.focus?.()
    }, leaveDelay())
    return () => window.clearTimeout(timer)
  }, [open, mounted, backTo])

  useEffect(() => {
    if (!mounted || leaving) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKey)
    sheetRef.current?.focus({ preventScroll: true })
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [mounted, leaving, onClose])

  if (!mounted) return null
  return createPortal(
    <div className={`choice-layer entry-guide-layer${leaving ? ' is-leaving' : ''}`} onClick={onClose}>
      <div className="choice-dim" />
      <div className="choice-sheet-motion">
        <div
          ref={sheetRef}
          className="choice-sheet entry-guide-sheet"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          tabIndex={-1}
          onClick={(event) => event.stopPropagation()}
        >
          <p id={titleId} className="choice-sheet-title">{title}</p>
          <div className="entry-guide-body">
            <GuideBody text={text} />
          </div>
          <button type="button" className="choice-close" onClick={onClose}>
            {WORDS.close}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

/**
 * Шаги входа над формой: позади — галочка, сейчас — подсвечен и с пояснением, впереди — приглушены.
 * onPick делает шаги кнопками: так создатель листает их в предпросмотре.
 */
export default function EntryGuide({ screen, at, onPick = null }) {
  const [open, setOpen] = useState(false)
  const moreRef = useRef(null)
  const openedAt = useRef(0)
  const show = useCallback(() => {
    openedAt.current = Date.now()
    setOpen(true)
  }, [])
  const hide = useCallback(() => {
    if (Date.now() - openedAt.current < OPEN_GRACE_MS) return
    setOpen(false)
  }, [])
  if (!screen) return null
  const states = stepStates(screen.steps, at)
  const Row = onPick ? 'button' : 'div'

  return (
    <section className="entry-guide" aria-label={screen.title}>
      <div className="entry-guide-head">
        <p className="entry-guide-title">{screen.title}</p>
        <button
          ref={moreRef}
          type="button"
          className="entry-guide-more"
          aria-haspopup="dialog"
          onClick={show}
        >
          {WORDS.more}
        </button>
      </div>
      <ol className="entry-guide-steps">
        {screen.steps.map((step, index) => {
          const state = states[index]
          return (
            <li key={step.id} className={`entry-guide-step is-${state}`} aria-current={state === 'now' ? 'step' : undefined}>
              <Row
                className="entry-guide-row"
                {...(onPick ? { type: 'button', onClick: () => onPick(step.id), 'aria-pressed': state === 'now' } : {})}
              >
                <span className="entry-guide-dot" aria-hidden="true">{state === 'done' ? '✓' : index + 1}</span>
                <span className="entry-guide-copy">
                  <span className="entry-guide-name">{step.title}</span>
                  <span className="entry-guide-line-slot" aria-hidden={state === 'now' ? undefined : true}>
                    <span className="entry-guide-line">
                      <span><Rich text={step.line} /></span>
                    </span>
                  </span>
                </span>
              </Row>
            </li>
          )
        })}
      </ol>
      <GuideSheet
        open={open}
        title={screen.title}
        text={screen.more}
        backTo={moreRef}
        onClose={hide}
      />
    </section>
  )
}

/** Предпросмотр у создателя: все экраны входа раздела, по шагам и с «Подробнее». */
export function EntryGuideBoard({ office = 'staff' }) {
  const ids = OFFICE_SCREENS[office] || OFFICE_SCREENS.staff
  const [screenId, setScreenId] = useState(ids[0])
  const screen = SCREENS[screenId] || SCREENS[ids[0]]
  const [at, setAt] = useState(screen?.steps[0]?.id)

  return (
    <section className="sec-ipban-form staff-invite-block entry-guide-board">
      <h3 className="sec-ipban-form-title">{WORDS.boardTitle}</h3>
      <p className="staff-hint">{WORDS.boardLead}</p>
      <div className="entry-guide-tabs" role="tablist" aria-label={WORDS.boardTitle}>
        {ids.map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={id === screenId}
            className={`entry-guide-tab${id === screenId ? ' is-on' : ''}`}
            onClick={() => {
              setScreenId(id)
              setAt(SCREENS[id]?.steps[0]?.id)
            }}
          >
            {SCREENS[id]?.tab || id}
          </button>
        ))}
      </div>
      <div className="entry-guide-stage">
        <EntryGuide key={screenId} screen={screen} at={at} onPick={setAt} />
      </div>
      <p className="staff-hint entry-guide-file">{WORDS.boardFile}</p>
    </section>
  )
}
