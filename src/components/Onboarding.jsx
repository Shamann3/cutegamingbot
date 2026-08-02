import { useOnboarding } from '../context/OnboardingContext'
import { useEscapeClose } from '../hooks/useEscapeClose'
import { ONBOARDING_WELCOME } from '../constants/onboardingSteps'
import Portal from './Portal'

export default function Onboarding() {
  const { visible, starting, dismiss } = useOnboarding()

  useEscapeClose(visible, dismiss)

  if (!visible || starting) return null

  return (
    <Portal lockScroll>
      <div className="onboarding-welcome-root" role="presentation">
        <div className="onboarding-overlay onboarding-overlay--dim" aria-hidden />

        <div
          className="onboarding-welcome-card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="onboarding-welcome-title"
        >
          <div className="farm-header-crest-wrap onboarding-welcome-crest-wrap">
            <div className="farm-header-crest-glow" aria-hidden />
            <img
              src="/assets/cute-crest.png?v=4"
              alt=""
              draggable={false}
              className="farm-header-crest-img"
            />
          </div>

          <p className="farm-header-cute onboarding-welcome-eyebrow">{ONBOARDING_WELCOME.eyebrow}</p>
          <h1 id="onboarding-welcome-title" className="farm-header-title farm-title-serif onboarding-welcome-title">
            {ONBOARDING_WELCOME.title}
          </h1>
          <p className="onboarding-welcome-text">{ONBOARDING_WELCOME.text}</p>

          <button type="button" className="farm-btn-primary onboarding-welcome-btn" onClick={dismiss}>
            {ONBOARDING_WELCOME.cta}
          </button>
        </div>
      </div>
    </Portal>
  )
}
