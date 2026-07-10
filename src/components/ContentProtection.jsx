import { useContentProtection } from '../hooks/useContentProtection'

export default function ContentProtection({ children }) {
  useContentProtection()
  return children
}
