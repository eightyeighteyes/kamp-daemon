import { useEffect, useState } from 'react'
import type { PanelManifest } from '../../../shared/kampAPI'

export type { PanelManifest }

/**
 * Returns the live list of panels registered by loaded extensions.
 *
 * Seeds from the current KampAPI registry (panels registered before React
 * mounted) and subscribes to the "kamp:panel-registered" CustomEvent for
 * any panels registered afterward.
 */
export function useRegisteredPanels(): PanelManifest[] {
  const [panels, setPanels] = useState<PanelManifest[]>(() => window.KampAPI?.panels.getAll() ?? [])

  useEffect(() => {
    // onRegister() goes through contextBridge — the preload calls our callback
    // directly, bypassing the context-isolation boundary that blocks CustomEvents.
    return window.KampAPI.panels.onRegister((manifest) => {
      setPanels((prev) => [...prev, manifest])
    })
  }, [])

  return panels
}
