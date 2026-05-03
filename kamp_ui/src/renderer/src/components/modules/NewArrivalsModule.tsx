import React, { useEffect, useState } from 'react'
import { getAlbums } from '../../api/client'
import type { Album } from '../../api/client'
import { useStore } from '../../store'
import { ShelfView } from './ShelfView'
import { GridView } from './GridView'
import { ListView } from './ListView'
import type { ModuleProps } from './registry'

export function NewArrivalsModule({ displayStyle }: ModuleProps): React.JSX.Element {
  const count = useStore((s) => s.recentlyAddedCount)
  const days = useStore((s) => s.recentlyAddedDays)
  const serverStatus = useStore((s) => s.serverStatus)
  const [albums, setAlbums] = useState<Album[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Skip until the server is reachable; this effect re-fires when serverStatus
    // transitions to 'connected', so modules populate without a manual reload.
    if (serverStatus !== 'connected') return
    getAlbums('date_added')
      .then((all) => {
        const cutoff = days > 0 ? Date.now() / 1000 - days * 86400 : null
        const recent = all
          .filter((a) => a.added_at !== null && (cutoff === null || a.added_at >= cutoff))
          .slice(0, count > 0 ? count : undefined)
        setAlbums(recent)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [count, days, serverStatus])

  if (loading) {
    return (
      <div className="module-skeleton-row">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="module-skeleton-card" />
        ))}
      </div>
    )
  }

  if (albums.length === 0) {
    return (
      <div className="module-empty">
        {days > 0 ? `No albums added in the last ${days} days.` : 'No albums in your library.'}
      </div>
    )
  }

  if (displayStyle === 'list') return <ListView albums={albums} />
  return displayStyle === 'grid' ? <GridView albums={albums} /> : <ShelfView albums={albums} />
}
