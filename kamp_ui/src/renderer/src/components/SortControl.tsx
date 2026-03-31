import React from 'react'
import { useStore } from '../store'

type SortOrder = 'album_artist' | 'album' | 'date_added' | 'last_played'

const SORT_LABELS: Record<SortOrder, string> = {
  album_artist: 'Artist',
  album: 'Album',
  date_added: 'Date Added',
  last_played: 'Last Played'
}

export function SortControl(): React.JSX.Element {
  const sortOrder = useStore((s) => s.sortOrder)
  const setSortOrder = useStore((s) => s.setSortOrder)

  return (
    <div className="sort-control">
      <span className="sort-label">Sort by</span>
      {(Object.keys(SORT_LABELS) as SortOrder[]).map((key) => (
        <button
          key={key}
          className={`sort-btn${sortOrder === key ? ' active' : ''}`}
          onClick={() => setSortOrder(key)}
        >
          {SORT_LABELS[key]}
        </button>
      ))}
    </div>
  )
}
