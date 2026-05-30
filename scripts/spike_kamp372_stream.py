#!/usr/bin/env python3
"""KAMP-372 spike: can we stream a Bandcamp album via mpv?

Approach:
  1. Fetch the album page HTML (authenticated, to surface purchased-quality URLs).
  2. Extract TralbumData embedded JSON — contains per-track streaming file URLs.
  3. Also probe the /api/tralbum/2/info endpoint for richer format data.
  4. Feed the first track's URL to mpv to confirm actual playback.

Usage:
    poetry run python scripts/spike_kamp372_stream.py
    poetry run python scripts/spike_kamp372_stream.py --play  # actually plays track 1

Output:
    - /tmp/kamp_spike_372_tralbum.json   — full TralbumData blob for inspection
    - /tmp/kamp_spike_372_api.json       — /api/tralbum/2/info response for comparison
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
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
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


def _load_session(session_file: Path) -> requests.Session:
    """Load Bandcamp cookies and build an authenticated requests.Session."""
    if not session_file.exists():
        sys.exit(
            f"Session file not found: {session_file}\n"
            "Log in to Bandcamp via kamp first, or pass --session-file."
        )
    state = json.loads(session_file.read_text())
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    for cookie in state.get("cookies", []):
        s.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain", ".bandcamp.com"),
            path=cookie.get("path", "/"),
        )
    logged_in = any(c["name"] == "js_logged_in" for c in state.get("cookies", []))
    print(f"  Session loaded: {len(state.get('cookies', []))} cookies, logged_in={logged_in}")
    return s


# ---------------------------------------------------------------------------
# Step 1: fetch album page & extract TralbumData
# ---------------------------------------------------------------------------


def _extract_tralbum_data(html: str) -> dict[str, Any] | None:
    """Extract TralbumData from Bandcamp album page HTML.

    Bandcamp embeds track info as:
        var TralbumData = { ... };
    in a <script> block. The value is valid JSON (with some JS-specific
    literals that we handle).
    """
    # Primary pattern: var TralbumData = {...};
    m = re.search(r"var TralbumData\s*=\s*(\{.*?\});\s*(?:var |</script>)", html, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            print(f"  [warn] TralbumData JSON parse failed: {exc}")

    # Fallback: data-tralbum attribute on any element
    m2 = re.search(r'data-tralbum="([^"]+)"', html)
    if m2:
        import html as html_lib
        try:
            return json.loads(html_lib.unescape(m2.group(1)))
        except json.JSONDecodeError as exc:
            print(f"  [warn] data-tralbum JSON parse failed: {exc}")

    return None


def step1_fetch_album_page(session: requests.Session) -> dict[str, Any] | None:
    print(f"\n[1] GET {ALBUM_URL}")
    resp = session.get(ALBUM_URL, timeout=30)
    print(f"  status={resp.status_code}  content-length={len(resp.text)}")

    if resp.status_code != 200:
        print(f"  ✗ unexpected status; first 500 chars:\n{resp.text[:500]}")
        return None

    blob = _extract_tralbum_data(resp.text)
    if blob is None:
        print("  ✗ TralbumData not found in album page HTML")
        print(f"  First 500 chars of HTML: {resp.text[:500]}")
        return None

    out = Path("/tmp/kamp_spike_372_tralbum.json")
    out.write_text(json.dumps(blob, indent=2))
    print(f"  ✓ TralbumData found — written to {out}")
    print(f"  Top-level keys: {list(blob.keys())}")

    tracks = blob.get("trackinfo", [])
    print(f"  Track count: {len(tracks)}")
    return blob


# ---------------------------------------------------------------------------
# Step 2: inspect streaming URLs per track
# ---------------------------------------------------------------------------


def step2_inspect_tracks(blob: dict[str, Any]) -> list[dict[str, Any]]:
    """Report which streaming formats are available per track."""
    tracks = blob.get("trackinfo", [])
    print(f"\n[2] Inspecting {len(tracks)} track(s) for streaming URLs")

    playable: list[dict[str, Any]] = []
    for i, t in enumerate(tracks):
        title = t.get("title", f"track {i+1}")
        file_data: dict[str, str] = t.get("file") or {}
        duration = t.get("duration", 0)

        formats = list(file_data.keys())
        if formats:
            url_sample = next(iter(file_data.values()))
            print(f"  Track {i+1}: {title!r}")
            print(f"    duration: {duration:.0f}s")
            print(f"    formats: {formats}")
            print(f"    url: {url_sample[:80]}...")
            playable.append({
                "index": i + 1,
                "title": title,
                "duration": duration,
                "file": file_data,
            })
        else:
            # Track with no streaming URL — may be a pre-order or restricted track.
            free_download = t.get("free_download")
            unreleased = t.get("unreleased_track")
            print(f"  Track {i+1}: {title!r} — no streaming URL "
                  f"(free_download={free_download}, unreleased={unreleased})")

    print(f"\n  → {len(playable)} / {len(tracks)} tracks have streaming URLs")
    return playable


# ---------------------------------------------------------------------------
# Step 3: probe /api/tralbum/2/info for richer format data
# ---------------------------------------------------------------------------


def step3_api_probe(blob: dict[str, Any], session: requests.Session) -> None:
    """Probe the tralbum API endpoint to see if authenticated sessions
    expose higher-quality streaming URLs (e.g. mp3-v0, flac).
    """
    tralbum_id = blob.get("id") or blob.get("tralbum_id")
    tralbum_type = blob.get("item_type", "a")  # 'a' = album, 't' = track

    if not tralbum_id:
        print("\n[3] ✗ No tralbum_id found — skipping API probe")
        return

    api_url = f"https://bandcamp.com/api/tralbum/2/info?tralbum_type={tralbum_type}&tralbum_id={tralbum_id}"
    print(f"\n[3] GET {api_url}")
    try:
        resp = session.get(api_url, timeout=20)
        print(f"  status={resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            out = Path("/tmp/kamp_spike_372_api.json")
            out.write_text(json.dumps(data, indent=2))
            print(f"  ✓ API response written to {out}")
            tracks = data.get("trackinfo", [])
            print(f"  Track count from API: {len(tracks)}")
            for t in tracks[:3]:
                file_data = t.get("file") or {}
                print(f"    {t.get('title')!r}: formats={list(file_data.keys())}")
        else:
            print(f"  ✗ API returned {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:
        print(f"  ✗ API probe failed: {exc}")


# ---------------------------------------------------------------------------
# Step 4: attempt mpv playback of first track URL
# ---------------------------------------------------------------------------


def step4_play_with_mpv(track: dict[str, Any], fmt: str = "mp3-128") -> bool:
    """Feed the track's streaming URL to mpv (5-second preview).

    We spawn mpv as a subprocess rather than using the IPC engine so this
    spike runs standalone without the full kamp daemon.
    """
    file_data: dict[str, str] = track["file"]
    url = file_data.get(fmt) or next(iter(file_data.values()), None)
    if not url:
        print(f"  ✗ No URL for format {fmt!r}")
        return False

    print(f"\n[4] mpv playback test")
    print(f"  Track: {track['title']!r}")
    print(f"  Format: {fmt}")
    print(f"  URL: {url[:100]}...")

    mpv_bin = "mpv"
    cmd = [
        mpv_bin,
        "--no-video",
        "--really-quiet",
        "--length=5",  # play only 5 seconds for the spike
        url,
    ]
    print(f"  Running: {' '.join(cmd[:4])} <url>")
    try:
        result = subprocess.run(cmd, timeout=30)
        if result.returncode == 0:
            print("  ✓ mpv exited cleanly — streaming URL is playable!")
            return True
        else:
            print(f"  ✗ mpv exited with code {result.returncode}")
            return False
    except FileNotFoundError:
        print("  ✗ mpv not found on PATH — install it first")
        return False
    except subprocess.TimeoutExpired:
        print("  ✗ mpv timed out (30s) — URL may be unreachable")
        return False
    except Exception as exc:
        print(f"  ✗ mpv error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Step 5: check if mpv accepts URL directly via loadfile IPC
# ---------------------------------------------------------------------------


def step5_ipc_loadfile_test(track: dict[str, Any]) -> None:
    """Verify that the mpv IPC 'loadfile' command accepts a URL string.

    The existing MpvPlaybackEngine.play() takes a Path. For streaming, we'd
    need to pass a URL string instead. This test confirms mpv's IPC accepts
    that without modification.
    """
    import shutil
    import socket
    import tempfile

    file_data: dict[str, str] = track["file"]
    url = next(iter(file_data.values()), None)
    if not url:
        print("\n[5] ✗ No URL available for IPC test")
        return

    tmpdir = tempfile.mkdtemp(prefix="kamp-spike-")
    sock_path = os.path.join(tmpdir, "mpv.sock")

    print(f"\n[5] mpv IPC loadfile test (via Unix socket)")
    print(f"  Spawning mpv idle with IPC socket at {sock_path}")

    proc = subprocess.Popen(
        ["mpv", "--no-video", "--idle=yes", "--really-quiet",
         f"--input-ipc-server={sock_path}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for the socket to appear
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if Path(sock_path).exists():
                break
            time.sleep(0.1)
        else:
            print("  ✗ mpv IPC socket did not appear within 5s")
            return

        # Connect and send a loadfile command with the URL
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # type: ignore[attr-defined]
        sock.connect(sock_path)
        cmd = json.dumps({"command": ["loadfile", url, "replace"]}) + "\n"
        sock.sendall(cmd.encode())
        time.sleep(1.0)  # give mpv a moment to respond

        # Read response
        sock.settimeout(2.0)
        try:
            resp_bytes = sock.recv(4096)
            resp_text = resp_bytes.decode(errors="replace")
            print(f"  mpv IPC response: {resp_text[:200]}")

            if '"error":"success"' in resp_text:
                print("  ✓ mpv IPC accepted the URL via loadfile — no code changes needed for URL support!")
            else:
                print("  ? Unexpected IPC response (check full response above)")
        except socket.timeout:
            print("  ? IPC recv timed out — mpv may be loading (not necessarily an error)")

        sock.close()

        # Check if mpv is actually playing by querying time-pos
        time.sleep(2.0)
        sock2 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # type: ignore[attr-defined]
        sock2.connect(sock_path)
        q_cmd = json.dumps({"command": ["get_property", "time-pos"]}) + "\n"
        sock2.sendall(q_cmd.encode())
        sock2.settimeout(2.0)
        try:
            resp2 = sock2.recv(4096).decode(errors="replace")
            print(f"  time-pos query: {resp2[:200]}")
            if '"data":' in resp2 and '"error":"success"' in resp2:
                data = json.loads(resp2.strip().split("\n")[0])
                pos = data.get("data")
                if pos is not None and float(pos) > 0:
                    print(f"  ✓ mpv is playing URL — time-pos={pos:.2f}s")
                elif pos == 0.0:
                    print("  ? time-pos=0.0 — may still be buffering")
                else:
                    print(f"  ? time-pos={pos} — unexpected")
        except (socket.timeout, json.JSONDecodeError) as exc:
            print(f"  ? time-pos query failed: {exc}")
        sock2.close()

    finally:
        proc.terminate()
        proc.wait(timeout=5)
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="KAMP-372 spike: Bandcamp streaming")
    parser.add_argument(
        "--session-file",
        type=Path,
        default=None,
        help="Path to bandcamp_session.json (default: kamp state dir)",
    )
    parser.add_argument(
        "--play",
        action="store_true",
        help="Actually play the first track for 5 seconds via mpv",
    )
    parser.add_argument(
        "--ipc-test",
        action="store_true",
        help="Test mpv IPC loadfile with URL (verifies no engine changes needed)",
    )
    args = parser.parse_args()

    # Resolve session file
    if args.session_file:
        sf = args.session_file
    else:
        try:
            from kamp_daemon.config import _state_dir
            sf = _state_dir() / "bandcamp_session.json"
        except ImportError:
            sf = Path.home() / ".local" / "share" / "kamp" / "bandcamp_session.json"

    print("=" * 60)
    print("KAMP-372 SPIKE: Bandcamp Streaming Feasibility")
    print("=" * 60)
    print(f"Album: {ALBUM_URL}")
    print(f"Session: {sf}")

    session = _load_session(sf)

    # Step 1: fetch album page
    blob = step1_fetch_album_page(session)
    if blob is None:
        print("\n✗ SPIKE FAILED at step 1")
        return 1

    # Step 2: inspect tracks
    playable = step2_inspect_tracks(blob)
    if not playable:
        print("\n✗ No playable tracks found — streaming may require purchase or login")
        return 2

    # Step 3: API probe
    step3_api_probe(blob, session)

    # Step 4: optional mpv playback
    if args.play:
        ok = step4_play_with_mpv(playable[0])
    else:
        ok = True
        print(f"\n[4] Skipped mpv playback (pass --play to test)")

    # Step 5: IPC loadfile test
    if args.ipc_test:
        step5_ipc_loadfile_test(playable[0])
    else:
        print(f"[5] Skipped IPC test (pass --ipc-test to verify engine compatibility)")

    # Summary
    print("\n" + "=" * 60)
    print("SPIKE SUMMARY")
    print("=" * 60)
    print(f"  Album page fetch:        ✓")
    print(f"  TralbumData extraction:  ✓")
    print(f"  Playable tracks found:   {len(playable)}/{len(blob.get('trackinfo', []))}")
    formats_seen: set[str] = set()
    for t in playable:
        formats_seen.update(t["file"].keys())
    print(f"  Streaming formats:       {sorted(formats_seen)}")
    if args.play:
        print(f"  mpv direct play:         {'✓ PASS' if ok else '✗ FAIL'}")
    print(f"\n  Inspect JSON dumps:")
    print(f"    /tmp/kamp_spike_372_tralbum.json")
    print(f"    /tmp/kamp_spike_372_api.json")
    print()
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
