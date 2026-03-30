import { forwardRef } from 'react'
import { useStore } from '../store'

export const SearchBar = forwardRef<HTMLInputElement>(function SearchBar(_, ref) {
  const query = useStore((s) => s.searchQuery)
  const setSearchQuery = useStore((s) => s.setSearchQuery)

  return (
    <div className="search-bar">
      <span className="search-icon">⌕</span>
      <input
        ref={ref}
        className="search-input"
        type="text"
        placeholder="Search…"
        value={query}
        onChange={(e) => void setSearchQuery(e.target.value)}
        aria-label="Search library"
      />
      {query && (
        <button
          className="search-clear"
          onClick={() => void setSearchQuery('')}
          aria-label="Clear search"
        >
          ✕
        </button>
      )}
    </div>
  )
})
