#!/usr/bin/env python3
"""KAMP-373 spike: do transport controls work with Bandcamp streaming URLs?

Tests every transport action against live streaming URLs via the mpv IPC socket:
  - play (loadfile with URL)
  - pause / resume
  - stop (seek to 0 + pause)
  - next (loadfile replace with next track URL)
  - prev (loadfile replace with prev track URL)
  - seek (absolute position seek on a streaming URL — needs CDN range support)

Runs standalone: spawns its own mpv process, no kamp daemon required.

Usage:
    poetry run python scripts/spike_kamp373_transport.py
    poetry run python scripts/spike_kamp373_transport.py --session-file /path/to/session.json
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    sys.exit("Install requests: poetry add requests")

ALBUM_URL = "https://theemarloes.bandcamp.com/album/di-hotel-malibu"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# How long to wait for mpv to start playing a stream before declaring failure
_PLAY_SETTLE = 4.0
# Time to play between transport actions in interactive tests
_PLAY_GAP = 2.0


# ---------------------------------------------------------------------------
# IPC helpers (mirrors MpvPlaybackEngine but minimal)
# ---------------------------------------------------------------------------


class _Mpv:
    """Minimal mpv IPC wrapper for spike testing."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="kamp-spike-373-")
        self._sock_path = os.path.join(self._tmpdir, "mpv.sock")
        self._sock: socket.socket | None = None
        self._proc: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        self._proc = subprocess.Popen(
            ["mpv", "--no-video", "--idle=yes", "--really-quiet",
             f"--input-ipc-server={self._sock_path}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if Path(self._sock_path).exists():
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("mpv IPC socket did not appear within 5s")
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # type: ignore[attr-defined]
        self._sock.connect(self._sock_path)
        self._sock.settimeout(3.0)

    def _send(self, *args: Any) -> dict[str, Any]:
        assert self._sock
        msg = json.dumps({"command": list(args)}) + "\n"
        self._sock.sendall(msg.encode())
        # Drain until we get a response (not just an event)
        buf = b""
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                for line in buf.split(b"\n"):
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                        if "error" in obj:
                            return obj  # type: ignore[return-value]
                    except json.JSONDecodeError:
                        pass
            except socket.timeout:
                break
        return {}

    def load(self, url: str) -> bool:
        resp = self._send("loadfile", url, "replace")
        return resp.get("error") == "success"

    def pause(self) -> bool:
        resp = self._send("set_property", "pause", True)
        return resp.get("error") == "success"

    def resume(self) -> bool:
        resp = self._send("set_property", "pause", False)
        return resp.get("error") == "success"

    def stop(self) -> bool:
        # Mirror MpvPlaybackEngine.stop(): pause + seek to 0
        r1 = self._send("set_property", "pause", True)
        r2 = self._send("seek", 0, "absolute")
        return r1.get("error") == "success" and r2.get("error") == "success"

    def seek(self, position: float) -> bool:
        resp = self._send("seek", position, "absolute")
        return resp.get("error") == "success"

    def get_property(self, name: str) -> Any:
        resp = self._send("get_property", name)
        if resp.get("error") == "success":
            return resp.get("data")
        return None

    def wait_for_play(self, timeout: float = _PLAY_SETTLE) -> bool:
        """Poll time-pos until it's > 0 (mpv is actually playing)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pos = self.get_property("time-pos")
            if pos is not None and float(pos) > 0.1:
                return True
            time.sleep(0.2)
        return False

    def shutdown(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._proc:
            self._proc.terminate()
            self._proc.wait(timeout=5)
            self._proc = None
        shutil.rmtree(self._tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Fetch streaming URLs (reuses KAMP-372 approach)
# ---------------------------------------------------------------------------


def _fetch_tracks(session_file: Path) -> list[dict[str, Any]]:
    state = json.loads(session_file.read_text())
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    for cookie in state.get("cookies", []):
        s.cookies.set(cookie["name"], cookie["value"],
                      domain=cookie.get("domain", ".bandcamp.com"),
                      path=cookie.get("path", "/"))

    resp = s.get(ALBUM_URL, timeout=30)
    resp.raise_for_status()

    import html as html_lib
    blob: dict[str, Any] | None = None
    # Modern Bandcamp: data-tralbum attribute on the page
    m2 = re.search(r'data-tralbum="([^"]+)"', resp.text)
    if m2:
        blob = json.loads(html_lib.unescape(m2.group(1)))
    else:
        # Older format: var TralbumData = {...};
        m = re.search(r"var TralbumData\s*=\s*(\{.*?\});\s*(?:var |</script>)", resp.text, re.DOTALL)
        if m:
            blob = json.loads(m.group(1))
    if not blob:
        sys.exit("TralbumData not found in album page — is the session valid?")

    tracks = []
    for t in blob.get("trackinfo", []):
        file_data = t.get("file") or {}
        if file_data:
            # Prefer mp3-v0 (higher quality VBR) for purchased albums; fall back to mp3-128
            url = file_data.get("mp3-v0") or file_data.get("mp3-128")
            tracks.append({
                "num": t.get("track_num", 0),
                "title": t.get("title", "?"),
                "duration": t.get("duration", 0),
                "url": url,
                "formats": list(file_data.keys()),
            })
    return tracks


# ---------------------------------------------------------------------------
# Transport tests
# ---------------------------------------------------------------------------


def _check(label: str, ok: bool) -> bool:
    status = "✓" if ok else "✗"
    print(f"  {status} {label}")
    return ok


def test_play(mpv: _Mpv, track: dict[str, Any]) -> bool:
    print(f"\n[play] Loading track {track['num']}: {track['title']!r}")
    ok = mpv.load(track["url"])
    _check("loadfile returned success", ok)
    playing = mpv.wait_for_play()
    _check(f"time-pos > 0 after {_PLAY_SETTLE}s", playing)
    if playing:
        pos = mpv.get_property("time-pos")
        dur = mpv.get_property("duration")
        paused = mpv.get_property("pause")
        print(f"  time-pos={pos:.2f}s  duration={dur:.1f}s  paused={paused}")
    return ok and playing


def test_pause_resume(mpv: _Mpv) -> bool:
    print(f"\n[pause] Pausing playback")
    ok_pause = mpv.pause()
    _check("pause command success", ok_pause)
    time.sleep(0.5)
    paused = mpv.get_property("pause")
    _check(f"mpv reports paused=True (got {paused})", paused is True)

    time.sleep(_PLAY_GAP)

    print(f"[resume] Resuming playback")
    ok_resume = mpv.resume()
    _check("resume command success", ok_resume)
    time.sleep(0.5)
    paused2 = mpv.get_property("pause")
    _check(f"mpv reports paused=False (got {paused2})", paused2 is False)
    return ok_pause and ok_resume and paused is True and paused2 is False


def test_seek(mpv: _Mpv, seek_to: float = 30.0) -> bool:
    """Test seeking to an arbitrary position on a streaming URL.

    This proves the CDN supports HTTP range requests (required for non-sequential seek).
    If bcbits.com doesn't support ranges, mpv will fail or report an error.
    """
    print(f"\n[seek] Seeking to {seek_to}s on streaming URL")
    ok = mpv.seek(seek_to)
    _check("seek command success", ok)
    time.sleep(1.5)  # give mpv time to re-buffer from the seek point
    pos = mpv.get_property("time-pos")
    _check(f"time-pos after seek: {pos:.2f}s (expected ~{seek_to}s)",
           pos is not None and abs(float(pos) - seek_to) < 5.0)
    playing = mpv.wait_for_play(timeout=3.0)
    _check("still playing after seek", playing)
    return ok and pos is not None and abs(float(pos) - seek_to) < 5.0


def test_next(mpv: _Mpv, next_track: dict[str, Any]) -> bool:
    print(f"\n[next] Loading next track {next_track['num']}: {next_track['title']!r}")
    ok = mpv.load(next_track["url"])
    _check("loadfile next returned success", ok)
    playing = mpv.wait_for_play()
    _check(f"next track playing after {_PLAY_SETTLE}s", playing)
    if playing:
        pos = mpv.get_property("time-pos")
        dur = mpv.get_property("duration")
        print(f"  time-pos={pos:.2f}s  duration={dur:.1f}s")
    return ok and playing


def test_prev(mpv: _Mpv, prev_track: dict[str, Any]) -> bool:
    print(f"\n[prev] Loading prev track {prev_track['num']}: {prev_track['title']!r}")
    ok = mpv.load(prev_track["url"])
    _check("loadfile prev returned success", ok)
    playing = mpv.wait_for_play()
    _check(f"prev track playing after {_PLAY_SETTLE}s", playing)
    return ok and playing


def test_stop(mpv: _Mpv) -> bool:
    print(f"\n[stop] Stopping playback")
    ok = mpv.stop()
    _check("stop command success", ok)
    time.sleep(0.5)
    paused = mpv.get_property("pause")
    pos = mpv.get_property("time-pos")
    _check(f"paused after stop (got {paused})", paused is True)
    _check(f"position near 0 after stop (got {pos})",
           pos is not None and float(pos) < 2.0)
    return ok and paused is True


def test_resume_after_stop(mpv: _Mpv) -> bool:
    print(f"\n[resume-after-stop] Resuming from stopped state")
    ok = mpv.resume()
    _check("resume success", ok)
    playing = mpv.wait_for_play(timeout=3.0)
    _check("playing after resume from stopped state", playing)
    return ok and playing


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="KAMP-373 spike: transport controls + streaming")
    parser.add_argument("--session-file", type=Path, default=None)
    args = parser.parse_args()

    if args.session_file:
        sf = args.session_file
    else:
        try:
            from kamp_daemon.config import _state_dir
            sf = _state_dir() / "bandcamp_session.json"
        except ImportError:
            sf = Path.home() / ".local" / "share" / "kamp" / "bandcamp_session.json"

    # Check for DB-exported session fallback
    if not sf.exists():
        tmp_sf = Path("/tmp/kamp_bandcamp_session.json")
        if tmp_sf.exists():
            sf = tmp_sf
        else:
            sys.exit(f"No session file at {sf} — run spike_kamp372_stream.py first")

    print("=" * 60)
    print("KAMP-373 SPIKE: Transport Controls + Bandcamp Streaming")
    print("=" * 60)

    print(f"\nFetching streaming URLs for {ALBUM_URL}...")
    tracks = _fetch_tracks(sf)
    print(f"  Got {len(tracks)} tracks")
    for t in tracks:
        print(f"  [{t['num']:2d}] {t['title']!r}  {t['duration']:.0f}s  formats={t['formats']}")

    if len(tracks) < 2:
        print("Need at least 2 tracks to test next/prev")
        return 1

    mpv = _Mpv()
    results: dict[str, bool] = {}

    try:
        print("\nStarting mpv...")
        mpv.start()
        print("  mpv IPC connected")

        # Test 1: play track 1
        results["play"] = test_play(mpv, tracks[0])
        time.sleep(_PLAY_GAP)

        # Test 2: pause / resume
        results["pause/resume"] = test_pause_resume(mpv)
        time.sleep(_PLAY_GAP)

        # Test 3: seek (the interesting one for streaming)
        results["seek"] = test_seek(mpv, seek_to=45.0)
        time.sleep(_PLAY_GAP)

        # Test 4: next track
        results["next"] = test_next(mpv, tracks[1])
        time.sleep(_PLAY_GAP)

        # Test 5: prev track (back to track 1)
        results["prev"] = test_prev(mpv, tracks[0])
        time.sleep(_PLAY_GAP)

        # Test 6: stop
        results["stop"] = test_stop(mpv)
        time.sleep(1.0)

        # Test 7: resume from stopped state
        results["resume-after-stop"] = test_resume_after_stop(mpv)

    finally:
        mpv.shutdown()

    # Summary
    print("\n" + "=" * 60)
    print("SPIKE SUMMARY — KAMP-373 Transport Controls")
    print("=" * 60)
    all_pass = True
    for action, ok in results.items():
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {action:25s} {status}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print("  → ALL TRANSPORT ACTIONS WORK WITH STREAMING URLS")
        print("  → VERDICT: PASS")
    else:
        print("  → SOME ACTIONS FAILED — inspect output above")
        print("  → VERDICT: PARTIAL / needs investigation")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
