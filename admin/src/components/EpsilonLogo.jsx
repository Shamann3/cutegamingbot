import vivoEpsilonLogo from '../../../assets/VivoEpsilon.png'

/**
 * Марка Cute Epsilon — тот же ассет, что на экране регистрации.
 * size: 'sm' | 'md' | 'lg' | 'hero'
 */
export default function EpsilonLogo({
  size = 'md',
  className = '',
  alt = 'Cute Epsilon',
  decorative = false,
}) {
  return (
    <img
      className={`eps-logo eps-logo--${size}${className ? ` ${className}` : ''}`}
      src={vivoEpsilonLogo}
      alt={decorative ? '' : alt}
      draggable={false}
      decoding="async"
      aria-hidden={decorative ? true : undefined}
    />
  )
}

export { vivoEpsilonLogo }
