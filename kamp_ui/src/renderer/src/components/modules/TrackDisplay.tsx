import React from 'react'
import { useStore } from '../../store'
import { useStereoRack } from './StereoRackContext'

function formatTime(seconds: number): string {
  const s = Math.floor(seconds)
  const mm = Math.floor(s / 60)
    .toString()
    .padStart(2, '0')
  const ss = (s % 60).toString().padStart(2, '0')
  return `${mm}:${ss}`
}

type TrackLeftProps = { artist: string; title: string }

function TrackLeft({ artist, title }: TrackLeftProps): React.JSX.Element {
  return (
    <span className="track-left">
      {artist ? (
        <>
          <span className="track-artist">{artist}</span>
          <span className="track-sep"> — </span>
          <span className="track-title">{title}</span>
        </>
      ) : (
        <span className="track-title">{title}</span>
      )}
    </span>
  )
}

type TrackRightProps = { position: number; duration: number; year: string; format: string }

function TrackRight({ position, duration, year, format }: TrackRightProps): React.JSX.Element {
  return (
    <span className="track-right">
      <span className="track-time">{formatTime(position)}</span>
      <span className="track-timesep">/</span>
      <span className="track-time">{formatTime(duration)}</span>
      {year && <span className="track-year">{year}</span>}
      {format && <span className="track-format">{format}</span>}
    </span>
  )
}

export function TrackDisplay(): React.JSX.Element {
  const { isPlaying, trackMeta } = useStereoRack()
  const position = useStore((s) => s.player.position)

  return (
    <div className={`track-display${isPlaying ? '' : ' is-idle'}`}>
      {trackMeta && (
        <>
          <TrackLeft artist={trackMeta.artist} title={trackMeta.title} />
          <TrackRight
            position={position}
            duration={trackMeta.duration}
            year={trackMeta.year}
            format={trackMeta.format}
          />
        </>
      )}
    </div>
  )
}
