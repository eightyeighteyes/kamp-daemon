## Future Improvements

### Homebrew Installable

*I want to be able to install tune-shifter through homebrew*

### Bandcamp Album Art

*If an archive already has high quality album art, I want to use that (as long as it's not too big)*

The ideal album art dimensions are at least 1000x1000 and the ideal album art size is around 1MB.

If the art that is distributed with the archive is not larger than 2MB, use that.

If the art is larger than 2MB, scale it down to an acceptable size.

If the art is smaller than 1MB and not 1000x1000, fall back to our existing image search.

### Configurable Album Art Search

*I want to be able to configure where album art is retrieved from*

The default setting should be "default" and retrieve the art from musicbrainz.

*I want to be able to retrieve album art from bandcamp*

The configuration setting for this should be `"bandcamp"`

*I want to be able to retrieve album art from iTunes / Apple Music*

The configuration setting for this should be `"apple"`.

*I want to be able to retrieve album art from Spotify*

The configuration setting for this should be `"spotify"`.

*I want to be able to retrieve album art from Qobuz*

The configuration settings for this should be `"qobuz"`

### Improved Tag Sourcing

*I want ALL the tags from MusicBrainz*

The following is a list of tags that are currently not populated:
  - AcoustID
  - Album Artist Sort Order
  - Artist Sort Order
  - Artists
  - ASIN
  - Barcode
  - Catalog Number
  - Disc Number
  - MusicBrainz Artist ID
  - MusicBrainz Recording ID
  - MusicBrainz Release Artist ID
  - MusicBrainz Release Group ID
  - MusicBrainz Release ID
  - Original Release Date
  - Original Year
  - Producer
  - Record Label
  - Release Country
  - Release Status
  - Release Type
  - Script
  - Total Discs
  - Total Tracks

### Better Cleanup

Fully delete folders from staging after moving files to library.

### GUI / menu bar app for sync status

### Allow a user to verify tags before they're written

### Cross-platform service installation (Linux systemd, Windows Task Scheduler)





