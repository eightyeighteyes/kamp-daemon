Welcome to tune-shifter!

To get started, run:
   tune-shifter

On first run, you'll be asked for your staging directory, library directory,
and contact email (used in the MusicBrainz User-Agent). Press Enter at each
prompt to accept the shown default. The config is saved automatically and the
daemon starts right away.

Then install the service so it starts at login:
  tune-shifter install-service

Now move a zip or folder into your staging folder and tune-shifter will take care of the rest!

To manage the service:
  tune-shifter stop     # pause
  tune-shifter play     # resume
  tune-shifter status   # check if it's running

To sync your collection from Bandcamp, run:
  tune-shifter sync

If most of your Bandcamp collection is already in your local library, run this first to avoid redownloading everything:
  tune-shifter sync --mark-synced
