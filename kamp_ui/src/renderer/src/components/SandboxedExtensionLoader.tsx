import { useEffect, useRef } from 'react'
import type { ExtensionInfo, SlotId } from '../../../shared/kampAPI'

/**
 * Static shim injected into every community extension iframe via srcdoc.
 *
 * The shim is static (no per-extension data) so its SHA-256 hash can be
 * listed in index.html's script-src CSP, satisfying Chromium's rule that
 * srcdoc iframes inherit the parent document's CSP.
 *
 * Extension code and metadata arrive via postMessage (kamp:init) sent after
 * the iframe's onLoad fires. The shim dynamically imports the extension code
 * as a blob: URL and calls register(). The extension's panels.register() call
 * sends kamp:register-panel back to the host, which registers a real panel
 * whose render() creates a fresh iframe on each tab activation.
 *
 * Hash (index.html script-src): sha256-fXNWd+rx+M3h78bhaTFeSztcM/uSwO0hPDuYKsxUtKQ=
 * If you change SANDBOX_SHIM, recompute the hash and update index.html.
 *
 * NOTE: sandboxed iframes without allow-same-origin reload when moved in the
 * DOM, so we do NOT use a holding-area/move strategy. Each panel mount creates
 * a fresh iframe; state is lost on tab switch.
 */
// prettier-ignore
// If you change this string, recompute the hash and update index.html script-src:
//   node -e "const s='<paste shim>';console.log('sha256-'+require('crypto').createHash('sha256').update(s,'utf8').digest('base64'))"
const SANDBOX_SHIM = `(function(){var r={},c={},pending=null;window.addEventListener('message',function(e){if(e.source!==window.parent)return;var m=e.data;if(!m||typeof m.type!=='string')return;if(m.type==='kamp:init'){var id=m.id,su=m.serverUrl;var K={serverUrl:su,panels:{register:function(p){if(!p||typeof p.id!=='string')return;r[p.id]=p.render;window.parent.postMessage({type:'kamp:register-panel',extensionId:id,manifest:{id:p.id,title:p.title,defaultSlot:p.defaultSlot,compatibleSlots:p.compatibleSlots}},'*');if(pending===p.id&&typeof r[p.id]==='function'){c[p.id]=r[p.id](document.body);pending=null}}}};var b=new Blob([m.code],{type:'text/javascript'});var u=URL.createObjectURL(b);import(u).then(function(mod){if(typeof mod.register==='function')mod.register(K)}).catch(function(err){console.error('[kamp sandbox '+id+']',err)}).finally(function(){URL.revokeObjectURL(u)})}else if(m.type==='kamp:panel-mount'&&m.panelId){if(typeof r[m.panelId]==='function'){c[m.panelId]=r[m.panelId](document.body)}else{pending=m.panelId}}else if(m.type==='kamp:panel-unmount'&&m.panelId){var fn=c[m.panelId];if(typeof fn==='function')fn();delete c[m.panelId];if(pending===m.panelId)pending=null}})})();`

const SANDBOX_SRCDOC =
  `<!doctype html>
<html>
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none'; script-src blob: 'unsafe-inline'; connect-src http://127.0.0.1:8000; img-src http://127.0.0.1:8000; style-src 'unsafe-inline'">
<style>html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }</style>
</head>
<body>
<script>${SANDBOX_SHIM}<` +
  `/script>
</body>
</html>`

/**
 * Creates a discovery iframe for an extension: loads the shim, sends kamp:init,
 * and waits for the extension to call panels.register() (which sends kamp:register-panel
 * back to the host). The iframe is removed once registration is complete.
 *
 * Returns a cleanup function that removes the iframe if registration hasn't
 * completed yet (e.g. on component unmount).
 */
