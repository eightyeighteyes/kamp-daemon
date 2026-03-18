"""macOS menu bar application for the tune-shifter daemon.

Excluded from coverage: requires AppKit/rumps runtime (macOS only).
Meaningfully unit-testing this module would require mocking all AppKit
and rumps internals, providing little value over manual testing on macOS.

Must only be imported on macOS — raises ImportError otherwise.
"""

from __future__ import annotations

import platform
import signal
import subprocess
import threading

if platform.system() != "Darwin":
    raise ImportError("tune_shifter.menu_bar is only available on macOS")

import rumps  # noqa: E402 — guarded above

from .daemon_core import DaemonCore, _PID_PATH

_ABOUT_URL = "https://github.com/eightyeighteyes/tune-shifter"
_SYMBOL_NAME = "music.note.square.stack"


class MenuBarApp(rumps.App):
    """rumps-based menu bar application for the tune-shifter daemon.

    Holds a DaemonCore reference and exposes pipeline start/stop and
    Bandcamp sync controls in the macOS menu bar.
    """

    def __init__(self, core: DaemonCore) -> None:
        # Set accessory policy BEFORE the AppKit run loop starts.  A launchd-launched
        # process has no GUI bundle, so this call grants it a Window Server connection
        # and allows the status-bar item to appear.
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )

        # quit_button=None — we supply our own Quit item so we can call
        # DaemonCore.shutdown() before exiting the AppKit run loop.
        super().__init__("tune-shifter", icon=None, quit_button=None)

        self._core = core
        self._sync_in_progress = False
        self._pulse_active = False

        # Replace the text title with an SF Symbol icon.
        self._set_sf_symbol_icon()

        # DaemonCore installs SIGTERM/SIGINT handlers that call shutdown() and
        # unblock core.wait(), but in the menu bar path there is no core.wait() call —
        # the AppKit run loop holds the main thread.  Override those signals here so
        # that SIGTERM also exits the run loop via _on_quit.
        def _quit_signal(signum: int, frame: object) -> None:
            self._on_quit(None)

        signal.signal(signal.SIGINT, _quit_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _quit_signal)

        # Build menu items.
        self._toggle_item = rumps.MenuItem("Stop", callback=self._on_toggle)
        self._sync_item = rumps.MenuItem("Bandcamp Sync", callback=self._on_sync)
        self._status_item = rumps.MenuItem("Status: Idle")

        self.menu = [
            self._toggle_item,
            None,  # separator
            self._sync_item,
            self._status_item,
            None,  # separator
            rumps.MenuItem("About Tune-Shifter", callback=self._on_about),
            rumps.MenuItem("Quit", callback=self._on_quit),
        ]

        # Apply initial enabled state for bandcamp-dependent items.
        self._refresh_bandcamp_items()

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _on_toggle(self, sender: rumps.MenuItem) -> None:
        if self._core.state == "running":
            self._core.stop()
            self._toggle_item.title = "Play"
        else:
            self._core.resume()
            self._toggle_item.title = "Stop"

    def _on_sync(self, sender: rumps.MenuItem) -> None:
        if self._sync_in_progress:
            return
        syncer = self._core.syncer
        if syncer is None:
            return
        self._sync_in_progress = True
        self._refresh_bandcamp_items()

        def _run() -> None:
            try:
                syncer.sync_once()
            finally:
                self._sync_in_progress = False

        threading.Thread(target=_run, daemon=True).start()

    def _on_about(self, sender: rumps.MenuItem) -> None:
        subprocess.run(["open", _ABOUT_URL], check=False)

    def _on_quit(self, sender: object) -> None:
        self._core.shutdown()
        _PID_PATH.unlink(missing_ok=True)
        rumps.quit_application()

    # ------------------------------------------------------------------
    # Timer: refresh status every 5 seconds
    # ------------------------------------------------------------------

    @rumps.timer(5)
    def _refresh(self, sender: object) -> None:
        # Keep toggle label in sync with the actual pipeline state (e.g. if
        # the pipeline was paused/resumed via SIGUSR1/SIGUSR2 externally).
        if self._core.state == "paused":
            self._toggle_item.title = "Play"
        else:
            self._toggle_item.title = "Stop"

        if self._sync_in_progress:
            self._status_item.title = "Status: Syncing\u2026"
            self._set_pulse(True)
        else:
            self._status_item.title = "Status: Idle"
            self._set_pulse(False)

        self._refresh_bandcamp_items()

    # ------------------------------------------------------------------
    # AppKit helpers
    # ------------------------------------------------------------------

    def _set_sf_symbol_icon(self) -> None:
        """Replace the rumps text title with an SF Symbol image."""
        try:
            from AppKit import NSImage

            img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                _SYMBOL_NAME, "tune-shifter"
            )
            if img:
                img.setTemplate_(True)  # adapts to light/dark menu bar
                self._nsapp.statusitem.button().setImage_(img)
                self.title = ""  # hide text title once icon is set
        except Exception:
            pass  # fall back to the "tune-shifter" text title on failure

    def _set_pulse(self, active: bool) -> None:
        """Add or remove NSSymbolPulseEffect on the status-bar icon.

        NSSymbolPulseEffect requires macOS 14+; the try/except silently degrades
        on older systems where the symbol just stays static during sync.
        """
        if active == self._pulse_active:
            return
        self._pulse_active = active
        try:
            from AppKit import (
                NSSymbolEffectOptions,
                NSSymbolEffectOptionsRepeatBehavior,
                NSSymbolPulseEffect,
            )

            btn = self._nsapp.statusitem.button()
            if active:
                btn.addSymbolEffect_options_(
                    NSSymbolPulseEffect.effect().effectWithByLayer(),
                    NSSymbolEffectOptions.optionsWithRepeatBehavior_(
                        NSSymbolEffectOptionsRepeatBehavior.behaviorPeriodicWithDelay_(
                            1.0
                        )
                    ),
                )
            else:
                btn.removeAllSymbolEffects()
        except Exception:
            pass  # NSSymbolPulseEffect requires macOS 14+

    def _refresh_bandcamp_items(self) -> None:
        """Disable Bandcamp Sync and Sync Status when config or conditions prevent use."""
        has_bandcamp = self._core._config.bandcamp is not None
        sync_available = has_bandcamp and not self._sync_in_progress

        if sync_available:
            self._sync_item.set_callback(self._on_sync)
        else:
            self._sync_item.set_callback(None)

        # setEnabled_ controls the visual gray-out at the AppKit level;
        # set_callback(None) alone only removes the click handler.
        try:
            self._sync_item._menuitem.setEnabled_(sync_available)
            self._status_item._menuitem.setEnabled_(has_bandcamp)
        except Exception:
            pass
