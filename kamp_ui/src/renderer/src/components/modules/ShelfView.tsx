import React, { useRef } from 'react'
import type { Album } from '../../api/client'
import { AlbumCard } from '../AlbumCard'

interface ShelfViewProps {
  albums: Album[]
}

const SCROLL_PX = 500
const EASE = 0.15

export function ShelfView({ albums }: ShelfViewProps): React.JSX.Element {
  const scrollRef = useRef<HTMLDivElement>(null)
  const targetRef = useRef(0)
  const animatingRef = useRef(false)

  const animate = (el: HTMLDivElement): void => {
    const maxScroll = el.scrollWidth - el.clientWidth
    const target = Math.max(0, Math.min(targetRef.current, maxScroll))
    const diff = target - el.scrollLeft
    if (Math.abs(diff) < 0.5) {
      el.scrollLeft = target
      animatingRef.current = false
      return
    }
    el.scrollLeft += diff * EASE
    requestAnimationFrame(() => animate(el))
  }

  const scroll = (dir: 'left' | 'right'): void => {
    const el = scrollRef.current
    if (!el) return
    if (!animatingRef.current) targetRef.current = el.scrollLeft
    targetRef.current += dir === 'right' ? SCROLL_PX : -SCROLL_PX
    if (!animatingRef.current) {
      animatingRef.current = true
      requestAnimationFrame(() => animate(el))
    }
  }

  return (
    <div className="module-shelf-wrapper">
      <button
        className="module-shelf-arrow module-shelf-arrow--left"
        onClick={() => scroll('left')}
        aria-label="Scroll left"
        tabIndex={-1}
      >
        ‹
      </button>
      <div className="module-shelf" ref={scrollRef} role="region" aria-label="Album shelf">
        {albums.map((album) => (
          <AlbumCard
            key={album.missing_album ? album.file_path : `${album.album_artist}\0${album.album}`}
            album={album}
          />
        ))}
      </div>
      <button
        className="module-shelf-arrow module-shelf-arrow--right"
        onClick={() => scroll('right')}
        aria-label="Scroll right"
        tabIndex={-1}
      >
        ›
      </button>
    </div>
  )
}
