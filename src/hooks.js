// Small custom hooks used to keep repeated logic out of components.

import { useEffect } from 'react'

export function useAutoScroll(ref, dependencies = []) {
  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, dependencies)
}
