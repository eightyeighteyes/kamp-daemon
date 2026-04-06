import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'
import { buildKampAPI } from './kampAPI'

// Custom APIs for renderer
const api = {
  openDirectory: (): Promise<string | null> => ipcRenderer.invoke('open-directory'),
  onOpenPreferences: (callback: () => void): (() => void) => {
    const handler = (): void => callback()
    ipcRenderer.on('open-preferences', handler)
    // Return a cleanup function so the caller can unsubscribe.
    return () => ipcRenderer.off('open-preferences', handler)
  }
}

const kampAPI = buildKampAPI()

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
    contextBridge.exposeInMainWorld('KampAPI', kampAPI)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.api = api
  // @ts-ignore (define in dts)
  window.KampAPI = kampAPI
}