function createDiscoveryIframe(
  ext: ExtensionInfo,
  onRegister: (manifest: {
    id: string
    title: string
    defaultSlot: string
    compatibleSlots?: string[]
  }) => void
): () => void {
  const iframe = document.createElement('iframe')
  iframe.sandbox.add('allow-scripts')
  iframe.srcdoc = SANDBOX_SRCDOC
  iframe.style.cssText = 'position:absolute;width:0;height:0;border:none;'
  iframe.title = `Discovery: ${ext.id}`

  let done = false

  function onMessage(event: MessageEvent): void {
    const msg = event.data as Record<string, unknown> | null
    if (!msg || msg.type !== 'kamp:register-panel') return
    if (msg.extensionId !== ext.id) return
    const manifest = msg.manifest as
      | { id: string; title: string; defaultSlot: string; compatibleSlots?: string[] }
      | undefined
    if (!manifest?.id) return
    done = true
    window.removeEventListener('message', onMessage)
    iframe.remove()
    onRegister(manifest)
  }

  window.addEventListener('message', onMessage)

  iframe.addEventListener(
    'load',
    () => {
      iframe.contentWindow?.postMessage(
        { type: 'kamp:init', id: ext.id, serverUrl: window.KampAPI.serverUrl, code: ext.code },
        '*'
      )
    },
    { once: true }
  )

  document.body.appendChild(iframe)

  return () => {
    if (!done) {
      window.removeEventListener('message', onMessage)
      iframe.remove()
    }
  }
}

interface Props {
  extensions: ExtensionInfo[]
}

/**
 * Registers each community (Phase 2) extension's panels with the host.
 *
 * For each extension, spins up a short-lived discovery iframe to run the
 * extension code and collect its panels.register() calls. Once registration
 * is complete the discovery iframe is discarded.
 *
 * When a panel tab is activated, render() creates a fresh sandboxed iframe,
 * sends kamp:init + kamp:panel-mount, and renders the extension content.
 * On deactivation, cleanup() sends kamp:panel-unmount and removes the iframe.
 *
 * State is lost on tab switch — the holding-area/move strategy was abandoned
 * because Chromium reloads sandboxed cross-origin iframes on DOM move.
 */
export function SandboxedExtensionLoader({ extensions }: Props): null {
  // Track cleanup functions for in-flight discovery iframes.
  const cleanupRefs = useRef<Map<string, () => void>>(new Map())

  useEffect(() => {
    for (const ext of extensions) {
      if (cleanupRefs.current.has(ext.id)) continue // already discovering

      const cleanup = createDiscoveryIframe(ext, (manifest) => {
        cleanupRefs.current.delete(ext.id)

        window.KampAPI.panels.register({
          id: manifest.id,
          title: manifest.title,
          defaultSlot: manifest.defaultSlot as SlotId,
          compatibleSlots: manifest.compatibleSlots as SlotId[] | undefined,
          render(container: HTMLElement): () => void {
            const panelId = manifest.id
            const iframe = document.createElement('iframe')
            iframe.sandbox.add('allow-scripts')
            iframe.srcdoc = SANDBOX_SRCDOC
            iframe.style.cssText = 'width:100%;height:100%;border:none;display:block;'
            iframe.title = `Extension: ${ext.id}`

            iframe.addEventListener(
              'load',
              () => {
                iframe.contentWindow?.postMessage(
                  {
                    type: 'kamp:init',
                    id: ext.id,
                    serverUrl: window.KampAPI.serverUrl,
                    code: ext.code
                  },
                  '*'
                )
                iframe.contentWindow?.postMessage({ type: 'kamp:panel-mount', panelId }, '*')
              },
              { once: true }
            )

            container.appendChild(iframe)

            return () => {
              iframe.contentWindow?.postMessage({ type: 'kamp:panel-unmount', panelId }, '*')
              iframe.remove()
            }
          }
        })
      })

      cleanupRefs.current.set(ext.id, cleanup)
    }

    return () => {
      cleanupRefs.current.forEach((fn) => fn())
      cleanupRefs.current.clear()
    }
  }, [extensions])

  return null
}
