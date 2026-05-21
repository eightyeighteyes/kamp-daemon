import React, { useState } from 'react'
import { useStore } from '../store'
import { UpdateNotesModal } from './UpdateNotesModal'

export function UpdateBanner(): React.JSX.Element | null {
  const updateAvailable = useStore((s) => s.updateAvailable)
  const setUpdateAvailable = useStore((s) => s.setUpdateAvailable)
  const [notesOpen, setNotesOpen] = useState(false)

  if (!updateAvailable) return null

  const dismiss = (): void => {
    void window.api.dismissUpdate(updateAvailable.version)
    setUpdateAvailable(null)
  }

  return (
    <>
      <div className="update-banner">
        <span className="update-banner-text">Kamp {updateAvailable.version} is out.</span>
        <button className="update-banner-link" onClick={() => setNotesOpen(true)}>
          What&rsquo;s new
        </button>
        <button className="update-banner-link" onClick={dismiss}>
          Dismiss
        </button>
      </div>
      {notesOpen && (
        <UpdateNotesModal
          version={updateAvailable.version}
          notes={updateAvailable.notes}
          onClose={() => setNotesOpen(false)}
          onDismiss={dismiss}
        />
      )}
    </>
  )
}
