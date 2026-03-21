Welcome to kamp-daemon!

To get started, run:
   kamp-daemon

On first run, you'll be asked for your staging directory, library directory,
and contact email (used in the MusicBrainz User-Agent). Press Enter at each
prompt to accept the shown default. The config is saved automatically and the
daemon starts right away.

Then install the service so it starts at login:
  kamp-daemon install-service

Now move a zip or folder into your staging folder and kamp-daemon will take care of the rest!

To manage the service:
  kamp-daemon stop     # pause
  kamp-daemon play     # resume
  kamp-daemon status   # check if it's running

To sync your collection from Bandcamp, run:
  kamp-daemon sync

On first sync, kamp-daemon will capture the state of your Bandcamp account. 
If you want to download your whole Bandcamp collection in one go, you need to run:
  kamp-daemon sync --download-all
