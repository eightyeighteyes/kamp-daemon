import React, { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useMenuBounds } from '../hooks/useMenuBounds'

interface Props {
  x: number
  y: number
  onClose: () => void
  children: React.ReactNode
}

export function ContextMenu({ x, y, onClose, children }: Props): React.JSX.Element {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent): void => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  useMenuBounds(ref, true)

  return createPortal(
    <div
      ref={ref}
      className="track-context-menu"
      style={{ top: y, left: x }}
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>,
    document.body
  )
}
