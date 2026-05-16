import React, { useRef, useState } from 'react'

type Props = {
  value: string
  editMode: boolean
  disabled?: boolean
  className?: string
  onSave: (value: string) => Promise<void>
  // Render the read-only view (a span, button, h1, etc).
  renderStatic: (value: string) => React.JSX.Element
}

export function EditableAlbumField({
  value,
  editMode,
  disabled = false,
  className = '',
  onSave,
  renderStatic
}: Props): React.JSX.Element {
  const [draft, setDraft] = useState(value)
  const [prevValue, setPrevValue] = useState(value)
  const [saving, setSaving] = useState(false)
  const [shake, setShake] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  // Set to true by the Escape handler before blur() so commit() knows to skip saving.
  // A ref (not state) is required because blur fires synchronously before React
  // flushes the setDraft(value) state update.
  const cancelRef = useRef(false)

  // Sync external value changes (after a save refreshes the album) back into local state.
  if (value !== prevValue) {
    setPrevValue(value)
    setDraft(value)
  }

  if (!editMode) return renderStatic(value)

  const commit = async (): Promise<void> => {
    if (cancelRef.current) {
      cancelRef.current = false
      return
    }
    const trimmed = draft.trim()
    if (!trimmed) {
      // Empty string is invalid — revert and shake.
      setDraft(value)
      setShake(true)
      setTimeout(() => setShake(false), 400)
      return
    }
    if (trimmed === value || saving) return
    setSaving(true)
    try {
      await onSave(trimmed)
    } finally {
      setSaving(false)
    }
  }

  return (
    <input
      ref={inputRef}
      className={`editable-album-field${saving ? ' saving' : ''}${shake ? ' shake' : ''} ${className}`.trim()}
      value={draft}
      disabled={disabled || saving}
      aria-label={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => void commit()}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault()
          inputRef.current?.blur()
        } else if (e.key === 'Escape') {
          e.stopPropagation()
          cancelRef.current = true
          setDraft(value)
          inputRef.current?.blur()
        }
      }}
      onClick={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
    />
  )
}
