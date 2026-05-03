import React, { useRef } from 'react'
import type { Album } from '../../api/client'
import { AlbumCard } from '../AlbumCard'

interface ShelfViewProps {
  albums: Album[]
}

const SCROLL_PX = 500

export function ShelfView({ albums }: ShelfViewProps): React.JSX.Element {
  const scrollRef = useRef<HTMLDivElement>(null)

  const scroll = (dir: 'left' | 'right'): void => {
    scrollRef.current?.scrollBy({
      left: dir === 'right' ? SCROLL_PX : -SCROLL_PX,
      behavior: 'smooth'
    })
  }

  const onKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      scroll('right')
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      scroll('left')
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
      <div
        className="module-shelf"
        ref={scrollRef}
        onKeyDown={onKeyDown}
        tabIndex={0}
        role="region"
        aria-label="Album shelf"
      >
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
