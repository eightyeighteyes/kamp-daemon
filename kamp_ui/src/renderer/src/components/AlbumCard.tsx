import React, { useState } from 'react'
import { useStore } from '../store'
import { artUrl } from '../api/client'
import type { Album } from '../api/client'
import { AlbumContextMenu } from './AlbumContextMenu'

type MenuPos = { x: number; y: number }

export function AlbumCard({ album }: { album: Album }): React.JSX.Element {
  const selectAlbum = useStore((s) => s.selectAlbum)
  const setActiveView = useStore((s) => s.setActiveView)
  const activeView = useStore((s) => s.activeView)
  const currentTrack = useStore((s) => s.player.current_track)
  const playing = useStore((s) => s.player.playing)
  const [artLoaded, setArtLoaded] = useState(false)
  const [menu, setMenu] = useState<MenuPos | null>(null)

  const isActive = album.missing_album
    ? currentTrack?.file_path === album.file_path
    : currentTrack?.album === album.album && currentTrack?.album_artist === album.album_artist

  const handleSelect = (): void => {
    if (activeView !== 'library') void setActiveView('library')
    void selectAlbum(album)
  }

  return (
    <div
      className={`album-card${isActive ? ' playing' : ''}`}
      tabIndex={0}
      draggable
      onClick={handleSelect}
      onKeyDown={(e) => e.key === 'Enter' && handleSelect()}
      onContextMenu={(e) => {
        e.preventDefault()
        setMenu({ x: e.clientX, y: e.clientY })
      }}
      onDragStart={(e) => {
        e.dataTransfer.setData(
          'text/kamp-album',
          JSON.stringify({
            album_artist: album.album_artist,
            album: album.album,
            file_path: album.file_path
          })
        )
        e.dataTransfer.effectAllowed = 'copy'
      }}
    >
      <div className={`album-art${artLoaded ? ' has-art' : ''}`}>
        {album.has_art && (
          <img
            className="album-art-img"
            src={artUrl(album.album_artist, album.album, album.file_path, album.art_version)}
            alt=""
            onLoad={() => setArtLoaded(true)}
            onError={() => setArtLoaded(false)}
          />
        )}
        {playing && isActive && <div className="now-playing-badge">▶</div>}
      </div>
      <div className="album-info">
        {album.missing_album ? (
          <div className="album-title">
            <em>{album.album}</em>
          </div>
        ) : (
          <div className="album-title">{album.album}</div>
        )}
        <div className="album-artist">{album.album_artist}</div>
        <div className="album-year">{album.year}</div>
      </div>

      {menu && (
        <AlbumContextMenu x={menu.x} y={menu.y} album={album} onClose={() => setMenu(null)} />
      )}
    </div>
  )
}
