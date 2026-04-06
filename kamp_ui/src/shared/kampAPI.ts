/**
 * Shared KampAPI types.
 *
 * Imported by the preload (builds the object) and by the renderer (consumes it).
 * Must contain only pure TypeScript — no Node.js or Electron imports.
 */

/** A panel contributed by a frontend extension. */
export type PanelManifest = {
  /** Unique identifier for the panel (e.g. "kamp-example-panel.stats"). */
  id: string
  /** Human-readable title shown in the nav tab. */
  title: string
  /**
   * Mount the panel into `container` and return a cleanup function.
   * Called once when the panel tab is first shown; cleanup is called on unmount.
   */
  render: (container: HTMLElement) => () => void
}

/** Descriptor returned by the main process for each discovered extension. */
export type ExtensionInfo = {
  id: string
  name: string
  /** Source code of the extension's entry point, read by the main process. */
  code: string
}

/** The full shape of window.KampAPI. */
export type KampAPI = {
  /**
   * Base URL of the kamp HTTP server.
   * Extensions should use this rather than hard-coding localhost:8000.
   */
  serverUrl: string

  panels: {
    /** Register a panel contributed by an extension. */
    register: (manifest: PanelManifest) => void
    /** Return a snapshot of all currently registered panels. */
    getAll: () => PanelManifest[]
    /**
     * Subscribe to panel registrations. The callback is invoked each time a
     * panel is registered. Returns an unsubscribe function.
     */
    onRegister: (callback: (manifest: PanelManifest) => void) => () => void
  }

  extensions: {
    /** Ask the main process to discover installed kamp-extension packages. */
    getAll: () => Promise<ExtensionInfo[]>
  }
}
