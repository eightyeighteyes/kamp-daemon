import React from 'react'
import { useStore } from '../store'
import { getTracksForAlbum } from '../api/client'
import type { Album } from '../api/client'
import { ContextMenu } from './ContextMenu'
import { revealInFinderLabel } from '../hooks/platformLabel'

interface Props {
  x: number
  y: number
  album: Album
  onClose: () => void
}

export function AlbumContextMenu({ x, y, album, onClose }: Props): React.JSX.Element {
  const playAlbumNext = useStore((s) => s.playAlbumNext)
  const addAlbumToQueue = useStore((s) => s.addAlbumToQueue)

  return (
    <ContextMenu x={x} y={y} onClose={onClose}>
      <button
        className="track-context-menu-item"
        onClick={() => {
          void playAlbumNext(album.album_artist, album.album, album.file_path)
          onClose()
        }}
      >
        ▶ Play Next
      </button>
      <button
        className="track-context-menu-item"
        onClick={() => {
          void addAlbumToQueue(album.album_artist, album.album, album.file_path)
          onClose()
        }}
      >
        + Add to Queue
      </button>
      <button
        className="track-context-menu-item"
        onClick={async () => {
          let filePath = album.file_path
          if (!filePath) {
            const tracks = await getTracksForAlbum(album.album_artist, album.album)
            filePath = tracks[0]?.file_path ?? ''
          }
          if (filePath) window.api.showItemInFolder(filePath)
          onClose()
        }}
      >
        {revealInFinderLabel()}
      </button>
    </ContextMenu>
  )
}
