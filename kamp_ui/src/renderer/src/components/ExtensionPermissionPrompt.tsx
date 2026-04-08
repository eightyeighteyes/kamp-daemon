/**
 * ExtensionPermissionPrompt — shown once per community (Phase 2) extension
 * before it is loaded. The extension only runs after the user explicitly
 * approves its declared permissions.
 *
 * App.tsx maintains a queue of pending extensions; this component displays
 * the first one. Approve/deny callbacks advance the queue.
 */

import React from 'react'
import type { ExtensionInfo } from '../../../shared/kampAPI'

// Map raw permission ids to human-readable descriptions.
const PERMISSION_LABELS: Record<string, string> = {
  'library.read': 'Read your music library (artists, albums, tracks)',
  'player.read': 'Read playback state (current track, position, volume)',
  'player.control': 'Control playback (play, pause, skip, seek)',
  'network.fetch': 'Make requests to external servers on the internet',
  settings: 'Read and write its own settings'
}

function permissionLabel(p: string): string {
  return PERMISSION_LABELS[p] ?? p
}

interface Props {
  extension: ExtensionInfo
  onApprove: () => void
  onDeny: () => void
}

export function ExtensionPermissionPrompt({
  extension,
  onApprove,
  onDeny
}: Props): React.JSX.Element {
  return (
    <div className="prefs-overlay ext-perm-overlay">
      <div
        className="prefs-dialog ext-perm-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Extension permissions"
      >
        <div className="prefs-header">
          <span className="prefs-title">EXTENSION PERMISSIONS</span>
        </div>

        <div className="ext-perm-body">
          <p className="ext-perm-intro">
            <strong>{extension.name}</strong>{' '}
            <span className="ext-perm-version">{extension.version}</span> is a community extension
            that requests the following permissions:
          </p>

          {extension.permissions.length > 0 ? (
            <ul className="ext-perm-list">
              {extension.permissions.map((p) => (
                <li key={p} className="ext-perm-item">
                  <span className="ext-perm-bullet">•</span>
                  {permissionLabel(p)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="ext-perm-none">This extension requests no special permissions.</p>
          )}

          <p className="ext-perm-warning">
            Community extensions run in a sandboxed iframe and cannot access your filesystem or
            system APIs. Only approve extensions you trust.
          </p>
        </div>

        <div className="ext-perm-actions">
          <button className="ext-perm-deny-btn" onClick={onDeny}>
            Don&apos;t Allow
          </button>
          <button className="ext-perm-approve-btn" onClick={onApprove}>
            Allow Extension
          </button>
        </div>
      </div>
    </div>
  )
}
