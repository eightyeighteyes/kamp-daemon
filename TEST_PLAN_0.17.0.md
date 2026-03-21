# Test Plan: 0.17.0 Error Notifications

## Pre-merge (dev venv)

1. `poetry run pytest tests/test_notifications.py -v --no-cov` — 11 tests verify the full IPC chain
2. `kamp-daemon test-notify --type extraction` (and each other type) — should print `Notification logic verified: <subtitle>` with no crash

That's all verifiable from the venv. OS notification display requires the Homebrew binary (needs the embedded `CFBundleIdentifier`).

---

## Post-merge / after Homebrew upgrade

3. `brew upgrade kamp-daemon` — picks up the launcher with the embedded plist
4. `kamp-daemon test-notify --type extraction` from the Homebrew binary — should print `Notification logic verified:` **and** show a macOS banner. On first run, macOS will prompt "kamp-daemon wants to send notifications" — approve it.
5. Check **System Settings → Notifications** — "kamp-daemon" should now appear as an entry
6. Repeat step 4 for `--type tagging`, `artwork`, `move`, `download`

## End-to-end with the daemon

7. `kamp-daemon daemon` (or let launchd start it) — menu bar icon appears
8. Drop a ZIP with no audio files into staging — should quarantine and fire an "Extraction failed" notification
9. _(Optional)_ Rename a staging directory to include `__test_tagging_error` and drop it in — fires "Tagging failed" without needing a real bad file

---

Steps 1–2 are verifiable today. Steps 3–9 gate on the release.
