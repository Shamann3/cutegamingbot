import EntranceSeal from '../components/EntranceSeal'

/** Стартовый экран: печать Cute Epsilon при открытии панели. */
export default function SplashPage({ displayName, onFinished }) {
  return (
    <EntranceSeal
      displayName={displayName}
      variant="boot"
      onFinished={onFinished}
    />
  )
}
