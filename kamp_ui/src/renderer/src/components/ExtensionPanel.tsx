import React, { useEffect, useRef } from 'react'
import type { PanelManifest } from '../hooks/useRegisteredPanels'

/**
 * Mounts an extension panel's DOM renderer into a container div.
 *
 * The panel's `render(container)` is called once on mount and its returned
 * cleanup function is called on unmount — matching the React useEffect contract.
 * Extensions render plain DOM; they never touch React internals.
 */
export function ExtensionPanel({ panel }: { panel: PanelManifest }): React.JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    return panel.render(el)
  }, [panel])

  return (
    <div
      className="extension-panel"
      ref={containerRef}
      style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}
    />
  )
}
