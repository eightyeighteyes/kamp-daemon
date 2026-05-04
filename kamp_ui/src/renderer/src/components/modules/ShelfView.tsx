import React, { useEffect, useRef } from 'react'
import type { Album } from '../../api/client'
import { AlbumCard } from '../AlbumCard'
import { useStore } from '../../store'

interface ShelfViewProps {
  albums: Album[]
  scrollToPlaying?: boolean
}

const SCROLL_PX = 500

export function ShelfView({ albums, scrollToPlaying = false }: ShelfViewProps): React.JSX.Element {
  const scrollRef = useRef<HTMLDivElement>(null)
  const hasMounted = useRef(false)
  const currentTrack = useStore((s) => s.player.current_track)

  const scroll = (dir: 'left' | 'right'): void => {
    scrollRef.current?.scrollBy({
      left: dir === 'right' ? SCROLL_PX : -SCROLL_PX,
      behavior: 'smooth'
    })
  }

  useEffect(() => {
    const shelf = scrollRef.current
    if (!shelf || !scrollToPlaying) return
    const behavior: ScrollBehavior = hasMounted.current ? 'smooth' : 'instant'
    hasMounted.current = true

    if (!currentTrack) {
      shelf.scrollTo({ left: 0, behavior })
      return
    }

    const idx = albums.findIndex((a) =>
      a.missing_album
        ? a.file_path === currentTrack.file_path
        : a.album === currentTrack.album && a.album_artist === currentTrack.album_artist
    )

    if (idx === -1) {
      shelf.scrollTo({ left: 0, behavior })
      return
    }

    // Matches the CSS layout: padding-left(12) + first-child margin(5) + idx*(card(180)+gap(15)) - scroll-padding(5)
    shelf.scrollTo({ left: 12 + idx * 195, behavior })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTrack?.album_artist, currentTrack?.album, currentTrack?.file_path, albums, scrollToPlaying])

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
